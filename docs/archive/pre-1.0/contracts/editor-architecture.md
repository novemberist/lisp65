# Editor/IDE Architecture

Stand: 2026-07-04. Dieses Dokument konkretisiert die Post-MVP-IDE aus
`docs/post-mvp-roadmap.md`. Es ist ein Designvertrag fuer Arbeit **nach** dem
eingebetteten VM-Stdlib-MVP. Es fuehrt kein neues MVP-Gate ein.

## Ziel

Die erste lisp65-IDE soll kein vollstaendiges Emacs sein. Ziel ist ein kleiner
MEGA65-nativer Lisp-Workspace:

- Dateien oeffnen, editieren, speichern
- `eval-buffer`, spaeter `eval-region`, `eval-defun`
- REPL und Editor teilen sich dieselbe Lisp-Umgebung
- einfache Completion, `apropos`, `describe`
- Fehler sollen auf Buffer/Region/Defun zurueckfuehrbar sein

Die Editorlogik liegt so weit wie moeglich in Lisp. Der Kernel liefert nur
notwendige I/O-, Screen-, Keyboard- und spaeter Datei-Primitives.

## Nicht-Ziele fuer die erste IDE

- keine Fenster-/Frame-Hierarchie wie in Emacs
- kein redisplay-Optimizer im Kernel
- keine native Gap-Buffer-/Piece-Table-Implementierung in C
- keine Abhaengigkeit von F011/D81-Runtime-Load fuer den ersten Prototyp
- keine vollstaendige CL-Condition-/Restart-Integration

## Buffer-Modell

Der erste Buffer ist eine Lisp-Struktur aus einfachen Bausteinen, bis Vektoren oder
dedizierte Textobjekte existieren:

```lisp
(name file-name lines point mark modified-p mode locals diagnostics)
```

Felder:

- `name`: Symbol oder String fuer die Buffer-Liste.
- `file-name`: String oder `nil`; erst aktiv, wenn das Load-/File-System steht.
- `lines`: Liste von Strings, eine Zeile pro Element.
- `point`: `(line . column)`, jeweils nullbasiertes Fixnum.
- `mark`: optionaler zweiter Punkt fuer Region-Operationen.
- `modified-p`: `t` nach editierenden Commands.
- `mode`: zunaechst `lisp-mode` oder `repl-mode`.
- `locals`: aktuell der aktive Zeilen-Write-Back-Cache
  `(line-index rev-codes length)` oder `nil`; spaetere mode-spezifische Optionen
  brauchen ein eigenes Feld oder ein erweitertes, versioniertes Locals-Layout.
- `diagnostics`: Liste von Fehler-/Warnobjekten mit Quelle.

Warum Liste von Zeilen: sie ist mit der aktuellen Stdlib darstellbar, gut testbar und
braucht keine neue Speicherrepraesentation. Spaeter kann die interne Darstellung auf
Gap Buffer, Piece Table oder Vektor umgestellt werden, solange die Command-API gleich
bleibt.

Der aktuelle MVP-Editor nutzt einen Ein-Slot-Cache fuer die aktive Zeile. EOL-Append
haengt das neue Zeichen vorn an `rev-codes`, EOL-Backspace entfernt den Kopf davon;
beides ist O(1), solange Cursor-Spalte und Cache-Laenge zusammenpassen. Die Zeile wird
erst bei `ide-buffer-lines`, Render oder Strukturwechseln wie Split, Mid-Line-Insert
und Zeilen-Merge materialisiert. `ide-insert-char` nutzt ausserdem Auto-Umbruch bei
`%ide-fill-column` 79, damit interaktives Tippen keine endlos langen Hotpath-Zeilen
erzeugt.

## Command-Loop

Commands sind normale Lisp-Funktionen mit einem einheitlichen Vertrag:

```lisp
(defun command-name (state event) ...)
```

`state` enthaelt aktuelle Buffer-Liste, aktiven Buffer, Mini-/REPL-Zustand und
optionale letzte Diagnose. `event` ist ein normalisiertes Tastaturereignis.

Phasen:

1. **Host-only Command-Tests:** Buffer-Funktionen laufen in den Host-Oracles ohne
   Hardware-I/O.
2. **REPL-integrierter Prototyp:** Commands werden als Lisp-Funktionen im aktuellen
   System geladen/eingebettet und koennen per Symbol aufgerufen werden.
3. **Keyboard-Loop:** Hardware-Tastatur liefert normalisierte Events.
4. **Screen-Redisplay:** Lisp berechnet ein Frame-Modell; Kernel rendert nur Zeichen.

Ein Keymap-Eintrag ist spaeter nur Daten:

