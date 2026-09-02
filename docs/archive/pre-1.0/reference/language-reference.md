# LISP 64 v2 — Sprachreferenz (konsolidiert)

Stand: 2026-06-29 · **Source of Truth** für den angestrebten Sprachumfang.
Vertiefende Einzel-Specs früherer Sessions wurden in `architecture.md` zusammengeführt
bzw. bleiben über die Git-History abrufbar.

Diese Datei beschreibt den **angestrebten** Umfang (Status-Legende unten). Was die
Kompatibilitätsschicht **heute konkret** bereitstellt, listet der Abschnitt
„CL-Subset: heute verfügbar"; die **Abweichungen vom Common Lisp** (z. B. `*`, `LAST`,
`NTH`, `MOD`) sind in `dialect-vs-cl.md` dokumentiert und mit Pinning-Tests fixiert.

**Status-Legende:** ✅ Host-Prototyp grün · 🔧 nativ (`.acme`) in Arbeit ·
📋 entschieden (Papier) · ◑ teilweise · ❌ bewusst raus.

## Identität

Ein **CL-nahes Lisp** auf dem C64, evolutionär aus LISP 64 (MacLisp-/Interlisp-
Familie) Richtung Common-Lisp-Subset. **Lisp-2** (getrennte Funktions-/Wert-
Namensräume). **Nicht** ANSI-konform (auf 64 KB kategorisch ausgeschlossen),
sondern ein klar definiertes, vertrautes Subset. Gesamtbild/Grenzen: `roadmap.md`.

## Auswertung & Scoping

| Aspekt | Stand | Detail |
| --- | --- | --- |
| Scoping | 📋 lexikalisch als Default + `special` (heute dynamisch) | an die VM gekoppelt, `development-plan.md` P2 |
| special markieren | 📋 `defvar`/`proclaim` + `(declare (special …))` | Compile-Zeit-Klassifikation |
| `#'`/`FUNCTION` | 📋 heute `QUOTE`; mit Closures bedeutungstragend, `#'(lambda …)` = Closure | |
| Closures | ✅ Host-Modell (`vm-model.py`) · 🔧 nativ via VM | `architecture.md` §7 |
| `t`/`nil` | selbstauswertend; `nil`=`()`=falsch | |
| Keyword-Literale `:foo` | ✅ selbstauswertend + interniert | |

## Funktionen & Makros

| Konstrukt | Stand | Detail |
| --- | --- | --- |
| `defun` | ✅ (über `DE`) | |
| `defmacro` + Backquote | ✅ Host | Quasiquote-Zeichen **`£`** (`$5C`), `,`/`,@` Standard (C64 hat keinen Backtick) |
| `gensym` (Hygiene) | ✅ Host + native resident | no-arg, Prefix, DM-Hygiene und Resident-Profil grün |
| FEXPRs (`DF`) | ◑ Altlast, durch Makros abgelöst | |
| Lambda-Listen | ◑ `&optional`/`&rest` geplant; `&key` Stufe 3 (emulierbar via `&rest`+`getf`) | |

## Zahlen

| Typ | Stand | Detail |
| --- | --- | --- |
| 32-Bit-Integer (Vorzeichen, Wraparound) | ✅/🔧 Kern | |
| Fixed-Point **16.16** | ✅ Host-Modell · 📋 nativ | `architecture.md` §9; Literal `1.5` via Token-Kontext |
| Voller Zahlenturm (Float/Ratio/Bignum/Complex) | ❌ | bewusst raus |
| Operatoren | `+ - * /` (CL-Schnitt: `*`=Multiplikation), `1+`/`1-`, `< > =` | |

## Reader-Syntax

| Syntax | Stand | Detail |
| --- | --- | --- |
| `'x` Quote, `£` Quasiquote, `,`/`,@` | 📋 (`£` entschieden) | C64: kein Backtick |
| `;` Zeilenkommentar | 📋 (CL-Schnitt; `(* …)` entfällt) | Blockkommentar `#\|…\|#` zurückgestellt |
| `:keyword` | ✅ | |
| `1.5` Fixed-Point-Literal | 📋 | Token-Kontext löst Dotted-Pair-`.` |
| Groß/Klein | 📋 Symbole upcase (case-insensitiv); **Strings case-sensitiv** | |
| Zeichensatz | 📋 Identifier **ASCII-only**; Umlaute nur via Custom-Charset | |

## Datenstrukturen

| Struktur | Stand | Detail |
| --- | --- | --- |
| Cons, Property-Listen | ✅/🔧 Kern | `architecture.md` §3 |
| Strings ≤128, Symbole/Literale ≤80 | 📋 Grenzen beibehalten | |
| `defstruct`-light | ✅ Host | Keyword-Konstruktor, setf-fähige Akzessoren |
| Mini-CLOS (Single-Dispatch) | ✅ Host · 🔧 nativ (CXPASS/CDPASS) | `architecture.md` §6; Multiple Dispatch ❌ |
| Arrays/Hash | ◑ 1-D-Array machbar; mehrdim./adjustable ❌ | |

## Kontrollfluss

