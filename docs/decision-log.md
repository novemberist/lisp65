# Decision Log

**Living append-only log.** New dated decisions continue to be appended here.
Historical entries deliberately retain their original language and path
strings; those paths are provenance, not promises that the old locations still
exist. Details and measurements live in the linked strategy, status, contract,
or archive documents. This file is not a frozen evidence archive and must not
be moved under `docs/archive/` while it remains the active decision chronology.

## 2026-07-08: Codex wird Projektlead

Codex uebernimmt Lead/Integration ueber alle Bereiche. Claude bleibt optionaler
Contributor/Reviewer, aber kein exklusiver Owner von `src/**`.

Quelle: `docs/project-lead-transition-plan.md`.

## 2026-07-08: Permanente Voll-Clones werden auslaufen

`../lisp65` ist der kanonische Integrations-Worktree. Neue Parallelaufgaben
laufen als kurzlebige `git worktree`s. `../lisp65-codex` und
`../lisp65-claude` wurden nach WIP-Audit archiviert unter
`../lisp65-archive/2026-07-08/`.

Quelle: `docs/project-lead-transition-plan.md`.

## 2026-07-08: Ein sichtbares Workbench-Produkt

Keine weiteren halb-funktionalen Nutzerprofile. Die Workbench ist das sichtbare
interaktive Produkt; Runtime bleibt spaeterer Export-/Deployment-Pfad fuer
fertige Programme, nicht zweites Alltagsprodukt.

Quelle: `docs/profile-consolidation-strategy.md`.

## 2026-07-08: Native Disk-Source-FASL-Schicht nicht im Workbench-Produkt

Die alte native `LISP65_FASL`-Disk-Source-Schicht kostet grob 1250 B Bank 0 und
sprengt den Arena-Workbench-Kandidaten. Workbench nutzt stattdessen den kleineren
`compile-string`-/`compile-buffer`-Slow-Path.

Quelle: `docs/profile-consolidation-strategy.md`,
`docs/mega65-native-budget-strategy.md`.

## 2026-07-08/09: Workbench-Caps als MVP-Bruecke akzeptiert

Der Workbench-Kandidat ist gruen mit `LISP65_SYMFN_EXT`, `NAMEPOOL=9536`,
`MAX_SYM=720`, `SYMPOOL_EXT_OFF=0xc9e0`, `VM_DIR_MAX=552`, `GC_ROOTS=128`,
`REPL_BUF_MAX=192`, `STR_ARENA_SIZE=0x2480`, `DISK_EXT_BASE=0x6900`,
`DISK_EXT_FILE_MAX=0x9600`.
Das ist akzeptiert fuer den MVP-Pin, aber keine dauerhafte Architekturreserve.
Der Pin entfernt den residenten RUN/STOP-IDE-Toggle; IDE-Start ist `(edit)`.
Die einstufige REPL-History ist wieder aktiv, aber nur als Workbench-Sparpfad
ohne separaten History-Puffer. Laengere einzeilige REPL-Eingaben sind wieder
moeglich; RETURN-bei-unbalancierten-Klammern bleibt bis zu weiterem
PRG-Ende-Reclaim offen.

Quelle: `docs/profile-consolidation-strategy.md`,
`docs/mega65-native-budget-strategy.md`.

## 2026-07-09: Workbench-Editor-Slice hebt `VM_DIR_MAX` auf 536

Dokumentnavigation (`C-v`/`C-z`, `C-x C-a`/`C-x C-e`), backward-kill-word
(`C-r`), einzeilige Mark/Region (`C-SPC`, `C-x C-x`, `C-x C-r`,
`C-x C-y`) und der `compile-file`-Source-Guard bleiben im einheitlichen
Workbench-Produkt. Dafuer steigt das Directory-Cap bewusst von
`VM_DIR_MAX=512` auf `VM_DIR_MAX=536`: Boot `319 -> align8=320`, ladbare
IDE-Lib `201`, `load_used=521`, `post_align=528`, Post-Align-Headroom `8`.
Kein neues Nutzerprofil wird eingefuehrt.

Quelle: `docs/workbench-gate.md`, `docs/project-status.md`.

## 2026-07-09: IDE-Disk-Lib braucht groesseres EXT-Code- und Symbolfenster

Der HW-Smoke zeigte zwei zusaetzliche Produktgrenzen: Die ladbare IDE-Lib passt
nicht mehr in das alte Bank-5-Codefenster vor `SYMPOOL_EXT_OFF=0xb000`, und
das alte Bank-4-Disk-Scratch-Dateifenster kappte die aktuelle `ide.ext.bin`.
Der Workbench-Pin verschiebt deshalb `SYMPOOL_EXT_OFF` aktuell auf `0xc9e0`,
nutzt `MAX_SYM=720`/`NAMEPOOL=9536` bis exakt zur Bank-5-Grenze und vergroessert
das gegatede Disk-Dateifenster auf `0x9600` ab Scratch `$46900` (String-Arena
je Halbfenster `0x2480`). Der
`workbench-disk-lib-budget-check` prueft seitdem auch den kombinierten
Stdlib+IDE-Lib-Symbol- und Namepool-Bedarf.

`make hw-workbench-ux-smoke` ist mit diesem Pin auf echter HW gruen. Der Harness
trennt den langen `(load-lib "ide")`-Core-Check von der folgenden
`function-kind`-Abfrage und nutzt fuer den Yank-Smoke lowercase-Testdaten, weil
das JTAG-Virtual-Keyboard uppercase-String-Inhalte in diesem Pfad unzuverlaessig
sendet.

## 2026-07-09: Save-New im Workbench-MVP nutzt `tmp`-Reserve statt BAM-Allokator

`save-buffer-to` kann im Workbench-MVP einen normalen neuen Source-Namen
anlegen, ohne den grossen M7-BAM-Allokator in die ladbare IDE-Lib zu ziehen:
Der Buffer-Inhalt wird in den versteckten vorallokierten Slot `tmp` geschrieben,
danach wird dessen Directory-Eintrag auf den Zielnamen umbenannt. Das passt in
das Produktbudget, kostet keinen Bank-0-C-Code und bleibt host-gated. Grenze:
Es ist genau ein Reserve-Slot im ausgelieferten D81, kein allgemeiner
Sektor-/BAM-Allocator.

Quelle: `lib/ide-disk.lisp`, `tests/bytecode/libs/p0-ide-lib.json`,
`docs/workbench-gate.md`.
sendet.

Quelle: `docs/workbench-gate.md`, `docs/project-status.md`.

## 2026-07-09: `eval-buffer` wird als schmale transiente API aufgenommen

Die ladbare IDE-Lib bekommt `(eval-buffer "name")`: Buffer-Source wird ueber die
bestehende `compile-string`-Reader-Naht gelesen und Form fuer Form via
`lcc-run` in die laufende Session kompiliert/installiert. Es entsteht kein
FASL-/L65M-Artefakt. Aus Budgetgruenden bleiben `eval-region` und Rueckgabe
des letzten Top-Level-Werts deferred. `M-x eval-buffer` ist nach dem
M-x-Registry-Reclaim als UI-Wrapper auf die aktuelle Buffer-Source gebunden.

Der erste Codefenster-Nachzug (`0xcb00`/`NAMEPOOL=9248`) war fuer die
gewachsene IDE-Lib zu knapp: Der Live-HW-Smoke lief bei `(load-lib "ide")` in
`too many symbols`, obwohl die Symbolslots rechnerisch nicht voll waren. Die
Root Cause war die kombinierte Namepool-Grenze. Der aktuelle Pin nutzt deshalb
`SYMPOOL_EXT_OFF=0xc9e0`, `NAMEPOOL=9536`, `MAX_SYM=720`;
`SYMPOOL_EXT_OFF+NAMEPOOL` bleibt `$ef20`. Der HW-Harness prueft
`M-x eval-buffer` in einer frischen zweiten Etherload-Session; der UI-Wrapper
ist auf echter MEGA65-HW mit `("evaluated" 42)` bestaetigt.

Quelle: `docs/ide-api-terminology.md`, `docs/workbench-gate.md`,
`docs/project-status.md`.

## 2026-07-09: Freies Speichern ist bis M6 als Lisp-Prototyp HW-gruen

Der D81-Write-Pfad wurde von read-only BAM-Sanity ueber BAM-Alloc, Ketten-Write
und Directory-Write bis zum Lisp-seitigen `save-new`-Prototyp auf echter
MEGA65-HW gepinnt. M6 laedt den Allocator als Source-Datei `m5alloc` von einer
Wegwerf-D81, reserviert im Vor-Image T45/S33, erzeugt `M6SRC` per BAM-Scan auf
T45/S34 -> S35, schreibt den Directory-Eintrag zuletzt und bestaetigt das
Ergebnis mit normalem Workbench-`(load "m6src")` plus `(m5-new-run) => 797`.

Das beweist den Daten->BAM->Directory-Loop in Lisp ueber `%disk-*`, ist aber
noch kein allgemeiner Produkt-`save-new`: globale Track-/Sektorwahl,
Directory-Kettennachwuchs, variable Kettenlaengen und Fehlerdisziplin bleiben
ein eigener Produktisierungsschritt.

Quelle: `docs/disk-save-slot-limit-vs-basic.md`, `docs/workbench-gate.md`,
`docs/reference/mega65-hardware-testing.md`.

## 2026-07-09: M7-`save-new` schreibt variable Ketten live auf HW

Der freie-Speichern-Prototyp hat nun einen separaten M7-Pfad:
`lib/m65-disk-alloc-var.lisp` stellt `(m65d-save-new name src)` bereit,
berechnet die benoetigte Anzahl 254-Byte-Datensektoren, scannt die BAM ueber
Tracks 1..80 ohne Track 40 und schreibt eine variable Sektorkette. Das
Host-Oracle `tools/host-lisp/d81_save_new_diff.py` berechnet denselben Plan
aus dem Vor-Image und prueft Datenkette, BAM-Counts/Bits und Directory-Eintrag
bitgenau. Der Live-Pin auf echter MEGA65-HW fuer die dreisektorige M7-Payload
ist `M7SRC` auf `T1/S0 -> T1/S1 -> T1/S2`, Directory T40/S4 Entry 2,
sichtbarer Marker `save new pass 5/5`, Workbench-`(load "m7src")` =>
`"m7-load-ok"` und `(m7-var-run) => 907`. Der M7-Harness braucht wegen des
groesseren Lisp-Allocators `--wait 45`; der 10s-Default war zu frueh.

M7 ersetzt M5/M6 absichtlich noch nicht: die alten Zweissektor-Smokes bleiben
Regressionen. Weiter offen fuer Produkt-`save-new` sind Directory-Ketten ueber
T40/S4 hinaus und harte Fehler-/Rollback-Disziplin.

Quelle: `docs/disk-save-slot-limit-vs-basic.md`, `docs/workbench-gate.md`,
`docs/reference/mega65-hardware-testing.md`.

## 2026-07-08: Workbench-Alias zeigt auf Arena-IDE + compile-string

`workbench-candidate` und `workbench-candidate-footprint-report` zeigen auf
`mvp-vm-stdlib-einsuite-core-workbench`. Claude hat den HW-Roundtrip bestaetigt:
`compile-string` einer mehrformigen Quelle, `load-lib`, `(b) => 42`,
`gc_badobj=0`, `mem_oom=0`.

Codex hat danach den erweiterten HW-Pfad mit D81 `ide` + Demo-/Compile-Slots
bestaetigt: IDE-on-demand, Buffer-Load/Save, Reload aus gepaddetem Save-Slot,
`compile-buffer-to-lib`, `load-lib`, `(demo-numbers-run) => 42` und `(edit)` auf dem geladenen
Buffer bei `617/640` Symbolen. Die 8-KB-Namepool-Variante scheiterte auf HW
trotz Symbol-Headroom mit `too many symbols`; der aktuelle Workbench-Pin nutzt
`NAMEPOOL=9536`, `SYMPOOL_EXT_OFF=0xc9e0` und `MAX_SYM=720`.

Quelle: `docs/project-status.md`, `docs/workbench-gate.md`,
`docs/archive/collaboration-2026-07-08.md`.

## 2026-07-08: `symfn` darf als MVP-Budgetvent nach EXT

`LISP65_SYMFN_EXT` verlagert Funktionszellen der Symboltabelle nach EXT-RAM.
Das loest den IDE-On-Demand-Symbolbedarf im Workbench-Pin ohne weiteren
Bank-0-BSS-Druck. Trade-off: Bytecode-CALL-Aufloesung zahlt DMA; MRU-/Slot-
Cache-Varianten passten nicht unter das PRG-Ende-Gate. Deshalb ist der Pfad fuer
MVP akzeptiert. Seit 2026-07-08 ist die dynamische Exposure per
`make workbench-symfn-dynamic-report` gegatet; aktueller Pin:
15 IDE-/Compiler-Szenarien, 127961 Host-Instruktionen,
8939 dynamische `symfn`-Aufloesungen. Das ist kein
Zyklusmodell; Live-HW-Timing bleibt nur bei beobachteter Latenzverschlechterung
noetig.

Quelle: `docs/workbench-gate.md`, `docs/symbol-table-ext-design.md`.

## 2026-07-08: `make check` misst den Workbench-Kandidaten

Das alte native-FASL-Core-Footprint-Gate ist nicht mehr Standardgate.
`make check` und `bank0-reclaim-report` verwenden den aktuellen
Workbench-Kandidaten. Das historische Target bleibt Referenz/Diagnose.

Quelle: `Makefile`, `docs/bank0-reclaim-candidates.md`.

## 2026-07-08: `mvp-ship` bezeichnet das Workbench-MVP

Die damalige Produktentscheidung legt den Paketinhalt fest: PRG, externes
Stdlib-Blob und D81 mit ladbarer IDE-Lib plus vorallokierten
Compile-Zielslots. Der alte `einsuite-full`-Ship-Pfad bleibt
Referenz/Regression, aber nicht mehr Produktdefinition. Die spaetere
Entscheidung vom 2026-07-09 trennt davon den unverifizierten Build und die
strikte G2-Promotion; sie ersetzt die damalige einfache Targetsemantik.

Quelle: `docs/workbench-gate.md`, `docs/project-status.md`.

## 2026-07-08: Persistenz-API in der ladbaren IDE-Lib

Die Workbench bekommt eine schmale Lisp-API fuer Editor-Persistenz und
persistente Library-Erzeugung aus Buffern: `dir`, `load-file-to-buffer`,
`save-buffer-to`, `eval-buffer`, `compile-buffer-to-lib` und
`compile-file-to-lib`. Die API lebt in
der ladbaren `ide`-Lib, nicht resident in Bank 0. `compile-file-to-lib` ist
hier kein ANSI-/nativer-FASL-Reader, sondern liest Disk-Source in Lisp und ruft
den Workbench-`compile-string`-Pfad.

Quelle: `lib/ide-disk.lisp`, `docs/workbench-gate.md`.

## 2026-07-08: Compile-Terminologie getrennt

`compile` ohne Zusatz soll kuenftig transientes Kompilieren in die laufende
Session bedeuten. Persistente L65M/FASL-Ausgabe heisst `compile-*-to-lib` oder
`compile-*-to-fasl`; Ausgabe plus sofortiges Laden heisst
`compile-*-to-lib-and-load`. Die Workbench-IDE-Wrapper wurden auf
`compile-buffer-to-lib` und `compile-file-to-lib` umgestellt; `compile-string` bleibt der kleine
Low-Level-Backend-Pfad.

Quelle: `docs/ide-api-terminology.md`.

## 2026-07-08: Editor-Compile-UX bleibt auf `compile-load`

Der erste Editor-Compile-Befehl ist `C-x C-k`: ein Minibuffer fragt den
Zielslot ab, Default `fasl0`, danach wird der aktuelle Buffer in die
Buffer-Tabelle gespiegelt und via Lisp-API
`(compile-buffer-to-lib dst name)` als L65M/FASL-Lib geschrieben und danach
per `load-lib` geladen. Es gibt keinen neuen
residenten C-Pfad und keine neue oeffentliche Compile-API nur fuer den Editor.

Quelle: `lib/ide-ui.lisp`, `lib/ide-disk.lisp`, `docs/workbench-gate.md`.

## 2026-07-08: Editor-Persistenzfehler laufen ueber `(ide-error)`

Find/Write/Save/Compile im Editor verwenden die oeffentlichen
Persistenz-Wrapper (`load-file-to-buffer`, `save-buffer-to`,
`compile-buffer-to-lib`). Damit zeigen REPL-API und Statuszeile
dieselben Fehlertexte wie `"source missing"`, `"slot missing"`, `"too large"`,
`"compile failed"` oder `"load failed"`. Der MVP-Nutzerfluss ist explizit
gepinnt:
`load-file-to-buffer` -> `(edit "demo")` -> `save-buffer-to` ->
`compile-buffer-to-lib` -> `load-lib` -> Demo-Funktion ausfuehren.

Quelle: `lib/ide-disk.lisp`, `tests/bytecode/libs/p0-ide-lib.json`,
`docs/workbench-gate.md`.

## 2026-07-08: `compile-string` setzt `(compile-error)`

`compile-string` bleibt rueckgabeseitig kompatibel (`t`/`nil`), setzt bei
direkten Fehlern aber `%compile-error`, abrufbar ueber `(compile-error)`.
Der Workbench-Pfad unterscheidet damit ohne neuen C-Code mindestens
`"bad source"`, `"bad slot"`, `"slot missing"`, `"too large"` und
`"save failed"`. Die IDE-Wrapper uebernehmen diese Details in `(ide-error)`.
Die Umsetzung nutzt vorhandene Disk-Directory-Bausteine aus `stdlib-load.lisp`
und bleibt im Workbench-Alignment unter der kritischen 320-Funktionsgrenze.

Quelle: `lib/lcc-fasl.lisp`, `lib/ide-disk.lisp`,
`tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json`.

## 2026-07-08: Kein `m65 -F` im normalen Deploy-Workflow

Etherload-Deploys sollen ohne harten JTAG-Reset laufen. `m65 -F` bleibt
Recovery-Werkzeug fuer echte Freezes, weil es das Hypervisor-Scharfstell-Flag
loescht.

Quelle: `docs/reference/mega65-hardware-testing.md`,
`docs/hardware-stress-tests.md`.

## 2026-07-08: `STACK_GUARD` und EDMA-Scroll bleiben Opt-in

`LISP65_STACK_GUARD` und `LISP65_SCREEN_EDMA_SCROLL` sind fachlich nuetzlich,
aber im Default-Core aktuell Bank-0-rot. Vor Default-Integration braucht es
belastbaren Reclaim.

Quelle: `docs/mega65-native-budget-strategy.md`,
`docs/bank0-reclaim-candidates.md`.

## 2026-07-09: Readerfehler bleiben ABI-kompatibel, aber explizit

`read_expr` und `read_expr_stream` behalten ihre bestehenden Signaturen. Ein
separater Readerstatus unterscheidet jetzt eine gueltige `NIL`-Form, EOF und
Fehler; ein Fehlercode pinnt die konkrete Ursache. Oeffentliche Readergrenzen
restaurieren den Shadow-Root-Stack und melden an ein aktives REPL-Toplevel,
Loader beenden ohne Toplevel die aktuelle Quelle explizit. Diese Variante
vermeidet den breiten und auf dem 6502 teuren Status-plus-Out-Parameter-Umbau.

Der interne Symbolvertrag bleibt lowercase, damit System- und Bytecode-Namen
kompatibel bleiben. Eingabe wird ASCII-case-insensitiv dorthin normalisiert;
die normative CL-nahe Fixture und der Testtreiber drucken Symbole kanonisch
uppercase. Strings quoten das Folgebyte nach Backslash, und `print_obj` escaped
Backslash und Quote fuer einen stabilen Read/Print-Roundtrip.

Quelle: `src/reader.c`, `src/reader.h`, `src/printer.c`,
`lib/tests/mvp-reader-cases.json`.

## 2026-07-09: Workbench nutzt identisches Code-Folding als AP1-Budgethebel

Das Workbench-Profil linkt mit `--icf=all`. Der llvm-mos-Linker faltet dabei
903 Byte identischer, bereits out-of-line erzeugter `cell_type`, `cell_a`,
`cell_b`, `cell_set_a` und `cell_set_b`-Klone aus verschiedenen Translation
Units. Es entstehen keine neuen Calls oder Frames; Funktionsadressen dieser
statischen Helfer sind kein Vertrag. Der Hebel finanziert die Readerhaertung,
ohne REPL-History, Zeilenlaenge, Closures, IDE oder Persistenz zu entfernen.
Host-, Produkt- und Footprint-Gates sind Pflicht; echte MEGA65-Hardware bleibt
wegen des neuen Linkerverhaltens Release-Abnahme.

Quelle: `Makefile`, `docs/project-status.md`.

## 2026-07-09: Ship trennt unverifizierten Build von G2-Promotion

Die Aussage vom 2026-07-08, `mvp-ship` baue lediglich das Workbench-Paket,
wird praezisiert: lokales WIP entsteht dirty-tree-tolerant mit
`mvp-ship-artifacts` unter `build/ship-candidate/` und traegt explizit den
Status `unverified-candidate`. Dieser Pfad ist fuer lokale Produktgates
erforderlich, aber keine Release- oder Promotionsentscheidung.

`mvp-ship` ist jetzt der strikte Wrapper. Er verlangt einen sauberen Tree,
speichert die Quellenprovenienz im Preflight, fuehrt das kumulative G2 aus,
vergleicht Commit, Tree und Worktree danach erneut, promotet nach
`build/ship/` und verifiziert das Ergebnis offline. Auch dieses Paket heisst
bewusst `g2-verified-candidate`: G3 und G5 sind nicht ausgefuehrt, daher ist es
noch keine Release-Freigabe.

Das Manifestformat `lisp65-workbench-ship-v2` pinnt Hash und Groesse aller
Artefakte, Commit-/Tree-/Worktree-Provenienz, aufgeloestes Produktprofil,
Toolchain-Report und Gatezustand. `verify-ship` vertraut keiner Buildsession,
sondern nur dem Manifest und dem Paketinhalt und lehnt unerwartete Pfade,
Symlinks sowie Hash-/Groessenabweichungen ab.

Reproduzierbarkeit wird getrennt von variablen Provenienzmetadaten gemessen:
`workbench-reproducibility-check` baut zwei isolierte Kandidaten und verlangt
byteidentische PRG- und Stdlib-Blob-Artefakte. Der erste Lauf am 2026-07-09 ist
gruen.

Quelle: `Makefile`, `scripts/build-mvp-vm-ship.sh`,
`tools/host-lisp/workbench_ship.py`, `docs/workbench-gate.md`.

## 2026-07-09: Produktgates sind kumulativ; Dry-Run und Live bleiben separat

G0 `check-source`, G1 `check-host` und G2 `check-product` sind kumulativ;
`make check` und `workbench-gate` sind Aliase fuer G2. Historische Vollprofile
und bekannte Diagnosepfade laufen nur noch ueber `check-reference` bzw.
`reference-diagnostics` und koennen das Standardproduktgate nicht rot faerben.

G3 `check-emulator` meldet explizit, dass derzeit kein belastbarer
Workbench-xmega65-Produktfluss verfuegbar ist. G4
`check-hardware-dry-run` prueft nur Deploy-Kommandos und Artefaktpfade, G5
`check-hardware` fuehrt echte MEGA65-Aktionen aus. G4 wird damit nicht mehr als
Hardwarebeweis und G5 nicht mehr als impliziter Bestandteil von `make check`
behandelt. CI-Provider und echte G3-/G5-Releaseautomatisierung bleiben offene
Architektur- und Infrastrukturarbeit.

Quelle: `Makefile`, `docs/make-target-taxonomy.md`,
`docs/project-realignment-plan-2026-07-09.md`.

## 2026-07-09: Workbench-Profil ist explizit und generatorseitig isoliert

`config/workbench.mk` ist die einzige kanonische Definition des interaktiven
Produktprofils. CFLAGS, Defines, Linkflags, Heap, Suite, Budgets und
Artefaktpfade sind dort explizit gepinnt; historische Profilketten werden
nicht mehr per `filter-out` zum Produktprofil umgebaut. Die generierte
Workbench-Stdlib liegt unter `build/bytecode/profiles/workbench/`, sodass
generische `stdlib-p0.*`-Artefakte den Produktbuild nicht mehr ueberschreiben.

Die Strukturmigration ist verhaltensneutral abgenommen: Das PRG bleibt bei
41032 Byte; PRG und externes Stdlib-Blob sind SHA-256-identisch zum
Ausgangsstand. Generische und historische Profile werden erst in einem
spaeteren Slice namespacet.

Quelle: `config/workbench.mk`, `mk/workbench.mk`,
`docs/workbench-gate.md`.

## 2026-07-09: Make-Module und Doctor bilden den AP3-Buildvertrag

Der Root-Makefile behaelt mit `.DEFAULT_GOAL := all` seinen stabilen Einstieg.
Toolchain, Workbench und Gate-Aggregationen liegen in `mk/toolchain.mk`,
`mk/workbench.mk` und `mk/gates.mk`. `mk/bytecode.mk` wird bewusst noch nicht
in denselben Slice gezogen, damit die breite generische Bytecodeflaeche
separat abgenommen werden kann.

`make doctor` prueft read-only und gatebezogen die lokale Bereitschaft. Default
ist G2; `DOCTOR_GATE` erlaubt G0/G1/G2/G4/G5 und `DOCTOR_FORMAT` Text oder
JSON. Compiler- und D81-Faehigkeitsproben nutzen temporaere Verzeichnisse
ausserhalb des Worktrees. Der G5-Vertrag prueft lokale Live-Tools, fuehrt aber
keine Hardwareaktion aus; Hardwarezugang bleibt deshalb `deferred`, und der
Gesamtstatus lautet entsprechend `ready-with-deferred` statt `ready`.

Quelle: `Makefile`, `mk/toolchain.mk`, `mk/gates.mk`,
`tools/host-lisp/project_doctor.py`.

## 2026-07-09: Ship-Verifikation prueft inneren Stdlib-Vertrag und Paketmenge

Das Workbench-Paket besteht exakt aus neun Dateien: acht im Manifest gelistete
Artefakte plus `manifest.json`. Zusaetzliche Eintraege sind ebenso ungueltig
wie fehlende, manipulierte oder ueber Symlinks umgeleitete Dateien. Der
Verifier prueft ausserdem Format, Rolle und Suite des inneren
Stdlib-Artefaktmanifests und gleicht dessen Blob-Groesse und SHA-256 mit dem
ausgelieferten Blob ab. Temporaere D81-Slot- und Demo-Dateien werden
standardmaessig ausserhalb des Paketverzeichnisses erzeugt und entfernt.

Quelle: `tools/host-lisp/workbench_ship.py`,
`scripts/build-workbench-d81.sh`.

## 2026-07-09: Bank-0-Lifetimes werden physisch und policybasiert gemessen

`bank0-lifetime-report` dedupliziert ELF-Symbole nach Section, Adresse und
Groesse, damit durch `--icf=all` bereits gefaltete Aliasnamen nicht erneut als
Reclaim-Potenzial zaehlen. Die versionierte Policy
`config/bank0-lifetime-workbench.json` klassifiziert grosse physische
Allokationen als `runtime-hot`, `runtime-cold`, `boot-only`, `dev-only` oder
`bss-cap`. Unklassifizierte Grosssymbole, Regelkonflikte, stale Matcher und
Wachstum ueber den aktuellen Bank-0-Pin machen G2 rot.

`boot-only` bezeichnet ausschliesslich theoretisches Lifetime-Potenzial. Ohne
separate Layout-, Boot-Stack-, Packaging- und Hardwaregates gilt kein Byte als
reclaimed. Der aktuelle Report weist 2206 B sicher boot-only aus; die
Architektur fuer deren Auslieferung und Wiederverwendung wird separat
entschieden.

Quelle: `tools/host-lisp/bank0_lifetime_report.py`,
`config/bank0-lifetime-workbench.json`, `docs/bank0-reclaim-candidates.md`.

## 2026-07-09: Trailer-Reclaim und Runtime-Core werden kombiniert

Die Workbench bleibt das einzige interaktive Produkt; ein expliziter
Runtime-Core wird als Export-/Deployment-Artefakt aufgebaut. Beide Profile
teilen ABI, Loader und Quellbaum, besitzen aber getrennte explizite
Konfigurationen, Budgets, Namespaces, Manifeste und spaeter profilgebundene
Boot-Overlays. Flag-Vererbung und `filter-out`-Profile sind ausgeschlossen.

Als erster Slice reserviert `io_disk_lib_staged` Code plus L65M-Trailer nur als
Load-Peak und committed nach erfolgreicher Registrierung ausschliesslich den
Code. Die IDE-Lib reclaimed dadurch 23010 B und behaelt 23396 B EXT-Reserve.
Der Mechanismus kostet 84 B Bank 0; Lifetime-Pins wurden auf den gemessenen
Produktstand nachgezogen. Der Commit ist eine Allokatortransaktion, noch keine
vollstaendige semantische Loadertransaktion: Vor Runtime-Core-Promotion ist ein
read-only L65M-Preflight vor der ersten sichtbaren Mutation erforderlich.

Quelle: `src/io.c`, `tools/host-lisp/workbench_disklib_budget.py`,
`scripts/vm-ext-code-reclaim-smoke-main.c`,
`docs/profile-consolidation-strategy.md`.

## 2026-07-09: Runtime-Core startet als evaluatorfreier G2-Prototyp

Der erste Runtime-Core wird nicht aus Workbench-Flags herausgefiltert, sondern
in `config/runtime-core.mk` vollstaendig explizit definiert. Sein Quellset
enthaelt VM, Speicher, Symbole, Embed-Loader, Interruptpfad und einen eigenen
benannten Launcher, aber keinen Reader, keine REPL, kein Eval, kein
Treewalk-`apply`, kein lcc und keinen Compiler. `LISP65_VM_NATIVE_APPLY`
ersetzt die sachlich falsche Kopplung dieser VM-Faehigkeit an Compile-REPL.

Der native Host-Smoke bootet ohne `eval_init`, haelt beide Treewalk-Hooks null
und fuehrt `runtime-main` zu 42 aus. Der llvm-mos-Prototyp misst bei denselben
Kern-Caps wie die Workbench 23079 B PRG und 15940 B Bank-0-Reserve; das
Link-Audit findet keine verbotene Entwicklungsflaeche. Der harte Prototyp-Pin
haelt mindestens 8192 B Bank-0- und Stack-Reserve fest.

Bewusste Grenze: Das Profil ist embedded-only. Disk-Lib-Loader,
Exportdescriptor, Paketverifier und Hardware-Deploy werden erst nach dem
vollstaendigen L65M-Preflight integriert; bis dahin ist es kein zweites
Nutzerprodukt.

Quelle: `config/runtime-core.mk`, `mk/runtime-core.mk`,
`products/runtime-core/main.c`, `tools/host-lisp/runtime_core_audit.py`,
`scripts/runtime-core-smoke-main.c`.

## 2026-07-09: Boot-Overlays verwenden einen hybriden, profilgebundenen Transport

Runtime Core und Workbench teilen den Overlay-ABI- und Lifetime-Vertrag, aber
nicht die physische Auslieferung. Der Runtime Core behaelt sein Boot-Overlay als
PROGBITS-Sektion im selben flachen PRG. Das gemessene Dateiende von etwa
`$81f2` bleibt weit unter seinem Limit `$b000`; der Boot ist damit unabhaengig
von Speicherresten eines vorherigen Transfers und benoetigt keinen residenten
Kopierpfad.

Die Workbench kann ihr 1078-B-Overlay nicht flach ausliefern: Dateiende `$c99a`
wuerde das Produktlimit `$c0c0` um 2266 B ueberschreiten. Descriptor und
Payload werden deshalb profilgebunden hinter dem bestehenden externen
Stdlib-Image in Bank 5 gestaget. Ein kleiner residenter Bootstrap prueft Format,
Build-ID, VMA, Entry, Laenge und CRC, kopiert erst danach per bestehender
F018-Naht und ruft den Entry fail-closed auf. Der gemessene Bruttogewinn hebt
die Post-Boot-Reserve von 192 auf 1266 B; Bootstrap plus zusaetzliches BSS
duerfen daher hoechstens etwa 242 B kosten, damit das harte 1024-B-Ziel haelt.

Ein separates direktes Bank-0-Preload vor `etherload -r` ist nur Diagnose, kein
Produktvertrag: Reset-Persistenz ist fuer diesen Bereich nicht belegt. Kein
Overlay-Reclaim wird vor Host-Negativtests, Boot-Stack-Watermark, Emulator-/
Hardware-Boot und Reclaim-Stress als Produktreserve gebucht.

Quelle: `docs/overlay-package-format.md`,
`scripts/lisp65-mega65-workbench-overlay.ld`,
`tools/host-lisp/overlay_package.py`, AP4.3-Linkmessungen.

Erster Loader-only-Befund: Der vollstaendige Descriptor-/CRC-Bootstrap kostet
im echten Workbench-Link mehr als die anfangs reservierten 242 B. Das residente
PRG misst 40609 B, das 1084-B-Overlay liegt bei `$c7b2..$cbee`; der Post-Boot-Stack-Gap
betraegt 2128 B und die Reserve ueber dem 1450-B-Laufzeitbudget nur 678 B. Das
1024-B-Ziel wird damit um 346 B verfehlt. Der sichere Vertrag wird nicht
abgespeckt. Der Loader-only-Slice bleibt ein bewusst roter Prototyp; vor einer
Promotion ist weiterer belegter Boot-only-Reclaim erforderlich.

Nachentscheidung: Der freigegebene kombinierte Ansatz verschiebt nicht nur den
Loader, sondern die gesamte einmalige Boot-Transaktion (`eval_init`,
`defprim`, `vm_load_embedded_stdlib`, `gc_freeze_boot`) hinter einen gemeinsamen
Entry. Der Installer ist strikt one-shot und stoppt auch auf `mem_oom`.
Dadurch misst das residente PRG 39524 B, das Overlay 2257 B, der Boot-Gap
955 B und die Post-Boot-Reserve 1764 B. Das harte Boot-Minimum bleibt beim
bereits gepinnten Wert 512 B; 1024 B werden als separater Zielwert berichtet
und aktuell um 69 B verfehlt. Das Post-Boot-Minimum 1024 B und der Zielwert
1536 B sind erfuellt. Die statischen und Host-Gates sind damit gruen, die
Promotion bleibt bis zum Soft-/Hardware-Stack-Watermark und Reclaim-Stress auf
dem Geraet gesperrt.

## 2026-07-09: AP4.4 wertet Boot-Canaries extern per JTAG aus

Die opt-in Diagnosevariante fuellt vor dem Installer den freien llvm-mos-
Softstack oberhalb des Overlay-Endes mit `$a5` und den freien Page-1-Stack mit
`$5a`. Der erste Target-Scanner im residenten C-Code drueckte den statischen
Boot-Gap auf 413 B und verletzte damit das unveraenderte 512-B-Minimum um 99 B.
Das Minimum wird nicht fuer Diagnosecode abgesenkt. Stattdessen exportiert das
Target nur Initialwerte, Abschluss-/Fehlerflags und Wipe-Status; der ohnehin
verpflichtende JTAG-Readback scannt die Speicherfenster extern. Der Host-Smoke
behaelt denselben Scanner an einer Array-Naht.

Der resultierende Diagnosebuild besitzt 641 B Boot-Gap, 1453 B Post-Boot-
Reserve und genau einen residenten Einstieg ins 2261-B-Overlay. Er bleibt ein
nicht-default Messartefakt. Der echte Lauf mit Combined Preload misst 452 B
Softstack-Marge und 202 B Page-1-Rest. Overlay-Wipe, IDE-Lib, GC-Stress,
REPL-Fehlererholung sowie VM-/Treewalk- und `funcall`-Bruecken sind danach
gruen. Damit ist die AP4.4-Reclaim-Abnahme erfuellt; eine Produktpromotion
braucht weiterhin die getrennte Stack-Guard-Abnahme und eine explizite
Architekturentscheidung.

## 2026-07-09: Stack-Guard schuetzt den Linker-Floor, Promotion bleibt separat

Der opt-in Device-Guard vergleicht den llvm-mos-Soft-SP nicht mehr nur mit dem
Ende des statischen Lisp-Heaps, sondern mit `__heap_start +
LISP65_STACK_MARGIN`. Damit umfasst die Schutzgrenze auch alle nach dem Heap
liegenden residenten BSS-Anteile und den nach Boot reclaimten Overlay-Floor.
Der Hostpfad bleibt unveraendert inaktiv.

Die exakte Guard-/Overlayvariante misst 39862 B Resident, 2245 B Overlay,
631 B Boot-Gap und 1427 B Post-Boot-Reserve. Der disassemblierte Grenzwert ist
`$c4dc = $c4c4 + 24`. Paket-, Kontrollfluss- und Footprint-Audits sowie der
echte IDE-/VM-Bridge-/GC-/Abort-Lauf sind gruen. Diese technische Abnahme
promotet den mehrteiligen Deploymentvertrag nicht still in Workbench, G4/G5
oder `mvp-ship`; diese Umschaltung bleibt eine eigene Architekturentscheidung.

## 2026-07-09: Guard-Overlay ist kanonischer Workbench-/Ship-v3-Vertrag

Nach expliziter Freigabe wird die technisch abgenommene Guard-Variante als
einziger interaktiver Produktpfad promotet. `workbench-product` besteht nach
der finalen ABI-Neubindung aus dem 39891-B-Resident-PRG und dem 36823-B-
Combined-Preload aus demselben finalen ELF und ABI-Vertrag. Der bisherige
flache Workbench-Link bleibt unter
`WORKBENCH_REFERENCE_*` und seinen historischen `mvp-*`-Targets verfuegbar,
ist aber kein Ship-Eingang mehr.

Das Paket behaelt exakt neun Dateien. `lisp65-workbench-ship-v3` bettet die
vollstaendige Stage-Bindung in `manifest.json` ein. Der Offline-Verifier
rekonstruiert Stdlib-Praefix, Nullpadding, Descriptor, Payload, CRC16,
Resident-/Preload-Hashes, Guard-ABI, Build-ID und die `$c9e0`-Stage-Grenze. Der
Reproduzierbarkeitscheck baut zwei isolierte Guard-Verzeichnisse und vergleicht
alle neun Paketdateien bytegenau.

G4 darf den dirty-tree-toleranten Kandidaten pruefen. G5 ist dagegen
verified-only: `check-hardware` verifiziert zuerst `build/ship/`, vererbt diesen
Pfad an die gesamte Live-Matrix und baut dort niemals einen Kandidaten. Damit
bleiben Entwicklungsdiagnose und Releaseabnahme getrennt. Die noch offene
Clean-Commit-Promotion ist eine Provenienzanforderung, keine technische
Ruecknahme der Produktentscheidung.

Der finale ABI-gebundene Candidate wurde anschliessend erneut auf echter
MEGA65-Hardware gestartet. Arithmetik, IDE-Laden, Bytecode-Erkennung,
VM-/Treewalk- und `funcall`-Bruecken, 400 Allokationsrunden sowie
Reader-Abbruch/Erholung sind gruen. Dieser Lauf ist eine technische
Candidate-Stichprobe, kein G5: Das neue `check-hardware` bricht ohne strikt
verifiziertes `build/ship/manifest.json` vor jeder Hardwareaktion ab.

## 2026-07-10: G5 akzeptiert nur vorab verifiziertes JTAG-Echo

Der Workbench-UX-Harness prueft jede komplette Form am aktiven Prompt, bevor er
RETURN separat sendet. Abweichende Eingaben werden per INST/DEL verworfen; ein
zweiter Capture muss den leeren Prompt beweisen. CR und Tilde sind im
Formtransport verboten, weil `m65` sie als RETURN beziehungsweise Escape
interpretiert. Jeder `m65`-Prozess hat einen normalen und einen harten Timeout.
Setup-Ergebnisse muessen sichtbar und frei vom nativen `*** `-Fehlerprefix sein;
finale Oracles werden exakt im neuesten REPL-Segment verglichen. Nur der
idempotente, prozessspezifische Core-Sentinel darf nach der Ausfuehrung einmal
wiederholt werden.

Commit `a82d68f9502c5e42267d33e1d5e528b760bb61ff` wurde in einem sauberen Worktree
durch G2 gebaut und als Ship-v3 promotet. Manifest-SHA-256 ist
`cee107a1b4de25a3deb2443fee824341b1dfbef841b109dbb01b9ca975e93f40`. Die
verified-only Hardwarematrix bestand Guard-Overlay, Basis-Deploy, 27 UX-Phasen,
BAM-Read und M2-M7 inklusive D81-Diff, Readback, Workbench-Load/Run und Restore.
Der echte Core-Sentinel nahm dabei einmal erfolgreich den neuen sicheren
Pre-submit-Retry.

Ein `mega65_ftp`-No-response unterbrach den Aggregate einmal vor dem M4-Load-
Oracle. M4 wurde daraufhin vollstaendig mit demselben Paket wiederholt und war
gruen; M5-M7 bestanden anschliessend ebenfalls. Ein zweiter, unveraenderter
`make check-hardware`-Gesamtlauf bestand danach die vollstaendige Matrix in
einem Prozess mit Exitcode 0. Der erste Fehler bleibt damit als externer
Ethernet-Transient dokumentiert, waehrend G5 fuer das benannte Paket auch als
Aggregate belegt ist. G3 bleibt nicht verfuegbar, und der Paketstatus bleibt
bis zu einer separaten Releaseentscheidung `g2-verified-candidate`.

## 2026-07-10: Semantikvertraege werden zentral registriert, Produktclaims separat freigegeben

`config/semantic-contracts.json` ist der autoritative Index fuer normative
lisp65-Fixtures, Engines, Adapter, Gate-Stufen, Coverage-Gaps und
Legacy-Referenzen. Die Registry kopiert keine Cases. Ihr Runner verwendet nur
Argumentlisten ohne Shell, validiert Pfade und Fixture-Formate fail-closed und
beendet bei Timeout die gesamte Adapter-Prozessgruppe.

AP5.1 registriert Reader und Bytecode-P0. G0 besitzt die reinen Python-Adapter;
G1 besitzt beide nativen Reader-Profile, ABI-Drift und C-VM. Die dafuer
benoetigten generierten Bytecode-Artefakte bleiben Make-Voraussetzungen und
werden nicht vom Registry-Runner gebaut. Die bisherigen Einzelziele wurden aus
den Aggregaten entfernt, nicht doppelt ausgefuehrt. LISP64 ist nur noch eine
explizite Referenz unter `check-reference`.

`check-product` ruft die G2-Registry-Stufe bereits auf. Solange kein
Produktclaim existiert, lautet das Ergebnis ausdruecklich `SKIP`. Ein spaeterer
Produktclaim braucht einen fixture-gebundenen G2-Adapter und zusaetzlich einen
separat im Runner freigegebenen Repo-Entrypoint. Ein Registry-Eintrag allein
darf daher keine Produktkonformitaet behaupten.

## 2026-07-10: Runtime-Slices, Split-Boot und Fehlertexte bilden Ship-v4

Die Workbench verwendet fuer alle transienten Images ein gemeinsames
Linker-`OVERLAY`: eine Bank-0-Ausfuehrungs-VMA und getrennte LMAs im
profilgebundenen Bank-3-Katalog. Das maschinelle Slotbudget ist auf `37/64`
gepinnt. Slots 0-1 verifizieren den Transport, 2-22 tragen den 21-Phasen-
L65M-Preflight, 23-29 den Commit, 30-32 den LCC-Installer, 33-35 den
profilgebundenen Boot-Fastpath und Slot 36 die dedizierte L65E-Slice. Weitere
Produktslots brauchen eine erneute Architektur- und Budgetentscheidung.

Der Boot bleibt bewusst geteilt. Das 1393-B-Bank-5-Overlay fuehrt `eval_init`
aus. Slots 33-35 pruefen die gebundene Stdlib, patchen die erlaubten flachen
Literale und publizieren Entries+Freeze. Die eingebettete Stdlib und das PRG
sind ein gemeinsam gebautes Artefakt: Semantik ist deshalb eine
Buildgate-Eigenschaft. Ship bindet Gate-Ergebnis, Contract-SHA, Build-ID,
Laenge und CRC; die Laufzeit prueft genau einmal die Whole-image-CRC vor der
ersten Bank-5-Bootmutation. Disk-Libs sind dagegen Laufzeitmedien und behalten
den vollen 21-Phasen-Preflight vor jeder sichtbaren Mutation.

Fehleridentitaet ist ein stabiler 45-Code-Vertrag. L65E-v1 enthaelt eine
erweiterbare Sparse-Tabelle mit Klartext fuer 31 nutzererreichbare Workbench-
Pfade; 14 im Profil nicht gebaute Codes sind explizit und begruendet
`not-built`. Ein ELF-Drift-Gate blockiert neue Emissionen ohne Klassifikation.
Slot 36 ist mit 1286/1320 B separat gegatet. Der Renderer alloziert nicht und
degradiert bei aktivem/defektem Transport auf `Ehh`, wobei `hh` den stabilen
Hex-Code bezeichnet.

Ship-v4 erweitert das Paket von neun auf zehn Dateien um die Runtime-Overlay-
Bank. Das Manifest bindet alle 37 Slots, den zweistufigen Stdlib-Vertrag und
`error_texts` mit Slot, Codeklassen, Offset, Laenge, CRC, SHA, Contract-SHA
und Build-ID. Der aktuelle WIP misst nach 519 B HW-Math-Reclaim einen
Guard-Wrapper-Floor von `$c41a`, 39644 B Resident, 35971 B Combined Preload,
1393 B Boot-Overlay, 1653 B Boot-Gap, 3048 B Runtime-Gap und 1598 B
Post-Boot-Reserve. Das 1536-B-Ziel ist damit im Link erfuellt.

Die Clean-Tree-Promotion ist abgeschlossen: Commit
`3f02391b6d462e5511ca93ece3dad9d7183c099c`, Manifest-SHA-256
`456d27134ec20e92f3507e340a9e8a0093460c532f943f82b601dc1f9823684a`, Status
`g2-verified-candidate`. G0-G2, G4-Dry-run und der byteidentische Doppelbuild
aller zehn Ship-v4-Dateien sind gruen; Live-G5 bleibt offen. Auf echter
Hardware muessen die einmalige 34325-B-CRC-/Bootlatenz und `C-x C-k` ueber
Compile, drei LCC-Slices und Load-Lib-Preflight/Commit gemessen werden;
OOM/Abort bei aktivem Latch muss
weiter sauber auf `Ehh` degradieren. Das Ship-v3/G5-Paket bleibt bis dahin der
historische live-verifizierte Stand.

## 2026-07-10: Reset-stabiler Attic-Katalog und ehrlicher Ship-v5-Vertrag

Die Bank-3-Ablage wird verworfen, weil der MEGA65-Reset Banks 1-3 wieder mit
ROM-Inhalt belegen kann. Der Runtime-Katalog liegt ab sofort als 64-KB-L65R-v1-
Fenster bei `$08000000` im Attic RAM. Das Binaerformat bleibt unveraendert und
behaelt seinen historischen Format-Tag `3`; nur das physische Storage-Binding
wechselt. Ein residenter, statisch initialisierter 20-B-EDMA-Job liest per
28-Bit-Quelle in das gemeinsame Bank-0-Ausfuehrungsfenster. ROM-Unprotect und
Reset-Restaging werden bewusst nicht eingefuehrt.

Ship-v5 bindet den Attic-Preload mit Adresse, Adressbreite, Laenge,
Whole-image-CRC16, SHA-256, Profil-Build-ID, `reset-stable-power-volatile` und
`redeploy-required`. Producer und Finalizer erzeugen nur v5; v3 und v4 bleiben
read-only verifizierbar. Der Katalogfehler ist stabiler Code 46 und besitzt den
residenten, allokationsfreien Text `E2e catalog missing; redeploy`, weil die
L65E-Slice bei fehlendem Attic selbst nicht erreichbar ist.

Der Attic-Transport kostet im finalen Link 46 B. Mit dem residenten Fehlerpfad
misst der WIP 39805 B Resident, 1393 B Boot-Overlay, 1493 B Boot-Gap, 2887 B
Runtime-Gap und 1437 B Post-Boot-Reserve. Das harte Minimum 1024 B bleibt mit
413 B Luft gruen; das unveraenderte 1536-B-Ziel wird um 99 B verfehlt. Dieser
Miss wird nicht durch ein niedrigeres Gate oder Mikrodiaeten kaschiert, sondern
als eigener Reserveblock von mindestens 192 B weitergefuehrt.

G5 wird zweistufig: Zuerst werden PRG, Bank 5 und Attic haltend per JTAG geladen
und vor erster Ausfuehrung per `memsave`/SHA geprueft. Danach startet der
kanonische Etherload-Pfad mit Reset, PRG-Reload und D81-Remount; Attic wird nach
Reset erneut gehasht und ein echter `load-lib`-Preflight muss ein exaktes letztes
REPL-Ergebnis am finalen leeren Prompt liefern. Ein atomarer Receipt bindet
beide Phasen an denselben Manifest-SHA; abweichende Zieladressen und ein
uebersprungener D81-Upload sind im Ship-G5-Pfad unzulaessig. JTAG ist dabei
Mess-Gate, nicht Produkt-Deploypfad.

Die Clean-Tree-Promotion ist fuer Commit
`4cff6b9562665765dbeab142660405f536a55fdf` abgeschlossen. Das strikt
verifizierte Ship-v5-Manifest hat SHA-256
`72a6cb508b29ac65c448a79620c6a82743bd1ec1fc5bc2015a31f67363d828bf` und den
Status `g2-verified-candidate`. G0-G2, Reproduzierbarkeit, G4 und der
zweistufige Dry-run direkt gegen den promoteten Satz sind gruen; Live-G5 bleibt
offen.

## 2026-07-11: AP4-Layout ist nach Validator-/Commit-Haertung eingefroren

Der Workbench-Produktvertrag umfasst 38 von 64 L65R-Slots. Slot 37 installiert
die immutable, build-gebundene Speicherinsel bei `$1800`; ihr Inventar bleibt
auf acht L65M-/Batch-Koordinatoren beschraenkt. Die Insel belegt 1108 B, der
mutable Rootstack-Annex 260 B, und 680 B des festen `$1800..$1fff`-Fensters
bleiben frei. Der Screenvertrag ist weiterhin `$0800`, 80x50 und ein Byte pro
Zelle; SEAM setzt vor Nutzung der Insel eine Screen-Relocation voraus. Das nur
beim Link benoetigte Seed-LMA liegt nicht mehr an einer willkuerlichen festen
Adresse, sondern 256-Byte-ausgerichtet direkt hinter Slot 37. VMA `$1800`,
Slot-ID, Attic-Katalog und Ship-Format aendern sich dadurch nicht.

Phase 05 des L65M-Preflights verwendet einen 4096-Bucket-/512-B-Hashfilter,
120-B-Blockreads und bei Hashgleichheit immer den exakten, NUL-begrenzten
Namensvergleich. Das Verdikt-Gate vergleicht 90.090 gueltige, beschaedigte und
abgeschnittene Szenarien ohne Abweichung; 56 Bulkread-Fixtures decken unter
anderem die konstruierte Hashkollision und Block-/Segmentgrenzen ab. Phase 05
verbraucht 1016 von 1500 projektierten Scratch-DMAs, der gesamte Preflight
13.968 von 15.000. Die MOS-Slice ist mit 1792/1792 B voll und besitzt keinen
lokalen Wachstumspuffer.

Der Commit ist phasenmajor: sieben geladene Slices ersetzen 5145 einzelne
Slice-Loads. Ingress- und Egress-CRC bleiben erhalten; ein IDE-Commit benoetigt
damit 42 statt 30.870 CRC-Laeufe. Die permanenten Ops-Gates pinnen 11.620 von
15.000 Source-Reads, 31.250 von 40.000 Preflight-Symbol-DMAs und 222.818 von
250.000 Commit-Namepool-DMAs. ABI v3 ist 47 B gross, der Transport besitzt den
einzigen 16-Bit-Repeat-Backstop. Vor der ersten Directory-Publikation rollt
`%lit-keep` bei OOM/Abort exakt auf den Checkpoint zurueck; Bank-5-Reservation,
Intern-/Namepool-Wachstum und bereits publizierte Entries bleiben bewusst
append-only beziehungsweise fail-stop. Der verworfene iterative Materializer benoetigte schon
als Helfer 1899 B und passte nicht in eine 1792-B-Slice. Deshalb bleibt die
Rekursion gebunden; der globale L65M-Vertrag ist auf Tiefe 9 gepinnt. Der
groesste gemessene Frame belegt damit 486 von 512 B. Tiefe 9 wird vollstaendig
committed, Tiefe 10 fail-closed als `L65M_ERR_GRAPH` abgelehnt.

Das gemeinsame Batch-Predicate bleibt derselbe achte Insel-Koordinator. Fuer
das MOS-Produkt ist sein ABI-/Slot-/Phase-/Busy-/Transportcheck als 73-B-
45GS02-Funktion implementiert; die lesbare C-Oracle treibt die Host-Mutationen.
Cookie-Drift wird beim unmittelbar folgenden `commit_enter`/`phase_enter` vor
jeder Slice-Arbeit abgewiesen. Das Commit-Ops-Gate auditiert die
Assemblerstruktur mit neun Mutationen, waehrend das Inselinventar exakt acht
Koordinatoren und 1108 B pinnt. Slot 37 belegt damit 1369/1396 B.

Das kanonische Guard-Produkt linkt mit Overlay-Basis `$c344`, 1851 B Boot-Gap
und 1811 B Post-Boot-Reserve. Damit sind das harte 1024-B-Minimum und das
1536-B-Komfortziel erfuellt. HW-Math hat seine 519 B bereits beigetragen und
ist keine kuenftige Reserve. Die 385 B Primitivnamen liegen bereits in
`.lisp65_boot.names`; ein weiterer Transfer bringt dem residenten Floor exakt
0 B. AP4 ist damit strukturell abgeschlossen und das Layout eingefroren. Neue
Slots, Inselbelegung oder VMA-Aenderungen brauchen eine neue Scope-Entscheidung.
Die verbleibende Abnahme ist Live-G5: verifizierte PRG-/Bank-5-/Attic-Readbacks,
Reset, Remount, echter `load-lib "ide"` innerhalb des 12-s-Budgets und exaktes
REPL-Ergebnis. Erst danach wechselt der Arbeitsfokus zu M4/AP6.

## 2026-07-11: AP4 ist nach sauberer Ship-v5-Promotion und Live-G5 geschlossen

Commit `5ce25a2b26ac1be03bd0a1ab1718329bb0c005bc` wurde in einem sauberen,
isolierten Worktree mit `make mvp-ship` gebaut und strikt nach `build/ship/`
promotet. Das unveraenderliche Manifest im Format
`lisp65-workbench-ship-v5` hat SHA-256
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd` und den
ehrlichen Status `g2-verified-candidate`. Die nachfolgende Hardwareabnahme
aendert diesen Manifeststatus nicht, sondern erzeugt einen separaten, an genau
diesen SHA gebundenen Live-G5-Nachweis.

Stage A las PRG-Payload, Bank-5-Preload und Attic-Katalog vor Ausfuehrung
bytegenau zurueck: PRG-Payload 39669 B,
`fe1edb7df21023236006777a8e835bf2e63530eab3ee21674184af1bf2a15ed6`, CRC
`e5a3`; Bank 5 35987 B,
`d97552f8949f6764a7e6ab2a1c5c51ed75386a65815ddf12a29cbbf6c568bf3f`, CRC
`d47c`; Attic 54105 B,
`55f1a6ad3cc15e51223db28fddf1f864908eec61fcf167c20bd301ca9cf5967e`, CRC
`b972`. Nach Reset und Remount blieb das Attic-Image exakt. Die installierte
1108-B-Insel bestand mit SHA-256
`b17c4e5282f04c56d5832930bd25dcf496a5f88ad39295a9132dde9995e61429` und CRC
`aa0c`. Der echte
`load-lib "ide"`-Preflight lieferte `overlay-ide-ok` nach 10 s bei einem
12-s-Budget. Guard-, VM-Bridge-, GC-, Reader-Recovery-, UX-, BAM- und M2-M7-
Persistenzziele bestanden mit demselben verifizierten Paket. Einzelne
transiente Eingabe-/Ethernetfehler wurden vom Harness erkannt und die
betroffenen Ziele vollstaendig wiederholt; sie wurden nicht als Produktpass
umgedeutet.

Commit `a5762e8` verlangt danach in vier Persistenz-Harnesses vor RETURN eine
verifizierte Eingabe. Er aendert weder Produktbytes noch den promoteten
Manifest-Pin. Mit Clean-Tree-G2, G4-Dry-run, verified-only Live-G5, 1811 B
Post-Boot-Reserve und 38/64 Slots ist AP4 formal beendet. Insel, Slots und VMA
bleiben eingefroren; jede weitere Layoutaenderung erfordert eine neue Scope-
Entscheidung. Der aktive Arbeitsfokus wechselt zu M4/AP6-Persistenz.

## 2026-07-11: IDE-Kapazitaet wird vor AP6 durch Core/IDEX und private Helfer geschaffen

Die IDE wird ohne Runtime-, Bytecode-ABI- oder AP4-Layoutaenderung in den
Pflichtkern `IDE` und den optionalen Komfort-Tier `IDEX` geteilt. `%ide-x` ist
die einzige physische Ueberlappung und wird beim IDEX-Load ueber die bestehende
symbolische Funktionszelle ersetzt. 40 interne Helfer werden ausschliesslich im
Artefaktbuild privat inline kompiliert und sind keine dynamische REPL-API mehr.

Der verworfene Zwischenstand mit 42 Helfern sprengte durch 32 Literale in
`%ide-cmd-action` den unveraenderten 56-B-Codepuffer. Die abgenommene Allowlist
haelt den schlechtesten Eintrag bei exakt 23 Literalen beziehungsweise 56/56 B
und schliesst die restliche Namepool-Luecke durch drei gekuerzte interne
Dispatchernamen. Kein residenter Cap wurde vergroessert.

Der Produktstand ist `IDE=152`, `IDEX=29`; die sequenzielle Suite besteht 124
Faelle. Mit der ausdruecklich ungemessenen AP6-Planungsobergrenze
`planning-envelope-v1` projiziert der Oracle 544/552
Directory-Slots, 705/720 Symbole und 9401/9536 Namepool-Bytes. AP4 bleibt bei
38/64 Slots, `$c344` und 1811 B Reserve eingefroren. Details und Gates stehen in
`docs/ide-capacity-remediation-2026-07-11.md`. Der naechste Arbeitsblock ist
AP6-Vertrag und -Implementierung; deren Produktfreigabe verlangt ein
`measured-manifest-v1` statt dieser Planungswerte.

## 2026-07-11: AP6 ersetzt den `tmp`-Pfad durch einen separaten M65D-COW-Kern

Der historische `tmp`-Rename ist aus IDE und Produkt-D81 entfernt. `M65D` ist
eine eigene on-demand Disk-Lib und bietet `m65d-save` als Upsert,
`m65d-save-new` als Create-only sowie `m65d-status` und `m65d-remount`.
`save-buffer-to` laedt M65D beim ersten Save automatisch; Create und Replace
verwenden denselben Copy-on-write-Pfad. Dadurch bleibt der IDE-Pflichtkern
klein und die Persistenztransaktion ist auch ausserhalb der Editor-UI nutzbar.

Der normative Vertrag pinnt 1..8192 B, die komplette vorhandene
Directory-Kette ohne Wachstum, eine neue Kette innerhalb genau einer
BAM-Haelfte und die Reihenfolge Daten+Verify, ein Claim-BAM-Sektor,
Directory-Commit, danach Freigabe der alten Kette. Vor dem Commit darf kein
neuer oder unvollstaendiger Eintrag sichtbar sein. Nach dem Commit darf bei
fehlgeschlagener Freigabe nur die alte Kette leaken. Es gibt keinen
Rollback- oder Power-Loss-Atomizitaetsanspruch zwischen physischen
Sektoroperationen. Nach unsicherem Write bleibt der Mutationspfad bis Reset
oder erfolgreichem Remount gelatcht.

Die stabile Status-ABI umfasst exakt zehn Codes 0..9: `ok`, `bad-name`,
`duplicate`, `too-large`, `no-space`, `directory-full`, `read-invalid`,
`write-verify-failed`, `needs-remount`, `committed-with-leak`. Der Vertrag und
die Zuordnung sind in `config/persistence-contract.json` maschinell gegatet.
Der unabhaengige D81-Oracle prueft 16 Szenarien an 82 Abbruchpunkten und lehnt
drei absichtliche Sicherheitsverletzungen ab.

M65D misst 35 Laufzeitfunktionen, 3857 B Code und 6719 B Image. Relativ zum
IDE-Core kommen 37 Symbole und 623 B Namepool hinzu. Die konservative
Gesamtprojektion bleibt bei 544/552 Directory, 693/720 Symbolen und
9223/9536 Namepool; der exakte kumulative Loaderreport misst 683 Symbole und
9110 B Namepool. AP4 bleibt unveraendert bei 38/64 Slots und 1811 B
Post-Boot-Reserve. Die weitergehende Zielspanne 24..28 Funktionen wurde nicht
durch Entfernen von BAM-, Directory-, Duplicate-, Latch- oder Remount-Checks
erzwungen.

G5 ist um den echten Nutzerpfad erweitert: zwei Creates, Readback, Replace,
Remount, anschliessend PRG-Reset mit derselben remote Wegwerf-D81 ohne Reupload
und erneuter Source-Load mit exaktem Ergebnis. Dieser Lauf ist gruen; der
vollstaendige Receipt steht im nachfolgenden AP6-Abschlussentscheid.

Der Abschlussreview haertet den Vertrag zusaetzlich: `m65d` ist eine
geschuetzte Systemdatei, Directory-Read-/Recheck-Fehler nach dem BAM-Claim
liefern Status 6 mit Latch, und Remount validiert neben beiden BAM-Haelften und
der Linkkette auch Typ, Startadresse und Blockzahl aller belegten Eintraege.
Eine globale Crosslink-/Sektor-Ownership-Pruefung zwischen verschiedenen
Dateien bleibt ausdruecklich nicht behauptet; AP6 ist ein Writervertrag fuer
ein zuvor konsistentes, exklusiv gemountetes D81, kein Dateisystem-Reparaturtool.

## 2026-07-11: AP6 ist nach Copy-on-write-, Reset- und HW-Abnahme geschlossen

Der produktive AP6-Pfad ist kein Prototyp-Allocator mehr. `M65D` schreibt neue
und bestehende Source-Dateien mit demselben Copy-on-write-Protokoll, verifiziert
jeden neuen Datensektor vor dem BAM-Claim und veroeffentlicht erst danach den
Directory-Eintrag. Der Host-Fault-Oracle prueft 16 Szenarien an 82 logischen
Schreibabbruechen. Name-, Groessen-, BAM-, Directory-, Status- und Latch-
Vertraege sind in G0-G2 maschinell gepinnt.

Der Hardwarelauf gegen das strikt verifizierte Ship-v5-Paket aus Commit
`f64bb41` und Manifest-SHA-256
`7d9873915e90102824fad7b379c938f8724d7b9f47770cab4adc5e48544ccb94`
bestand mit `ap6src` und `z6src` zwei unabhaengige Create-Vorgaenge in derselben
Session, exakten Readback, Replace, `m65d-remount`, Reset ohne D81-Reupload und
erneuten Load beider Dateien. Das Ergebnis nach Reset war
`(("(defun ap6-persisted () 612)") 612 ("(defun ap6-b () 613)") 613)`.
Der zuvor bei `directory-open` auftretende OOM ist durch zeilenweises Source-
Streaming beseitigt. Die destruktiven M2-M7-Proben bestanden auf Wegwerf-D81s
mit hostseitigem Byte-Diff und anschliessendem Workbench-Load-/Run-Oracle; M7
lieferte fuer die variable Dreisektorkette abschliessend `907`.

Der saubere G2-Abschlussbuild misst `M65D` mit 35 Funktionen, 3857 B Code und
6719 B Image. Fuer Resident + IDE + M65D + IDEX endet die konservative
Projektion bei 544/552 Directory-Slots, 693/720 Symbolen und 9223/9536
Namepool-Bytes. AP4 bleibt bei 38/64 Slots und 1811 B Post-Boot-Reserve
eingefroren. Nicht Teil von AP6 sind Directory-Wachstum, globale Crosslink-/
Sektor-Ownership-Reparatur und Power-Loss-Atomizitaet zwischen physischen
Sektorwrites. Der Arbeitsfokus wechselt damit zu AP5.3/AP5.4 und anschliessend
AP7.

## 2026-07-11: AP5 pinnt Hostsemantik breit, Produktclaims bleiben separat

Die historische Phase-1-Eval-Fixture wird nicht zum heutigen Sprachvertrag
umetikettiert. `eval-surface-v1` ist eine neue, kleine gemeinsame Fixture fuer
Python-P0, nativen C-Treewalk, nativen C-Compiler/VM und Lisp-`lcc`. Sie pinnt
17 Cases/22 Formen. Globale Wertzellen und `&rest` bleiben bewusst in den
breiteren engine-spezifischen Gates: Die vier Engines besitzen dafuer heute
keine identische oeffentliche Route. Engine-spezifische Transformationen im
gemeinsamen Runner wurden deshalb verworfen.

Der Bytecodevertrag verlangt nun auch den nativen C-Compiler und Lisp-`lcc`.
Beide bestehen 23 positive Golden-Vektoren und den negativen Rel8-Fall. Der
neue C-Adapter deckte einen echten Drift auf: `bc_compile_defun` emittierte im
Tail-`if` einen ueberfluessigen Sprung. Der Defun-Produktpfad folgt jetzt dem
bereits gepinnten Python-/LCC-Codegen; Golden-Daten wurden nicht angepasst.
Die sechs Disk-CALLPRIM-Faelle ohne nativen VM-Diskstub sind nicht mehr durch
ein stilles Boolean verborgen, sondern als begruendete Adapter-Omissions
sichtbar. LCC kennt jetzt auch CALLPRIM 21/22, ohne neuen Directory-Eintrag.

`allow_omitted_*` ist ein exakter `{name, reason}`-Vertrag. Unbekannte,
duplizierte, wieder aufgenommene, falsch klassifizierte und geerbte stale
Eintraege brechen `check-source`; 20 final aufgeloeste Suiten werden geprueft.
Sieben stale Vorkommen wurden entfernt. Das Artefaktmanifest traegt die
aufgeloesten Namen, Gruende und Zaehler.

Diese Entscheidung erhebt weiterhin keinen Workbench-Produktclaim. G2 bleibt
mit `reason=no-product-claims` sichtbar `SKIP`, bis der enge Build-Surface-/
Binding-Adapter separat architektonisch freigegeben ist. Ein Host-Gate wird
nicht als Ersatz fuer echte 45GS02-Ausfuehrung dargestellt. Der Produktlink
bleibt bei 38/64 Slots und erreicht 1813 B Post-Boot-Reserve. Die konservative
AP6+IDEX-Projektion endet nach den zwei neuen LCC-Symbolreferenzen bei 544/552
Directory-Slots, 695/720 Symbolen und 9253/9536 Namepool-Bytes.

## 2026-07-11: G2 pinnt Workbench-Eval-Surface, nicht Live-Semantik

Der separat freigegebene Vertrag `workbench-eval-surface-v1` hat den Typ
`surface` und erhebt einen engen Produktclaim: Der ausgelieferte Workbench-
Build bindet den internen Einstieg an `TREEWALK_STRIP -> lcc-run -> P0-VM`.
Der bestehende Behavior-Vertrag `eval-surface-v1` bleibt hostseitig; seine 17
Cases werden durch diesen G2-Adapter nicht als auf dem 45GS02 ausgefuehrt
dargestellt. Die Live-Verhaltensabnahme bleibt deshalb ein expliziter G5-Gap.

Ship-v5 wird nicht erweitert. Stattdessen bindet das bereits ausgelieferte und
mehrfach gehashte `resolved-profile.txt` Contract-Format, Fixture-Pfad und
-SHA, Route sowie die verbotenen oeffentlichen Funktionen. Registry, Fixture
und beide Runner sind zusaetzliche `input_sha256`-Pins. Der Adapter verifiziert
den Ship-v5-Kandidaten, die P0-Stdlib-Eintraege sowie SHA-256 und Symbolsatz des
finalen ELF:
interner `eval`-Router, LCC-Installer und VM muessen vorhanden sein;
`eval_env`, `eval_string` und deren Bootnamen muessen fehlen.

`semantic-contracts-g2` baut nun explizit `mvp-ship-candidate-artifacts`, damit
ein direkter Aufruf keinen alten Kandidaten konsumieren kann. Die Aenderung
fuehrt kein Runtime-Verhalten, keine ABI und kein Layout ein. Der Abschlusslink
bleibt bei 38/64 Slots und 1811 B Post-Boot-Reserve. AP5 und M2 sind damit
abgeschlossen; als naechster Sanierungsblock folgt AP7.

## 2026-07-11: AP7 trennt Workbench, Runtime Export und Release fail-closed

Die Workbench bleibt das einzige interaktive Produkt. Ihr neuer
maschinenlesbarer Vertrag pinnt REPL, Editor, lcc Compile/Install,
Source-Load/Save, Compile/Load-Lib und Fehlererholung; `ide` und `m65d` bleiben
on demand, `idex` optional. `workbench-deploy[-dry-run]` akzeptiert nur das
zuvor strikt verifizierte Ship-v5-Paket aus `build/ship/` und baut weder einen
Candidate noch eine destruktive Testmatrix im Hintergrund.

Runtime Export v1 folgt der freigegebenen Variante aus versiegeltem L65M-Modul,
build-gebundenem Bank-5-Preload und resetfestem Inline-Boot-Overlay. Das
Candidate-Paket umfasst exakt sieben Dateien und bindet Profil-SHA/Build-ID,
Entry/Arity, Capabilities, Abhaengigkeiten, PRG, L65M sowie Preload-Adresse,
Laenge, SHA und CRC16. Packer und Offline-Verifier pruefen identischen Codeblob
und Entry-Satz zwischen L65M und Preload. Der G2-Kandidat misst 25248 B PRG,
19809 B Boot-Gap und 15132 B Post-Boot-Reserve; Native-Host-Smoke und ein
zweiter byteidentischer Paketbuild sind Teil des Abschlussgates. Die
Provenienz bleibt ehrlich `host-p0-generator`; Workbench-Emitter, G4-Deploy und
G5-Cold-Boot sind offene Gaps und verhindern einen Releaseclaim.

Der historische Prelude/F011-Release schreibt nur noch nach
`build/legacy-interim-ship/` und `build/release/legacy-interim/`. Die
generischen Targets `release`, `ship-check` und `ship-release` brechen mit
Exitcode 2 ab, solange G3-G5-Evidenz und ein aktueller G6-Vertrag fehlen. Ein
maschinenlesbarer Index klassifiziert alle getrackten Markdown-Dokumente und
blockiert Drift. `project-status.md` enthaelt nur noch Source/G2, letzte
manifestgebundene G5-Evidenz, Releasezustand, Gaps und Queue; Messwerte bleiben
in generierten Reports.

AP7 und M5 sind damit als Produktschnitt abgeschlossen, nicht als Release.
Oeffentliche Sprach- oder ABI-Aenderungen aus dem Dialektentwurf bleiben ein
separater AP8-Semantik-/Migrationsblock nach M5.

## 2026-07-11: AP8.0 friert Dialekt-v1 ein und trennt mod von remainder

Der aktuelle Dialekt wird ab jetzt entlang zweier unabhaengiger Achsen
klassifiziert: Rolle (`core`, `workbench`, `library`, `internal`, `removed`)
und Auslieferung (`bank0-native`, `bank5-preload`, `disk-on-demand`,
`build-only`). `config/dialect-contract.json` bindet sechs reale Surfaces an
ihre Source-Suiten und Deskriptoren. Das G0-Gate pinnt 267 oeffentliche, 335
interne und 52 private-inline Namen. Vorschlaege veraendern die aktuelle
Surface nicht; Dialekt-v1 erlaubt keine Entfernung oeffentlicher Namen.

Die bisherige Gleichsetzung von `mod` und `remainder` war semantisch falsch.
`remainder` behaelt Opcode 24 und den truncierenden C-Rest mit Vorzeichen des
Dividenden. `mod` folgt der Common-Lisp-Semantik mit Vorzeichen des Divisors
und belegt den zuvor in P0 ungueltigen Arithmetikslot 17. Kein vorhandener
Opcode und keine Prim-ID wurde umnummeriert; historische `PRINTBOOL`-Objekte
waren nie P0-kompatibel. Nullteiler liefern in Treewalk, Python-P0,
C-Compiler/VM und Lisp-`lcc` ein kontrolliertes Fehlerresultat. Der gemeinsame
Eval-Vertrag prueft direkte negative Operanden, beide Divisorvorzeichen,
Funktionsdesignatoren und Nullteiler in allen vier Engines.

Der `TREEWALK_STRIP`-Produktbuild installiert `mod` und `remainder` zusaetzlich
als zwei kleine Bank-5-Bytecode-Bridges. Direkte Aufrufe bleiben einzelne
Opcodes; erstklassige Funktionsdesignatoren erreichen dieselbe Semantik ueber
die bestehende Funktionszelle, ohne die residente Treewalk-Implementierung
zurueckzuholen. Der dadurch sichtbar gewordene 8er-Alignment-Cliff wird mit
einer eng begrenzten Workbench-Kapazitaetserhoehung von 552 auf 560 Eintraege
beantwortet; Reserve-Gates und andere Profile bleiben unveraendert. Die
konservative AP6+IDEX-Projektion bleibt mit 552/560
Directory-Slots, 695/720 Symbolen und 9253/9536 Namepool-Bytes innerhalb aller
Gates. Der Abschlusslink bleibt bei 38/64 Runtime-Slots und 1800 B
Post-Boot-Reserve; die Kapazitaetserhoehung kostet gemessen 10 B Bank-0-BSS.

Directory-only-Helfer und globale Symbolrueckgewinnung sind nicht Bestandteil
dieses Schritts. Erstere brauchen eine eigene direkte Call-/Relocation-Semantik;
letztere ist ohne Unload wegen erstklassiger Symbolindizes unsicher. Der
naechste AP8-Block schliesst deshalb zuerst `every`/`some` im aktuellen,
verified-only Workbench-G5-Harness. Ein Host-Pass oder der historische
Minimal-Diagnoselink gelten dafuer ausdruecklich nicht als Produktbeweis.

## 2026-07-11: AP8.1 schliesst die zwei Higher-Order-Repros mit engem G5-Receipt

Die zwei registrierten HW-Haenger fuer `every` und `some` sind im aktuellen
verified-only Workbench-Produktpfad nicht mehr reproduzierbar. Das saubere
Ship-v5 aus Commit `78083d6b79df189e97c617577f7b89d62d4a3219` ist an
Manifest-SHA-256
`275723fb7259261c9606cee6a0dcc17c593a4cbf9c77f44b482d7cd031d5e211`
gebunden. Nach Persistence-Remount lief die Reihenfolge `every` -> `some`,
nach dem langen IDE+IDEX-Such-/Repeat-Zustand die Gegenreihenfolge
`some` -> `every`; die Resultate waren exakt `t`, `3`, `3`, `t` mit leerem
Folgeprompt.

Der JTAG-Transport ersetzt die urspruengliche Apostroph-Source nicht durch
`quote`. Er materialisiert das Apostroph ueber Zeichencode 39 in einer
Source-Datei und laedt diese in jedem Zustand zweimal. Damit durchlaeuft der
Reader die exakte registrierte Source und nicht eine allokationsverschiedene
Ersatzform. Das abschliessende `x` beobachtet das fachliche Resultat der
zweiten Ausfuehrung; die zwei erfolgreichen `load`-Rueckgaben belegen das
Terminieren beider Laeufe, nicht zwei separat gespeicherte Einzelverdikte.

Der eingecheckte Receipt unter
`tests/bytecode/runtime/evidence/ap8.1-g5-78083d6/receipt.json` ist absichtlich
auf `ap8.1-higher-order` begrenzt. Er bindet sauberen Commit und Tree,
verifiziertes Manifest, Live-Memory-Receipt, Stage-/Post-Reset-Readbacks sowie
alle vier Forms-/Screen-Paare per SHA-256. Das Registry-v2-Gate wiederholt den
Screen-Oracle und lehnt fehlende, manipulierte, verwaiste oder per Symlink
ersetzte Evidenz fail-closed ab. Der Aggregate traf nach dem bereits gruenen
UX-Block auf einen Etherload-No-response. Der enge Receipt attestiert die
nachfolgenden Komponenten nicht; ein ununterbrochener Exit-0-Gesamtlauf oder
ein allgemeiner Release-G5 wird nicht behauptet.

Die Registry markiert damit `active=0`, `resolved-g5=2`. Das ist ein
produktgebundener Regressionsabschluss des historischen Hang-Scope, kein
Nachweis einer identifizierten Root Cause und kein Ersatz fuer den weiterhin
offenen allgemeinen AP5.3-Live-Eval-Vertrag. AP8.2 ist der naechste Block;
AP4-Layout, Slots und Kapazitaeten bleiben unveraendert.

## 2026-07-11: AP8.2 trennt extern gestagtes Runtime-Appliance und Standalone-Boot

Der aktuelle Runtime Export bleibt ein **extern gestagtes Appliance-Profil**.
Nach jedem Power-Cycle verifiziert und schreibt der Host den profilgebundenen
Bank-5-Preload und startet das Runtime-PRG. Das Inline-Boot-Overlay liegt im
PRG; Attic, D81, SD-Upload und Runtime-Diskloader gehoeren nicht zu diesem
Profil. Ein Reset darf Bank 5 erhalten, ein Power-Cycle nicht. Der G5-Vertrag
muss deshalb einen echten Kaltstart bezeugen und danach neu stagen; er darf
Reset-Stabilitaet nicht als Power-Festigkeit ausgeben.

Ein autonomer Start ist ein eigener, benannter Architekturblock **Runtime
Export Standalone Boot**. Er umfasst mindestens einen D81/SD-Loader, einen
fail-closed Recovery-Pfad fuer fehlende oder korrupte power-volatile Preloads
und einen geaenderten Capability-/Manifestvertrag. Erst dieser Block darf
`runtime_disk_loader=true` oder einen Start ohne externes Bank-5-Staging
behaupten. Er wird nicht als Harnessdetail in AP8.2 eingeschoben.

Die Runtime-Anwendung ist durch die echte Workbench-`lcc`/FASL-Route in einen
reservierten Slot einer Wegwerf-D81 emittiert worden. Das kanonisch extrahierte
L65M-v1-Artefakt ist mit Source-, Ship-, D81- und Compilerinput-SHAs als
Workbench-Golden versiegelt. Eine zweite physische Workbench-Emission ist
unter einer anderen, derivationsgebundenen Capture-ID byteidentisch zu Golden
und abgeleitetem Bank-5-Payload. Derselbe Receipt, ein Hardlink oder dieselbe
Capture-ID darf nicht beide Rollen belegen. Der Python-P0-
Generator bleibt ein unabhaengiges Differential-Oracle und ist bewusst nicht
bytegleich: Er belegt seine eigene intern konsistente Rebase, ist aber weder
Golden-Autoritaet noch Ersatz fuer Workbench-Provenienz.

Der Bank-5-Preload erhaelt ausserhalb des unveraenderten L65M-v1-Payloads einen
kleinen build-gebundenen Trailer. Vor `vm_load_embedded_stdlib` prueft der
evaluatorfreie Runtime Core Trailer/Magic und Payload-Laenge, danach Build-ID
und zuletzt CRC16-CCITT-FALSE ueber das vollstaendige gebundene Preload aus
Payload und Trailer. Truncation, fremde
Build-ID und Bitflip besitzen getrennte Diagnosecodes; alle enden gleich
fail-closed mit `RUNTIME_PRELOAD_ERROR=$e4`, `NIL` als Resultat und ohne
Entry-Ausfuehrung.

Runtime-Export-Ship und -Contract liegen als v2 vor. Das Manifest bindet Profil
und Build-ID, den vollstaendigen Preload samt Payload-/Trailergrenze, Adresse,
Laengen, Whole-image-CRC/SHA und Payload-CRC/SHA. Das symbolische
Hardware-Oracle wird aus dem exakten ELF gewonnen und pinnt
`lisp65_runtime_state`, `lisp65_runtime_result` und
`lisp65_runtime_preload_detail` samt Groesse, Encoding und erwarteten
Verdikten. Zusaetzlich traegt das PRG genau einen `L65P`-Binding-Record mit
Payload-Laenge, Whole-image-CRC und Build-ID. Ship-v2 liest diesen Record aus
den ausgelieferten PRG-Bytes und gleicht ihn gegen Profil und Preload ab; der
Runtime Core verwendet denselben Record volatil als Laufzeitquelle. Dadurch
haengt weder der Hardwaretest an handgeschriebenen Adressen noch die
Preload-Garantie an einem bloss selbstberichteten Manifestwert.

G4 ist abgeschlossen und bleibt ein rein lokaler, nicht-destruktiver Dry-run:
strikte Paket-/Oracle-Pruefung und exakter Kommandoplan, aber kein Toolstart,
kein Hardwarezugriff und kein D81-/SD-/Attic-Schritt. Der maschinelle Plan
traegt `offline=true` und `side_effects=false`; er kann nie G5-Evidenz werden.
Der volle `runtime-export-candidate-check` einschliesslich Host-Selftests,
Ship-v2-Verifier, zweitem Paketbuild, byteidentischem Sieben-Dateien-Diff und
G4 ist gruen.

Der echte Runtime-G5 besteht aus getrennten power-cycle-gebundenen Phasen:
sauberer Preload mit exaktem Ergebnis sowie Truncation, Payload-Bitflip und
fremde Build-ID mit jeweils exaktem Fehleroracle. Vor dem Staging muss der
Bank-5-Digest vom Soll abweichen; der Truncation-Fall leert den Zielspan, damit
kein alter Trailer ueberlebt. Full-span-Readbacks, State-/Result-Bytes,
Manifest-/Oracle-SHAs, Cycle-ID und Bediener-Attestierung werden atomar und
fail-closed quittiert.

## 2026-07-12: AP8.2 ist mit vierphasigem Runtime-G5 abgeschlossen

Der echte Runtime-G5 ist nach vier getrennten physischen Power-Cycles gruen.
`clean` lieferte exakt State `3`, Fixnum `42` und Detail `0`; `truncated`,
`bitflip` und `build-id-mismatch` lieferten jeweils State `$e4`, `NIL` und die
Detailcodes `1`, `3` und `2`. Alle Prestage-Digests unterschieden sich vom
kanonischen Ziel, alle Full-span-Readbacks entsprachen der geplanten Phase und
die vier Cycle-IDs sind verschieden.

Der selbststaendig wiederverifizierbare Evidenzsatz liegt unter
`tests/bytecode/runtime/evidence/ap8.2-g5-589844f/`. Er bindet den
Sieben-Dateien-Candidate mit Build-ID `0x13338ff0` und Manifest-SHA-256
`589844faff2d8674baf75f4e8faeef22ab4e7eef2d0db698c4a928c53461f6f6`,
das Oracle mit SHA-256
`e7db0887bab3f601793f2bcee6073518ccd626bfa2bf29e01c57f44336def3ba`
sowie das voll verifizierte Fremdprofil `0xbb562d37`. Der Suite-Verifier
rekonstruiert alle vier Receipts aus den archivierten Rohbytes.

Damit ist AP8.2 abgeschlossen. Die Evidenz gilt nur fuer das extern gestagte
Runtime-Appliance-Profil. Die bisherigen Workbench-G5-Receipts beweisen
weiterhin nur Reset/Remount innerhalb einer versorgten Session, keinen
Workbench-Kaltstart nach Power-Cycle. Dieser Workbench-Cold-Start-
Recoveryvertrag bleibt bis G6 offen und wird nicht aus Runtime-Export-Evidenz
abgeleitet. Ebenso bleibt Standalone-Boot mit D81/SD-Loader, Recovery und
Capabilityvertrag ein eigener Roadmap-Block.

## 2026-07-12: AP8.3 oeffnet Dialekt v2 als hart getrenntes Migrationsprofil

Dialekt v1 bleibt unveraendert als `frozen-evidence`-Profil am Commit
`f6527d25e2035eae5a98dae7431d641515e2fd2e` gebunden. Features und Backports
sind verboten; nur isolierte Reproduzierbarkeits-Rebuilds sind zulaessig. v1
wird erst archiviert, wenn v2 seine eigene vollstaendige G5-Umschaltmatrix
bestanden hat. Damit bleiben die AP8.1-/AP8.2-Evidenz und alte Artefakte an
einen lebenden, aber eingefrorenen Vertrag gebunden.

Dialekt v2 entsteht parallel und ohne Runtime-Kompatibilitaetsbibliothek oder
alte Runtime-Aliase. Migrationspolitik und Profilpromotion sind getrennte
Vertraege, damit die Promotion nicht den SHA der Politik veraendert, den ihr
Receipt beweist. Der aktive Selektor bleibt fail-closed auf v1. v2 kann nur
mit abgeschlossenem Familienpraefix, ohne blockierende oder semantisch offene
Entscheidungen, mit einem real aufgeloesten v2-Surface-Vertrag und mit externer
G5-Evidenz aktiv werden.

Die Klassifikation bindet 231 eindeutige oeffentliche v1-Namen aus 267
Surface-Eintraegen exakt einmal: 70 `keep`, 30 `move-library`, 85
`internalize`, 39 `replace`, 3 `redefine` und 4 `remove-v2`. `%`-Namen,
Descriptor-Nicht-Exporte und private Inlines besitzen getrennte interne
Regeln; ein neuer oeffentlicher Name ohne explizite Klassifikation macht G0
rot. `replace` ist ausschliesslich eine Quellmigration und erzeugt keinen
Runtime-Alias. Offene Semantikentscheidungen bleiben `pending` und blockieren
die spaetere Promotion.

Die Syntaxachse inventarisiert zusaetzlich 19 aus den Quellen abgeleitete
oeffentliche Makros disjunkt und vollstaendig. 18 bleiben in v2 oeffentlich;
`do` entfaellt. Dot-Reader-Syntax sowie feste, dotted, `&rest`- und
voll-variadische Lambda-Listen sind Teil des eingefrorenen v1-Snapshots.

Die Familienreihenfolge ist Prelude/Control, Lists, Strings, System/Runtime,
IDE. Jede Familie braucht normative Differentialvertraege, einen an Baseline-
und Candidate-Manifeste gebundenen Messreport sowie eine positive Symbol- und
Namepool-Bilanz. Boot- und geladener Arbeitsumfang werden getrennt gerechnet.
Die Familien-Receipts muessen jeden Fall ihres SHA-gebundenen Fixtures pro
Engine exakt einmal abdecken; Teilmengen koennen keine Migration abschliessen.
Strings haengen explizit am First-Class-Buffer-Block, die IDE-Internalisierung
an Directory-only/L65M-v2. Buffer liegt verbindlich vor `unload`; Export-only-
Interning/`require` liegt vor `unload` und hinter Directory-only/L65M-v2.

Der neue P0-ABI-Ledger partitioniert Opcode- und Prim-ID-Raum jeweils ueber
alle 256 Werte. Dialekt v1 ist durch einen Genesis-Hash statusgefroren. Aktive
IDs duerfen in einem Folgeprofil nur aktiv bleiben oder Tombstones werden;
Tombstones werden nie reaktiviert oder wiederverwendet und behalten Name und
Operandenformat fuer Decoder und Diagnose. Der Ledger bindet derzeit 36
aktive Opcodes und 23 aktive Prim-IDs an Markdown, Python-Decoder, C-VM,
Python-/C-Compiler und Device-LCC. Eine oeffentliche Namensentfernung aendert
den ABI-Status nicht automatisch; `REMAINDER`/24 und `EQL`/55 bleiben aktiv.

Die Profilumschaltung ist kein Buildflag. Der versionierte G5-Matrixvertrag
nennt vier Runtime-Export-Korruptions-/Erfolgsfaelle, sieben
Workbench-Persistenzziele und drei Workbench-UX-/Runtimeziele mit exakten
Erwartungen. Ein spaeteres Receipt muss Candidate-Manifest, Build-ID,
Migrations-/v2-/Matrix-SHAs, Familienreports und sichere physische Cycle-IDs
binden. Auch ein erfolgreicher v2-Switch waere ohne G6 keine Releasefreigabe.

## 2026-07-12: AP8.4 migriert Prelude/Control und bindet Arity ans Artefakt

Prelude/Control ist das erste abgeschlossene v2-Familienpraefix. `/=` ist
binaer; `defparameter` setzt bei jedem Laden, `defvar` nur bei ungebundenem
Symbol; `do` und der oeffentliche Name `remainder` entfallen. Opcode 24 bleibt
aktiv und dekodierbar. Das normative Fixture bindet 19 Faelle ueber Treewalk
und nativen Compiler/VM in beiden Profilen. Die 76 Beobachtungen sind gruen;
jede gewollte Abweichung traegt exakt eine aufgeloeste Decision-ID.

Das v1-Harness wird nicht aus dem Kandidaten mit einem Profil-Define gebaut,
sondern aus dem eingefrorenen Evidenz-Commit `f6527d25...` exportiert. Beide
Profilbinaries besitzen eigene Build-Receipts fuer Compiler, Defines,
Quellen/Header, Preloads, Binary-SHA und Buildprofil-SHA. Die vier Verdicts
binden diese Provenienz plus den je Engine kombinierten Prelude-SHA. Damit
beweist der Semantikadapter die nativen Engines und nicht nur das Fixture-
Schema.

`STRICT_ARITY` nutzt das bestehende CodeObject-Flagsbyte: Bit 0 bleibt REST,
Bit 1 aktiviert die Pruefung, Bits 2..7 kodieren die Anzahl optionaler
Parameter. Fest bedeutet exakt, optional bedeutet min..max, rest bedeutet
mindestens min. v1 ohne Flag behaelt sein historisches NIL-Padding. v1 und v2
sind getrennte Builds; v1 weist v2-Flags am Produktgate zurueck, v2 prueft am
Frame-Eintritt und erfasst dadurch auch `funcall` und `apply`. Das Source-
Lowering fuer `&optional` bleibt vertagt. Fehlercode 48 hat den nutzerlesbaren
Text `wrong argument count`.

Die gemessene Bilanz trifft die Projektion exakt: loaded `-16` Symbole und
`-108 B` Namepool, Boot `-21`/`-132 B`, Directory `-16`. Der erste ungegatete
Prototyp verschob den eingefrorenen Overlay-Floor ueber `$c356`; deshalb wurde
kein Layout geaendert, sondern der bereits beschlossene harte Profilschnitt
auch im Binary durchgesetzt. Der v1-Produktlink ist danach wieder gruen bei
38/64 Slots, 1836 B Post-Boot-Reserve und 1894 B Boot-Stack-Gap.

Die Budgetevidenz wird aus gebauten L65M-Profilimages rekonstruiert, nicht aus
der Klassifikationsliste: v1 bindet 13223 B, v2 10710 B (`-2513 B`). Das harte
v2-Profil verlangt `STRICT_ARITY` am Loader- und VM-Gate; flagloser v1-Code
bleibt dekodierbar, ist dort aber kein lax ausfuehrbares Kompatibilitaetsprofil.
Ein eigenes LCC-Differential mit 14 Beobachtungen schliesst die zuvor offene
Device-Compiler-Surface fuer `do`/`do*`/`remainder`.

## 2026-07-12: AP8.5 bearbeitet Listenmigration, native Mutation und Expansion

AP8.5 migriert den vorhandenen Listenbestand plus `filter`; die neuen
Komfortnamen `putf`, `adjoin`, `union`, `complement` und `sort` bleiben im
eigenen Block `lists-v2-expansion`. Bis dahin verwenden Migrationshinweise das
direkte Lambda-Idiom und behaupten keinen vorhandenen `complement`-Export.

Die gemeinsame Workbench-/Runtime-Core-Surface fuer `nreverse`, `rplaca` und
`rplacd` wird vertagt. Der isolierte Prototyp mit CALLPRIM 24/25 und einem
Bytecode-Core-`nreverse` endete bei Workbench-VMA `$c46a` und verfehlte die
eingefrorene `$c356`-Grenze um 276 B; eine zulaessige layout-neutrale
Konsolidierung brachte keinen Gewinn. Da diese Identitaeten nie ausgeliefert
wurden, bleiben die Prim-IDs 23--255 unallokiert statt als Tombstones im
Vertrag. AP8.5 behaelt ausschliesslich die lokale v2-Treewalk-Arity fuer
`nreverse`/`rplaca`/`rplacd` bei 1/2/2; VM-/Bytecode-Semantik folgt erst in
einem eigenen Kapazitaetsblock. AP4 und das Speicherlayout bleiben
eingefroren.

Familiengewinn und Compilerinfrastruktur werden getrennt verbucht. Die
einmaligen Kosten des v2-LCC-Profils duerfen weder der Listenfamilie noch jeder
folgenden Familie erneut belastet werden. Ein maschinengepruefter kumulativer
Report fuehrt deshalb Familien-, Infrastruktur- und Nettolinie separat gegen
die historische Paragraf-8-Projektion. Der erste Ledger misst Lists allein mit
`-18` Directory, `-103 B` rohen Namensdaten, `-273 B` Code und `-929 B` EXT;
die einmalige LCC-Infrastruktur mit `+18`, `+356 B`, `+689 B` und `+1941 B`.
Damit steht die deployte Nettolinie vor weiteren Familien ehrlich bei `0`,
`+253 B`, `+416 B` und `+1012 B`. Nicht deployte Blockkosten werden nicht
eingerechnet.

AP8.5 hat daraus einen dauerhaften Ablauf abgeleitet: isolierter v2-Produktlink
vor finaler Familien-Evidence, nicht erst danach. Der erste Listenlink wurde
bei `$c4da` gegen die gepinnte Grenze `$c356` abgewiesen. Auch der genau einmal
zugelassene, layout-neutrale Prototyp mit Bytecode-`nreverse` und zwei nativen
Settern scheiterte bei `$c46a`: 276 B VMA-Defizit und nur 1518 B hypothetische
Post-Boot-Reserve statt des 1536-B-Ziels. Es folgt keine zweite Byte-Diaet.

Lists bleibt deshalb `in-progress` und bindet den maschinenlesbaren Block
`config/v2-native-list-primitives-block.json`. Die lokale Treewalk-Arity 1/2/2
schliesst die Korrektheitsluecke; die portable Vereinheitlichung wartet auf ein
gemeinsames Lists-/Strings-Kapazitaetsbudget. Die vermeintliche letzte
Primitivnamen-Reserve ist bereits verbraucht: `.lisp65_boot.names` liegt bei
`$c741` mit `$17d` beziehungsweise 381 B im Boot-Overlay und bietet durch eine
weitere Verlagerung 0 residente Bytes. Als struktureller Folgepfad bleibt nach
der lesenden Strings-Analyse nur ein gemeinsam begruendeter Bedarf und danach
gegebenenfalls ein neu freizugebender Colour-RAM-/Attic-Rebalance. Insel,
VMA-Grenze und Slotlayout bleiben unveraendert eingefroren.

## 2026-07-12: Der v2-LCC-Parameterfehler ist ein gebundener Service

Die Workbench-Serviceklassifikation waechst von 29 auf 30 Ziele. Der neue,
nur im v2-Staging vorhandene Eintrag `%lcc-error-invalid-parameter-list` ist
ein intentionaler Error-Service, kein oeffentlicher Funktionsname. Prim-ID 56
bindet ihn an den stabilen Fehlercode 59. Der normative Fall mit doppeltem
`&optional` verlangt in Treewalk, Compiler-VM, Python-P0 und Lisp-LCC exakt
`!error:code=59:symbol=%lcc-error-invalid-parameter-list`; ein anderer
Sentinel oder ein unspezifischer Runtime-/Undefined-Fehler ist kein Ersatz.
Alle vier Engines belegen den vollstaendigen ungueltigen Parameterlistenpfad.
Der native C-Compiler-VM-Harness umgeht keine Grenze durch groessere
Equivalence-Puffer: Er laedt stattdessen das wirklich generierte residente
v2-LCC-Blob, materialisiert dessen Literalmetadaten und registriert 341
Directory-Eintraege. Manifest-, Blob- und Inventar-SHAs sind gebunden. Falsche
Manifest-SHA und Blob-Bitflip werden in den Mutationstests fail-closed
abgewiesen. Derselbe carrier-freie Harness pinnt die oeffentliche
`eval`-/`funcall`-/`apply`-Surface jeweils auf 42.

Der 33 Zeichen lange Sentinel legte zugleich eine Reader-Grenze offen:
`symbol.c` akzeptierte bereits 33 Zeichen, `read_atom` bislang nur 32. Der
einzige Vertragswechsel hebt deshalb den Tokenpuffer von 33 auf 34 Bytes an:
32 und 33 Zeichen werden gelesen, 34 bleiben ein vollstaendig konsumierter,
fail-closed `token-too-long`-Fehler. Isoliert mit `-Os -fno-lto` gemessen bleibt
das Reader-Objekt auf dem Host bei 2752 B Text und auf llvm-mos bei 5037 B Text
(jeweils Delta 0); `read_atom` bleibt hostseitig bei 80 B Stack und steigt auf
llvm-mos von 36 auf 37 B. Weitere Reader-Grenzen aendern sich nicht.

## 2026-07-12: CP4 schliesst Zero Miss und entfernt den C-Carrier

Das interne v2-Workbench-Set besteht weiterhin aus genau vier Artefakten. Der
mechanische 73-Aufrufe-Codemod ergibt 335 identische v1/v2-Beobachtungen. Nach
dem `eval`-Bytecodewrapper misst die Staging-Inventur 449 `CALLPRIM`s und 1791
Directory-Aufrufe; unaufgeloeste Sites, unaufgeloeste Ziele und Tombstone-
Aufrufe stehen jeweils bei null. Die 30 Zielklassen sind als 3 Listenprims,
16 Native-Services und 11 Error-Services gepinnt. Der freie Prim-ID-Bereich
beginnt deshalb explizit bei 57.

Erst dieser Nullstand aktiviert `LISP65_V2_CARRIER_CUT`. Sechs fehlende
Profilvoraussetzungen werden einzeln als Compile-Fehler getestet. Das reale
Cut-ELF enthaelt weder `apply`, `eval_vm_apply`, `eval_vm_bridge` noch die
beiden Treewalk-Hookdefinitionen; direkte VM-Aufrufe, beide indirekten
Designatoren, BCODE-Makroexpansion und DIRMISS bleiben gruen. Die Registry ist
weiter eine statische Branch-Inventur ohne Funktionszeiger-Hop.

Damit ist Checkpoint 4 geschlossen. Das Profil bleibt dennoch intern und am
Ship-Gate gesperrt. Die einzige Promotion darf erst CP5 nach realen
Workbench-/Runtime-Core-Differenzlinks, positiver Budgetabnahme und der vollen
G5-Hardwarematrix vornehmen. Es gab keine Layout-, Slot- oder Insel-Aenderung.

## 2026-07-12: CP5 Workbench-Link stoppt bei +3398 B residentem Floor

Der reale v1-Guard-Link bleibt mit `$c34e/$c350` und 1800 B Post-Boot-Reserve
gruen. Der identisch konfigurierte v2-Carrier-Cut erreicht dagegen
`bss_end=$d094`; damit liegt er 148 B ueber der physischen RAM-Grenze, 3392 B
ueber dem VMA-Limit und 3398 B ueber dem v1-Floor. CP5 und G5 bleiben gesperrt.

Ein neuer maschinenlesbarer Symboldiff trennt deshalb die harte LTO/ICF-
Produktmetrik von `-Oz -fno-lto`-Namensindikatoren. Fuer weitere Planung wird
nicht mit dem knappen 3399-B-Minimum, sondern pessimistisch mit 4096 B Reclaim
gerechnet. Ein Fehlschlag fuehrt ausschliesslich zur abgestimmten Auswahl aus
(a) Insel plus Slice-Cap als neue Layoutentscheidung, (b) De-Residentisierung
oder (c) Runtime-Core zuerst; keine dieser Optionen wird durch den Report
vorweggenommen.

## 2026-07-12: Layoutneutraler CP5-Einmalversuch endet bei 1051 B Reclaim

Der vorab vereinbarte Einmalversuch hat zwei korrekte Konsolidierungen ergeben:
Slice und Concat teilen eine atomare String-Transaktion; `apply`, `funcall` und
`vm_native_apply` teilen im Carrier-Cut einen array-basierten VM-Aufrufkern.
Alle fokussierten ASAN/UBSAN-, STRICT_ARITY-, Atomizitaets-, Carrier-Cut- und
MOS-Linktests bleiben gruen. Ein Tabellenumbau des Service-Dispatchers wurde
verworfen, weil er das reale MOS-Objekt um 61 B vergroesserte.

Der gemeinsame reale LTO/ICF-Link reduziert den residenten v2-vs-v1-Floor nur
von +3398 B auf +2347 B. Das sind 1051 B Reclaim und 2348 B weniger als das
harte 3399-B-Minimum. Das entspannte Diagnose-ELF endet bei `$cc77/$cc78`:
905 B physischer RAM-Headroom, aber 2338 B VMA-Ueberzug und nach 1450 B
Runtime-Stack -546 B Post-Boot-Reserve, also 2082 B unter dem 1536-B-Minimum.

Damit ist der lokale Code-Size-Unterblock geschlossen und darf nicht durch
weitere Varianten verlaengert werden. CP5, die G5-Promotion und jeder Ship-Pfad
bleiben gesperrt. Insel, Slice-Cap, Slots und VMA-Pins wurden nicht veraendert.
Der naechste Schritt verlangt Nutzerzustimmung fuer genau eine der gepinnten
Optionen: (a) Insel plus Slice-Cap, (b) De-Residentisierung oder (c)
Runtime-Core zuerst.

## 2026-07-12: Profil-Split sequenziert Evidenz, nicht Releases

Die freigegebene Strategie kombiniert zwei parallele Arbeitslinien:
Runtime-Core beweist den v2-Capability-Vertrag intern; die
Workbench-De-Residentierung bleibt der einzige Release-Pfad. Runtime-Core ist
strikt nicht shippbar, darf CP5 nicht abschliessen und darf keine weitere
Sprachfamilie oder einen AP8-Block freigeben. Dialekt v1 bleibt eingefrorene
Evidenz und wird nicht ausgeliefert. Release-Autoritaet besitzen ausschliesslich
der geschlossene Workbench-v2-Link und die volle Workbench-plus-Runtime-G5-
Matrix.

Die Layoutoption ist endgueltig verworfen. Ihr maximaler quantifizierter Gewinn
von rund 1302 B (932 B Insel plus etwa 370 B Slice-Cap) liegt unter beiden
verbleibenden Luecken: 2338 B VMA und 2082 B Reserve. Ein Bruch des AP4-Freeze,
der das Produkt weiterhin nicht linkt, ist keine zulaessige Zwischenloesung.

## 2026-07-12: Registry-Schliessung ist produktneutral, Services bleiben produktspezifisch

Der erste echte Runtime-Core-Cut-Link hat eine zu enge CP4-Voraussetzung
sichtbar gemacht: `LISP65_V2_CARRIER_CUT` verlangte konkret
`LISP65_V2_WORKBENCH_SERVICES`. Runtime-Core linkt absichtlich kein `eval.c`;
der dort definierte Workbench-Dispatcher fuehrte deshalb zu einem
unaufgeloesten `eval_v2_workbench_service`. Ihn oder einen Stub in Runtime-Core
zu ziehen waere eine falsche Servicebehauptung und wuerde Workbench-Sentinels
in das evaluatorfreie Produkt tragen.

Der Cut verlangt deshalb nun `LISP65_V2_SERVICE_REGISTRY_CLOSED`. Dieses Flag
ist ein Beweisergebnis, kein Dispatcher. Workbench setzt es zusammen mit ihrem
weiterhin getrennten Serviceflag nach dem 30-Ziel-Gate. Runtime-Core setzt es
nach einem eigenen Artefakt-Allowset: alle CodeObjects tragen `STRICT_ARITY`,
alle vier Directory-Aufrufe sind als `runtime-step` klassifiziert,
`CALLPRIM`s, Tombstones 1/2, Workbench-IDs 30--56, unaufgeloeste und
unklassifizierte Aufrufe stehen jeweils bei null. Der fokussierte Cut bleibt
auf Host und llvm-mos carrier-frei; `vm_native_apply` bleibt gelinkt.

## 2026-07-12: Der Kapazitaetsledger rechnet die vollstaendige v2-LCC-Profilinfrastruktur

Der CP4-LCC-Override hatte den maschinenlesbaren Ledger nicht neu aufgebaut;
dadurch standen dort noch die AP8.5-Infrastrukturwerte. Der Rebuild pinnt nun
das ABI-Profil fuer Compiler und Artefaktdecoder identisch. Nach der
Prim-34-Entsymbolisierung misst er gegen v1 `+21` Directory-Eintraege,
`+814 B` rohe Namensdaten, `+1065 B` Code und `+3087 B` EXT. Der Posten heisst
deshalb allgemein
`lcc-v2-profile-infrastructure`. Lists bleibt davon getrennt bei `-18`,
`-103 B`, `-273 B` und `-929 B`; die ehrliche Nettolinie lautet `+3`,
`+711 B`, `+792 B` und `+2158 B`. Produktcode und Layout aendern sich dadurch
nicht.

## 2026-07-12: `number->string` etabliert die De-Residentisierungsschablone

Der erste begrenzte Service-Prototyp verschiebt `number->string` aus dem
residenten v2-Dispatcher in ein oeffentliches 200-B-CodeObject in Bank 5. Der
Ziffernhelfer bleibt private-inline und erzeugt weder Symbol noch Directory-
Eintrag. Beide Compiler emittieren Directory-Aufrufe. Prim-ID 40 bleibt wegen
bereits erzeugter v2-Staging-Artefakte dauerhaft als `number->string`
dekodierbarer Tombstone reserviert; im eingefrorenen v1-Profil bleibt ID 40
reserviert und das native Verhalten unveraendert.

Ein sauberer Baseline-Worktree und der Kandidat teilen Commit `ca9cfb9`; der
relaxte Paarlink bindet Source-, Toolchain-, Flag-, Manifest- und ELF-SHAs. Er
gewinnt real 82 B am Heap-Floor und 80 B an der Overlay-VMA. Der Kandidat endet
bei `heap_start=$cc26`, `runtime_overlay_vma=$cc28` und -464 B Reserve. Damit
bleiben 2258 B VMA- und 2000 B Reservedefizit; der Prototyp ist ausdruecklich
nicht promotionsfaehig.

Die bestehende Tippmessung wurde ABI-profilgebunden gemacht. Ihr warmer Render-
nach-Insert-Pfad steigt von 4183 auf 4312 VM-Instruktionen (`+129`, 3,08
Prozent) und bleibt im 5-Prozent-Budget. Der `-16384`-Pfad wird ohne
verschachteltes Boot-Literal per `cons` aufgebaut und anschliessend atomar durch
den internen Stringkonstruktor publiziert; alle vier Engines beobachten
`"-16384"`. Das Muster ist als verbindliche
Schablone dokumentiert; nur weitere ABI-Tombstones verlangen Einzelzustimmung.

Der Prim-40-Tombstone vergroessert den separaten Runtime-Core-Proof um 26 B.
Sein reproduzierbarer Link misst nun 28644 B PRG, 25127 B resident und 11736 B
Post-Boot-Reserve. Das 8192-B-Hard-Minimum bleibt gruen; der sichtbare Abstand
zum 12288-B-Ziel waechst auf 552 B. Release- oder G5-Autoritaet entsteht daraus
weiterhin nicht.

## 2026-07-12: Prim 34 wird durch einen commit-last FASL-Writer ersetzt

Der v2-Workbench-Schreibpfad verwendet `%save-staged` nicht mehr als residenten
Native-Service. Prim-ID 34 bleibt dauerhaft unter diesem Namen dekodierbar,
ist im v2-Profil aber ein nicht wiederverwendbarer Tombstone; v1 und seine
Artefakte bleiben unveraendert. Sechs Bank-5-CodeObjects uebernehmen
Kapazitaetspruefung, Sektorbefuellen, Tail-Walk und Commit. Die Kette wird vor
dem ersten Write vollstaendig und mit Fuel 255 validiert. Danach wird der
vierbyteige L65M-Praefix im ersten Sektor invalidiert, der Tail geschrieben und
der vollstaendige erste Sektor zuletzt publiziert. Read-/Write-Abbruch kann
damit kein plausibles Teil-FASL hinterlassen.

Der Host-Oracle pinnt zehn Grenzlaengen, fuenf deterministische I/O-Fehler,
exakte Bytes und Linkmarker sowie unveraenderte BAM-, Directory- und
Nachbarbereiche. Die bestehenden acht D81-Persistenzgates sind ebenfalls gruen.
Der finale entspannte MOS-LTO/ICF-Link verschiebt Heap/VMA von `$cc26/$cc28`
auf `$c9ce/$c9d0`, netto exakt 600 B. Es bleiben 1658 B VMA- und 1400 B
Reservedefizit. Kein Slot, kein Inselbyte und kein Layoutpin wurde geaendert;
CP5, Ship und Hardware-G5 bleiben gesperrt.

Die Burn-down-Projektion ist deshalb enger, aber nicht geschlossen: Ein
separat freizugebender LCC-Installer kann voraussichtlich 450--650 B gewinnen.
Danach bleiben 1008--1208 B VMA und 750--950 B Reserve offen. Die 932-B-
Inselreserve ist weiterhin nicht freigegeben und selbst dann kein garantiert
schliessender Einzelhebel. Prim-38-Tombstone und private Gateway-ID sind eine
eigene ABI-Entscheidung.

## 2026-07-12: Der Vier-Kommandos-Installer-Gateway wird nach realem Link verworfen

Der freigegebene Prototyp setzte den oeffentlichen `lcc-install` als
STRICT_ARITY-2-CodeObject in Bank 5 um und reservierte versuchsweise Prim 57
fuer ein privates BEGIN/STEP/FINISH/FUEL_ABORT-Gateway. Prim 38 waere nur bei
erfolgreicher Promotion zum Tombstone geworden. Der vollstaendige v2-
Artefaktbau war semantisch geschlossen: null CALLPRIM 38, vier statische
CALLPRIM-57-Stellen, 1804 Directory-Aufrufe und keine Misses oder Tombstones.

Der reale MOS-LTO/ICF-Link widerlegt jedoch die Budgetannahme. Gegen dieselbe
`b0d6b07`-Baseline stiegen BSS, Heap und Overlay-VMA jeweils um 486 B, von
`$c9ce/$c9d0` auf `$cbb4/$cbb6`. Der Symbol-Diff erklaert das Ergebnis:
`eval_v2_workbench_service` +344 B, notwendiges Abort-Cleanup +89 B und
`vm_callprim` +46 B. Der alte Koordinator war bereits stark in den residenten
Service gefaltet; ausgelagert wurde fast nur die billige Schleife, waehrend
Owner-, Sequenz-, Fuel- und Cleanup-Vertraege neu resident bezahlt wurden.

Der Prototyp ist deshalb vollstaendig zurueckgerollt. Prim 38 bleibt in v2
aktiv, Prim 57 bleibt reserviert; v1, Slots 30--32, Inselklasse und Layout sind
unveraendert. Die Zahl 8 bleibt in drei getrennten Namensraeumen eindeutig:
`LISP65_ERR_LCC_INSTALL` im REPL-Fehlerraum, `needs-remount` im M65D-
Statusraum und `LCC_INSTALL_ERR_SHAPE` im privaten Installerstatus. Es wurde
kein neuer Sentinel oder L65E-Text eingefuehrt. Der Stop-Report bindet beide
ELFs, den Candidate-Profilhash und die Symbol-Deltas. Jede Fortsetzung verlangt
eine neue Architekturentscheidung; eine Insel- oder Layoutreaktion ist nicht
freigegeben.

## 2026-07-12: Marginal-Sweep findet einen 2542-B-String-Builder-Schnitt

Vier Verantwortungsklassen wurden in getrennten Temp-Worktrees gegen die
unveraenderte FASL-Baseline real mit MOS-LTO/ICF gelinkt. Der vollstaendige
LCC-Installationskoordinator liefert 1058 B, entfernt aber den Compile-Pfad und
schliesst das Budget nicht. Ein isolierter REPL-Komfortschnitt liefert 460 B,
kostet aber Echo, Backspace, History und IDE-Toggle. Der Boot-Cluster ist kein
ehrlicher Hebel: Der alte 1371-B-Wert war ein nonfunktionaler Boot-Skip; mit
erhaltener Trust-Reihenfolge bleiben 110 B nur durch Verlust vorgeschriebener
Diagnosen. Sein promotionsfaehiges Planungsbudget ist null.

Der starke Befund liegt innerhalb von `LISP65_V2_NATIVE_STRING_CAPS`. Prim
26/27, die atomaren Slice-/Concat-Builder, haben im aktuellen Workbench-
Artefakt exakt null Aufrufe. Prim 28/29, die Code-List-Konverter, bleiben mit
48/27 Aufrufen aktiv. Das ausschliessliche Entfernen der Builder verschiebt die
Overlay-VMA von `$c9d0` auf `$bfe2`, exakt 2542 B. Der harte Produktlink liegt
884 B unter `$c356` und behaelt 2676 B Post-Boot-Reserve, 1140 B ueber dem
1536-B-Ziel. Slots, Insel und Layout bleiben unveraendert.

Der Stub ist keine Promotion: Die normative Familien-Evidence verwendet 26/27
und pinnt deren GC-/OOM-/Fault-Atomizitaet. Empfohlen wird deshalb eine noch
nicht freigegebene Vertragsentscheidung: Builder und Codecs trennen, 28/29
behalten, 26/27 dauerhaft tombstonen und atomare Konstruktion in den spaeteren
Buffer-/String-Konstruktionsblock verschieben. Ein Workbench-only-Schalter ist
verworfen, weil derselbe v2-ABI sonst produktabhaengige Semantik haette.

Zwei alte Layoutzahlen werden korrigiert. Die Insel hat nach 1108 B Code und
260 B Annex nur 680 B frei; 932 B war der Vor-Annex-Stand. Der 1396->1024-
Slice-Cap ist kein unabhaengiger Reclaim, weil Slot 37 aktuell 1369 B belegt.
Gerade deshalb ist der String-Schnitt die bevorzugte 1.1-Reserveentscheidung:
Er schliesst den Link, ohne die letzte strukturelle Layoutreserve zu verbrauchen.
Bis zur Nutzerfreigabe bleiben Produkt, ABI, CP5, Ship und G5 unveraendert rot.

## 2026-07-12: String-Caps schliesst die harten Budgets, nicht das 1.1-Ziel

Der freigegebene reine Entfernungsschnitt entfernt die unbenutzten atomaren
String-Builder aus Bank 0. Prim-IDs 26 (`%string-slice`) und 27
(`%string-concat-list`) bleiben wegen bereits erzeugter v2-Staging-Evidenz
dauerhafte Tombstones. Die internen Code-List-Codecs 28/29 bleiben aktiv;
`substring` und `string-append` materialisieren ueber diesen Pfad. Ein OOM
publiziert kein VM-Ergebnis. Transaktionales Arena-Rollback, Span-DMA und ein
First-Class-Buffer sind in den benannten 1.1-Block
`buffer-and-string-construction` verschoben und erhalten spaeter neue IDs.

Der vollstaendige stack-guarded Produktlink ist gegenueber dem Seed-/Stub-Sweep
die autoritative Messung. Er endet bei `runtime_overlay_vma=$c0fa`, 604 B unter
`$c356`, und bei 2397 B Post-Boot-Reserve. Das 1536-B-Hard-Minimum ist um 861 B
uebertroffen; gegen die akzeptierte v2-FASL-Baseline `$c9d0` gewinnt der Link
2262 B. Es gibt keinen neuen Slot, keine Inselnutzung und keine
Layoutaenderung.

Die zugesagte ABI-1.1-Reserve von 2676 B wird dennoch um 279 B verfehlt. Diese
Differenz entspricht dem Stack-Guard-/Produktgraph, den der Sweep nicht
enthielt. Der Vertrag bleibt bei 2676 B und CP5 bleibt pending; G5 wurde nicht
gestartet. Die naechste Architekturentscheidung ist entweder eine explizite
Neupinnung auf 2397 B oder ein einmaliger reiner Entfernungsschnitt fuer
mindestens 279 B. Insel-, Slot- und Layoutaenderungen bleiben ausserhalb dieser
Entscheidung.

## 2026-07-12: Privater GitHub-Mirror wird Teil des Block-Rituals

Der lokale Ext4-Arbeitsbaum
`/home/alex/Videos/lisp65-cp4-safety-20260712` bleibt der kanonische
Integrations-, Build- und Evidenzstand. Das private Remote `github` unter
`git@github.com:novemberist/lisp65.git` ist ausschliesslich ein Off-Site-
Backup/Mirror. Es begruendet weder eine zweite Wahrheit noch einen neuen
Pull-basierten Integrationsfluss.

Das verbindliche Abschlussritual jedes Entwicklungsblocks lautet ab jetzt:
Commit und Gate-Nachweis, Erneuerung samt Verifikation des Sicherheitsbundles,
danach `git push github`. Der Push gilt nur bei erfolgreichem Git-Exitstatus und
aktualisierter Remote-Ref als abgeschlossen. Die bekannten ENOSPC-Warnungen
beim Schreiben von `known_hosts` sind harmlos und aendern diese Erfolgskriterien
nicht.

Das Remote bleibt privat. Ein spaeteres Public-Schalten ist eine eigene
Freigabeentscheidung und setzt zuvor die in `docs/reference/README.md`
dokumentierte Lizenz-/Redistributionspruefung der mitgetrackten PDF-Snapshots
voraus.

## 2026-07-12: CP5 wird auf den vollen Produktlink mit 2397 B neu gepinnt

Der volle stack-guarded Produktgraph ist fuer CP5 autoritativ. Seine 2397 B
Post-Boot-Reserve ersetzen die 2676-B-Prognose des Seed-/Stub-Links; das harte
1536-B-Releasekriterium bleibt unveraendert und ist mit 861 B Marge erfuellt.
Der 279-B-Unterschied ist kein Regressionsbudget, sondern ein bekannter
Korrekturfaktor fuer den im Stub fehlenden Stack-Guard- und finalen
Verdrahtungsgraph. Kuenftige Seed-/Stub-Projektionen werden vor einer
Architekturentscheidung um mindestens diesen Faktor pessimiert.

Die 861 B sind bis zur bestandenen G5-Matrix gebankt. Danach duerfen sie fuer
ABI 1.1 nur postenweise und jeweils nach einem eigenen realen Probelink
ausgegeben werden. Insel, Slice-Cap, Slots und Layout bleiben Reserven und
werden fuer diese Neupinnung nicht angefasst. Damit ist der Produktlink-Teil
von CP5 gruen; die verbleibende CP5-Bedingung ist die vollstaendige
Workbench-plus-Runtime-G5-Matrix.

Der erste saubere Kandidatenpack nach dieser Entscheidung hat zugleich den
internen Runtime-Core-Proof neu gelinkt. Durch den bereits freigegebenen
String-Builder-Schnitt sinkt sein PRG von 28644 auf 26296 B und sein residenter
Anteil von 25127 auf 22781 B; die Post-Boot-Reserve steigt von 11736 auf
14082 B und uebertrifft das 12288-B-Berichtsziel um 1794 B. Der alte Pin wurde
vom Packer fail-closed abgewiesen und auf diese reale, byteidentisch
reproduzierte Messung aktualisiert. Der Proof bleibt nicht shippbar und hat
allein keine CP5- oder G5-Autoritaet.

## 2026-07-12: G5 startet und findet eine dynamische `boundp`-Luecke in CP4

Der auf Commit `3f7e001` versiegelte interne Kandidat hat die erste echte
Workbench-G5-Sequenz begonnen. Overlay-Boot, Ergebnis 42, IDE-Load,
Bytecode-Compile-Kind, VM-Bridges, GC-Stress und Reader-Recovery sind auf der
MEGA65 gruen. Der vollstaendige UX-Fall stoppt danach beim ersten
`save-buffer-to`: `m65d-save` endet mit `*** vm: type error`.

Die Hardwarediagnose grenzt den Fehler vom String-Codec ab. `%string-codes`
liefert fuer `"ap6src"` korrekt `(97 112 54 115 114 99)`, waehrend
`m65d-status`, `m65d-save` und `m65d-remount` scheitern. Ihr gemeinsamer
Einstieg verwendet `(funcall (function boundp) ...)`; `boundp` direkt ist im
carrier-freien v2-Produkt undefiniert und als Funktionsdesignator ein
Type-Error. `vm_apply_primitive` deckt diesen weiterhin als Treewalk-Primitive
installierten Funktionsdesignator nicht ab.

Damit war die CP4-Zero-Miss-Aussage fuer statische `OP_CALL`-/`CALLPRIM`-Sites
korrekt, aber fuer native Funktionsdesignatoren in Literalen unvollstaendig.
CP5 bleibt bei 4/5 und G5 ist rot. Die 861 B bleiben gebankt; ein Fix darf sie
nicht vor bestandener G5 still ausgeben. Die restliche Matrix wurde nach dem
ersten semantischen Fehler nicht weitergefahren. Das SHA-gebundene
`g5-start-failure-receipt.json` haelt Kandidat, Rohbelege und Diagnose fest.

## 2026-07-12: CP4 wird mit generiertem Designator-Dispatch erneut geschlossen

Der G5-Fund wird als Fehler der Vollstaendigkeitskonstruktion behandelt, nicht
als Anlass fuer eine weitere Handliste. `config/v2-native-function-registry.json`
ist ab jetzt die gemeinsame Quelle fuer den nativen VM-Designator-Dispatch und
die generierte Differentialmatrix. Das CP4-Gate erzwingt Paritaet zwischen 15
Registry- und 15 Dispatch-Eintraegen. Jede dieser Primitiven wird ueber direct,
funcall und apply in native C Treewalk, nativer C-Compiler-VM, Python-P0-VM und
selbstgehostetem LCC ausgefuehrt: 180 von 180 Beobachtungen sind gleich.

`boundp` erhaelt die regulaere, im v1 weiterhin reservierte v2-Prim-ID 57. Damit
benutzen direkter Aufruf, funcall und apply denselben CALLPRIM-Pfad; es gibt
keinen neuen allgemeinen OP_CALL-Fallback. Die internen Codecs 28/29 bleiben
absichtlich keine Funktionsdesignatoren. Dieser Ausschluss ist in der Registry
explizit und endet mit dem stabilen Fehlercode
`LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR` und dem Text
`vm: primitive is not a function designator`.

Der reale volle Stack-Guard-Neulink schliesst bei `$c1d8`, 382 B unter dem
VMA-Limit `$c356`, und bei 2175 B Post-Boot-Reserve. Gegen `$c0fa`/2397 B sind
das 222 B VMA- und Reservekosten. Das 1536-B-Hard-Minimum
bleibt mit 639 B Marge erfuellt; Insel, Slice-Anzahl, Slots und Layout bleiben
unveraendert. Diese 639 B sind bis G5 gebankt und danach weiterhin nur
postenweise per 1.1-Probelink ausgebbar.

CP5 bleibt vorerst 4/5. Der fruehere G5-Lauf ist nur der historische Trigger
der Wiedereroeffnung. Seine gruenen Teilsequenzen werden nicht recycelt; die
vollstaendige Hardwarematrix beginnt auf dem neu gebundenen Binary von vorn.

Der anschliessende saubere Runtime-Core-Paarlink bleibt byteidentisch
reproduzierbar. Gegen die Vor-Fix-Pinnung kostet derselbe Abschluss 216 B
resident: PRG 26514 B, resident 22997 B, Post-Boot-Reserve 13866 B. Damit liegt
der interne Proof weiterhin 1578 B ueber seinem 12288-B-Berichtsziel und 5674 B
ueber dem 8192-B-Hard-Minimum. Er bleibt nicht shippbar und hat keine eigene
CP5- oder Hardwareautoritaet.

## 2026-07-12: Frischer G5-Lauf bestaetigt CP4 und stoppt an Library-Kapazitaet

Der von Commit `4a11f21` frisch versiegelte Kandidat hat G5 ohne
Evidenzrecycling begonnen. `overlay-stack-guard` und `stdlib-runtime` sind
gruen. Im vollstaendigen UX-Fall ist insbesondere der zuvor rote Pfad
geschlossen: Erstes Persistenz-Create liefert `(t nil bytecode)`; Read,
zweites Create, Replace, Remount, Higher-Order-Persistenz sowie Reset/Reload
bestehen. Damit ist der generierte `boundp`-Designatorabschluss auf echter
Hardware bestaetigt und CP4 bleibt geschlossen.

Die Matrix stoppt spaeter fail-closed bei `higher-order-idex-some`.
`save-buffer-to` liefert `nil` und `ide-error` meldet
`"persistence unavailable"`. Nach IDE und IDEX stehen 682 von 720 Symbolen;
`load-lib "m65d"` liefert `nil`, und `m65d-save` bleibt ungebunden. Ein
frischer Gegenversuch mit IDE -> M65D -> IDEX ergibt `(t t nil bytecode 685
720)`: Die Reihenfolge verschiebt nur, welche dritte Library nicht mehr
registriert werden kann. Vor dem Reset hatte derselbe UX-Lauf bei 678/720 noch
genug Spielraum fuer das lazy M65D; vier weitere Symbole legen die fehlende
Kompositionsgarantie offen.

Der Fehler ist weder Carrier-Cut noch Medium oder Transport. Er verlangt eine
Produktentscheidung ueber gemeinsame IDE-/IDEX-/M65D-Kapazitaet; eine reine
Harness-Umsortierung waere keine Abnahme. Das neue Failure-Receipt bindet
Kandidat, Hardwareplan, internes Paket und Rohbelege per SHA. CP5 bleibt 4/5,
639 B bleiben gebankt, die restlichen Matrixfaelle wurden nicht gestartet, und
jedes korrigierte Binary muss G5 vollstaendig von vorn durchlaufen.

## 2026-07-12: Library-Komposition wird mit Nutzermarge konstruktiv geschlossen

Option B ist verworfen: IDEX aus dem Persistenzvertrag auszuschliessen wuerde
Wortnavigation und Speichern gegeneinander konditionieren und damit die
unbedingte Persistenzgarantie brechen. Der Produktvertrag fordert stattdessen
IDE + IDEX + M65D gleichzeitig sowie mindestens 32 freie Symbol- und
Directory-Slots fuer die Nutzersitzung.

Die Privatisierung lief zuerst. 27 weitere M65D-/IDEX-Helfer wurden einzeln
durch die bewaehrte Private-Inline-Mechanik probiert; 25 scheitern an rel8-
Zweigen, zwei an der 255-Byte-Codeobjektgrenze. Der ehrliche Gewinn ist null.
Der frische Hardwarewasserstand nach IDE+IDEX ist 677 Symbole, 9111
Namepool-Bytes und 533 Directory-Eintraege. Das Manifestmodell liegt bei
672/9060/533; die permanente Post-Reset-Korrektur ist daher gemessen +5
Symbole und +51 Namensbytes, nicht eine pauschale Huelle.

Der kleinste gruen verlinkte Pin ist `MAX_SYM=752`, `NAMEPOOL=10208`,
`VM_DIR_MAX=608` und `SYMPOOL_EXT_OFF=$c680`. Das generierte v2-Kompositionsgate
laedt die vier Manifeste Resident+IDE+IDEX+M65D als eine Reihenfolge und endet
bei 571/608 Directory-Eintraegen (576 post-align, 32 frei), 713/752 Symbolen
(39 frei) und 9718/10208 Namensbytes (490 frei). Die alten Caps sind ein
negativer Kontrollfall: Directory -11, Namepool -182 und nur sieben statt 32
freier Symbole.

Das GC-Gate zaehlt exakt `Symbolzahl × GC-Laeufe` Root-Scan-Besuche und misst
fuenf Hostpunkte. Der lineare Fit erreicht R² > 0,9999; 720 -> 752 addiert im
Hostmodell rund 0,25 us je Vollscan. Das ist bewusst kein MEGA65-Zyklusclaim;
die Zielhardwareabnahme bleibt die vollstaendige G5-Matrix.

Der volle Produktlink endet bei `$c22c` und 2091 B Post-Boot-Reserve. Gegen
den 2175-B-Kandidaten kostet die gesamte Cap-Korrektur 84 B. Diese 84 B werden
als ausdrueckliche Release-Blocker-Ausnahme aus der gebankten Marge bezahlt;
555 B ueber dem 1536-B-Ziel bleiben gebankt. Slotzahl, Insel und
Overlay-Layout aendern sich nicht. CP4 ist mit dem permanenten
Kompositionsgate erneut geschlossen, CP5 bleibt bis zu einer komplett neuen
G5-Runde 4/5; kein Teilresultat des vorigen Binaries wird wiederverwendet.

## 2026-07-12: Workbench 10/10 gruen, aber der G5-Skeleton bindet das falsche Runtime-Profil

Der auf Commit `6c1fa1c` versiegelte Kandidat hat die Workbench-Seite der
14-Fall-Matrix vollstaendig von vorn durchlaufen. Overlay/Stack-Guard,
Stdlib-Deploy, der komplette UX-Lauf und alle sieben Persistenzfaelle sind
gruen. Insbesondere bestehen nach IDE+IDEX das lazy M65D, Create/Read/Replace,
Remount und Reset sowie die zuvor rote `higher-order-idex-some`-Sequenz mit
Ergebnis `3`; `every` liefert `t`, M-x/eval-buffer `("evaluated" 42)`. Die
Disk-Oracles enden mit dem exakten BAM-Diff sowie `737`, `767`, `797`, `797`
und `907`. Damit ist die neue 752/10208/608-Komposition auf echter Hardware
funktional bestaetigt.

Ein einzelner M5-Start erhielt vor dem Senden des Test-PRG keine
Ethernet-Antwort. Es gab weder semantische Ausfuehrung noch Medienmutation;
der unmittelbare Kandidaten-Restore bestand. Der einmalige Wiederanlauf
benutzte eine frische Wegwerf-D81, einen neuen Remote-Namen und einen eigenen
Evidence-Pfad und war vollstaendig gruen. Der Vorfall ist als
praesemantischer Transport-Retry gebunden, nicht als versteckter Produkt-Retry.

Vor den vier Runtime-Faellen stoppt die Matrix dennoch fail-closed. Der
Kandidat bindet das v2-Runtime-Core-PRG mit SHA-256 `eeb0985b...`, waehrend die
im Plan genannten `runtime-export-g5-*`-Targets nach Aufloesung das separate
v1-Runtime-Export-PRG mit SHA-256 `04719b37...` und anderem Preload bauen. Ein
Lauf dieser Targets waere Hardwareevidenz fuer ein anderes Binary und Profil.
Zusaetzlich steht der interne G5-Vertrag weiterhin auf `verifier-skeleton`;
alle drei Domain-Verifier sind ungebunden und ein positives Receipt wird vom
Tool ausdruecklich abgelehnt. Der v2-Runtime-Proof selbst verspricht ebenfalls
`hardware_g5_claim=none`.

Darum wurden keine Power-Cycle-Tokens behauptet und keiner der vier
Runtime-Faelle gestartet. Das gebundene
`g5-composition-partial-run-report.json` traegt `g5_claim=none`, 10/14
Hardwarebeobachtungen und den exakten Bindungsblocker. CP5 bleibt 4/5 und die
555 B bleiben gebankt. Die Schliessung verlangt zuerst v2-gebundene
Runtime-Hardwarepaketierung und alle drei Receipt-Verifier. Weil deren SHAs
Teil des Kandidatenvertrags sind, entsteht dabei ein neuer Kandidat; danach
muessen alle 14 Faelle erneut von vorn laufen, die vier Runtime-Phasen jeweils
nach einem eigenen echten Power-Cycle.

## 2026-07-12: G5-Skeleton bindet die vollstaendige Artefaktmenge konstruktiv

Der Packaging-Stop wird als Fehler der Beweisfuehrung und nicht als
Produktregression geschlossen. Das interne Kandidatenmanifest enumeriert jetzt
alle von der 14-Fall-Matrix beruehrten PRGs, Preloads, Runtime-Phasenbilder,
Overlay-/Attic-Image und die D81 sowie die Policy- und Verifier-Artefakte per
SHA. Ein permanentes Paritaetsgate verlangt, dass die Vereinigungsmenge aller
Case-Referenzen plus Policy-Artefakte exakt dieser Kandidatenmenge entspricht.
Damit kann kein Target mehr ein nicht manifestiertes Binary testen.

Der Runtime-Core-Proof erhaelt dafuer ein eigenes strikt nicht shippbares
v2-Hardwarepaket. Es bindet das Proof-Manifest, PRG, ELF, den kanonischen
Preload, Clean-/Truncation-/Bitflip-/Foreign-Build-ID-Stages und das aus dem ELF
abgeleitete Hardware-Oracle. Der bestehende Raw-State-Verifier prueft dieses
Format zusaetzlich zum unveraenderten Runtime-Export-Format; dessen kompletter
Harness-Selbsttest bleibt gruen.

Ein gemeinsamer, SHA-gebundener Domain-Verifier besitzt drei getrennte
Einstiege: Runtime revalidiert alle vier Rohreadback-Receipts und verlangt vier
verschiedene physische Cycle-IDs; Persistenz bindet Before-/After-D81 und fuehrt
die fallgenauen Host-Diff-Oracles erneut aus; UX bindet die entscheidenden
Rohtexte und den Live-Ship-Readback. Das Top-Level-Receipt kann nur bei exakt
14 verifizierten Faellen `passed` tragen. Die einmalige Retry-Regel ist nun
Vertrag: ausschliesslich Transportfehler vor semantischer Ausfuehrung und
Medienmutation, frische Evidenz und Wegwerfmedien, beide Versuche gebunden.

Diese Wiedereroeffnung bewegt kein Produktbyte und gibt keinen Bank-0-Spielraum
aus. Die 555 B bleiben bis zur vollstaendig neu ausgefuehrten G5-Matrix
gebankt. Der gruen beobachtete Zehnerlauf bleibt Produktevidenz, wird aber nicht
in das neue G5-Receipt uebernommen.

## 2026-07-12: 14/14 Rohfaelle gruen, Receipt-Schluss stoppt an zwei Skeleton-Schemafehlern

Der auf Commit `413fb34` gebundene Kandidat hat alle 14 Hardwarefaelle von
vorn bestanden. Der zuvor zu frueh gelesene M7-Marker war reine
Harness-Paketierung: Der G5-Wrapper hatte die bereits gepinnten Parameter
`--wait 45 --timeout 40` des normalen M7-Targets nicht uebernommen. Nach deren
Wiederherstellung bestanden die zehn Workbench-Faelle erneut, einschliesslich
des exakten 676-B-D81-Diffs und `m7-var-run => 907`. Clean, Truncated, Bitflip
und Build-ID-Mismatch bestanden danach unter vier verschiedenen bestaetigten
physischen Power-Cycles.

Ein G5-Claim entsteht trotzdem noch nicht. Beim Packen der drei Domain-Receipts
zeigten sich zwei konstruktive Fehler im neuen Verifier: Der Runtime-Vertrag
fordert ein Paketverzeichnis, leitete es aber durch einen Nur-Datei-Checker;
der UX-Vertrag verlangte fuer seinen Persistenzbeleg irrtuemlich den alten
M5-Wert `797` statt des tatsaechlichen Reset-Oracles `612/613`. Beide Fehler
machen ein ehrliches positives Receipt unmoeglich. Fremde Evidence oder ein
synthetischer Marker sind unzulaessig.

Die Reparatur bindet das Runtime-Paketverzeichnis ueber die SHA seiner
`manifest.json` und pinnt fuer UX den vollstaendigen Reset-Rueckgabewert mit
beiden Quellen und Werten. Ein Selbsttest weist eine falsche Paket-Manifest-SHA
ab. Da der Domain-Verifier selbst Kandidatenartefakt ist, entsteht erneut ein
neuer Kandidat und alle 14 Faelle muessen nochmals von vorn laufen. Die
14/14-Rohbeobachtung von `413fb34` bleibt Produkt- und Harnessdiagnose, aber
keine wiederverwendbare G5-Evidenz. Die 555 B bleiben gebankt.

## 2026-07-12: G5-Evidenzidentitaet folgt Produkt-SHAs und verlangt Vorab-Preflight

Die Neustartdoktrin wird praezisiert: Ein G5-Kandidat ist die kanonische Menge
der sechs Produktartefakt-SHAs (Runtime-PRG/Preload sowie Workbench-PRG,
Preload, Attic-Katalog und D81), nicht die SHA des gesamten Harness-Manifests.
Bestandene Fall-Receipts binden an `product_identity_sha256` und bleiben bei
reinen Harness-, Verifier- oder Paketierungsfixes gueltig. Nur ein Delta in
mindestens einer Produkt-SHA erzwingt einen vollstaendigen Neulauf; ansonsten
werden nach Fix-forward ausschliesslich fehlende Faelle ausgefuehrt.

Vor jedem weiteren physischen Fall ist ein statischer 14-Faelle-Preflight
Pflicht. Er revalidiert Kandidat, Runtime- und Workbench-Paket, loest alle 14
Make-Targets ohne Seiteneffekt auf und pinnt pro Fall Target und expandierte
Recipe-SHA. Fremde normale Ship-/Runtime-Export-Pakete, fehlende Verifier oder
die verlorenen M7-Zeitparameter lassen den Preflight scheitern. Jeder
Domain-Falleintrag bindet das Preflight-Receipt, unter dem er ausgefuehrt wurde;
nach einem Harness-Fix duerfen deshalb alte gruene Faelle und neue Restfaelle
mit verschiedenen Preflight-SHAs dieselbe unveraenderte Produktidentitaet
schliessen.

Der unmittelbar vor dieser Praezisierung gestartete Overlay-Lauf war technisch
gruen, begann aber ohne den nun verpflichtenden Preflight und wird nicht
angerechnet. Ein finaler Ein-Zeremonie-Lauf bleibt optional und darf erst nach
einem vollstaendig gruenen Preflight zur Promotion dienen.

Der Runtime-Core hatte seine eingebettete Build-ID bislang indirekt aus dem
gesamten Git-HEAD abgeleitet. Das haette bei jedem reinen Harness-Commit den
Runtime-PRG-SHA bewegt und die Produktidentitaetsregel wirkungslos gemacht.
Sein `source_commit`-Provenienzfeld wird deshalb nun mit einem stabilen
40-Hex-Produktinput-Digest belegt. Dieser umfasst Runtime-C-/Headerquellen,
Buildprofile, Linkerscript, Runtime-Suite sowie Bytecode-/Preload-Emitter, aber
keine G5-Harness-, Verifier-, Dokument- oder Receiptdatei. Der Git-Arbeitsbaum
muss beim Versiegeln weiterhin sauber sein. Damit bewegt nur eine tatsaechliche
Runtime-Produktinputaenderung die Build-ID und den Produkt-SHA.

## 2026-07-12: Interne CP5-G5-Matrix schliesst mit 14/14 und vier Power-Cycles

Die unveraenderte Produktidentitaet
`67400c05a96f18dbfb69941c8a7a1ff8bd6fb9c2ba1baa665c6a5f3a86fb6ed8`
hat die interne Hardwarematrix vollstaendig bestanden. Der verpflichtende
statische 14-Faelle-Preflight war gruen und seiteneffektfrei. Der bereits
bestandene Overlay-Fall blieb gemaess der Produkt-SHA-Doktrin an seinen
frueheren gruenen Preflight gebunden; alle weiteren Faelle binden den aktuellen
Preflight mit SHA
`4b6cef6a39336fb2aa9d27a673d17d72403cbcf5c238bea2efaf691acbd86656`.

Die Workbench schliesst mit zehn verifizierten Faellen: IDE+IDEX+M65D,
`some => 3`, `every => t`, M-x/eval-buffer sowie sieben Persistenzpfade mit
den exakten Disk-Oracles bis 907 und dem Reset-Ergebnis 612/613. Der Runtime
Core schliesst mit `clean => 42` und den terminalen Detailcodes 1, 2 und 3 fuer
Truncation, fremde Build-ID und Bitflip. Die vier Runtime-Faelle tragen die
verschiedenen bestaetigten Cycle-IDs `g5-67400c05-runtime-clean-01`,
`g5-67400c05-runtime-truncated-01`,
`g5-67400c05-runtime-build-id-01` und
`g5-67400c05-runtime-bitflip-01`.

Die Domain-Receipt-SHAs sind `35d879f1e95a...` fuer Workbench UX,
`4d92ea4de2aa...` fuer Workbench-Persistenz und `639dcb3eccfe...` fuer den
Runtime Core. Das separat erneut verifizierte Top-Receipt
`build/cp5-g5-v2-bound/receipts/g5.json` hat die SHA
`80781e1ba57527b17bae047647d0d5bb685f4fe566ce688683a8aade9f83dce6`
und meldet `PASS cases=14 physical_power_cycles=4 g5=passed`.

Damit ist die interne CP5-Hardwarebedingung bestanden. Die verbliebenen 555 B
haben den Status `banked-until-g5` erfuellt, bleiben aber fuer ABI 1.1
reserviert und duerfen weiterhin nur postenweise nach einem eigenen Probelink
ausgegeben werden. Kandidat und Hardwarepakete bleiben `shippable=false` und
erteilen weder globale Profilumschaltung noch Release-Autoritaet. Die
transaktionale Uebernahme in den CP5-Hauptvertrag ist ein eigener
Integrationsschritt; dessen Receipt-Emitter und Host-5-Gate werden nicht durch
eine manuelle JSON-Umschaltung umgangen.

Der Abschlussaudit repariert ausserdem zwei vorbestehende reine
Evidenzbindungen: Checkpoint 1 wird auf den seit `4b30b06` erweiterten
Capability-/Carrier-Vertragstext neu versiegelt, Checkpoint 3 auf das seit der
G5-Paketierung erweiterte Makefile. Nur die Evidence-SHAs und die beiden
Receipt-Pointer bewegen sich; der normalisierte Contract-Policy-SHA, die
Checkpoint-Metriken und alle sechs Produktartefakt-SHAs bleiben unveraendert.
Der Hauptvertragsvalidator ist danach wieder gruen bei 4/5.

## 2026-07-12: Release-Arbeitsplan R0 stellt die Vertragskonsistenz wieder her

Der korrigierte Release-/1.1-Plan beginnt mit einer reinen Konsistenzphase vor
jeder CP5-Promotion. Der Migrationsvertrag bindet nun den aktuellen
Capability-/Carrier-Hauptvertrag mit SHA
`65b66914f12356788b8a34444fa2554ee959945c41508cea8795f8d9f70d0d69`.
Die globale Matrix bindet den nach der v2-Runtime-Paketierung aktuellen
Runtime-Hardware-Verifier; ihr neuer SHA
`e9be5ee2538942f84d5fc7cb42eb7dd2f24f83c4724af4019ee7d5c1050fe2e4`
wird sowohl vom Migrations- als auch vom internen G5-Vertrag uebernommen.
Die absichtlich noch fehlenden Workbench-Verifier-SHAs bleiben dagegen bis R5
offen und erzeugen keine vorgezogene globale G5-Autoritaet.

Der Arbeitsplan wird als `proposal` in den Dokumentindex aufgenommen und
pinnt Directory-only/L65M-v2 nur noch einmal als releasekritischen
IDE-Pflichtblock. R0 bewegt weder Produktcode noch eine der sechs
Produktartefakt-SHAs. Migrationsvalidator, Semantik-Lint, Dokumentindex,
interner G5-Vertrag und der vollstaendige `check-source`-Lauf sind danach
gruen. Die Kandidaten- und Receipt-Huelle wird gemaess Produktidentitaetsregel
ohne Hardware-Neulauf neu versiegelt.

## 2026-07-13: Runtime-Receipts werden fuer Produktidentitaets-Resume verifizierbar

Der erste R1-Audit findet eine asymmetrische Bindung: Workbench-Fallreceipts
tragen bereits die stabile Produktidentitaet, die vier nativen Runtime-
Rohreceipts tragen zusaetzlich die SHA ihres damaligen Hardwarepakets und
Oracles. Ein reiner Paketierungs- oder Policy-Neubau machte deshalb die
erneute Domain-Aggregation unmoeglich, obwohl Runtime-PRG, Preload, Build-ID,
Phasenimages und Hardwarebeobachtungen unveraendert waren.

Der Domain-Verifier implementiert nun die freigegebene Resume-Doktrin auch
fuer Runtime: Nach erfolgreicher Produktidentitaets- und Preflight-Pruefung
kopiert er historische Runtime-Receipts in ein temporaeres Verzeichnis und
bindet dort ausschliesslich `manifest_sha256` und `oracle_sha256` an das
aktuelle Kandidatenpaket. Anschliessend laeuft der bestehende strikte
Runtime-Suite-Verifier ueber alle vier Kopien. Phasenmutation, Stage-/Clear-
Images, Adressen, Rohreadbacks, erwartete und beobachtete Werte, Cycle-IDs,
Build-ID und komplette Evidence-Inventare bleiben unveraendert und werden
gegen das aktuelle produktidentische Paket erneut geprueft. Die normalisierten
Kopien werden nicht als Evidenz publiziert.

Damit wird keine Hardwarebeobachtung umgedeutet: Ein Produkt-SHA-Delta bleibt
weiterhin ein Vollneulauf. Die neue Mechanik schliesst nur die zuvor
widerspruechliche Verpackungsbindung fuer den ausdruecklich erlaubten
produktidentischen Fix-forward-Fall.

## 2026-07-13: R1 schliesst CP5 transaktional und oeffnet R2

Die interne Hardwareevidenz wird als deterministisches, versioniertes Archiv
mit eigenem Offline-Verifier in den Hauptvertrag uebernommen. Checkpoint 5
leitet seine Werte aus diesem Archiv und dem realen Produktlink ab: Workbench-
VMA `$c22c`, 2091 B Workbench-Reserve, 13866 B Runtime-Core-Reserve, -1956 B
deploytes Bank-0-Netto, kein Layout-, Slot- oder Inseldelta sowie G5 bestanden.
Alle fuenf Checkpoint-Receipts sind SHA-gebunden und das Host-5-Gate fuehrt den
Archivnachweis selbst aus.

Damit erfolgt die genau einmal erlaubte atomare Promotion des Capability-/
Carrier-Blocks in das nicht shippbare Stagingprofil. Der Migrationsvertrag
markiert nur diesen Architekturblock als abgeschlossen und oeffnet als einzige
Arbeitslinie die sequenzielle Familienmigration. Die 555 B bleiben fuer ABI
1.1 reserviert. Globale Dialektumschaltung, Ship und Release bleiben ohne die
spaetere Familienmigration, globale G5-Matrix und G6 unveraendert gesperrt.
Die neun noch offenen Semantikentscheidungen werden nicht still vorbelegt;
sie bilden die naechste groessere Abstimmung in R2.

## 2026-07-13: Neun R2-Semantiken entschieden, Lists migriert

Der R2-Entscheidungsvertrag bindet 17 normative Faelle in Strings,
System/Runtime und IDE. `search`, `position`, `string-ref` und der kuenftige
`buffer-ref` teilen die nullbasierte Indexachse. `key-event` besitzt einen
optionalen Fixnum-Modus mit Default 0, liefert `(key code modifiers)` und bei
leerer nichtblockierender Queue `nil`. `load-libs` wird geordnet expandiert,
stoppt beim ersten Fehler und rollt bereits geladene Bibliotheken nicht zurueck.
`set` ist strikt zweistellig, verlangt ein Symbol und liefert den Wert.

`m65-screen` ist ausdruecklich keine garantierte Sessionbibliothek: IDE rendert
ueber native CALLPRIMs; der permanente Kompositionssatz bleibt
IDE+IDEX+M65D plus Nutzermarge. Eine spaetere Aufnahme von `m65-screen` verlangt
ein neues Manifest-Gate. Der v1-Name `edit` bleibt entgegen dem ersten
Planungsschnitt als residenter Autoload-Einstieg erhalten. Die vorhandene
Bootstrap-Naht und ihre vorhandene Loader-Diagnose werden beibehalten; eine
zusaetzliche neue Fehlermeldung ist nicht Teil des Schnitts.

Nach der Capability-/Carrier-Promotion wird die Lists-Evidenz gegen diesen
entschiedenen Vertrag neu erzeugt. Alle 35 Faelle bestehen in vier Engines;
loaded sinkt die Surface um 13 Symbole und 96 Namepool-Bytes. Der
Kapazitaetsledger bindet den CP5-Abschluss als erfuellte, separat budgetierte
Capability-Voraussetzung. Lists wechselt auf `migrated`, Strings auf
`in-progress`; globale Profil-, Ship- und Releaseautoritaet entstehen nicht.

## 2026-07-13: Promotion ist ab jetzt Versiegelung

Promotionsevidenz bindet an einen abgeschlossenen Zustand statt an spaeter
veraenderte Live-Dateien. Jede kuenftige Block- und Familienpromotion erzeugt
deshalb ein deterministisches Archiv mit eingebettetem Standardbibliotheks-
Verifier. Alle transitiven mutablen Referenzen muessen als exakte Bytes
eingebettet oder ausdruecklich per Content-SHA gebunden sein. Der einmal real
gefuehrte Archiv-only-Test ist fuer Capability/Carrier und Lists gruen; beide
Zweitbauten sind byteidentisch.

Versiegelte Archivpfade werden nie amendiert. Errata sind neue Dokumente,
Ersatzbeweise neue Promotionen. Das lebende Register bindet Block/Familie,
Commit, Archivpfad und Archiv-SHA; sein Gate prueft diese Liste und die
Einbahn-Grenze, nicht erneut den historischen Inhalt. Aktuelle Quellen haben
weiter eigene Gates. Der Capability-Vertrag liest nach seiner Promotion keine
historischen Receipt-Abhaengigkeiten mehr aus dem Live-Baum. Lists ist der
erste regulaer registrierte Familienabschluss; jede kuenftige migrierte
Familie muss vor dem Statuswechsel ein eigenes Siegel besitzen.

## 2026-07-13: Strings migriert und versiegelt

Die Strings-Familie schliesst mit 36 Faellen in vier Engines. Der native
Treewalk-Orakelpfad erhaelt dafuer zwei harness-exklusive Direktbruecken zu den
internen Codecs; die Codec-Symbole bleiben absichtlich keine
Funktionsdesignatoren. Seine v2-`apply`-Naht bildet jetzt wie die drei anderen
Engines feste Argumente plus letzte Liste ab. Diese Orakelmechanik ist durch
`LISP65_DIALECT_FAMILY_HARNESS` vom Produktlink getrennt.

Die neue on-demand `str`-Quelle verwendet nur `%string-codes` und
`%string-from-codes`; die oeffentlichen Zeichenlisten-Konverter bleiben
entfernt. Die Surface-Messung trifft die Projektion exakt: loaded `-7` Symbole
und `-79 B`, Boot `-19/-232 B`, Familiencontainer `-1375 B`. Die tiefere
Helferbuchhaltung ist ebenfalls sichtbar: Gegen v1 kostet die geladene private
Schicht `+242 B` Code und `+87 B` rohe Definitionsnamen. Das ist kein Bank-0-
Verbrauch und keine Ausgabe der 555 B, sondern der gepinnte Zwischenstand bis
zum nachgelagerten First-Class-Buffer.

Der Evidenzkandidat `71e1871` wurde vor dem Statuswechsel deterministisch als
`dialect-v2-strings-71e1871` versiegelt und offline aus dem Archiv allein
verifiziert. Danach wechselt Strings auf `migrated`, System/Runtime auf
`in-progress`. Lists-Evidenz wird von kumulativen Gates nicht mehr neu erzeugt;
abgeschlossene Familien werden nur ueber ihr Register-Siegel identifiziert.

## 2026-07-13: Fehlerkanal und Lists-Malformed-Upgrade geschlossen

Die beiden System/Runtime-Voraussetzungen `public-error-channel` und
`lists-malformed-type-errors` sind als G2-Bloecke abgeschlossen. Ein interner
Prim-ID-58-Service signalisiert den vorhandenen stabilen VM-Typfehlercode 38;
er ist weder oeffentliche Surface noch Function-Designator. Eine Probe mit
eigenem Fehlercode und neuem Text wurde verworfen, nachdem der reale
Stack-Guard-Link die gemeinsam ueberlagerte Laufzeitkante ueberschritt. Die
gebankten 555 B bleiben unangetastet.

Lists umfasst nun 43 Faelle. Sieben dotted-/Alist-Faelle sowie vier
`nth`/`nthcdr`-Indexfaelle laufen in v2 ueber den gemeinsamen Fehlerkanal; alle
344 Profil-/Engine-Beobachtungen bestehen. Der unveraenderte Strings-Promotion-
Snapshot wird nicht amendiert. Der saubere HEAD-Vergleich reproduziert den
separaten Stack-Guard-Probelinkfehler bereits ohne diese Aenderung; er ist daher
kein Delta dieses Blocks und keine Berechtigung zur Budgetausgabe.

## 2026-07-13: System/Runtime-Kandidat promotionsbereit

System/Runtime besitzt nun zwei neue native v2-Primitives: das strikt
zweistellige `set` und `key-event` mit optionalem Fixnum-Modus. Beide werden
wie alle nativen Function-Designators aus der Registry in den Apply-Dispatch
generiert. Die Registry umfasst 17 Designators, 51 Aufrufwegfaelle und 204
vier-Engine-Beobachtungen. Der gezielte Familienfall umfasst zusaetzlich 12
Faelle beziehungsweise 96 Profil-/Engine-Beobachtungen; alle sind gruen.

Die Familienmessung trennt erstmals oeffentliche Loaded-Surface, Workbench-
Bootmenge und interne Directory-Namen. Sie trifft die Planprojektion exakt:
loaded `-16/-205 B`, Boot `-23/-296 B`, Directory `-3`; der gebaute
Familiencontainer sinkt um `3326 B`. Die tiefe Artefaktmessung weist loaded
`-488 B` Code und `-1562 B` EXT aus. Das erweiterte v2-LCC-Profil kostet fuer
die neuen Lowerings gegenueber dem Strings-Stand `+33 B` Code und `+117 B`
EXT; diese Kosten liegen ausserhalb Bank 0. Die 555 B bleiben gebankt.

Der historische Runtime-Core-Proof wird nach der Snapshot-Doktrin nicht mehr
gegen das lebende ABI-Ledger revalidiert. Sein Carrier-Archiv bleibt allein
ueber Registereintrag und Archiv-SHA gebunden; das aktuelle System/Runtime-
Gate prueft stattdessen die neuen Quellen und Receipts.

Der unveraenderte Kandidatencommit `9f9d34b` ist als
`dialect-v2-system-runtime-9f9d34b` versiegelt. Das Archiv enthaelt 362
Dateien, verifiziert sich ohne Live-Baum und ist in zwei Bauten byteidentisch
mit SHA `3a226b85ca94e5b2f5979824a1a9caf5c560510048ceba1bec2cbd086c3aed97`.
System/Runtime wechselt danach auf `migrated`, IDE auf `in-progress`.

## 2026-07-13: R2-Stack-Guard klassifiziert; 555-B-Aussage korrigiert

Der rote `make workbench-overlay-stack-guard` ist auf `0b80171` und
`65c28c4` identisch: Das Default-Target bindet noch das generische Vor-v2-
Workbench-Profil und landet bei VMA `0xc3a6`, 80 B ueber `0xc356`. Der
explizit gebundene v2-Target ist dagegen in beiden Staenden gruen. Owner ist
die kanonische Produkt-/Profilverdrahtung; R4 darf erst nach SHA-Paritaet
zwischen Default- und gebundenem v2-Target auf diesen Einstieg zeigen.

Die richtige Profilprobe widerlegt zugleich die zuvor geschriebene Aussage,
die 555 B seien durch System/Runtime unangetastet geblieben. Der gebundene
v2-Link bewegt sich von `0xc22c`/2091 B Reserve auf `0xc2a4`/1971 B:
`+94 B` residenter Text und `+26 B` residentes Read-only-Material, zusammen
120 B. Der Boot-Overlay waechst separat um 81 B. Damit sind aktuell 435 B
beobachtet; fuer die 120 B existiert keine Debit-Autorisierung. Owner ist der
System/Runtime-Promotionsaudit. Exit ist entweder vollstaendiger 120-B-Reclaim
oder eine ausdrueckliche postenweise Debit- und Ledgerentscheidung.

Beide Faelle stehen in `config/r2-known-open.json` mit Owner und
Exit-Kriterien. Directory-only bleibt bis zu ihrer Schliessung ein blockierter
Entwurf. Sein Formatvorschlag behaelt v1-Dekodierung, verwendet in v2
`name_off=0xffff` fuer anonyme Ordinale, materialisiert lokale Entry-Refs zu
BCODE-Immediates und bindet Diagnosen hostseitig ueber Artefakt-SHA plus
Entry-Ordinal. Der vorlaeufige Manifest-Census lautet 100 Directory-only plus
40 bereits inline Helfer, brutto 2006 B Namen.

## 2026-07-13: 120-B-Debit autorisiert; Bank auf 435 B neu gepinnt

Der gemessene System/Runtime-Verbrauch wird nicht reclaimed. Die 120 B kaufen
releasekritische R2-Korrektheits-, Semantik- und Migrationsarbeit; ihr Fehler
war die verspaetete Buchung, nicht die Art der Ausgabe. Die einmalige
rueckwirkende Autorisierung bindet die Attribution `94 B` residenter Text plus
`26 B` Read-only-Material; der separate Boot-Overlay-Anstieg bleibt mit 81 B
sichtbar. Die Produktreserve ist 1971 B, damit sind `1971 - 1536 = 435 B`
gebankt. Diese Heilung ist ausdruecklich kein Praezedenzfall.

Die Verfahrensklasse ist prospektiv geschlossen: Jedes neue Architekturblock-
und Familienpromotionsreceipt besitzt ein Pflichtfeld `bank_delta`. Das Gate
prueft Produkt-SHAs, Reservearithmetik und verlangt fuer jedes negative Delta
eine bereits vorhandene, SHA-gebundene Autorisierung fuer exakt dasselbe
Baseline-/Kandidatenpaar und exakt dieselbe Hoehe.
Null und Rueckgewinn duerfen keine Autorisierung tragen. Die zwei bereits
abgeschlossenen G2-Receipts bleiben als SHA-gepinnte historische Ausnahmen
unveraendert; versiegelte Promotionsarchive werden nicht amendiert.

Der Budget-Known-Open ist damit geschlossen. Der Default-Stack-Guard bleibt
unter dem Owner der kanonischen Produkt-/Profilintegration offen und erhaelt
die harte Frist vor R4-Versiegelung. Directory-only/L65M-v2 ist review-ready;
seine Promotion verlangt weiterhin die Schliessung dieses letzten R2-
Produktlinkfalls und ein `bank_delta` von null oder mit Vorabautorisierung.

## 2026-07-13: Directory-only-Vertrag freigegeben

L65M-v2 verwendet `name_off=0xffff` als dauerhaft unerreichbaren Anonym-
Sentinel; legale Offsets enden bei `0xfffe` und muessen innerhalb der
dekodierten Stringtabelle liegen. v1 weist Sentinel-Eintraege strikt ab und
emittiert nie v2. Lokale Ordinale bleiben containerlokal, waehrend
containeruebergreifende Aufrufe ausschliesslich benannte Exporte verwenden.
Phase 05 enumeriert jeden Entry-Index genau einmal und prueft alle Entry-Refs
gegen `entry_count`. Die Geraetediagnose ist als
`lib <artifact-id> entry #<nullbasierter Ordinal>` gepinnt.

Vor dem ersten Directory-only-Probelink wird die kanonische Stack-Guard-
Verdrahtung geschlossen. Default- und expliziter v2-Target muessen denselben
Artefaktsatz adressieren; ein separater Ausgabepfad ist unzulaessig, weil der
Pfad Teil des ABI-Vertrags und damit der Produkt-Build-ID ist.

## 2026-07-13: Kanonischer Stack-Guard geschlossen

`workbench-overlay-stack-guard` bindet nun v2-Profil, v2-Suite,
v2-Artefaktverzeichnis und den vollstaendigen v2-Define-Satz. Der explizite
Capability-Target verwendet nicht laenger einen zweiten Ausgabepfad: Weil
`product_elf` Teil des auf dem Geraet gebundenen ABI-Vertrags ist, erzeugte
dieser Pfad trotz identischer Codegroesse eine andere Build-ID und damit
andere Produkt-SHAs.

Nach der Vereinheitlichung bestehen beide Vollbauten mit exakt demselben
Artefaktsatz-SHA `9d8e4d0ec888...`. Die Einzelwerte sind PRG
`019bafa46b8d...`, Preload `650b9e062994...`, Runtime-Overlays
`7a28e140daeb...` und ELF `a138165cff9b...`. Beide Links enden bei VMA
`$c2a4`, 1971 B Post-Boot-Reserve und 1751 B Boot-Stack-Gap. Die Bank bleibt
435 B, `bank_delta=0`; der letzte R2-Known-Open und die R4-Frist sind damit
geschlossen.

## 2026-07-13: Directory-only-Probereceipt trifft die Projektion exakt

Die Hostprobe transformiert die frisch gebauten IDE-/IDEX-v1-Container ohne
Aenderung ihrer Codeblobs in strikt versionsgebundene L65M-v2-Artefakte. 87
IDE- und 13 IDEX-Eintraege tragen den Anonym-Sentinel. Alle 252 lokalen
Referenzen materialisieren als Entry-Ref: 248 direkte CALL/TAILCALL-Stellen
und vier bereits vom nativen BCODE-Apply-Pfad getragene Funktionsdesignatoren.

Gemessen entfallen exakt 100 Symbolinternings und 2006 Namepool-Bytes bei null
Directory-Slot-Delta. Das physische Containerdelta ist wegen zweier getrennter
Align2-Pads `-2004 B`. Die projizierte Sessionmarge steigt von 39 auf 139
Symbole und von 490 auf 2496 Namepool-Bytes; 32 Post-Align-Directory-Slots
bleiben stehen. Diagnosemaps binden fuer jeden anonymen Helfer Lib, Ordinal,
Quellpfad und Code-SHA; die Meldungen folgen `lib <id> entry #<ordinal>`.

Das Receipt meldet bewusst `passed-not-promoted`: Es belegt Format, Census und
Hostvalidator, nicht den nativen Loader oder die VM. Der Produktartefaktsatz
bleibt `9d8e4d0ec888...`, die Bank 435 B und `bank_delta=0`. Hier liegt der
vereinbarte Abstimmungshalt vor der Produktimplementierung.

## 2026-07-13: Directory-only/L65M-v2 implementiert; 166-B-Debit autorisiert

Die Produktimplementierung uebernimmt den Probenemitter byteidentisch und
erweitert nativen Validator, Commit-Pfad und VM um strikt versionsgebundene
L65M-v2-Eintraege und lokale Ordinalreferenzen. Alle vier BCODE-
Funktionsdesignatoren bestehen direct/`funcall`/`apply`, insgesamt 12/12
Routen. Die sechs Installations-Negativklassen einschliesslich GC, OOM,
Latch-Recovery und Phasenabbruch sind gruen. Diagnosemaps binden Container-SHA,
Ordinal, Quellpfad und Code-SHA; auf dem Geraet genuegt die globale Meldung
`entry #N`, die Hostmap loest sie eindeutig auf.

Von den 100 anonymen Eintraegen sparen elf wegen vertragsgemaesser
containeruebergreifender Namensreferenzen kein Interning. Sie sind im
Inter-Library-API-Artefakt als Export oder Restrukturierungskandidat
klassifiziert. Netto entfallen 89 Internings und 1793 B Namepool bei null
Directory-Slot-Delta. Ein gezielter Inline-Reclaim liefert weitere zwei
Symbole, 32 B Namepool und 24 B EXT. Der reale Kompositionsstand ist damit
127 freie Symbole, 2279 B Namepool, 32 Post-Align-Slots und exakt 16 KiB
EXT-Headroom.

Der reale Link stoppt die Promotion bei einer residenten Abweichung von 166 B:
163 B Text, 2 B Read-only-Material und 1 B BSS. Der exakte Kandidat
`01fcdddd96ff...` endet bei VMA `$c34a`, 1805 B Reserve und 1585 B
Boot-Stack-Gap. Der vorab gebundene Debit fuer genau dieses Baseline-/
Kandidatenpaar ist genehmigt; die Bank wird von 435 auf 269 B neu gepinnt.
Der Block schliesst mit G2-Receipt und ohne Known Open.

## 2026-07-13: IDE versiegelt; R2 abgeschlossen

Die IDE-Familie trifft ihren Familienvertrag exakt: loaded `-72/-1295 B`,
Boot `-1/-13 B`, Directory `0`, physischer Familiencontainer `-2004 B`.
Beide Compiler-/VM-Engines sind gruen. Commit `4c947e8` ist als
`dialect-v2-ide-4c947e8` versiegelt; das 335-Dateien-Archiv verifiziert sich
aus einem leeren Verzeichnis allein und ist im lebenden Register an SHA
`3f6cc11148307f896ebc5f9ea1f77b89de1575e355d3d3558999f59f8bb85797`
gebunden.

Alle fuenf Familien sind damit `migrated`. Der finale Soll/Ist-Bericht bindet
die fuenf Differentialreceipts und summiert `-124` Loaded-Symbole, `-1783 B`
Loaded-Namepool, `-90` Boot-Symbole, `-856 B` Boot-Namepool und `-39`
Directory-Eintraege; der separat messbare Prelude-Artefakteffekt ist
`-2617 B`.

Der alte Vertragsautomat koppelte die fuenfte Familie unmittelbar an
`ready-for-g5`, obwohl der freigegebene Arbeitsplan R3 (G3/G6), R4 (finale
Produktidentitaet) und erst dann R5 (Verifier-Bindung/G5) vorsieht. Der neue
ehrliche Zwischenzustand ist `r2-complete`: Er verlangt alle Familien, alle
Semantikentscheidungen und den finalen Soll/Ist-Bericht, erlaubt aber die
bewusst noch ungebundenen R5-Verifier. `ready-for-g5` bleibt fail-closed und
verlangt weiterhin deren reale SHA-Bindung. Naechster Block ist R3.

## 2026-07-13: R3-Vertrag und separate Kaltstart-Stager-Probe

R3 pinnt Xemu als Vorfilter und Hardware als Arbiter. Die 15 Bootfaelle tragen
neunmal `emulator-valid` und sechsmal `hardware-only`; G3 darf insbesondere
keine F011-, SD-Puffer-, DMA-Timing- oder physische Reset-Aussage erben. Der
Ein-Laufwerk-Vertrag bootet `L65SYS,65` auf Laufwerk 8, laedt die permanente
Komposition und wechselt dann einmal auf `L65WORK,65`. Laufwerk 9 bleibt
explizit abgelehnter Nicht-Scope. Produktmedienidentitaet, SHA-gebundener
Mount-Schreibschutz und der M65D-Identitaetscheck vor Write und Directory-
Publish bilden unabhaengige Schutzschichten.

Der Kaltstart-Stager ist ein eigenes verkettetes Artefakt vor der Workbench.
Die Strukturprobe baut einen 128-B-Stager sowie deterministische Produkt- und
Work-D81-Abbilder. Im ersten Lauf blieben alle bisherigen Produktartefakte
byteidentisch zum Produkt-SHA `01fcdddd96ff...`; die Bank blieb 269 B,
`bank_delta=0`. Der
strukturelle Artefaktsatz `10dc1e4dd2c7...` ist eine neue, nicht promotete
Probenidentitaet. Das Receipt steht bewusst auf `passed-not-implemented`:
Loader, Autoboot, G3 und G6 sind nicht ausgefuehrt. ROM, xmega65 und SD-Basis
sind fuer den realen Lauf separat SHA-gebunden; Hardware-Receipts muessen
zusaetzlich Maschine, Core und physische Cycle-ID binden.

Der unmittelbar anschliessende frische kanonische Neubau hat diese
Byteidentitaet nicht reproduziert und den Block deshalb vor Promotion
gestoppt. Alle fuenf Artefaktlaengen, VMA `$c34a`, 1805 B Reserve, 1585 B
Boot-Stack-Gap und die 269-B-Bank sind identisch; die Artefakt-SHAs ergeben
aber den Produkt-SHA `da4c72a2254a...`. Die IDE-/IDEX-/M65D-Container bleiben
exakt, und zwischen dem Directory-only-Commit und HEAD gibt es keine relevante
Produktquelldifferenz. Der Befund ist daher als vorbestehende kanonische
Rebuild-Identitaetsdrift klassifiziert, nicht als R3-Bank- oder Layoutkosten.
G3/G6 bleiben `not-run`; die Baseline-Entscheidung war der neue Review-Halt.

Das anschliessende Archiv-Audit fand die `01fcdddd...`-Produktbytes weder im
Dateiinventar noch in den eingebetteten D81s; das R2-Siegel hatte nur die
Receipts und SHAs materialisiert. Zwei getrennte frische Clones von
`99634e79f33...` wurden daraufhin mit verschiedenen Python-Hashseeds,
Zeitzonen, Kalendertagen und `SOURCE_DATE_EPOCH`-Werten gebaut. Beide liefern
byteidentisch `da4c72a2254a...`, den achtteiligen Artefaktsatz
`06bc10b9a618...` und dieselben Linkmetriken. Aktive Nichtdeterministik ist
damit nicht beobachtet; die Ursache ist eine R2-Provenienzluecke zwischen
lebendem Buildzustand und Siegel.

Der Identitaetsuebergang ist mit `bank_delta=0` akzeptiert. R2 bleibt
historisch an `01fcdddd...`, R3 startet reproduzierbar an `da4c72a2...`. Die
neu erzeugte Strukturprobe bindet den Release-Artefaktsatz `68feec451d27...`
und bleibt `passed-not-implemented`. Die Promotionspolicy v2 verlangt ab jetzt
vor jedem Siegel den variierten Frischclone-Doppelbau und bettet Receipt sowie
alle Produktbytes selbst ein; externe Produkt-SHA-Bindungen sind unzulaessig.

## 2026-07-13: R4-Produktkandidat versiegelt

G3 schliesst fuer den Produktartefaktsatz `d63fd2cb43c1...` mit exakt neun von
neun `emulator-valid`-Faellen. Alle sechs `hardware-only`-Faelle bleiben
ausdruecklich `not-run`; F011-, SD-Puffer-, DMA-Timing- und physische
Reset-Aussagen sind ausgeschlossen. G5 und G6 sind offen, der Kandidat ist
versiegelt, aber nicht releasefaehig.

Der neue Archivtyp `product-candidate` verhindert eine falsche Einordnung als
Familie oder Capability-Carrier. Der finale Cut `8c99a6649326...` wurde in
zwei getrennten, in Hashseed und Zeitkontext variierten Clones gebaut. Beide
Bauten liefern alle 13 Produktartefakte byteidentisch mit Build-ID `fa377c50`;
gegenueber dem vorherigen Doppelbau aenderte sich nur der gebundene
Source-Commit. Harness-, Evidenz- und Versiegelungsarbeit bewegen die
Produktbytes damit nachweislich nicht.

Das Archiv `r4-product-candidate-8c99a66.tar.gz` materialisiert 108 Dateien
einschliesslich aller 13 Produktbytes und der vollstaendigen G3-Rohevidenz.
Es wurde zweimal byteidentisch mit SHA `8ca3992ee202...` erzeugt und aus einem
leeren Verzeichnis ohne Repository oder Netz erfolgreich verifiziert. Ein
historischer R3-Vertrag bindet am lebenden Receipt-Pfad noch den vorherigen
Doppelbau-SHA; das Siegel materialisiert dort das aktuelle Receipt und fuehrt
den alten Bytezustand ehrlich als externe Content-Bindung fort. Das lebende
R3-Vorlaufreceipt bleibt an seinem historischen Pfad unveraendert; der finale,
an `8c99a664...` gebundene Doppelbaubeleg lebt im R4-Siegel.

R5 konsumiert ausschliesslich dieses registrierte R4-Siegel als
Produktidentitaet. `config/r5-global-g5-contract.json` stand deshalb zunaechst
auf `input-bound-preflight-not-run`; der lebende Baum besitzt keine
Produktautoritaet. Erst der statische globale Preflight durfte die 14-Faelle-
Matrix und vier physischen Power-Cycles freigeben.

## 2026-07-13: R5-Static-Preflight bestanden, Hardware nicht gelaufen

R5 materialisiert die 13 Produktartefakte ausschliesslich aus dem registrierten
R4-Archiv und rekonstruiert deren Set-SHA `d63fd2cb43c1...` vor jedem
Matrixfall. Runtime Core und die Persistenz-Helfer bilden eine getrennte
Test-Closure; byteidentische Ueberschneidungen
mit den 13 Produktmitgliedern sind als Gate verboten und betragen null.
Harness-Aenderungen erfordern ein neues Closure-Inventar und die Offline-
Neuverifikation bereits bestandener Receipts; ein Produkt-SHA-Delta verwirft
alle Faelle und verlangt ein neues R4-Siegel.

Der neue Workbench-Verifier ist fuer beide Workbench-Domaenen negativ
geprueft. Je Domaene werden veraenderte Artefaktbytes, ein semantisch
verfaelschtes Roh-Oracle mit aktualisiertem SHA und eine falsche
Produktidentitaet abgelehnt: 6/6 Mutationen rot. Der Static-Preflight loest
alle 14 Zielrezepte samt drei SHA-gebundenen Domain-Verifiern und allen
referenzierten Closure-Dateien auf. Sein versioniertes Receipt meldet
`hardware_side_effects=none`, G5/G6 `not-run` und `release=not-release-capable`.
Erst jetzt duerfen die 14 physischen Faelle und vier echten Power-Cycles
beginnen.

Ein absichtlich wiederholter Preflight-Bau fand zuvor fluechtiges `built_at`
im Runtime-Footprint: Produktbytes und Carrier-Binaerdateien waren identisch,
aber das Test-Closure-Inventar driftete. Der Footprint respektiert deshalb nun
`SOURCE_DATE_EPOCH`, gebunden an den R4-Commit. Zwei isolierte Runtime-Carrier-
Bauten muessen seither vor jedem R5-Preflight vollstaendig byteidentisch sein;
der einmalige Diagnosefund ist damit ein stehendes Gate geworden.

## 2026-07-13: R5-Ausfuehrungsschicht geschlossen, Preflight erneut bestanden

Der erste statische R5-Uebergang fand vor dem Hardwarelauf eine fehlende
Verdrahtung: Die 14 Targets erzeugten zwar verifizierbare Rohbelege, aber noch
keine normierten Fall-Receipts. `r5_g5_case_receipts.py` schliesst nur diese
Luecke. Der Transformator schreibt keine neuen Formate, sondern erzeugt das
bereits definierte native Workbench-Receipt beziehungsweise bindet das vom
Runtime-Verifier selbst erzeugte native Receipt in das bestehende
`lisp65-dialect-v2-*-g5-case-evidence-v1` ein. Beide Schichten werden sofort
offline verifiziert; ohne erfolgreiches Fall-Receipt kann kein Target gruen
enden.

Produkt- und Harness-Rot sind getrennt: Die Targets melden
`R5_PRODUCT_RESULT=FAIL`, bevor ein Packer laeuft; Verpackungs- oder
Verifierfehler melden `R5 receipt chain: FAIL kind=harness`. Receipt-Bundles
sind an die Test-Closure-Generation gebunden. Bei einem reinen Harness-Fix
duerfen bereits bestandene, SHA-gebundene Fall-Receipts unter der neuen Closure
offline neu verifiziert werden. Unreceipted Rohbelege sind nie promotionsfaehig
und werden nicht nachtraeglich zu Beweisen verpackt. Bestehende Bundles werden
nie ueberschrieben.

Die Fall-Receipts benoetigten den schon normierten, aber bislang nicht
materialisierten finalen Dialektvertrag. Er ist nun unter
`config/dialect-v2-contract.json` mit 126 oeffentlichen Namen und SHA
`509930882af9...` gebunden; sein Definitionsmanifest klassifiziert 17 native
Primitives, 18 Makros und 91 Funktionen aus den abgeschlossenen R2-
Entscheidungen. Das Profil bleibt bis zum bestandenen G5 weiterhin fail-closed
auf Dialekt v1.

Der wiederholte Preflight deckte ausserdem eine reine Harness-
Nichtdeterministik auf: Ein aus einem Make-Target gestartetes untergeordnetes
`make -n` erbte `MAKEFLAGS/MAKELEVEL`, waehrend der direkte Offline-Verifier
dies nicht tat. Die Rezeptprojektion entfernt diese Elternprozessvariablen
nun explizit. Danach ist der vollstaendige Preflight erneut gruen: 14/14
Target→Rohbeleg→natives Receipt→Fall-Receipt→Verifier, 6/6 Negativmutationen,
80 SHA-inventarisierte Test-Closure-Mitglieder, Closure-Set
`31e5fff35db3...`, Candidate-SHA `0e62f80a4248...` und versioniertes
Preflight-Receipt `79dfbba25874...`. Produktset `d63fd2cb...` blieb
unveraendert; Hardware wurde nicht beruehrt, G5/G6 bleiben `not-run`.

Der anschliessende erste BAM-Read-Anlauf stoppte vor jeder semantischen
Ausfuehrung: Der verifizierte Input-Screen zeigte noch BASIC, waehrend der
fail-closed Clear-Screen kurz darauf den leeren `lisp65>`-Prompt zeigte. Das
ist ein Transport-/Boot-Timingfall, kein BAM- oder Produktbefund; ein
Fall-Receipt wurde folgerichtig nicht erzeugt. Der offizielle Lauf verwendet
deshalb die frische Evidenzgeneration `r5-run-20260713-02`, pinnt die
Workbench-Bootwartezeit auf 8 s und fuehrt BAM-Read mit dem alten
Diagnoseverzeichnis nur als Ledgerbefund der vorherigen Closure fort. Der
anschliessende FTP-Ausfall im aktuellen Kandidaten geschah ebenfalls vor
Deploy und Semantik; genau dessen frisches Verzeichnis wird als
`transport-failure-before-semantic-execution` im nativen Receipt gebunden.
Da Makefile und damit die Test-Closure geaendert wurden, ist vor dem zweiten
Versuch ein neuer vollstaendiger Static-Preflight Pflicht.

## 2026-07-13: BAM-Read-Orakel an Testmedium gebunden

Der nach dem Power-Cycle gestartete zweite BAM-Read-Versuch erreichte erstmals
die semantische Ebene. Core-Arithmetik und T40/S1 waren exakt gruen; T40/S2
lieferte `(t 0 255 0 38)` statt des im Runner verbliebenen Carrier-Orakels
`(t 0 255 0 39)`. Die lesende Hostdiagnose zeigte, dass das vom R5-Harness
SHA-gebundene Workbench-Testmedium selbst an dieser Stelle 38 traegt und die
zugehoerige Bitmap ebenfalls exakt 38 freie Sektoren enthaelt. Die Maschine
hat das Medium korrekt gelesen; rot war das historische Harness-Orakel, nicht
das Produkt.

Der Korrekturschnitt bindet die BAM-Werte nun konstruktiv an das tatsaechlich
hochgeladene D81. Der HW-Runner leitet beide Ergebnisformen aus dessen Bytes
ab; das native Fall-Receipt nimmt das D81 als Rohartefakt auf; der Offline-
Verifier prueft dessen SHA zusaetzlich gegen `workbench-test-d81` der
Kandidaten-Test-Closure, fuehrt die BAM-Sanity aus und rekonstruiert die
erwarteten Ergebnisformen selbst. Der Static-Preflight versiegelt Medien-SHA
und beide abgeleiteten Orakel. Damit kann ein spaeteres, gueltiges D81-Layout
nicht erneut an einer Zahl aus einem aelteren Carrier scheitern.

Der fehlgeschlagene Lauf bleibt Diagnose und wird nicht nachtraeglich
verpackt. Die frische Evidenzgeneration ist `r5-run-20260713-03`. Ihr
14-Faelle-Preflight steht bei unveraendertem Produktset `d63fd2cb...` auf
Test-Closure `dca334941404...`, Candidate `dfdcef3498b3...` und versioniertem
Preflight-Receipt `ea5f2bb4fef9...`. Das BAM-Medium ist `928af5424ebc...`,
seine gepinnten Orakel sind S1 `(t 40 2 40 35)` und S2
`(t 0 255 0 38)`. G5/G6 bleiben `not-run`; BAM-Read muss nach einem weiteren
physischen Neustart als fehlender Fall erneut laufen und sofort ein Receipt
erzeugen.

## 2026-07-13: ABI-4-Batchregression vor G5 geschlossen

Der Lauf `r5-run-20260713-04` erzeugte sieben sofort offline verifizierte
Workbench-Fallreceipts fuer das historische R4-Produktset `d63fd2cb43c1...`.
Der achte Fall `overlay-stack-guard` bestand Produkt-SHA-Readback,
Reset/Remount und Arithmetik, ueberschritt aber beim ersten `(load-lib
"ide")` das gepinnte 12-Sekunden-Laufzeitgate. Auch nach 48 Sekunden blieb
der Commit in Phase 3 bei Cursor 28 aktiv. Das ist ein Produktbefund, kein
Harnessbefund; fuer den roten Fall entstand folgerichtig kein Receipt.

Die gebundene ELF-Diagnose lokalisierte den Fehler in
`vm_l65m_batch_repeat`: Der L65M-v2-Commitkontext meldet ABI 4, waehrend das
handgeschriebene Prädikat noch `cmp #$03` aus der ABI-3-Zeit enthielt. Dadurch
war der vorhandene Batchpfad still deaktiviert und der Commit fiel auf die
pro Eintrag bezahlte Overlay-Uebertragung zurueck. Der 12-Sekunden-Guard hat
damit eine semantisch gruene, aber vierfach zu langsame Produktregression beim
ersten Hardwarekontakt des ABI-4-Pfads gestoppt.

Die Reparatur ersetzt nicht nur das einzelne Literal. Eine gemeinsame
C-Quelle erzeugt 13 Assemblerwerte fuer alle gefundenen Sprachgrenzen:
L65M-Batch-ABI, Slotbasen und Struct-Offets sowie R3-Stager-Jobadresse und
Produkteinstieg. Das stehende Inventargate klassifiziert alle drei
Assemblerquellen; die MEGA65-Mathematik bleibt unter ihrem eigenen
Disassembly-/Oracle-Gate, waehrend neue unklassifizierte Assemblerdateien,
rohe numerische Spruenge oder neue nicht inventarisierte Immediates den Build
stoppen. Der Commitzweig disassembliert jetzt konstruktiv zu `cmp #$04`.

Der reale Probelink bleibt bei 44.618 B Linked-PRG, 39.564 B Resident-PRG,
VMA `$c34a`, 1.805 B Post-Boot-Reserve, 269 B Bankmarge und 1.669 B
Boot-Overlay. Auch EXT 16.439 B, 121 Symbole, 2.162 B Namepool und 32
Directory-Slots bleiben identisch: `bank_delta=0`, `boot_overlay_delta=0`,
alle fuenf Kapazitaetsdimensionen null. Neben dem reparierten Opcode bewegen
sich gebundene Build-ID/CRC-Bytes, weil der neue Generator selbst in die
Produktprovenienz eingeht; das ist Identitaetsdelta ohne Groessen- oder
Kapazitaetsdelta.

Damit verlieren die sieben alten Fallreceipts nichts von ihrem historischen
Wert, sind aber fuer die neue Produktidentitaet nicht uebernehmbar. Der
weitere Pfad ist fail-closed: variierter Doppelbau, neue R3/G3-Bindung, neues
R4-`product-candidate`-Siegel, neuer statischer R5-Preflight und danach alle
14 Hardwarefaelle mit vier frischen Power-Cycles. Bis dahin bleiben G5, G6
und Release offen.

Der anschliessende variierte Doppelbau schliesst sowohl den achtteiligen
Kernsatz `1501d4d6dd09...` als auch den vollstaendigen 13-Artefakt-Satz
`d92b0aace122...` byteidentisch ueber verschiedene Hashseeds, Zeitzonen und
Zeitkontexte. Die neue Produkt-Build-ID ist `2371a2c9`. Stager, Deskriptor,
beide D81-Abbilder und Mount-Descriptor stimmen in beiden Frischclones
ueberein; die Kompositionsmargen bleiben 269 B Bank, 16.439 B EXT, 121
Symbole, 2.162 B Namepool und 32 Directory-Slots.

G3 wurde gegen exakt dieses neue Set vollstaendig wiederholt und schliesst
erneut mit 9/9 `emulator-valid`. Alle sechs `hardware-only`-Faelle bleiben
ausdruecklich `not-run`; F011-, SD-, DMA- und physische Reset-Aussagen sind
weiter ausgeschlossen. Das R4-Assertionsobjekt ist damit fuer ein neues,
separates `product-candidate`-Siegel freigegeben. Das alte R4-Archiv bleibt
unveraendert und historisch an `d63fd2cb...` gebunden.

## 2026-07-13: ABI-4-R4 neu versiegelt und R5 statisch neu gepinnt

Der finale ABI-4-Produktcut `5e1314f746e7...` ist als separates
`product-candidate`-Archiv `r4-product-candidate-5e1314f` versiegelt. Es
enthaelt 113 selbststaendig pruefbare Dateien und alle 13 Produktartefakte des
Sets `d92b0aace122...`; sein Archiv-SHA ist `bc05335bcac6...`. Die isolierte
Offline-Verifikation ist gruen, und ein zweiter Archivbau ist byteidentisch.
Das fruehere R4-Siegel bleibt unveraendert und wird nicht umetikettiert.

R5 materialisiert den neuen Kandidaten ausschliesslich aus diesem registrierten
Archiv. Der statische Preflight fuer `r5-run-20260713-05` bindet die
Produkt-SHA `d92b0aac...`, Candidate `d00aabcd...`, 80 getrennte
Test-Closure-Artefakte als Set `d7dc282c...` und null Ueberlappung zwischen
Produkt- und Testmenge. Der Runtime-Carrier-Doppelbau ist byteidentisch; alle
sechs absichtlich manipulierten Workbench-Evidenzen werden abgelehnt.

Alle 14 Matrixketten sind vor dem ersten Hardwarefall vollstaendig von Target
ueber Rohbeleg und natives Receipt bis zum normierten Fall-Receipt und seinem
Offline-Verifier gebunden. Das getrackte Preflight-Receipt hat SHA
`4a3a3b23746f...` und meldet ausdruecklich `hardware=not-run`, G5/G6
`not-run`, Release nicht freigegeben. Die sieben alten Fallreceipts gegen
`d63fd2cb...` bleiben historische Evidenz und werden nicht uebernommen. Fuer
den neuen Produkt-SHA laufen alle zehn Workbench- und vier Runtime-Faelle
frisch; die Runtime-Faelle verlangen vier eigene physische Power-Cycles.

## 2026-07-13: R5-Boot-Wait per Fix-forward geschlossen

Der erste frische Hardwarefall `overlay-stack-guard` bestand nach einem
zulaessigen Etherload-Retry alle Produktorakel. Insbesondere schloss
`(load-lib "ide")` in rund 9,3 Sekunden unter dem gepinnten
12-Sekunden-Gate; Bytecode-Kind, VM-Bruecken, GC und Reader-Recovery waren
gruen. Sein Fall-Receipt wurde sofort offline verifiziert.

Der folgende Fall `stdlib-runtime` fand vor der semantischen Ausfuehrung eine
Harnessluecke: Der Target setzte `BOOT_WAIT_SEC=8`, konsumierte den Wert aber
nicht und begann 12 ms nach dem Etherload-Reset mit der JTAG-Eingabe. Der
fehlgeschlagene Rohbeleg erhielt kein Receipt. Der Fix fuegt genau den
versprochenen Acht-Sekunden-Wait zwischen Produktstart und erster Eingabe ein.
Produktset und R4-Siegel bleiben unveraendert.

Weil das Makefile zur Test-Closure gehoert, wurde R5 regelgemaess statisch neu
gepinnt. Die neue 80-teilige Closure ist `a9f0b2b665af...`, der Candidate
`30dcff3dd7dd...` und das Preflight-Receipt `6d9cdd14d240...`; 14/14 Ketten
und 6/6 Negativmutationen sind erneut gruen. Das bestandene Overlay-Receipt
wurde aus seinen unveraenderten Rohbelegen offline gegen die neue Closure
re-verifiziert, nicht auf Hardware wiederholt. Die uebrigen Faelle bleiben
offen, G5/G6 und Release bleiben gesperrt.

## 2026-07-13: R5-Harness respektiert Directory-only konstruktiv

Nach dem Boot-Wait-Fix bestand `stdlib-runtime` auf Hardware und erhielt ein
sofort offline verifiziertes Fall-Receipt. Der folgende Fall `ux-complete`
bestand Arithmetik, IDE-Load unter dem Laufzeitgate und Bytecode-Kind, stoppte
aber am ersten Persistenzaufbau mit `vm: undefined function`. Der Rohbeleg
besitzt kein Receipt; die sieben nachfolgenden Persistenzfaelle wurden nicht
gestartet.

Die versiegelten R4-Manifeste lokalisieren den Befund eindeutig im Harness:
Der UX-Smoke rief `%ide-store-buffer` direkt auf, obwohl dieser Helfer seit
Directory-only anonym und nur containerintern ordinal erreichbar ist. Drei
weitere anonyme IDE-Helfer wurden im selben Skript direkt referenziert. Das
Produkt und seine Persistenzsemantik waren an dieser Stelle noch nicht
ausgefuehrt und bleiben unveraendert.

Der Fix ersetzt diese privaten Aufrufe durch kleine, nach jedem Deploy neu
installierte REPL-Testhelfer, die ausschliesslich die oeffentliche IDE-
Oberflaeche und den gebundenen Sessionzustand verwenden. Die Klasse wird
zusaetzlich statisch geschlossen: Der R5-Preflight liest die anonymen
Funktionsnamen direkt aus den drei im R4-Siegel eingebetteten Library-
Manifesten und lehnt direkte, `function`-, `funcall`- und `apply`-Designatoren
aus jedem gebundenen Harness-Skript ab. Der Negativselbsttest weist alle vier
Ablehnungsformen fuer einen manipulierten `%ide-store-buffer`-Aufruf nach.
Aktuell sind 102 eindeutige anonyme Namen gegen zehn Skripte geprueft, mit
null Treffern.

Weil Skript und Preflight-Tool zur Test-Closure gehoeren, wurde sie neu
gepinnt. Beim anschliessenden Hardware-Retry antwortete die Maschine dreimal
vor semantischer Ausfuehrung nicht auf die automatische Ethernet-Discovery,
waehrend ein expliziter Link-Local-Handshake sofort gelang. Die acht
gebundenen Workbench-Hardware-Skripte uebernehmen deshalb jetzt den bereits im
Releasepfad dokumentierten `MEGA65_IP`-Override; ein explizites `--ip` bleibt
vorrangig. Das schliesst den Transportbefund fuer alle verbleibenden Faelle,
nicht nur fuer UX.

Der erste Lauf mit expliziter Adresse erreichte das Produkt und installierte
drei der neuen Testhelfer. Der vierte `defun` ueberschritt jedoch das
verifizierbare aktive JTAG-Echofenster und wurde vor Ausfuehrung verworfen.
Auch das ist ein reiner Harnessbefund ohne Receipt. Der Zustandsersatz wird
nun direkt mit `cons` formuliert; fuer den Dokumenttest bleibt ein kurzer
Session-Setter, dessen Eingabe vollstaendig echo-verifizierbar ist.

Der folgende Vollanlauf bestaetigte die vier Sessionhelfer und erreichte den
ersten echten Persistenzaufruf. Dessen Eingabe war vollstaendig
echo-verifiziert; der Abschluss-Screenshot kam jedoch vor Ergebnis und Prompt.
Eine spaetere passive Aufnahme zeigte exakt `(t nil bytecode)`. Der Befund ist
damit ein gemessener Harness-Timingfehler, kein Produktfehler. Create,
zweites Create und Replace erhalten ein explizites 20-Sekunden-
Abschlussbudget, das der Harness-Selbsttest festhaelt.

Die finale 80-teilige Closure ist `37f1ac92e95d...`. Candidate
`ab68f63d2e16...`, 14/14 statische
Ketten, 6/6 Verifier-Negativmutationen und das getrackte Preflight-Receipt
`ec18b1644bb3...` sind gruen; das 13-Artefakt-Produktset bleibt exakt
`d92b0aace122...`. Die bestandenen Receipts fuer `overlay-stack-guard` und
`stdlib-runtime` wurden aus ihren unveraenderten Rohbelegen offline unter die
neue Closure ueberfuehrt. Der Stand ist damit ehrlich 2/14; G5, G6 und Release
bleiben offen.

## 2026-07-13: L65M-v2-Exportpublikation und Late Binding strukturell korrigiert

Der folgende `ux-complete`-Lauf erreichte die reale IDE+IDEX-Komposition und
fand einen Produktfehler im neuen L65M-v2-Emitter: Alle elf bereits als
Inter-Library-API klassifizierten Exporte waren weiterhin anonym. Zusaetzlich
wurde der Override-Hook `%ide-x` in IDE und IDEX als lokaler Entry-Ref
verdichtet. Damit blieb zwar sein Ordinal aufloesbar, die spaet geladene
IDEX-Definition konnte aber die bereits frueh gebundenen IDE-Aufrufe nicht
ersetzen. Der Fall stoppte vor Persistenzabschluss und besitzt kein Receipt.

Die Korrektur ist kein `%ide-x`-Sonderfall. `late_bound_exports` ist jetzt ein
allgemeiner L65M-v2-Vertragsbaustein: Exporte werden immer benannt publiziert;
normale lokale Exporte duerfen weiterhin ordinal gebunden werden, explizit
spaet gebundene Exporte behalten dagegen ihre symbolischen Call- und
Designator-Knoten. `override_exports` ist konstruktiv eine Teilmenge davon.
Der Hook-Audit ueber die reale IDE/IDEX-Definitionsmenge findet exakt einen
Ueberlapp, `%ide-x`, und null undeklarierte Hooks.

Drei Gates schliessen die Fehlerklasse: `exports ∩ anonymous = ∅`, jeder
Override ist in Provider und Overrider benannt, und auf spaet gebundene
Exporte existiert keine Entry-Ref-Kante. Der native Produktpfad laedt die
reale residente v2-Closure, committet IDE, prueft die Kernfunktionszelle,
committet IDEX, fordert einen Zellwechsel und beobachtet anschliessend exakt
`M-x [find-file]`. Der Hardware-UX-Fall prueft denselben Wechsel unmittelbar
nach IDEX-Load und meldet bei Rueckfall explizit `hook not overridden`.

Die Probe misst IDE mit 76 und IDEX mit 15 anonymen Eintraegen; alle elf
Exporte sind benannt. Gegen den wiedereroeffneten R4-Stand kostet die
Korrektur exakt ein Symbol und sieben Namepool-Bytes. Es bleiben 120 Symbole,
2.155 B Namepool, 32 Post-Align-Slots und 16.439 B EXT; EXT und Directory
haben Delta null. Fuer Bank und Boot-Overlay ist Delta null vorgepinnt, der
reale Neulink steht aber noch aus. Da die beiden Library-Container Produktartefakte
sind, verlieren die zwei bestandenen `d92b0aac...`-Receipts keine historische
Gueltigkeit, sind aber nicht uebernehmbar. Der Pflichtpfad ist variierter
Doppelbau, R3/G3, neues R4-Siegel, vollstaendiger R5-Preflight und danach
14 frische Hardwarefaelle mit vier frischen Runtime-Power-Cycles.

Der anschliessende reale Produktlink bestaetigt den Preiszettel. Das
Workbench-PRG bleibt bei 39.564 B, der Boot-Overlay bei 1.669 B, die
Post-Boot-Reserve bei 1.805 B und der Boot-Stack-Gap bei 1.585 B. Damit sind
`bank_delta=0` und `boot_overlay_delta=0` real gemessen. Die Komposition
schliesst mit 16.439 B EXT, 120 Symbolen, 2.155 B Namepool und 32 Directory-
Slots. Zwei in Clone, Hashseed, Datum und Zeitzone variierte Vollbauten sind
fuer alle 13 Produktartefakte byteidentisch; das neue Set ist
`20760405e10f...`, die Build-ID `d46a2bab`.

Der neu gebundene R3-Static-Preflight umfasst erneut exakt neun
`emulator-valid`- und sechs `hardware-only`-Faelle. Alle 15 stehen noch auf
`not-run`; insbesondere erzeugt der Doppelbau keinen G3-, Hardware- oder
Releaseclaim. Naechster Schritt ist der vollstaendige G3-Neunerlauf gegen
genau dieses Set.

Dieser Neunerlauf ist abgeschlossen. Alle neun `emulator-valid`-Faelle
bestehen gegen `20760405e10f...`; alle sechs `hardware-only`-Faelle stehen
weiter unveraendert auf `not-run`. Damit sind Autoboot-Kontrolle,
Deskriptorvalidierung, Restage-Entscheidung, Re-Verifikation vor dem Ketten und
die Medien-Policy erneut vorgefiltert. Der Lauf macht weiterhin keine Aussage
ueber F011-, SD-, DMA- oder physische Reset-Semantik. R4 ist fuer ein neues,
separates Produktkandidatensiegel vorbereitet.

## 2026-07-13: Late-Binding-R4 versiegelt und R5 bei 0/14 neu gepinnt

Der finale R4-Cut `312d5abfc920...` reproduziert trotz variierter Clone-,
Hashseed-, Datums- und Zeitzonenumgebung alle 13 Produktartefakte
byteidentisch. Das Produktset bleibt `20760405e10f...`, die Build-ID
`d46a2bab`. Das neue Archiv
`r4-product-candidate-312d5ab.tar.gz` besitzt SHA
`6a67427644c865f9dbe78978656ab8594b1dc32ec73858844b1269a304b4707a`,
enthaelt 115 Dateien einschliesslich der 13 Produktbytes und verifiziert sich
isoliert offline. Ein zweiter Archivbau ist byteidentisch. Das Siegel bindet
G3 9/9 `emulator-valid`, Hardware 0/6, G5/G6 `not-run` und
`not-release-capable`; alle frueheren R4-Archive bleiben unveraenderte
historische Belege ihrer jeweiligen Produktidentitaet.

R5-Lauf `r5-run-20260713-06` konsumiert ausschliesslich dieses registrierte
R4-Siegel. Vor Hardware wurden die 13 Artefakte mit Set-SHA
`20760405e10f...` materialisiert und verifiziert. Die getrennte 80-teilige
Test-Closure ist `226a2cfd03b6...`, besitzt null Produktueberlappung und bindet
Candidate `0f14609765ac...`. Das Directory-only-Gate prueft 91 anonyme
Eintraege aus den versiegelten IDE-/IDEX-/M65D-Manifesten gegen zehn
Harness-Skripte und findet null Referenzen. Alle sechs manipulierten
Verifier-Eingaben werden abgelehnt; alle 14 Ketten Target -> Rohbeleg ->
Fall-Receipt -> Verifier sind statisch bereit. Das getrackte
Preflight-Receipt ist `95b1cbfb638c...`.

Der Produkt-SHA-Wechsel verbietet jede Receipt-Uebernahme. Der Stand ist
deshalb bewusst 0/14 Hardware: Als Naechstes laufen alle zehn
Workbench-Faelle frisch; danach verlangen die vier Runtime-Faelle je einen
eigenen neuen physischen Power-Cycle. G5, G6 und Release bleiben bis zu diesen
Beweisen fail-closed.

## 2026-07-13: R5-Fix-forward schliesst das aktive Echo-Fenster

Die ersten beiden frischen Faelle von `r5-run-20260713-06`,
`overlay-stack-guard` und `stdlib-runtime`, bestanden auf Hardware und wurden
sofort offline verifiziert. `ux-complete` bestaetigte danach Create, Read,
Replace, Remount/Reset und beide Higher-Order-Oracles. Die neue fruehe
IDEX-Hook-Assertion wurde jedoch in allen drei Eingabeversuchen am selben
letzten Wrap abgeschnitten. Das aktive Echo stimmte nicht vollstaendig, Enter
wurde nie gesendet und der Hook-Ausdruck nie ausgefuehrt. Der Fall besitzt
kein Receipt; dies ist ein Harness-, kein Produktbefund.

Der identische Oracle ist nun in drei kurze, jeweils echo-verifizierte Formen
zerlegt: State bauen, `%ide-x` aufrufen, Message `1005` als
`idex-hook-overridden` pruefen. Ein ausgefuehrtes falsches Ergebnis bleibt
Status 4 und Produktfehler. Nicht ausgefuehrte Status 5/6/124 werden dagegen
explizit als `receipt chain: FAIL kind=harness` klassifiziert. Der
UX-Harness-Selbsttest beweist beide Fehlerklassen und den Vollpfad.

Die Test-Closure wurde ohne Produktueberlappung auf `1c15cf3e3a48...`
neu gepinnt; Candidate ist `8759f1313ad5...`, das statische Preflight-Receipt
`b97a6e78be35...`. Alle 14 Ketten und 6/6 Negativmutationen sind erneut
gruen. Die zwei bestandenen Rohbelege wurden unter der neuen Closure offline
re-verifiziert. Der ehrliche Stand bleibt deshalb 2/14; nur der fehlende
UX-Fall wird wiederholt.

## 2026-07-13: Globale G5-Matrix 14/14 als Hardwareabnahme versiegelt

R5-Lauf `r5-run-20260713-06` ist auf dem finalen Produktset
`20760405e10f024c9d0922885093f812d2aa929a097e48095ed669227c7f8ae0`
vollstaendig hardwaregruen. Zehn Workbench- und vier Runtime-Faelle besitzen
je genau ein SHA-gebundenes, offline verifiziertes Fall-Receipt. Die vier
Runtime-Faelle binden vier unterschiedliche physische Cycle-IDs. Gegenueber
dem R4-Produktkandidaten wurden keine Produktbytes und keine der fuenf
Kapazitaetsdimensionen bewegt.

Der neue Promotionsarchivtyp `hardware-acceptance` versiegelt genau diesen
Beweisgegenstand, ohne ihn als Familie oder Produktkandidat umzudeuten. Archiv
`r5-global-g5-e247b06.tar.gz` hat SHA
`af07b7c497d09fdfc1ddab825342d10a7eb093605142752d0d073fc533d660f6`,
enthaelt 191 Dateien einschliesslich aller 13 Produktbytes, der kompletten
80-teiligen Test-Closure, der 14 Receipt-Ketten und ihrer Rohbelege. Zwei
Packlaeufe sind byteidentisch; der eingebettete Standardbibliotheks-Verifier
arbeitet aus einem leeren Verzeichnis ohne Repository oder Netzwerk. Drei
Manipulationen an Produktbyte, Fall-Receipt und Top-Receipt werden abgelehnt.

Der Claim lautet eng: G5 `passed` fuer Produktset `20760405...`; G6 und alle
sechs Hardware-Bootfaelle `not-run`; nicht releasefaehig. Der optionale finale
Ein-Zeremonie-Neulauf wird im stehenden Promotionsvertrag dauerhaft als
verzichtbar markiert. SHA-gebundene Fall-Receipts mit Cycle-IDs sind das
Beweisobjekt; eine gemeinsame Wiederauffuehrung erzeugte keine zusaetzliche
Evidenz. R6 darf nur die versiegelten R4-/R5-Objekte konsumieren.

## 2026-07-13: R6 materialisiert das versiegelte Produkt als Zwei-Medien-Ship

Der R6-Packer ist eine reine Transformation. Er konsumiert ausschliesslich
die registrierten Archive `r4-product-candidate-312d5ab` und
`r5-global-g5-e247b06`; Compiler, Linker und Disk-Builder sind nicht Teil des
Pfads. Alle 13 Produktartefakte werden byteidentisch aus R5 kopiert, waehrend
G3-Receipt und 15-Faelle-Bootmatrix byteidentisch aus R4 stammen. Produktset
`20760405...`, Bank, EXT, Symbole, Namepool und Directory bleiben
unveraendert.

Das Paket enthaelt das schreibgeschuetzte `L65SYS,65` mit exakt neun
Produktdateien und das leere, beschreibbare `L65WORK,65`. Jede der neun
L65SYS-Dateien ist gegen das zugehoerige R5-Produktartefakt geprueft. Das
Manifest bindet vollen Source-Commit, Toolchain, beide Promotionen, alle
Artefakt-SHAs, Gate-Grenzen, Medienvertrag, Packerquelle und AP7-Erstsitzung.
Der Standardbibliothek-only-Verifier arbeitet aus einer Paketkopie ohne
Repository oder Netzwerk und fuehrt zusaetzlich die eingebetteten R4-/R5-
Verifier aus.

Zwei mit unterschiedlichen `PYTHONHASHSEED`- und `TZ`-Werten erzeugte Pakete
sind fuer alle 23 Pfade in Bytes und Modi identisch. Paketset
`d2aea670d85f...` und Vergleich `1b96d41d3439...` sind im getrackten
Packer-Receipt gebunden. Veraenderungen an Produktbyte, Manifest oder
eingebettetem R5-Archiv werden abgelehnt. Der Claim bleibt eng: G3 nur
Emulator-Vorfilter bestanden, G5 14/14 bestanden, G6 und alle sechs
Hardware-Bootfaelle `not-run`, Release nein. Der naechste Schritt ist Review;
der 15-Faelle-Preflight und G6 wurden nicht vorgezogen.

## 2026-07-13: R6/G6-Preflight bindet alle 15 Faelle vor Hardware

Der freigegebene R6/G6-Ausfuehrungsvertrag konsumiert ausschliesslich das
Paketset `d2aea670d85f...` und das Produktset `20760405e10f...`. Der statische
Preflight hat den Paketverifier ausgefuehrt, alle 13 Produktrollen gegen ihre
Ship-SHAs gebunden, die neun `emulator-valid`-Faelle aus dem R4-Siegel als
bestanden uebernommen und fuer jeden der sechs `hardware-only`-Faelle Target,
Verfahren, Rohbelegmenge und Fall-Receipt-Verifier festgeschrieben. Die
Maschine ist als `TE0000B18447` an `/dev/ttyUSB1` gebunden. Ergebnis: 15/15
statisch vollstaendig, G3 9/9 versiegelt, G6 ehrlich 0/6 `not-run`, Release
nein. Das getrackte Receipt bindet Source-Commit `de2c92a4d209...`.

Zwei Manifestbefunde sind als nicht G6-blockierende, aber vor R7 zwingend zu
schliessende Voraussetzungen separat gepinnt: oeffentliche Rollennamen statt
lokaler Heimatpfade sowie `packed_on` aus dem Source-Commit-Zeitstempel mit
Cross-Midnight-Doppelbau. Sie veraendern keine Produktbytes und erteilen keine
vorzeitige Releaseautoritaet. Ab jetzt darf jeder physische G6-Fall erst nach
vollstaendiger Rohbelegbindung und erfolgreicher Offline-Pruefung als
bestanden gelten.

## 2026-07-13: Owner invertiert die Medienpolitik von Allowlist zu Denylist

Alex entscheidet im laufenden BUFSEL-Neupinnungszyklus, den bisherigen
`L65WORK,65`-Namenszwang ersatzlos zu entfernen. Beschreibbar ist jedes
strukturell valide 1581-Medium, sofern es nicht durch die Konjunktion aus
Name `L65SYS`, ID `65` und dem Packer-verifizierten Boot-Strukturmarker
`L65B` an Header-Offset 29 als Produktmedium erkannt wird. Der Packer bindet
diesen Marker an die exakte Anwesenheit von `AUTOBOOT.C65`, `BOOT.ID` und
`LISP65.PRG`. Der physische bzw.
Mount-Level-Schreibschutz der Produktdisk bleibt eine unabhaengige zweite
Schicht. Status 11 `wrong-work-media` bleibt nur als nie emittierter
ABI-Tombstone erhalten.

Die COW-, Verify- und Commit-Reihenfolge bleibt unveraendert. Der vorhandene
Transaktionsslot bindet nun ein Paar aus frischem Mount-Generation-Token und
der vollstaendigen kanonischen Namensidentitaet plus beiden exakten ID-Bytes.
Dadurch bleibt ein Wechsel
zwischen zwei unterschiedlich benannten, jeweils fuer sich beschreibbaren
Nutzermedien vor jedem Write und vor Directory-Publish fail-closed. Drei
normative Klassen werden gemeinsam mit dem permanenten `$D689=$80`-Fall
gefahren: Produktablehnung, beliebig benannter Save/Remount/Read-Roundtrip
und Identitaetswechsel A nach B. `L65WORK.D81` bleibt ausschliesslich eine
bequeme Paketbeigabe. BUFSEL und Medienpolitik teilen genau eine neue
R4/R5/G6-Identitaetskette.

Beim Aufbau dieser Kette wird zugleich ein alter Rueckwaerts-Bindungszyklus
entfernt: Der R3-Vertrag deklarierte Produktreceipt und Harness als SHA-Eingaben,
waehrend das Produktreceipt den Vertrag selbst SHA-band. Ab jetzt deklariert
der Vertrag diese Dateien als erzeugte, erst durch R4 zu versiegelnde Outputs.
Die Outputs binden ihre Eingaben vorwaerts; R4 bindet danach das abgeschlossene
Set. Damit ist die Snapshot-Doktrin fuer R3 konstruktiv statt nur prozedural.

Der BUFSEL-Core-Link erhaelt dabei ein eigenes, neues
`bufsel-product-identity-transition.json`: Produkt-SHA `d1fd7402...`,
Core-Artefaktset `65f83148...`, 313 B Bankmarge und ein positiver Delta von
44 B gegen die historische 269-B-Baseline. Die drei aelteren
Identitaets-Transitions werden weder geaendert noch als Live-Baseline
umgedeutet. Das aktuelle kanonische Core-Doppelbaureceipt ist an die neue
Transition gebunden; der vollstaendige BUFSEL-/Medienpolitik-Kandidat bleibt
getrennt im Product-Block-Receipt und dessen variiertem Doppelbau.

Ein anschliessender Global-Gate-Lauf belegt die Snapshot-Grenze praktisch:
Das historische Directory-only-Receipt bindet das damalige
Product-Receipt `fa0db9...`, waehrend der gleichnamige Live-Pfad inzwischen
den neuen Kandidaten traegt. Historische Architektur-Evidenz wird daher bei
Live-Drift nur noch akzeptiert, wenn exakt Pfad und SHA in einem intakten,
im Promotionsregister SHA-gebundenen Archiv vorkommen. Fuer `fa0db9...` ist
dies das Siegel `r4-product-candidate-312d5ab`; eine frei erfundene oder
manipulierte SHA bleibt fail-closed. Das alte R4-Assertion-Set selbst bleibt
gegen den neuen Kandidaten erwartungsgemaess rot, bis G3 ein neues R4-Siegel
autorisiert.

Der erste G3-Anlauf dieses neuen Kandidaten stoppte vor dem zweiten Tracefall
an einem reinen Host-Harness-Befund: Der erste Fall hatte Dump und Marker
korrekt erzeugt, aber der Distrobox-`podman exec`-Wrapper blieb danach
gestoppt und hielt die Container-Storage-Locks. Der tokengebundene Cleanup
besass zuvor nur direkte `xmega65`-Prozesse. Er besitzt nun auch
ausschliesslich tokenpassende `podman`-Wrapper; ein Negativ-Selftest beweist,
dass ein Wrapper mit fremdem Token unberuehrt bleibt. Safe-Runner,
Cleanup-Helfer und Smoke-Verifier sind seitdem explizite statische
Preflight-Bindungen. Zwei Tracefaelle liefen danach unmittelbar
hintereinander gruen, ohne Lockrest.

G3 schliesst danach fuer Produktset `6dc9c487...` mit 9/9
`emulator-valid`; alle sechs Hardwarefaelle bleiben `not-run`, und das
Receipt macht keine F011-/SD-/DMA-/Reset-Behauptung. Der finale R4-Cut
`91cab98...` erzeugt in zwei variierten Frischclones erneut exakt dieselben
13 Produktartefakte. Das neue `product-candidate`-Siegel
`r4-product-candidate-91cab98` enthaelt 117 Dateien, verifiziert isoliert
offline und ist zweimal byteidentisch unter Archiv-SHA `66576d52...` gebaut.
R5 konsumiert ab jetzt dieses Siegel; die drei aelteren R4-Siegel bleiben
unveraendert historische Beweisobjekte.

## 2026-07-13: BUFSEL-/Medienkandidat besteht globale G5-Matrix 14/14

R5-Lauf `r5-run-20260713-07` ist fuer Produktset
`6dc9c48742404f72f266c21d37bffc57d537920f9fd6eda66c0a2cf077701489`
vollstaendig hardwaregruen. Alle zehn Workbench-Faelle und alle vier
Runtime-Faelle besitzen genau ein unmittelbar offline verifiziertes
Fall-Receipt. Die Runtime-Faelle binden vier unterschiedliche physische
Cycle-IDs. Das historische 907-Oracle, Persistenz, Higher-Order-Verhalten und
die vier terminalen Runtime-Klassen sind erneut gruen; gegenueber dem
registrierten R4-Produktkandidaten wurden keine Produktbytes bewegt.

Vor der Aggregation wurde ein rein evidenzseitiger Altstand geschlossen: Der
Seal-Vertrag und der Packer referenzierten noch den vorigen R4-Kandidaten. Die
Fall-Receipts blieben gueltig, weil weder Produktset noch Test-Closure bewegt
wurden. Der Vertrag bindet nun Candidate `d26981bd...`, Closure
`e8329344...` und Lauf `r5-run-20260713-07`; die R4-Promotions-ID wird aus der
tatsaechlich materialisierten Archivbindung abgeleitet statt als alte
Konstante gespiegelt.

Das append-only Archiv `r5-global-g5-e3e08e2.tar.gz` besitzt SHA
`685e2d70ce17543693b5ec11236ad5ed27f7f8ada1301ecb4a3e247e1a78a91f`,
enthaelt 191 Dateien und verifiziert sich isoliert ohne Repository oder
Netzwerk. Ein zweiter Packlauf ist byteidentisch. Drei Manipulationen an
Produktbyte, Fall-Receipt und Top-Receipt werden abgelehnt. Der enge Claim
lautet: G5 passed fuer Produktset `6dc9c487...`; G6 0/6 `not-run`; Release
nein. Das fruehere R5-Siegel bleibt unveraendert historische Evidenz fuer
`20760405...`.

## 2026-07-13: R6-Ship auf BUFSEL-/Medienbeweise neu materialisiert

Der reine R6-Packer konsumiert nun ausschliesslich die registrierten Siegel
`r4-product-candidate-91cab98` und `r5-global-g5-e3e08e2`. Alle 13
Produktartefakte werden unveraendert aus dem R5-Archiv uebernommen; das
Produktset bleibt `6dc9c487...`, Build-ID `e132c7b9`. Das Zwei-Medien-Modell
enthaelt weiter das physisch schreibgeschuetzte `L65SYS,65` und die bequeme,
leere `L65WORK,65`; README und Manifest erlauben zugleich jede valide
Nicht-Produkt-1581 als Nutzermedium.

Zwei Packlaeufe mit variiertem Hashseed und verschiedener Zeitzone erzeugen
23/23 byte- und modusidentische Dateien. Das Paketset ist `0626a828...`, das
Manifest `e3fc4b1d...`. Beide Offline-Verifikationen bestehen, ebenso die drei
Negativproben Produktbyte, Manifest und eingebettetes R5-Archiv. Bank, EXT,
Symbole, Namepool und Directory bleiben gegen R5 jeweils bei Delta null. G6
bleibt bis zum neu gebundenen 15-Faelle-Preflight und sechs frischen
Hardwarefaellen `not-run`.

Der erste Preflight-Versuch stoppte vor jeder Hardwareaktion an einer reinen
Ordnungsabweichung: Der neue Fall `arbitrary-user-media-save-remount-read`
stand im lebenden Harness am Ende, im versiegelten R4-Katalog dagegen in der
kanonischen alphabetischen Folge. Die lokale Matrix wurde exakt an das Siegel
angeglichen. Dabei wurde auch ein Negativ-Selbsttest von Positionsindizes auf
Fall-IDs umgestellt; Sortierung kann seine Mutation damit nicht mehr
wirkungslos machen.

Der wiederholte statische Preflight bindet unter Receipt-SHA `ce180d44...`
alle 15 Faelle: neun versiegelte `emulator-valid`-Passes und sechs
`hardware-only`-Faelle `ready-not-run`. Produktset, beide Medien, beide
Promotionsarchive, Maschine und alle Ausfuehrungswerkzeuge sind gebunden. G6
bleibt ehrlich 0/6; die naechste Aktion ist der erste frische Hardwarefall.

## 2026-07-14: Primitive-Sichten erhalten eine erzwungene Einzelquelle

Der vierte G6-Hardwarefall stoppte vor jedem Medienzugriff: `function-kind`
klassifizierte `poke` als Primitive, der Compile-REPL-Dispatch kannte den Namen
aber nicht. Nach den frueheren Apply- und Directory-only-Funden ist dies die
dritte Instanz derselben Wurzelklasse. Die Korrektur erweitert daher nicht nur
eine Handtabelle. `config/v2-native-function-registry.json` partitioniert nun
alle 57 aktiven v2-Prim-IDs und ist die alleinige Quelle fuer die Sichten
CALLPRIM, Apply, `function-kind` und Compile-REPL. Oeffentliche Namen sind
allseitig vorhanden; jede Abweichung besitzt einen expliziten eingeschraenkten
View und eine Begruendung. Zusaetzlich bindet dieselbe Quelle die zwoelf
Opcode-Designatoren sowie die expliziten Intrinsic-Aliase `not`/`null`; der
Compile-REPL-Census wird gegen diese Menge geprueft. Der generierte
Kreuzparitaetsreport weist 39 oeffentliche Registry-Eintraege, 34
CALLPRIM-Einschraenkungen und keine unklassifizierte oder fehlende Primitive aus.

`peek` und `poke` erhalten die gefrorenen v2-Prim-IDs 61/62. Ihre Semantik ist
strict: exakt 2/3 Argumente, alle Fixnums, jedes Byte im Bereich 0--255. Die 17
Arity-, Typ- und Bereichsfehler laufen wie die positiven Aufrufe ueber direct,
`funcall` und `apply` auf allen vier Engines. Der vollstaendige generierte Satz
umfasst 207 Faelle und 828 Beobachtungen. Produktmedien bleiben bis Probelink,
Kapazitätsabnahme und regulärer R4/R5-Neupinnung unangetastet.

Der Kapazitaets-Probelink trennt zwei Effekte. `peek`/`poke` waren im alten
Produkt bereits durch `eval_init` interned; ihre neuen LCC-Literale machen sie
lediglich fuer den statischen Kompositionscensus sichtbar. Die gemessene
Hardwarekorrektur +5 Symbole/+51 Namensbytes wird deshalb um genau diese
Doppelzaehlung auf +3/+41 reduziert. Symbol- und Namepool-Wasserstand bleiben
damit real bei 120/2160. Der echte Preis ist ausschliesslich der 22 B groessere
LCC-Prim-Mapper in EXT (16441 -> 16419, weiterhin 35 B ueber dem 16-KiB-Boden).
Bank 0 gewinnt gleichzeitig 240 B (313 -> 553); das Boot-Overlay bleibt nach
der Treewalk-Strip-Verengung exakt 1669 B. Der EXT-Debit ist vor R3/R4
entscheidungspflichtig und wird nicht still durch das bestehende Medienbudget
autorisiert.

## 2026-07-14: 22-B-EXT-Debit autorisiert; 35 B werden kritische Wache

Die Owner-Entscheidung autorisiert Option 1 und damit genau 22 B EXT fuer die
beiden erforderlichen LCC-Prim-Mapper-Zweige von `peek` und `poke`. Ein Reclaim
ist nicht verlangt: 16419 B halten den gepinnten 16-KiB-Boden mit 35 B Marge.
Diese Restmarge ist ab jetzt kritisch; der naechste Block mit auch nur einem
negativen EXT-Delta stoppt wieder am Kapazitaets-Gate. Die strukturelle
Entlastung bleibt das fuer 1.1 terminierte Attic-Regal der Library-FASLs.

Auch der gleichzeitige Bankgewinn ist voll attribuiert. Ein echter Symboldiff
zwischen dem R4-versiegelten ELF fuer Produktset `6dc9c48742404f...` und dem
kanonischen variierenden Doppelbau weist `vm_callprim` -159 B,
`vm_native_call` -141 B, den Entfall der 39-B-Tabelle
`vm_apply_primitive.primfn` und den neuen gemeinsamen 97-B-Pfad
`vm_byte_args` aus. Die benannte Summe ist -242 B; +2 B Alignment ergeben
exakt -240 B residenten Text und damit 240 B Bankgewinn (313 -> 553). Das
Attributionsreceipt ist maschinell aus den beiden gebundenen ELFs
reproduzierbar; der Gewinn ist kein stilles Ledger-Rauschen.

## 2026-07-14: Historische R3-Baseline aus dem R4-Siegel materialisiert

Der erste neue G3-Preflight stoppte an einer historischen Live-Bindung: Der
R3-Vertrag referenzierte fuer den alten 313-B-Bankstand noch den beweglichen
Pfad des kanonischen Produkt-Doppelbaus, waehrend dieser Pfad inzwischen den
neuen 553-B-Kandidaten beschreibt. Die Baselinebytes werden deshalb unveraendert
aus dem R4-Archiv `r4-product-candidate-91cab98.tar.gz` unter einem eigenen
Snapshot-Pfad materialisiert; ihr SHA bleibt `b81fc4b83323...`. Der lebende
Produktbeleg darf fortschreiten, die historische Vertragsgrundlage nicht.

## 2026-07-14: Primitive-Sichten-Kandidat besteht G3 und wird als R4 versiegelt

Der vollstaendige Produktkandidat `7e76134374c7...` (Build-ID `0546c36c`)
besteht den seriell erzeugten G3-Vorfilter mit 9/9 `emulator-valid`; alle sechs
Hardwarefaelle bleiben ausdruecklich `not-run`. Ein zuvor durch zwei
gleichzeitig gestartete Runner kontaminierter Rohbelegsatz wurde verworfen und
nicht in ein Receipt uebernommen. Der anschliessende finale R4-Doppelbau auf
Commit `bdad6154e935...` reproduziert alle 13 Artefakte byteidentisch.

Das `product-candidate`-Siegel `r4-product-candidate-bdad615` enthaelt 110
Dateien, darunter die gebundene 22-B-EXT-Autorisierung, den reproduzierbaren
240-B-Bank-Symboldiff und den historischen Baseline-Snapshot. Es verifiziert
isoliert offline und ist in zwei Packlaeufen byteidentisch unter Archiv-SHA
`b7ad593754cd...`. Seine Claims bleiben eng: G3 bestanden, G5/G6 offen,
Release nicht freigegeben. R5 konsumiert ausschliesslich dieses Archiv.

## 2026-07-14: Primitive-Sichten-R5 besteht den statischen 14-Faelle-Preflight

R5-Lauf `r5-run-20260714-08` materialisiert alle 13 Produktartefakte
ausschliesslich aus dem registrierten R4-Siegel `r4-product-candidate-bdad615`;
das Produktset bleibt `7e76134374c7...`. Die getrennte Test-Closure umfasst 80
Artefakte, ist mit Set-SHA `4257b9afcb55...` gebunden und besitzt null
Ueberschneidung mit dem Produktset. Der Runtime-Testtraeger ist durch einen
byteidentischen Doppelbau belegt.

Der vollstaendige statische Preflight steht auf 14/14 `ready`: jede Route
bindet Target, Rohbeleg, natives Receipt, Fall-Receipt und Domain-Verifier.
Sechs absichtlich manipulierte Workbench-Evidenzen aus zwei Domaenen werden
abgelehnt; alle 15 Target-Dateibindungen sind vollstaendig. Das getrackte
Preflight-Receipt hat SHA `6fb5793185db...` und besteht sowohl seine direkte
Offline-Verifikation als auch den unabhaengigen R5-Archiv-Eingangscheck.
Hardware blieb seiteneffektfrei `not-run`; G5/G6 und Release bleiben offen.

## 2026-07-14: Primitive-Sichten-Kandidat besteht globale G5-Matrix 14/14

R5-Lauf `r5-run-20260714-08` ist fuer Produktset
`7e76134374c78d8080f8e310cc8ea595046dde08fa5714379d330c3e8afc7250`
vollstaendig hardwaregruen. Alle zehn Workbench-Faelle und alle vier
Runtime-Faelle besitzen genau ein unmittelbar offline verifiziertes
Fall-Receipt; ein gemeinsamer Offline-Durchgang verifiziert danach die exakte
14-Faelle-Matrix erneut. Die Runtime-Faelle binden vier unterschiedliche
physische Cycle-IDs. Das Produktset blieb gegen das registrierte R4-Siegel
unveraendert; Bank, EXT, Symbole, Namepool und Directory weisen in R5 jeweils
Delta null aus.

Ein frueher D81-Transportversuch erreichte die Maschine nicht und stoppte vor
der semantischen Produktausfuehrung. Er erzeugte vertragstreu weder natives
noch aeusseres Receipt. Der anschliessende Transport-Retry lief gegen dieselbe
Produkt- und Closure-Identitaet gruen. Damit hinterlaesst eine Nicht-Ausfuehrung
keinen Beweismuell und die kodifizierte Retry-Politik ist auch in diesem
Grenzfall praktisch bestaetigt.

Dieser Lauf traegt erstmals drei Produktkorrekturen gemeinsam durch die volle
Matrix: die Registry als erzwungene Einzelquelle aller Primitiv-Sichten, den
vollstaendigen BUFSEL-/Hardwarekontextbesitz jeder Disktransaktion und die
Denylist-Medienpolitik fuer beliebig benannte valide Nicht-Produkt-1581-Medien.
Persistenz, Higher-Order-Pfade, das historische 907-Orakel und alle vier
Runtime-Terminalklassen bleiben dabei gruen.

Der erste Siegelentwurf wurde nicht registriert: Seine isolierte
Positivpruefung fand eine gespiegelt fest verdrahtete Datums-Konstante im
eingebetteten Offline-Verifier. Der Entwurf wurde geloescht. Packer und
Offline-Verifier validieren das Siegeldatum nun strukturell als ISO-Datum und
binden seine Gleichheit ueber Manifest und Top-Receipt; kuenftige Siegel
erfordern keine neue Datums-Neupinnung.

Auch das lebende R5-Eingangs-Gate spiegelte noch Produktset, Lauf-ID und
Register-Subject des vorigen Siegels. Es leitet diese Werte nun aus dem
versiegelten R5-Vertrag ab und prueft sie kreuzweise gegen Top-Receipt und
Promotionsregister. Das Gate kann damit neue append-only R5-Siegel pruefen,
ohne fuer jede Produktidentitaet neue Konstanten einzubauen.

Das append-only Archiv `r5-global-g5-2ce5fe6.tar.gz` besitzt SHA
`cc114451458693a9e7dfe5b2c939cabba9bafc8c8871b0ec29bdc3b6249f4d37`,
enthaelt 191 Dateien und verifiziert sich isoliert ohne Repository oder
Netzwerk. Ein zweiter Packlauf mit anderem Hashseed und anderer Zeitzone ist
byteidentisch. Drei Manipulationen an Produktbyte, Fall-Receipt und Top-Receipt
werden abgelehnt. Der enge Claim lautet: G5 passed fuer Produktset
`7e761343...`; G6 0/6 `not-run`; Release nein. Alle frueheren R5-Siegel
bleiben unveraendert historische Evidenz ihrer jeweiligen Produktidentitaet.

## 2026-07-14: G6 stoppt M65D-Headerkorruption; externer D81-Zeuge wird Pflicht

G6-Fall 4 auf Produktset `7e76134374c7...` hat einen echten
Datenintegritaetsfehler gefunden. `%m65d-dir-scan` behandelte die
32-Byte-Regionen von T40/S0 ab Pseudo-Entry 1 als Directory-Slots, obwohl
dieser Sektor ausschliesslich 1581-Header und Linkwurzel ist und das reale
Directory bei T40/S3 beginnt. M65D publizierte dadurch `G6SAVE` im Header,
beanspruchte zugleich einen Datenblock in der BAM und las seine eigene falsche
Struktur erfolgreich zurueck; der unabhaengige `c1541`-Blick sah dagegen eine
leere Disk. Der Fall besitzt kein bestandenes Receipt. Die ersten drei
G6-Receipts bleiben historische Evidenz ausschliesslich fuer das alte Set.

Owner gibt Option 1 frei: Der Header-Sprung wird groessenneutral von Entry 1
auf Entry 8 korrigiert. Track 40/S0 darf nie Directory-Slot sein; der erste
zulaessige Entry-Sektor ist T40/S3. Die Abnahme verlaesst sich nicht mehr auf
M65Ds Eigenreadback. Vier permanente Blank-D81-Faelle decken Create,
Create/Replace sowie zwei- und dreisektorige Ketten ab. Ein separater
Vollabbild-Zeuge aus `d81_persistence_fault` und `d81_bam_sanity` fordert
byteidentischen Header, einen extern sichtbaren realen Directory-Eintrag,
allokierte Datenbloecke exakt gleich der sichtbaren Kette, keine
Doppelallokation und `freie Datenbloecke + sichtbare Dateibloecke = 3160`.
Negative Selbsttests lehnen Header-Schreibzugriff und verwaiste BAM-Allokation
ab.

Die zwei Harnesskorrekturen bleiben getrennt: `$D689` wird durch
`(poke 214 137 128)` adressiert, und die M65D-Erfolgs-ABI ist Status `0`,
nicht `t`. Weil sich der M65D-Produkt-SHA aendert, sind variierter Doppelbau,
R4-Neusiegel, alle 14 G5-Hardwarefaelle und alle sechs G6-Faelle frisch
verpflichtend. Bis alle automatisierten Host-, Differential-, Paritaets- und
Kapazitaetsgates gruen sind, beginnt kein neuer Hardwarelauf.

Der anschliessende reale Produktlink bestaetigt den groessenneutralen Schnitt:
`m65d.ext.bin` bleibt 7223 B und aendert gegen das letzte R5-Produkt genau ein
Byte von `01` auf `08`; Workbench-ELF, Resident-PRG, Boot-Overlay und
Bank-5-Preload sind byteidentisch. Der finale variierte Frischclone-Doppelbau
auf Commit `7844c347a360...` reproduziert alle 13 Produktartefakte als Set
`87986a149a4a...` mit Build-ID `58a3009b`; Kapazitaet bleibt bei 553 B Bank,
16419 B EXT, 120 Symbolen, 2160 Namepool-Bytes und 32 Directory-Slots. G3
besteht fuer dieses Set 9/9 `emulator-valid`; alle sechs Hardwarefaelle
bleiben ausdruecklich `not-run`. Die vier neuen Voll-D81-Beobachtungen melden
je T40/S3#0, 1/1/2/3 sichtbare Bloecke, keinen Header-Write und exakt 3160 in
der BAM-Bilanz.

## 2026-07-14: M65D-Integritaetskandidat wird als R4 versiegelt

Der finale R4-Cut `359abaed377d...` reproduziert das Produktset
`87986a149a4a...` (Build-ID `58a3009b`) in zwei variierten Frischclone-Bauten
mit 13/13 byteidentischen Artefakten. Gegen den zuvor versiegelten Kandidaten
bleiben Bank, EXT, Symbole, Namepool und Directory jeweils bei Delta null;
auch das Boot-Overlay bleibt byteidentisch. G3 ist 9/9
`emulator-valid` bestanden, waehrend G5 und alle sechs Hardware-Bootfaelle
ausdruecklich `not-run` bleiben. Der Kandidat ist nicht releasefaehig.

Das unveraenderliche Archiv `r4-product-candidate-359abae.tar.gz` umfasst 112
Dateien und besitzt SHA
`b0c0a443b3e871f32d3391b1ff1accdcea5363a0aa9a6fec48709a3825c2c38e`.
Zwei Packlaeufe sind byteidentisch; die isolierte Offline-Pruefung benoetigt
keinen lebenden Baum. Drei Negativproben lehnen veraenderte M65D-Produktbytes,
ein beschaedigtes Manifest und einen fehlenden gebundenen G3-Beleg ab. R5 darf
diese Produktidentitaet ausschliesslich aus dem registrierten R4-Siegel
materialisieren.

## 2026-07-14: R5-Preflight fuer M65D-Integritaetskandidat ist vollstaendig

R5 konsumiert fuer Lauf `r5-run-20260714-09` ausschliesslich das registrierte
Siegel `r4-product-candidate-359abae`; der lebende Baum besitzt keine
Produktbyte-Autoritaet. Alle 13 Artefakte materialisieren als Set
`87986a149a4a...` (Build-ID `58a3009b`). Der interne Runtime-Testtraeger ist
in zwei Bauten reproduzierbar und bleibt ausserhalb des Produktsets.

Der statische Preflight bindet 80 Test-Closure-Artefakte unter Set
`8299bd3239f0...`, weist Produktueberlappung null nach und schliesst alle 14
Ketten von Target ueber Rohbeleg und Fall-Receipt bis zum Offline-Verifier.
Sechs manipulierte Workbench-Eingaben werden abgelehnt. Receipt-SHA ist
`982ac2f090304efe48dfae32ee6ea648d873e8311d6216ad657eef9192cd1459`.
G5 und G6 bleiben `not-run`; vor dem ersten Hardwarefall muessen
`check-source` und `check-host` vollstaendig gruen sein.

## 2026-07-14: LCC-Kapazitaetsledger uebernimmt Primitive-Sicht-Kosten

Das finale `check-host` stoppt am veralteten harten Erwartungswert des
LCC-v2-Infrastrukturcontainers. Der bereits autorisierte Primitive-Sicht-Fix
kostet im Produkt 22 EXT-Codebytes; der Familienledger misst die vollstaendige
L65M-Huelle und damit gegen seinen vorherigen Stand +22 Codebytes, +64
EXT-Containerbytes und +10 rohe Namepoolbytes bei Directory-Delta null. Dies
ist keine weitere Kapazitaetsausgabe: Der reale Produktlink bleibt bei 16419 B
EXT-Headroom und Produktset `87986a149a4a...`.

Der neu aus den Quellen erzeugte Ledger weist fuer die vier Familien weiterhin
netto -7 Directory-Eintraege, -594 Namepoolbytes und -1092 EXT-Bytes aus. Das
Gate ist auf die gemessene Containerkost aktualisiert und wieder gruen.

## 2026-07-14: Number-to-string-Beleg bindet die aktuelle Pruefkette

Der anschliessende vollstaendige `check-host` stoppt fail-closed am historischen
Vier-Engine-Beleg fuer `number->string`. Der Vergleich zweier unabhaengig
gerenderter aktueller Belege zeigt keinen semantischen Drift: Treewalk,
Compiler-VM, Python-P0 und Lisp-LCC liefern weiterhin bytegleich `"-16384"`.
Geaendert sind ausschliesslich der SHA des frisch gebauten
Equivalence-Pruefbinaries und drei Runner-/Generatorbindungen aus der bereits
freigegebenen Registry-Einzelquellenarbeit.

Der lebende Beleg wird auf diese aktuelle Pruefkette neu gepinnt. Er ist weder
Produktartefakt noch Mitglied der versiegelten R5-Test-Closure; Produktset,
R4-Siegel und statischer R5-Preflight bleiben daher unveraendert. Hardware
bleibt bis zu einem erneut vollstaendig gruenen `check-host` gesperrt.

## 2026-07-14: String-Codec-Workload uebernimmt den M65D-Quellstand

Der naechste vollstaendige `check-host` stoppt spaet am historischen
String-Codec-Workload-Beleg. Zwei Wiederholungsmessungen sind byteidentisch.
Ergebnisse und Heap-Churn aller vier Workloads bleiben unveraendert; allein
`mini8` steigt von 86397 auf 86712 P0-Operationen und bleibt damit unter dem
gepinnten Limit von 95000. Ursache ist die korrigierte M65D-Quelle in der
vollstaendigen Workbench-Suite: deren Source- und Suite-SHAs wandern mit.

Das lebende Workload-Receipt sowie seine Checkpoint-3- und
Capability-Carrier-Bindungen werden konsistent neu gepinnt. Keines dieser
Objekte ist Mitglied der R5-Test-Closure; Produktset, R4-Siegel und statischer
R5-Preflight bleiben unveraendert. Der Messdrift ist explizit sichtbar und
autorisiert keine Aenderung an Workload-Grenzen oder Produktbytes.

Das Checkpoint-Repin aendert folgerichtig den SHA des Capability-Carrier-
Vertrags. Der kumulative Kapazitaetsledger uebernimmt ausschliesslich diese
Prerequisite-Bindung; alle Familien-, Infrastruktur- und Nettowerte bleiben
bytegleich unveraendert.

## 2026-07-14: Prelude-Control-Evidenz bindet aktuelle Build-Provenienz

Der naechste geloggte Vollanlauf stoppt im spaeten Live-Vergleich der
Prelude-Control-Familie. Alle 76 Beobachtungen bleiben unveraendert; die vier
Verdicts unterscheiden sich ausschliesslich in Binary- und
Buildprofil-SHAs. Die v1-Seite bindet nun den kanonischen eingefrorenen
Snapshot-Build `2b2ac358...`, die v2-Seite das aktuelle Equivalence-Binary
`eeb38529...`.

Verdicts, Differential-Receipt, Budgetvergleich, Migrationsvertrag und die
daraus abgeleiteten Dialektbindungen werden als eine SHA-Kette neu gepinnt.
Der Kapazitaetsledger aendert nur seine Migrationsvertragsbindung; alle
Messwerte bleiben unveraendert. Da das Prelude-Differential-Receipt und die
Dialektvertraege Mitglieder der R5-Test-Closure sind, wird die Closure mitsamt
statischem 14-Faelle-Preflight neu gebaut. Produktset und R4-Siegel bleiben
unveraendert; Hardware wurde noch nicht begonnen.

## 2026-07-14: R5-Test-Closure nach Prelude-Provenienz neu gepinnt

Die Prelude-Control-Neupinnung aendert keine der 76 Beobachtungen und kein
Produktbyte, aber erwartungsgemaess die lebende R5-Test-Closure. Der erneut aus
dem unveraenderten R4-Archiv gebaute statische Preflight bindet weiterhin alle
13 Produktartefakte als Set `87986a149a4a...`, schliesst alle 14
Receipt-Ketten und lehnt sechs manipulierte Verifier-Eingaben ab. Die 80
Test-Closure-Artefakte besitzen nun Set `db727337a813...`; Produktueberlappung
bleibt null. Das neue Preflight-Receipt besitzt SHA
`854f00e0e9553c1df1cf0ccb3857ea01ba9dd90e219630224bd54001db6739ae`.
G5 und G6 bleiben `not-run`; Hardware wurde nicht begonnen.

## 2026-07-14: Alle 1581-Leser behandeln T40/S0 als reine Linkwurzel

Der abschliessende `check-host` fand nach dem M65D-Schreibfix einen alten
Core-Loader-Fall, der einen Dateieintrag bei T40/S0+32 erwartete. Das neue
valide Blank-D81-Modell machte diese Fixture-Annahme reproduzierbar rot. Die
Produktanalyse zeigte dieselbe Formatklasse in milderer lesender Form:
`load` und `load-lib` scannten die Headerbereiche vor dem Folgen der Kette;
IDE-`dir` uebersprang nur einen statt aller acht Pseudo-Slots.

Alle produktiven Dateisuchen beginnen nun groessenneutral bei T40/S3. Der
absichtlich ueber die Linkwurzel laufende `dir`-Walker sowie die R3-/R6-
Offline-Parser scannen auf T40/S0 null Eintraege. Zwei Negativfixtures
praeparieren den Header als scheinbar passende Datei und belegen, dass weder
`load` noch `load-lib` ihn akzeptieren. Der reale Probelink bleibt in allen
Kapazitaetsdimensionen unveraendert: Bank 553 B, EXT 16419 B, 120 Symbole,
2160 B Namepool und 32 Directory-Eintraege frei. Wegen geaenderter
Produktartefaktbytes folgen dennoch neuer Doppelbau, R3/G3, R4 und R5; Hardware
bleibt bis zur vollstaendig gruenen Host-Suite gesperrt.

Der anschliessende variierte Fresh-Clone-Doppelbau ist fuer alle acht
Workbench- und alle 13 R3-Produktartefakte byteidentisch. Das vollstaendige
Produktset lautet `44163b315c17...`, Build-ID `20733c90`; die Kapazitaetswerte
bleiben gegen `87986a149a4a...` unveraendert. G3, R4 und R5 sind fuer diese
neuen Bytes noch offen.

## 2026-07-14: Leserbereinigter Kandidat besteht den G3-Vorfilter

Der statische 15-Faelle-Preflight bindet das vollstaendige Produktset
`44163b315c17...` mit Build-ID `20733c90` und weist alle neun Emulator- sowie
sechs Hardwarepfade vollstaendig aus. Der anschliessende serielle G3-Lauf
besteht 9/9 `emulator-valid`-Faelle; alle sechs `hardware-only`-Faelle bleiben
ausdruecklich `not-run`. Produkt-D81 und Produktset bleiben waehrend des Laufs
byteidentisch.

Der Receipt ist mit seinen Roh-Dumps, PRGs und xmega65-Protokollen gebunden und
offline erneut geprueft. Sein Claim ist ausschliesslich der Emulator-Vorfilter
fuer Autoboot-Sequenz, Katalog-Parsing und Staging-Logik. Er trifft keine
Aussage ueber F011-, SD-, DMA-, Reset- oder Power-Cycle-Semantik. R4 und R5
bleiben bis zum neuen unveraenderlichen Produktkandidaten-Siegel offen;
Hardware wurde fuer dieses Set noch nicht begonnen.

## 2026-07-14: D81-Leser-Kandidat wird als R4 versiegelt

Der finale R4-Cut `07de3cfc453f...` reproduziert Produktset
`44163b315c17...` mit Build-ID `20733c90` in zwei variierten Frischclone-
Bauten 13/13 byteidentisch. Der Doppelbau variiert Hashseed, Zeitzone,
Source-Epoch und Kalendertag; Bank, EXT, Symbole, Namepool, Directory und
Boot-Overlay bleiben gegen den letzten G5-Kandidaten jeweils bei Delta null.

Das neue append-only-Archiv `r4-product-candidate-07de3cf.tar.gz` umfasst 113
Dateien und besitzt SHA `478607d97610...`. Es materialisiert alle 13
Produktartefakte, den vollstaendigen G3-Beleg und den eingebetteten
Offline-Verifier. Zwei Archivbauten sind byteidentisch; die isolierte
Verifikation besteht ohne Repository oder Netzwerk. Manipuliertes Produktbyte,
manipuliertes Manifest und ein entfernter G3-Beleg werden jeweils abgelehnt.
Der Claim bleibt eng: G3 9/9 `emulator-valid`, Hardware 0/6, G5/G6 `not-run`,
nicht releasefaehig. R5 darf diese Identitaet ausschliesslich aus diesem
registrierten Siegel konsumieren.

## 2026-07-14: R5 fuer den D81-Leser-Kandidaten statisch neu gepinnt

R5-Lauf `r5-run-20260714-10` materialisiert alle 13 Produktartefakte
ausschliesslich aus dem registrierten R4-Siegel
`r4-product-candidate-07de3cf`. Die getrennte 80-teilige Test-Closure besitzt
nach der abschliessenden Prelude-Provenienzbindung Set `70a345c12ebc...` und
null Produktueberlappung; der interne Runtime-
Testtraeger ist in zwei Bauten byteidentisch und bleibt internal-proof-only.

Der statische 14-Faelle-Preflight bindet jedes Target ueber Rohbeleg, natives
Receipt und normalisiertes Fall-Receipt an seinen Verifier. Alle 14 Ketten
sind `ready`; sechs absichtlich manipulierte Workbench-Evidenzeingaben werden
abgelehnt. Der getrackte Preflight-Receipt besitzt SHA `b9404c0fbb3e...` und
verifiziert erneut gegen die vollstaendige materialisierte Kette. Hardware-
Side-Effects sind null, G5/G6 bleiben `not-run`, Release bleibt gesperrt.

Der erste Source-Vollanlauf fand davor korrekt eine historische
Prelude-Control-Inventarbindung an die alten `load`-/`load-lib`-Quell-SHAs.
Alle 76 Beobachtungen und saemtliche Budgetwerte blieben unveraendert; nur
Inventar, Manifest, Differential-Receipt, Budgetvergleich, Migrationsvertrag
und Dialekt-Snapshot wurden als zusammenhaengende Provenienzkette neu gepinnt.
Weil diese Dateien zur Test-Closure gehoeren, wurde der statische R5-Preflight
danach vollstaendig neu gebaut statt seinen ersten Zwischenstand zu bewahren.

Der anschliessende Source-Lauf fand ausserhalb der R5-Closure eine historische
Live-Bindung im R6-Selftest: Das alte Ship-Receipt bindet den Packer-Cut
`d53199cf...`, waehrend der lebende Offline-Verifier inzwischen die
T40/S0-Leserbereinigung enthaelt. Die Snapshot-Doktrin wird nun auch hier
angewandt. Neue Builds muessen weiterhin Packer, Vertrag und Verifier
byteidentisch an ihren Source-Commit binden; ein historisches Receipt prueft
dagegen die Existenz der damaligen Werkzeugbytes am damaligen Commit und
verlangt nur fuer den weiterhin lebenden Ship-Vertrag Byteidentitaet. Das
historische R6-Receipt bleibt dadurch Beweis fuer sein altes Produktset, ohne
den neuen Verifier zur Rueckentwicklung zu zwingen. R6 wird nicht vorzeitig
auf den neuen Kandidaten umgestellt und erzeugt keinen neuen G6- oder
Releaseclaim.

## 2026-07-14: Spaete Live-Belege folgen der korrigierten Workbench

Der vollstaendige Hostlauf fand zwei weitere, nicht zur R5-Test-Closure
gehoerende Live-Belege mit historischen Quellannahmen. Der String-Codec-
Workload bindet nun die aktuellen IDE-/Load-Quellen. Zwei Neumessungen sind
byteidentisch; Ergebnisse, Heap-Churn und Limits aller vier Workloads bleiben
unveraendert, `mini8` verbessert sich von 86712 auf 86481 Operationen bei
einem Limit von 95000. Checkpoint 3, Capability-Carrier-Vertrag und dessen
reine Kapazitaetsledger-Bindung werden konsistent nachgezogen.

Die alte Privatisierungsprobe nahm weiterhin 12 private M65D- und 11 private
IDEX-Helfer an. Der aktuelle Census zaehlt 13 beziehungsweise 8. Zwei der
alten M65D-Kandidaten sind nicht mehr Kandidaten: `%m65d-release-old` ist
bereits privat, `%m65d-dir-next` existiert nach der T40/S0-Bereinigung nicht
mehr. Von den 25 verbleibenden Kandidaten scheitern 20 an rel8, vier an der
Codeobjektgrenze und der rekursive `%m65d-dir-scan` an einem expliziten
Rekursionsgate. Zusaetzlich privatisierbar bleiben null; Kompositionsvertrag,
Produktbytes und alle Kapazitaetswerte bleiben unveraendert. Checkpoint 4 und
die zugehoerige Prerequisite-Bindung werden auf diesen aktuellen Beleg
gepinned.

Ein dabei exponierter Selftest des historischen De-Residentisierungsprototyps
hatte zwei unabhaengige Git-Repositories in derselben Sekunde committed und
daraus gleichen HEAD abgeleitet. Ueber einer Sekundengrenze war diese Annahme
falsch. Der Test erzeugt den Kandidaten nun per lokalem Clone des Baseline-
Fixtures; gleicher HEAD und abweichender Dirty-State sind damit konstruktiv
statt zeitabhaengig garantiert.

Nach Schliessung dieser lebenden Provenienzkette besteht `make check-host`
vollstaendig. Darin enthalten sind der unabhaengige Blank-D81-Oracle, 16
Persistenzfaelle mit 82 Fault-Points und expliziter BAM-Konsistenz, alle
Vier-Engine-Differentiale sowie die Produkt- und Closure-Gates. Der statische
R5-Preflight bindet weiterhin Produktset `44163b315c17...`; die aktualisierte
80-teilige Test-Closure lautet `92897d5301e...`, sein getracktes Receipt hat
SHA `2e1fedace6add42583000bcc5e9537744a8f5851677bb53946323e10b53cce28`.
Alle 14 Hardwarefaelle bleiben `not-run`; erst der nun folgende reale Lauf
darf diesen Status aendern.

## 2026-07-14: D81-Integritaetskandidat besteht globale G5-Matrix 14/14

R5-Lauf `r5-run-20260714-10` ist fuer Produktset
`44163b315c17ea2915be9929108db513d73315927dc9ac15043a0daa59d5a6d9`
vollstaendig hardwaregruen. Alle zehn Workbench-Faelle und alle vier
Runtime-Faelle besitzen jeweils genau ein SHA-gebundenes, unmittelbar offline
verifiziertes Fall-Receipt. Die Coverage ist exactly-once; die vier
Runtime-Faelle binden vier unterschiedliche physische Cycle-IDs. Gegenueber
dem registrierten R4-Produktkandidaten wurden keine Produktbytes bewegt;
Bank, EXT, Symbole, Namepool und Directory bleiben in R5 jeweils bei Delta
null.

Der Workbench-Lauf bestaetigt insbesondere die korrigierte 1581-Sicht mit
einem unabhaengigen Hostparser: Header und BAM bleiben konsistent, reale
Directory-Eintraege sind extern sichtbar, Mehrsektorketten besitzen weder
Lecks noch Doppelallokationen, und das historische 907-Oracle bleibt gruen.
Persistenz, Higher-Order-Pfade, IDE/IDEX-Late-Binding und alle vier
Runtime-Terminalklassen bestehen auf demselben Produktset.

Ein erster `clean`-Runtime-Versuch stieg nach bytegenauem Staging und
Produktstart beim seriellen Zustands-Readback aus. Er erzeugte kein aeusseres
Fall-Receipt und bleibt als fehlgeschlagene Harnessdiagnose separat erhalten.
Da semantische Produktausfuehrung bereits begonnen hatte, wurde er nicht als
frueher Transport-Retry umgedeutet: Erst ein neuer physischer Power-Cycle mit
neuer Cycle-ID lief vollstaendig gruen. Der anschliessende gemeinsame
Offline-Durchgang verifiziert exakt 14 aktuelle Receipt-Ketten und ignoriert
den Diagnoseordner konstruktiv.

Der enge Stand vor Versiegelung lautet: G5 `passed` fuer Produktset
`44163b31...`; G6 und alle sechs Hardware-Bootfaelle `not-run`; Release nicht
freigegeben. Die dauerhaft als verzichtbar markierte Ein-Zeremonie-Auffuehrung
wird nicht wiederholt. R6 darf erst das neue append-only R5-Siegel
materialisieren.

## 2026-07-14: D81-Integritaets-G5 als Hardwareabnahme versiegelt

Das append-only Archiv `r5-global-g5-29c46a5.tar.gz` besitzt SHA
`c9539f8d86a22d6c84dc8043a4961243bef2bf3e014e60a1eabaf466872b565f`
und enthaelt 191 Dateien: alle 13 aus R4 materialisierten Produktbytes, die
80-teilige getrennte Test-Closure, exakt 14 Fall-Receipt-Ketten samt
Rohbelegen sowie den eingebetteten Offline-Verifier. Zwei Vollpacklaeufe mit
unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher Zeitzone sind
byteidentisch.

Die isolierte Positivpruefung arbeitet ohne Repository und Netzwerk. Drei
Negativpruefungen lehnen ein manipuliertes Produktbyte, ein manipuliertes
Fall-Receipt und ein manipuliertes Top-Receipt ab. Das lebende Register bindet
Promotion `r5-global-g5-29c46a5`, Source-Commit `29c46a5c2c99...` und den
Archiv-SHA. Alle frueheren R5-Siegel bleiben gemaess Einbahn-Grenze
unveraendert historische Evidenz ihrer Produktsets.

Der Claim lautet ausschliesslich: G5 `passed` fuer Produktset
`44163b315c17ea...`; G6 und sechs Hardware-Bootfaelle 0/6 `not-run`; Release
nicht freigegeben. Die optionale Ein-Zeremonie-Auffuehrung bleibt dauerhaft
verzichtbar. R6 darf nur dieses registrierte R5-Beweisobjekt zusammen mit dem
registrierten R4-Produktkandidaten konsumieren.

## 2026-07-14: R6 materialisiert das D81-Integritaetsprodukt neu

Der reine R6-Packer konsumiert ausschliesslich die registrierten Archive
`r4-product-candidate-07de3cf` und `r5-global-g5-29c46a5`. Alle 13
Produktartefakte werden byteidentisch aus dem R5-Siegel uebernommen; G3-
Receipt und 15-Faelle-Matrix stammen aus dem R4-Siegel. Der Packer ruft weder
Compiler, Linker noch Disk-Builder auf. Produktset `44163b315c17...`, Build-ID
`20733c90` und alle fuenf Kapazitaetsdimensionen bleiben unveraendert.

Zwei Packlaeufe unter unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher
Zeitzone erzeugen fuer alle 23 Pfade identische Bytes und Modi. Das Paketset
lautet `2fc2014ceed55cf06c475a3f1d882539dcc625606d57ccee540065f6d13b83c9`;
das Produkt-D81 besitzt SHA `90284a2e3b2d...`, das unveraenderte leere
L65WORK-D81 SHA `bf887cd4f8b1...`. Die neun L65SYS-Eintraege sind jeweils
byteidentisch zu ihrer Produktkomponente.

Der Standardbibliothek-only-Verifier arbeitet aus beiden Paketen allein und
verifiziert die eingebetteten R4-/R5-Siegel rekursiv. Manipuliertes
Produktbyte, Manifest und R5-Archiv werden abgelehnt. Das neue
Packer-Receipt bindet Source-Commit `44ce931cfed2...`, Paketset, Doppelpack,
Negativtests und Kapazitaets-Delta null. Das fruehere Receipt bleibt unter
eigener historischer Kennung unveraendert. Der Claim bleibt G3 Vorfilter
passed, G5 14/14 passed, G6 0/6 `not-run`, Release nein.

## 2026-07-14: Korrigiertes R6-Paket besteht den 15-Faelle-Preflight

Der statische G6-Preflight bindet Paketset `2fc2014ceed55cf0...` und
Produktset `44163b315c17...` an Source-Commit `9a562de90b63...`. Der
Paketverifier laeuft erneut aus dem Ship allein; Manifest, Produkt-D81,
leeres Work-D81 sowie die eingebetteten R4-/R5-Archive stimmen mit dem
Harness-Vertrag ueberein. Maschine `TE0000B18447` an `/dev/ttyUSB1` und alle
Ausfuehrungswerkzeuge sind statisch gebunden.

Alle 15 Routen sind vollstaendig: neun `emulator-valid`-Faelle konsumieren
ihre versiegelten R4-G3-Belege als `sealed-pass`; sechs `hardware-only`-
Faelle besitzen Target, Verfahren, Rollen, Rohbelege und Verifier und bleiben
ehrlich `ready-not-run`. G5 wird ausschliesslich aus dem eingebetteten neuen
R5-Siegel als 14/14 uebernommen. Hardware-Side-Effects des Preflights sind
null; G6 bleibt 0/6 und Release nicht freigegeben. Die naechste Aktion ist
der hostfreie physische Kaltstart des ersten G6-Falls.

## 2026-07-14: Medienwechsel innerhalb einer Transaktion wird terminal

G6-Fall 5 hat auf Produktset `44163b315c17...` den schwerwiegendsten
Persistenzbefund der Serie erzeugt: Nach einem Freezer-Wechsel von Medium A
auf B schrieb M65D Nutzdaten und Metadaten auf B, leakte dort sechs
BAM-Bloecke und publizierte anschliessend durch den automatischen Status-8-
Remount-Retry eine sichtbare Datei. A blieb byteidentisch; der unangetastete
zweite B-Readback bleibt als Beweisobjekt gebunden. G6 stoppt ehrlich bei 4/6,
der Kandidat ist nicht releasefaehig.

Owner-Entscheidung: Transaktionen ueberleben niemals einen Medienwechsel.
Status 8 bleibt nur vor Transaktionsbeginn einmal remount-/retry-faehig. Nach
Beginn liefert ein Name-/ID-/Generations- oder D68B--D68F-Tokenwechsel den
neuen stabilen Status 12 `media-changed-during-transaction`; er ist terminal,
setzt den Latch und erfordert nach explizitem Remount einen neuen Save durch
den Nutzer. Der IDE-Convenience-Pfad darf Status 12 niemals wiederholen.

Der native F011-Pfad bindet deshalb den exakten D68B--D68F-Mount-Token und
prueft ihn vor/nach RMW, unmittelbar vor `STA $D081`, nach BUSY und um den
Readback. Das verbleibende Instruktionsfenster wird am finalen Produktlink in
Zyklen gemessen; ein fuer den realen Freezer erreichbares Fenster eskaliert
release-blockierend zu einer Core-/HYPPO-Sperre. Drei automatisierte
Zwei-Medien-Oracles injizieren den Wechsel vor Daten-, BAM- und Directory-
Write; eine einzige reale Freezer-Bestaetigung bleibt fuer G6. Medium B wird
vor Wiederverwendung ausschliesslich aus dem sauberen `G6B.D81` restauriert.

Der finale Produktlink quantifiziert das Restfenster nun statt es kleinzureden:
30 CPU-Zyklen einschliesslich des letzten `LDA $D68B,X` auf D68F und des
abschliessenden `STA $D081`, davon 26 Zyklen nach Abschluss des Registerreads
(nominell 740,741 ns bei 40,5 MHz). Der Core nimmt den RESTORE-Hypervisor-Trap
an einer Instruktionsgrenze an; damit kann der Freezer prinzipiell auch dieses
Fenster treffen. Die vorab vereinbarte Eskalation ist deshalb ausgeloest:
R4 bleibt bis zu einer Core-/HYPPO-Sperre der Drive-0-Mountidentitaet blockiert.
Der lokale Guard bleibt als Verteidigung und Diagnose erhalten, ist aber kein
Atomizitaetsbeweis.

Die probe-first Verdichtung haelt alle nicht verhandelbaren Kapazitaetsboeden:
EXT-Post-Headroom exakt 16.384 B, Directory exakt 32, Symbole 120, Namepool
2160. Der reale Produktlink misst 1917 B Post-Boot-Reserve, entsprechend 381 B
Bankreserve und einem noch nicht autorisierten Bankdelta von -172 B gegen das
letzte Siegel (553 B). Weder dieses Delta noch ein neuer Produktkandidat ist
promotet.

## 2026-07-14: Owner akzeptiert die gemessene Stock-Core-Restgrenze

Alex entscheidet fuer 1.0 gegen einen Projekt-Fork von `mega65-core` und
akzeptiert das gemessene Restfenster als ausdrueckliche Vertragsgrenze. Die
Entscheidung korrigiert zwei zuvor zu weit gehende Begruendungen: Fuer einen
Freezer-Treffer gibt es keine gemessene Wahrscheinlichkeit; RESTORE wird
frame-seitig vorgemerkt, an Instruktionsgrenzen angenommen und das Fenster
wiederholt sich pro Sektor-Write. Ausserdem ist ein fremder BAM- oder
Directory-Sektor nicht Power-Loss-aequivalent: Metadaten von Medium A koennen
die Mediengrenze zu B ueberqueren und dort das Dateisystem beschaedigen.

Der 1.0-Vertrag behauptet deshalb keine Atomizitaet zwischen der letzten
D68F-Pruefung und `STA $D081`. In diesem 30-Zyklen-Fenster kann hoechstens der
eine bereits gestartete Daten-, BAM- oder Directory-Sektor das neu eingelegte
Medium treffen. Die Nachpruefung liefert terminal Status 12, danach sind
weitere Writes und jeder automatische Retry verboten. Die byte-neutrale
Nutzerdiagnose lautet `medium changed during write; check both disks`; die
README erklaert das Sichern und unabhaengige Pruefen beider Medien vor einem
expliziten neuen Save.

Die Schadensgrenze wird fuer Daten, BAM und Directory getrennt adversarial
geprueft: A bleibt je isoliertem Befehl byteidentisch, B aendert genau
hoechstens den adressierten Sektor, danach folgen Status 12 und null weitere
Writes. Diese drei Receipts tragen
`known-contract-boundary-characterized-not-a-safety-pass`; sie sind kein
Sicherheits-PASS. Die drei normalen Vor-Kommando-Injektionen muessen B weiter
vollstaendig byteidentisch lassen. Eine reale Freezer-Bestaetigung bindet
Vor-/Nachabbilder beider Medien an dieselbe Null-oder-ein-Sektor-Grenze.

Ein Drive-0-Mount-Lock bleibt als Upstream-Vorschlag fuer das offizielle
`mega65-core`-Projekt auf dem 1.1/2.0-Zettel. Er ist weder 1.0-Releasebedingung
noch Anlass fuer einen lokalen Core-Fork oder eine neue Plattformdefinition.

## 2026-07-14: 172-B-Sicherheitsdebit autorisiert; EXT erreicht den Boden

Alex autorisiert Option 1 und damit den gemessenen Bank-0-Debit von 172 B fuer
die releasekritische Transaktions-Medienbindung. Die Bankreserve wird von 553
auf 381 B neu gepinnt; 1917 B Post-Boot-Reserve halten den unveraenderten
1536-B-Releaseboden. Die Ausgabe finanziert den D68B--D68F-Tokenbesitz, den
Doppel-Guard um BAM- und Directory-Writes sowie die nachgewiesene
Ein-Sektor-Schadensgrenze. Sie ist kein Feature-Debit und wird nicht durch
eine nachtraegliche Sicherheitscode-Diaet zurueckgeholt.

Der reale ELF-Symboldiff attribuiert die Bewegung vollstaendig: 380 B neue
Guard-Pfade stehen 217 B gleichzeitigem Kredit durch die
`vm_callprim`-Konsolidierung gegenueber. 163 B benannte Nettobewegung plus 9 B
Alignment ergeben exakt 172 B groessere residente VMA und damit den
Bank-Debit. Das Attributionsreceipt wird aus dem letzten R4-Siegel und dem
neuen kanonischen Doppelbau reproduzierbar erzeugt.

EXT endet bei exakt 16384 B Post-Headroom und damit bei null Marge gegen den
gepinnten Boden. Ab jetzt stoppt jedes weitere negative EXT-Byte sofort am
Kapazitaets-Gate und muss mit eigener Vorabfinanzierung eintreffen. Als
strukturelle Entlastung bleibt das fuer 1.1 terminierte Attic-Regal benannt,
das die Library-FASLs aus der EXT-Gleichung nimmt. Symbole, Namepool und
Directory bleiben bei 120, 2160 B und 32 Eintraegen.

## 2026-07-14: Transaktional gebundener Medienguard als R4 versiegelt

Der autorisierte R4-Cut `18d8c56cdd19...` reproduziert alle 13
Produktartefakte in zwei frischen, ueber Hashseed, Zeitzone, Source-Epoch und
Kalendertag variierten Builds byteidentisch als Set `1051d7820fa7...` mit
Build-ID `b0aed08c`. Damit ist zugleich bewiesen, dass die G3- und
Siegelautorisierungs-Commits keine Produktbytes bewegt haben. G3 besteht 9/9
`emulator-valid`; alle sechs `hardware-only`-Faelle bleiben `not-run`.

Das append-only-Archiv `r4-product-candidate-18d8c56.tar.gz` umfasst 112
Dateien und besitzt SHA `af85e2d7cd93...`. Zwei Archivbauten sind
byteidentisch; der eingebettete Verifier besteht isoliert ohne Repository und
Netzwerk. Ein manipuliertes Produktbyte, eine manipulierte Manifestbindung
und ein entfernter G3-Beleg werden jeweils abgelehnt. Der Claim bleibt eng:
G3 9/9 als Emulatorvorfilter, Hardware 0/6, G5/G6 `not-run`, nicht
releasefaehig. R5 darf Produktset `1051d782...` ausschliesslich aus diesem
registrierten Siegel materialisieren und muss alle 14 Hardwarefaelle frisch
mit vier physischen Cycle-IDs ausfuehren.

## 2026-07-14: R5-Preflight fuer den Medienguard statisch geschlossen

R5-Lauf `r5-run-20260714-11` konsumiert das registrierte R4-Siegel
`r4-product-candidate-18d8c56` als einzige Produktquelle. Die Materialisierung
prueft alle 13 Artefakte als Set `1051d782...`; der lebende Baum ist keine
Produktautoritaet. Der unveraenderte Dialektinhalt wurde mit Source-Cut
`18d8c56...` neu gesnapshottet und gehoert ausschliesslich zur getrennten
Test-Closure.

Die 80 Closure-Artefakte ergeben Set `8e5232f09080...` bei null
Produktueberlappung. Zwei Runtime-Carrier-Bauten sind byteidentisch, sechs
manipulierte Workbench-Verifier-Eingaben werden abgelehnt und alle 14 Ketten
Target -> Rohbeleg -> natives Receipt -> Fall-Receipt -> Verifier sind
statisch geschlossen. Das getrackte Preflight-Receipt besitzt SHA
`799f01114c59...`; G5, G6 und Release bleiben `not-run`/nicht freigegeben.
Als naechster Schritt folgen alle zehn Workbench- und vier Runtime-Faelle
frisch, letztere unter vier neuen physischen Cycle-IDs.

## 2026-07-14: Medienguard-Kandidat besteht globale G5-Matrix 14/14

R5-Lauf `r5-run-20260714-11` hat alle zehn Workbench- und vier Runtime-Faelle
auf Produktset `1051d7820fa7...` bestanden. Die Workbench-Faelle binden eine
gemeinsame Sitzung; die vier Runtime-Faelle `clean`, `truncated`, `bitflip`
und `build-id-mismatch` binden jeweils einen eigenen, vom Owner bestaetigten
physischen Power-Cycle. Ein frueher Transport-Retry blieb korrekt receipt-los
und ist keine semantische Ausfuehrung. Alle 14 erzeugten Fall-Receipts wurden
jeweils unmittelbar offline verifiziert.

Die autorisierte Siegelquelle ist Commit `087320c2c06b...`. Zwei Packlaeufe
mit unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher Zeitzone
erzeugen dasselbe 4.876.442-Byte-Archiv mit 191 Dateien und SHA
`d2a211e817af...`. Das Archiv `r5-global-g5-087320c.tar.gz` verifiziert
isoliert ohne Repository oder Netzwerk. Manipulationen an einem Produktbyte,
einem Fall-Receipt und dem Top-Receipt werden jeweils abgelehnt. Es ist als
append-only `hardware-acceptance` im lebenden Promotionsregister eingetragen.

Der Claim bleibt eng: G5 ist fuer exakt Produktset `1051d7820fa7...` 14/14
bestanden; G6 bleibt 0/6 `not-run`; der Kandidat ist nicht releasefaehig. Der
dauerhaft als unnoetig markierte Ein-Zeremonie-Neulauf wird nicht aufgefuehrt.
R6 darf ausschliesslich dieses R5-Siegel materialisieren.

## 2026-07-14: R6 transformiert das finale R5-Siegel reproduzierbar

Packer-Cut `10f93c91fba1...` konsumiert ausschliesslich die registrierten
Archive `r4-product-candidate-18d8c56` und `r5-global-g5-087320c`. Zwei mit
unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher Zeitzone ausgefuehrte
Packlaeufe stimmen fuer alle 23 Pfade, Modi und Bytes ueberein. Paketset
`2089b6fd52d4...` enthaelt alle 13 Produktartefakte byteidentisch zu
`1051d7820fa7...`; auch alle neun L65SYS-Eintraege sind byteidentisch, und
L65WORK bleibt ein leeres, valides 1581-Medium.

Beide Pakete verifizieren mit ihrer eingebetteten Standardbibliothek-only-
Pruefung offline. Veraenderungen an Produktbyte, Manifest und eingebettetem
R5-Archiv werden abgelehnt. Das Manifest besitzt SHA `6c343aa61993...`, die
Produkt-D81 SHA `c337d7668f7f...`, und das getrackte Packer-Receipt SHA
`5afcd92cbd24...`. Bank, EXT, Symbole, Namepool und Directory weisen als reine
Transformation jeweils Delta null aus.

Der R6/G6-Vertrag ist auf diese gemessenen Paketwerte neu gebunden; sein
Selbsttest lehnt 17 interne Mutationsklassen ab. Der Claim bleibt bis zum
statischen 15-Faelle-Preflight unveraendert: G3 Emulatorvorfilter bestanden,
G5 14/14 bestanden, G6 0/6 `not-run`, Release nein.

## 2026-07-14: Finaler R6/G6-Preflight ist 15/15 geschlossen

Der statische Preflight auf Source-Cut `68b80f46a2da...` verifiziert das
Paketset `2089b6fd52d4...` und Produktset `1051d7820fa7...` gegen den neuen
R6-Packer-Receipt. Neun `emulator-valid`-Faelle werden ausschliesslich aus
dem R4-Siegel als bestanden konsumiert. Alle sechs `hardware-only`-Faelle
sind mit Maschine, Werkzeugen, Produkt-, Medien- und Archiv-SHAs sowie ihren
vollstaendigen Evidenzrouten als `ready-not-run` gebunden.

Der Zwei-Medien-Oracle-Selbsttest und alle 17 Harness-Negativklassen sind
gruen. Das getrackte Preflight-Receipt besitzt SHA `e0e193c0890e...` und
verifiziert erneut offline. Es fuehrt keine Hardwareaktion aus und behauptet
weiter G6 0/6 `not-run` sowie Release nein. Erst der nun folgende physische
Kaltstart darf den ersten G6-Fall erzeugen.

## 2026-07-14: Post-Capture-Planungsread wird tokengebunden klassifiziert

Der dritte manuelle Versuch von G6-Fall `mid-write-media-swap-abort` erfasste
das native D68B--D68F-Token nach der Medienklassifikation korrekt, lieferte
nach einem anschliessenden Freezer-Wechsel aber Status 6 statt des terminalen
Status 12. Beide vollstaendigen Medien-Readbacks blieben byteidentisch; der
Guard verhinderte jeden Write. Der Befund ist deshalb kein neuer
Datenintegritaetsschaden, sondern eine Diagnose- und Retry-Luecke zwischen
Token-Capture und erstem Write: Ein Planungsread konnte vor Erreichen des
Write-Guards am falschen Medium scheitern.

Die interne Ein-Argument-Sicht von `%disk-write-sector` klassifiziert nun
genau diesen Rueckweg. Status 6 wird nur bei abweichendem nativen Mount-Token
zu Status 12; bei unveraendertem Token bleibt der echte Lesefehler Status 6.
Zwei neue P0-Faelle beweisen beide Richtungen mit jeweils null Writes. Die
M65D-Familie besteht damit 38 Faelle, der Persistenzvertrag 26
Negativmutationen und der R6/G6-Verifier weiterhin 17 Manipulationsklassen.
Der geaenderte 15-Faelle-Vertrag beansprucht noch keine neue G3-, G5- oder
G6-Evidenz; die bisherigen Siegel bleiben historische Beweise fuer ihr
jeweiliges Produktset.

Der reale Link beziffert den noch nicht autorisierten Preis gegen den
versiegelten Pin: `io_disk_transaction_classify_status` +27 B,
`vm_callprim` +14 B und 8 B Layout ergeben 49 B Bank-0-Debit. Die
Post-Boot-Reserve liegt bei 1868 B, also 332 B ueber dem unveraenderten
1536-B-Ziel. Gleichzeitig sinkt der M65D-Code von 4024 auf 4020 B und hebt
den EXT-Post-Headroom von 16384 auf 16388 B; Symbole, Namepool, Directory und
Boot-Overlay bleiben unveraendert. Status ist `passed-not-promoted`, bis eine
Vorabautorisierung das Bank-Debit deckt.

Der Owner autorisiert am 2026-07-15 Option 1 und pinnt die Bank nach
Promotion auf 332 B. Bedingung war ein selbst pruefender EXT-Nachweis. Der
neue Receipt `post-capture-planning-capacity-probe-receipt.json` konsumiert
das versiegelte R4-Archiv und den realen Kandidatenlink, weist fuenf
Manipulationen ab und belegt 16384 -> 16388 B EXT-Post-Headroom. Die neue
4-B-Marge stammt ausschliesslich aus dem M65D-Codepfad 4024 -> 4020 B;
40 weitere eingesparte Artefaktbytes sind nach jedem Lib-Commit freigegebene
Metadaten und werden nicht als Post-Headroom verbucht. Die kumulative
Autorisierung gegen die gemeinsame R3-Baseline deckt 221 B Bank-Debit und
31 B EXT-Debit; gegen das unmittelbar vorherige Siegel ist der neue Block
Bank -49 B und EXT +4 B. Fuer 1.1 bleibt das Attic-Regal die erste
strukturelle Entlastung des weiterhin kritischen EXT-Pfads.

## 2026-07-15: Post-Capture-Planungsguard als R4 versiegelt

Der finale R4-Cut `41cf793e4901...` reproduziert alle 13 Produktartefakte in
zwei frischen, ueber Hashseed, Zeitzone, Source-Epoch und Kalendertag
variierten Builds byteidentisch als Set `a2e5fe2da462...` mit Build-ID
`5b6e6afa`. G3 besteht 9/9 `emulator-valid`; alle sechs Hardwarefaelle sowie
G5 und G6 bleiben fuer diese Produktidentitaet `not-run`.

Das append-only-Archiv `r4-product-candidate-41cf793.tar.gz` umfasst 115
Dateien, besitzt SHA `d044230a83a3...` und stimmt in zwei Archivbauten
bytegenau ueberein. Der Verifier besteht isoliert aus dem Archiv allein. Ein
veraendertes Produktartefakt, eine veraenderte Manifestbindung und ein
entfernter G3-Beleg werden jeweils abgelehnt. Der Kapazitaetsclaim bindet die
kumulative Owner-Autorisierung: 332 B Bankmarge und 16388 B EXT-Post-Headroom
mit 4 B Marge; die Herkunft dieser vier Bytes ist im eingebetteten
Planungsread-Kapazitaetsreceipt vollstaendig attribuiert. R5 konsumiert ab
jetzt ausschliesslich dieses Siegel und muss 14/14 samt vier physischen
Power-Cycles frisch erbringen.

## 2026-07-15: Lebende Carrier- und Prelude-Evidenz auf den finalen Cut gepinnt

Der vollstaendige Hostlauf stoppt zunaechst an zwei bewusst exakten
Evidenzgates. Die v1-Serviceinventur erhaelt `boundp` als vierten
`callprim`-Uebergang mit exakt zwei M65D-Carrier-Aufrufen; die v2-Closure
umfasst damit 29 statt 28 Ziele. Current und Staging sind wieder vollstaendig:
30 aktuelle Ziele, null unresolved v2-Ziele und 353 unveraenderte
Workbench-Differentialfaelle. Das String-Codec-Workload-Receipt aendert nur
vier Input-SHAs; alle vier Messwerte und Grenzwerte bleiben bytegleich.

Der spaetere Prelude-Livevergleich weist ebenfalls keine Beobachtungsdrift
aus. Alle 76 Faelle, Binary-SHAs und Preload-SHAs bleiben unveraendert; nur
die beiden Buildprofil-SHAs wandern mit dem aktuellen Makefile. Verdicts,
Differential-Receipt, Budgetvergleich, Migrations-, Surface-, Kapazitaets-
und Dialektvertrag werden als bestehende lebende SHA-Kette neu gepinnt. Die
R5-Test-Closure wechselt dadurch auf `cfcbd9b1f7d5...`; ihr statischer
14-Faelle-Preflight lehnt weiterhin sechs Manipulationen ab. Produktset
`a2e5fe2da462...`, R4-Siegel und Produktbytes bleiben unveraendert, Hardware
ist fuer diesen Kandidaten weiterhin `not-run`.

## 2026-07-15: Einzelne private Inline-Gelegenheit bis 1.1 aufgeschoben

Der lebende Private-Inline-Census weist nach dem finalen M65D-Fix erstmals
genau einen weiteren geeigneten Helfer aus: `%m65d-dir-target-ok-p`. Die
uebrigen 24 Kandidaten bleiben exakt klassifiziert (19 Rel8-Grenzen, vier
Codeobjekt-Grenzen und eine Rekursion). Die Gelegenheit wird in R6 bewusst
nicht angewandt: Sie behebt keinen Produktfehler, es besteht kein aktueller
Kapazitaetsbedarf, und eine nachtraegliche Ein-Symbol-Optimierung wuerde die
bereits reproduzierten Produktbytes sowie R4/R5 ohne Releasegewinn bewegen.

Das lebende Probe-Receipt pinnt deshalb den Kandidaten namentlich als
`eligible_but_not_applied`, beansprucht weiterhin null Reclaim und verweist
ihn in den 1.1-Reclaim-Vorrat. Produktset `a2e5fe2da462...`, R4-Siegel,
Kapazitaetszahlen und R5-Test-Closure bleiben unveraendert.

## 2026-07-15: Finaler Planungsguard-Kandidat besteht globale G5-Matrix 14/14

R5-Lauf `r5-run-20260715-12` hat alle zehn Workbench- und vier
Runtime-Faelle auf Produktset `a2e5fe2da462...` bestanden. Die zehn
Workbench-Faelle binden die gemeinsame Cycle-ID
`r5-run-20260715-12-workbench-session-01`; `clean`, `truncated`, `bitflip`
und `build-id-mismatch` besitzen vier getrennte, vom Owner bestaetigte
physische Power-Cycle-IDs. Alle 14 Fall-Receipts wurden unmittelbar und beim
Siegelbau nochmals offline verifiziert.

Zwei Transportereignisse bleiben sauber getrennt: Beim ersten
Overlay-Readback und bei dessen erster Wiederholung lief kein Produkt und es
entstand kein Receipt. Beim ersten `save-new-var`-Lauf waren Produktoracles
und Ergebnis 907 gruen, aber der abschliessende Workbench-Restore verlor den
Transport; auch dieser Lauf blieb ohne Fall-Receipt und wurde vollstaendig
wiederholt. Keines der Ereignisse wurde als Produktbefund oder bestandene
Evidenz umgedeutet.

Die autorisierte Siegelquelle ist Commit `94abc53761a1...`. Zwei Packlaeufe
erzeugen dasselbe 4.878.437-Byte-Archiv mit 191 eingebetteten Dateien und SHA
`2e22dc80fef6...`. `r5-global-g5-94abc53.tar.gz` verifiziert isoliert ohne
Repository oder Netzwerk; Manipulationen an Produktbyte, Fall-Receipt und
Top-Receipt werden abgelehnt. Der Kapazitaetsclaim bindet 332 B Bankmarge,
16.388 B EXT-Post-Headroom mit 4 B Marge sowie unveraendert 120 Symbole,
2160 B Namepool und 32 Directory-Eintraege.

Das append-only-Siegel ist als `hardware-acceptance` registriert. Sein Claim
bleibt eng: G5 ist fuer exakt `a2e5fe2da462...` 14/14 bestanden; G6 bleibt
0/6 `not-run`; Release ist nicht freigegeben. Der dauerhaft unnoetige
Ein-Zeremonie-Neulauf wird nicht aufgefuehrt. R6 darf ausschliesslich dieses
R5-Siegel materialisieren.

## 2026-07-15: R6 transformiert das finale Planungsguard-Siegel reproduzierbar

Packer-Cut `fda8db09dd72...` konsumiert ausschliesslich die registrierten
Archive `r4-product-candidate-41cf793` und `r5-global-g5-94abc53`. Zwei mit
unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher Zeitzone ausgefuehrte
Packlaeufe stimmen fuer alle 23 Pfade, Modi und Bytes ueberein. Paketset
`4b3410108a5c...` enthaelt alle 13 Produktartefakte byteidentisch zu
`a2e5fe2da462...`; auch alle neun L65SYS-Eintraege sind byteidentisch, und
L65WORK bleibt ein leeres, valides 1581-Medium.

Beide Pakete verifizieren mit ihrer eingebetteten Standardbibliothek-only-
Pruefung offline. Veraenderungen an Produktbyte, Manifest und eingebettetem
R5-Archiv werden abgelehnt. Das Manifest besitzt SHA `872650d612f3...`, die
Produkt-D81 SHA `1f885b17b2f2...`, und das getrackte Packer-Receipt SHA
`e473fcad178a...`. Bank, EXT, Symbole, Namepool und Directory weisen als
reine Transformation jeweils Delta null aus; der Pin bleibt
332/16388/120/2160/32.

Der R6/G6-Vertrag ist auf diese gemessenen Paketwerte neu gebunden. Der Claim
bleibt bis zum statischen 15-Faelle-Preflight unveraendert: G3
Emulatorvorfilter bestanden, G5 14/14 bestanden, G6 0/6 `not-run`, Release
nein.

## 2026-07-15: Planungsstatus hat eine Wahrheitsquelle

Der G6-Befund „Save liefert 12, `m65d-status` danach 6“ war eine
unvollstaendige Stelle desselben post-capture-Planungsguards: Der native
Klassifikator lieferte Status 12 an den Aufrufer, waehrend der persistente
Lisp-Status noch den vorausgegangenen Planungsread-Fehler 6 enthielt.
`%m65d-run-unlatched` publiziert nun den klassifizierten Wert genau einmal
ueber `%m65d-set`; Rueckgabewert und `m65d-status` stammen damit aus derselben
Quelle. Tokenwechsel ergibt 12/12, stabiler Token mit Lesefehler 6/6, jeweils
null Writes und ohne Partial-Write-Latch.

Das Completion-Receipt
`post-capture-planning-status-state-completion-receipt.json` misst gegen den
vorherigen Kandidaten Bank-Delta 0 und EXT-Delta -3 B Headroom: 16.388 ->
16.385 B, der 16-KiB-Boden bleibt mit 1 B Marge erfuellt. Symbole, Namepool,
Directory und Boot-Overlay bleiben unveraendert. Die Blockpromotion wartet
auf die ausdrueckliche Erweiterung der kumulativen EXT-Autorisierung von 31
auf 34 B; der Befund wird nicht still unter die bestehende Autorisierung
gebucht. Der Owner autorisiert den inkrementellen Debit von 3 B am
2026-07-15 und pinnt EXT auf 16.385 B bei unveraendertem 16.384-B-Boden.
Die Restmarge von 1 B gilt fuer 1.0 funktional als null: EXT ist im
1.0-Zug eingefroren, ein weiterer Debit ist auch um ein Byte nicht
autorisierbar. Jede weitere EXT-Aenderung muss gleichzeitig strukturelle
Entlastung mitbringen; als benannte Entlastung bleibt das 1.1-Attic-Regal
terminiert. Da sich das ausgelieferte
M65D-Artefakt von 7214 auf 7217 B und dessen SHA aendert, ist eine Uebernahme
alter Hardware-Receipts auf den neuen Kandidaten unzulaessig; R4/R5/R6 und
die anwendbaren G6-Hardwarefaelle muessen frisch gebunden werden.

## 2026-07-15: G6-Profil Stock-Core SD-D81 hat fuenf anwendbare Faelle

Owner-Entscheidung: Der Fall `product-medium-physical-write-protect` wird im
Profil `stock-core-sd-d81` nicht kuenstlich bestanden. Es liegt kein
physisches Medium vor, und der Stock-Freezer bietet keinen Read-only-Schalter
fuer ein gemountetes D81-Image. Das Gate behauptet deshalb ausschliesslich:
„G6: 5/5 anwendbare Hardwarefaelle bestanden;
product-medium-physical-write-protect n/a: kein physisches Medium in der
SD-D81-Konfiguration“. Das N/A-Receipt bindet Profil, Produktset und
Ship-Manifest; JTAG-Pokes, Core-Manipulationen und synthetische PASS-Belege
sind ausgeschlossen.

Der Produkt-Codepfad-Audit findet keinen Zweig, der ein eigenes F011-
Write-Protect-Signal liest oder auswertet. `$D68B` bleibt allein Teil des
opaken fuenf Byte grossen Mount-Tokens; diese Semantik bleibt durch Host-
Phasenfixtures und den anwendbaren Hardwarefall zum Mid-Write-Medienwechsel
abgedeckt. C6 in `docs/upstream-findings.md` fordert fuer den offiziellen
Core einen virtuellen D81-Read-only-Attach-Schalter, ohne Projekt-Core-Fork.

## 2026-07-15: Finales R6-Paket besteht statischen 15-Faelle-Preflight

Preflight-Cut `7614ad1350a7...` konsumiert ausschliesslich das gemessene
Paketset `4b3410108a5c...` und dessen Packer-Receipt. Alle neun
`emulator-valid`-Faelle werden aus dem eingebetteten R4-Siegel als bestanden
verifiziert. Die sechs `hardware-only`-Faelle sind mit Maschine, Core-/ROM-,
Produkt-, Medien-, Werkzeug- und Verifier-SHAs vollstaendig gebunden und
bleiben `ready-not-run`.

Der Selbsttest weist weiterhin 17 Manipulationsklassen ab, einschliesslich
Bank-5-, BUFSEL-, Medienidentitaets-, Phaseninjektions- und
Freezer-Grenzoracles. Das getrackte Preflight-Receipt besitzt SHA
`bfbc324f1443...`. Claim-Grenze: G3 9/9 Emulatorvorfilter, G5 14/14, G6 0/6
`not-run`, Release nein. Ab jetzt darf die Physik sprechen; eine weitere
statische oder paketierende Verdrahtung ist vor Fall 1 nicht offen.

## 2026-07-15: Status-Single-Source als neuer R4-Kandidat versiegelt

Der finale R4-Cut `5942e0cf81a4...` reproduziert alle 13 Produktartefakte in
zwei ueber Hashseed, Zeitzone, Source-Epoch und Kalendertag variierten
Fresh-Clone-Bauten byteidentisch als Set `c41b9643ada1...` mit Build-ID
`f6faad87`. Ein zweiter Doppelbau auf dem spaeteren R4-Vertrags-Cut bestaetigt
zusaetzlich, dass die Evidenz- und Vertragscommits keine Produktbytes bewegen.
G3 besteht 9/9 `emulator-valid`; alle sechs `hardware-only`-Faelle, G5 und G6
bleiben fuer diese Produktidentitaet `not-run`.

Das append-only-Archiv `r4-product-candidate-5942e0c.tar.gz` umfasst 119
Dateien, ist in zwei Archivbauten byteidentisch und besitzt SHA
`900c067c54aa...`. Es verifiziert isoliert aus dem Archiv allein.
Manipulationen an einem Produktbyte, der Manifestidentitaet und dem
eingebetteten G3-Receipt werden jeweils abgelehnt. Der Kapazitaetsclaim bindet
332 B Bankmarge und 16385 B EXT-Post-Headroom bei unveraendertem
16384-B-Boden. Das verbleibende Byte ist fuer 1.0 ausdruecklich nicht
ausgebbar; jede weitere EXT-Aenderung verlangt gleichzeitige strukturelle
Entlastung. R5 konsumiert ausschliesslich dieses Siegel und muss 14/14 samt
vier physischen Power-Cycles frisch erbringen.

## 2026-07-15: R5-Preflight auf Status-Single-Source-Kandidat gebunden

R5-Lauf `r5-run-20260715-13` konsumiert ausschliesslich das registrierte
R4-Siegel `r4-product-candidate-5942e0c`. Die Materialisierung verifiziert
alle 13 Produktartefakte als Set `c41b9643ada1...`; der Runtime-Core bleibt
als reproduzierbar doppelt gebauter Testtraeger ausserhalb des Produktsets.
Die 80-Artefakt-Test-Closure besitzt Set `e2d2b6a434c4...`; Produktueberlappung
ist null.

Der statische 14-Faelle-Preflight bindet Target, Rohbeleg, Fall-Receipt und
Verifier fuer jeden Fall. Sechs absichtlich manipulierte Workbench-Belege
werden abgelehnt. Das getrackte Preflight-Receipt besitzt SHA
`ffe94b72e968...`. Claim-Grenze: G3 9/9 Emulatorvorfilter; G5 `not-run`;
vier physische Power-Cycles `not-run`; G6 `not-run`; Release nein. Erst nach
diesem Preflight darf die Hardwarematrix fuer das neue Produktset starten.

## 2026-07-15: Status-Single-Source-Kandidat besteht globale G5-Matrix 14/14

R5-Lauf `r5-run-20260715-13` hat alle zehn Workbench- und vier
Runtime-Faelle auf Produktset `c41b9643ada1...` bestanden. Die Workbench-
Faelle binden gemeinsam `r5-run-20260715-13-workbench-session-01`.
`clean`, `truncated`, `bitflip` und `build-id-mismatch` besitzen vier
getrennte, vom Owner bestaetigte physische Cycle-IDs. Jede native und aeussere
Fall-Receipt-Kette wurde unmittelbar sowie beim Siegelbau erneut offline
verifiziert. Ein frueher Stage-A-Transportstopp durch zwei veraltete lokale
Diagnoseprozesse blieb vor Produktausfuehrung und korrekt receipt-los; nach
gezieltem Prozessabschluss wurde nur der fehlende Fall wiederholt.

Der autorisierte Siegel-Cut `b40cbe258e7e...` ist vor dem Packen off-site
gepinnt. Zwei mit unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher
Zeitzone ausgefuehrte Packlaeufe erzeugen dasselbe 4.878.961-Byte-Archiv mit
191 eingebetteten Dateien und SHA `be7b3f17ccad...`. Das Archiv
`r5-global-g5-b40cbe2.tar.gz` verifiziert isoliert ohne Repository oder
Netzwerk; Manipulationen an Produktbyte, Fall-Receipt und Top-Receipt werden
abgelehnt. Der Top-Receipt besitzt SHA `6fb6332a4df7...`.

Das append-only Siegel ist als `hardware-acceptance` registriert. Sein Claim
bleibt eng: G5 ist fuer exakt Produktset `c41b9643...` 14/14 bestanden; G6
bleibt `not-run`, und Release ist nicht freigegeben. Der Kapazitaetsclaim
bindet 332 B Bank, 16.385 B EXT, 120 Symbole, 2160 B Namepool und 32
Directory-Eintraege jeweils mit Siegel-Delta null. R6 darf ausschliesslich
dieses R5-Siegel materialisieren.

## 2026-07-15: R6 transformiert das Status-Single-Source-Siegel reproduzierbar

Packer-Cut `e21f984930f3...` konsumiert ausschliesslich die registrierten
Archive `r4-product-candidate-5942e0c` und `r5-global-g5-b40cbe2`. Zwei mit
unterschiedlichem `PYTHONHASHSEED` und unterschiedlicher Zeitzone ausgefuehrte
Packlaeufe stimmen fuer alle 24 Pfade, Modi und Bytes ueberein. Die gegenueber
dem historischen 23-Dateien-Stand zusaetzliche Datei ist ausschliesslich das
profilgebundene `evidence/g6-hardware-profile.json`; sie aendert kein
Produktbyte.

Paketset `925cda9ab833...` enthaelt alle 13 Produktartefakte und alle neun
L65SYS-Eintraege byteidentisch zu `c41b9643...`; L65WORK bleibt ein leeres,
valides 1581-Medium. Beide Pakete verifizieren offline. Veraenderungen an
Produktbyte, Manifest und eingebettetem R5-Archiv werden abgelehnt. Das
Manifest besitzt SHA `323d6f497c18...`, die Produkt-D81 SHA
`90efed69721c...`, und das Packer-Receipt SHA `a6a20dff0459...`.

Bank, EXT, Symbole, Namepool und Directory weisen als reine Transformation
jeweils Delta null aus; der Pin bleibt 332/16385/120/2160/32. Der Claim traegt
die Profilgrenze im Wert: G6 ist `not-run(5/5-applicable)`, waehrend physischer
Produktmedien-Schreibschutz in der Stock-Core-SD-D81-Konfiguration sichtbar
N/A bleibt. Release ist nicht freigegeben. Als naechstes bindet der statische
15-Faelle-Preflight genau dieses Paketset.

## 2026-07-15: Finaler Status-Single-Source-Ship-Preflight ist 15/15 geschlossen

Preflight-Cut `499d6dfa067d...` konsumiert ausschliesslich Paketset
`925cda9ab833...` und dessen R6-Packer-Receipt. Alle neun `emulator-valid`-
Faelle werden aus dem eingebetteten R4-Siegel als bestanden verifiziert. Die
fuenf im Stock-Core-SD-D81-Profil anwendbaren `hardware-only`-Faelle sind mit
Maschine, Core-/ROM-, Produkt-, Medien-, Werkzeug- und Verifier-SHAs als
`ready-not-run` gebunden.

Der physische Produktmedien-Schreibschutzfall ist ueber das eigenstaendige
Profil-Receipt SHA `2fec324c3d61...` als N/A gebunden; synthetische Hardware-
Belege bleiben ausgeschlossen. Der Selbsttest weist 18 Mutationsklassen ab,
einschliesslich Bank-5-, BUFSEL-, Medienidentitaets-, Phaseninjektions- und
Freezer-Grenzoracles. Das getrackte Preflight-Receipt besitzt SHA
`9a3e5c8c3d25...` und verifiziert offline.

Claim-Grenze: G3 9/9 Emulatorvorfilter, G5 14/14, G6 0/5 anwendbare Faelle
`not-run`, WP 1/1 profilgebunden N/A, Release nein. Erst jetzt darf der
hostfreie Hardwarelauf beginnen.

## 2026-07-15: G6 besteht 5/5 anwendbare Hardwarefaelle und wird versiegelt

Der finale Lauf auf Maschine `TE0000B18447`, Core `git-03b24c6b` und der
gebundenen ROM besteht `power-cycle-autoboot-restage-repl`,
`warm-reset-valid-catalog-fastpath`, `disk-swap-resident-composition`,
`work-media-save-remount-read` und `mid-write-media-swap-abort` gegen exakt
Produktset `c41b9643ada1...` und Ship-Manifest `323d6f497c18...`. Der
Freezer-Fall liefert terminale Rueckgabe 12 und persistenten Status 12 aus
derselben Statusquelle; beide Vollabbilder bleiben im beobachteten Lauf
byteidentisch. Der Receipt behauptet daraus keinen allgemeinen
Sicherheits-PASS, sondern bindet weiterhin die vom Owner akzeptierte Grenze
von hoechstens einem fremden Sektor.

Der physische Produktmedien-Schreibschutzfall bleibt im aktiven
Stock-Core-SD-D81-Profil sichtbar N/A. Der Top-Receipt mit SHA
`edcca70cc747...` traegt deshalb den exakten Claim „5/5 anwendbare
Hardwarefaelle bestanden; physical write protect N/A“ und haelt Release bis
R7 gesperrt.

Siegel-Cut `aed1595a1a2d...` erzeugt unter zwei verschiedenen Hashseed- und
Zeitzonenumgebungen byteidentische Archive. Das append-only Archiv
`r6-g6-hardware-acceptance-aed1595.tar.gz` ist 318.210.467 Bytes gross,
enthaelt 173 Payloaddateien und besitzt SHA `b339a274a97c...`. Es verifiziert
isoliert ohne Repository oder Netzwerk und lehnt Manipulationen an
Produktbyte, Fall-Receipt und Top-Receipt ab. Die Promotion ist als
`hardware-acceptance` registriert; ihr Claim bleibt „G6 bestanden, R7 offen“.

## 2026-07-15: Beide R7-Manifestvoraussetzungen sind geschlossen

Der R7-Prerequisite-Packer konsumiert ausschliesslich das registrierte
G6-Siegel `r6-g6-hardware-acceptance-aed1595`. Im oeffentlichen
Manifestentwurf werden die fuenf hostabhaengigen Toolchain-Angaben fuer
`c1541`, ROM, SD-Basis und die beiden xmega65-Ebenen durch stabile Rollennamen
ersetzt; die jeweiligen Bytezahlen und SHAs bleiben erhalten. Der Scan findet
null absolute Pfade, insbesondere kein Heimatverzeichnis.

`packed_on` wird als `2026-07-15T13:14:59+02:00` direkt aus dem
Commit-Zeitstempel von Cut `52e184df6541...` abgeleitet. Zwei Packprozesse mit
verschiedenen Hashseeds und den Zeitzonen `Etc/GMT+12` sowie
`Pacific/Kiritimati` beobachten lokal die unterschiedlichen Kalendertage
2026-07-14 und 2026-07-16, erzeugen aber byteidentische Manifestbytes. Der
Manifestentwurf besitzt SHA `b21df1025762...`, der Receipt SHA
`95a3b216a76e...`; alle 13 Produktartefakte bleiben Set `c41b9643...` mit
Produktdelta null. Der Beleg erteilt selbst keine Releasefreigabe. R7 ist nun
nicht mehr technisch, sondern nur noch durch Releaseidentitaet, finales
Bundle, privaten Tag und Mirror offen.

Das stehende Source-Gate folgt nach dem G6-Siegel ebenfalls der
Snapshot-Doktrin: Es baut den aktuellen Produktstand frisch und bestaetigt
Set `c41b9643...`, verifiziert R3--G6 aber aus dem registrierten
G6-Archiv. Spaetere Harnessverschaerfungen duerfen dadurch keine versiegelten
R3/R4/R5-Receipts gegen den lebenden Baum neu interpretieren.

## 2026-07-15: Private Freigabe lisp65 1.0.0 mit Dialect V2

Owner-Entscheidung ist SemVer-Tag `v1.0.0`; Dialect V2 ist bewusst die im
ersten Produktrelease ausgelieferte Sprache, Dialect V1 war nie ein Release.
Der annotierte Tag zeigt auf Abschlusscut
`589729471b39ef218397663480905a36fd03dd16` und bindet Produktset
`c41b9643...`, G6-Siegel `b339a274...`, den engen G6-Claim 5/5 anwendbar mit
physischem Produktmedien-WP als profilgebundenem N/A sowie Bundle-SHA
`5bea5ca9...`.

Der R7-Packer baut kein Produkt. Er kopiert alle 13 Artefakte ausschliesslich
aus dem im registrierten G6-Siegel enthaltenen R6-Ship und bettet dieses
Siegel als Beweisquelle in `releases/lisp65-1.0.0.tar.gz` ein. Zwei in
Hashseed und Zeitzone variierte Packs sind byteidentisch. Der paketinterne
Offline-Verifier prueft das G6-Siegel erneut, vergleicht 13/13 Produktbytes
gegen dessen Ship und lehnt Manipulationen an Produktbyte, Manifest und
Quellsiegel ab. Produkt- und Kapazitaetsdelta sind null. Die Freigabe ist
privat; eine oeffentliche Veroeffentlichung bleibt ein eigener Schritt.

## 2026-07-15: lisp65 1.0.1-light paketkorrigiert und oeffentlich veroeffentlicht

Owner-Freigabe ist `1.0.1-light`: ausschliesslich korrigierte Erstsession-
Ladereihenfolge, Nutzerhinweise und Release-Metadaten, ohne Produktcode,
FASL-Slot-Provisionierung oder neue Hardwarebehauptung. Produktset
`c41b9643ada1...` bleibt 13/13 byteidentisch zu 1.0.0. Der neue statische
15-Faelle-Preflight und Receipt `18b3993cc3b1...` binden das Paket an die fuenf
historischen G6-Fallreceipts; null Hardwarefaelle wurden neu ausgefuehrt.

Der R7-Doppelpack erzeugt `releases/lisp65-1.0.1.tar.gz` mit 318.582.072 Bytes
und SHA `2706beca7d47...`. Der paketinterne Offline-Verifier konsumiert das
unveraenderliche G6-Siegel `b339a274...`, prueft den Paket-Rebind und lehnt
Manipulationen an Produktbyte, Manifest, Quellsiegel, Rebind-Receipt und README
ab. Der private annotierte Tag `v1.0.1` besitzt Objekt
`a567bfa62203...` und zeigt auf Cut `547947116b96...`.

Der kuratierte oeffentliche Snapshot bindet 642 Dateien an privaten Exportcut
`7ea0cb4e88d2...`. Oeffentliches `main` und Tagziel sind
`456ce01211fd...`, Tagobjekt ist `d56ae548fc91...`. GitHub-Release
`https://github.com/novemberist/lisp65/releases/tag/v1.0.1` ist weder Draft
noch Prerelease. Tarball, Manifest und Receipt wurden nach Upload vollstaendig
zurueckgelesen; GitHubs Groessen und SHA-256-Digests stimmen mit den lokalen
Siegelwerten ueberein. Branch- und Tag-Refs beider Repositories wurden per
`ls-remote` gegen die lokalen Refs geprueft.

## 2026-07-17: 1.1-G keeps the green surface and defers unsafe or unfunded edges

The owner authorizes `read-from-string` and `restart-repl` for the Wave-2
candidate against their measured capacity delta. `restart-repl` remains a
hardware-not-run claim until the fresh Wave-2 G6 case. The approved
`gc`/`room` and `(error string)` contracts may proceed to bounded
implementation probes; their capacity deltas still require separate review.

The complete tick hook moves to C2. There is no prompt-only idle substitute in
1.1 because it would support neither honest `(time)` semantics nor a running
game loop, while callbacks from `lisp_poll()` or an IRQ are not reentrancy
safe. The `ticks` tombstone and parity revalidation input follow C2.

The bit operations `logand`, `logior`, `logxor`, and `ash` move to C2.2. The
compact-opcode cut passes the ABI gate but exceeds the u16 Attic shelf catalog
by 327 bytes; the runtime-slice cut exceeds its cap by 603 bytes. C2.2 already
owns the required catalog evolution, so reclaiming space in the retiring
format is rejected. `peekw` and `pokew` remain tombstoned: signed 15-bit
fixnums cannot represent their full unsigned result, and their advertised
bit-composition route is unavailable until C2.2. Attic shelf catalog headroom
becomes a standing numeric budget before every Wave-3 planning pass.

Sources: `docs/planning/development-plan-1.1.md`,
`docs/planning/v11-g-contract-drafts.md`, and
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-bitops-architecture-probe-receipt.json`.

## 2026-07-17: State/error carrier attempt exhausted; C2.2 fallback takes effect

The owner authorized exactly one generic private-service facade/co-pack
attempt for `gc`, `room`, and `(error string)`. Success required both resident
fit and carrier-window fit in one real product link; cap relaxation, reclaim
series and a second tuning attempt were excluded in advance.

The link fails both axes. Resident BSS ends at `$c43a`, 228 bytes beyond the
fixed `$c356` boundary. `lcc-install-01` is 2,007 bytes, 215 bytes over its
1,792-byte hard window; `lcc-install-02` is 1,560 bytes, 280 bytes over its
planned 1,280-byte co-pack allocation. The attempt is therefore exhausted and
the pre-authorized fallback is active: all three names are absent from the
1.1 ABI and public surface and move together to C2.2. Their direct/`funcall`/
`apply`, allocation, unwind, maximum-String and NUL semantics remain pinned as
historical host evidence; no product or hardware claim is inferred.

The product delivery sources are byteidentical to pre-attempt commit
`0da2d57`, and the canonical five-container shelf is restored to 65,368 bytes
with 167 bytes of u16 catalog headroom. That remainder cannot carry H/I/J as
planned shelf modules. Wave 3 is consequently owner-gated between a
shelf-free 1.1 cut (L-lite only plus neutral corrections) and one bounded
L65S-v4 staging-catalog probe derived from the C2.0 address contract.

Sources: `config/v11-g-state-error-contract.json`,
`config/v11-g-private-service-pack-plan.json`,
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-state-error-implementation-probe-receipt.json`, and
`docs/planning/wave-3-shelf-feasibility-2026-07-17.md`.

## 2026-07-18: Wave-2 closes error text and metadata contracts; list core earns a credit

The requested error-text library is not implemented a second time. The
already shipped L65E-v1 reusable runtime-overlay slice is the canonical
delivery: 60 stable codes, 43 Workbench texts, a resident `Ehh` fallback,
1,240 bytes inside its existing 1,320-byte window, and zero capacity delta.

Treewalk and CALLPRIM list mutation now delegate `nreverse`, `rplaca`, and
`rplacd` to one implementation while their strict-arity and route-specific
error contracts stay outside that core. All existing list and native-view
parity gates remain green. Isolated product links show a 12-byte resident
credit (`vm_callprim` −108 B, shared/Treewalk path +96 B) and no movement in
EXT, fixed overlay, runtime bank, island, installer, symbols, Namepool,
Directory, or shelf. The owner authorized the credit; the common Wave-2 repin
absorbs it without an intermediate product identity.

The function-metadata result is a SHA-bound host contract, not a false device
delivery claim. Its 136 public records include 102 exact arities decoded from
their code objects and 34 explicitly unresolved native/macro authorities;
missing signatures and docstrings remain null. Complete `ide-help` delivery is
therefore gated. The failed one-shot L65S-v4 result moves the future
reset-persistent metadata index with H/I/J behind C2; a product-D81-only side
file remains forbidden by the one-swap rule.

Sources: `config/v11-wave2-error-text-library-contract.json`,
`config/v11-wave2-list-primitive-unification.json`,
`config/v11-function-metadata-contract.json`, and their Wave-2 receipts under
`tests/bytecode/dialect-v2/evidence/architecture-blocks/`.

The same common repin applies the separately prepared 16-name harvest. Public
M-x spellings remain Strings and map directly to numeric command IDs; the
private buffer state reuses the value cell of the public `ide-buffers` symbol;
`bytecode` remains the sole retained kind symbol. All 18 echo cases pass. The
measured composition moves from 303 to 319 free symbols and from 4,702 to
4,884 free Namepool bytes. Removing the literal names also shrinks IDE and the
L65S-v3 shelf by 200 bytes, taking u16 shelf headroom from 167 to 367 bytes.
The complete real-link delta is favorable or neutral in every pinned
dimension: Bank reserve 1,849 → 1,861, Peak/Post EXT headroom +200/+2, with
Overlay, runtime bank, island, installer, Directory, and code-buffer pins
unchanged. The bound common-repin receipt is
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-common-repin-receipt.json`;
fresh Wave-2 G5/G6 hardware evidence remains required.

## 2026-07-18: `restart-repl` contract reopened after fail-fast hardware smoke

The first Wave-2 G6 invocation of the public `restart-repl` surface exposed a
contract error: the implementation and its real-link gate deliberately jumped
through `$FFFC`, but the stock MEGA65 platform reset returns to BASIC rather
than rerunning the mounted product. The case stopped receipt-less at 2/5
applicable G6 cases. Historical R4/R5 evidence for product set `6c358e79...`
remains immutable.

The owner required a product-local self-restart and authorized a three-byte
direct candidate (`LDX #$FF; TXS; JMP _start`) subject to a receipt-less
hardware pre-smoke. That pre-smoke did not return to a fresh banner and prompt.
Static CRT shape had proved initialization instructions, not re-entrant product
behavior; live Bank 5 is already patched and extended by the session.

A single bounded recovery design then tried to preserve the verified 16-KiB
Bank-5 boot window in Bank 7 and restore it before `_start`. Immediate JTAG
readback invalidated the design assumption: MEGA65 Fast RAM is 384 KiB at
`$00000000..$0005ffff` (Banks 0--5); `$70000` read back as 16,023 zero bytes
even immediately after an `m65 -@` load reported there. No valid recovery-image
execution occurred. The direct and recovery product changes were rolled back;
the resident and linked PRGs are byteidentical to the pre-fix Wave-2 candidate,
post-boot reserve is again 1,861 bytes, and neither the authorized three bytes
nor the unapproved recovery costs are booked.

The product-local fresh-session contract remains mandatory and load-bearing
for the deferred `unload` rationale, but its implementation is reopened. A
later proposal must either restore a pristine image through a valid Attic
path or define and prove a complete in-process reset. It is a new reviewed
probe, followed by the fail-fast smoke and the complete identity-bound cycle;
static linked control flow is never again sufficient evidence for this surface.
The diagnosis is bound by
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-self-restart-probe-receipt.json`.

## 2026-07-18: Bounded Attic whole-image restart attempt failed its only link

The owner approved one non-iterative attempt to capture the cold-stager-
verified Bank-5 image as a reconstructible Attic tenant at `$08200000` and
restore it before product-local CRT re-entry. The contract required generation
and full SHA-256 identity before restore, CRC32 over header and payload, a
second payload CRC32 after restoration, and a fail-closed
`restart unavailable - reboot from disk` outcome. Host mutation gates and the
separate stager budget passed.

The one authorized real product link failed before producing a candidate.
Resident code moved the BSS front by 1,291 bytes and, with 32 bytes of
`.noinit`, ended at `$c83c`, overlapping the fixed runtime-overlay VMA `$c356`
by 1,254 bytes. A separate compiler warning exposed an independent invalid
assumption: llvm-mos `uintptr_t` is 16-bit, so converting physical address
`$00050000` through it produced zero. Per the owner rule there was no second
link, no tuning round and no hardware smoke. The complete probe implementation
was rolled back and no debit was booked.

The C2 inheritance is explicit: Bank 5 is mutable session state before C2 and
cannot be restarted by CRT entry alone, while a resident whole-image verifier
and restore path does not fit the current boundary. C2 must reduce the restore
surface through its immutable/mutable split rather than fossilize this failed
pre-C2 mechanism. Wave 2 remains blocked on `restart-repl`; any next direction
requires a fresh owner decision. Receipt:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-attic-recovery-probe-receipt.json`.

## 2026-07-18: `restart-repl` leaves 1.1 and becomes mandatory C2.3 freight

The owner ends pre-C2 implementation attempts after three independently
rejected architectures: platform reset exits to BASIC; direct CRT re-entry
reuses session-mutated Bank 5; and the correctly identity-bound Attic
whole-image restore exceeds the resident boundary by 1,254 bytes. These are
not three local defects but one missing invariant: immutable executable state
and mutable session state are not separated before C2.0.

Wave 2 therefore removes the public wrapper, resident control action, surface
entries, host witnesses and double-restart G6 evidence. It continues with
`read-from-string` and the rest of its already accepted product scope. The
feature-specific R3 stop is removed; normal capacity and product-identity gates
remain. `restart-repl` is not deleted: C2.3 must deliver it and must invoke it
twice on real hardware to prove stack and mutable-state idempotence, unchanged
Attic code identity and unchanged media.

The `unload` deferral no longer claims that fresh sessions are cheap in 1.1.
Its remaining reasons are the C1 lease/retirement coupling and the narrow LIFO
utility. The 1.1 escalation ladder is RUN/STOP to abort while preserving the
session, product-disk restart for a fresh Lisp65 session, and power cycle for a
cold machine.

The failed Attic probe also establishes a local platform rule: a 28-bit
physical DMA address is not a C pointer and must remain `uint32_t` or explicit
DMA-list bytes. llvm-mos warned correctly when `$00050000` was converted
through 16-bit `uintptr_t`; L7 is therefore only a documentation question to
verify against current upstream docs, not a reported compiler bug.

The fully regenerated product graph closes the removal as a credit-only
capacity change: post-boot Bank reserve rises by 46 bytes, the resident EXT
image shrinks by 36 bytes, EXT-code headroom rises by 14 bytes, and the
composition recovers one symbol plus 13 Namepool bytes. All structural slices,
Directory and shelf are unchanged. Removing the exact-arity function also
repins the live host metadata boundary from 136/102/34 to 135/101/34
(records/exact/unresolved). The scope receipt remains explicitly non-promotional
until these exact credits are absorbed by the common Wave-2 repin.

## 2026-07-18: Decision Log remains the living append-only chronology

The earlier housekeeping classification of this file as a frozen pre-1.0
record was factually wrong: post-1.0 owner and architecture decisions continue
to be appended here. The planned move under `docs/archive/` is revoked. The log
stays at `docs/decision-log.md`; historical language and path strings remain
unchanged, and the header makes their provenance status explicit.

## 2026-07-19: lisp65 1.1.0 is sealed and published

The owner accepts the Wave-3 close and the lisp65 1.1.0 release. Product set
`048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024`
contains 14 artifacts. Its global G5 proof is 14/14 hardware-green, and its G6
proof is 5/5 for all cases applicable to the tested single-device stock-core
SD-D81 profile. The physical product-medium write-protect case remains
explicitly not applicable because that profile exposes no physical or virtual
write-protect medium; no unqualified 6/6 claim is made. The registered G6 seal
is
`c6a00b232a0dcd5bc3bbf1b6ab6869ef8d97ef6720d32415d881a9bb08d206ae`.

R7 consumed only the registered G6 seal and copied all 14 product artifacts
byte-for-byte. Two varied-environment packs were identical, the archive
verified offline from its own contents, and six independent mutations were
rejected. The resulting `lisp65-1.1.0.tar.gz` is 1,391,636,779 bytes with
SHA-256
`f121004d382dacb85567480d0f80ac3415cc494cd6f4f54a753c9250a6adbcb0`.
R7 changes no product bytes and requires no repeated hardware cases.

The curated public source snapshot is commit
`36412982415ab2b949668459cee91195ccf0c3cb`, tagged `v1.1.0`, and published at
`https://github.com/novemberist/lisp65/releases/tag/v1.1.0`. The release
tarball, manifest and receipt were downloaded after publication and matched
their local digests. The private proof branch, the independently historied
public branch, both annotated tags, the release assets and the registered
promotion archives are distinct identities and were each checked against
their remote authority. The release is neither a draft nor a prerelease.

The release documentation preserves the accepted boundaries rather than
promoting them away: definition-to-first-call latency is 1.90--1.96 seconds
with isolated longer observations and C2/1.2 as the committed cure; function
metadata remains 101 exact plus 34 unresolved; `restart-repl` remains C2.3
freight; and color RAM does not yet scroll with character RAM. The generated
41-binding IDE keymap is both the documentation source and the test source.
The former fixed-slot and non-transactional `compile-string` errata retire
because arbitrary-name compiler output now uses the complete M65D COW
transaction.

## 2026-07-19: C2.0 address, identity and freight contract approved

The owner approves all five C2.0 review decisions: the session-local `BCODE`
to directory to image/ordinal chain; the exact C2I-v1 entry and literal
encodings; the substitutive no-dual-decoder transition; the generation,
publication-journal and reset rules; and the unchanged 3/3/3 freight order.

Review widened entry code length from u8 to u16 by consuming the former
reserved byte and re-laying out the still-exact 16-byte record. Legal lengths
are 1..65,535. Zero-length entries and hot-restage attempts in a live session
are permanent negative cases. This applies the prior u8-sector and u16-catalog
lessons before the format is implemented rather than after a product cycle.

C2.1 is authorized only as a separate internal proof target. This decision
does not change product bytes, authorize capacity, permit a dual decoder or
make an execution/performance claim. The KERNAL stays resident by default;
unmapping its 8,192-byte CPU window requires a separately reviewed combined
block that owns typed input, RUN/STOP, IRQ/NMI and Freezer map recovery.

## 2026-07-19: C2.1 pauses before bytes for a metadata-envelope addendum

The first proof-target seam audit found no authoritative C2I metadata header,
section counts, entry-flag bit assignment or binary-safe string-record rule.
The approved 32-byte L65S-v4 record has region positions, lengths and CRCs but
no free entry/literal counts. Hard-coded proof counts would therefore prove a
different decoder from the future product decoder.

No C2 image or product byte was emitted. The five approved C2.0 decisions
remain in force, but C2.1 implementation waits for review of the proposed
local 24-byte self-describing header. Expanding the shelf record is retained
as the costlier alternative; proof-only compile-time counts are rejected as
false evidence.

## 2026-07-19: C2I local 24-byte metadata envelope approved

The owner approves Option A without amendment. Every C2I metadata region is
self-describing through the local 24-byte header; the 32-byte L65S-v4 shelf
record remains only the identity-bound region locator. Entry and literal
record widths, section counts and offsets, binary-safe length-prefixed strings,
entry flag bits and literal kind IDs are now fixed before the first image.

C2.1 must emit and decode this exact envelope. Expanding the shelf record is
not selected, and proof-only compile-time counts remain forbidden. This
approval authorizes only the separate internal proof target, not product bytes,
capacity or an execution claim.

## 2026-07-19: C2.1 product-layout link pauses at the mutable directory envelope

The direct C2 image, four-engine routes, negative matrix and independent MOS
target proof passed without changing the product. The first full-composition
substitution step then found that the approved mutable session plane names its
fields but does not define their byte-level envelope. Hard-coding the current
six images or inventing proof-only arrays would recreate the already rejected
proof-diverges-from-product class.

Generated manifests bind the current input at six images, 583 callable entries
and 2,084 literal resolutions. The recommended C2D-v1 layout is a
self-describing 10,150-byte mutable table in the Bank-5 region released by the
old materializers. Retiring the existing 761-byte Bank-0 directory arrays and
retaining 64 bytes of hot cache yields a projected 697-byte Bank-0 data credit.
The descriptor-on-call fallback is 4,320 bytes but changes the approved
directory semantics and needs a hardware latency proof. Fixed Bank-0 arrays
miss the reserve target by 9,018 bytes before code.

No product byte or pinned capacity changed. The product-layout link remains
paused pending owner review of the session-directory addendum.

## 2026-07-19: External C2D-v1 session directory approved

The owner approves Option A without amendment. The mutable session plane is a
self-describing C2D-v1 table in the Bank-5 region released by the retired
materializers. Its final header is the publish-last commit marker after the
export journal succeeds. The descriptor-on-call alternative remains an
unselected fallback requiring a contract amendment and hardware latency proof;
fixed Bank-0 arrays remain structurally rejected.

The approved current arithmetic is 10,150 bytes for six images, 583 callable
entries and 2,084 resolutions. Retiring 761 bytes of legacy Bank-0 directory
data while retaining 64 bytes of hot state projects a 697-byte Bank-0 data
credit. These are layout-probe inputs, not a capacity authorization or product
claim.

The C2.2 repin must redefine the capacity vocabulary for the new geometry:
immutable Attic code/metadata, the Bank-5 C2D mutable plane, the hot code
window and remaining runtime slices replace the old resident-EXT-code and
28-materializer-slice terms.

## 2026-07-19: Full C2 emission pauses at recursive literals

The complete six-image manifest census found 2,084 literal nodes. Four IDE
LIST nodes carry 168 child edges, but the approved C2I-v1 vocabulary has no
recursive CONS or LIST representation. The earlier direct proof used only
entry references and therefore remains correct but does not cover this format
class. No complete image or product byte was emitted.

The recommended repair is strict C2I-v2 with a backward-only cons-pair kind and
canonical LIST-to-cons lowering. It adds 165 net descriptors, 1,320 immutable
metadata bytes and 330 C2D resolution bytes; the table becomes 10,480 bytes and
leaves a projected 40,336-byte Bank-5 margin. The smaller edge-section format
is the bounded fallback. Retaining the L65M recursive materializer or rewriting
only today's four IDE constants is rejected as mixed-decoder or census-specific
behavior. Owner format review is required before full-composition emission.

## 2026-07-19: C2I-v2 backward-only cons lowering approved

The owner approves Option A. C2I-v2 represents recursive aggregate literals as
backward-only cons-pair descriptors and lowers each legacy LIST canonically to
a chain ending in the shared NIL descriptor. Forward and self pair references
are format errors; the negative matrix must reject both. The resolver must be
iterative or prove its stack bound against the longest current chain.

The version change is free only because no product has shipped C2I-v1. C2I-v1
remains immutable historical proof evidence, there is no dual decoder, and the
same change after a product seal would require a migration contract. The edge
section remains unselected. This approval changes no product byte and spends no
capacity.

## 2026-07-19: Full C2 emission pauses at general-symbol semantics

The complete six-image census contains 979 legacy SYMBOL literal nodes with
344 distinct spellings. They are general Lisp values: the same representation
serves quoted data, variables, compiler opcode names, future designators and
function names. Name equality therefore cannot prove a callable edge, and
encoding every node as C2I's export-name kind would fabricate API provenance.

The recommended zero-record-byte repair is C2I-v2 kind 8,
`general-symbol-name-offset`. It reuses the binary-safe local string pool and
interns the value without asserting a function binding. Kind 5 remains
exclusive to compiler-proven cross-container callable edges naming declared
exports. All legacy SYMBOL nodes map to kind 8 because the old artifact carries
no use provenance. C2D remains 10,480 bytes with 40,336 projected Bank-5 bytes
free; the new decoder branch is intentionally unpriced until a real link.

No full-composition image or product byte was emitted. Owner format review is
required before implementation continues.

## 2026-07-19: C2I-v2 general-symbol kind 8 approved

The owner approves Option A. C2I-v2 kind 8 represents general symbol values;
kind 5 remains exclusive to compiler-proven cross-container callable edges
naming declared exports. Every legacy SYMBOL maps to kind 8 because its
spelling carries no use provenance. Name equality is never sufficient to emit
kind 5.

All graph consumers inherit the same boundary: tree-shaking, `who-calls`,
ide-help cross-references and future call-graph tools may treat only kind 5 as
call evidence. Kind 8 is invisible to them and may not be upgraded by spelling.
The format, record, descriptor and C2D byte deltas are zero; the decoder branch
is priced by the real link. Full C2I-v2 emission may proceed.

## 2026-07-19: Full six-image C2I-v2 host emission closes

The consolidated C2I-v2 contract has emitted and independently decoded all six
generated manifests. The result contains 583 entries and 2,249 descriptors;
all 2,084 legacy nodes compare semantically. Canonical lowering produces 168
backward pair descriptors and one shared NIL, with a longest chain of 74. The
resolver uses one forward pass and no recursive decoder walk.

All 979 legacy SYMBOL values are kind 8. Kind 5 remains zero, including the
twelve current spellings that also name declared exports; spelling does not
become provenance. A dedicated consumer gate binds kind 5 as the only call
evidence for tree-shaking, `who-calls` and ide-help. Fifteen mutations cover
both version directions, pair direction, kind-8 records, kind-5 declaration
and emitter provenance, zero entry length and magic. A separate fixture keeps
two references to one descriptor identical.

The exact C2D-v1 table is 10,480 bytes and leaves 40,336 bytes of its Bank-5
session region. This remains a host architecture proof: product bytes and
capacity are unchanged, and target decoder, product link and device execution
are not claimed.

## 2026-07-19: Independent C2I-v2/C2D-v1 target decoder links

A separate C implementation validates a compact vector derived from the same
C2I-v2 contract. It covers one complete entry record, kind 8, shared descriptor
identity, two backward pair levels, L65S-v4-direct and C2D-v1 region binding.
The host executable passes and the pinned llvm-mos MEGA65 compiler produces a
real 4,276-byte PRG (4,274 bytes text, 80 bytes BSS).

This is deliberately not booked as product capacity. CRT, proof control and
unsliced validation are present, the artifact was not run on a device, and no
product source or byte changed. The result supplies an independent target
boundary and a conservative sizing input for the real substitution link.

## 2026-07-28: `defstruct` freight parked after Link-75 fail-closed

The owner selects Option A. The hardware-proven `require` foundation remains:
the first `(require 'defstruct)` and its generation-idempotent repeat both
returned `t` from Link 75 with product-bound `SESS` media. The subsequent
`(defstruct point x y)` entered the red fail-closed frame without a result or
trailing prompt.

`defstruct` therefore leaves active 1.2.x freight. No retry, diagnosis,
product/library fix, new link or hardware run is authorized. The clean
homogeneous/mixed DMA measurement is not reopened. Restart requires a new
explicit commission and begins from
`docs/planning/c2.2-link75-defstruct-red-frame-owner-decision.md`, whose R-1,
R-2 and R-3 entries preserve the IRQ gap, latency attribution and method
order. Released v1.2.0 is unchanged.

## 2026-07-28: Link 76 closes strict interrupt ownership

The strict ownership cut masks Ethernet, Auto-IEC and Audio-DMA before the
owned raster IRQ is enabled. The exact-core inventory structurally excludes
F011/SD and Buffered-UART as CPU interrupt sources and records
interrupt-generating cartridges as unsupported.

The first WPLTO exposed a 42-byte fixed-handoff overflow. The accepted repair
moved the unchanged 108-byte, boot-only `c2k_crc16` body into ordinary
resident text. The final ELF proves that it executes before ownership, has
exactly one direct caller and is unreachable afterwards. The resulting
handoff is 223/289 bytes; WPLTO leaves 243 bytes text headroom, the exact
54-byte E000 floor and 113 bytes session-family headroom. Sixteen source,
placement and policy mutations are rejected.

Exactly one product link produced Link 76,
`569cb2496aa0d251e989a31edf2015880599029a7b6ccb69c8a9c6d3b5373343`.
The three mask-register hardware readbacks remain bundled with the final
Phase-V session; no on-metal effectiveness claim is made yet.

## 2026-07-28: Phase V1 `random` is host-green

The first visible post-release freight is a pure-Lisp additive lagged
Fibonacci generator in the base composition, not a dynamic library. Its
55-slot state and cursor live only in canonical Lisp symbol values.
Rejection sampling prevents modulo bias; the permanent fixture proves an
actual reject-then-accept path.

Against Link 76 the host artifact adds 489 bytes of Bank-2 code, 77 bytes of
directory data, eleven code objects and 31 resolution words, with zero
resident bytes or overlay records. Projected Bank-2 headroom is 24,301
bytes. Nine mutations reject bias, state, lag, arithmetic, input-consumption
and parked-loader dependencies. Product link and hardware remain pending
until the `while` contract is reviewed.
## 2026-07-29 — Halt #3: `while` contract accepted

The owner accepted `(while test form*)` as structured local iteration, not as
a non-local-exit primitive. The cut uses only `JFALSEREL`/`JMPREL`, adds no VM
opcode, resident state, permanent root, C2J field or overlay record, and binds
four execution views including the compiler carrier actually packaged into
the product. Implementation and exactly one WPLTO probe are authorized; a
product link and hardware run are not.

The proof must execute a loop whose backward edge crosses a streamed VM
code-window boundary and report logical steps separately from window refills.
The target-window reload paid by every such admitted iteration is documented
as a performance property. If the complete cut cannot retain all Link-76
walls, it is parked with an exact scope number rather than reopening geometry.
