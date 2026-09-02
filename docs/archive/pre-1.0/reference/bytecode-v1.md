# LISP 64 — Bytecode v1 (stabile Schnittstelle)

Stand: 2026-06-28. Dies ist der **Vertrag** zwischen Compiler und VM und damit die
zentrale, backend-übergreifende Schnittstelle (Host → IR → Bytecode → {C64-VM,
später MEGA65-VM}, siehe `Projektnotizen_Architektur_2026-06-24.md`). Quelle der
Wahrheit für Opcode-Nummern: die `Phase4VMOpXxx = N`-Equates in
`src/v2/modules/20-bytecode-vm.acme`; der Drift-Check
`python3 tools/host-lisp/phase4_disasm.py --check-acme` muss `Drift: 0` melden.

## Freeze-Status

- **v1-Kern (eingefroren):** Opcodes 0–44 (Halt, Stack/Arithmetik/Vergleich,
  Branch, Call/Arg/Literal, Nil/T/Not). Smoke-abgedeckt und live im REPL erprobt.
  Nummern und Operandenformat sind ab hier stabil; neue Ops kommen **hinten** dazu.
- **Provisorisch (NICHT eingefroren):** 45 `PUSHOBJ` (nur im OBJECT_VALUES-Build),
  46 `LOADL` / 47 `STOREL` (Phase-6 Frame-Slots), 48 `DROP`, 49 `CLOSURE`,
  50 `CALLCLOSURE1` (Phase-6 Closure-Prototyp). Diese können sich mit Phase 6
  Stufe 2 (lexikalisch/Closures) noch ändern.

## Code-Objekt-Format

Ein kompiliertes Code-Objekt liegt im Code-Heap und beginnt mit einem Header
(Offsets aus `20-bytecode-vm.acme`):

| Offset | Größe | Feld | Wert/Bedeutung |
| ---: | ---: | --- | --- |
| 0 | 1 | Typ-Tag | `$B4` (`Phase4VMCodeObjTypeBytecode`) |
| 1 | 1 | Flags | reserviert |
| 2–3 | 2 | Payload-Länge | Bytecode-Länge (LE) |
| 4–5 | 2 | Literal-Pointer | Zeiger auf die Literaltabelle (LE) |
| 6+ | n | Payload | die Bytecode-Sequenz |

Hinter der Payload steht die **Literaltabelle**: 1 Byte Anzahl, dann die Einträge
(vom Compiler über `Phase4CompilerEmitLiteral8/S8/16/S16` befüllt). `PUSHLIT*`
indiziert in diese Tabelle.

## Operandenformate

| Kürzel | Bytes | Bedeutung |
| --- | ---: | --- |
| `none` | 0 | kein Operand |
| `u8` | 1 | vorzeichenlos (Immediate) |
| `idx` | 1 | Literaltabellen-Index |
| `rel8` | 1 | vorzeichenbehaftet, relativ zum **folgenden** Opcode-Byte |
| `u16` | 2 | little-endian (Adresse/Root-Index) |
| `u8u8` | 2 | Frame-Tiefe + Slot (LOADL/STOREL, provisorisch) |

## Opcode-Tabelle (v1)

| # | Mnemonic | Operand | Wirkung (Stack-Effekt) |
| ---: | --- | --- | --- |
| 0 | HALT | none | hält die VM |
| 1 | PUSHI8 | u8 | push Immediate |
| 2 | ADD | none | a b → a+b |
| 3 | PRINTACC | none | druckt ACC |
| 4 | CALL16 | u16 | Aufruf an Adresse |
| 5 | RET | none | Rücksprung |
| 6 | PUSHLIT8 | idx | push Literal (u8) |
| 7 | PUSHLITS8 | idx | push Literal (s8) |
| 8 | PUSHLIT16 | idx | push Literal (u16) |
| 9 | PUSHLITS16 | idx | push Literal (s16) |
| 10 | PUSHLITTYPED | idx | push typisiertes Literal |
| 11–13 | PUSHARG0/1/2 | none | push Argument 0/1/2 |
| 14 | SUB | none | a b → a−b |
| 15 | MUL | none | a b → a*b |
| 16 | DIV | none | a b → a/b |
| 17 | PRINTBOOL | none | druckt Bool |
| 18 | LESS | none | a b → a<b |
| 19 | GREATER | none | a b → a>b |
| 20 | ZEROP | none | a → a=0 |
| 21 | MINUSP | none | a → a<0 |
| 22 | ADD1 | none | a → a+1 |
| 23 | SUB1 | none | a → a−1 |
| 24 | REMAINDER | none | a b → a mod b |
| 25 | MINUS | none | a → −a |
| 26 | LOGAND | none | a b → a&b |
| 27 | LOGOR | none | a b → a\|b |
| 28 | JMPREL | rel8 | unbedingter Relativsprung |
| 29 | JFALSEREL | rel8 | Sprung, wenn TOS falsch |
| 30 | EQ | none | a b → a≡b |
| 31 | ABS | none | a → \|a\| |
| 32 | LOGXOR | none | a b → a^b |
| 33 | COMPL | none | a → ~a |
| 34 | LBYTE | none | Low-Byte |
| 35 | HBYTE | none | High-Byte |
| 36 | CALLROOT1 | u16 | Aufruf benannter Code-Root, 1 Arg |
| 37 | TAILSELF1 | none | Tail-Selbstaufruf, 1 Arg |
| 38 | CALLROOT2 | u16 | Code-Root, 2 Args |
| 39 | CALLROOT3 | u16 | Code-Root, 3 Args |
| 40 | TAILSELF2 | none | Tail-Selbstaufruf, 2 Args |
| 41 | TAILSELF3 | none | Tail-Selbstaufruf, 3 Args |
| 42 | NOT | none | a → ¬a |
| 43 | PUSHNIL | none | push NIL |
| 44 | PUSHT | none | push T |
| 45 | PUSHOBJ | u16 | push Objekt-Literal — *provisorisch (OBJECT_VALUES)* |
| 46 | LOADL | u8u8 | Frame-Slot lesen — *provisorisch (P6)* |
| 47 | STOREL | u8u8 | Frame-Slot schreiben — *provisorisch (P6)* |
| 48 | DROP | none | TOS verwerfen — *provisorisch (P6)* |
| 49 | CLOSURE | u16 | Closure bauen — *provisorisch (P6)* |
| 50 | CALLCLOSURE1 | none | Closure aufrufen, 1 Arg — *provisorisch (P6)* |