| Konstrukt | Stand | Detail |
| --- | --- | --- |
| `cond`/`if` | ✅ Host · 🔧 nativ (Branch-Opcodes da) | |
| `case`/`ecase` | ✅ Host (`cl-compat`) | verschachtelbar (LAMBDA-gebunden); Schlüssel genau einmal ausgewertet |
| `prog`/`go`/`return` | ✅/🔧 Kern | |
| `loop`-Subset | ✅ Host | `FOR…IN`/`FROM…TO[…BY]`/`REPEAT`, `collect/sum/count/while/until/do/finally` |
| `dotimes`/`dolist` | ✅ Host · ✅ Treewalker · ✅ P0-Bytecode | `dotimes`: Result mit `var=count`; `dolist`: Result mit `var=nil`; Bytecode-v1-Body durch rel8-Spruenge begrenzt |
| Multiple Values | 📋 **hartes Limit 2** | |
| TCO | ✅ Host-Modell · 🔧 nativ (mehrstufig) | `architecture.md` §5 |

## Fehler-/Condition-Modell

✅ Host: `catch`/`throw`, `unwind-protect`, `handler-case` (typ-dispatch),
`ignore-errors`, `signal`, typisierte Conditions (`condition-type`/`-message`/
`-data`), Break-Loop; automatischer Unwind (mit VM). **Keine Restarts.**

## Sequenzen & Ausgabe

| Bereich | Stand | Detail |
| --- | --- | --- |
| `mapcar`/`mapcan`/`mapc` | ✅/🔧 | |
| `reduce`/`every`/`some`/`count` | ✅ Host (`cl-compat`) | |
| `sort`/`*-if`/`remove-duplicates`/`subseq`/`find`/`position` | ✅ Host (`lib-seq`) | |
| `setf`-light (+ `setf`-functions via `SETF-FN`) | ✅ Host | car/cdr/get/var/Struct-/CLOS-Slots |
| `format`-Subset | ✅ Host | `~A ~S ~D ~X ~C ~% ~~` + Padding; `~{…}` streichbar |

## CL-Subset: heute verfügbar (`cl-compat`, host-grün)

Konkret bereitgestellt (✅ host-getestet, `cl-compat-tests` PASS=97; Stand
2026-06-29). Abweichungen vom CL (`LAST`/`NTH`/`MOD`/`*`) sind in `dialect-vs-cl.md`
gepinnt; nicht-baubare CL-String-Funktionen siehe ebd. (kein `READ-FROM-STRING`/
`INTERN` im Kernel).

- **Control:** `CASE`/`ECASE` (verschachtelbar, Schlüssel einmal ausgewertet),
  `WHEN`/`UNLESS`, `DOLIST`/`DOTIMES`, `LET*`, `PROG1`, `IDENTITY`.
- **Listen-Konstruktoren/Kopierer:** `COPY-LIST`/`COPY-TREE`/`COPY-ALIST`,
  `REVAPPEND`, `LIST*`, `MAKE-LIST`, `ADJOIN`, `SUBST`, `BUTLAST`, `NTHCDR`.
- **alist/plist:** `ACONS`, `PAIRLIS`, `GETF`, `RASSOC` (+ native `ASSOC`).
- **Zahlen:** `PLUSP`, `REM`, `SIGNUM`, `EXPT` (e≥0), `MAX`/`MIN` (variadisch),
  `GCD`/`LCM` (+ prelude `MOD`/`EVENP`/`ODDP`, native `ABS`/`MINUSP`/`ZEROP`).
- **Higher-order:** `REDUCE`, `EVERY`/`SOME`, `NOTANY`/`NOTEVERY`,
  `FIND`/`POSITION`, `REMOVE-IF`/`DELETE-IF`, `COUNT`, `MAPCON`.
- **Typ-Prädikate:** `SYMBOLP`, `TYPEP` (Kern-Typsymbole) (+ native `ATOM`/`CONSP`/
  `LISTP`/`NUMBERP`/`STRINGP`/`NULL`).
- **Mengen** (`lib-sets`): `UNION`/`INTERSECTION`/`SET-DIFFERENCE`/`SUBSETP`/`MAKESET`.

**Belege/Beispiele:** kleine Programme auf dieser Schicht in
`docs/mvp-sample-programs.md` (`demo-simplify`/`demo-calc`/`demo-db` + `lib-diff`),
host-getestet und im Aggregat `tools/host-lisp/run-tests.sh`.

## Modularisierung

✅ Host: Multi-File via `LOAD`, `require`/`provide` (Laden-genau-einmal +
Abhängigkeiten). **Pakete:** Präfix-Konvention statt Namensräume; volles
`defpackage` ❌. Native Loader-Story: `development-plan.md` P3.

## Werkzeuge (Phase 8, Vorarbeit)

✅ Host: Editor-Logik (`editor-core`: Buffer/Cursor/Auto-Indent/Klammer-Match/
Keymap/`classify`), Paredit-Subset (`slurp`/`barf`/`wrap`/`splice` + buffer-
globaler S-Expr-Scanner), `eval-defun` + SLIME/Paredit-Keymap. Architektur:
`architecture.md` §10.

## Bewusst ausgeschlossen (❌)

Voller Zahlenturm · CLOS/MOP/Multimethoden · volles `defpackage` · volles
`format` (Conditionals/`~R`/Pretty) · Regex · Restart-System · beliebig lange
Strings · ANSI-Konformität insgesamt.

## Auslieferung

Drei Modelle: interaktiv (Quelle/REPL), Bytecode (VM), cross-kompiliertes
Standalone-`.prg`. Kein CL-Image-Bloat; nur selektives Linken fürs `.prg`.
