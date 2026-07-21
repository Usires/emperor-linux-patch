#!/usr/bin/env python3
"""
Emperor: Battle for Dune — Linux/Proton Compatibility Patch
============================================================

Patches Game.exe (4 code patches) and resource.cfg (8 CD-path patches)
so the game runs under Linux/Wine/Proton without the original CDs.

What this DOES:
  - Makes the per-CD-switch check (fired during campaign play when the
    game asks for CD2/CD3/CD4) always report "CD present", so the
    per-CD lookups resolve to your local data/ tree instead of failing
    the mission-load.

What this does NOT do:
  - Remove the initial CD-check at startup. The official 1.09 patch
    (EM109DE.exe) already does that. Apply it first, or this script
    will refuse to run (MD5 check on Game.exe).

Prerequisites:
  - The official 1.09 patch (EM109DE.exe) has been applied
    → PATCHW32.DLL is at the 1.09 release
    → EMPEROR.EXE is byte-identical to the Westwood original
  - The four mission-data files (DIALOG.BAG, MOVIES0001.RFD,
    MOVIES0001.RFH, MUSIC.BAG) have been extracted from each of CD2,
    CD3, and CD4 into a local data/CD2/, data/CD3/, data/CD4/ tree.
    The filenames are identical on all three CDs.

We do NOT touch:
  - EMPEROR.EXE (stays byte-identical to the Westwood original)
  - PATCHW32.DLL (stays at 1.09 release)
  - PATCHGET.DAT (unchanged)

Usage:
  python3 scripts/emperor_linux_patch.py <game-directory>

Example:
  python3 scripts/emperor_linux_patch.py ~/Games/Emperor_FAUGUS/

Result:
  - Game.exe.original.bak         (backup, first run only)
  - resource.cfg.original.bak     (backup, first run only)
  - Game.exe                      (4 code patches applied)
  - resource.cfg                  (8 CD paths redirected)

Idempotent: already-patched files are detected and skipped.

By Nix & Dirk, 2026. MIT License.
"""

import hashlib
import shutil
import struct
import sys
from pathlib import Path


# === Expected original MD5 of Game.exe ===
# Westwood-Original (1.09-Patch-Stand). Wenn die MD5 der Game.exe im
# Target directory does not match — script aborts: either wrong
# game directory or already patched.
GAME_EXE_EXPECTED_MD5 = "7dc4fda2f6b7e8a6b70e846686a81938"


# === Game.exe Patches ===
# Four code patches that make the per-CD-switch check (fired during
# campaign play when the game asks for CD2/CD3/CD4) always answer
# "CD present". The check still runs; we just lie to it.
#
# The official 1.09 patch already removes the *initial* CD-check at
# startup. These patches address the per-CD-switch check that fires
# mid-campaign, which 1.09 does NOT fix.
#
# The offsets were verified via ghidra disassembly of Game.exe at
# the 1.09-patch state.
GAME_PATCHES = [
    {
        "name":   "Patch 1: per-CD switch check 1 (jne → NOP)",
        "desc":   "Per-CD check 1: 'wrong CD' jump NOP'd → always 'present'",
        "offset": 0x9668f,
        "from":   bytes.fromhex("29020000"),
        "to":     bytes.fromhex("00000000"),
    },
    {
        "name":   "Patch 2: per-CD switch check 2 (je → NOP)",
        "desc":   "Per-CD check 2: 'wrong CD' jump NOP'd → always 'present'",
        "offset": 0x966c4,
        "from":   bytes.fromhex("da010000"),
        "to":     bytes.fromhex("00000000"),
    },
    {
        "name":   "Patch 3: per-CD switch check 3 (je → jmp + NOP)",
        "desc":   "Per-CD check 3: conditional jump flipped to unconditional",
        "offset": 0x96731,
        "from":   bytes.fromhex("0f8492010000"),
        "to":     bytes.fromhex("e99301000090"),
    },
    {
        "name":   "Patch 4: per-CD switch check 4 (xor al,al → mov al,1)",
        "desc":   "Per-CD check 4: return value forced to 'success'",
        "offset": 0x968bf,
        "from":   bytes.fromhex("32c0"),
        "to":     bytes.fromhex("b001"),
    },
]


