# MEGA65-BASIC-65-Paritaets-Libraries

Stand: 2026-07-06. Dieses Dokument entwirft ladbare lisp65-Libraries, die
MEGA65-BASIC-65-Komfort fuer Grafik, Sound, Eingabe, Datei-I/O und
Systemzugriff abdecken. Es ist ein Post-MVP-Plan, kein neues Gate fuer
`make mvp-ship`.

Referenzen:

- MEGA65 BASIC 65 Reference PDF, March 4, 2024:
  <https://files.mega65.org/files/m/mega65-basic65-reference_94Fyc5.pdf>
- Lokaler Snapshot: `docs/reference/MEGA65_BASIC_65_Referenzhandbuch.pdf`
- Editierbare Referenzquelle im MEGA65-User-Guide-Projekt:
  <https://github.com/MEGA65/mega65-user-guide/blob/master/appendix-basic65.tex>
- Lokale Vorarbeit: `docs/reference/platform-layer.md`,
  `docs/library-modularization-strategy.md`, `docs/core-vs-library.md`,
  `docs/post-mvp-roadmap.md`

## Ziel

Feature-Paritaet heisst hier: Ein lisp65-Nutzer soll die praktischen
MEGA65-BASIC-Faehigkeiten erreichen koennen, ohne BASIC-Syntax, Zeilennummern
oder den BASIC-Programmeditor zu emulieren.

Nichtziel:

- keine BASIC-Token-/Syntax-Kompatibilitaet;
- keine Emulation von `AUTO`, `LIST`, `RENUMBER`, `CONT`, BASIC-Arrays,
  BASIC-Variablennamen oder Direct-Mode-Sonderfaellen;
- keine grossen neuen Bank-0-Flaechen fuer Komfortbefehle;
- keine Disk-Admin-Befehle wie `HEADER`, `BACKUP`, `COLLECT` im normalen
  User-Bundle.

Die API soll CL-/Lisp-nahe Namen behalten. BASIC-nahe Kurznamen werden nur in
einem optionalen Facade-Bundle installiert.

## Namens- und Namespace-Regel

lisp65 hat aktuell keine Packages. Deshalb sollten die stabilen Libraries
praefigierte Namen verwenden:

- stabile API: `m65-line`, `m65-sound`, `m65-joy`, `m65-dir`;
- optionale BASIC-Facade: `line`, `box`, `circle`, `sound`, `play`, `sprite`
  als Aliase nach explizitem `(load-lib "basic65")`.

Damit kann normale CL-nahe Stdlib weiter wachsen, ohne dass BASIC-Komfortnamen
den globalen Namespace dauerhaft dominieren.

## Schichten

```
User-Code / Demo / IDE
  |
  | optional: BASIC65-Aliase
  v
m65-text  m65-gfx  m65-draw  m65-sprite  m65-sound  m65-input  m65-disk
  \        |        /          /           /          /          /
   \       |       /          /           /          /          /
                 m65-hw
                   |
          Core-Prims: peek/poke/sys, screen-*, read-key/poll-key,
          disk-sector-Prims, load/save/load-lib
```

`m65-hw` ist der einzige gemeinsame Low-Level-Hub. Die sichtbaren
Komfort-Bundles sollen grob und domainbezogen bleiben, wie die aktuelle
Disk-Lib-Strategie es vorgibt.

## Bundle-Matrix

