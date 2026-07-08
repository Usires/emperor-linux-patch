# Open-Source Dependencies

This project is intentionally minimal — a single Python script that
performs byte-level patches on existing game files. No third-party
libraries, no runtime dependencies, no build step.

## Runtime requirements

- **Python 3.8+** (standard library only: `hashlib`, `shutil`, `struct`,
  `sys`, `pathlib`)

That's it. The script is a single file with zero external dependencies.

## Development-time tools (not shipped to end users)

| Tool | Purpose | License |
|------|---------|---------|
| [ghidra](https://ghidra-sre.org/) | Reverse engineering, instruction-level disassembly of `Game.exe` | Apache 2.0 |
| [radare2](https://www.radare.org/n/) | Cross-check of disassembly offsets | LGPL 3.0 |
| [Wine](https://www.winehq.org/) | Testing environment for patched game | LGPL 2.1+ |
| [Proton](https://github.com/ValveSoftware/Proton) | Testing environment for Steam-launched game | BSD-style (Valve) |
| [git](https://git-scm.com/) | Version control | GPL 2.0 |

## Inspiration & prior art

- **Dune 2000 (open-source project)** — established the pattern of
  community-maintained Linux compatibility patches for Westwood RTS games.
- **cnc-ddraw / DDrawCompat** — community efforts to keep DirectDraw-era
  games alive on modern systems.
- **PCGamingWiki** — invaluable resource for game compatibility notes.

No code was copied from these projects; they informed the approach but the
patcher is original work.

## Code provenance

Every line of `scripts/emperor_linux_patch.py` was written by Nix & Dirk
in 2026. The four code patches in `Game.exe` and eight path patches in
`resource.cfg` were derived from first-principles reverse engineering, not
copied from existing "no-CD" patches or community trainers.

If you find a line of code in this repository that you believe was
copied from another project, please open an issue with the source.
