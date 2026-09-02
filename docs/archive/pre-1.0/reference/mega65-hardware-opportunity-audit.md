# MEGA65 Hardware Opportunity Audit

Stand: 2026-07-07.

Dieses Audit prueft, ob lisp65 den MEGA65 bereits gut genug nutzt, und welche
Hardware-Hebel noch fehlen. Grundlage sind die lokalen Referenz-PDFs in
`docs/reference/`, bestehende Projektbefunde und eine aktuelle Web-Recherche zu
MEGA65-Dokumentation/Core-Status.

## Kurzfazit

Wir nutzen den MEGA65 fuer das MVP bereits deutlich jenseits eines C64-Modells:
40-MHz-Modus, VIC-IV-Screen, F018-DMA, EXT-RAM, F011-Disk-I/O, Etherload/JTAG
und Bytecode-Stdlib in erweitertem Speicher sind produktiv im Projekt.

Nicht voll erschoepft sind aber mehrere MEGA65-spezifische Pfade:

1. Enhanced/Inline-DMA fuer 28-bit-Ziele, Color-RAM, Screen-Scroll und Blits.
2. 45GS02-Flat-Access (`[bp],Z`) als kleiner 28-bit-Accessor statt DMA fuer
   einzelne Bytes/Worte.
3. 45GS02-Q-Register und Hardware-Multiplier/Divider fuer Fixnum/Fixed-Point.
4. Attic RAM als kalter Bulk-Speicher fuer Quellen, Assets und FASLs.
5. F011-Sektorpuffer/DMA-Prefetch statt byteweisem `$DE00`-Transfer.
6. VIC-IV/Sprite/Audio-DMA/Ethernet als on-demand Library-Familien.

Die Strategie bleibt: erst messen, dann nur die minimalen HW-Naehte resident in
Bank 0 ziehen. Die API-Oberflaeche gehoert in Lisp-Libs.

## Versionslage der Web-Recherche

- Die offiziellen PDF-Handbuecher werden laut MEGA65-Doku-Landing-Page und
  `MEGA65/mega65-user-guide` laufend aus der User-Guide-Quelle gebaut. Die lokal
  vorliegenden `mega65-book.pdf`, `mega65-chipset-reference.pdf` und
  `mega65-userguide.pdf` sind vom 2026-04-08 und damit fuer dieses Audit aktuell
  genug.
- `MEGA65/mega65-core` listet als neuesten Release `release-0.97.2` vom
  2025-09-28; dieser Release ist ein R6A-Kompatibilitaets-Patch ohne neue
  Features oder Bugfixes. Daraus folgt: kein neuer Core-Hebel hebt unsere
  bisherigen HW-Gates automatisch auf.
- Die offenen Core-Issues enthalten weiterhin VIC-IV-/Color-RAM-nahe Themen
  (`Colour RAM can be written from unintended address ranges`,
  `Colourram unintentionally wraps around at 32kb`, RRB/FCM-Themen). Fuer
  Grafik/Color-RAM-Features gilt deshalb: echte HW-Tests vor Produktfreigabe.

## Bereits Erschlossen

- CPU wird in `src/main.c` explizit in den 40-MHz-Modus gesetzt (`$D054` VFAST).
- F018-DMA ist der verifizierte Standardpfad fuer EXT-RAM:
  `vm_dma`/`ext_dma` nutzen feste 12-Byte-Listen und registerfreien Trigger.
- EXT-RAM wird fuer Bytecode-Blob, Code-Region, Symbolbereiche und EXT-Heap
  genutzt.
- F011-Pfade decken `load`, `save`, `load-lib`, FASL/D81 und HW-Smokes ab.
- Eigener Screen-Treiber umgeht den KERNAL-Scroll-Crash und nutzt VIC-IV 80x25.
- Etherload/JTAG-Harness ist der reale Arbiter; xemu ist nur Vorfilter.

## Wichtige Referenzbefunde

### 28-bit Address Space und Color RAM