| Lib | D81 | Zweck | Requires | BASIC-65-Familien |
| --- | --- | --- | --- | --- |
| `m65-hw` | `M65HW` | Register, Speicher, Bit-/Word-Helfer, EDMA-Grundlagen | Core | `PEEK`, `POKE`, `WPEEK`, `WPOKE`, `SETBIT`, `CLRBIT`, `HASBIT`, `BANK`, `DMA`, `EDMA`, `SYS` |
| `m65-text` | `M65TEXT` | Textscreen, Farben, Cursor, Window, VSYNC | Core + `m65-hw` | `BORDER`, `BACKGROUND`, `COLOR`, `CURSOR`, `RCURSOR`, `WINDOW`, `SCNCLR`, `T@&`, `C@&`, `VSYNC` |
| `m65-gfx` | `M65GFX` | Grafikscreen-Kontext, Palette, Pen, Viewport, Pixelzugriff | Core + `m65-hw` | `GRAPHIC`, `SCREEN`, `SCNCLR`, `PEN`, `PALETTE`, `RGRAPHIC`, `RPALETTE`, `RPEN`, `PIXEL`, `VIEWPORT` |
| `m65-draw` | `M65DRAW` | Zeichenalgorithmen und Bitmap-Operationen | `m65-gfx` | `DOT`, `LINE`, `BOX`, `CIRCLE`, `ELLIPSE`, `POLYGON`, `PAINT`, `DMODE`, `DPAT`, `CUT`, `PASTE`, `GCOPY`, `CHAR`, `CHARDEF` |
| `m65-sprite` | `M65SPR` | Sprites, Attribute, Bewegung, Kollision | Core + `m65-hw`; optional `m65-disk` | `SPRITE`, `MOVSPR`, `SPRCOLOR`, `SPRSAV`, `RSPRITE`, `RSPPOS`, `RSPCOLOR`, `RSPRSYS`, `BUMP`, `COLLISION` |
| `m65-sound` | `M65SND` | SID-Soundeffekte und Musikstrings | Core + `m65-hw` | `SOUND`, `PLAY`, `RPLAY`, `TEMPO`, `VOL`, `ENVELOPE`, `FILTER` |
| `m65-input` | `M65IN` | Tastatur, Joystick, Paddle, Maus, Lightpen | Core + `m65-hw` | `GET`, `GETKEY`, `JOY`, `POT`, `MOUSE`, `RMOUSE`, `LPEN` |
| `m65-disk` | `M65DISK` | strukturierte Disk-/Datei-API ueber F011/D81 | Core + residenter Disk-Loader | `DIR`, `DISK`, `DS`, `DS$`, `RDISK`, `CHDIR`, `MKDIR`, `DOPEN`, `DCLOSE`, `APPEND`, `PRINT#`, `INPUT#`, `LINE INPUT#`, `FREAD#`, `FWRITE#`, `BLOAD`, `BSAVE`, `BVERIFY`, `DVERIFY`, `DLOAD`, `DSAVE`, `RENAME`, `SCRATCH`, `TYPE` |
| `m65-system` | `M65SYS` | bewusst gefaehrliche System-/Admin-Helfer | Core + `m65-hw` | `SPEED`, `RSPEED`, `MEM`, `WAIT`, eingeschraenktes `SYS TO`, optional `FREEZER`/`MONITOR` |
| `basic65` | `BASIC65` | Alias-/Facade-Bundle fuer BASIC-nahe Namen | explizite Auswahl | installiert Kurznamen und Convenience-Makros |

Runtime-v1 sollte keine impliziten Abhaengigkeiten laden. Nutzer oder Facade
laden explizit:

```lisp
(load-libs "m65hw" "m65gfx" "m65draw")
(m65-screen 320 200 2)
(m65-pen 1)
(m65-line 25 25 295 175)
```

Spaeter kann ein Manifest-Loader `requires` automatisch aufloesen. Bis dahin
bleibt die Reihenfolge sichtbar und testbar.

## API-Entwurf

### `m65-hw`

Basis fuer alle anderen MEGA65-Libs:

- `(m65-peek address)` / `(m65-poke address byte)`
- `(m65-wpeek address)` / `(m65-wpoke address word)`
- `(m65-setbit address bit)`, `(m65-clrbit address bit)`,
  `(m65-hasbit address bit)`
- `(m65-edma-copy len source target)`, `(m65-edma-fill len byte target)`
- `(m65-sys address a x y z s)`, spaeter `(m65-sys-to ...)`
- Registerkonstanten fuer VIC-IV, SID, CIA, F011, DMAgic, Systempalette

Erster Auditpunkt: unsere `peek`/`poke`-Prims muessen klar dokumentieren, ob
sie 28-bit/flat-Adressen wie BASIC akzeptieren oder nur den aktuellen
Bank-0-/I/O-Sichtbereich. Falls nicht flat, braucht `m65-hw` eine kleine
gegatede Kernel-Naht fuer 28-bit Reads/Writes oder nutzt vorhandene EXT-/DMA-
Helfer.

### `m65-text`

Text- und UI-Komfort, nicht Bitmap-Grafik:

- `(m65-border color)`, `(m65-background color)`, `(m65-color color)`
- `(m65-cursor on col row)`, `(m65-cursor-position)`
- `(m65-window left top right bottom clear)`
- `(m65-text-code col row)`, `(m65-set-text-code col row code)`
- `(m65-text-color col row)`, `(m65-set-text-color col row color)`
- `(m65-text-clear)`, `(m65-vsync raster)`

Das kann teilweise auf vorhandenen `screen-*`-Prims liegen. Direkte `T@&`/
`C@&`-Paritaet ist eine gute Lisp-Lib, solange der Screen-RAM-Pfad sicher
gepinnt ist.

