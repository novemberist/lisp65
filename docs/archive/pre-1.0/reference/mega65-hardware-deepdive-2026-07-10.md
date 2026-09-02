# MEGA65-Hardware-DeepDive-Manifest (2026-07-10)

Status: Wissens- und Ideensammlung, kein Produktvertrag und keine Roadmap.
Erstellt von Claude als paralleler Recherche-Auftrag; bewusst additiv zum
laufenden Sanierungsplan (`project-realignment-plan-2026-07-09.md`) — dieses
Dokument ändert keinen Produktcode und fordert keine Featurearbeit vor G6.

Quellenbasis:

- Lokale Referenz-PDFs (`docs/reference/`): MEGA65-Buch (2026-04-08, 1455 S.,
  bes. Appendix K „45GS02 Microprocessor“ und L „Instruction Sets“),
  Chipset-Referenz (2026-04-08, 245 S.), BASIC-65-Referenzhandbuch (2022).
- Projektinterne HW-Dokumente und Quellcode (u. a.
  `mega65-hardware-opportunity-audit.md`, `mega65-extram-access.md`,
  `mega65-file-io-research.md`, `mvp-hw-findings.md`, `src/mem.c`, `src/io.c`,
  `src/screen.c`, `src/vm_embed.c`).
- Internetrecherche: `iomap.txt`/Releases im mega65-core-Repo, HYPPO-Appendix
  des User-Guide-Repos (`appendix-hypervisor-calls.tex`), c65gs-Blog
  (P. Gardner-Stephen), MEGA65-Wiki, RetroCogs-Blog, Xemu-Wiki.
  **Verifikationsstatus (Nachlauf 2026-07-10):** Die Web-Fakten wurden in einem
  zweiten Durchgang adversarial gegen die Primärquellen geprüft (je 3
  unabhängige Prüfer): 18 Claims bestätigt (u. a. Enhanced-DMA-Interface,
  HOTREG, Audio-DMA-Register, HyperRAM-Bughistorie inkl. Root Cause,
  F011-Errata 2016, Core-Release-Daten, 300-ns-Attic-Naivlatenz), 4 als
  überdehnt korrigiert (im Text eingearbeitet, siehe §8/§9). Die
  HYPPO-Aufrufkonventionen sind gegen den Quelltext des User-Guide-Appendix
  geprüft. Verbleibende Einzelwerte ohne Gegenprüfung sind mit
  *(unverifiziert)* markiert.

---

## 1. Systemüberblick

### CPU und Takt

- 45GS02 mit 1 / 2 / 3,5 / 40,5 MHz. In den Slow-Modi zählt die CPU
  zyklenkompatibel zum 6502, führt Instruktionen aber intern schneller aus und
  idlet — Speicherzugriffe liegen bis zu ~7 µs neben dem C64-Timing (VSP-artige
  VIC-II-Tricks funktionieren deshalb nicht; auf dem MEGA65 sind sie unnötig,
  weil Screen-RAM frei platzierbar ist).
- Bei 40 MHz gilt 6502-Zyklenzählung nicht mehr: Branches sind oft billiger,
  `LDA/LDX/LDY/LDZ` kosten typisch +1 Takt.
- Geschwindigkeitshebel (Prioritäten beachten): `POKE 0,64/65` (C64-API),
  VIC-III `$D031` FAST-Bit, VIC-IV `$D054` Bit 6 VFAST — lisp65 setzt heute
  `$D054 |= $40` in `src/main.c`. Hypervisor kann per `$D67D.4` Full-Speed
  erzwingen.
- Badlines existieren physisch nicht (VIC-IV hat eigene Busse); eine
  Badline-Emulation (40-Takte-Pause) ist über `$D710` Bit 0 zuschaltbar und
  wird bei 40 MHz ignoriert.

### Speicherkarte (28 Bit, Auszug)

| Bereich | Inhalt |
| --- | --- |
| `$0000000–$005FFFF` | 384 KB Chip-RAM (40 MHz; Bänke 0–5) |
| `$0020000–$003FFFF` | „ROM“-Bereich (C65-ROM in RAM; via HYPPO-Trap schreibbar) |
| `$4000000–$7FFFFFF` | Slow Bus / Cartridge (1–10 MHz) |
| `$8000000–$87FFFFF` | 8 MB Attic-RAM (HyperRAM; DMA-fähig, nicht VIC-sichtbar) |
| `$FF80000–$FF87FFF` | 32 KB Colour-RAM (2-KB-Spiegel bei `$1F800`/`$D800`) |
| `$FFD0/1/2/3xxx` | I/O-Personalities C64 / C65 / Ethernet / MEGA65 |
| `$FFD6C00 / $FFD6E00` | FDC- / SD-Sektorpuffer (je 512 B) |
| `$FFD7100–$FFD717F` | UUID64, RTC, 64 B NVRAM |
| `$FFD8000–$FFDBFFF` | Hypervisor-ROM (16 KB, nur im Hypervisor-Modus) |
| `$FFDE800–$FFDEFFF` | Ethernet-Frame-Puffer (RX read-only / TX write-only) |

- **I/O-Knock** auf KEY `$D02F`: `$47,$53` = MEGA65-Personality (Voraussetzung
  für fast alle `$D6xx/$D7xx`-Register; lisp65: `m65_io_enable` in `src/io.c`).
  `$A5,$96` = VIC-III, `$45,$54` = Ethernet-Personality (Frame-Puffer ersetzt
  komplettes I/O bei `$D000` — CIA-IRQs vorher stilllegen!).
- **Banking-Prioritäten:** MAP-Instruktion > VIC-III-`$D030`-ROM-Banking >
  C64-Cartridge > `$00/$01`. `$D030` Bit 0 CRAM2K blendet das 2. Colour-RAM-KB
  über die CIAs — im Projekt als Produktpfad verworfen (bricht Disk-Lib-Laden).
