# Post-MVP Roadmap

Stand: 2026-07-12. Dieses Dokument ist **Planung nach dem MVP**, kein aktiver
Arbeitsauftrag. Der aktuelle Produkt- und Gate-Stand steht in
`docs/project-status.md` und `docs/workbench-gate.md`; dieses Dokument darf
keine neuen Gates erzeugen.

## Zielbild

lisp65 soll nach dem MVP nicht nur ein Lisp-Interpreter sein, sondern eine kleine
MEGA65-native Lisp-Arbeitsumgebung:

- interaktive REPL mit editornahem Workflow
- Lisp-geschriebene Standardbibliothek und Werkzeuge
- sauberes Laden von Nutzerdateien und Libraries
- ausgebauter kompilierbarer Funktionspfad ueber Bytecode
- spaeter optional ein nativer 45GS02-AOT-Compiler

Die Bytecode-VM ist durch den MVP-Pivot bereits Substrat. Die strategische
Reihenfolge nach dem MVP ist daher: **Runtime-/Load-Basis -> Emacs-like IDE ->
Bytecode/Compiler ausbauen -> AOT-Compiler**.

## Leitplanken

- **MVP bleibt zuerst.** Dieses Dokument darf keine neuen Gates fuer `make
  mvp-ship`, den VM-Stdlib-Ship oder die aktuelle Stdlib-Konformitaet erzeugen.
- **Kernel klein halten.** Editor, Help, Completion, Inspector und Compiler-Frontend
  sollen so weit wie moeglich in Lisp liegen. Der Kernel liefert nur stabile Primitive.
- **Bytecode vor Native-AOT.** Der P0-Bytecodepfad existiert bereits; nach dem MVP
  wird er verbreitert, debugbarer gemacht und als gemeinsame IR fuer spaetere
  Backends stabilisiert.
- **Eval-Semantik bleibt erhalten.** Im Geraeteprodukt routet `eval` lcc-first in den
  Bytecodepfad; Host-Treewalk und C-Compiler bleiben als unabhaengige Referenzen fuer
  Makros, Bootstrapping, Debugging und Drift-Waechter erhalten.
- **ANSI CL ist Referenz, nicht Produktversprechen.** Die Inventur in
  `docs/ansi-cl-inventory.md` trennt vorhandene Oberflaeche, essenzielle CL-nahe
  Luecken, machbare Library-Arbeit und bewusst ausgeschlossene ANSI-Familien.
- **Debuggability zaehlt.** Jede Compilerstufe braucht Quellbezug, Funktionsnamen,
  Backtrace-/Inspector-Hooks und einfache Dump-Tools.

## Freigegebener AP8.2-Block: Runtime Export

AP8.2 produktisiert zunaechst ein nicht-interaktives, extern gestagtes
Runtime-Appliance. Der Host staged nach jedem Power-Cycle den build-gebundenen
Bank-5-Preload und startet das PRG mit Inline-Boot-Overlay. Dieses Profil hat
bewusst keinen D81-/SD-Loader und verwendet keinen Attic-Katalog.

Die Reihenfolge fuer diesen Block war verbindlich. Stand 2026-07-12 sind alle
fuenf Schritte abgeschlossen:

1. **Abgeschlossen:** Das nichttriviale Demo wurde mit der echten Workbench-
   `lcc`/FASL-Route emittiert, kanonisch extrahiert und mit kompletter
   Provenienz als Golden versiegelt.
2. **Abgeschlossen:** Die zweite Workbench-Emission ist byteidentisch zum
   Golden. Der bewusst nicht bytegleiche Python-P0-Generator bleibt nur
   Differential-Oracle und keine Produktprovenienz.
3. **Abgeschlossen:** Whole-preload-Integritaet laeuft vor dem Runtime-Loader;
   Ship-/Manifest-v2 bindet Laenge, Build-ID, CRC/SHA und das symbolische
   Oracle fuer State, Resultat und Preload-Detailcode.
4. **Abgeschlossen:** Der lokale G4-Dry-run ist maschinell als offline und
   ohne Side Effects gegatet; der volle Candidate- und Reproduzierbarkeitscheck
   ist gruen.
5. **Abgeschlossen:** Auf echter Hardware wurden nach je einem physischen
   Power-Cycle der saubere Lauf und die drei fail-closed Klassen Truncation, Bitflip und
   fremde Build-ID (`build-id-mismatch`) mit atomaren Receipts geprueft. Der
   archivierte Vierphasen-Satz liegt unter
   `tests/bytecode/runtime/evidence/ap8.2-g5-589844f/`.

Ein autonomes **Runtime Export Standalone Boot** folgt nur als eigener
spaeterer Block. Er benoetigt D81/SD-Loader, Recovery fuer fehlende oder
korrupte power-volatile Preloads und einen erweiterten Capabilityvertrag;
`runtime_disk_loader=true` wird vorher nicht behauptet. Ebenso bleibt der
Workbench-Kaltstart nach Power-Cycle ein eigener offener G6-Vertrag. Die
existierenden Workbench-Reset-/Remount-G5-Belege schliessen ihn nicht.