## Ausführungsmodell

Stack-VM (`Phase4VMRun` → `Phase4VMDispatch`): Opcode holen, gegen
`Phase4VMOpLast` bounds-checken, über `Phase4VMDispatchTable` (wortindiziert)
springen. Eigener Wert-Stack (`Phase4VMStackDepth`) + Return-Stack
(`Phase4VMReturnStackDepth`) + Root-Kontext-Tiefe; Statuscodes in
`Phase4VMStatus` (z. B. `BadOpcode`). 32-Bit-Integer-Semantik (Wraparound),
Boolesche als 1/0.

## REPL-Integration (Live-Pfad, flag-gegated)

Hinter `TERM_TEST_PHASE4_VM_REPL_DISPATCH` (`06-init-repl.acme:923`) entscheidet
`Phase4ReplReadFormIsOwned` pro gelesener Form:
- `(DE …)` → vom VM-Pfad **kompiliert** (Code-Objekt + Code-Root angelegt).
- `GETDEF`/`PDEF`/`PP` → vom VM-Pfad behandelt (Dekompiler/Pretty-Print).
- Aufruf, dessen Kopf eine bereits kompilierte **Code-Root** hat → über die VM
  **ausgeführt**.
- alles andere → Carry gesetzt → Fallback auf den Tree-Walker (`CallEval`).

**Live verifiziert (2026-06-28):** `(DE DF (A B C) (PLUS B C))` dann
`(DF 1 19 23)` → `42`, `(QUOTE P4FALL)` → `P4FALL` (Fallback), Smoke
`make phase4-vm-repl-dispatch-script-test-screenshot`.

## Compiler-Coverage: was aus `(DE …)` heute kompiliert wird

Vermessen (statisch) am Lowering `Phase4LowerLispListBodyToSourceExpr` +
`Phase4CompileLispDefinitionListBridge` (2026-06-28).

**Form-Shape:** nur `(DE name params body)` oder `(DE name body)` mit **genau einer
Body-Form**. Mehrere Body-Formen → `BadSourceNode` (kein impliziter PROGN ohne Flag).

**Parameter:** bis **3** (`Arg0/Arg1/Arg2`). Ein Bezug auf den 4. Parameter ist in der
IR nicht darstellbar → fällt.

**Body-Konstrukte (immer aktiv, Operator-Tabelle):**
- Binär: `PLUS DIFFERENCE TIMES QUOTIENT REMAINDER LOGAND LOGOR LOGXOR`
- Vergleich: `LESSP GREATERP EQ`
- Unär: `ZEROP MINUSP ADD1 SUB1 MINUS ABS COMPL LBYTE HBYTE NOT`
- Kontrolle: `COND` (→ `If3`)
- Aufrufe: benannte Calls bis **3 Args** (`Call1/2/3`) + Tail-Selbstaufruf
  (`TailSelf1/2/3`)
- Literale: Fixnums, `NIL`, `T`

**Nur mit Build-Flags:** Operator-Aliase `+ - * / 1+ 1- < > EQL` …
(`…OPERATOR_ALIAS_LOWERING`), `SETQ` (`…SOURCE_SETQ_LOWER`), `PROGN`
(`…SOURCE_PROGN_LOWER`), `LET` (`…SOURCE_LET_LOWER`), `LAMBDA`/Closures
(`…SOURCE_LAMBDA_*`), quoted Objekte (`…OBJECT_VALUES`).

**Heute NICHT abgedeckt (Default-Build):** `PROG`/`GO`/`RETURN`, mehrere Body-Formen,
>3 Parameter, Aufrufe mit >3 Args, Strings, allgemeine quoted Listen, `LET`/`SETQ`/
`PROGN` (ohne die jeweiligen Flags).