### `m65-gfx`

Grafik-Kontext, Ressourcen und State:

- `(m65-graphic-clear)`
- `(m65-screen width height depth)` fuer den einfachen BASIC-`SCREEN`-Fall
- `(m65-screen-def screen width-flag height-flag depth)`
- `(m65-screen-open screen)`, `(m65-screen-set draw view)`,
  `(m65-screen-close screen)`
- `(m65-screen-clear color)`
- `(m65-pen color)`, `(m65-pen-state n)`
- `(m65-palette screen index r g b)`,
  `(m65-palette-color index r g b)`, `(m65-palette-restore)`
- `(m65-palette-value screen index channel)`
- `(m65-pixel x y)`
- `(m65-viewport-def x y width height)`, `(m65-viewport-clear)`
- `(m65-graphic-state screen parameter)`

V1 sollte nicht versuchen, BASICs ROM-Screen-Allokator exakt nachzubauen.
Naheliegender Start ist der bereits belegte sichtbare Bank-4-Pfad aus
`docs/reference/platform-layer.md`: 640x200x1, 16000 Bytes ab `$40000`,
80 Bytes pro Zeile. Danach koennen 320/640 und 1/2/4/8 Bitplanes wachsen.

### `m65-draw`

Zeichnen auf dem von `m65-gfx` gesetzten Kontext:

- `(m65-dot x y color)` und `(m65-line x0 y0 x1 y1)`
- `(m65-polyline points)` als Listenform fuer BASICs variable `LINE`
- `(m65-box x0 y0 x1 y1 solid)`
- `(m65-quad x0 y0 x1 y1 x2 y2 x3 y3 solid)`
- `(m65-circle x y radius flags start stop)`
- `(m65-ellipse x y rx ry flags start stop)`
- `(m65-polygon x y rx ry sides drawsides subtend angle solid)`
- `(m65-paint x y mode border-color)`
- `(m65-dmode ...)`, `(m65-dpat ...)`
- `(m65-cut x y w h)`, `(m65-paste x y)`, `(m65-gcopy ...)`
- `(m65-char col row height width direction string font-address)`
- `(m65-chardef index rows)`

Prioritaet: `dot`, `line`, `box`, `circle` zuerst. `paint` braucht eine
kontrollierte Arbeitsliste oder einen nativen Scratch-Helper, damit es nicht
rekursiv den Stack sprengt. `cut`/`paste`/`gcopy` sollten ueber EDMA/Scratch
kommen, nicht ueber langsame Byte-fuer-Byte-Lisp-Schleifen.

### `m65-sprite`

Paritaet zur BASIC-Sprite-Schicht:

- `(m65-sprite-clear)`
- `(m65-sprite-load name)`, `(m65-sprite-save name)` ueber `m65-disk`
- `(m65-sprite n on color priority x-expand y-expand multicolor)`
- `(m65-sprite-color mc1 mc2)`
- `(m65-sprite-hires on)`
- `(m65-sprite-pos n x y)`, `(m65-sprite-move n angle speed)`
- `(m65-sprite-move-to n x0 y0 x1 y1 speed)`
- `(m65-sprite-param n param)`, `(m65-sprite-system-param param)`
- `(m65-sprite-position n param)`, `(m65-sprite-multicolor n)`
- `(m65-bump type)`
- `(m65-collision-enable type handler)` / `(m65-collision-disable type)`

V1 sollte direkte Positionierung, Attribute, Multicolor und Polling-Kollision
liefern. BASICs asynchrone `MOVSPR`-Bewegung und `COLLISION`-Interrupts
brauchen eine Runtime-Tick-/Callback-Entscheidung; bis dahin ist ein expliziter
`(m65-sprite-step)`-Scheduler die sauberere Library-Loesung.

### `m65-sound`

Soundeffekte und Musik:

- `(m65-sound voice freq dur dir min sweep wave pulse)`
- `(m65-sound-clear)`
- `(m65-vol right left)`
- `(m65-tempo value)`
- `(m65-envelope n attack decay sustain release wave pulse)`
- `(m65-filter ...)`
- `(m65-play v1 v2 v3 v4 v5 v6)`
- `(m65-playing-p voice)`

V1 kann direkte SID-Register fuer einfache Toene und `sound-clear` nutzen.
BASICs `SOUND` ist asynchron; `PLAY` laeuft ueber getrennte SID-Voice-Gruppen
und Musikstrings. Fuer echte Paritaet brauchen wir entweder einen Timer-/IRQ-
Tick in der Runtime oder einen explizit vom Programm aufgerufenen
`(m65-sound-step)`. Ohne diesen Tick ist nur "Tone setzen" paritaetsnah,
nicht Hintergrundmusik.

