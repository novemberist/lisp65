# F011 Stdlib Binding Gap

Stand: 2026-07-01. Dieses Dokument ist der kompakte Handoff fuer Lane K zur aktuellen
F011-Stdlib-Grenze. Lane T beweist Transport und macht die Binding-Luecke reproduzierbar;
die Ursache liegt voraussichtlich im Kernel-/Runtime-Pfad fuer `load_source`,
Funktionszellen, Rooting oder GC.

## Reproduktion

Standard-Gate:

```sh
make xemu-f011-stdlib-smoke
make legacy-interim-ship-footprint-report
```

Layer-Probe plus dekodierter Report:

```sh
make f011-stdlib-layer-probe-report
```

Heap/Root-Matrix mit explizitem Funktionszellengap:

```sh
make f011-stdlib-profile-matrix
```

Die Layer-Probe schreibt `build/f011-stdlib-layer-probe-dump.bin` und danach
`build/legacy-interim-ship/footprint-report.txt` mit dekodierten
`str11_*`-Zeilen. Der normale
Ship-Report nutzt weiterhin `build/f011-autoload-dump.bin` und meldet ohne Probe-Dump
`str11_mask=missing`.

Der Report endet mit einer maschinenlesbaren Kurzfassung:

```text
F011 binding gap summary:
status=gap-observed
```

Im Standard-Report ohne Layer-Probe lautet der Status `no-layer-probe`.

## Aktueller Ist-Befund

Standard-F011-Smoke:

```text
loaded=25
chunks=25
bindings=1 mask 1
sentinels=1
functions=78 syms 178
free_cell_sample=16
```

Aktuelle Profilmatrix:

```text
expected_function_symbols=118
profiles=1254:256 1275:128 1300:96 1300:64
per-profile fn_gap is generated in build/legacy-interim-ship/f011-stdlib-profile-matrix.txt
min/max fn_gap is summarized in build/legacy-interim-ship/ship-readiness.txt
```

Layer-Probe:

```text
layer=lisp65 f011-stdlib-layer: 11 fns 78 syms 116 sent 1 str11 3
layer=lisp65 f011-stdlib-layer: 15 fns 77 syms 142 sent 1 str11 3
layer=lisp65 f011-stdlib-layer: 16 fns 77 syms 150 sent 1 str11 3
layer=lisp65 f011-stdlib-layer: 17 fns 77 syms 155 sent 1 str11 3
layer=lisp65 f011-stdlib-layer: 20 fns 77 syms 167 sent 1 str11 3
layer=lisp65 f011-stdlib-layer: 23 fns 77 syms 175 sent 1 str11 3
str11_mask=3
str11_names=%char-list=,string=,%char-list<
str11_bound=%char-list=,string=
str11_missing=%char-list<
```

## Statischer Sollverlauf

`make legacy-interim-ship-footprint-report` berechnet die erwartete
Funktionsflaeche aus den
chunked LOAD-Dateien:

```text
L10 ... expected_function_symbols=78 %let-vals,let,let*
L11 ... expected_function_symbols=81 %char-list=,string=,%char-list<
L12 ... expected_function_symbols=84 string<,string-append,%subseq-list
L15 ... expected_function_symbols=97 %reduce-from,reduce,every,some
L24 ... expected_function_symbols=118 dolist
```

Damit passt das Prelude-Ende bei `L10` exakt (`78`). Die Abweichung beginnt im ersten
String-Chunk `L11`: runtime sind `%char-list=` und `string=` sichtbar, `%char-list<`
aber nicht, obwohl der Chunk statisch genau diese drei Bindings enthaelt.

## Interpretation

- Der F011-Transport ist nicht die Primaergrenze: alle 25 Chunks werden geladen, und die
  Symbolzahl waechst bis `178`.
- Die Funktionsflaeche waechst ab `L11` nicht proportional zur Source-Flaeche; sie bleibt
  bei `77`/`78`, obwohl der statische Sollwert bis `118` geht.
- `str11=3` zeigt, dass der erste String-Chunk teilweise wirkt. Die Kante liegt also
  innerhalb oder unmittelbar nach der Evaluation der `L11`-Formen, nicht erst bei spaeteren
  Schichten.
- Naheliegende Lane-K-Pruefpunkte: `load_source`-Rooting ueber mehrere Top-Level-Formen,
  `set-symbol-function`/Funktionszellen unter engem Bank-0-Profil, GC-Root-Set waehrend
  Reader/Eval, sowie moegliche Pointer-Nichtpersistenz nach Chunk-Grenzen.

## Relevante Artefakte

- `scripts/f011-stdlib-smoke-main.c` emittiert die Runtime-Diagnose.
- `tools/host-lisp/stdlib_function_chunks.py --names build/legacy-interim-ship/stdlib-chunks` erzeugt
  den statischen Chunk-Sollverlauf.
- `scripts/ship-footprint-report.sh` dekodiert `str11` in sichtbare und fehlende Namen.
- `tools/host-lisp/f011_binding_gap.py build/legacy-interim-ship/footprint-report.txt` fasst den
  Report als `status=...` zusammen.
- `build/legacy-interim-ship/footprint-report.txt` ist der historische Bericht
  nach dem letzten expliziten Legacy-Report-Lauf.