**Geschlossene VM-Welt:** ein generischer Call wird zur Laufzeit nur aufgelöst, wenn
die Zielfunktion eine kompilierte **Code-Root** hat — kompilierter Code ruft
kompilierten Code. Ein Aufruf an eine nur tree-walker-definierte Funktion läuft im
VM-Pfad ins Leere.

**Fallback-Sicherheit — BEHOBEN (C3, 2026-06-28):** Ein `(DE …)` ist *immer* „owned"
und wird zur VM geroutet. Schlägt das Lowering fehl (nicht unterstützter Body), legt
`Phase4TryDispatchReplReadFormOwned` jetzt die Originalform auf den DStack zurück und
gibt Carry-set zurück → der REPL fällt auf `CallEval` (Tree-Walker) durch und
definiert die Funktion normal. Verifiziert
(`make phase4-vm-repl-dispatch-fallback-script-test-screenshot`):

```
(DE FB (X) (ADD1 X) (ADD1 X))  -> FB ; Mehr-Form-Body → Tree-Walker
(FB 41)                         -> 42
(DE FC (A B C D) (PLUS A D))    -> FC ; 4 Params → Tree-Walker
(FC 1 2 3 9)                    -> 10
```

Damit ist der Hybrid **default-tauglich**: kompilierbare `(DE …)` gehen zur VM,
nicht unterstützte werden transparent vom Tree-Walker definiert (kein Verlust, kein
Crash). Der kompilierbare Pfad ist unverändert
(`(DE DF (A B C) (PLUS B C))`/`(DF 1 19 23)` = `42` weiter über die VM).

## Weg zum Default

Der Hybrid (VM für „owned" Formen, sonst Tree-Walker) ist gebaut und flag-gegated.
Erledigt auf dem Weg zum Default:
- **Fallback-Sicherheit** (C3) — nicht kompilierbare `(DE …)` fallen sauber zurück.
- **Namens-Druck** (2026-06-28) — ein VM-kompiliertes `(DE …)` druckt jetzt den
  Funktionsnamen wie der Tree-Walker (`(DE DF …)` → `DF`), Ausgabe ist konsistent.

**Blocker T1 — Tree-Walker → VM-Aufruf — BEHOBEN (C4, 2026-06-28).** Eine
VM-kompilierte Funktion hat eine Code-Root, aber keine `EXPR`. Früher scheiterte ein
tree-walker-evaluierter Aufruf an sie (`UNDEFINED FUNCTION`). Jetzt fängt
`Phase4TreeWalkerVMCallBridge` den `loc_11D7`-„keine Definition"-Fall ab (flag-gegated):
hat das Symbol eine Code-Root, werden die Argumente per `CallEval` ausgewertet, das
Code-Objekt über die VM ausgeführt und das Ergebnis wie bei einem Arithmetik-Primitiv
(`hDONE`: ACC32→Zahlknoten) zurückgegeben. Verifiziert
(`make phase4-vm-repl-dispatch-mixed-script-test-screenshot`):

```
(DE ADDER (A B) (PLUS A B))                       -> ADDER ; VM-kompiliert
(ADDER 3 4)                                        -> 7
(DE TWVAR (N) (PROG NIL (RETURN (ADDER N 100))))   -> TWVAR ; Tree-Walker (PROG)
(TWVAR 5)                                          -> 105   ; TW→VM, Variablen-Arg ok
```

Beide Richtungen funktionieren jetzt (VM→TW und TW→VM), inkl. nicht-literaler
Argumente (Variable `N` wird per `CallEval` ausgewertet). Default-Build bleibt
byte-identisch (Einsprung nur unter `TERM_TEST_PHASE4_VM_REPL_DISPATCH`).

Damit ist die **Transparenz hergestellt** — der letzte inhaltliche Blocker für
„Flag→Default" ist weg.

**C6 — Voll-Regression bestanden, Flip aber bewusst aufgeschoben (2026-06-28).**
Regression: nicht-owned Formen sind mit gesetztem Flag **byte-gleich** im Verhalten
(Control-Smoke identisch), owned-kompilierbar/Fallback/Cross-Call alle korrekt,
`closure-fast-check` exit 0. **Der Flip auf Default unterbleibt vorerst aus zwei
datengestützten Gründen:**
1. **Heap-Kosten** — der Dispatch-Build hat drastisch weniger freie Nodes
   (~1000 vs ~8200; Control 981 vs 8211). Das enthält VM-Test-Gerüst; die echte
   Produktions-Footprint des Code-Heaps muss erst isoliert gemessen/getunt werden.
2. **Schmale Coverage** — die meisten realen Funktionen fallen zurück (PROG/Mehrform/
   >3 Params/Rekursion); Kompilieren lohnt heute kaum, der Default-Flip wäre fast
   reiner Overhead.

Vorbedingung für den Flip: (a) Produktions-Code-Heap-Footprint messen/tunen,
(b) Coverage (C5) ausweiten. Bis dahin: Default = Tree-Walker, Hybrid bleibt
flag-verfügbar und transparenz-bewiesen; `reference-src-compare` unberührt.