### `m65-input`

Eingabe als strukturierte Lisp-Werte:

- `(m65-key)` nichtblockierend, `(m65-getkey)` blockierend
- `(m65-joy port)` mit Richtungsnibble und Button-Bits
- `(m65-joy-direction state)`, `(m65-joy-button-p state n)`
- `(m65-pot port)`
- `(m65-mouse-on port sprite hot-x hot-y x y)`, `(m65-mouse-off)`
- `(m65-mouse-state)` -> Liste `(x y buttons)` oder `nil`
- `(m65-lpen)` spaeter

Die API sollte nicht BASICs "Rueckgabe per Variable" kopieren. Lisp gibt eine
Liste oder `nil` zurueck.

### `m65-disk`

Der aktuelle MVP hat `load`, `save` und `load-lib`. BASIC-Paritaet braucht
darueber hinaus eine nutzbare Datei- und Directory-Schicht:

- `(m65-dir pattern unit)` -> Liste von Eintraegen, kein Screen-Print
- `(m65-disk-status)` -> Liste oder String fuer `DS`/`DS$`
- `(m65-disk-prop n)` fuer `RDISK`
- `(m65-chdir name unit)`, `(m65-mkdir name unit)`
- `(m65-delete name unit)`, `(m65-rename old new unit)`
- `(m65-copy src dst unit)`, `(m65-concat sources dst unit)`
- `(m65-open channel name mode unit)`, `(m65-close channel)`,
  `(m65-append channel name unit)`
- `(m65-read-line channel)`, `(m65-read-byte channel)`,
  `(m65-write-string channel string)`, `(m65-write-byte channel byte)`
- `(m65-bload name address raw unit)`, `(m65-bsave name start end raw unit)`
- `(m65-type name unit)` als Convenience ueber read-line/print

Die V1-Implementierung sollte auf dem vorhandenen F011/D81-Walk und den
`%disk-*`-Prims aufbauen. REL-Dateien, IEC-Printer/Plotter und SD-Karten-Unit
12 sind separate spaetere Backends, keine Voraussetzung fuer die erste
MEGA65-D81-Paritaet.

### `m65-system`

Bewusst getrenntes Power-User-Bundle:

- `(m65-speed mhz)`, `(m65-speed-state)`
- `(m65-mem-reserve bank4-mask bank5-mask)`
- `(m65-wait address mask value)`
- `(m65-sys-to ...)`
- optional `(m65-freezer)` / `(m65-monitor)` nur nach UI-/Safety-Entscheidung

`HEADER`, `BACKUP`, `FORMAT`, `COLLECT`, `BOOT`, `GO64`, `MONITOR` und
`FREEZER` sind keine normalen App-Library-Funktionen. Sie gehoeren, wenn
ueberhaupt, in ein explizites Admin-/Danger-Bundle.

## BASIC-Facade

`basic65` kann Aliase und Makros installieren:

```lisp
(load-libs "m65hw" "m65gfx" "m65draw" "m65sound" "m65input" "basic65")

(screen 320 200 2)
(pen 1)
(line 25 25 295 175)
(sound 1 7382 50)
```

Die Facade sollte klein bleiben: keine eigenen Algorithmen, nur Aliase,
Defaults und eventuell BASIC-nahe Argumentformen. So kann man sie weglassen,
wenn ein Programm saubere `m65-*`-Namen bevorzugt.

## Paritaetsstufen

### Stufe A: sofort sinnvoll

Diese Funktionen sind mit heutiger Architektur plausibel als Bytecode-Libs:

- `m65-hw`: Bit-/Word-Helfer und Konstanten, sofern `peek`/`poke` reichen.
- `m65-text`: Border/Background/Textfarben, Screenzellen, VSYNC.
- `m65-gfx` V1: 640x200x1 Bank-4-Framebuffer, `screen`, `clear`, `pixel`.
- `m65-draw` V1: `dot`, `line`, `box`, einfache `circle`.
- `m65-sound` V1: `sound-clear`, einfache SID-Toene.
- `m65-input` V1: `key`, `joy`, einfache Button-Helfer.
- `m65-disk` V1: strukturierter Directory-Walk, Delete/Rename/Mkdir soweit
  vorhandene Disk-Prims es tragen.

### Stufe B: kleine Runtime-Naht noetig