Die Chipset-Referenz beschreibt einen 28-bit-Adressraum bis 256 MB. Die ersten
384 KB Chip-RAM sind real relevant; Attic RAM liegt ab `$8000000`. Color RAM ist
32 KB gross und liegt vollstaendig bei `$FF80000-$FF87FFF`; nur die ersten 1-2
KB sind ueber die klassischen Fenster erreichbar. Die Referenz empfiehlt fuer
vollen Color-RAM-Zugriff Advanced-DMA oder 32-bit Base-Page-Indirect-Access.

Projektbefund: CRAM2K (`$D030` Bit 0) hat auf unserer HW den Disk-Lib-Ladepfad
gebrochen. Daher bleibt CRAM2K ausgeschlossen; der richtige Farbfix ist direkter
28-bit-Zugriff oder Enhanced-DMA auf `$FF80000`.

### DMA

Die MEGA65-DMA laeuft mit ca. 40 MB/s Fill bzw. 20 MB/s Copy, kann den vollen
256-MB-Adressraum adressieren, kennt Option-Listen, Transparenzwerte,
fractional/stride-Adressierung, Line-Drawing und Audio-DMA. Unser aktueller
Produktpfad nutzt nur den konservativen F018/F018B-Listenpfad via `$D700`, nicht
Enhanced-DMA via `$D705` und nicht Inline-DMA via `$D707`.

Wichtig: DMA blockiert die CPU bis zum Job-Ende; Audio-DMA ist die Ausnahme.
Grosse Jobs muessen bei Echtzeitpfaden ggf. segmentiert werden.

Live-HW-Befund 2026-07-07: Enhanced-DMA ist fuer Bank-4-Copy/Fill, Attic-RAM-
Roundtrip und Color-RAM-Fill/Pattern-Readback gruen. Das reicht fuer eine kleine
interne EDMA-Plattformnaht fuer Screen/Color/Attic-Experimente; nicht fuer eine
breite Lisp-Primitive-API im Kern.

### 45GS02 Flat Access und Q-Register

Die 45GS02 kann 28-bit-Adressen ueber 32-bit Base-Page-Indirect-Zugriffe
ansprechen. Die Doku beschreibt `LDA [ptr],Z`/`STA [ptr],Z` fuer einzelne
Upper-Memory-Bytes und `LDQ`/`STQ`/`ADCQ` usw. fuer 32-bit-Operationen ueber das
Pseudo-Register Q = A/X/Y/Z.

Projektbefund: aeltere Tests in `docs/mega65-extram-access.md` sahen
Flat/MAP-Reads in xemu unzuverlaessig und haben F018-DMA als einzigen
bank-agnostischen Pfad gepinnt. Der Live-HW-Smoke vom 2026-07-07 bestaetigt
diese Vorsicht: Flat Access ist gegen Bank-0-High-RAM gruen, aber gegen Bank 4
und Color RAM rot (`0xff` statt des geschriebenen Bytes). Damit ist Flat Access
kein allgemeiner `peek28`/`poke28`-Pfad und kein EXT-/Color-Produktpfad.

Q-Register sind im Live-HW-Smoke gruen, wenn Inline-Asm das Z-Register danach
wieder auf 0 setzt. llvm-mos-generierter Code nutzt Z fuer spaetere Stores; ein
Q-Helper muss diese Konvention respektieren.

### Hardware-Math

Der MEGA65 hat Hardware-Register fuer 32-bit Multiplikation und Division:
`MULTINA`, `MULTINB`, `MULTOUT`, `DIVOUT` und `DIVBUSY`. Multiplikation ist laut
Doku sofort verfuegbar; Division kann bis ca. 20 Zyklen brauchen. Das ist fuer
spaetere Fixnum-/Fixed-Point-Kerne deutlich interessanter als breite
C-Arithmetik in Bank 0.

