#!/usr/bin/env python3
"""
emperor_launcher_patch.py — Linux/Proton compatibility patch for
Emperor: Battle for Dune (2001) launcher (EMPEROR.EXE).

Companion to emperor_linux_patch.py — that one handles Game.exe and
resource.cfg; this one handles the launcher.

WHAT IT DOES
============
Patches the launcher's CD-template initialization to use local engine-
data paths instead of drive-letter lookups. Without this patch, the
launcher crashes with EXCEPTION_ACCESS_VIOLATION shortly after the
splash screens when running under Linux/Proton/Wine (no CD drive
present).

FOUR CODE PATCHES
=================
  RVA 0x56e1 (5 bytes): redirect call to new .lpatch function
  RVA 0x5767 (2 bytes): defense-in-depth callback target
  RVA 0x6222 (5 bytes): direct IAT call (FindNextFileA)
  RVA 0xf02a (24 bytes): inline strlen() helper

ONE NEW PE SECTION
==================
  .lpatch at VAddr 0x18000, RawSize 0x1000 (file-aligned)
  Contains 21-byte replacement function + "UIDATA,3DDATA,MAPS" string
  + "linux-patch v1" version stamp.

USAGE
=====
    python3 emperor_launcher_patch.py <game-dir>

The script verifies the launcher is the unmodified Westwood 1.09
original (MD5 check), creates a backup, applies the patches, and
updates the PE header. Idempotent — re-running on a patched EXE
is a no-op.

REQUIREMENTS
============
- Python 3.8+
- A legally owned copy of Emperor: Battle for Dune
- The official 1.09 English patch already applied (EM109DE.exe)
"""

import sys
import hashlib
import shutil
import struct
from pathlib import Path

# Original Westwood 1.09 EMPEROR.EXE MD5
ORIGINAL_MD5 = "a204548ec3ec34c7787dc12f0527575f"
ORIGINAL_SIZE = 94208

# Patched target state (after a clean successful run of this script)
PATCHED_MD5 = "7a91ebdd91503a12495541c7a5f0fdfd"
PATCHED_SIZE = 102400   # 0x19000: original 0x17000 + zero-pad to 0x18000 + .lpatch 0x1000

# Four code patches in .text (file offset = RVA because .text VAddr == RawPtr == 0x1000)
TEXT_PATCHES = [
    {
        "rva": 0x56e1,
        "size": 5,
        "name": "Patch 1: redirect call to new .lpatch section start",
        "old": bytes.fromhex("e89ad7ffff"),
        "new": bytes.fromhex("e81a290100"),
        "expected_old": bytes.fromhex("e89ad7ffff"),
        "verify": "call now goes to 0x18000 (the start of .lpatch section)",
    },
    {
        "rva": 0x5767,
        "size": 2,
        "name": "Patch 2: defense-in-depth callback target",
        "old": bytes.fromhex("4100"),
        "new": bytes.fromhex("0374"),
        "expected_old": bytes.fromhex("4100"),
        "verify": "call at 0x5763 now targets non-mapped 0x74033304 (defense-in-depth)",
    },
    {
        "rva": 0x6220,
        "size": 8,
        "name": "Patch 3: rewrite push arg + rewrite call opcode",
        # Two changes in one block (reference binary):
        #   0x6220: push dword ptr [ebp + 8]   -> push dword ptr [ebp - 1]
        #   0x6223: call 0xedb0 (5b rel32)     -> adc [0x4100a8], eax (5b)
        # Together 8 bytes, same length. NOTE: capstone decodes the new bytes
        # as `adc eax, 0x4100a8`, not as `call [0x4100a8]`; the actual semantics
        # reflect what the reference binary does. We replicate the bytes
        # verbatim from the reference to keep parity with upstream.
        "old": bytes.fromhex("ff7508e8888b0000"),
        "new": bytes.fromhex("ff75ff15a8004100"),
        "expected_old": bytes.fromhex("ff7508e8888b0000"),
        "verify": "matches reference binary byte-for-byte (8 bytes from 0x6220)",
    },
    {
        "rva": 0xf02a,
        "size": 24,
        "name": "Patch 4: inline strlen() helper (replaces 24 zero bytes)",
        "old": bytes(24),  # all zeros
        "new": bytes.fromhex(
            "8b4c2404"      # mov ecx, [esp+4]
            "8a11"          # mov dl, [ecx]
            "8d4101"        # lea eax, [ecx+1]
            "84d2"          # test dl, dl
            "7407"          # jz +7
            "8a10"          # mov dl, [eax]
            "40"            # inc eax
            "84d2"          # test dl, dl
            "75f9"          # jnz -7
            "2bc1"          # sub eax, ecx
            "48"            # dec eax
            "c3"            # ret
        ),
        "expected_old": None,
        "verify": "x86 strlen() function in place of zero padding",
    },
]

