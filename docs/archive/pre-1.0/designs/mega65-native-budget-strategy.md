# MEGA65-native Budget-Strategie

Stand: 2026-07-08. Diese Strategie konkretisiert die Frage, wie lisp65
MEGA65-Hardware nutzt, ohne wieder in ein C64-artiges 64-KB-Denken
zurueckzufallen. Sie ist kein neuer MVP-Task, sondern ein Entscheidungsrahmen
fuer Bank-0-, IDE-, Compiler- und Library-Arbeit.

## Nordstern

Bank 0 ist nicht der Ort fuer das wachsende Lisp-System. Bank 0 ist der kleine,
heisse Maschinenraum:

- VM/GC/Objektmodell
- Reader/Printer-Minimum
- wenige stabile Hardware-Primitive
- Boot-/Load-Naehte
- REPL-/Fehlerpfad

Alles, was Sprache, IDE, Compiler-Frontend, Libraries oder Nutzerprogramme ist,
soll als Bytecode/FASL in EXT-RAM oder auf Disk wachsen. Ein groesseres Feature
ist erst dann ein Kernel-Feature, wenn es mit Lisp/Bytecode nicht korrekt oder
nicht budgetierbar ausdrueckbar ist.

## Aktueller MEGA65-Stand

Bereits genutzt:

- EXT-RAM fuer Bytecode-Image, Code-Region, Namepool/Symval/Nameoff und EXT-Heap.
- F018-DMA fuer EXT-Zugriffe und Blob-/Codebewegung.
- F011-Disk-I/O fuer `load`, `save`, `load-lib` und FASL/D81-Workflows.
- Etherload + JTAG/HW-Harness fuer echte Hardwaretests, Screenshots und Counter.
- 80x25-Screen + native Bulk-Ausgabe fuer IDE-/REPL-Rendering.
- Selbstgehosteter lcc als Bytecode-Compiler statt residentem C-Compiler.

Noch nicht voll ausgeschoepft:

- Boot-Code-Reclaim: Boot-/Embed-Materialisierung bleibt nach dem Start resident.
- Runtime-Core ohne IDE/lcc/FASL-Emitter fuer fertige Programme.
- MAP/banked-code-Strategien fuer groessere C-Module.
- Direkter 28-bit-Hardwarezugriff, z. B. Color-RAM ohne CRAM2K-Fenster.
- MEGA65-Grafik/Sound/Sprite-Libraries als on-demand Bundles.

Ein vertiefter Referenz- und Web-Audit dazu steht in
`docs/mega65-hardware-opportunity-audit.md`.

## Budget-Wahrheit

Der Treewalk-Strip hat real ca. 6.4 KB Bank-0-Reserve freigemacht. Diese Reserve
ist nicht verschwunden, sondern wurde bewusst reinvestiert:

- Disk-`load`/`save` und F011-Pfade
- FASL/Legacy-`compile-file-to-lib` und `lcc-install`
- Bulk-Render und Screen-Prims
- groessere Symbol-/Directory-/GC-Roots-Caps
- IDE-/Compiler-Workflow im Ein-Produkt

Das ist ein guter Tausch, aber es laesst uns wieder am Rand arbeiten. Deshalb
gilt ab jetzt: jeder neue Bank-0-Verbrauch braucht einen klaren Lebenszeit- und
Profilvertrag. "Passt gerade so" ist kein Produktkriterium.

### Nachzug 2026-07-08: Workbench-Caps sind nur eine MVP-Bruecke

Der `compile-string`-/`compile-buffer`-Slow-Path ist der richtige kurzfristige
Hebel, weil er den teuren nativen Disk-Source-FASL-Pfad aus Bank 0 haelt. Die
aktuelle Messung zeigt aber, dass selbst dieser kleinere Pfad nur durch
produktbezogenes Cap-Tuning gruen wird:

- Baseline mit `LISP65_COMPILE_STRING` und grossen Caps war Bank-0-rot.
- Aktueller Workbench-Pin: `LISP65_SYMFN_EXT`, `NAMEPOOL=9536`,
  `MAX_SYM=720`, `SYMPOOL_EXT_OFF=0xc9e0`, `VM_DIR_MAX=552`,
  `GC_ROOTS=128`, `REPL_BUF_MAX=192`, `STR_ARENA_SIZE=0x2480`,
  `DISK_EXT_BASE=0x6900`, `DISK_EXT_FILE_MAX=0x9600`.
