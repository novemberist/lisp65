# Fixed-Point Surface

Stand: 2026-07-02. Dieses Dokument pinnt den ersten Post-MVP-Fixed-Point-Slice
fuer lisp65. Der Slice ist Library/Spec-Arbeit in Lane L/T; er fuehrt keinen
neuen nativen Zahlentyp und keine neuen VM-/Kernel-Primitive ein.

## Representation

Fixed-Point-Werte sind normale Fixnums mit festem Skalierungsfaktor:

- Format: Q8.7 signed.
- Scale: `128`.
- Raw value: `real * 128`.
- Nominal representable real range: `-128.0` bis `127 + 127/128`.
- Smallest step: `1/128`.

Beispiele:

```lisp
(integer->fx 3)       ; => 384
(fx 1 64)             ; => 192, also 1.5
(fx -1 -64)           ; => -192, also -1.5
(fx->integer 192)     ; => 1
```

`fx` nimmt als zweiten, optionalen Parameter bereits rohe 1/128-Einheiten. Es
gibt absichtlich keine Dezimal-Literal-Syntax.

## Library Surface

Der erste Slice liegt in `lib/stdlib-fixed.lisp`:

- `fx-scale`
- `fx`
- `integer->fx`
- `fx->integer`
- `fx+`
- `fx-`
- `fx*`
- `fx/`
- `fx<`

`fx+`, `fx-` und `fx<` arbeiten direkt auf den skalierten Fixnums. `fx*` und
`fx/` kompensieren den Skalierungsfaktor in Lisp-Code und vermeiden dabei breite
native Zwischenwerte. Das ist portabel zum aktuellen P0-Bytecode-Modell, aber
bewusst nicht schnell.

## Overflow and Errors

Dieser Slice macht keine neuen Runtime-Promises ueber Integer-Overflow. Alle
Operationen laufen auf den bestehenden Fixnums, und ein Ueberlauf folgt dem
jeweiligen Eval-/VM-Fixnum-Vertrag.

`fx*` und `fx/` sind nur fuer Werte gedacht, deren interne, wiederholte
Addition im aktuellen Fixnum-Bereich bleibt. Division durch Null ist ausserhalb
des Vertrags. Spaetere Slices koennen native breite Zwischenwerte, Sättigung
oder explizite Fehler einfuehren; der MVP-Slice bleibt auf Host- und Bytecode-
Oracle-Gleichheit beschraenkt.

## Test Contract

`make fixed-point-check` prueft:

- Host-Eval gegen `lib/tests/stdlib-fixed-eval-cases.json`.
- P0-Bytecode-Compile/Run gegen `tests/bytecode/stdlib/p0-fixed-point-subset.json`.

Die Bytecode-Suite ist absichtlich getrennt von `p0-stdlib-subset.json`, damit
Fixed-Point nicht in das eingebettete MVP-Stdlib-Image hineinwaechst.