- ROM-Bereich `$20000–$3FFFF` ist per HYPPO-Trap `toggle_rom_writeprotect`
  (`$D640`, A=`$70`) bzw. `rom_writeenable`/`rom_writeprotect` (`$D641`,
  A=`$02`/`$00`) als RAM freischaltbar → bis zu +128 KB.
  **Reset-Caveat (HW-gemessen 2026-07-10):** HYPPO re-staged bei jedem Reset
  das C65-ROM nach `$20000–$3FFFF` und überschreibt auch Bank 1 — Banks 1–3
  sind daher nur für session-transiente Daten nutzbar, nie für
  reset-persistente Artefakte. Reset-stabil gemessen: Bank 5 (bytegenau) und
  Attic-RAM `$8000000` (SHA-genau); beides ist jedoch nicht power-fest.

---

## 2. 45GS02-CPU-Erweiterungen

### Q-Pseudoregister (virtuelles 32-Bit-Register)

- A/X/Y/Z (A=LSB … Z=MSB) agieren als 32-Bit-Register; Auswahl per Präfix
  `NEG NEG` vor der Instruktion (Assembler-Mnemonics `LDQ, STQ, ADCQ, SBCQ,
  CPQ, EORQ, ANDQ, BITQ, ORQ, ASLQ, ASRQ, LSRQ, ROLQ, RORQ, INQ, DEQ`).
- Kein Immediate-Modus; 32-Bit-Konstanten via `LDA/LDX/LDY/LDZ #…` laden.
- Indexierte Modi mit Vorsicht (X/Y/Z tragen Datenteile); Ausnahme:
  Base-Page-Indirekt-Z-indiziert addiert Z **nicht** (außer bei `LDQ`) — genau
  dafür gedacht, kombiniert mit Flat-Access (`NEG NEG NOP`-Präfix) beliebige
  32-Bit-Werte irgendwo im Speicher in einer Instruktion zu lesen/schreiben.
- lisp65-Erfahrung: Q-Register-Pfad ist HW-grün, aber llvm-mos nutzt Z intern —
  Inline-Asm muss Z=0 restaurieren (`hw-access-smoke`).

### Flat-Memory-Access (`[zp],Z` mit 32-Bit-Pointer)

- `NOP`-Präfix ($EA) vor `LDA ($nn),Z` macht den Zero-/Base-Page-Pointer
  32 Bit breit (ACME-Syntax `LDA [$nn],Z`). Vom Buch als bevorzugter Weg für
  Einzelzugriffe > 1 MB empfohlen; DMA für Blöcke, MAP nur für Code-Banking.
- **Wichtige Projekt-Diskrepanz:** Auf echter HW (2026-07-07) war Flat-Access
  gegen Bank 4 und Colour-RAM rot (`flat_bank4_obs=FAIL`), nur Bank-0-High-RAM
  grün; xemu divergiert zusätzlich. Für lisp65 bleibt F018-DMA der einzige
  belastbare bank-agnostische EXT-Pfad (`docs/mega65-extram-access.md`).
  Buch-Empfehlung und HW-Realität widersprechen sich hier — falls Flat-Access
  je gebraucht wird, zuerst Core-Version/Erratum klären.

### Base Page, Stack, neue Instruktionen

- Base-Page-Register B verschiebt die „Zero Page“ beliebig (`TAB`/`TBA`) —
  256 schnelle Register pro Kontext; nützlich für VM-Registersätze oder
  Coroutine-Kontexte.
- 16-Bit-Erweiterungen: `PHW #$nnnn` (Wort pushen), Wort-Ops `INW/DEW/ASW/ROW`,
  16-Bit-Relative-Branches (`LBRA`-Familie), `NEG`, `ASR`; Stackpointer mit
  SPH-Anteil (16 Bit, `TYS`/`TSY`).
- `EOM` (= `NOP` auf 6502) beendet MAP-Sequenzen atomar gegen IRQs.

### MAP-Instruktion (>64 KB, >1 MB)

- Klassisch: 8-KB-Granularität via A/X (untere 32 KB) und Y/Z (obere 32 KB),
  Offsets in 256-B-Schritten. MEGA65-Erweiterung: X=`$0F` bzw. Z=`$0F`
  selektiert per A/Y das „Megabyte-Byte“ der 28-Bit-Adresse; für >1 MB sind
  bis zu drei MAP-Aufrufe nötig (Mapping-Code muss während der Sequenz sichtbar
  bleiben, sonst läuft die CPU ins Leere).
- Projekt-Status: MAP als Budgethebel bewust Post-MVP (Veneers, IRQ-/DMA-
  Verträglichkeit, llvm-mos-Linking ungeklärt).

---

## 3. DMAgic (F018/F018B + MEGA65-Erweiterungen)

### Performance und Trigger

- Fill ≈ 40,5 MB/s (1 B/Takt), Copy ≈ 20,25 MB/s (2 Takte/B); 8-KB-Blit in
  ~200 µs. **Die CPU steht während des Jobs** (nur Audio-DMA läuft weiter) —
  lange Jobs für Echtzeitpfade segmentieren; Command-Bit 3 „Yield“ existiert.
- Trigger: `$D700` LSB-Write startet Legacy-Job (`$D701` MSB, `$D702` Bank —
  **Write auf `$D702` löscht `$D704`**, `$D704` = Megabyte der Listenadresse),
  `$D703` Bit 0 wählt F018 (11-B-Liste) vs. F018B (12-B-Liste, Cmd-MSB).
  `$D705` = Enhanced-Job (Options-Tokens), `$D706` = Enhanced im aktuellen
  CPU-Mapping, **`$D707` = Inline-DMA**: Liste folgt direkt im Instruktionsstrom,
  die CPU setzt hinter der Liste fort — kompaktester Aufrufpfad, im Projekt
  bisher ungenutzt.