- Gemessen damit: `prg_file_end=0xc0bc`, `stack_gap=1610`,
  `bank0_reserve=160`; der Pin deckt IDE-On-Demand, Save/Reload eines
  gepaddeten Slots, ein neues Source-File via `tmp`-Reserve und
  anschliessenden Demo-FASL-Load in einer Session.
  Die Mini-REPL-History ist wieder aktiv, passt aber nur als
  `LISP65_REPL_HISTORY_IN_BUF`-Sparpfad und verbraucht fast die komplette
  PRG-Ende-Reserve. Der groessere REPL-Buffer ist ein reiner BSS-Tradeoff.

Der HW-Compile-Roundtrip ist inzwischen gruen: mehrformige Quelle via
`compile-string` in einen vorallokierten Slot, danach `load-lib` und Ausfuehrung
der geladenen Funktion mit `gc_badobj=0`/`mem_oom=0`; der erweiterte Test mit
`(edit)` und IDE-Tipp-Smoke ist ebenfalls gruen. Das ist fuer das MVP
akzeptabel, aber kein dauerhaft gesunder Wachstumszustand. `LISP65_SYMFN_EXT`
kauft einen reproduzierbaren Produktpin, keine vollstaendige Bank-0-Architektur-
Sanierung. Weitere Featurearbeit darf nicht daraus bestehen, `MAX_SYM`,
`VM_DIR_MAX`, `GC_ROOTS`, Stack-Gap-Ziele oder Hotpath-DMA immer weiter
auszureizen.

Konsequenz: Nach dem gruenen Workbench-Compile-Gate bleibt Bank-0-Reclaim ein
mittelfristiger Pflichtpfad. Besonders relevant sind Boot-only-Code, BSS-Caps
mit echter Produktmathematik, Clone-/Accessor-Cluster und ein klarer
Runtime-Core ohne IDE/lcc/FASL-Emitter.

## Primaerer Reclaim-Kandidat

Der groesste wahrscheinlich vermeidbare Bank-0-Block ist nicht mehr der
Treewalk, sondern Boot-/Embed-Code, der nur einmal laeuft:

- `vm_load_embedded_stdlib`
- `md_lit_node`
- `vm_register_embedded`
- `vm_lit_keep`
- Teile der Boot-Registrierung um `eval_init`

Groessenordnung im aktuellen Core: ca. 3 KB bis 4 KB, je nach Profil. Dieser
Code liegt nach dem Boot resident tot. Ein sauberer Reclaim ist trotzdem kein
Nebenbei-Fix, weil Code/Heap-Overlap, BSS-Zeroing, Etherload-Grenzen und
Accessoren betroffen sind.

Strategie:

1. Erst einen `bank0-lifetime-report` bauen: Symbolgroessen per `llvm-nm` in
   `runtime-hot`, `runtime-cold`, `boot-only`, `dev-only` und `bss-cap`
   klassifizieren.
2. Dann einen Boot-Code-Reclaim-Spike isoliert bauen. Ziel: mindestens 1.5 KB
   sichere Reserve; Stretch: 3 KB.
3. Erst nach HW-Boot und `make check`/Dry-Run-Gates wird daraus ein Produktpfad.

## Profilstrategie

### Dev-Core

Ziel: interaktive Entwicklung.

Resident:

- REPL
- lcc
- `load`/`save`/`load-lib`
- FASL/Legacy-`compile-file-to-lib`
- kleine CL-nahe Basis

On demand:

- IDE
- Format/Strings-extra/Fixed/Places/Collections
- Projektlibs

Budgetziel: nach Boot genug Reserve fuer IDE-Lib + realistische User-Session,
nicht nur fuer den leeren Prompt.

### Full/MVP

Ziel: Komfortprodukt und Regressionstraeger.

Resident darf mehr sein als im Dev-Core, aber Full ist nicht die langfristige
Antwort fuer "alle Features immer gleichzeitig". Full bleibt nuetzlich, solange
wir schnelle Alltagstests und HW-Smokes brauchen.

### Runtime-Core

Ziel: fertige Programme.

Resident:

- VM/GC
- Loader
- minimale Runtime-Libs
- Entry-Point-Launcher

Nicht resident:

- IDE
- lcc
- FASL-Emitter
- breite Entwicklungs-/Introspektionslibs

Dieses Profil ist der Weg zu "genug Budget fuer echte Programme". Wer nur ein
fertiges Spiel/Tool startet, soll nicht den Editor und Compiler mitbezahlen.

## C-vs-Lisp-Regeln