```lisp
((ctrl-x ctrl-s) . save-buffer)
((ctrl-c ctrl-c) . eval-defun)
```

## Eval-Funktionen

Die Eval-Funktionen extrahieren Source-Text und uebergeben ihn an die vorhandene
Reader/Eval-/Compiler-Schicht:

- `eval-buffer`: konkateniert alle Zeilen mit Newline und evaluiert Top-Level-Formen.
  Im MVP-Pin existiert die schmale Produktform `(eval-buffer "buffer-name")`.
- `eval-region`: evaluiert den Text zwischen `point` und `mark` (deferred).
- `eval-defun`: findet die umgebende Top-Level-Form und evaluiert nur diese (deferred).

Rueckgabevertrag:

```lisp
(status value diagnostics new-state)
```

`status` ist `ok` oder `error`. `diagnostics` enthaelt mindestens Buffername,
Start-/Endposition und eine kompakte Fehlermeldung. Solange der Reader keine
vollstaendigen Quellpositionen liefert, duerfen Positionen approximativ sein
(z. B. Region/Defun-Start).

## Completion und Describe

Completion arbeitet zuerst rein ueber die Symbol-/Funktionsumgebung:

- `apropos`: Substring-Suche ueber bekannte Symbolnamen.
- `complete-symbol`: gemeinsames Prefix ueber passende Namen.
- `describe`: zeigt Funktionsstatus, Art (`primitive`, `closure`, `bytecode`,
  `macro`), Arity soweit bekannt, optional Docstring.

Minimal benoetigte Introspektionsdaten:

- Symbolname als String oder String-Liste.
- Prädikat: Symbol hat Funktionsbindung?
- Funktionsart: primitive/closure/bytecode/macro.
- Optional: Arity/Rest-Flag/Docstring/Source.

Was heute noch fehlt, bleibt ein klarer Kernel-/Runtime-Handoff fuer spaeter:
`symbol-name`, Funktionsmetadaten und eine iterierbare Obarray/Symbol-Liste.

## Screen-/Keyboard-Primitives

Die erste Hardware-UI braucht nur kleine Primitive. Die Editorlogik rendert daraus
ein flaches Frame aus Zeichen und Attributen.

Screen:

- `(screen-size)` -> `(columns rows)`
- `(screen-clear)`
- `(screen-put-char x y code attr)`
- `(screen-flush)` optional, falls Double-Buffering kommt

Keyboard:

- `(read-key)` blockierend
- `(poll-key)` -> Event oder `nil`
- Eventform: `(key code modifiers)`, z. B. `(key 65 (ctrl))`

Datei-I/O spaeter:

- `(read-file-as-string path)`
- `(write-string-to-file path text)`
- `(probe-file path)`

Diese Primitives sind absichtlich grob. Namen und genaue Signaturen werden erst nach
dem Load-System-Vertrag festgezurrt.

## Host-Test-Slices

Die IDE kann vor Hardware-UI in kleinen Host-Slices wachsen:

1. Buffer-Operationen: Insert/Delete/Split/Join/Move.
2. Region-Operationen: Mark, Region-Text, Replace-Region.
3. Lisp-Parsing-Helfer: Top-Level-Form-Grenzen fuer `eval-defun`.
4. Completion: String-Prefix/Search gegen eine feste Symbolnamenliste.
5. Describe-Modell: formatierte Metadaten aus Testdaten.

Done fuer den ersten Post-MVP-IDE-Prototyp: Host-Tests koennen einen Buffer editieren,
eine Region/Defun extrahieren, eine Completion liefern und einen Eval-Auftrag als
Source-String plus Positionsspanne erzeugen.

Aktueller erster Slice: `lib/ide-buffer.lisp` plus
`make ide-host-slice-check` deckt Buffer-Accessor, Insert/Delete, Region-Lines
und einfache Top-Level-Defun-Grenzen ab.

Aktueller zweiter Slice: `lib/ide-completion.lisp` erweitert denselben Host-Check
um `ide-apropos`, `ide-prefix-matches`, `ide-complete-symbol` und ein einfaches
`ide-describe-symbol`-Datenmodell. Das ist weiterhin reine Lisp-Logik ohne
Screen-/Keyboard- oder Runtime-Load-Abhaengigkeit.

Aktueller dritter Slice: `lib/ide-eval-request.lisp` baut aus Region oder
aktueller Top-Level-Form einen Eval-Auftrag `(EVAL-SOURCE buffer start end source)`.
Damit ist `eval-region`/`eval-defun` als Datenvertrag vorbereitet, ohne schon
Runtime-Loading, Editor-UI oder Device-I/O festzulegen.