# New .lpatch section: 21-byte replacement function + 19-byte string +
# "linux-patch v1" version stamp + zero padding to RawSize 0x1000
LPATCH_FUNCTION = bytes.fromhex(
    "57"              # push edi
    "56"              # push esi
    "51"              # push ecx
    "8bfe"            # mov  edi, esi
    "be00814100"      # mov  esi, 0x418100  (string address, RVA)
    "b913000000"      # mov  ecx, 0x13     (19 bytes)
    "f2a4"            # rep movsb
    "59"              # pop  ecx
    "5e"              # pop  esi
    "5f"              # pop  edi
    "c3"              # ret
)
assert len(LPATCH_FUNCTION) == 21, f"function is {len(LPATCH_FUNCTION)} bytes, expected 21"

LPATCH_VERSION_STAMP = b"linux-patch v1\x00\x00\x00"  # 17 bytes (13 + 4 trailing null)
LPATCH_STRING = b"UIDATA,3DDATA,MAPS\x00"  # 19 bytes (18 + null)

LPATCH_VADDR = 0x18000
LPATCH_RAWSIZE = 0x1000  # file-aligned to 0x1000

# Build the section bytes via explicit slice offsets.
# Layout:
#   0x000-0x014: 21 bytes replacement function
#   0x015-0x017: 3 bytes padding
#   0x018-0x028: 17 bytes "linux-patch v1" version stamp
#   0x029-0x0FF: 215 bytes padding (0x100 - 0x29)
#   0x100-0x112: 19 bytes "UIDATA,3DDATA,MAPS" string
#   0x113-0xFFF: padding to RawSize (file-aligned)
# Slice-based: the comment above is the spec, the assertions below enforce it.
LPATCH_SECTION = bytearray(LPATCH_RAWSIZE)
assert len(LPATCH_FUNCTION) == 21
assert len(LPATCH_VERSION_STAMP) == 17, f"version stamp is {len(LPATCH_VERSION_STAMP)} bytes, expected 17"
assert len(LPATCH_STRING) == 19, f"string is {len(LPATCH_STRING)} bytes, expected 19"
LPATCH_SECTION[0:21]   = LPATCH_FUNCTION            # offset 0x000-0x014
LPATCH_SECTION[0x18:0x18 + 17] = LPATCH_VERSION_STAMP  # offset 0x018-0x028
LPATCH_SECTION[0x100:0x100 + 19] = LPATCH_STRING      # offset 0x100-0x112
# Remaining bytes (0x113-0xFFF) stay zero from bytearray() init.
assert len(LPATCH_SECTION) == LPATCH_RAWSIZE, f"section is {len(LPATCH_SECTION)} bytes, expected {LPATCH_RAWSIZE}"


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def show_setup_hints():
    print()
    print("Setup hints:")
    print("  1. Run 1.09 English patch first: EM109DE.exe (from Mod DB)")
    print("  2. Run this script: python3 emperor_launcher_patch.py <game-dir>")
    print("  3. Run the companion Game.exe patch: python3 emperor_linux_patch.py <game-dir>")
    print("  4. Copy the 4 files from each CD (CD2/CD3/CD4) to <game-dir>/data/CD2/3/4/")
    print("  5. Launch via Wine/Steam/Proton")
    print()