Neue Funktionalitaet kommt zuerst als Lisp/Bytecode, ausser eine der folgenden
Bedingungen ist erfuellt:

1. Sie braucht echten Hardwarezugriff: DMA, F011, Screen/Farb-RAM, IRQ, Timer,
   Sound, Sprites, 28-bit Speicherzugriff.
2. Sie ersetzt nach Messung mehr Bank-0- oder C-Stack-Kosten, als sie selbst
   kostet.
3. Sie ist ein Stabilitaetsprimitive: Fehlerpfad, GC, VM, Loader-Kern.

Ein neuer C-Prim braucht vor dem Merge:

- Footprint-Delta in Bytes.
- Stack-Gap-Delta.
- Aussage, welches Lisp/Bytecode-Stueck er ersetzt.
- Host-Gate und, bei Hardwarepfad, HW- oder Dry-Run-Rezept.

`screen-scroll` ist die Warnung: eine richtige Idee kann trotzdem ein schlechter
Bank-0-Deal sein, wenn sie weder gate-neutral ist noch die echte Ursache
beseitigt.

Nachzug 2026-07-08: EDMA-Screen/Color-Scroll ist auf echter HW gruen
(`hw-edma-screen-smoke` 7/7), aber die produktnahe C-Naht
`LISP65_SCREEN_EDMA_SCROLL` ist im Dev-Core footprint-rot: +439 B Text, +14 BSS,
Stack-Gap 1466 -> 1012 B. Das bestaetigt die Regel: Hardwarefaehigkeit allein
reicht nicht; der Default-Core braucht vorher Reclaim oder eine kleinere
Assembly-Naht.

## MEGA65-Hardware-Regeln

### EXT-RAM

EXT-RAM ist Standard fuer wachsende Daten und Code. Bank 0 bleibt Cache und
Arbeitsbereich. Direktes C-Zeigerdenken gilt nicht: die verifizierte portable
Naht ist F018-DMA bzw. gezielte Accessoren.

### DMA

DMA ist fuer Bulk gut, fuer sehr kleine Operationen nicht automatisch. Jede neue
DMA-Nutzung wird gegen CPU-Kopie bzw. existierende Primitive gemessen. Setup-Code
kann groesser sein als die Operation.

### Color RAM / Screen

Kein CRAM2K als schneller Fix, solange es Disk-/DMA-Pfade stoert. Fuer echten
Farbfix bevorzugt: direkter MEGA65-Adressraum/28-bit-Pfad zu Color-RAM oder ein
kleiner, isolierter Hardware-Accessor mit HW-Test.

Nachzug 2026-07-08: Der direkte Flat-Store nach `$FF80000` ist auf echter HW rot;
fuer Color RAM bleibt damit EDMA der belastbare 28-bit-Pfad. Vollfarbe fuer
IDE-Zeilen >=13 ist aber kein MVP-Blocker: der Clamp-Pfad ist stabil und
verhindert I/O-Escapes. Der gemessene fill-only EDMA-Ansatz fuer
Uniform-Zeilenfarbe in `scr_write_span` ist fuer den Core-IDE keine
Produktoption: Im Core ist `scr_write_span` dead-stripped, im Full-Profil reisst
die Integration das Stack-Gap. Ship-Default bleibt deshalb B-drop. Per-Char-
EDMA im normalen Highlighter-Hotpath bleibt ausgeschlossen. Ein Bulk-in-Core-
Spike darf erst zusammen mit OOM-/Render-Performance gemessen werden.

### MAP / banked code

MAP/banked-code ist ein Post-MVP-R&D-Pfad, kein schneller Budgetfix. Ziel waere,
kalte C-Module oder Boot-Code aus Bank 0 herauszuziehen. Vorher muessen
Assembler-Veneers, Call-Konvention, Interrupt-/DMA-Vertraeglichkeit und
llvm-mos-Linking geklaert sein.

### Grafik/Sound/Sprites

MEGA65-BASIC-65-Paritaet kommt als on-demand Library-Familie:

- `m65-hw`: Low-Level-Register/Memory/Timer
- `m65-gfx`/`m65-draw`
- `m65-sprite`
- `m65-sound`
- `m65-input`
- `m65-disk`
- optional `basic65` als Facade

Nur die minimalen Hardware-Naehte gehen in den Kernel; die API-Oberflaeche liegt
in Lisp-Libs.

## Mess- und Gate-Strategie

Neue Budgetentscheidungen muessen die folgenden Zahlen nennen:

