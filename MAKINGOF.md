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

### The CD-check has two parts

What I didn't appreciate until late in the project: the game's
CD-handling has **two separate checks**, not one:

1. **The initial CD-check at startup.** This is removed by the official
   1.09 patch (`EM109DE.exe`), which also fixes community-map bugs. If
   you don't have 1.09 applied, the game never gets far enough to ask
   for a CD switch. The Linux patcher requires 1.09 (verified by MD5).

2. **The per-CD-switch check during campaign play.** When the game
   loads mission data from CD2, CD3, or CD4, it asks "is the right disc
   in the drive?" and bails out if the answer is "no." On real hardware
   you swap discs. On Linux, you don't have a CD drive. *This* is what
   the Linux patcher fixes.

The Linux patcher does **not** touch the initial CD-check — 1.09
already does. The Linux patcher touches the per-CD-switch check.

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
(`EM109DE.exe`). Verified the 1.09 patch removes the initial CD-check
at startup and updates `PATCHW32.DLL`. `EMPEROR.EXE` itself stays
byte-identical to the Westwood original (MD5:
`a204548ec3ec34c7787dc12f0527575f`).

Disassembled `Game.exe` in ghidra and located the per-CD-switch check
that fires when the campaign asks for CD2/CD3/CD4:

```
0x9668f: jne  0x968ba     ; CD-switch check 1 — "not the right CD" jump
0x966c4: je   0x968a4     ; CD-switch check 2 — "is the right CD" jump
0x96731: je   0x968c5     ; CD-switch check 3 — "is the right CD" jump
0x968bf: xor  al, al      ; return 0 (failure) at end of check
```

Four instructions. 16 bytes total. The first two can be NOP'd (turn
the conditional jumps into no-ops). The third needs to be flipped from
`je` (jump-if-equal, i.e. jump-if-error) to `jmp` (always jump, so we
always take the "wrong CD" path which the rest of the code handles
gracefully). The fourth force-returns `1` (success).

The trick: we don't *remove* the check, we *lie* to it. The check
still runs, still asks "is the right disc present?", and our patches
make it answer "yes" every time. Combined with the `resource.cfg`
redirect, the game loads its CD2/3/4 data from local disk.

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

Replace with local paths so the per-CD lookups resolve into a
`data/CD2/`, `data/CD3/`, `data/CD4/` directory tree:

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

Each CD directory needs four mission-data files (the filenames are
identical on all three CDs):

```
data/CD2/    data/CD3/    data/CD4/
  DIALOG.BAG    DIALOG.BAG    DIALOG.BAG
  MOVIES0001.RFD  MOVIES0001.RFD  MOVIES0001.RFD
  MOVIES0001.RFH  MOVIES0001.RFH  MOVIES0001.RFH
  MUSIC.BAG    MUSIC.BAG    MUSIC.BAG
```

Eight lines in the config. The CRLF must be preserved (the game's
parser is strict). Idempotency: detect the already-patched state and
skip.

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

- **There are two CD-checks, not one.** The initial check (at startup)
  is removed by 1.09. The per-CD-switch check (during campaign play)
  is what this Linux patcher fixes. Treat them as separate problems
  with separate solutions. If you only fix one, the game either
  doesn't start or crashes mid-campaign.

- **The check is answered, not removed.** We don't NOP out the
  per-CD-switch check. We make it lie — always answer "CD present."
  Combined with `resource.cfg` redirect, the game loads its CD2/3/4
  data from local disk.

- **`resource.cfg` is the unsexy 80% of the work.** Even with the
  Game.exe patch, if the path lookups still go to `E:\`, the game
  can't find the data. Don't skip the resource patch.

- **Disassemble the actual binary; don't trust community patches.**
  The "MYTH/TomCraft" patches floating around target slightly different
  code revisions. They look like they should work but the offsets are
  off by 5–20 bytes.

- **CRLF matters.** Westwood's config parser is strict about line
  endings. If you write a patched `resource.cfg` with LF only, the
  parser silently ignores the last line. We hit this in testing.

- **An MD5 check is worth the friction.** The script refuses to patch
  a file that doesn't match the expected MD5. Annoying for users with
  custom builds, but prevents 99% of "I patched the wrong file"
  disasters.

## Tools & timeline

- **2026-06-15** — First Wine test, CD-prompt issue confirmed (couldn't get past startup)
- **2026-06-22** — Downloaded a community "no-CD" patch, rejected as untrustworthy
- **2026-06-29** — Started reverse engineering in ghidra
- **2026-07-01** — Realised the 1.09 patch already removes the *initial* CD-check; the
  real problem is the per-CD-switch check that fires mid-campaign
- **2026-07-03** — Located the 4 per-CD-switch instructions in `Game.exe` via disassembly
- **2026-07-05** — First working end-to-end patch (manual bytes via hex editor)
- **2026-07-07** — Wrote Python patcher v1 (with all the MYTH/TomCraft overengineering)
- **2026-07-08** — Realized the `EMPEROR.EXE` patches were unnecessary, rewrote
  patcher v2 from 611 lines down to 318 lines. End-to-end test with real files
  passes.
- **2026-07-09** — Corrected documentation: the 1.09 patch removes the initial
  CD-check; this Linux patcher only handles the per-CD-switch check, and
  the local data/ tree needs four files per CD (not just movies).
- **2026-07-09 (evening)** — Under Wine/Proton the launcher (`EMPEROR.EXE`)
  occasionally crashes with `EXCEPTION_ACCESS_VIOLATION` shortly after the
  splash screens, before the patched `Game.exe` even gets a turn. Reverse
  engineered the launcher the same way we did `Game.exe`: 4 code patches
  in `.text` plus a new `.lpatch` PE section (21-byte replacement function,
  24-byte inline `strlen`, 19-byte CD-path string, version stamp). Patches
  replicate the upstream reference binary's offsets byte-for-byte
  (`0x56e1`, `0x5763`, `0x6220`, `0xf02a`); our section is `.lpatch` instead
  of `.tomcraft` so users see at a glance which patcher produced it.
- **2026-07-09 (late)** — Added `scripts/emperor_launcher_patch.py` and the
  `scripts/emperor.py` dispatcher (subcommands `patch` / `rollback` /
  `status`). The dispatcher orchestrates both phases; backups stay in
  place until the user deletes them, so `--rollback` is non-destructive
  and re-patchable.

## Credits

- **Reverse engineering:** Dirk (manual disassembly, byte-level verification)
- **Patch design:** Nix (helper extraction, code review, edge-case detection)
- **Testing:** Dirk (real `Game.exe` + Wine/Proton on CachyOS with kernel 7.1.3, AMD RX 9070)
- **Documentation:** Nix (with input from Dirk)

By Nix & Dirk, 2026. *"Reverse engineering: 5% inspiration, 95%
'surely this byte is not the one I need'."*
