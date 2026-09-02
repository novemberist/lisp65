# Eval vs. Bytecode Equivalence

Stand: 2026-07-02. Dieses Gate vergleicht den M1-Host-Evaluator mit der P0-
Host-Bytecode-VM auf denselben Ausdruecken. Ziel ist nicht volle CL-
Konformitaet, sondern fruehes Erkennen von Divergenzen zwischen Tree-Walker- und
Compilerpfad.

## Target

```sh
make eval-bytecode-equivalence-check
```

Das Target ist Teil von `make check`.

Die Suiten liegen unter `tests/bytecode/equivalence/*.json`. Eine Suite nennt:

- `sources`: Lisp-Dateien, die in den Host-Evaluator geladen und fuer Bytecode
  kompiliert werden;
- `functions`: die kompilierten Funktionsobjekte fuer das Bytecode-Directory;
- `cases`: Ausdruecke, die beide Pfade auswerten muessen.

Der Checker rendert Host-Eval-Werte in derselben kanonischen Textform wie die
Bytecode-VM: Symbole klein, `nil` klein, Strings ohne Escape-Neuschreibung.

## Scope

Der erste P0-Slice deckt ab:

- direkte Arithmetik und `let*`-Lowering;
- `case` ueber Makro/Eval und Compiler-Lowering;
- Listenfunktionen, Higher-Order-Aufrufe und bare Lambdas;
- Strings und kleines `format`.

Bewusst nicht Teil dieses Gates sind bytecode-only Bridge-Funktionen wie
`consp`/`atom`/`null`/`equal`. Diese sind als Produkt-Stdlib-Entries getestet,
aber nicht mehr Host-Eval-Primitive.

## Pflege

Neue Compiler-Surface sollte zuerst hier mit einem kleinen Eval-gegen-Bytecode-
Fall landen. Wenn ein Fall nur bytecode-only ist, gehoert er weiter in die
Bytecode-Stdlib-Suite statt in dieses Gate.