Live-HW-Befund 2026-07-07: Multiplikation und Division sind gruen, wenn die
Register byteweise angesprochen werden und Division explizit auf `DIVBUSY`
wartet. C-Struct-Zugriffe auf die IO-Register sind fuer den Harness nicht als
Ground Truth ausreichend.

### F011 / SD

Die F011/45IO27-Doku beschreibt neben byteweisem DRQ-Transfer auch einen
memory-mapped Sector Buffer (`$FFD6C00-$FFD6DFF`) und die Moeglichkeit, den
Buffer bei `$DE00-$DFFF` sichtbar zu machen. Der Puffer kann per DMA kopiert
werden und erlaubt, dass ein Sektor im Hintergrund geladen wird, waehrend das
Programm weiterarbeitet.

Projektbefund: fruehere Versuche mit Flat-Read/DMA direkt aus `$FFD6C00` waren
unzuverlaessig; der stabile Pfad ist aktuell `$D680=$81` plus `$DE00`. Mit JTAG
sollte ein neuer Sektorpuffer-DMA-Smoke entscheiden, ob wir beim Loader
Prefetch/Bulk-DMA sicher einsetzen koennen.

### VIC-IV, Sprites, Audio und Ethernet

VIC-IV kann Screen/Bitmap/Color/Charset/Sprites an flexible Adressen legen,
Sprites in erweiterten Modi betreiben, Palette/FCM/Raster-Rewrite nutzen und
mehrere 8-bit-Farb-Playfields darstellen. Audio-DMA bietet vier Kanaele fuer
8/16-bit Samples und niedrige Bank-0-Kosten bei Playback. 45E100 Ethernet hat
2-KB-Framebuffer, RX/TX-Interrupts und DMA-faehige Buffer.

Diese Themen sind fuer MVP-Budget nicht Kern-Entlastung, aber wichtig fuer
Post-MVP-Libraries und fuer eine bessere Dev-Transport-Schicht.

## Priorisierte Chancen

### P0: Enhanced-DMA als schmale Plattform-Naht

Ziel:

- `m65_edma_copy/fill` als interne, sehr kleine C/Asm-Naht fuer 28-bit
  Quelle/Ziel.
- Erst fuer Tests/Screen/Color-RAM, nicht sofort als allgemeines Lisp-Prim.

Erwarteter Nutzen:

- Color-RAM-Fix ohne CRAM2K.
- Screen-Scroll-Prototyp: Screen-RAM-Zeilen per DMA verschieben, Color-RAM
  passend mitziehen, nur neue Zeile malen.
- Spaetere Grafik-Blits mit Transparenzwert ohne CPU-Schleife.

Risiken:

- Bank-0-Kosten fuer generischen Helper koennen den Nutzen auffressen.
- Enhanced-DMA-Optionen muessen auf echter HW gegatet werden.
- Nicht alle exotischen C65-DMA-Ideen sind im aktuellen Core voll implementiert.

Gate:

- `edma-color-fill-hw`: 2000 Color-RAM-Zellen bei `$FF80000` setzen, Screenshot
  pruefen.
- `edma-screen-scroll-hw`: 80x25 Screen+Color eine Zeile schieben, Inhalt und
  Farben per Screenshot/JTAG pruefen.
- Footprint-Delta gegen CPU-Scroll messen.

Status 2026-07-08: `hw-access-smoke` und `hw-color-ram-smoke` bestaetigen EDMA
fuer Bank 4, Attic RAM und Color RAM. `hw-edma-screen-smoke` bestaetigt auf
echter HW zusaetzlich 80x25-Screen-RAM- plus 28-bit-Color-RAM-Scroll nach oben
inklusive Tail-Fill (`7/7` PASS).

Produktnaher Nachzug 2026-07-08: `src/screen.c` hat einen opt-in
`LISP65_SCREEN_EDMA_SCROLL`-Pfad, aber der Dev-Core-Footprint ist rot. Delta
gegen den normalen Dev-Core:

