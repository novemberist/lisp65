# Profil-Konsolidierungsstrategie: ein Workbench-Produkt

Stand: 2026-07-08. Anlass: Die bisherigen Budget-Fixes haben zu immer mehr
Spezialprofilen gefuehrt. Einzelne Profile sind technisch nuetzlich, aber als
Nutzerprodukt unhaltbar, wenn jedes nur einen Teil der gewuenschten Workbench
kann: lange Dateien ohne Compiler, Compiler ohne IDE, Runtime ohne Dev-Loop usw.

## Entscheidung

lisp65 bekommt wieder **ein sichtbares interaktives Produktprofil**: die Workbench.

Die Workbench ist der einzige Pfad, der als Nutzerprodukt gelten darf. Alle
anderen Targets sind Diagnose-, Referenz- oder historische Profile. Neue
Feature-/Budget-Fixes duerfen nicht mehr dadurch "geloest" werden, dass ein
weiteres halb-funktionales Produktprofil entsteht.

Das hebt die Runtime-Idee nicht auf. Ein schlankes Runtime-Profil bleibt als
**Export-/Deployment-Ziel** fuer echte Programme sinnvoll und wahrscheinlich
notwendig. Es ist aber kein zweites Alltagsprodukt, in das Nutzer manuell fuer
den normalen Entwicklungsloop wechseln muessen. UX-Ziel: Workbench schreibt und
baut ein Laufzeitartefakt; Runtime fuehrt dieses Artefakt aus.

## Aktueller Kandidat

Stand 2026-07-08 ist der Produktkandidat **Workbench = Arena-IDE plus
`compile-string`-/`compile-buffer`-Slow-Path, ohne native Disk-Source-FASL-
Schicht**:

- Makefile-Alias: `make workbench-candidate`
  (`mvp-vm-stdlib-einsuite-core-workbench`).
- Footprint-Gate: `make workbench-candidate-footprint-report`.
- Enthalten: REPL, manueller IDE-Start via `(edit)`, Packed-String-Arena, lcc,
  Disk-`load`/`save`, `load-lib`, `compile-string` als kleiner
  FASL/L65M-Backend-Pfad.
- Bewusst nicht enthalten: native `LISP65_FASL`-Prims. Diese Schicht kostet nach
  Messung etwa 1250 B Bank 0 und sprengt zusammen mit der Arena den Kandidaten.
- HW-IDE-Gate fuer die Arena selbst ist gruen: laengere Datei tippen/scrollen,
  `mem_oom=0`, kein Screen-Muell.
- HW-Compile-Roundtrip ist gruen: mehrformige Quelle via `compile-string` in
  vorallokierten Disk-Slot schreiben, `load-lib`, Ergebnisfunktion ausfuehren.
- HW-IDE-On-Demand plus Persistenzpfad ist gruen: D81 mit `ide`, `an`,
  `demo` und Compile-Zielslots; `load-file-to-buffer`, `save-buffer-to`,
  `compile-buffer-to-lib`, `load-lib` und Demo-Ausfuehrung liefen auf echter HW.
- Aktueller Cap-Pin nach Editor-/Save-New-Nachzug: `LISP65_SYMFN_EXT`,
  `NAMEPOOL=9536`, `MAX_SYM=720`, `SYMPOOL_EXT_OFF=0xc9e0`,
  `VM_DIR_MAX=552`, `GC_ROOTS=128`, `STR_ARENA_SIZE=0x2480`,
  `DISK_EXT_BASE=0x6900`, `DISK_EXT_FILE_MAX=0x9600`. Der
  RUN/STOP-IDE-Toggle ist aus dem residenten Pin entfernt.

Der Kandidat ist als **aktueller `mvp-ship`-Pin** gepinnt. `make mvp-ship`
erzeugt Workbench-PRG, externes Stdlib-Blob und ein D81 mit ladbarer IDE-Lib
plus vorallokierten Compile-Zielslots. Persistentes Datei-Compile heisst im
Workbench-Pin `compile-file-to-lib`; `compile-file` ohne Zusatz bleibt fuer
kuenftige transiente Semantik reserviert.

