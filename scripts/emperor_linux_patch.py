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
# Maps the 8 original CD paths (E:\, D:\, .\cd3\, .\cd4\) to a local
# data/ directory layout. The actual data files (DIALOG.BAG,
# MOVIES0001.RFD/RFH, MUSIC.BAG) are not provided here — users must
# extract them from their legally owned copies of CD2/CD3/CD4.
# CRLF line endings are preserved (Westwood's parser is strict).
RESOURCE_CFG_PATCHES = [
    ("MOVIES1", "E:\\Movies",  "D:\\Movies"),
    ("MOVIES2", "E:\\Movies",  "data\\CD2\\Movies"),
    ("MOVIES3", "E:\\Movies",  "data\\CD3\\Movies"),
    ("MOVIES4", "E:\\Movies",  "data\\CD4\\Movies"),
    ("CD1",     "E:\\",        "D:\\"),
    ("CD2",     "D:\\",        "data\\CD2"),
    ("CD3",     ".\\cd3\\",    "data\\CD3"),
    ("CD4",     ".\\cd4\\",    "data\\CD4"),
]


# === Hilfsfunktionen ===

def md5_of_file(path: Path) -> str:
    """Berechne MD5-Hash einer Datei."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def make_backup(target_path: Path) -> Path:
    """Create a backup in the target directory if it does not yet exist.

    Backups heißen wie die Original-Datei mit .original.bak-Suffix.
    Existing backups are not overwritten.
    """
    backup_path = target_path.with_suffix(target_path.suffix + ".original.bak")
    if backup_path.exists():
        print(f"  ✓ Backup already exists: {backup_path.name}")
        return backup_path
    shutil.copy2(target_path, backup_path)
    print(f"  ✓ Backup created: {backup_path.name}")
    return backup_path


def apply_patches_simple(path: Path, patches: list) -> bool:
    """Wende einfache Byte-Patches auf eine Datei an.

    Pro Patch: liest die Bytes an `offset`, prüft gegen `from`,
    overwrites with `to`. Already-patched locations are skipped.
    Bei Mismatch (Bytes passen weder zu `from` noch zu `to`) wird
    abgebrochen — das deutet auf falsche Datei oder bereits manuell
    veränderte Datei hin.
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
    """Prüfe, ob Game.exe alle 4 Patches trägt."""
    data = path.read_bytes()
    return all(
        data[p["offset"]:p["offset"] + len(p["to"])] == p["to"]
        for p in GAME_PATCHES
    )


def patch_resource_cfg(path: Path) -> bool:
    """Ersetze CD-Pfade in resource.cfg gemäß RESOURCE_CFG_PATCHES.

    Format der resource.cfg:
      <Schluessel>          ← Schlüsselzeile (z.B. "CD1", "MOVIES3")
      <Pfad>                ← Pfad-Zeile (die wir patchen wollen)
      (leerzeile)

    Die Datei benutzt DOS-Zeilenenden (CRLF). Wir erhalten den Stil
    exakt — Pfad-Ersetzungen werden mit dem gleichen EOL-Suffix wie
    die Original-Zeile geschrieben, damit die resultierende Datei
    byte-konform zur HYBRID-Referenz ist.
    """
    print(f"\n  🔧 Patching {path.name} ({len(RESOURCE_CFG_PATCHES)} CD paths):")
    raw = path.read_bytes()

    # EOL-Stil robust ermitteln: Mehrheits-Vote.
    # CRLF-Dateien haben genauso viele \r wie \n (jedes \n hat ein \r davor).
    # LF-only-Dateien haben \n ohne \r davor.
    n_crlf = raw.count(b"\r\n")
    n_lf_only = raw.count(b"\n") - n_crlf
    eol = b"\r\n" if n_crlf >= n_lf_only else b"\n"
    eol_label = "CRLF" if eol == b"\r\n" else "LF"
    print(f"    File EOL style: {eol_label} ({n_crlf} CRLF, {n_lf_only} LF-only)")

    lines = raw.splitlines(keepends=True)

    errors = []
    patched = 0
    for key, original, replacement in RESOURCE_CFG_PATCHES:
        # key/original/replacement sind hier Python-strings; für Byte-Vergleich
        # brauchen wir latin-1 (1:1 ASCII-Mapping)
        key_b = key.encode("latin-1")
        original_b = original.encode("latin-1")
        replacement_b = replacement.encode("latin-1")

        pending_key = None
        found = False
        for i, line_b in enumerate(lines):
            stripped_b = line_b.rstrip(b"\r\n")
            if stripped_b == key_b:
                pending_key = key_b
                continue
            if pending_key == key_b and stripped_b == original_b:
                # Patch diese Zeile: Pfad durch Replacement ersetzen, EOL erhalten
                lines[i] = replacement_b + eol
                pending_key = None
                found = True
                print(f"    ✅ {key}: {original!r} → {replacement!r}")
                patched += 1
                break
        if not found:
            errors.append((key, original))
            print(f"    ❌ {key}: 'original={original!r}' not found")

    if errors:
        print(f"  ⚠️  {len(errors)} patch(es) could not be applied:")
        for k, o in errors:
            print(f"      - {k}: {o!r}")
        return False

    path.write_bytes(b"".join(lines))
    return True


def verify_resource_cfg(path: Path) -> bool:
    """Prüfe, ob resource.cfg alle 8 Pfad-Patches trägt."""
    raw = path.read_bytes()
    text = raw.decode("latin-1")
    return all(replacement in text for _, _, replacement in RESOURCE_CFG_PATCHES)


# === Hauptlogik ===

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
        # MD5 passt nicht, aber die 4 Patches sind schon drin → idempotenter Re-Run
        print(f"  ✓ Game.exe already patched (MD5 {game_md5} ≠ original)")
        game_ok = True
    else:
        print(f"❌ Game.exe MD5 does not match AND file is not patched!")
        print(f"   Expected:    {GAME_EXE_EXPECTED_MD5}")
        print(f"   Found:       {game_md5}")
        print(f"   Likely wrong directory or corrupted file.")
        return False

    # --- Backups anlegen ---
    print()
    make_backup(game_exe)
    make_backup(resource_cfg)

    # --- Game.exe patchen ---
    if not game_ok:  # wenn nicht bereits oben als "schon gepatcht" erkannt
        if not apply_patches_simple(game_exe, GAME_PATCHES):
            return False

    # --- resource.cfg patchen ---
    if verify_resource_cfg(resource_cfg):
        print(f"\n  ⊙ resource.cfg already patched (all 8 replacements present), skipping")
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