## Freigegebener AP8.3-Block: Dialekt-v2-Migration

AP8.3 fuehrt einen harten Dual-Profil-Schnitt ein. Dialekt v1 bleibt als
Evidenzprofil eingefroren; Dialekt v2 wird ohne Runtime-Kompatibilitaets-Lib
familienweise aufgebaut. Der aktive Produktselektor bleibt bis zu einer
vollstaendigen v2-G5-Matrix auf v1.

Die verbindliche Reihenfolge ist Prelude/Control, Lists, Strings,
System/Runtime und zuletzt IDE. Jede Familie braucht Differentialfixtures und
einen manifestgebundenen Symbol-/Namepool-/Directory-Messreport. Directory-
only/L65M-v2, First-Class-Buffer, Export-only-Interning/`require`, `unload` und
neue Kontrollflussformen bleiben getrennte Architekturblocks. Buffer liegt
vor `unload`; die IDE-Internalisierung wartet explizit auf Directory-only.

Die konkrete Politik und ihre G5-Umschaltmatrix stehen in
`docs/dialect-v2-migration-contract.md`. Prelude/Control ist mit AP8.4
abgeschlossen: 76 profil-/engine-getrennte Beobachtungen und der reale
Budgetreceipt sind gruen. Als naechste Familie folgt `lists`; Strings wartet
weiterhin auf den getrennten First-Class-Buffer-Block.

## Phase 0: Post-MVP-Basis

Diese Schicht macht die spaeteren Features belastbar.

Konkreter Load-System-Startvertrag: `docs/load-system.md`. Er definiert Dateinamen,
Suchpfade, Modulnamen, `provide`/`require`, Autoloads sowie D81-/SD-Konventionen,
ohne das geparkte Runtime-I/O wieder in das MVP-Gate zu ziehen.

- natives `(load)`/`(save)` aus dem M4-Full-Produkt haerten und um Suchpfade/Module erweitern
- Library-Konvention festlegen: Dateinamen, Suchpfade, Modulnamen, Autoloads
- Fehlermodell verbessern: klare Meldungen, Abbruchpunkte, einfache Backtraces
- Introspektionsprimitive fuer IDE/Compiler: `symbol-function`, Funktionsmetadaten,
  Funktionsliste, ggf. Docstrings
- persistente Artefakte vorbereiten: Source-Libraries, spaeter Bytecode-Dateien,
  optional Images

Done-Kriterium: Nutzer kann eigene Lisp-Dateien auf Disk legen, laden, Fehler
diagnostizieren und danach in der REPL weiterarbeiten.

## Phase 1: Emacs-like IDE / Lisp Workspace

Die IDE bringt zuerst sichtbaren Nutzerwert und zwingt die Runtime in realistische
Workflows. Ziel ist kein vollstaendiges Emacs, sondern ein kleiner Lisp-Machine-artiger
Workspace.

Konkreter Startvertrag: `docs/editor-architecture.md`; die Feature-Reihenfolge steht in
`docs/ide-extension-plan.md`. Die erste IDE-Arbeit bleibt host-testbar und hardwarefrei:
Buffer-Datenmodell, Command-Loop, `eval-buffer`/`eval-region`/`eval-defun`,
Completion/Describe und ein spaeterer kleiner Screen-/Keyboard-Primitive-Satz.

MVP fuer die IDE:

- REPL/Minibuffer mit mehrstufiger History, Cursor-Navigation und mehrzeiligem Input
- Buffer-Modell in Lisp: Text als editierbare Struktur, mehrere Buffer
- `eval-buffer`, `eval-region`, `eval-defun`
- Symbol-Completion aus aktueller Obarray/Funktionsumgebung
- `apropos`, `describe`, einfache Help-/Docstring-Anzeige
- Fehleranzeige mit Ruecksprung in den Buffer, soweit Quellpositionen vorhanden sind
- minimaler Inspector fuer Symbole, Listen, Funktionen und Strings

Kernelbedarf:

- stabile Screen-/Keyboard-Primitive
- Datei-I/O fuer Lesen/Schreiben von Buffern
- Timer/Idle-Hook optional fuer UI-Responsiveness
- keine Editorlogik im Kernel, ausser wo Hardwarezugriff unvermeidbar ist

Done-Kriterium: Eine Datei kann im System editiert, evaluiert, gespeichert und nach
einem Fehler sinnvoll korrigiert werden.

## Phase 2: Compiler-/Bytecode-Substrat

Die P0-VM traegt den MVP. Nach dem MVP braucht es eine klarere interne
Compilergrenze und breitere Sprachabdeckung.

- Makroexpansion als expliziter Schritt
- kleine, dokumentierte IR fuer Special Forms, lokale Variablen, Closures, Calls,
  Konstanten und Spruenge
- Funktionsmetadaten: Name, Arity, Rest-Parameter, Quellinfo, Debugname
- definierte Grenze zwischen interpretierten und kompilierten Funktionen
- Tests, die gleiche Programme per Eval und per Compilerpfad vergleichen