Wichtig: Ein kleiner `compile-string`-/`compile-buffer-to-lib`-Backend-Pfad ist nur ein
Implementierungshebel, kein neues dauerhaftes Sprachmodell. Der Nutzerworkflow
bleibt Datei-orientiert: Workbench bearbeitet und speichert Library-Quellen,
erzeugt daraus FASL/L65M-Artefakte, und Runtime laedt diese Artefakte spaeter.
`compile-file-to-lib` darf intern ueber "Datei in Arena-/Editor-String laden,
dann `compile-string`" laufen; die API darf aber nicht dauerhaft "Dateiname"
und "Quelltext-String" verwechseln.

### Nachzug: compile-string-Kandidat und Bank-0-Interpretation

Der aktuelle Workbench-Kandidat ist Arena-IDE plus `compile-string`/
`compile-buffer`-Slow-Path, nicht die alte native `LISP65_FASL`-Schicht. Der
Pfad kompiliert Quelltext aus einem Arena-/Editor-String und schreibt das
FASL/L65M-Artefakt ueber den generischen Save-Pfad. Der sichtbare Workflow
bleibt dateiorientiert: Quelle editieren, speichern, kompilieren, Artefakt
laden oder spaeter in Runtime ausfuehren.

Die gepinnte gruen gemessene Cap-Variante ist:

- `LISP65_SYMFN_EXT`
- `NAMEPOOL=9536`
- `MAX_SYM=720`
- `SYMPOOL_EXT_OFF=0xc9e0`
- `VM_DIR_MAX=552`
- `GC_ROOTS=128`
- `REPL_BUF_MAX=192`
- `STR_ARENA_SIZE=0x2480`
- `DISK_EXT_BASE=0x6900`
- `DISK_EXT_FILE_MAX=0x9600`
- `stack_gap=1612`
- `bank0_reserve=162`
- IDE-On-Demand plus kleiner Compile-Roundtrip hat Directory-/Symbol-Headroom

Nach der Bank-5-/Bank-4-Fensterkorrektur liegt das PRG-Ende bei `0xc0bc`
und damit 4 Bytes unter dem aktuellen Workbench-Gate. Der auf 192 Bytes
erweiterte REPL-Buffer kostet BSS/Stack-Gap, nicht PRG-Code, und ist deshalb
als Sofortgewinn vertretbar. `NAMEPOOL=9536` und `MAX_SYM=720` sind Teil des
Pins, weil der 8-KB-Namepool auf echter HW beim Demo-Compile trotz
Symbol-Headroom mit `too many symbols` ausstieg und der 9248er Namepool nach
`eval-buffer` beim aktuellen IDE-Load ebenfalls zu knapp wurde.

Diese Cap-/EXT-Kombination ist eine **MVP-Bruecke**, kein dauerhaftes
Architekturversprechen. `symfn` liegt im EXT-RAM; der aktuelle Pin hat bewusst
keinen Symfn-Cache, weil Cache-Varianten das PRG-Ende-Gate sprengten. Wenn
weitere Workbench-Pflichtfeatures wieder nur durch engere Caps, gelockerte
Stack-Gates oder Hotpath-DMA ohne Messung passen, gilt das als
Architekturproblem. Dann ist der naechste Schritt Reclaim, nicht ein neues
halb-funktionales Profil und nicht weiteres Abschaben von `MAX_SYM`,
`VM_DIR_MAX`, `GC_ROOTS` oder Stack-Gap.

## Workbench-Vertrag

Ein Workbench-Build muss den normalen Entwicklungsloop ohne Profilwechsel
abdecken:

