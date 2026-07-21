# Emperor Linux/Proton Patcher

Make **Emperor: Battle for Dune** (2001, Westwood/EA) run on Linux via
Wine or Proton — without the original CDs and without a working CD drive.

This is a from-scratch compatibility
patcher written after first-principles reverse engineering of the
game binaries (offsets and patch bytes documented in
[MAKINGOF.md](MAKINGOF.md)). Especially games spanned over multiple
media are problematic when it comes to a requested "disc swap"
mid-game: under Wine a basic USB-CD/DVD drive doesn't always pick
up the swap reliably, so this patcher completes the installation by
making every campaign CD look locally present.

The game itself, its engine, and all assets are not redistributed —
you must legally own a copy. (Original media are a bit rare these
days; eBay is a reasonable source if you're starting from scratch.)

> **Read this in:** [English](#english) · [Deutsch / German](#deutsch--german)

---

<a id="english"></a>

## English

### What this patches

Emperor on Linux needs three layers patched before it boots cleanly:

| Layer | Problem it solves | How |
|---|---|---|
| **Launcher (`EMPEROR.EXE`)** | Crashes with `EXCEPTION_ACCESS_VIOLATION` shortly after the splash screens under Wine/Proton — no CD drive is present | 4 code patches in `.text` (offsets `0x56e1`, `0x5763`, `0x6220`, `0xf02a`) + a new `.lpatch` PE section (21-byte replacement function, 24-byte inline `strlen`, version stamp, CD-path string) |
| **Game (`Game.exe`)** | The per-CD-switch check during campaign play asks for CD2/CD3/CD4 by name and bails out if the answer is "CD not present" | 4 code patches at offsets `0x9668f`, `0x966c4`, `0x96731`, `0x968bf` that make the check always report "CD present" |
| **Config (`resource.cfg`)** | The CD-path lookups in the config file point at drive letters (`E:\`, `D:\`, `.\cd3\`, `.\cd4\`) | 8 path strings redirected to a local `data/CD{2,3,4}/` layout |

**`PATCHW32.DLL` is left untouched** — the official 1.09 patch state is
preserved as-is.

### Why three patches instead of one

The official 1.09 patch (which you must apply first) already makes
some changes to the *initial* CD-check at game startup. It does **not** remove the
*per-CD-switch* check during campaign play — that's what this
patcher's `Game.exe` + `resource.cfg` layer fixes. And even with both
of those, the launcher itself crashes on Linux because it has its own
CD-dependent code path that runs before `Game.exe` is ever loaded.
That's what the new `EMPEROR.EXE` layer fixes.

All three patches are coordinated by one tool (see below) so you can
patch and roll back as a unit.

### Prerequisites

- A legally owned copy of **Emperor: Battle for Dune** (GOG, EA, original CD — any source)
- The official **1.09 English patch** applied once:
  download [`EM109DE.exe`](https://www.moddb.com/games/emperor-battle-for-dune/downloads/emperor-patch-109)
  from Mod DB and run it on your game directory. Without it, the game won't start on modern systems and the MD5 check
  in the patcher will fail.
- **Python 3.8+** on the machine you run the patcher from
- A writable game directory you control
- The four files from each of CD2, CD3, and CD4 extracted into your
  local `data/` subdirectory: `DIALOG.BAG`, `MOVIES0001.RFD`,
  `MOVIES0001.RFH`, `MUSIC.BAG` (the filenames are identical on all
  three CDs)

> The 1.09 patch is not bundled here for licensing reasons. Apply it
> before running the patcher — the MD5 check will refuse otherwise.

### Layout: clone into the game directory

The patcher is a thin directory of Python scripts that lives **next
to the game binaries**. That keeps everything visible at a glance and
makes `git pull` updates trivial.

```bash
# 1. Pick a game directory (or use an existing one).
GAME=~/Games/Emperor_FAUGUS        # example path; pick your own
mkdir -p "$GAME/data/CD2" "$GAME/data/CD3" "$GAME/data/CD4"

# 2. Copy EMPEROR.EXE, Game.exe, and the original resource.cfg into $GAME
#    from your legally owned copy (GOG, EA, original CD...).
#    PATCHW32.DLL is part of the 1.09 patch release, see step 4.

# 3. Drop the four mission-data files from each CD into the matching subdir
cp /path/to/CD2/DIALOG.BAG       "$GAME/data/CD2/"
cp /path/to/CD2/MOVIES0001.RFD  "$GAME/data/CD2/"
cp /path/to/CD2/MOVIES0001.RFH  "$GAME/data/CD2/"
cp /path/to/CD2/MUSIC.BAG       "$GAME/data/CD2/"
# Repeat for CD3 and CD4

# 4. Apply the official 1.09 patch onto the game directory
#    (EM109DE.exe from Mod DB; legacy Windows installer; run via Wine
#     or copy a pre-patched Game.exe/resource.cfg from somewhere else)

# 5. Clone this repo INTO the game directory — alongside EMPEROR.EXE
#    and Game.exe, not on top of them
cd "$GAME"
git clone https://github.com/Usires/emperor-linux-patch.git
# This creates $GAME/emperor-linux-patch/ with scripts/, README.md, etc.
# Your $GAME/Game.exe, $GAME/EMPEROR.EXE and $GAME/data/ stay untouched.
```

After cloning you'll have:

```
$GAME/
  EMPEROR.EXE                   # original 1.09 launcher (will be patched)
  Game.exe                      # original 1.09 game   (will be patched)
  resource.cfg                  # original 1.09 config  (will be patched)
  PATCHW32.DLL                  # 1.09 release, untouched
  data/
    CD2/  CD3/  CD4/           # the four mission files per CD
  emperor-linux-patch/          # this repo
    README.md
    MAKINGOF.md
    scripts/
      emperor.py                # unified dispatcher (patch|rollback|status)
      emperor_linux_patch.py    # Game.exe + resource.cfg patcher
      emperor_launcher_patch.py # EMPEROR.EXE launcher patcher
```

The patcher scripts are marked executable and have a `#!/usr/bin/env
python3` shebang, so you can invoke them directly with `./emperor.py`
or via `python3 emperor.py`. Both work the same.

### Patch the game

From **inside the game directory** (the one with `Game.exe` /
`EMPEROR.EXE` / `resource.cfg` at its root):

```bash
cd ~/Games/Emperor_FAUGUS               # your GAME
./emperor-linux-patch/scripts/emperor.py patch .
```

The `.` at the end is "this directory is the game directory". The
dispatcher runs both phases in order — `Game.exe` + `resource.cfg`
first, then `EMPEROR.EXE` — and verifies each step. Re-runs are safe:
already-patched files are detected and skipped.

You should see output like this (truncated for readability):

```
✓ Game.exe MD5 matches: 7dc4fda2f6b7e8a6b70e846686a81938 (Westwood original)
✓ Backup created: Game.exe.original.bak
✓ Backup created: resource.cfg.original.bak

🔧 Patching Game.exe (4 patches):
  ✅ Patch 1: per-CD check 1 — jne → NOP (CD-switch reports "present")
  ✅ Patch 2: per-CD check 2 — je → NOP
  ✅ Patch 3: per-CD check 3 — je → jmp + NOP
  ✅ Patch 4: per-CD check 4 — xor al,al → mov al,1 (force success)

🔧 Patching resource.cfg (8 CD paths):
  ✅ MOVIES1: 'E:\\Movies' → 'D:\\Movies'
  ✅ MOVIES2: 'E:\\Movies' → 'data\\CD2\\Movies'
  ... (6 more) ...

The `from` paths shown above are whatever the resource.cfg currently
contains for that key — with a Westwood retail install they read
`E:\Movies` etc., but with a GOG / FAUGUS / Wine-mapped install the
patcher shows the actual paths it found (e.g. `Z:\Movies`) before
rewriting them to the local `data/CD{2,3,4}/` layout. Lines that
already match the target are reported as `⊙ already ... skipping`.

🔍 Verification:
  Game.exe:     ✅ OK
  resource.cfg: ✅ OK

============================================================
  Phase 2/2: EMPEROR.EXE launcher
============================================================
✓ Patch 1: redirect call to new .lpatch section start
✓ Patch 2: defense-in-depth callback target
✓ Patch 3: rewrite push arg + rewrite call opcode
✓ Patch 4: inline strlen() helper (replaces 24 zero bytes)
✓ Updated PE header: NumberOfSections=5, SizeOfImage=0x19000
✓ Added new section header: .lpatch (VAddr=0x18000, ...)

🎉 Both phases are clean. Launch Emperor via Wine/Proton.
```

The patcher writes side-by-side `*.original.bak` backups next to each
patched file on first run, so you can always go back.

### Launch the game

**Proton (Steam):** Add the game as a non-Steam shortcut, enable Proton,
launch. Steam auto-handles the Wine prefix.

**Wine directly:**
```bash
cd ~/Games/Emperor_FAUGUS
wine Game.exe
```

The game starts (CD1 check bypassed by 1.09), campaign CD-switches
report "CD present" (the `Game.exe` patches), the `resource.cfg`
redirects CD-path lookups to your local `data/CD2/`, `data/CD3/`,
`data/CD4/`, and the launcher doesn't crash before any of that gets
a chance to run (the `EMPEROR.EXE` patch).

### Single-phase invocation

Each phase script can be invoked directly if you only want to
patch one layer:

```bash
./emperor-linux-patch/scripts/emperor_linux_patch.py .          # Game.exe + resource.cfg only
./emperor-linux-patch/scripts/emperor_launcher_patch.py .       # EMPEROR.EXE only
```

Both scripts accept the game directory as their single argument and
behave the same way the dispatcher does for their layer.

### Check the state of your game directory

```bash
./emperor-linux-patch/scripts/emperor.py status .
```

prints a per-file table showing whether each managed binary is patched,
unpatched, or unknown, and whether a `.original.bak` backup exists:

```
📊 Patch status for: /home/you/Games/Emperor_FAUGUS

  File                 Backup                       State
  -------------------- ---------------------------- --------------------
  Game.exe             ✅ present                    ✅ patched (md5 480265ac…)
  resource.cfg         ✅ present                    ✅ patched (CD paths redirected)
  EMPEROR.EXE          ✅ present                    ✅ patched (.lpatch applied)
```

### Roll back

To restore the original binaries (e.g. if a patch breaks something,
or you just want to compare):

```bash
./emperor-linux-patch/scripts/emperor.py rollback .
```

This restores every `*.original.bak` next to its original file. The
backup files are preserved, so re-running the patcher is always
non-destructive. Your `data/CD*/`, saves, and INI edits are never
touched.

### Idempotency

Re-running any of the three scripts on an already-patched game
directory is safe — they detect the patched state (4-patch markers in
each binary, redirect strings in `resource.cfg`, or section-presence
in `EMPEROR.EXE`) and skip without re-modifying anything.

### Troubleshooting

**"Game.exe MD5 does not match AND file is not patched!"**

- Did you apply the 1.09 patch first? Without it, `Game.exe` has
  different byte offsets and the MD5 check fails.
- Are you in the right game directory? The script looks for `Game.exe`,
  `EMPEROR.EXE`, and `resource.cfg` directly in the given path.

**"X patch(es) could not be applied" on `resource.cfg`**

- Your `resource.cfg` may already be patched (re-run is fine, will
  skip and report skipped).
- If it's the original and patches fail: check the file uses CRLF
  line endings (`file resource.cfg` should say "CRLF" or "with CRLF").
- If the patcher can't find a CD path key like `MOVIES1` / `CD2` /
  etc., your `resource.cfg` may be from a different edition or
  localized variant. Open it in a text editor and verify the section
  structure matches the [upstream 1.09 layout](MAKINGOF.md#the-cd-path-redirect-uses-crlf-exactly).

**Game still asks for CD after patching**

- Verify `data/CD2/Movies/`, `data/CD3/Movies/`, `data/CD4/Movies/`
  exist with content. The patcher doesn't create or verify these —
  that's your responsibility.
- Check `resource.cfg` paths match your actual `data/` layout.

**Game crashes shortly after splash screens (Wine/Proton)**

- Make sure both phases ran: `./emperor.py status .` should show all
  three files as `✅ patched`.
- If `EMPEROR.EXE` shows `unpatched`, run the launcher patcher once:
  `./scripts/emperor_launcher_patch.py .`
- The crash signature in `proton.log` or Wine's output looks like
  `EXCEPTION_ACCESS_VIOLATION (0xc0000005)` with `eip=0x4034a0` and
  `info[1]=0x8` — that's what phase 2 exists to fix.

**`permission denied` when running `./emperor.py`**

- The execute bit may have been lost (e.g. cloned on a Windows host
  then copied over). Restore it: `chmod +x scripts/*.py`. Or use
  `python3 scripts/emperor.py patch .` instead — both work.

### License

MIT — see [LICENSE](LICENSE). The patcher code is original work; the
patched game binaries are not redistributed.

The game "Emperor: Battle for Dune", its engine, and all contents
are property of Westwood Studios / Electronic Arts. This project
does not distribute any copyrighted material — it provides a tool
that modifies files you must already own.

### Attribution

- Reverse engineering & test environments: **Dirk Steiger**
- Patcher design, scripting, documentation: **Nix & Dirk, 2026**

By Nix & Dirk, 2026. *"Reverse engineering: 5% inspiration, 95%
'surely this byte is not the one I need'."*

---

<a id="deutsch--german"></a>

## Deutsch / German

### Was dieser Patcher macht

Emperor: Battle for Dune braucht unter Linux drei Patches, bevor das
Spiel sauber startet:

| Schicht | Problem | Lösung |
|---|---|---|
| **Launcher (`EMPEROR.EXE`)** | Stürzt unter Wine/Proton mit `EXCEPTION_ACCESS_VIOLATION` kurz nach den Splash-Screens ab (kein CD-Laufwerk vorhanden) | 4 Code-Patches in `.text` (Offsets `0x56e1`, `0x5763`, `0x6220`, `0xf02a`) + eine neue `.lpatch`-PE-Section (21-Byte-Ersatzfunktion, 24-Byte-Inline-`strlen`, Versions-Stempel, CD-Pfad-String) |
| **Spiel (`Game.exe`)** | Die CD-Wechsel-Abfrage während der Kampagne fragt nach CD2/CD3/CD4 und bricht ab, wenn die Antwort „CD nicht vorhanden“ lautet | 4 Code-Patches an Offsets `0x9668f`, `0x966c4`, `0x96731`, `0x968bf`, die die Abfrage immer „CD vorhanden“ antworten lassen |
| **Config (`resource.cfg`)** | Die CD-Pfad-Lookups zeigen auf Laufwerksbuchstaben (`E:\`, `D:\`, `.\cd3\`, `.\cd4\`) | 8 Pfad-Zeichenketten werden auf ein lokales `data/CD{2,3,4}/`-Layout umgebogen |

**`PATCHW32.DLL` bleibt unangetastet** (1.09-Release bleibt erhalten).

### Warum drei Patches statt einem

Der offizielle 1.09-Patch entfernt bereits den *initialen* CD-Check
beim Spielstart. Was er *nicht* fixt, ist die *CD-Wechsel-Abfrage*
während der Kampagne — das übernimmt die `Game.exe` + `resource.cfg`-
Schicht hier. Und selbst wenn beide gefixt sind, stürzt der Launcher
unter Linux separat ab, weil er einen eigenen CD-abhängigen Codepfad
hat, der vor `Game.exe` läuft. Das fixt die `EMPEROR.EXE`-Schicht.

Alle drei Patches werden von einem Tool koordiniert (siehe unten),
sodass du Patch und Rollback als Einheit ausführen kannst.

### Voraussetzungen

- Eine legal erworbene Kopie von **Emperor: Battle for Dune** (GOG, EA, Original-CD — egal)
- Der offizielle **1.09-Patch** einmal angewendet: lade
  [`EM109DE.exe`](https://www.moddb.com/games/emperor-battle-for-dune/downloads/emperor-patch-109)
  aus dem Westwood-Archiv auf Mod DB und führe es im Spielverzeichnis
  aus. Der 1.09-Patch fixt Community-Map-Bugs und entfernt den
  initialen CD-Check beim Start. Ohne ihn startet das Spiel auf
  modernen Systemen gar nicht, und die MD5-Prüfung im Patcher
  schlägt fehl.
- **Python 3.8+** auf dem Rechner, auf dem du den Patcher ausführst
- Die Spieldateien in einem beschreibbaren Verzeichnis
- Die vier Dateien von jeder der CDs 2, 3 und 4 in deine lokale
  `data/`-Unterverzeichnisstruktur extrahiert: `DIALOG.BAG`,
  `MOVIES0001.RFD`, `MOVIES0001.RFH`, `MUSIC.BAG` (die Dateinamen
  sind auf allen drei CDs identisch)

> Der 1.09-Patch ist aus lizenzrechtlichen Gründen nicht im Repo
> enthalten. Wende ihn vor dem Linux-Patcher an, sonst schlägt die
> MD5-Prüfung fehl.

### Layout: Repo ins Spielverzeichnis klonen

Der Patcher ist ein dünnes Verzeichnis mit Python-Skripten, das
**neben** den Spiele-Binaries liegt. So bleibt alles auf einen Blick
sichtbar und `git pull` zum Aktualisieren ist trivial.

```bash
# 1. Wähle (oder erstelle) ein Spielverzeichnis.
GAME=~/Games/Emperor_FAUGUS        # Beispielpfad; nimm deinen eigenen
mkdir -p "$GAME/data/CD2" "$GAME/data/CD3" "$GAME/data/CD4"

# 2. Kopiere EMPEROR.EXE, Game.exe und die ursprüngliche resource.cfg nach $GAME
#    aus deiner legal erworbenen Kopie (GOG, EA, Original-CD...).
#    PATCHW32.DLL gehört zum 1.09-Release, siehe Schritt 4.

# 3. Lege die vier Missionsdateien von jeder CD ins passende Unterverzeichnis
cp /path/to/CD2/DIALOG.BAG       "$GAME/data/CD2/"
cp /path/to/CD2/MOVIES0001.RFD  "$GAME/data/CD2/"
cp /path/to/CD2/MOVIES0001.RFH  "$GAME/data/CD2/"
cp /path/to/CD2/MUSIC.BAG       "$GAME/data/CD2/"
# Analog für CD3 und CD4

# 4. Wende den offiziellen 1.09-Patch auf das Spielverzeichnis an
#    (EM109DE.exe von Mod DB; legacy-Windows-Installer; via Wine
#     starten oder eine bereits gepatchte Game.exe/resource.cfg
#     von anderswo kopieren)

# 5. Klone dieses Repo IN das Spielverzeichnis — neben EMPEROR.EXE
#    und Game.exe, nicht obendrüber
cd "$GAME"
git clone https://github.com/Usires/emperor-linux-patch.git
# Das erstellt $GAME/emperor-linux-patch/ mit scripts/, README.md, etc.
# $GAME/Game.exe, $GAME/EMPEROR.EXE und $GAME/data/ bleiben unangetastet.
```

Danach hast du:

```
$GAME/
  EMPEROR.EXE                   # ursprünglicher 1.09-Launcher (wird gepatcht)
  Game.exe                      # ursprüngliches 1.09-Spiel   (wird gepatcht)
  resource.cfg                  # ursprüngliche 1.09-Config    (wird gepatcht)
  PATCHW32.DLL                  # 1.09-Release, unangetastet
  data/
    CD2/  CD3/  CD4/           # die vier Missionsdateien pro CD
  emperor-linux-patch/          # dieses Repo
    README.md
    MAKINGOF.md
    scripts/
      emperor.py                # Dispatcher (patch|rollback|status)
      emperor_linux_patch.py    # Patcher für Game.exe + resource.cfg
      emperor_launcher_patch.py # Patcher für EMPEROR.EXE
```

Die Patcher-Skripte sind ausführbar markiert und haben einen
`#!/usr/bin/env python3`-Shebang, du kannst sie also direkt mit
`./emperor.py` aufrufen oder via `python3 emperor.py`. Beides ist
äquivalent.

### Spiel patchen

Aus dem **Spielverzeichnis** (das mit `Game.exe` / `EMPEROR.EXE` /
`resource.cfg` direkt im Stamm):

```bash
cd ~/Games/Emperor_FAUGUS               # dein GAME
./emperor-linux-patch/scripts/emperor.py patch .
```

Der `.` am Ende bedeutet „dieses Verzeichnis ist das Spielverzeichnis".
Der Dispatcher führt beide Phasen nacheinander aus — `Game.exe` +
`resource.cfg` zuerst, dann `EMPEROR.EXE` — und verifiziert jeden
Schritt. Re-Runs sind sicher: bereits gepatchte Dateien werden
erkannt und übersprungen.

Der Dispatcher schreibt `*.original.bak`-Backups neben jede
gepatchte Datei beim ersten Lauf — so kannst du jederzeit wieder
zurück.

### Spiel starten

**Proton (Steam):** Spiel als Nicht-Steam-Verknüpfung hinzufügen,
Proton aktivieren, starten. Steam kümmert sich um das Wine-Prefix.

**Direkt mit Wine:**
```bash
cd ~/Games/Emperor_FAUGUS
wine Game.exe
```

Das Spiel startet (CD1-Check durch 1.09 umgangen), die CD-Wechsel-
Abfragen während der Kampagne melden „CD vorhanden" (die `Game.exe`-
Patches), die `resource.cfg` leitet CD-spezifische Lookups auf deine
lokalen `data/CD2/`, `data/CD3/`, `data/CD4/`-Verzeichnisse um,
und der Launcher stürzt nicht mehr ab, bevor irgendwas davon läuft
(der `EMPEROR.EXE`-Patch).

### Einzelphase aufrufen

Jedes Phasen-Skript lässt sich auch direkt aufrufen, wenn du nur eine
Schicht patchen willst:

```bash
./emperor-linux-patch/scripts/emperor_linux_patch.py .          # nur Game.exe + resource.cfg
./emperor-linux-patch/scripts/emperor_launcher_patch.py .       # nur EMPEROR.EXE
```

Beide Skripte nehmen das Spielverzeichnis als einziges Argument und
verhalten sich für ihre Schicht genauso wie der Dispatcher.

### Zustand prüfen

```bash
./emperor-linux-patch/scripts/emperor.py status .
```

gibt eine Tabelle pro Datei aus, die zeigt, ob jede verwaltete Datei
gepatcht, ungepatcht oder unbekannt ist und ob ein `.original.bak`-
Backup vorliegt:

```
📊 Patch status for: /home/du/Games/Emperor_FAUGUS

  Datei                Backup                       Zustand
  -------------------- ---------------------------- --------------------
  Game.exe             ✅ vorhanden                  ✅ gepatcht (md5 480265ac…)
  resource.cfg         ✅ vorhanden                  ✅ gepatcht (CD-Pfade umgeleitet)
  EMPEROR.EXE          ✅ vorhanden                  ✅ gepatcht (.lpatch angewendet)
```

### Rollback

Um die Originale wiederherzustellen (z.B. wenn ein Patch etwas kaputt
macht, oder du einfach vergleichen willst):

```bash
./emperor-linux-patch/scripts/emperor.py rollback .
```

Stellt jede `*.original.bak`-Datei unter ihrem ursprünglichen Namen
wieder her. Die Backup-Dateien bleiben liegen, ein Re-Patch ist also
immer zerstörungsfrei. Deine `data/CD*/`, Saves und INI-Änderungen
werden nie angefasst.

### Idempotenz

Erneutes Ausführen eines der drei Skripte auf einem bereits
gepatchten Verzeichnis ist sicher — sie erkennen den gepatchten
Zustand (4-Patch-Marker in jeder Binary, Redirect-Strings in
`resource.cfg` bzw. Section-Anwesenheit in `EMPEROR.EXE`) und
überspringen ohne erneute Änderung.

### Fehlerbehebung

**„Game.exe MD5 does not match AND file is not patched!"**
- Hast du den 1.09-Patch zuerst angewendet? Ohne ihn hat `Game.exe`
  andere Byte-Offsets, und die MD5-Prüfung schlägt fehl.
- Bist du im richtigen Spielverzeichnis? Das Skript sucht `Game.exe`,
  `EMPEROR.EXE` und `resource.cfg` direkt im angegebenen Pfad.

**„X patch(es) could not be applied" auf `resource.cfg`**
- Deine `resource.cfg` ist möglicherweise schon gepatcht (Re-Run ist
  in Ordnung, wird übersprungen).
- Wenn sie ursprünglich ist und die Patches scheitern: prüfe, ob die
  Datei CRLF-Zeilenenden verwendet (`file resource.cfg` sollte „CRLF"
  zeigen).

**Spiel fragt nach dem Patchen immer noch nach CD**
- Prüfe, ob `data/CD2/Movies/`, `data/CD3/Movies/`, `data/CD4/Movies/`
  mit Inhalt existieren. Der Patcher legt das nicht an.
- Prüfe, ob die Pfade in `resource.cfg` zu deiner tatsächlichen `data/`-
  Struktur passen.

**Spiel stürzt unter Wine/Proton kurz nach den Splash-Screens ab**
- Prüfe, ob beide Phasen gelaufen sind: `./emperor.py status .` sollte
  alle drei Dateien als `✅ gepatcht` zeigen.
- Falls `EMPEROR.EXE` ungepatcht ist: einmalig
  `./scripts/emperor_launcher_patch.py .` ausführen.
- Die Crash-Signatur in `proton.log` oder der Wine-Ausgabe sieht aus
  wie `EXCEPTION_ACCESS_VIOLATION (0xc0000005)` mit `eip=0x4034a0` und
  `info[1]=0x8` — das ist das, was Phase 2 fixt.

**`permission denied` beim Ausführen von `./emperor.py`**
- Das Execute-Bit kann verloren gehen (z.B. wenn die Datei auf einem
  Windows-Host geklont und dann kopiert wird). Wiederherstellen:
  `chmod +x scripts/*.py`. Oder `python3 scripts/emperor.py patch .`
  verwenden — beides geht.

### Lizenz

MIT — siehe [LICENSE](LICENSE). Der Patcher-Code ist eigenständige
Arbeit; die gepatchten Spieldateien werden nicht verteilt.

Das Spiel "Emperor: Battle for Dune", seine Engine und alle Inhalte
sind Eigentum von Westwood Studios / Electronic Arts. Dieses Projekt
vertreibt kein urheberrechtlich geschütztes Material — es stellt
ein Werkzeug bereit, das Dateien verändert, die du bereits besitzen
musst.

### Mitwirkende

- Reverse Engineering & Testumgebungen: **Dirk Steiger**
- Patcher-Design, Scripting, Dokumentation: **Nix & Dirk, 2026**

By Nix & Dirk, 2026. *"Reverse Engineering: 5% Inspiration, 95%
'komm, das ist bestimmt nicht der Byte, den ich brauche'."*