# === resource.cfg Patches ===
# For each CD/MOVIES key, force the path to a known-good local layout,
# regardless of what the user's resource.cfg currently contains. This
# is robust against:
#   - Wine/Proton mapping CD/DVD drives to arbitrary letters
#   - Installers that pre-configure the paths (some set CD1=D:\,
#     some set CD2=data\CD2 already, some keep Westwood defaults)
#   - Users who manually edited the file to point at their setup
#
# Targets follow the reference layout used by the FAUGUS installer:
#   CD1     → D:\           (DVD drive letter; not actually read because
#                            the EXE patch overrides the CD struct,
#                            but we keep it as a sensible default)
#   CD2-4   → data\CD2-4    (mission data already extracted locally)
#   MOVIES1 → D:\Movies     (same reasoning as CD1)
#   MOVIES2-4 → data\CD2-4\Movies  (per-campaign movie lookup)
#
# The actual data files (DIALOG.BAG, MOVIES0001.RFD/RFH, MUSIC.BAG)
# are not provided here — users must extract them from their legally
# owned copies of CD2/CD3/CD4 into data/CD2/, data/CD3/, data/CD4/.
# CRLF line endings are preserved (Westwood's parser is strict).
#
# Patch semantics: each entry is (key, replacement). The patcher
# replaces whatever path sits under `key` with `replacement`. Already-
# patched entries are detected and skipped (idempotent).
RESOURCE_CFG_PATCHES = [
    ("MOVIES1", "D:\\Movies"),
    ("MOVIES2", "data\\CD2\\Movies"),
    ("MOVIES3", "data\\CD3\\Movies"),
    ("MOVIES4", "data\\CD4\\Movies"),
    ("CD1",     "D:\\"),
    ("CD2",     "data\\CD2"),
    ("CD3",     "data\\CD3"),
    ("CD4",     "data\\CD4"),
]


# === Helper functions ===