- `prg_bytes`: 40558 -> 40997 (+439)
- `bank0_text_data_bytes`: 40524 -> 40963 (+439)
- `bank0_bss_bytes`: 3033 -> 3047 (+14)
- `stack_gap_bytes`: 1466 -> 1012 (-454), Gate `1450`
- Status: `stack-gap-too-small,bank0-reserve-too-small`

Entscheidung: EDMA-Scroll bleibt opt-in und Messpfad, nicht Default-Core. Fuer
Produktintegration braucht es vorher Bank-0-Reclaim (~450 B+) oder eine deutlich
kleinere Assembly-Naht.

### P0: 45GS02 Flat-Accessor neu testen

Ziel:

- Kleinen HW-Smoke fuer `LDA/STA [bp],Z` gegen Bank 4/5, `$FF80000` und ggf.
  `$FFD6C00` bauen.

Erwarteter Nutzen:

- Einzelne Color-RAM- und Register-Writes ohne DMA-Setup.
- Einfachere Low-Level-Libs fuer `m65-hw` und Debug-Counter.
- Moeglicher schneller Pfad fuer sehr kleine EXT-Zugriffe, falls HW stabil ist.

Risiken:

- Projektgeschichte zeigt xemu/HW-Divergenzen; DMA bleibt fuer Heap/Bulk der
  sichere Standard.
- Inline-Asm muss llvm-mos-Registerdruck sauber ueberleben.

Gate:

- HW-JTAG-Roundtrip mit Ground-Truth-Readback, nicht nur sichtbare Farben.
- Separate xemu-Notiz: xemu darf hier fehlschlagen, wenn HW sauber ist; dann nur
  HW-gated freigeben.

Status 2026-07-07: HW-JTAG-Roundtrip ist fuer Bank-0-High-RAM gruen, fuer Bank 4
und Color RAM rot. Kein allgemeiner Flat-Accessor fuer EXT/Color-RAM; nur
gezielte Bank-0-Spezialfaelle weiter verfolgen.

### P0: Hardware-Math/Q fuer Fixnum und Fixed-Point evaluieren

Ziel:

- Winzige Assembly-Microbenchmarks fuer 16/32-bit `*`, `/`, `mod`, fixed `mul`,
  fixed `div`.
- Codegroesse und Laufzeit gegen llvm-mos-C-Ausgabe und VM-Bytecode messen.

Erwarteter Nutzen:

- Breitere Zahlenunterstuetzung ohne grosse C-Routinen.
- Weniger Laufzeitkosten fuer Fixed-Point-Demos, Grafik und spaeter AOT.
- Q-Register kann 32-bit Loads/Stores/Add/Sub kompakter machen.

Risiken:

- Als residenter Primitive-Satz darf das nicht zur Bank-0-Arithmetikbibliothek
  auswachsen.
- Signed/overflow-Semantik muss exakt zu Lisp-Fixnum-Konvention passen.

Gate:

- Host-Oracle fuer Semantik, HW-Smoke fuer Registerpfad, Footprint-Delta.
- Nur Kernoperationen resident; breite API in Lisp-Lib `fixed`/`m65-math`.

Status 2026-07-07: Registerpfad ist im HW-Smoke gruen. Offen bleibt
Semantik-/Footprint-Arbeit fuer signierte Fixnum- und Fixed-Point-Operationen.

### P1: Attic RAM als kalter Bulk-Store

Ziel:

- Attic RAM nicht als cons-Heap, sondern als Blob-/Asset-/Source-/FASL-Store.

Nutzen:

- Grosse Quellen, Assets, Demos und temporare Compiler-Artefakte ohne Bank-5-
  Kollisionen.
- Runtime-Core kann Cold Storage vom hot Chip-RAM trennen.

Risiken:

- Nicht fuer VIC/SID/Audio direkt sichtbar; Inhalte muessen nach Chip-RAM/DMA
  gestreamt werden.
- Laufzeit von dort ist langsamer; fuer hot code ungeeignet.

Gate:

- Attic roundtrip per EDMA/Flat-Access.
- Blob-Manifest mit klaren Regionen: code bank 5, symbol pool, disk scratch,
  attic blobs.