- REPL bootet direkt und bleibt der interaktive Einstieg.
- IDE ist verfuegbar und kann realistische Dateien bearbeiten.
- Packed-String-Arena ist Pflicht, damit laengere Dateien nicht an
  char-list-Strings scheitern.
- lcc ist verfuegbar, damit neue Definitionen am Geraet kompiliert/installiert
  werden koennen.
- Disk-`load`/`save` und `load-lib` sind verfuegbar.
- Screen-/Editor-Rendering ist stabil; Syntax-Highlighting ist optional, aber
  kein Grund fuer ein separates Profil.
- Fehler duerfen in die REPL zurueckfallen, aber nicht in ein anderes Produkt
  zwingen.

Wenn eine Implementierung dieses Vertrags nicht ins Budget passt, ist das ein
Architekturproblem. Die Loesung ist dann Bank-0-Reclaim, residenten C-Code
reduzieren, Lisp/Bytecode-Slow-Paths oder echte Hardware-Speicherstrategie,
nicht ein neues Nutzerprofil.

Fuer den aktuellen MVP darf der Workbench-Vertrag durch einen knapp gepinnten
Cap-Satz erfuellt werden, solange die Gates gruen sind. Fuer Post-MVP-Arbeit ist
dieser Zustand jedoch als Schuldenindikator zu behandeln: neue Features muessen
entweder in Lisp/Bytecode/on-demand wachsen oder durch belegten Bank-0-Reclaim
finanziert werden.

## Runtime-Export

Echte Userprogramme werden voraussichtlich nicht dauerhaft zusammen mit IDE,
lcc, Workbench-Libs und vollem Session-Zustand in dasselbe Budget passen. Dafuer
bleibt ein Runtime-Pfad geplant:

- minimaler VM-/FASL- oder Bytecode-Loader;
- die fuer das Programm benoetigten Libraries;
- das Userprogramm als FASL/L65M/Blob/Disk-Artefakt;
- kein IDE-Editor, kein lcc-Dev-Komfort, keine Workbench-Diagnostik;
- Start ueber ein klares "Build/Run packaged app"-Modell aus der Workbench.

Der Unterschied zur alten Zwei-Produkt-Strategie ist der Workflow: Runtime ist
das Zielartefakt fuer groessere oder fertige Programme, nicht ein zweites
halb-funktionales Lisp-System, in dem man entwickeln soll.

### AP4-Zielarchitektur: Workbench plus Runtime-Export

Beschluss vom 2026-07-09: Lifetime-Reclaim und Runtime-Core werden kombiniert.
Die Workbench bleibt das einzige interaktive Entwicklungsprodukt. Runtime-Core
wird als separates, aus der Workbench erzeugtes Deployment-Artefakt mit eigenem
explizitem Profil, Namespace, Manifest und Budget gebaut. Beide teilen
Quellbaum, Objektmodell, Bytecode-ABI und L65M-Loadervertrag, erben aber keine
Feature-Flags voneinander und werden nicht ueber `filter-out`-Ketten erzeugt.

Heute sind zwei Binaries notwendig, weil Reader, REPL, lcc-Installation und
Treewalk-Bruecken native Entwicklungsflaeche sind. Langfristige Konvergenz ist
erst ehrlich, wenn diese Flaeche in ladbare Bytecode-/Bankmodule migriert ist.
Boot-Overlays sind stets profilgebunden und duerfen trotz gemeinsamer ABI nicht
zwischen Workbench und Runtime-Core ausgetauscht werden.

Der erste G2-Messprototyp liegt unter `config/runtime-core.mk` und
`build/products/runtime-core/`. Er ist evaluatorfrei und beweist den direkten
benannten Bytecode-Entry, enthaelt aber bewusst noch keinen Disk-Lib-Loader.
Damit bleibt die Profilgrenze messbar, ohne die bekannte L65M-Teilmutationsluecke
als fertigen Exportpfad auszugeben. Runtime-Exportstatus erhaelt das Profil erst
mit Preflight, App-Manifest, Paketverifier und Cold-Boot-Abnahme.