Done-Kriterium: Host- und/oder Target-Compiler koennen eine wachsende Sprachmenge in
eine dokumentierte Zwischenform und den P0+/v1-Bytecode uebersetzen und gegen Eval
verifizieren.

## Phase 3: Bytecode-VM ausbauen

Die erste VM ist eine pragmatische Stack-VM und im MVP bereits aktiv. Post-MVP geht
es nicht um einen Neustart, sondern um Erweiterung, Debuggability und Dateiformate.

Opcode-Gruppen:

- Konstanten laden: NIL, T, Fixnums, Symbole, Strings, quoted Objects
- lokale/env-Zugriffe: load/store local, closed-over values
- Control Flow: branch, branch-if-nil, return
- Calls: call function, call primitive, tail-call optional
- Cons-/Listenpfad: cons, car, cdr, type predicates als schnelle Opcodes oder Primcalls
- Stack-/Frame-Operationen: dup, drop, maybe rotate

Artefakte:

- Bytecode-Objekt im Heap oder in separatem Codebereich
- Printer/Dumper fuer Bytecode-Funktionen
- Loader fuer Bytecode-Dateien
- Host-Assembler fuer Tests
- Lisp-Compiler fuer ein kleines, wachsendes Subset

Done-Kriterium: deutlich groessere Prelude-/Stdlib- und Nutzerprogramm-Teilmengen
laufen als Bytecode, mit Eval-Fallback fuer Makros und noch nicht kompilierte Formen.

## Phase 4: AOT-Compiler

AOT kommt in zwei Stufen.

1. **Bytecode-AOT:** Lisp-Source wird offline oder on-device zu Bytecode-Dateien
   kompiliert, die schnell geladen werden koennen. Das ist der naheliegende erste
   Packaging-Gewinn.
2. **Native 45GS02-AOT:** Bytecode/IR wird zu nativen Routinen kompiliert. Das lohnt
   sich erst, wenn VM, Metadaten, GC-Root-Konvention und Calling Convention stabil sind.

Native-AOT braucht vorher Entscheidungen zu:

- Calling Convention zwischen nativen Funktionen, VM, Eval und Primitives
- GC-Root-Maps fuer native Frames
- Closure-Repraesentation und Environment-Zugriff
- Code-Speicherlayout, Relocations, Labels und Debug-Dumps
- Fallback bei Debugging, Tracing und Fehlern

Done-Kriterium fuer die erste native AOT-Stufe: kleine leaf-Funktionen ohne Closures
und mit klaren GC-Root-Regeln laufen nativ und sind gegen Bytecode/Eval vergleichbar.

## Phase 5: Produktisierung

Wenn IDE und Bytecode stehen, werden Sprache und Umgebung zu einem nutzbaren System.

- Package-/Modulmodell
- Autoloads und vorkompilierte Libraries
- Session-/Workspace-Persistenz
- bessere Help-Systeme und Tutorial-Dateien
- BASIC-10/65-nahe Komfort-Libraries fuer Grafik, Sound, Sprites, Disk und System
  nach `docs/mega65-basic-parity-libraries.md`
- Performance-Dashboard: Eval vs. Bytecode vs. native AOT

## Offene Architekturentscheidungen

- Bytecode-Format: kompakt binaer, S-Expression-basiert, oder beides?
- Compiler-Ort: Host-only zuerst, on-device spaeter, oder beide parallel?
- Code-Speicher: Heap-Objekte, separater Codebereich, Banked RAM?
- Debug-Metadaten: wie viel Quellposition passt ins Zielsystem?
- Module/Packages: CL-nahe Packages oder kleineres Symbol-Namespace-Modell?
- Editor-Textmodell: Liste von Zeilen, Gap Buffer, Piece Table oder einfache Vektoren
  sobald Vektoren existieren?
- Image-Save: notwendig oder reichen Source-/Bytecode-Dateien?

## Naechste Dokumente nach dem MVP

Wenn der MVP stabil ist, sollten diese Designs zuerst entstehen:

- `docs/load-system.md` fuer `(load)`, Suchpfade, Module und Autoloads
  (**angelegt 2026-07-02**)
- `docs/editor-architecture.md` fuer Buffer, Commands, Eval-Pfade, Completion/
  Describe und Screen/Keyboard-Prims (**angelegt 2026-07-02**)
- `docs/eval-bytecode-equivalence.md` fuer kleine Eval-vs-Compiler/VM-
  Aequivalenztests (**angelegt 2026-07-02**)
- `docs/ansi-cl-inventory.md` fuer vorhandene und fehlende ANSI-CL-Funktionen/
  Makros nach Machbarkeit (**angelegt 2026-07-02**)
- `docs/bytecode-vm.md` fuer Opcode-Set, Frames, Datei-/Dump-Format
- `docs/compiler-ir.md` fuer Makroexpansion, IR und Eval/Compiler-Aequivalenztests

Bis dahin bleibt diese Roadmap bewusst grob. Sie soll Richtung geben, aber keine
aktuellen MVP-Lanes blockieren.