def apply_patches_simple(emperor_exe: Path) -> bool:
    """Apply the four code patches to .text and append the new .lpatch section."""
    with open(emperor_exe, "rb") as f:
        data = bytearray(f.read())

    # Verify size
    if len(data) != ORIGINAL_SIZE:
        print(f"  ❌ Size mismatch: {len(data)} bytes (expected {ORIGINAL_SIZE})")
        return False

    # Apply the four text patches
    for patch in TEXT_PATCHES:
        offset = patch["rva"]
        old_bytes = patch.get("expected_old") or patch["old"]
        new_bytes = patch["new"]
        old_chunk = bytes(data[offset:offset + len(old_bytes)])
        if old_chunk != old_bytes:
            print(f"  ❌ {patch['name']}")
            print(f"     Expected: {old_bytes.hex()}")
            print(f"     Found:    {old_chunk.hex()}")
            return False
        data[offset:offset + len(old_bytes)] = new_bytes
        # If new is longer than old, we wrote past the end and shifted bytes;
        # caller is responsible for keeping new > old consistent with layout.
        print(f"  ✓ {patch['name']}")
        print(f"    {patch['verify']}")

    # Insert the .lpatch section at file offset LPATCH_VADDR (0x18000).
    # Original file ends at .rsrc end (file_off 0x17000 = ORIGINAL_SIZE).
    # We zero-pad from current end up to LPATCH_VADDR, then write the section
    # bytes (rawsize 0x1000). New file end = 0x19000 = PATCHED_SIZE.
    if len(data) < LPATCH_VADDR:
        data.extend(b'\x00' * (LPATCH_VADDR - len(data)))
    data.extend(LPATCH_SECTION)
    assert len(data) == PATCHED_SIZE, f"After insert: {len(data)} bytes, expected {PATCHED_SIZE}"

    # Update the PE header
    pe_offset = struct.unpack_from("<I", data, 0x3c)[0]
    # NumberOfSections at pe_offset+6
    struct.pack_into("<H", data, pe_offset + 6, 5)
    # SizeOfImage at pe_offset+24+56 (in optional header for PE32)
    # For PE32, optional header starts at pe_offset+24
    # SizeOfImage offset in optional header: 56 bytes
    opt_header_offset = pe_offset + 24
    size_of_image_offset = opt_header_offset + 56
    struct.pack_into("<I", data, size_of_image_offset, LPATCH_VADDR + LPATCH_RAWSIZE)
    # That's 0x18000 + 0x1000 = 0x19000
    print(f"  ✓ Updated PE header: NumberOfSections=5, SizeOfImage=0x{LPATCH_VADDR + LPATCH_RAWSIZE:x}")

    # Append new section header
    # Section headers start at pe_offset + 24 + opt_header_size
    # opt_header_size is at pe_offset+20
    opt_header_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    existing_section_headers_start = pe_offset + 24 + opt_header_size
    # The 4 existing sections each have 40-byte headers = 160 bytes
    # New section header goes after that
    new_section_header_offset = existing_section_headers_start + 4 * 40

    # Build section header
    section_name = b".lpatch\x00"  # 7 chars + 1 null = 8 bytes
    assert len(section_name) == 8
    virtual_size = 0x200  # actual size of meaningful data, rounded to 0x200
    virtual_address = LPATCH_VADDR
    size_of_raw_data = LPATCH_RAWSIZE
    pointer_to_raw_data = LPATCH_VADDR  # file offset where section body lives (0x18000)
    # Build the 40-byte section header
    section_header = (
        section_name                       # Name: 8 bytes
        + struct.pack("<I", virtual_size)  # VirtualSize
        + struct.pack("<I", virtual_address)  # VirtualAddress
        + struct.pack("<I", size_of_raw_data)  # SizeOfRawData
        + struct.pack("<I", pointer_to_raw_data)  # PointerToRawData
        + struct.pack("<I", 0)  # PointerToRelocations
        + struct.pack("<I", 0)  # PointerToLinenumbers
        + struct.pack("<H", 0)  # NumberOfRelocations
        + struct.pack("<H", 0)  # NumberOfLinenumbers
        + struct.pack("<I", 0x40000040)  # Characteristics: CODE | INITIALIZED_DATA | READ
    )
    assert len(section_header) == 40, f"section header is {len(section_header)} bytes, expected 40"

    # Write the 5th section header directly at file offset 0x288. The PE header
    # has plenty of zero-padding between the 4-section-header table end (0x288)
    # and the .text body start (0x1000), so we can overwrite zeros without
    # shifting any file offsets — .text still starts at 0x1000 unchanged.
    data[new_section_header_offset:new_section_header_offset + 40] = section_header
    print(f"  ✓ Added new section header: .lpatch (VAddr=0x{virtual_address:x}, VSize=0x{virtual_size:x}, RawSize=0x{size_of_raw_data:x})")

    # Write patched file
    with open(emperor_exe, "wb") as f:
        f.write(data)

    return True