Der AP4.3-Linkprototyp bestaetigt die Profilbindung auch technisch: Ein
Runtime-Core-Split gewinnt 3091 B im Resident-PRG und packt das 3144-B-Overlay
mit Resident-/ABI-Hashes. Er ist kein gemeinsames Overlayformat fuer beide
Produkte. Verbindlich ist fuer Runtime Core ein resetfestes Inline-Boot-Overlay
und fuer die Workbench ein getrenntes EXT-Staging mit fail-closed DMA-Bootstrap.
Die Hardwareabnahme steht noch aus.

## Profil-Taxonomie

**Produktprofil**

- Ein Target: aktuell `make mvp-ship`.
- Muss das Workbench-Gate bestehen.
- Darf in README/Release-Docs als "das Produkt" erscheinen.

**Diagnoseprofile**

- Duerfen Features isolieren, bewusst Budget brechen oder Instrumentierung
  enthalten.
- Namen/Doku muessen klar als `diag`/`probe`/`smoke` erkennbar sein.
- Keine Nutzerempfehlung, kein MVP-Claim.

**Referenzprofile**

- Erhalten alte semantische Pfade fuer Equivalence/Regression, z.B. Treewalk-
  oder C-Compiler-Referenzen.
- Sie muessen nicht UX-vollstaendig sein.

**Runtime-Exportprofile**

- Schlanke Laufzeit fuer aus der Workbench gebaute Programme.
- Duerfen IDE/lcc/Dev-Komfort weglassen, muessen aber klar als Deployment-
  Artefakt dokumentiert sein.
- Gelten erst als Produktbestandteil, wenn die Workbench einen nachvollziehbaren
  Build-/Exportpfad dorthin anbietet.

**Historische/obsolete Profile**

- Bleiben nur so lange, wie sie aktiv beim Debuggen helfen.
- Wenn ein Target weder Produkt, Diagnose noch Referenz ist, soll es aus
  `make check` und spaeter aus dem Makefile verschwinden.

## Budget-Regeln

Ab jetzt gilt fuer Produktentscheidungen:

1. Arena-Strings sind Pflicht, kein optionaler Komfort.
2. lcc ist Pflicht, kein separater "Compiler-Build".
3. IDE ist Pflicht, kein separater "Editor-Build".
4. Disk-Load/Save ist Pflicht.
5. FASL/`compile-file-to-lib` ist ein Nutzerworkflow, aber nicht zwingend als
   fetter nativer C-Pfad. Wenn native FASL-Prims den Workbench-Vertrag sprengen,
   muss der Legacy-`compile-file`-Pfad ueber kleinere Lisp-/Bytecode- oder
   generische Disk-Pfade umgesetzt werden.
6. Runtime-only ist ein spaeterer Export-/Deployment-Pfad fuer echte Programme,
   aber kein Ersatz fuer die interaktive Workbench.
7. Neue C-Prims brauchen eine Budget-Begruendung im Workbench-Profil.
8. Neue Lisp-/Bytecode-Libs brauchen einen Session-Budget-Check, aber duerfen
   nicht automatisch neue Produktprofile erzeugen.

## Konsolidierungsplan

### P0: Profil-Proliferation einfrieren

- Keine neuen Nutzerprofile mehr.
- Neue Makefile-Targets muessen als Produkt, Diagnose oder Referenz markiert
  sein.
- Alte Doku, die zwei Produkte oder Dev-Core/Runtime-Core als aktuellen Plan
  beschreibt, bekommt einen Superseded-Hinweis auf dieses Dokument.

### P1: Workbench-Kandidaten ehrlich messen

Mindestmatrix:

- aktuelles `einsuite-full`
- aktuelles `arena-ide`
- Workbench-Kandidat: Arena + IDE + lcc + Disk-Load/Save + `load-lib`
- optional: derselbe Kandidat mit nativer FASL-Schicht, nur als Kostenmessung