### P1: F011-Sektorpuffer-DMA und Prefetch

Ziel:

- Re-test, ob F011-Sektorpuffer direkt per DMA/Flat stabil gelesen werden kann.
- Wenn ja: Loader von byteweisem `$DE00` auf Bulk-DMA/Pipeline heben.

Nutzen:

- Schnellere `load-lib`, `load`, FASL-Streams.
- Weniger CPU-Zeit im Ladepfad.

Risiken:

- Fruehere Projektbefunde waren negativ; nur HW entscheidet.
- Kollision mit `$D680`/BUFSEL/SD-FDC-Fenster muss sauber kontrolliert werden.

Gate:

- `f011-buffer-dma-hw`: bekannten D81-Sektor lesen, per DMA nach Bank 4, JTAG-
  Dump gegen erwartete Bytes.
- Danach erst Prefetch.

### P1: MEGA65-BASIC-Paritaetslibs

Ziel:

- On-demand Lib-Familie statt Kernwachstum:
  `m65-hw`, `m65-gfx`, `m65-draw`, `m65-sprite`, `m65-sound`, `m65-input`,
  `m65-disk`, optional `basic65`-Facade.

Nutzen:

- Nutzer bekommen BASIC-nahe Grafik/Sound/IO-Faehigkeiten.
- Kernel enthaelt nur Register-/DMA-/F011-Minimalnaehte.

Risiken:

- VIC-IV/Color-RAM/RRB haben offene Core-Issues; visuelle HW-Gates sind Pflicht.

Gate:

- Kleine Demos pro Lib, jeweils als Quelle auf D81 inspizierbar und HW-geprueft.

### P2: ROM-Banks 2/3 als RAM fuer Runtime-Core

Ziel:

- Spaeterer Runtime-Core kann ggf. ROM-Write-Protect per Hypervisor-Trap loesen
  und Banks 2/3 als RAM nutzen.

Nutzen:

- Mehr Chip-RAM auf allen Modellen.

Risiken:

- KERNAL/Interrupt-/MAP-Vertraeglichkeit; Dev-Core braucht KERNAL-nahe
  Komfortpfade eher als Runtime-Core.
- Nicht MVP.

Gate:

- Eigenes IRQ-/MAP-Konzept, kein KERNAL-Aufruf im gemappten Zustand.

### P2: 45E100 Ethernet als Dev-Transport

Ziel:

- Post-MVP raw Ethernet/UDP-aehnlicher Transport fuer Remote-REPL, FASL-Push und
  Debug-Telemetrie.

Nutzen:

- Koennte Disk-/Etherload-Zyklen spaeter reduzieren.

Risiken:

- Eigener Netzwerkstack ist gross. Nur als sehr einfaches Raw-Protokoll
  realistisch.

Gate:

- Raw-frame echo/send/receive mit JTAG-Dumps, keine IP-Schicht als MVP.

## Nicht als naechstes verfolgen

- CRAM2K-Fix fuer Color RAM: auf unserer HW regressiert `load-lib`.
- MAP/banked-code als Sofort-Budgetfix: zu viele Linker-/IRQ-/Call-Konventions-
  Fragen.
- Raw-Floppy-Track-DMA fuer unsere D81-Libs: technisch spannend, fuer lisp65
  derzeit kein Nutzen.
- Hypervisor-private virtuelle Page-Register: nur nach separater HYPPO-Analyse.
- xemu-only-Freigaben fuer HW-Pfade: xemu ist nuetzlich, aber nicht der Arbiter.

## Konkreter naechster Arbeitsplan

Status 2026-07-08:

- `make hw-access-smoke-prg` baut ein isoliertes Access-Probe-PRG:
  `build/lisp65-mega65-hw-access-smoke.prg`.
- `make hw-color-ram-smoke-prg` baut ein isoliertes Color-RAM-Probe-PRG:
  `build/lisp65-mega65-hw-color-ram-smoke.prg`.