- Job-Liste: Cmd (Copy/Fill implementiert; Swap/MINTERM-Mix fehlen im Core),
  Count, Src, Src-Bank+Flags, Dst, Dst-Bank+Flags, Modulo. Flag-Bits je Seite:
  HOLD, MODULO, DIR (dekrementierend), I/O-Sichtbarkeit während des Jobs.

### Enhanced-Options (vor der Liste, `$00` terminiert)

| Token | Wirkung |
| --- | --- |
| `$80 xx` / `$81 xx` | Src-/Dst-Bits 20–27 („MB-Byte“) → volle 28-Bit-Adressen (Colour-RAM `$FF…`, Attic `$80…`) |
| `$82/$83`, `$84/$85` | Src-/Dst-Skip-Rate (Bruchteil/ganze Bytes) → Striding, Skalierung (~20 MPixel/s Texture-Scaling) |
| `$86 xx`, `$06/$07` | Transparenzwert / Transparenz an/aus (Bytes mit Wert xx werden nicht geschrieben) |
| `$87–$8F`, `$97–$9F` | Hardware-Line-Drawing (Dst/Src): ≈40,5 MPixel/s Linien |
| `$0A/$0B` | Listenformat F018/F018B erzwingen |
| `$0D/$0E/$0F` | Raw-Flux-Floppy-Writes/-Reads (beliebige Diskformate) |

- Trick: HOLD + I/O-Flag ⇒ 20,5 M Writes/s auf **ein** Register
  (z. B. `$D021`-Rasterbars).
- lisp65 nutzt heute: 12-Byte-F018-Listen mit registerfreiem Trigger und
  Pflicht-`"memory"`-Clobber (LTO-Reordering-Falle!, `src/mem.c`); Enhanced-DMA
  nur im opt-in EDMA-Scroll.

### Audio-DMA (`$D711`, `$D720–$D75F`)

- 4 Kanäle (2×L, 2×R, Cross-Volumes für Panning); 16/8/4-Bit-Samples (gepackte
  Nibbles!), Loop, Sinus-Kurzmodus; Frequenz = 24-Bit-Inkrement/2²⁴ × 40,5 MHz.
- Samples müssen im Chip-RAM liegen (kein Attic); Top-Adresse vergleicht nur
  16 Bit → max. 64 KB pro Sample. Läuft in CPU-Idle-Zyklen: sehr enge
  Warteschleifen ohne Speicherzugriff verursachen Aussetzer.

---

## 4. VIC-IV

### Speicher-Platzierung und kopierfreies Scrolling

- SCRNPTR `$D060–$D063` (28 Bit), COLPTR `$D064/65`, LINESTEP `$D058/59`
  (virtuelle Zeilenbreite), CHRCOUNT `$D05E`(+`$D063`-Bits), DISPROWS `$D07B`,
  TEXTXPOS/TEXTYPOS `$D04C–$D04F` (Pixel-Feinposition).
- Idiom: Screen-RAM byte-genau auf einen großen Textpuffer legen; Scrollen =
  SCRNPTR/COLPTR verschieben statt Zeilen kopieren; LINESTEP > CHRCOUNT gibt
  virtuelle Breite. **Das ist die architektonisch sauberste Alternative zum
  EDMA-Zeilenkopier-Scroll** (das an +439 B Bank 0 scheiterte).

### Hot-Registers — Fallstrick Nr. 1

- Solange `$D05D` Bit 7 (HOTREG) gesetzt ist, rekonstruiert **jeder** Write auf
  `$D011/$D016/$D018/$D031/$DD00`(VIC-Bank-Bits) sämtliche abgeleiteten
  VIC-IV-Register (SCRNPTR, LINESTEP, COLPTR=0, DISPROWS, …) — auch beim
  Zurückschreiben desselben Werts. Eigenes Video-Setup ⇒ HOTREG abschalten
  (`TRB $D05D` mit A=`$80`); Wiedereinschalten zweistufig (Pending-Cancel).
  Projekt-Randnote: der historische „Scroll-Müll“ kam von Farb-Writes, die bei
  Offset ≥1024 in `$DD00` einschlugen — ein Hot-Register-Treffer.

### SEAM / FCM / NCM / RRB

- Super-Extended Attribute Mode (`$D054` Bit 0 CHR16, sinnvoll mit Bit 2):
  2 Screen- + 2 Colour-Bytes pro Zelle → 8192 Chars, Flips, Alpha-Flag,
  NCM-Flag, 256-Farb-Vordergrund (FCOLMCM), BOLD+REVERSE = Alternate-Palette
  (effektiv 512 Farben).
- Full-Colour-Mode: 64 B/Char, 8 bpp; **Datenadresse = 64 × Charnummer,
  CHARPTR wird ignoriert**; Pixel `$FF` = Colour-RAM-Farbe, `$00` transparent.
  NCM: 4 bpp bei 16 px Zellbreite (halbe Fetch-Last). EXGLYPH (`$D063` Bit 7):
  Glyph-Daten aus Attic-RAM.
- Alpha-Blending (`$D054` Bit 7 + alpha_mode): Pixelwert = Alpha zwischen HG/VG
  → antialiasiertes Font-Rendering in Hardware (nur gegen Hintergrundfarbe).
- Raster-Rewrite-Buffer: GOTOX-Tokens im SEAM-Screen setzen die
  Render-X-Position pro Rasterzeile zurück/vor → mehrere Text-/Grafik-Layer,
  „Hardware-Bobs“ (Community-Tutorial: RetroCogs „RRB for pixies“), pixelgenaues
  per-Layer-Y-Scrolling via fcm_yoffs/rowmask. Grenze = Rasterzeit; DBLRR
  verdoppelt sie in V200. Fallstrick: Anzeige endet am letzten gezeichneten
  Zeichen — letzter Layer muss bis zum rechten Rand reichen.