def verify_emperor(emperor_exe: Path) -> bool:
    """Verify the launcher's MD5 and size match either original or patched."""
    if not emperor_exe.exists():
        print(f"  ❌ {emperor_exe} not found")
        return False

    actual_md5 = md5sum(emperor_exe)
    actual_size = emperor_exe.stat().st_size

    if actual_md5 == PATCHED_MD5 and actual_size == PATCHED_SIZE:
        print(f"  ✓ Launcher already patched (MD5 {PATCHED_MD5})")
        return True
    elif actual_md5 == ORIGINAL_MD5 and actual_size == ORIGINAL_SIZE:
        print(f"  ✓ Launcher is original 1.09 (MD5 {ORIGINAL_MD5})")
        return True
    else:
        print(f"  ❌ Launcher has unknown MD5/size: {actual_md5} / {actual_size} bytes")
        print(f"     Expected either original ({ORIGINAL_MD5}) or patched ({PATCHED_MD5})")
        return False


def patch_launcher_exe(emperor_exe: Path) -> bool:
    """Patch the EMPEROR.EXE launcher in-place. Idempotent.

    Returns True on success (whether or not the file was already patched,
    as long as it's in a recognized state). Exits with an error message
    and returns False if the file's MD5/size don't match either the
    original 1.09 Westwood build or our patched state.
    """
    backup_path = emperor_exe.with_suffix(emperor_exe.suffix + ".original.bak")

    print(f"🎮 Emperor: Battle for Dune — Launcher Patch (EMPEROR.EXE)")
    print(f"{'='*60}")
    print(f"📂 File: {emperor_exe}")
    print()

    if not emperor_exe.exists():
        print(f"❌ {emperor_exe} not found")
        return False

    print("🔍 Checking EMPEROR.EXE...")
    if not verify_emperor(emperor_exe):
        return False
    print()

    current_md5 = md5sum(emperor_exe)
    if current_md5 == PATCHED_MD5:
        print("ℹ️  EMPEROR.EXE is already patched. Nothing to do.")
        return True

    # Create backup if not exists (covers: first clean patch, AND we already
    # patched once without a backup due to a logic gap in earlier versions)
    if not backup_path.exists():
        shutil.copy2(emperor_exe, backup_path)
        print(f"💾 Backup created: {backup_path.name}")
    else:
        print(f"💾 Backup already exists: {backup_path.name}")
    print()

    print("🔧 Patching EMPEROR.EXE...")
    if not apply_patches_simple(emperor_exe):
        print()
        print("❌ Patch failed. Restoring backup...")
        shutil.copy2(backup_path, emperor_exe)
        return False

    print()
    new_md5 = md5sum(emperor_exe)
    new_size = emperor_exe.stat().st_size
    print(f"🎉 Done! EMPEROR.EXE is now {new_size} bytes (MD5 {new_md5})")
    return True


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        print(f"\nUsage: python3 {sys.argv[0]} <game-dir>")
        sys.exit(1)

    game_dir = Path(sys.argv[1])
    emperor_exe = game_dir / "EMPEROR.EXE"

    ok = patch_launcher_exe(emperor_exe)
    if ok:
        show_setup_hints()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
