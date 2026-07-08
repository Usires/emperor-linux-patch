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

The original 2001 release has two compatibility obstacles on modern Linux:

1. **`Game.exe` calls `GetDriveTypeA("E:\\")`** at startup to verify the
   game CD is inserted. Without it, the game refuses to start.
2. **`resource.cfg` hard-codes CD drive letters** (`E:\`, `D:\`,
   `.\cd3\`, `.\cd4\`) for movie files and level data spread across 4 CDs.

This patch:

- **Patches 4 instructions in `Game.exe`** to bypass the CD-check at
  offsets `0x9668f`, `0x966c4`, `0x96731`, `0x968bf` (verified via
  disassembly).
- **Patches 8 path strings in `resource.cfg`** to point at a local
  `data/CD2/`, `data/CD3/`, `data/CD4/` directory layout.

The original `EMPEROR.EXE` and `PATCHW32.DLL` are **left untouched** —
the patch is layered on top of the official 1.09 update.

### Prerequisites

- A legally owned copy of **Emperor: Battle for Dune** (GOG, EA, original
  CD — any source)
- The official **1.09 English patch** applied: download
  [`EM109DE.exe`](https://www.google.com/search?q=emperor+battle+dune+1.09+patch+EM109DE)
  from the Westwood patch archive and run it once on your game directory.
  This updates `PATCHW32.DLL` to the 1.09 release and is required for
  the game to work on modern systems *regardless* of this Linux patch.
- **Python 3.8+** on the machine you run the patcher from
- The game files in a writable directory you control

> The 1.09 patch is not bundled here for licensing reasons. Apply it
> before running the Linux patch — the MD5 check in the script will fail
> otherwise.

### Usage

#### 1. Prepare the directory layout

Copy the movie files from each CD into a local `data/` subdirectory:

```bash
cd ~/Games/Emperor_FAUGUS/  # your game directory
mkdir -p data/CD2/Movies data/CD3/Movies data/CD4/Movies
# Copy from your CD rips / GOG install / original media
cp /path/to/CD2/Movies/* data/CD2/Movies/
cp /path/to/CD3/Movies/* data/CD3/Movies/
cp /path/to/CD4/Movies/* data/CD4/Movies/
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
    ✅ Patch 1: jne → NOP
    ✅ Patch 2: je → NOP
    ✅ Patch 3: je → jmp + NOP
    ✅ Patch 4: xor al,al → mov al,1

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

The game will start without a CD prompt and load movies/data from your
local `data/` directory.

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

Die Originalversion von 2001 hat zwei Kompatibilitätsprobleme auf modernem
Linux:

1. **`Game.exe` ruft beim Start `GetDriveTypeA("E:\\")` auf**, um zu
   prüfen, ob die Spiel-CD eingelegt ist. Ohne CD startet das Spiel nicht.
2. **`resource.cfg` enthält feste CD-Laufwerksbuchstaben** (`E:\`, `D:\`,
   `.\cd3\`, `.\cd4\`) für Filmdateien und Level-Daten auf 4 CDs.

Dieser Patch:

- **Patcht 4 Instruktionen in `Game.exe`** an den Offsets `0x9668f`,
  `0x966c4`, `0x96731`, `0x968bf`, um die CD-Prüfung zu umgehen (per
  Disassembly verifiziert).
- **Patcht 8 Pfad-Zeichenketten in `resource.cfg`**, sodass sie auf ein
  lokales `data/CD2/`, `data/CD3/`, `data/CD4/`-Verzeichnis zeigen.

Die originale `EMPEROR.EXE` und `PATCHW32.DLL` bleiben **unangetastet** —
der Patch setzt auf dem offiziellen 1.09-Update auf.

### Voraussetzungen

- Eine legal erworbene Kopie von **Emperor: Battle for Dune** (GOG, EA,
  Original-CD — egal)
- Der offizielle **1.09-Patch** muss angewendet sein: lade
  [`EM109DE.exe`](https://www.google.com/search?q=emperor+battle+dune+1.09+patch+EM109DE)
  aus dem Westwood-Archiv und führe es einmal im Spielverzeichnis aus.
  Es aktualisiert `PATCHW32.DLL` auf den 1.09-Stand und ist Voraussetzung
  dafür, dass das Spiel auf modernen Systemen läuft — *unabhängig* von
  diesem Linux-Patch.
- **Python 3.8+** auf dem Rechner, auf dem du den Patcher ausführst
- Die Spieldateien in einem beschreibbaren Verzeichnis

> Der 1.09-Patch ist aus lizenzrechtlichen Gründen nicht im Repo
> enthalten. Wende ihn vor dem Linux-Patch an — sonst schlägt die
> MD5-Prüfung fehl.

### Verwendung

#### 1. Verzeichnisstruktur vorbereiten

Kopiere die Filmdateien von jeder CD in ein lokales `data/`-Unterverzeichnis:

```bash
cd ~/Games/Emperor_FAUGUS/  # dein Spielverzeichnis
mkdir -p data/CD2/Movies data/CD3/Movies data/CD4/Movies
# Aus CD-Rips / GOG-Installation / Original-Medien kopieren
cp /path/to/CD2/Movies/* data/CD2/Movies/
cp /path/to/CD3/Movies/* data/CD3/Movies/
cp /path/to/CD4/Movies/* data/CD4/Movies/
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

Das Spiel startet ohne CD-Abfrage und lädt Filme/Daten aus deinem
lokalen `data/`-Verzeichnis.

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