- Upstream-Vorsicht: offene Core-Issues zu Colour-RAM-Wraps/RRB/FCM → jedes
  Grafik-Feature nur mit echtem HW-Gate (Projektregel bestätigt).

### Sprites, Raster-IRQ, Palette (Kurzform)

- Sprites: bis 64 px breit (`$D057`), Höhe bis 255 (`$D055/$D056`), Full-Colour
  4 bpp (`$D06B`), Tiles, 16-Bit-Pointer überall in 4 MB (`$D06E` Bit 7 +
  SPRPTRADR `$D06C–E`), H640/V400-Positionsauflösung, eigene Palettenbank;
  VIC-IV-Ringpuffer erlaubt horizontales Multiplexing.
- Raster-IRQ klassisch `$D012/$D019/$D01A`; fein: RASCMP `$D079/$D07A`,
  physische vs. VIC-II-Raster wählbar (FNRSTCMP).
- Palette: 4 Bänke à 256 × RGB in `$D100–$D3FF` (Bankwahl `$D070`);
  **Nibble-reversed** gespeichert; Bankwechsel wirkt sofort (billige
  Paletten-Animation).

---

## 5. Mathe-Einheit (`$D768–$D77F`, `$D70F`)

- MULTINA `$D770–73`, MULTINB `$D774–77` (32 Bit LE); Produkt 64 Bit in
  MULTOUT `$D778–7F`; Division: Quotient `$D76C–6F`, **32-Bit-Bruchteil**
  `$D768–6B` (Festkomma gratis). Busy-Flags `$D70F` Bit 7 DIVBUSY / Bit 6
  MULBUSY; Multiplikation effektiv sofort, Division ≤ ~20 Takte (Busy-Poll).
- Kombinatorisch — Outputs folgen den Inputs, kein Start-Kommando. Unsigned;
  Vorzeichen selbst normalisieren.
- Programmierbare Math-Unit `$D780 ff.` laut Buch „presently disabled“ — nicht
  darauf bauen.
- lisp65: Registerpfad HW-grün (byteweise Zugriffe als Ground Truth); offene
  Fragen sind signed-Semantik, Overflow-Verhalten und Codegröße vs. llvm-mos.

---

## 6. F011-FDC und SD-Controller

- F011 `$D080–$D08A`: Kommandos u. a. `$40` Read, `$84` Write(+Precomp),
  `$20` Spinup; Status `$D082` (BUSY/DRQ/EQ/RNF/CRC/LOST); TRACK/SECTOR/SIDE
  `$D084–86`; kein „Seek-Track-n“-Kommando (steppen + Header lesen); FDC-IRQs
  nicht implementiert → Polling.
- Sektorpuffer 512 B, memory-mapped `$FFD6C00` (FDC) / `$FFD6E00` (SD),
  BUFSEL `$D689` Bit 7; alternativ `$D680←$81` mappt ihn nach `$DE00–$DFFF`
  (lisp65-Produktionspfad). Der Puffer ist DMA-fähig — Bulk-DMA statt
  byteweisem `$DE00`-Kopieren ist als Gate `f011-buffer-dma-hw` definiert,
  aber nie gelaufen (P1-Opportunity).
- SD `$D680–$D693`: 32-Bit-Sektornummer `$D681–84`; Kommandos `$02/$03`
  Read/Write, `$04/$05/$06` Multi-Sektor-Write, `$0C` Flush, `$83/$84`
  Fill-Mode, `$C0/$C1` Slot-Wahl. **Write-Gate**: `$57` (bzw. `$4D` für
  Sektor 0) muss ≤ ~1 ms vor dem Write kommen. SPI ~20 MHz → praktisch
  1–1,7 MB/s; Karten ≤ 2 GB nicht unterstützt.