Zu erfassen:

- PRG-Ende, Stack-Gap, Bank-0-Reserve
- Symbol-/Directory-Headroom
- externes Image und Sympool-Kollisionen
- String-Arena-Kapazitaet
- IDE-Tipp-/Scroll-Gate auf HW
- lcc-Install/Run-Gate
- Load/Save/Load-Lib-Gate

### P2: Einen Workbench-Pin setzen

Erledigt am 2026-07-08: `mvp-ship` ist auf den Workbench-Pfad gepinnt. Andere
Kandidaten sind Diagnose/Referenz.

### P3: Runtime-Export separat entwerfen

Nach dem Workbench-Pin bekommt der Runtime-Pfad einen eigenen Vertrag:

- Welche Artefakte erzeugt die Workbench?
- Welche Loader-/FASL-/L65M-Schicht muss im Runtime-Image resident sein?
- Wie werden benoetigte Libraries gebundelt?
- Welche Mindestprogramme muessen in Runtime laufen?

Dieser Pfad darf kleiner sein als die Workbench, aber er darf nicht den
Workbench-Loop ersetzen.

### P4: Bank-0-Reclaim statt Feature-Split

Wenn der Workbench-Pin nicht passt, priorisieren wir in dieser Reihenfolge:

1. native FASL-/Compile-File-C-Schicht aus dem Produkt entfernen oder zu einem
   kleineren Slow-Path umbauen;
2. alte Debug-/Probe-/Altpfade aus Produkt-CFLAGS entfernen;
3. Tabellen/Caps nur als gemessenen Produktpin nutzen, nicht als permanente
   Feature-Finanzierung;
4. residente C-Helfer durch Lisp/Bytecode ersetzen, wenn der Hotpath es erlaubt;
5. Boot-only-/dev-only-Code aus Bank 0 reclaimen, sobald der MVP-Pin steht;
6. Attic-RAM/Enhanced-DMA als echter Wachstumspfad fuer Daten, nicht als neuer
   Profil-Split.

### P5: Profil-Aufraeumung

Nach Workbench-Pin:

- Makefile-Kopf kommentiert klar: Produkt vs Diagnose vs Referenz.
- `make check` prueft nur das Produkt plus stabile Diagnose-/Referenz-Gates,
  nicht jede historische Profilvariante.
- Release-/README-Doku nennt nur die Workbench.

## Workbench-Gate

Ein Build ist erst Workbench-faehig, wenn mindestens diese Nutzerablaeufe auf
echter MEGA65 oder einem explizit akzeptierten HW-Gate gruen sind:

- Boot in REPL.
- IDE laden/starten.
- 40-60 Zeilen Lisp-Code tippen und scrollen, ohne OOM und ohne Screen-Muell.
- Datei speichern und wieder laden.
- einfache `defun`/`lambda`/Closure-Programme mit lcc kompilieren und ausfuehren.
- `load-lib` einer Disk-Lib.
- JTAG-Counter: `mem_oom=0` im Normalfall, `gc_badobj=0`.

FASL/`compile-file-to-lib` bleibt Ziel des Workbench-Workflows, darf aber erst
dann als Pflicht-Gate gelten, wenn seine Implementation in denselben Produktpin
passt oder als kleiner Slow-Path neu gebaut ist.

## Nicht-Ziele

- Kein drittes Nutzerprofil fuer "nur Compiler" oder "nur lange Dateien".
- Kein Runtime-only-MVP als Ersatz fuer die Workbench; Runtime ist Exportziel,
  nicht Entwicklungsersatz.
- Kein Feature als "geliefert" zaehlen, wenn es nur in einem halb-funktionalen
  Spezialprofil laeuft.
- Kein Bank-0-Fix durch Verschieben des Problems in ungetestete HW-Regionen.