- `prg_bytes`
- `prg_file_end`
- `.text + .rodata`
- `.bss`
- `stack_gap`
- `bank0_reserve`
- `boot_required_symbols`
- `entries`
- EXT-Image-Ende und Kollision mit Symbolpool/Code-Region
- fuer Hotpaths: statische CALL-Kanten oder gemessene SP-Wassermarke

Zusaetzliche gewuenschte Reports:

1. `bank0-reclaim-report`: sortiert `llvm-nm`-Symbole nach Groesse,
   Clone-Clustern und BSS-Hebeln. Das ist die vorbereitende Stufe fuer einen
   spaeteren `bank0-lifetime-report` nach Lebenszeit und Featuregruppe.
2. `profile-delta-report`: vergleicht Full, Dev-Core und Runtime-Core nach
   gleichen Metriken.
3. `hotpath-depth-report`: fuer IDE/Compiler/Loader die normale CALL-Kette und
   gemessene SP-Wassermarke.

Nachzug 2026-07-08: `make bank0-reclaim-report` schreibt
`build/bytecode/bank0-reclaim-report.txt`; der Befund liegt in
`docs/bank0-reclaim-candidates.md`. Aktueller Dev-Core: nur ~8-16 B Reserve,
fuer einen 300-B-Guard-Puffer fehlen grob 290 B, fuer den EDMA-/Screen-
Experimentpuffer grob 440 B.

Nachzug 2026-07-09: Der Workbench-Compile-String-/IDE-On-Demand-Kandidat
bestaetigt dieselbe Richtung. Mit `LISP65_SYMFN_EXT`, `NAMEPOOL=9536`,
`MAX_SYM=720`, `SYMPOOL_EXT_OFF=0xc9e0`, `VM_DIR_MAX=552`, `GC_ROOTS=128`,
`REPL_BUF_MAX=192`, `STR_ARENA_SIZE=0x2480`, `DISK_EXT_BASE=0x6900` und
`DISK_EXT_FILE_MAX=0x9600` wird er gruen (`bank0_reserve=160`). Diese Zahl ist ein Pin
fuer den MVP-Kandidaten, nicht der neue Normalpuffer. Fuer
nachhaltige Entwicklung bleibt das Reclaim-Ziel mindestens 300-500 B, besser
1.5 KB+ ueber Boot-Code-Reclaim.

## Priorisierte Schritte

1. **Kurzfristig: C-Wachstum einfrieren.** Keine neuen Kernel-Prims ohne
   Footprint-Delta und Gegenwert.
2. **Workbench-Compile-Gate pinnen.** `compile-string`/`compile-buffer`
   gruen bauen, HW-Roundtrip fahren und nur mit gruenem Footprint-Alias als
   Produktkandidat setzen.
3. **IDE-Scroll weiter messen.** SP-Wassermarke und non-tail Render-Kette
   flachlegen, bevor neue Screen-Prims entstehen.
4. **EDMA-Screen/Color nicht defaulten.** Der opt-in Pfad bleibt Mess- und
   R&D-Pfad, bis mindestens ~450 B Bank-0-Reclaim oder eine kleinere
   Assembly-Naht nachgewiesen sind. Kleinere EDMA-Farb-Fill-Helper muessen
   isoliert gemessen werden und duerfen nicht automatisch in den Core-Hotpath.
5. **Bank-0-Reclaim-Report nutzen, dann Lifetime-Report bauen.** Erst die
   groessten Symbole/Clone-Cluster/BSS-Hebel messen, danach boot-only/dev-only/
   runtime-hot sichtbar machen.
6. **Boot-Code-Reclaim-Spike.** Ziel: belastbare 1.5-3 KB Reserve.
7. **Runtime-Core definieren.** Ohne IDE/lcc/FASL-Emitter, fuer echte Programme.
8. **MEGA65-HW-Libs on demand.** Grafik/Sound/Sprite/API in Lisp, Kernel nur
   fuer minimale 28-bit/DMA/Register-Naehte.
9. **MAP/banked-code erst nach Reclaim/Runtime-Core.** Grosses R&D, kein
   Sofort-Fix.

## Entscheidungsformel

Ein Feature ist MEGA65-native und produktfaehig, wenn es:

1. Bank 0 als knappen Maschinenraum respektiert,
2. EXT-RAM/Disk als normalen Wachstumsort nutzt,
3. Hotpaths nach Tiefe und nicht nur nach Bytecodegroesse bewertet,
4. echte HW-Eigenschaften misst statt xemu- oder C64-Annahmen zu uebernehmen,
5. in mindestens ein klares Produktprofil passt.