def md5_of_file(path: Path) -> str:
    """Compute the MD5 hash of a file's contents."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def make_backup(target_path: Path) -> Path:
    """Create a backup in the target directory if it does not yet exist.

    Backups use the original filename with a `.original.bak` suffix
    appended (e.g. `Game.exe` → `Game.exe.original.bak`). Existing
    backups are not overwritten.
    """
    backup_path = target_path.with_suffix(target_path.suffix + ".original.bak")
    if backup_path.exists():
        print(f"  ✓ Backup already exists: {backup_path.name}")
        return backup_path
    shutil.copy2(target_path, backup_path)
    print(f"  ✓ Backup created: {backup_path.name}")
    return backup_path


def apply_patches_simple(path: Path, patches: list) -> bool:
    """Apply simple byte patches to a file.

    For each patch: reads bytes at `offset`, checks them against `from`,
    overwrites with `to`. Already-patched locations are skipped. If the
    bytes match neither `from` nor `to`, the function aborts — that
    points at the wrong file or a file that has been modified manually
    in an unexpected way.
    """
    print(f"\n  🔧 Patching {path.name} ({len(patches)} patches):")
    data = bytearray(path.read_bytes())

    for p in patches:
        actual = bytes(data[p["offset"]:p["offset"] + len(p["from"])])
        if actual == p["to"]:
            print(f"    ⊙ {p['name']}: already patched, skipping")
            continue
        if actual != p["from"]:
            print(f"    ❌ {p['name']}: bytes do not match!")
            print(f"       Expected (original): {p['from'].hex()}")
            print(f"       Expected (patched):  {p['to'].hex()}")
            print(f"       Found:               {actual.hex()}")
            return False

        data[p["offset"]:p["offset"] + len(p["to"])] = p["to"]
        print(f"    ✅ {p['name']}: {p['from'].hex()} → {p['to'].hex()}")

    path.write_bytes(data)
    return True


def verify_game(path: Path) -> bool:
    """Check whether Game.exe carries all 4 patches."""
    data = path.read_bytes()
    return all(
        data[p["offset"]:p["offset"] + len(p["to"])] == p["to"]
        for p in GAME_PATCHES
    )


def patch_resource_cfg(path: Path) -> bool:
    """Replace CD paths in resource.cfg according to RESOURCE_CFG_PATCHES.

    Format of resource.cfg:
      <key>                ← key line (e.g. "CD1", "MOVIES3")
      <path>              ← path line (the one we patch)
      (blank line)

    For each (key, replacement) in RESOURCE_CFG_PATCHES we look up the
    line that follows `key` and overwrite it with `replacement`,
    regardless of what the line currently contains. This makes the
    patcher robust against:
      - Wine/Proton mapping CD drives to arbitrary letters
      - Installers that pre-configure CD paths differently from the
        Westwood retail defaults
      - Users who manually edited the file

    Already-patched entries (line already equals `replacement`) are
    skipped. Missing keys are reported as warnings, not errors, so a
    resource.cfg from a stripped-down release can still be partially
    patched.

    The file uses DOS line endings (CRLF). We preserve that style:
    replacements are written with the same EOL suffix as the line we
    overwrite, so the resulting file stays byte-compatible with the
    FAUGUS reference layout.
    """
    print(f"\n  🔧 Patching {path.name} ({len(RESOURCE_CFG_PATCHES)} CD paths):")
    raw = path.read_bytes()

    # Detect EOL style by majority vote:
    # CRLF files have as many \r as \n (every \n has a \r before it).
    # LF-only files have \n with no preceding \r.
    n_crlf = raw.count(b"\r\n")
    n_lf_only = raw.count(b"\n") - n_crlf
    eol = b"\r\n" if n_crlf >= n_lf_only else b"\n"
    eol_label = "CRLF" if eol == b"\r\n" else "LF"
    print(f"    File EOL style: {eol_label} ({n_crlf} CRLF, {n_lf_only} LF-only)")

    lines = raw.splitlines(keepends=True)

    missing = []
    patched = 0
    skipped = 0
    for key, replacement in RESOURCE_CFG_PATCHES:
        # key/replacement are Python strings here; for byte comparison
        # we need latin-1 (1:1 ASCII mapping)
        key_b = key.encode("latin-1")
        replacement_b = replacement.encode("latin-1")

        pending_key = False
        found = False
        for i, line_b in enumerate(lines):
            stripped_b = line_b.rstrip(b"\r\n")
            if pending_key:
                # This is the path line that follows `key`. Replace it,
                # preserving the EOL suffix of the original line.
                if stripped_b == replacement_b:
                    print(f"    ⊙ {key}: already {replacement!r}, skipping")
                    skipped += 1
                else:
                    lines[i] = replacement_b + eol
                    print(f"    ✅ {key}: {stripped_b.decode('latin-1')!r} → {replacement!r}")
                    patched += 1
                pending_key = False
                found = True
                break
            if stripped_b == key_b:
                pending_key = True

        if not found:
            missing.append(key)
            print(f"    ⚠️  {key}: key not found in resource.cfg (skipping)")

    if missing:
        print(f"  ⚠️  {len(missing)} key(s) not present in resource.cfg:")
        for k in missing:
            print(f"      - {k}")

    if patched == 0 and skipped == 0:
        # Nothing to write back, but also nothing verified — treat as
        # failure so the user notices the missing keys.
        return False

    path.write_bytes(b"".join(lines))
    return True


def verify_resource_cfg(path: Path) -> bool:
    """Check whether every CD/MOVIES key in resource.cfg carries its
    expected replacement path.

    Unlike a substring search, this walks key→path pairs so a path
    that happens to appear elsewhere in the file (e.g. as a comment)
    does not produce a false positive.
    """
    raw = path.read_bytes()
    lines = raw.splitlines()
    expected = {k: r.encode("latin-1") for k, r in RESOURCE_CFG_PATCHES}
    pending = None
    found_keys = set()
    for line_b in lines:
        if pending is not None:
            if line_b == expected[pending]:
                found_keys.add(pending)
            pending = None
            continue
        if line_b in (k.encode("latin-1") for k in expected):
            pending = line_b.decode("latin-1")
    # All keys that are *present* in the file must carry the right path.
    # Keys that are simply not present (some retail variants omit
    # MOVIES2-4) are tolerated — they are warnings during patching,
    # not failures here.
    return found_keys == {k for k in expected if any(
        line == k.encode("latin-1") for line in lines
    )}


# === Main logic ===

def patch(game_dir: Path) -> bool:
    """Patch Game.exe + resource.cfg in the target directory. Returns True on success."""
    game_exe = game_dir / "Game.exe"
    resource_cfg = game_dir / "resource.cfg"

    # --- Sanity-Checks ---
    if not game_dir.is_dir():
        print(f"❌ Directory does not exist: {game_dir}")
        return False
    if not game_exe.is_file():
        print(f"❌ Game.exe not found in: {game_dir}")
        return False
    if not resource_cfg.is_file():
        print(f"❌ resource.cfg not found in: {game_dir}")
        return False

    # --- MD5-Check der Game.exe ---
    game_md5 = md5_of_file(game_exe)
    game_ok = False
    if game_md5 == GAME_EXE_EXPECTED_MD5:
        print(f"  ✓ Game.exe MD5 matches: {game_md5} (Westwood original)")
    elif verify_game(game_exe):
        # MD5 doesn't match but the 4 patches are already there — idempotent re-run
        print(f"  ✓ Game.exe already patched (MD5 {game_md5} ≠ original)")
        game_ok = True
    else:
        print(f"❌ Game.exe MD5 does not match AND file is not patched!")
        print(f"   Expected:    {GAME_EXE_EXPECTED_MD5}")
        print(f"   Found:       {game_md5}")
        print(f"   Likely wrong directory or corrupted file.")
        return False

    # --- Create backups ---
    print()
    make_backup(game_exe)
    make_backup(resource_cfg)

    # --- Patch Game.exe ---
    if not game_ok:  # not already flagged as "already patched" above
        if not apply_patches_simple(game_exe, GAME_PATCHES):
            return False

    # --- resource.cfg patchen ---
    if verify_resource_cfg(resource_cfg):
        print(f"\n  ⊙ resource.cfg already patched (all CD paths correct), skipping")
    else:
        if not patch_resource_cfg(resource_cfg):
            return False

    # --- Verification ---
    print("\n  🔍 Verification:")
    print(f"    Game.exe:     {'✅ OK' if verify_game(game_exe) else '❌ FAIL'}")
    print(f"    resource.cfg: {'✅ OK' if verify_resource_cfg(resource_cfg) else '❌ FAIL'}")

    return verify_game(game_exe) and verify_resource_cfg(resource_cfg)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/emperor_linux_patch.py <game-directory>")
        print("Example:   python3 scripts/emperor_linux_patch.py ~/Games/Emperor_FAUGUS/")
        sys.exit(1)

    game_dir = Path(sys.argv[1]).expanduser().resolve()

    print(f"🎮 Emperor: Battle for Dune — Linux/Proton Compatibility Patch")
    print(f"   Target: {game_dir}")
    print()

    ok = patch(game_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