- Historische Errata (bestätigt, mega65-core Issue #22): der 2016er-Core
  hatte hängende und um exakt 2 Bytes rotierte F011-Sektor-Writes — lange
  behoben, erklärt aber die Vorsicht älterer Community-Quellen. xemu-F011 ist
  bis heute defekt (Projekterfahrung: Write-Kalibrierung nur am Gerät).
- 1581-Geometrie und der komplette produktivierte Lese-/Schreib-/Verify-Pfad
  stehen in `docs/mega65-file-io-research.md` / `docs/f011-write-calibration.md`.

---

## 7. HYPPO-Hypervisor (Traps `$D640–$D67F`)

### Aufrufkonvention

- Servicenummer in A, dann `STA $D640+X` (Registeradresse wählt die
  Trap-Gruppe); **direkt danach `CLV`** einlegen — die CPU führt das Folgebyte
  je nach Timing aus oder nicht (`NOP` riskiert 45GS02-Präfix-Deutung).
- Erfolg = Carry gesetzt; Fehler = Carry gelöscht + Fehlercode in A
  (`geterrorcode` A=`$38`). Übrige Register bleiben erhalten.
- `setname` (A=`$2E`): Dateiname null-terminiert ASCII < 63 Zeichen,
  **page-aligned** zwischen `$0000` und `$7E00` (Y = MSB) — deckt sich mit dem
  im Projekt gefundenen Alignment-Zwang.
- Hypervisor liegt bei `$8000–$BFFF` (im Hypervisor-Modus); Freeze/Unfreeze und
  Task-Switching laufen darüber.

### Servicetabelle (User-Guide-Appendix, Auswahl mit A-Codes an `$D640`)

| Gruppe | Services |
| --- | --- |
| Version/Fehler | `getversion $00`, `geterrorcode $38` |
| Laufwerk | `getdefaultdrive $02`, `getcurrentdrive $04`, `selectdrive $06`, `getdrivesize $08` |
| Verzeichnis | `getcwd $0A`, `chdir $0C`, `mkdir $0E`*, `rmdir $10`*, `cdrootdir $3C`, `opendir $12`, `readdir $14`, `closedir $16` |
| Dateien | `openfile $18`, `readfile $1A`, `writefile $1C`, `mkfile $1E`, `closefile $20`, `closeall $22`, `seekfile $24`, `rmfile $26`, `fstat $28`, `rename $2A`, `filedate $2C`, `setname $2E` |
| Suche/Laden | `findfirst $30`, `findnext $32`, `findfile $34`, `loadfile $36`, `setup_transfer_area $3A`, `loadfile_attic $3E` (lädt bis 16 MB direkt ins Attic-RAM!) |
| D81-Mounts | `d81attach0 $40`, `d81detach $42`, `d81write_en $44`, `d81attach1 $46`, `attach $4A` |
| Tasks/System | `create_task_* $62/$66/$68`, `switch_to_task $6C`, `sendmessage $52` …, `toggle_rom_writeprotect $70`, `toggle_force_4502 $72`, `get/set_mapping $74/$76`, `serial_monitor_write $7C`, `reset $7E`; ROM-Schutz auch via `$D641` A=`$00/$02` |

*teilweise als „not implemented“ markiert — vor Nutzung im Appendix prüfen.

- `readfile` liefert sektorweise in den SD-Puffer `$FFD6E00` (per DMA oder
  Mapping abholen); `loadfile` lädt ganze Dateien an eine 28-Bit-Adresse.
- **Projektbefund als Einordnung:** Im Etherload-Kontext war HYPPO-DOS auf
  echter HW tot (`dos_disk_count==0`, `selectdrive → $80 no_such_disk`) —
  vermutlich weil der Boot-Weg den DOS-Zustand nicht initialisiert hinterlässt.
  Wer HYPPO-DOS will (z. B. `d81attach` für Library-Disk-Wechsel oder
  FAT-Zugriff für FASLs), muss zuerst diese Kontextfrage klären; das ist der
  einzelne größte „unbekannte Schalter“ zwischen lisp65 und einem ganzen
  Feature-Feld (Mounts, FAT-Dateien, Attic-Loads).

---

## 8. Attic-/HyperRAM — reale Zahlen

- Anbindung über den „Slow devices“-Bus; ohne Controller-Pufferung liegt die
  Zugriffslatenz bei ~300 ns — „etwa was ein C64 von 1982 mit seinen DRAMs
  hatte“ (Originalzitat des Core-Entwicklers, verbatim bestätigt). Deshalb
  sind Write-Buffer/Prefetch im Controller essenziell.
- Durchsätze per DMA (Entwickler-Benchmark Mai 2020, damaliger Core-Stand —
  als Größenordnung lesen, nicht als aktueller Pin): Fill → Slow-RAM
  9,3 MB/s; Chip→Slow 4,3 MB/s; Slow→Chip 2,5 MB/s; Slow→Slow 1,5 MB/s.
  Eigene Nachmessung ist als Idee B.7 vorgesehen.
- Konsequenz für lisp65 (deckt sich mit dem Audit): Attic ist Cold-Store für
  Blobs/Assets/Compiler-Artefakte — per DMA blockweise, nie als Hot-Heap und
  nie für Code-Ausführung. Nicht VIC-/Audio-DMA-sichtbar.
- Errata-Historie (bestätigt): bis Nov. 2023 duplizierte ein HyperRAM-Lesebug
  sequenzielle Bytes (Paare lasen denselben Wert, der korrekte kam eine
  Transaktion später); Root Cause war ein Clock-Domain-Crossing-Fehler
  zwischen HyperRAM-Controller (162 MHz) und Slow-Devices-Modul (81 MHz).
  Debug-Register `$BFFFFF0–5` antworten ohne Chip-Latenz (Controller- vs.
  Chip-Fehler unterscheidbar) *(unverifiziert)*. Auf Core ≥ 0.97 irrelevant,
  aber bei fremden/alten Geräten wissenswert.

## 9. Core-Versionen und Boards

- 0.96 (publiziert Sep. 2024, Batch-3/R6): **nicht in Slot 0 von
  DEVKIT/älteren Boards oder Nexys flashen** (bricht den Flasher; bestätigt,
  Original-WARNING in den Release-Notes). 0.97.0 (Mai 2025,
  „10th Anniversary“): breiteste Basis — Pakete für R6, R3/R3A, R2 und
  Nexys4DDR (bestätigt).
- 0.97.1/0.97.2 (Sep. 2025) — **Korrektur gegenüber den Release-Notes**: die
  Notes nennen 0.97.2 einen reinen R6A-Kompatibilitätspatch, aber das
  Changelog weist ihn als „M65TARGET bugfix for R6“ aus (Issue #920:
  `M65MODEL` lieferte falsche Werte; 0.97.1 war der verunglückte erste
  Fixversuch — „should not be used“). Praktisch relevant: Wer `$D629`
  M65MODEL ausliest (siehe Idee A.4), braucht auf R6-Boards ≥ 0.97.2 für
  verlässliche Werte.
- Praxisregel fürs Projekt: Feature-Verfügbarkeit (RRB-Details, SD-Verhalten,
  Flat-Access!) ist core-versionsabhängig — HW-Gates dokumentieren idealerweise
  die Core-Version mit (passt zu AP2-Provenienz: Toolversionen ins Manifest).

## 10. Xemu vs. echte Hardware (Fidelity-Karte)

- Xemu zielt nur auf Scanline-Genauigkeit; CPU-Zyklen/Opcode können abweichen;
  HyperRAM-Timing nicht moduliert. DMA-Jobs sind in xemu 15–20 ms statt µs
  (Projektmessung) — Timing-/Durchsatzaussagen nie aus xemu ableiten.
- F011 defekt; SD-Puffer liegt bei `$DE00` statt `$FFD6E00`; D81-Mount ist ein
  virtueller Pool; HDOS-Traps werden geloggt (nützlich!); Freezer funktioniert
  nicht; Flat-/MAP-Divergenzen dokumentiert.
- RRB-Emulationshistorie (bestätigt): Xemus ursprüngliche RRB-Implementierung
  war laut Autor „mostly a kind of hack“, damit MEGAMAZE lief; RRB-Y-Positioning
  fehlte bis Mitte 2021 komplett, GOTOX rechnete in H320 falsch. Auch aktuell
  gilt: RRB-/SEAM-Features ausschließlich auf echter HW abnehmen.
- `$D60F` Bit 5 REALHW unterscheidet Gerät von Xemu zur Laufzeit — sauberer
  als Heuristiken, für Test-Weichen geeignet.
- Projektregel bleibt richtig: xemu = Vorfilter, echte HW = Arbiter.

## 11. Sonstige Peripherie mit Ausnutzungspotenzial

- **Hardware-Tastatur-Queue `$D610`** (ASCII, Write=Pop; `$D619` PETSCII;
  Modifier `$D60A/$D611`): ereignisbasierte Eingabe inkl. Modifier — könnte
  Matrix-/KERNAL-Reste im REPL/Editor ersetzen und macht Control-Chords
  robust testbar (virtuelle Tastendrücke `$D615–17` als Injektionskanal für
  HW-Smokes, wo JTAG-Typing heute Zeichen verliert).
- **45E100 Ethernet**: 100 Mbit, 4×2-KB-RX-Ringpuffer, CRC in HW, IRQ-fähig;
  Frame-Puffer DMA-tauglich. etherload erreicht ~2 MB/s. Realistisch für
  lisp65: Raw-Frame-Protokoll (Remote-REPL, FASL-Push, Telemetrie) — kein
  IP-Stack nötig; `mega65-weeip` existiert als Referenz.
- **4541 IEC-Offload**: serieller IEC-Bus in Hardware inkl. JiffyDOS-Timing
  (~10×) — nur relevant, falls je externe Laufwerke unterstützt werden sollen.
- **RTC + 64 B NVRAM** (`$FFD7140`): persistente Konfiguration (z. B.
  Workbench-Settings) ohne Disk-Write; UUID64 als Geräte-ID.
- **Digi-DACs `$D6F8–FB`** und Crossbar-Mixer (128×16-Bit-Koeffizienten):
  prozedurales Audio ohne Audio-DMA; 32 Takte Wartezeit zwischen
  Koeffizient-Writes.
- **µs-Timer**: BASIC exponiert `TI`/`SLEEP` mikrosekundengenau — ein
  µs-Zeitgeber-Prim wäre auch für Benchmarks/Smokes nützlich (Registerquelle
  im Buch/iomap nachschlagen, CIA-unabhängig).

---

## 12. Was lisp65 heute schon nutzt / bewusst verworfen hat

Vollständige Matrix in `docs/mega65-hardware-opportunity-audit.md` und den
HW-Dokumenten; Kurzfassung zur Einordnung der Ideen:

- **Produktiv:** 40 MHz (`$D054`), F018-DMA als einziger EXT-Pfad (mit
  `"memory"`-Clobber-Härtung), Bank-4/5-EXT-Layout (Heap-Overflow, String-Arena,
  Disk-Scratch, Stdlib-Blob, EXT-Symboltabellen inkl. `symfn`), F011-Treiber
  (Read/RMW-Write/Verify, `$DE00`-Mapping), eigener VIC-IV-Screen-Treiber,
  RUN/STOP-Poll, Etherload-/JTAG-/xemu-Harnesse.
- **Verworfen (Gründe dokumentiert):** CRAM2K, Flat-Access für EXT/Colour,
  KERNAL-I/O und -Scroll, roher SD-Zugriff neben gemountetem D81, EDMA-Scroll
  als Default (+439 B), Symfn-Cache (PRG-Ende), Markstack-GC (HW-Freeze),
  `m65 -F` im Normalworkflow, JTAG-Typing für Chords.
- **Bekannte offene HW-Fragen:** `every`/`some`-Hänger, F011-Puffer-DMA
  ungetestet, Farb-RAM ab Zeile 13, HYPPO-Kontext, Laufwerk 9,
  einmaliger `gc_badobj=4`-Readback.

---

## 13. Konkrete Ideen — priorisiert und gegen den Sanierungsplan gestellt

Sortierung: Erst was der Sanierung (AP1–AP7) direkt hilft, dann AP8-Features.
Alles Folgende respektiert den Feature-Freeze: Kategorie A sind
Sanierungs-Hebel, B sind Messungen/Spikes ohne Produktänderung, C ist
Post-G6-Roadmap-Material.

### A. Sanierungsdienlich (AP4 „Echte Speicherreserve“)

1. **HW-Math statt llvm-mos-Softmult/-div im Kern (Bank-0-Reclaim).**
   llvm-mos linkt für 16-Bit-Multiplikation/Division Bibliotheksroutinen ins
   PRG. Ein kleines Prim-Paar über MULTINA/B / DIVOUT könnte diese Libcalls
   ersetzen — Doppelnutzen: schneller **und** PRG-Ende-Gewinn.

   **Messergebnis 2026-07-10** (`llvm-nm --print-size` auf dem aktuellen
   `lisp65-mega65-vm-stdlib-einsuite-core-workbench.prg.elf`):

   | Routine | Bytes | Aufrufer im PRG |
   | --- | ---: | --- |
   | `__udivmodhi4` | 216 | `apply`, `print_obj` |
   | `__udivhi3` | 189 | `repl`, `__divhi3` |
   | `__umodhi3` | 166 | `__modhi3` |
   | `__divhi3` | 115 | `vm_fixbinop` |
   | `__modhi3` | 104 | `apply`, `vm_fixbinop` |
   | `__mulhi3` | 50 | `vm_fixbinop`, `vm_callprim`, `repl`×2, `scr_putc`×2, `scr_cursor`, `fill_row` |
   | Summe | **840** | 14 statische Callsites |

   Realistischer Zuschnitt: Die drei **unsigned Divisionsroutinen (571 B)**
   durch einen einzigen HW-Divider-Helper ersetzen (4 Byte-Stores → DIVBUSY-
   Poll → 4 Byte-Loads, geschätzt ~70–100 B) und `__mulhi3` durch einen
   MULTINA/B-Helper (~50 B, netto ±0, aber deutlich schneller). Die signed
   Wrapper (219 B) bleiben und rufen den Helper. **Erwarteter Netto-Reclaim
   ~450–520 B Bank 0** — grob die Hälfte des EDMA-Scroll-Defizits — plus
   Latenzgewinn genau in den Hotpaths (`vm_fixbinop` = Lisp-`* / mod`,
   `print_obj` = Ziffernausgabe, `scr_putc` = Zeilenadressierung y×80).
   Sauberster Einbau ohne Callsite-Änderung: eigene starke Symbole
   `__udivmodhi4`/`__udivhi3`/`__umodhi3`/`__mulhi3` definieren, dann zieht
   der Linker die compiler-rt-Versionen gar nicht erst. Voraussetzungen:
   MEGA65-I/O gemappt (im Produkt immer der Fall), keine IRQ-Konkurrenz um
   die Math-Register (Produkt hat keinen eigenen IRQ-Handler), xemu-Verhalten
   der Math-Unit gegenprüfen, HW-Gate über `hw-access-smoke` hinaus
   (`math_mul`/`math_div` sind dort bereits grün).
2. **Inline-DMA (`$D707`) als kleinere DMA-Naht.** Die heutige
   Trigger-Sequenz + statische Liste in `ext_dma`/`vm_dma` ist bewährt, aber
   nicht minimal. Inline-DMA legt die Liste in den Instruktionsstrom — weniger
   Bytes und keine Adressregister-Sequenz. Riskant wegen llvm-mos-Codegen →
   als isolierter Spike mit `hw-access-smoke`-Erweiterung, erst nach AP1/AP2.
3. **ROM-Banks 2/3 als RAM (+128 KB)** via `toggle_rom_writeprotect` steht
   schon als P2 im Audit; das HYPPO-Trap-ABI dafür ist jetzt vollständig
   dokumentiert (Aufrufkonvention inkl. `CLV`-Regel, `$D641`-Variante). Falls
   AP4-Reclaim unter Ziel bleibt, ist das der größte Einzelhebel jenseits von
   Boot-Reclaim — braucht aber das MAP-/IRQ-Konzept und bleibt deshalb hinter
   Boot-Reclaim priorisiert.
4. **Core-Version ins Ship-/Gate-Manifest aufnehmen** (AP2-Synergie): HW-Gates
   protokollieren künftig `$D629` M65MODEL + Core-Release; kostet Minuten,
   macht HW-Ergebnisse über Core-Updates hinweg vergleichbar.

### B. Messungen/Spikes ohne Produktrisiko (parallel möglich)

5. **`f011-buffer-dma-hw` endlich ausführen** (definiertes P1-Gate): Sektor
   per DMA aus `$FFD6C00/$FFD6E00` nach Bank 4 statt byteweisem `$DE00`-Loop.
   Wenn grün: Loader-/`load-lib`-Latenz sinkt spürbar (512 B in ~25 µs statt
   Byte-Loop), und der Persistenzpfad (AP6) bekommt Luft.
6. **Tastatur-Queue-Spike (`$D610`)**: Mini-PRG, das Queue + Modifier + 
   virtuelle Tasten (`$D615–17`) auf echter HW verifiziert. Wenn tragfähig:
   (a) Editor-Input-Pfad vereinfachen, (b) HW-UX-Smokes können Chords
   injizieren statt JTAG-Typing-Grenzen zu umschiffen.
7. **Attic-Durchsatz nachmessen** (eigene Zahlen statt Blog-Werte): kleines
   Smoke-PRG mit DMA-Blocktransfers Chip↔Attic inkl. JTAG-Counter-Readback —
   validiert die Cold-Store-Strategie und liefert Planungszahlen für
   FASL-Caching.
8. **HYPPO-Kontextfrage klären**: Warum ist `dos_disk_count==0` nach
   Etherload-Boot? Test: normaler SD-Boot (ohne Etherload) + Trap-Probe;
   danach Etherload-Boot + `d81attach0`-Probe. Das Ergebnis entscheidet über
   ein ganzes Feature-Feld (Idee 10/11).

### C. Post-Sanierung (AP8-Kandidaten, nach G6)

9. **Editor-Rendering v2: SCRNPTR-Fenster statt Kopier-Scroll.** Screen-RAM
   irgendwo in 384 KB + LINESTEP/DISPROWS/TEXTYPOS = das Anzeige-Fenster fährt
   über den Puffer; Scrollen wird ein Registerwrite. Löst das
   EDMA-Scroll-Footprint-Dilemma strukturell (kein Kopiercode mehr statt
   billigerem Kopiercode). Voraussetzungen: HOTREG-Disziplin, Colour-Strategie
   (COLPTR wandert mit), Interaktion mit dem 1000-B-Legacy-Screen klären.
10. **Library-Disk-Wechsel per `d81attach`** („MOUNT für lisp65“): Sessions
    könnten zwischen Library-/Projekt-D81s umschalten ohne Freezer — hängt an
    Idee 8; API-seitig trivial (`(disk-attach "LIBS.D81")`).
11. **FASL-/Asset-Pipeline über HYPPO-FAT**: `setname`+`findfile`+`loadfile`
    bzw. `loadfile_attic` laden Dateien direkt von der SD-FAT (bis 16 MB, auch
    ins Attic) — würde Blob-Preload per Etherload auf dem Gerät ersetzen
    (Standalone-Boot ohne PC!). Gleiches HYPPO-Vorbehalts-Gate.
12. **Sound-Library über Audio-DMA** (BASIC-Parität `m65-sound`+): 4 Kanäle
    ohne CPU-Last, Loop-Musik + SID-Effekte parallel; Nibble-Samples für
    RAM-Ökonomie. Der im Paritätsplan offene „Tick-Hook“ wird nur für
    Sequencer nötig — reine Sample-Playback-API braucht keinen IRQ.
13. **IDE-Overlays per RRB** (Autocomplete-Popup, Fehler-Marker, Statuszeile
    als eigener Layer) statt Redraw-Logik; SEAM/FCOLMCM gibt nebenbei
    256-Farb-Syntax-Highlighting und Alpha-FCM proportionale Fonts.
14. **Remote-REPL über Ethernet-Raw-Frames**: Entwicklungs-Turbolader
    (Eval-over-LAN, FASL-Push, Telemetrie-Stream) mit 2-KB-Puffern und DMA;
    Xemu kann Ethernet teilweise emulieren, HW-Gate trotzdem Pflicht.
15. **Kleinvieh mit gutem Verhältnis**: `TI`-µs-Timer-Prim (Benchmarks),
    NVRAM-Settings (64 B reichen für Workbench-Prefs), Undelete
    (`SCRATCH ,R`-Parität im Directory), `REALHW`-Weiche in Smokes,
    LOADIFF-Import als Asset-Weg in die Grafik-Libs.

### Ausdrücklich nicht empfohlen (bestätigt Projektlinie)

- Flat-Access als genereller `peek28/poke28` (HW-rot), CRAM2K-Farbfix,
  MAP-Banking als schneller Budgetfix, Raw-Flux-DMA für D81-Workflows,
  xemu-basierte Freigaben von HW-Verhalten, VSP-/Mid-Line-Tricks (VIC-IV
  ändert Modi nur am Zeilenanfang — und macht sie überflüssig).

---

## 14. Fallstricken-Katalog (Kurzreferenz)

1. Vor `$D6xx/$D7xx`-Nutzung: Knock `$47,$53` auf `$D02F`.
2. HOTREG an + Write auf `$D011/$D016/$D018/$D031/$DD00` ⇒ VIC-IV-Setup weg.
3. FCM ignoriert CHARPTR (Adresse = 64 × Charnummer).
4. Palette nibble-reversed; Bankwechsel wirkt sofort.
5. DMA blockiert die CPU; `$D702`-Write löscht `$D704`; Swap/Mix im Core nicht
   implementiert.
6. Audio-DMA: Samples nur Chip-RAM, 64-KB-Top-Vergleich, enge Loops brauchen
   einen Memory-Read.
7. SD-Write ohne vorheriges Write-Gate (`$57`, ~1 ms) schlägt fehl; Busy-Flag
   bleibt bei Read-Ahead gesetzt; Karten ≤ 2 GB unbrauchbar.
8. HYPPO: `CLV` nach dem Trap-`STA`; `setname` page-aligned < `$7E00`;
   Carry = Erfolg; im Etherload-Kontext DOS-Zustand ungeklärt.
9. CRAM2K verdeckt die CIAs; Farb-Offsets ≥ 1024 treffen I/O (`$DD00`!).
10. llvm-mos: DMA-Trigger brauchen `"memory"`-Clobber; Q-Register-Asm muss
    Z=0 restaurieren; variabler Shift `1u<<(i&7)` war ein Codegen-Bug.
11. UART-/FDC-IRQs nicht implementiert (Polling); eigener IRQ-Handler existiert
    im Produkt bisher nicht.
12. xemu: DMA ms-langsam, F011 defekt, Freezer fehlt, Flat/MAP divergiert —
    nie als Freigabeinstanz.
13. Attic: ~300 ns Einzelzugriffslatenz — nur Block-DMA, nie Hot-Path.
14. Core-Flashing: 0.96+ nicht in Slot 0 alter Boards (Flasher-Bruch).

---

## 15. Nachschlagewerk-Wegweiser

- 45GS02-Instruktionen/Adressmodi/Zyklen: MEGA65-Buch Appendix K (Architektur,
  Flat-Access K-11 ff., Q-Register K-12 ff., Speed K-5) und L (Opcode-Matrix,
  Cycle-Counts).
- VIC-IV-Register komplett: Chipset-Referenz Kap. VIC-IV; DMAgic ebd. + Buch
  Appendix P; Mathe-Einheit Buch Appendix K („CPU Maths Acceleration“).
- HYPPO: `mega65-user-guide`-Repo `appendix-hypervisor-calls.tex` (lokal
  gespiegelt im Session-Scratchpad, bei Bedarf neu ziehen).
- iomap.txt im mega65-core-Repo als Registerwahrheit zwischen den Handbüchern.
- Community-Techniken: c65gs.blogspot.com (DMAgic-Interface 2018,
  HyperRAM-Timing 2020, HyperRAM-Bugfix 2023), retrocogs.mega65.com (RRB),
  Xemu-Wiki „M65 project status“ (Fidelity-Liste).