- 28-bit flat `peek`/`poke`/`wpoke`, falls current Prims nicht reichen.
- EDMA-copy/fill als sichere Primitive, statt DMAgic-Registersequenzen in
  Lisp zu duplizieren.
- Schneller Pixel-/Fill-Helper fuer Bitplanes > 1.
- Kanalbasierte Datei-I/O-Prims fuer `DOPEN`/`PRINT#`/`INPUT#`-Paritaet.
- Timer-/Tick-Hook fuer asynchrones `PLAY`, `SOUND` und `MOVSPR`.

### Stufe C: spaeter oder eingeschraenkt

- `PAINT` als echter Flood-Fill ohne Arrays/Vektoren.
- `CUT`/`PASTE`/`GCOPY` mit beliebigen Bitplane-Tiefen.
- `COLLISION`-Callbacks wie BASIC-Interrupt-Handler.
- REL-Dateien und Printer/Plotter-Devices.
- SD-Karten-Unit `U12` und Mount-Management.
- Voller BASIC-`PRINT USING`-Numerikkomfort; das gehoert eher zu `format`.

### Ausgeschlossen aus der normalen Paritaet

- BASIC-Programmeditor-Kommandos (`AUTO`, `LIST`, `EDIT`, `RENUMBER`,
  `DELETE`, `MERGE`, `NEW`, `CONT`, `RUN` als BASIC-Programmlauf).
- Disk-Destruktivbefehle im Komfort-Bundle (`HEADER`, `BACKUP`, Low-Level
  Format).
- GO64-/Monitor-/Freezer-Flows als normale App-Funktionen.

## Pilot-Reihenfolge

1. **P1 `m65-hw` + Host-RAM-Oracle.** Registerkonstanten, bit/word helpers,
   `peek`/`poke`-Semantik auditieren. Keine HW-Smokes.
2. **P2 `m65-gfx`/`m65-draw` Bank-4 monochrom.** `screen`, `clear`, `dot`,
   `line`, `box`; Host-Oracle gegen simulierten 16000-B-Framebuffer; optionaler
   xemu-Smoke nur ueber die dokumentierten Prozess-Safety-Skripte.
3. **P3 `m65-sound` simple tone.** SID-Registerwerte hostseitig pruefen,
   Geraete-Smoke nur manuell/kurz.
4. **P4 `m65-input`.** Joystick-/Key-Helfer, danach Maus-API ohne Pointer-
   Sprite-Automatik.
5. **P5 `m65-disk` V1.** Strukturierte Directory-API und einfache
   read/write-String-Helfer ueber vorhandene Disk-Prims.
6. **P6 `m65-sprite`.** Erst unmittelbare Sprite-Attribute und Positionen,
   danach Bewegung/Collision.
7. **P7 `basic65` Facade.** Erst wenn die praefigierten Libs stabil sind.

## Teststrategie

- Jede Lib bekommt eine `tests/bytecode/libs/p0-m65*.json`-Suite und ein
  eigenes D81-Artefakt.
- Hardware-nahe Funktionen brauchen Host-Oracles mit simuliertem RAM/Framebuffer
  und klaren Registerwrites, bevor irgendein xemu-/HW-Smoke sinnvoll ist.
- Xemu-/xmega65-Ziele bleiben explizit und duerfen nicht von `make check`
  unkontrolliert gestartet werden. Prozess-Safety aus
  `docs/xmega65-process-safety.md` bleibt Pflicht.
- Device-Smokes fuer Grafik sollten PNG/Dump-orientiert sein: Framebuffer-Bytes
  plus sichtbare Pixelsignatur. Sound-Smokes koennen initial nur Register-/
  Status-Dumps pruefen; echte Hoerprobe bleibt manuell.

## Offene Entscheidungen

- Soll `peek`/`poke` fuer `m65-hw` flat 28-bit garantieren oder fuehren wir
  separate `m65-flat-peek`/`m65-flat-poke` ein?
- Nutzen `m65-gfx` und `m65-draw` dauerhaft den direkten Bank-4/5-Pfad oder
  bauen wir spaeter eine ROM-BASIC-kompatible Screen-Allokation nach?
- Kommt ein allgemeiner Timer-/Tick-Hook in den Core, oder bleiben Musik und
  Sprite-Bewegung explizit kooperativ?
- Wie viel BASIC-Alias-Oberflaeche ist ohne Packages akzeptabel?
- Wann werden Vektoren/Arrays verfuegbar genug, um `paint`, Sprite-Daten und
  Audiosequenzen nicht mehr als Listen/Strings modellieren zu muessen?
