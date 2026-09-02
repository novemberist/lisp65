# Stdlib Footprint Polish

Stand: 2026-07-02. Diese Notiz haelt den aktuellen Bytecode-Footprint des
eingebetteten MVP-Stdlib-Sets fest und benennt konkrete Polish-Kandidaten.

## Aktueller Stand

Quelle: `make stdlib-footprint-rank` nach der Format-Helper-Bereinigung und
Number Surface P2.

- Embedded Funktionen: `126`
- Code-Bytes im Embed-Artefakt: `3302`
- Directory-Bytes: `882`
- Literal-Nodes/Patches: `142` / `142`
- Host-Embed-Oracle: `160` Cases gruen

Zwischenstand direkt nach Format-Dedupe, vor Number P2:

- `117` Funktionen
- `3203` Code-Bytes
- `819` Directory-Bytes

Vorheriger Stand vor Format-Dedupe:

- `118` Funktionen
- `3231` Code-Bytes
- `826` Directory-Bytes

Die entfernte Doppelung war `%format-arg-list` vs. `%format-display-list`.
`%format-display-list` liegt jetzt in `lib/stdlib-format.lisp`; die Extra-
Format-Schicht verwendet diese gemeinsame Helper-Funktion.

## Groesste Einzelobjekte

Top-Kandidaten nach Codeobjekt-Laenge:

```text
112  %format-directive          lib/stdlib-format-extra.lisp
 66  %case-key-tests            lib/prelude-m1.lisp
 58  %subseq-list               lib/stdlib-strings.lisp
 53  %case-key-test             lib/prelude-m1.lisp
 53  mapcar                     lib/stdlib-lists.lisp
 47  equal                      lib/stdlib-bytecode-bridges.lisp
 47  string-suffix-p            lib/stdlib-strings.lisp
 44  %char-list<                lib/stdlib-strings.lisp
 44  %nonnegative-digits        lib/stdlib-format.lisp
 43  %char-list-search          lib/stdlib-strings.lisp
 42  remf                       lib/stdlib-plists.lisp
```

Nach Quelle:

```text
872  lib/prelude-m1.lisp
861  lib/stdlib-strings.lisp
489  lib/stdlib-lists.lisp
229  lib/stdlib-math.lisp
217  lib/stdlib-format-extra.lisp
215  lib/stdlib-format.lisp
158  lib/stdlib-sequences.lisp
100  lib/stdlib-plists.lisp
 99  lib/stdlib-bytecode-bridges.lisp
 62  lib/stdlib-control.lisp
```

## String-Slice

Die teuersten String-nahe Funktionen sind:

```text
58  %subseq-list
47  string-suffix-p
44  %char-list<
43  %char-list-search
40  %char-list=
35  %char-list-prefix-p
36  substring
33  string-trim
32  %trim-left-list
29  string-append
28  %char-member-p
28  string-equal
```

Fazit: Weitere String-Erweiterungen sollten nicht automatisch in
`p0-stdlib-subset.json` landen. Kandidaten wie Split/Join, Replace,
Tokenisierung oder Editor-spezifische Scanner gehoeren zuerst in separate
Post-MVP-Suiten.

## Helper-Duplikation

`make stdlib-footprint-rank` meldet nach der Bereinigung keine exakten
Codeobjekt-Duplikate ab 20 Bytes mehr. Strukturelle Aehnlichkeiten bleiben
sichtbar, vor allem in:

- `string-prefix-p` / `string-suffix-p`
- `%trim-left-list` / `%trim-right-list`
- `%format-display-code-p` / `%format-readable-code-p`

Diese sind nicht ohne weiteres durch einen Helper kleiner zu machen, weil ein
zusaetzlicher Funktionsaufruf im P0-Bytecode ebenfalls Directory- und
Call-Overhead erzeugt. Erst ab klarer Wiederverwendung in mehreren groesseren
Funktionen lohnt sich eine weitere Faktorisierung.

## Embed-Grenze

Heavy Post-MVP-Slices bleiben ausserhalb des MVP-Embeds, bis Hardware-Footprint
und Nutzen gegeneinander entschieden sind:

- `lib/stdlib-fixed.lisp` wird ueber `make fixed-point-check` separat geprueft.
- `lib/stdlib-strings-polish.lisp` wird ueber
  `make post-mvp-stdlib-polish-check` separat geprueft. Der erste Slice enthaelt
  `string-left-trim` und `string-right-trim` als Wrapper um die bestehenden
  Trim-Helfer; er ist host-/bytecode-geprueft, aber nicht Teil von
  `p0-stdlib-subset.json` und damit nicht im Produkt-Embed.
- IDE-Buffer-Operationen bleiben Host-Slice und werden nicht in
  `p0-stdlib-subset.json` aufgenommen.
- Weitere String-P2-Funktionen sollen zuerst eine eigene Suite bekommen.

Vor einer Aufnahme in das Produkt-Embed kann der Bytecode-Anteil kalkuliert
werden:

```sh
make stdlib-embed-whatif
```

Der Report kompiliert das aktuelle Produkt-Bundle plus optionale Suites und
meldet Delta fuer Funktionen, Code-Bytes, Directory-Bytes, Literal-Slots und eine
konservative PRG-Delta-Schaetzung. Der echte harte Gate bleibt danach weiterhin
`make mvp-vm-stdlib-footprint-report`.

Aktueller What-if-Stand:

```text
p0-string-polish-subset: +2 Funktionen, +48 Code-Bytes, +14 Directory-Bytes, est. PRG +70 B
p0-fixed-point-subset:   +16 Funktionen, +489 Code-Bytes, +112 Directory-Bytes, est. PRG +701 B
beide zusammen:          +18 Funktionen, +537 Code-Bytes, +126 Directory-Bytes, est. PRG +771 B
```

Das aktuelle MVP-Embed bleibt damit auf die vorhandene REPL-Stdlib fokussiert.