Aktueller vierter Slice: `lib/ide-ui.lisp` fuehrt Command-Dispatch und Redisplay
als Lisp-Schicht ein. Punktbasierte Buffer-Operationen in `lib/ide-buffer.lisp`
koennen Zeichen einfuegen, Zeilen splitten, rueckwaerts loeschen und den Cursor
bewegen. `ide-step` normalisiert Tastaturereignisse wie `(key 97 nil)` zu Commands
und liefert einen neuen State; `ide-visible-frame-lines` berechnet das gekappte
Frame-Modell mit Statuszeile. `ide-render` haelt einen Render-Cache im State,
schreibt nur Dirty Lines plus alte/neue Cursor-Zeile und nutzt `screen-write-string`
fuer ganze Zeilen. Das Attribut-Bit `0x40` laesst die C-Primitive bis zum
Zeilenende auffuellen; der fruehere Lisp-seitige Padding-Helper wurde nach dem
Perf-Umbau entfernt. Der Cursor wird per RVS-Attribut `0x80` sichtbar gezeichnet.
Fuer Same-Row-Updates nutzt `ide-render` einen Fast-Path: bei
gueltigem Cache und unveraenderter Cursor-Zeile werden nur die aktuelle
Textzeile und die Statuszeile im Cache gepatcht und neu geschrieben. View-
Wechsel invalidieren deshalb den Render-Cache. Horizontales Scrollen ist wieder
entfernt: Auto-Umbruch bleibt der interaktive Schutzpfad, extern lange Zeilen werden
links beginnend auf die Bildschirmbreite gekappt. Die Live-Hardware-Schicht laeuft
ueber `ide-render`. Die frueheren
`ide-runtime-symbol-*`-Symbolbrowser-Helfer wurden nach dem
TAB-/Budget-Audit 2026-07-09 entfernt; Completion nutzt `(dir)`- und
Buffer-Listen statt Symboltabellen-Introspektion. Die aktiven Pfade sprechen
die Kernel-Primitives `screen-size`, `screen-write-string`, `screen-put-char`,
`read-key` und `poll-key` an und bleiben duenne Aufrufer um die host-getestete
Logik.

Fuer Performance-Debugging erzeugt `make ide-bytecode-cost-report` aus dem
aktuellen Stdlib-Manifest `build/bytecode/ide-bytecode-costs.txt`. Der Report
rankt IDE-Funktionen nach statischer P0-Payload-/Objektgroesse sowie statischen
Call- und Opcode-Zaehlern. Er misst keine dynamischen Call-Returns und keine
DMA-Reloads auf dem MEGA65; Fusionen im Render-/String-Hot-Path sollten deshalb
erst nach dem Geraete-Zaehler priorisiert werden. Der Render-Kontrakt ist
absichtlich verhaltensbezogen: Dirty-Line-Rendering, Bulk-Write und
Zeilenauffuellen muessen erhalten bleiben, aber Helper duerfen fuer die
MEGA65-Hot-Path-Kosten verschmolzen oder inlined werden.

`make ide-render-callgraph` schreibt zusaetzlich
`build/bytecode/ide-render-callgraph.txt`. Dieser Report verfolgt ab
`ide-render` die statischen `CALL`/`TAILCALL`/`CALLPRIM`-Kanten und markiert,
welche Kanten in der C-VM normalerweise einen rekursiven `vm_run`-Frame oder
einen nativen `vm_callprim`-Leaf bedeuten. Er misst keine Laufzeit-Tiefe; sein
Zweck ist, vor HW-Instrumentierung die wahrscheinlichsten Reentry-Kanten im
Renderpfad sichtbar zu machen.

`make ide-bytecode-dynamic-report` ergaenzt das um einen dynamischen Host-P0-VM-
Trace fuer konkrete IDE-Szenarien: einzelne Tastendruecke, kaltes/warmes
`ide-render`, langen Zeileninsert, wiederholtes Tippen mit Render pro Taste,
Backspace, Cursor-Navigation, 25-Zeilen-Render und Dirty-Scan. Der Report
schreibt `build/bytecode/ide-bytecode-dynamic.txt` mit dynamischen
Opcode-Zaehlern, Opcode-Paaren, Funktions-Hotspots und Call-Zielen. Er ist
weiterhin nicht zyklus- oder DMA-genau, liefert aber die belastbare Vorstufe
fuer P0-Superinstructions und gezielte Lisp-Helper-Fusion. `make check` fuehrt
den Report mit Total- und Szenario-Budgets aus, damit IDE-Tipp-/Render-Kosten
nicht unbemerkt wieder steigen.
