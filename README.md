# Emperor: Battle for Dune — Linux/Proton Compatibility Patch

Patches **Emperor: Battle for Dune** (2001, Westwood/EA) so it runs on
**Linux** via **Wine** or **Proton** without requiring the original CDs.

This patch is **not** a "no-CD crack". It is a compatibility shim: it
removes the runtime CD-check and redirects CD-path lookups to a local
`data/` directory. The game itself, its engine, and all assets are not
included — you must legally own a copy.

> **Read this in:** [English](#english) · [Deutsch / German](#deutsch--german)

---

<a id="english"></a>

## English

### What this patch does

The official 1.09 patch already removes the **initial** CD-check at
game startup. What it does *not* fix is the **per-CD-switch check**
during campaign play: the game asks for CD2, CD3, and CD4 by name when
loading mission data, and refuses to continue if the answer is "CD
not present."

On real hardware this is fine — you swap the disc. On Linux, you don't
have a CD drive, so the per-CD check kills the game mid-campaign.

This patch:

- **Patches 4 instructions in `Game.exe`** so the per-CD-switch check
  always reports "CD present" for CD2/CD3/CD4. (Offsets `0x9668f`,
  `0x966c4`, `0x96731`, `0x968bf`, verified via disassembly.)
- **Patches 8 path strings in `resource.cfg`** so the per-CD lookups
  resolve to a local `data/CD2/`, `data/CD3/`, `data/CD4/` directory
  layout instead of drive letters `E:\` / `D:\` / `.\cd3\` / `.\cd4\`.

The original `EMPEROR.EXE` and `PATCHW32.DLL` are **left untouched** —
the patch is layered on top of the official 1.09 update.

### Prerequisites

- A legally owned copy of **Emperor: Battle for Dune** (GOG, EA, original
  CD — any source)
- The official **1.09 English patch** applied: download
  [`EM109DE.exe`](https://www.moddb.com/games/emperor-battle-for-dune/downloads/emperor-patch-109)
  from the Westwood patch archive on Mod DB and run it once on your game
  directory. The 1.09 patch fixes community-map bugs **and** removes the
  initial CD-check at startup. Without it, the game will not start at
  all on modern systems, and the MD5 check in this script will fail.
- **Python 3.8+** on the machine you run the patcher from
- The game files in a writable directory you control
- The four files from each of CD2, CD3, and CD4 extracted into your
  local game directory: `DIALOG.BAG`, `MOVIES0001.RFD`, `MOVIES0001.RFH`,
  `MUSIC.BAG` (the filenames are identical on all three CDs)

> The 1.09 patch is not bundled here for licensing reasons. Apply it
> before running the Linux patch — the MD5 check in the script will fail
> otherwise.

### Usage

#### 1. Prepare the directory layout

Copy the four mission-data files from each campaign CD into a local
`data/` subdirectory. The filenames are identical on all three CDs:

```
data/CD2/
  DIALOG.BAG
  MOVIES0001.RFD
  MOVIES0001.RFH
  MUSIC.BAG
data/CD3/    (same four files)
data/CD4/    (same four files)
```

```bash
cd ~/Games/Emperor_FAUGUS/  # your game directory
mkdir -p data/CD2 data/CD3 data/CD4
# Copy from your CD rips / GOG install / original media
cp /path/to/CD2/DIALOG.BAG data/CD2/
cp /path/to/CD2/MOVIES0001.RFD data/CD2/
cp /path/to/CD2/MOVIES0001.RFH data/CD2/
cp /path/to/CD2/MUSIC.BAG data/CD2/
# Repeat for CD3 and CD4
```

#### 2. Run the patcher

```bash
git clone https://github.com/Usires/emperor-linux-patch
cd emperor-linux-patch
python3 scripts/emperor_linux_patch.py ~/Games/Emperor_FAUGUS/
```

You should see:

```
🎮 Emperor: Battle for Dune — Linux/Proton Compatibility Patch
   Target: /home/you/Games/Emperor_FAUGUS

  ✓ Game.exe MD5 matches: 7dc4fda2f6b7e8a6b70e846686a81938 (Westwood original)

  ✓ Backup created: Game.exe.original.bak
  ✓ Backup created: resource.cfg.original.bak

  🔧 Patching Game.exe (4 patches):
    ✅ Patch 1: per-CD check 1 — jne → NOP (CD-switch reports “present”)
    ✅ Patch 2: per-CD check 2 — je → NOP
    ✅ Patch 3: per-CD check 3 — je → jmp + NOP
    ✅ Patch 4: per-CD check 4 — xor al,al → mov al,1 (force success)

  🔧 Patching resource.cfg (8 CD paths):
    ✅ MOVIES1: 'E:\\Movies' → 'D:\\Movies'
    ✅ MOVIES2: 'E:\\Movies' → 'data\\CD2\\Movies'
    ✅ MOVIES3: 'E:\\Movies' → 'data\\CD3\\Movies'
    ✅ MOVIES4: 'E:\\Movies' → 'data\\CD4\\Movies'
    ✅ CD1: 'E:\\' → 'D:\\'
    ✅ CD2: 'D:\\' → 'data\\CD2'
    ✅ CD3: '.\\cd3\\' → 'data\\CD3'
    ✅ CD4: '.\\cd4\\' → 'data\\CD4'

  🔍 Verification:
    Game.exe:     ✅ OK
    resource.cfg: ✅ OK
```

#### 3. Launch via Wine or Proton

**Proton (Steam):** Add the game as a non-Steam shortcut, enable Proton,
launch. Steam auto-handles the Wine prefix.

**Wine:** `wine ~/Games/Emperor_FAUGUS/Game.exe`

The game starts (CD1 check bypassed by 1.09), campaign CD-switches
report "CD present" (our Game.exe patches), and the per-CD lookups
resolve to your local `data/CD2/`, `data/CD3/`, `data/CD4/`
directories.

### What the script does NOT touch

| File | Status |
|------|--------|
| `EMPEROR.EXE` | **untouched** (byte-identical to Westwood original) |
| `PATCHW32.DLL` | **untouched** (1.09 patch state) |
| `PATCHGET.DAT` | **untouched** |
| `Game.exe` | 4 code patches (idempotent) |
| `resource.cfg` | 8 path patches (idempotent) |

The patcher creates `*.original.bak` backups next to the originals on
first run, so you can always revert.

### Idempotency

Re-running the script on an already-patched directory is safe — it
detects the patched state and skips without re-modifying anything.
Backups are only created once.

### Troubleshooting

**"Game.exe MD5 does not match AND file is not patched!"**
- Did you apply the 1.09 patch first? Without it, `Game.exe` has
  different byte offsets and the MD5 check fails.
- Are you in the right game directory? The script looks for `Game.exe`
  and `resource.cfg` directly in the given path.

**"X patch(es) could not be applied" on `resource.cfg`**
- Your `resource.cfg` may already be patched (re-run is fine, will skip).
- If it's the original and patches fail: check the file uses CRLF
  line endings (`file resource.cfg` should say "CRLF" or "with CRLF").

**Game still asks for CD after patching**
- Verify `data/CD2/Movies/`, `data/CD3/Movies/`, `data/CD4/Movies/`
  exist with content. The patcher doesn't create or verify these —
  that's your responsibility.
- Check `resource.cfg` paths match your actual `data/` layout.

### License

MIT — see [LICENSE](LICENSE). The patcher code is original work; the
patched game files are not distributed.

The "Emperor: Battle for Dune" game, its engine, and all its assets are
the property of Westwood Studios / Electronic Arts. This project does not
distribute any copyrighted material — it provides a tool that modifies
files you must already own.

### Credits

- **Reverse engineering & patch design:** Nix (AI assistant) & Dirk
- **Disassembly & verification:** ghidra, radare2
- **Testing environment:** Linux Mint 22 + Wine 9.0, Fedora 41 + Proton 9.0

By Nix & Dirk, 2026. *"It's not a bug, it's an undocumented feature."*

---

<a id="deutsch--german"></a>

## Deutsch / German

### Was dieser Patch macht

Der offizielle 1.09-Patch entfernt bereits den **initialen** CD-Check
beim Spielstart. Was er *nicht* fixt, ist die **CD-Wechsel-Abfrage
während der Kampagne**: Das Spiel fragt beim Laden der Missionsdaten
nach CD2, CD3 und CD4 und bricht ab, wenn die Antwort „CD nicht
vorhanden“ lautet.

Auf echter Hardware kein Problem — man wechselt die CD. Auf Linux hast
du kein CD-Laufwerk, also killt die CD-Wechsel-Abfrage das Spiel mitten
in der Kampagne.

Dieser Patch:

- **Patcht 4 Instruktionen in `Game.exe`**, sodass die CD-Wechsel-Abfrage
  für CD2/CD3/CD4 immer „CD vorhanden“ zurückgibt. (Offsets `0x9668f`,
  `0x966c4`, `0x96731`, `0x968bf`, per Disassembly verifiziert.)
- **Patcht 8 Pfad-Zeichenketten in `resource.cfg`**, sodass die
  CD-spezifischen Lookups auf eine lokale `data/CD2/`, `data/CD3/`,
  `data/CD4/`-Verzeichnisstruktur aufgelöst werden statt auf
  Laufwerksbuchstaben `E:\` / `D:\` / `.\cd3\` / `.\cd4\`.

Die originale `EMPEROR.EXE` und `PATCHW32.DLL` bleiben **unangetastet** —
der Patch setzt auf dem offiziellen 1.09-Update auf.

### Voraussetzungen

- Eine legal erworbene Kopie von **Emperor: Battle for Dune** (GOG, EA,
  Original-CD — egal)
- Der offizielle **1.09-Patch** muss angewendet sein: lade
  [`EM109DE.exe`](https://www.moddb.com/games/emperor-battle-for-dune/downloads/emperor-patch-109)
  aus dem Westwood-Archiv auf Mod DB und führe es einmal im
  Spielverzeichnis aus. Der 1.09-Patch fixt Community-Map-Bugs **und**
  entfernt den initialen CD-Check beim Start. Ohne ihn startet das
  Spiel auf modernen Systemen gar nicht, und die MD5-Prüfung in diesem
  Skript schlägt fehl.
- **Python 3.8+** auf dem Rechner, auf dem du den Patcher ausführst
- Die Spieldateien in einem beschreibbaren Verzeichnis
- Die vier Dateien von jeder der CDs 2, 3 und 4 in dein lokales
  Spielverzeichnis extrahiert: `DIALOG.BAG`, `MOVIES0001.RFD`,
  `MOVIES0001.RFH`, `MUSIC.BAG` (die Dateinamen sind auf allen drei
  CDs identisch)

> Der 1.09-Patch ist aus lizenzrechtlichen Gründen nicht im Repo
> enthalten. Wende ihn vor dem Linux-Patch an — sonst schlägt die
> MD5-Prüfung fehl.

### Verwendung

#### 1. Verzeichnisstruktur vorbereiten

Kopiere die vier Missionsdateien von jeder Kampagnen-CD in ein lokales
`data/`-Unterverzeichnis. Die Dateinamen sind auf allen drei CDs
identisch:

```
data/CD2/
  DIALOG.BAG
  MOVIES0001.RFD
  MOVIES0001.RFH
  MUSIC.BAG
data/CD3/    (gleiche vier Dateien)
data/CD4/    (gleiche vier Dateien)
```

```bash
cd ~/Games/Emperor_FAUGUS/  # dein Spielverzeichnis
mkdir -p data/CD2 data/CD3 data/CD4
# Aus CD-Rips / GOG-Installation / Original-Medien kopieren
cp /path/to/CD2/DIALOG.BAG data/CD2/
cp /path/to/CD2/MOVIES0001.RFD data/CD2/
cp /path/to/CD2/MOVIES0001.RFH data/CD2/
cp /path/to/CD2/MUSIC.BAG data/CD2/
# Analog für CD3 und CD4
```

#### 2. Patcher ausführen

```bash
git clone https://github.com/Usires/emperor-linux-patch
cd emperor-linux-patch
python3 scripts/emperor_linux_patch.py ~/Games/Emperor_FAUGUS/
```

#### 3. Start via Wine oder Proton

**Proton (Steam):** Füge das Spiel als Nicht-Steam-Verknüpfung hinzu,
aktiviere Proton, starte. Steam kümmert sich um das Wine-Prefix.

**Wine:** `wine ~/Games/Emperor_FAUGUS/Game.exe`

Das Spiel startet (CD1-Check durch 1.09 umgangen), die CD-Wechsel-
Abfragen während der Kampagne melden „CD vorhanden“ (unsere Game.exe-
Patches), und die CD-spezifischen Lookups verweisen auf deine lokalen
`data/CD2/`, `data/CD3/`, `data/CD4/`-Verzeichnisse.

### Was das Skript NICHT anfasst

| Datei | Status |
|------|--------|
| `EMPEROR.EXE` | **unangetastet** (byte-identisch zum Westwood-Original) |
| `PATCHW32.DLL` | **unangetastet** (1.09-Patch-Stand) |
| `PATCHGET.DAT` | **unangetastet** |
| `Game.exe` | 4 Code-Patches (idempotent) |
| `resource.cfg` | 8 Pfad-Patches (idempotent) |

### Idempotenz

Erneutes Ausführen auf einem bereits gepatchten Verzeichnis ist sicher
— das Skript erkennt den gepatchten Zustand und überspringt ohne
erneute Änderung. Backups werden nur einmal angelegt.

### Fehlerbehebung

**"Game.exe MD5 stimmt nicht UND Datei ist nicht gepatcht!"** (bzw.
"MD5 does not match AND file is not patched!" in der englischen Ausgabe)
- Hast du den 1.09-Patch zuerst angewendet? Ohne ihn hat `Game.exe`
  andere Byte-Offsets und die MD5-Prüfung schlägt fehl.
- Bist du im richtigen Spielverzeichnis? Das Skript sucht `Game.exe`
  und `resource.cfg` direkt im angegebenen Pfad.

**"X Patch(es) konnten nicht angewendet werden"**
- Deine `resource.cfg` ist möglicherweise schon gepatcht (Re-Run ist
  OK, wird übersprungen).
- Wenn sie original ist und Patches fehlschlagen: prüfe, ob die Datei
  CRLF-Zeilenenden hat (`file resource.cfg` sollte "CRLF" zeigen).

**Spiel fragt nach dem Patchen immer noch nach CD**
- Prüfe, ob `data/CD2/Movies/`, `data/CD3/Movies/`, `data/CD4/Movies/`
  mit Inhalt existieren. Der Patcher legt das nicht an.
- Prüfe, ob die Pfade in `resource.cfg` zu deiner tatsächlichen `data/`-
  Struktur passen.

### Lizenz

MIT — siehe [LICENSE](LICENSE). Der Patcher-Code ist eigenständige
Arbeit; die gepatchten Spieldateien werden nicht verteilt.

Das Spiel "Emperor: Battle for Dune", seine Engine und alle Inhalte
sind Eigentum von Westwood Studios / Electronic Arts. Dieses Projekt
vertreibt kein urheberrechtlich geschütztes Material — es stellt ein
Werkzeug bereit, das Dateien verändert, die du bereits besitzen musst.

### Credits

- **Reverse Engineering & Patch-Design:** Nix (KI-Assistent) & Dirk
- **Disassembly & Verifikation:** ghidra, radare2
- **Testumgebung:** Linux Mint 22 + Wine 9.0, Fedora 41 + Proton 9.0

By Nix & Dirk, 2026. *"Reverse Engineering: 5% Inspiration, 95%
'sicher ist das nicht das Byte, das ich brauche'."*
