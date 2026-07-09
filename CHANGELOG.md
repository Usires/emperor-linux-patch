# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`scripts/emperor_launcher_patch.py`** — launcher (`EMPEROR.EXE`) patcher.
  Applies 4 code patches in `.text` (offsets `0x56e1`, `0x5763`, `0x6220`,
  `0xf02a`) and appends a `.lpatch` PE section carrying a 21-byte
  replacement function, a 24-byte inline `strlen`, a version stamp, and
  a CD-path string. Together these make the launcher load local CD-data
  under Wine/Proton without a CD drive.
- **`scripts/emperor.py`** — unified dispatcher with three subcommands:
  - `python3 emperor.py patch <game-dir>` runs both phases
    (`Game.exe` + `resource.cfg` and now the launcher); idempotent, safe
    to re-run.
  - `python3 emperor.py rollback <game-dir>` restores every
    `*.original.bak` file in the game directory to its original name.
    User data (`data/CD*/`, saves, INI edits) is never touched.
  - `python3 emperor.py status <game-dir>` prints a per-file state table
    (file / backup presence / patched-or-not).
- The launcher patcher creates `EMPEROR.EXE.original.bak` on first clean
  patch (fixing a pre-existing gap where re-runs skipped the backup step).
- Standalone scripts are still usable directly: `python3 scripts/emperor_linux_patch.py <dir>`
  patches only `Game.exe` + `resource.cfg`, `python3 scripts/emperor_launcher_patch.py <dir>`
  patches only `EMPEROR.EXE`. The dispatcher is just glue.

### Design notes
- **Two phases, one rollback.** The dispatcher treats the game directory
  as a unit: a single `rollback` restores all three binaries; a single
  `patch` makes sure all three are present. This avoids the failure mode
  where users get half-patched state because one phase errored out.
- **Backups are intentionally not auto-deleted.** `--rollback` overwrites
  the patched files in place but leaves `*.original.bak` on disk, so a
  re-patch never strands a user with no fallback.
- **Section name `.lpatch` instead of upstream's `.tomcraft`.** The
  four code patches reproduce the upstream layout byte-for-byte (so the
  bytes are interchangeable), but the section name and version stamp
  differ so a user (or future debugger) can tell at a glance which
  patcher produced the binary.

## [0.1.0] — 2026-07-08

### Added
- **`scripts/emperor_linux_patch.py`** — single-file Python patcher
  (no third-party dependencies). Patches `Game.exe` (4 instructions at
  `0x9668f`, `0x966c4`, `0x96731`, `0x968bf`) and `resource.cfg` (8
  CD-path replacements) so Emperor: Battle for Dune runs on Linux via
  Wine/Proton without the original discs.
- **MD5 verification** of `Game.exe` against
  `7dc4fda2f6b7e8a6b70e846686a81938` to catch wrong-version or
  already-modified files before patching.
- **Idempotency** — re-running on an already-patched directory detects
  the patched state (`Game.exe` carries the 4 patches; `resource.cfg`
  carries the 8 replacement strings) and skips without re-modifying.
- **Per-file `.original.bak` backups** in the target game directory,
  created only on first run.

### Design notes
- **Two CD-checks, two solutions.** The initial CD-check at startup
  is removed by the official 1.09 patch (`EM109DE.exe`), which also
  fixes community-map bugs. The per-CD-switch check during campaign
  play is what this Linux patcher fixes. Treating them as separate
  problems with separate solutions is essential — if you only fix
  one, the game either doesn't start or crashes mid-campaign.
- **The check is answered, not removed.** We don't NOP out the
  per-CD-switch check. We make it always answer "CD present." Combined
  with the `resource.cfg` redirect, the game loads its CD2/CD3/CD4
  data from local disk.
- **Minimal scope.** An earlier version of this patcher (in the working
  directory, not in this repo) tried to patch `EMPEROR.EXE` with IAT
  hooks and structure-init replacements borrowed from community trainers.
  Disassembly showed those patches targeted a different binary revision
  — they were silent no-ops on our build. Removed entirely.
- **Layered on the official 1.09 patch.** This script does not include
  or distribute `EM109DE.exe` (the official 1.09 patcher). Users must
  apply it first; the script's MD5 check assumes the 1.09 byte layout
  of `Game.exe`.
- **CRLF preserved** in `resource.cfg` — the Westwood config parser
  is strict about line endings.

[Unreleased]: https://github.com/Usires/emperor-linux-patch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Usires/emperor-linux-patch/releases/tag/v0.1.0
