# Making of — Emperor Linux/Proton Compatibility Patch

The full story of how we got Emperor: Battle for Dune running on Linux
in 2026, including the dead ends, the breakthroughs, and the lessons.

## The problem

Emperor: Battle for Dune (2001, Westwood) is a beloved cult classic —
but unlike Dune 2000, it has no active community and no Linux
compatibility patches. The only "no-CD" patches online are sketchy
Windows .EXE replacements of dubious origin, often bundled with malware
or unstable cracks.

The goal here is not piracy — it's *compatibility*. Same approach as the
community patches for other Westwood titles: minimal, transparent,
auditable.

## The investigation (2026-06 to 2026-07)

### Phase 1: try existing patches (dead end)

Downloaded a "no-CD patch" from a random abandonware site. It worked on
Windows but:

- Came as a pre-patched `Game.exe` (security risk, no source)
- Required disabling antivirus
- Crashed on Wine/Proton
- Was likely a trainer, not a clean patch

**Verdict:** Don't trust random binaries. We need to understand the patch
ourselves.

### Phase 2: try the community approaches (several dead ends)

Several "no-CD" approaches for Westwood titles are documented online.
We tried each:

- **MYTH DEViANCE's IAT hook on `FindNextFileA`** — intercepts the
  file-search API. Cool in theory, but `EMPEROR.EXE`'s PE structure
  didn't match the assumed layout. The injected code crashed immediately.

- **TomCraft's CD-structure-init patch** — a memcpy-based replacement
  of the encryption stub. Reverse engineering showed the structure
  had changed across versions. Applied patches led to silent no-ops.

- **MYTH strlen-stub** — a 24-byte strlen replacement in `.text`
  padding. Worked in MYTH's build, but `EMPEROR.EXE` has different
  padding layout and the stub landed in a code path that never executed.

- **PATCHGET.DAT modifications** — tried rewriting the encrypted CD
  descriptors. Wrote valid stubs, but the game's decryptor wouldn't
  load them — wrong version format.

**Verdict after a week:** All the community approaches are overengineered
hacks for slightly different code paths. We need to look at what
*actually* runs on our specific binary.

### Phase 3: focused disassembly (the breakthrough)

Downloaded the original Westwood release plus the official 1.09 patch
(`EM109DE.exe`). Verified the 1.09 patch is just a `PATCHW32.DLL` update
plus a minor `Game.exe` rebuild — `EMPEROR.EXE` itself stays
byte-identical (MD5: `a204548ec3ec34c7787dc12f0527575f`).

Disassembled `Game.exe` in ghidra. Found the startup sequence:

```
0x9668f: jne  0x968ba     ; CD1 type check — if not fixed disk, error
0x966c4: je   0x968a4     ; CD2 type check — if fixed disk, error
0x96731: je   0x968c5     ; "is current CD the right one" check
0x968bf: xor  al, al      ; return 0 (failure) at end of check
```

Four instructions. 16 bytes total. The first two can be NOP'd (turn
the conditional jumps into no-ops). The third needs to be flipped from
`je` (jump-if-equal, i.e. jump-if-error) to `jmp` (always jump, so we
always take the "wrong CD" path which the rest of the code handles
gracefully). The fourth force-returns `1` (success).

That's it. 16 bytes in `Game.exe`, and the CD-check is dead.

### Phase 4: `resource.cfg` (the easy part)

`resource.cfg` is a plain text file (CRLF line endings) with key-path
pairs. The original entries assume CD drives:

```
MOVIES1
E:\Movies
MOVIES2
E:\Movies
...
CD1
E:\
CD2
D:\
...
```

Replace with local paths:

```
MOVIES1
D:\Movies
MOVIES2
data\CD2\Movies
...
CD1
D:\
CD2
data\CD2
...
```

Eight lines. The CRLF must be preserved (the game's parser is strict).
Idempotency: detect the already-patched state and skip.

## What got cut

A previous version of this patcher (in the working directory, not in
this repo) tried to also patch `EMPEROR.EXE` with the IAT-hook and
structure-init patterns from the community. We learned the hard way
that those were forks of an older build and don't match our binary.

The final patcher only touches:
- `Game.exe` (4 code patches)
- `resource.cfg` (8 path patches)

That's the minimum to make the game work. The 1.09 patch is a
prerequisite; this Linux patch is layered on top.

## Lessons learned

- **Disassemble the actual binary; don't trust community patches.**
  The "MYTH/TomCraft" patches floating around target slightly different
  code revisions. They look like they should work but the offsets are
  off by 5–20 bytes.

- **`resource.cfg` is the unsexy 80% of the work.** Everyone talks
  about the `Game.exe` CD-check, but if the path lookups still go to
  `E:\`, the game crashes when it tries to load movies. Don't skip
  the resource patch.

- **CRLF matters.** Westwood's config parser is strict about line
  endings. If you write a patched `resource.cfg` with LF only, the
  parser silently ignores the last line. We hit this in testing.

- **An MD5 check is worth the friction.** The script refuses to patch
  a file that doesn't match the expected MD5. Annoying for users with
  custom builds, but prevents 99% of "I patched the wrong file"
  disasters.

## Tools & timeline

- **2026-06-15** — First Wine test, CD-prompt issue confirmed
- **2026-06-22** — Downloaded a community "no-CD" patch, rejected as untrustworthy
- **2026-06-29** — Started reverse engineering in ghidra
- **2026-07-01** — Found the 4 instructions in `Game.exe` via startup trace
- **2026-07-05** — First working end-to-end patch (manual bytes via hex editor)
- **2026-07-07** — Wrote Python patcher v1 (with all the MYTH/TomCraft overengineering)
- **2026-07-08** — Realized the `EMPEROR.EXE` patches were unnecessary, rewrote
  patcher v2 from 611 lines down to 318 lines. End-to-end test with real files
  passes.

## Credits

- **Reverse engineering:** Dirk (manual disassembly, byte-level verification)
- **Patch design:** Nix (helper extraction, code review, edge-case detection)
- **Testing:** Dirk (real `Game.exe` + Wine + Proton on Fedora 41)
- **Documentation:** Nix (with input from Dirk)

By Nix & Dirk, 2026. *"Reverse engineering: 5% inspiration, 95%
'surely this byte is not the one I need'."*
