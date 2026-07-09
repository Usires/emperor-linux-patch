#!/usr/bin/env python3
"""
emperor.py — Emperor: Battle for Dune — unified patcher CLI.

Orchestrates the two phase-specific scripts and adds a rollback path.

USAGE
=====
  python3 emperor.py patch    <game-dir>
  python3 emperor.py rollback <game-dir>
  python3 emperor.py status   <game-dir>

WHAT GETS PATCHED
=================
  Game.exe        (per-CD-switch checks → 4 code patches)
  resource.cfg    (8 CD paths → local data/ tree)
  EMPEROR.EXE     (launcher: 4 code patches + .lpatch section)

These are the same patches as the standalone scripts:
  scripts/emperor_linux_patch.py       (Game.exe + resource.cfg)
  scripts/emperor_launcher_patch.py    (EMPEROR.EXE)

Both scripts can still be invoked directly; this CLI is a thin wrapper.

ROLLBACK
========
  Restores every *.original.bak in <game-dir> to its original name.
  No user-data (data/CD2/, data/CD3/, data/CD4/, saves, etc.) is touched.
  Backups that don't exist for a given file are skipped silently.

BY NIX & DIRK, 2026. MIT LICENSE.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))


# Files we patched or could have patched. Each maps to its backup suffix.
# If we ever add a phase, extend this list and update both scripts.
MANAGED_FILES = [
    ("Game.exe",       "Game.exe.original.bak"),
    ("resource.cfg",   "resource.cfg.original.bak"),
    ("EMPEROR.EXE",    "EMPEROR.EXE.original.bak"),  # matches launcher script's with_suffix naming
]


# === Helpers ===

def banner(label: str) -> None:
    print()
    print("=" * 60)
    print(f"  {label}")
    print("=" * 60)


def run_phase(phase_name: str, fn, *args, **kwargs) -> bool:
    """Run a phase function, catch exceptions, return True on clean success."""
    banner(phase_name)
    try:
        return bool(fn(*args, **kwargs))
    except Exception as exc:
        print(f"❌ {phase_name} raised: {type(exc).__name__}: {exc}")
        return False


def discover_backup(target: Path, backup_name: str) -> Path | None:
    """Return backup path if it exists next to target; else None.

    Looks up case-insensitively on Linux to be forgiving — Westwood games use
    mixed case ('EMPEROR.EXE' vs 'Game.exe'), and the launcher script writes
    'EMPEROR.EXE.original.bak' which we mirror here for consistency.
    """
    parent = target.parent
    # Exact match first
    exact = parent / backup_name
    if exact.is_file():
        return exact
    # Case-insensitive fallback for Linux filesystems
    target_lower = backup_name.lower()
    for candidate in parent.iterdir():
        if candidate.name.lower() == target_lower and candidate.is_file():
            return candidate
    return None


# === Subcommand: patch ===

def cmd_patch(game_dir: Path) -> int:
    from emperor_linux_patch import patch as patch_game_and_cfg
    from emperor_launcher_patch import patch_launcher_exe

    if not game_dir.is_dir():
        print(f"❌ Game directory does not exist: {game_dir}")
        return 1

    ok_game = run_phase("Phase 1/2: Game.exe + resource.cfg", patch_game_and_cfg, game_dir)
    ok_launcher = run_phase(
        "Phase 2/2: EMPEROR.EXE launcher",
        patch_launcher_exe,
        game_dir / "EMPEROR.EXE",
    )

    banner("Summary")
    print(f"  Game.exe + resource.cfg:    {'✅ patched (or already patched)' if ok_game else '❌ FAIL'}")
    print(f"  EMPEROR.EXE launcher:       {'✅ patched (or already patched)' if ok_launcher else '❌ FAIL'}")
    print()
    if ok_game and ok_launcher:
        print("🎉 Both phases are clean. Launch Emperor via Wine/Proton.")
        return 0
    print("⚠️  At least one phase failed; check output above. Idempotent re-runs are safe.")
    return 2


# === Subcommand: rollback ===

def cmd_rollback(game_dir: Path) -> int:
    if not game_dir.is_dir():
        print(f"❌ Game directory does not exist: {game_dir}")
        return 1

    print(f"🗑  Rolling back patches in: {game_dir}")
    print()

    restored = 0
    already_clean = 0
    for filename, backup_name in MANAGED_FILES:
        target = game_dir / filename
        backup = discover_backup(target, backup_name)
        if backup is None:
            print(f"  ⊙ {filename}: no backup found ({backup_name}); skipping")
            already_clean += 1
            continue
        if not target.exists():
            print(f"  ⚠️  {filename}: backup exists but target is missing; leaving backup in place")
            continue
        # Restore: copy backup contents over target, leave backup intact for re-checks
        target.write_bytes(backup.read_bytes())
        print(f"  ✅ {filename}: restored from {backup_name}")
        restored += 1

    banner("Rollback summary")
    print(f"  Restored:  {restored}")
    print(f"  No-op:     {already_clean}")
    print()
    if restored:
        print("🎉 Rollback complete. Original binaries are in place.")
        print("   Note: backups (*.original.bak) are preserved so you can re-patch later.")
    else:
        print("ℹ️  Nothing to roll back — game directory was already clean.")
    return 0


# === Subcommand: status ===

def cmd_status(game_dir: Path) -> int:
    if not game_dir.is_dir():
        print(f"❌ Game directory does not exist: {game_dir}")
        return 1

    print(f"📊 Patch status for: {game_dir}")
    print()
    print(f"  {'File':<20} {'Backup':<28} {'State'}")
    print(f"  {'-'*20} {'-'*28} {'-'*20}")
    for filename, backup_name in MANAGED_FILES:
        target = game_dir / filename
        backup = discover_backup(target, backup_name)
        bk = "✅ present" if backup else "—"

        if not target.exists():
            state = "missing"
            print(f"  {filename:<20} {bk:<28} {state}")
            continue

        # Determine state from content first; backup presence is independent info
        from emperor_launcher_patch import ORIGINAL_MD5 as LAUNCHER_ORIG_MD5, PATCHED_MD5 as LAUNCHER_PATCHED_MD5
        from emperor_linux_patch import GAME_EXE_EXPECTED_MD5, md5_of_file
        target_md5 = md5_of_file(target)
        if filename == "EMPEROR.EXE":
            if target_md5 == LAUNCHER_PATCHED_MD5:
                state = "✅ patched (.lpatch applied)"
            elif target_md5 == LAUNCHER_ORIG_MD5:
                state = "○ unpatched (Westwood original 1.09)"
            else:
                state = f"❓ unknown (md5 {target_md5[:8]}…)"
        elif filename == "Game.exe":
            if target_md5 == GAME_EXE_EXPECTED_MD5:
                state = "○ unpatched (Westwood original)"
            else:
                state = f"✅ patched (md5 {target_md5[:8]}…)"
        elif filename == "resource.cfg":
            # Cheap heuristic: did we already substitute any path?
            raw = target.read_bytes()
            if b"data\\CD2" in raw or b"data/CD2" in raw:
                state = "✅ patched (CD paths redirected)"
            elif b"D:\\" in raw or b"E:\\" in raw:
                state = "○ unpatched (still has CD-path keys)"
            else:
                state = "❓ unknown"
        else:
            state = "—"
        print(f"  {filename:<20} {bk:<28} {state}")

    return 0


# === CLI ===

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="emperor.py",
        description="Emperor: Battle for Dune — unified patcher CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("patch", help="apply both Game.exe + EMPEROR.EXE patches (idempotent)")
    p.add_argument("game_dir", type=Path, help="path to the Emperor game directory")

    r = sub.add_parser("rollback", help="restore originals from *.original.bak backups")
    r.add_argument("game_dir", type=Path, help="path to the Emperor game directory")

    s = sub.add_parser("status", help="show current patch state of the game directory")
    s.add_argument("game_dir", type=Path, help="path to the Emperor game directory")

    args = parser.parse_args(argv)
    game_dir = args.game_dir.expanduser().resolve()

    if args.command == "patch":
        return cmd_patch(game_dir)
    if args.command == "rollback":
        return cmd_rollback(game_dir)
    if args.command == "status":
        return cmd_status(game_dir)
    parser.error(f"unknown subcommand: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
