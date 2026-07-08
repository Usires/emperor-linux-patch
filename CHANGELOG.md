# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