- `make hw-edma-screen-smoke-prg` baut ein isoliertes Screen/Color-EDMA-Probe-
  PRG: `build/lisp65-mega65-hw-edma-screen-smoke.prg`.
- Dry-Run-Deploys:
  `make hw-access-smoke-dry-run`,
  `make hw-color-ram-smoke-dry-run`,
  `make hw-edma-screen-smoke-dry-run`.
- JTAG-Readback:
  `make hw-access-smoke-readback`,
  `make hw-color-ram-smoke-readback`,
  `make hw-edma-screen-smoke-readback`.
- Live-HW-Readback:
  `hw-access-smoke` Pflichtfaelle `8/8` PASS,
  `hw-color-ram-smoke` Pflichtfaelle `2/2` PASS,
  `hw-edma-screen-smoke` Pflichtfaelle `7/7` PASS.
- Explorative Flat-Probes:
  `flat_bank4_obs=FAIL got=0x00ff want=0x007b`,
  `flat_cell_obs=FAIL got=0x00ff want=0x0002`.

1. EDMA als kleine interne Plattformnaht weiter nur opt-in halten. Der
   produktnahe Screen-/Color-Scroll-Prototyp ist HW-gruen, aber im Dev-Core
   footprint-rot.
2. Vor Default-Integration: Bank-0-Reclaim oder kleinere Assembly-Naht suchen;
   danach erneut `screen-edma-scroll-footprint-delta` und erst dann IDE-
   Stabilitaetsgate auf HW.
3. Flat Access fuer EXT-RAM und Color RAM explizit ausgeschlossen lassen. Nur
   Bank-0-High-RAM-Spezialfaelle duerfen ihn nutzen.
4. Q/HW-Math in Micro-Assembly-Prototypen fuer Fixnum/Fixed-Point evaluieren:
   signed Semantik, Overflow-Verhalten, Codegroesse und Laufzeit messen.
5. F011-Sektorpuffer-DMA separat testen; dieser Live-Lauf sagt dazu noch nichts.
6. Danach die Budgetstrategie aktualisieren.

## Quellen

Lokale Referenzen:

- `docs/reference/mega65-chipset-reference.pdf` (PDF-Datum 2026-04-08):
  System Memory Map, VIC-IV, F018 DMA, Audio DMA, 45E100, F011.
- `docs/reference/mega65-book.pdf` (PDF-Datum 2026-04-08):
  45GS02, MAP, 28-bit Machine Code, LDQ/STQ, Hardware-Math.
- `docs/reference/MEGA65_BASIC_65_Referenzhandbuch.pdf`: BASIC-65 API-Paritaet,
  EDMA, BLOAD/BSAVE, FREAD/FWRITE, Grafik/Sound/Sprite-Kommandos.
- `docs/mega65-extram-access.md`: Projektbefund zu DMA vs. MAP/Flat.
- `docs/ide-performance-analysis.md`: Projektbefund zu Scroll/Color-RAM/CRAM2K.

Web-Recherche:

- MEGA65 Docs Landing Page:
  https://mega65.atlassian.net/wiki/spaces/MEGA65/pages/21331992/Documentation%2B-%2BLanding%2BPage
- MEGA65 User Guide Repository:
  https://github.com/MEGA65/mega65-user-guide
- MEGA65 Core Releases:
  https://github.com/MEGA65/mega65-core/releases
- MEGA65 Core Issues:
  https://github.com/MEGA65/mega65-core/issues
- MEGA65 Core `iomap.txt`:
  https://github.com/MEGA65/mega65-core/blob/development/iomap.txt
- Enhanced-DMA Design Note:
  https://c65gs.blogspot.com/2018/01/improving-dmagic-controller-interface.html
- 45GS02 Q-Register Note:
  https://c65gs.blogspot.com/2021/05/debugging-32-bit-virtual-register.html
- ca65 45GS02 Mode:
  https://cc65.github.io/doc/ca65.html
