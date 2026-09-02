# GC-Audit & Härtenachweis (Lane K)

Stand: 2026-06-30. Auftrag (von Codex vorgeschlagen): „GC fertigziehen bzw. stressfest
machen — Mark-Sweep korrekt über Env, Closures, Macros, Symbolwerte/Funktionszellen,
Reader-Zwischenobjekte."

## Verdikt

**Der GC ist korrekt und stressfest. Keine Bugs gefunden, keine Code-Änderung am GC
nötig.** Dieses Dokument hält den Audit + die Testfälle fest, damit das Ergebnis
nachvollziehbar und reproduzierbar bleibt.

## Struktur (src/mem.c)

- **Mark-Sweep** über festen Zellenpool + Freelist. Zelle 0 = NIL reserviert.
- **`gc_mark` ist voll iterativ** (expliziter `markstack[256]`, keine C-Rekursion):
  cdr-Kette per Schleife, car per Push. Wichtig auf dem 6502 — rekursives Marken
  würde bei GC mitten in tiefer eval-Rekursion den HW-Stack (Page 1, ~256 B) sprengen.
- **Traversiert** `a`+`b` für `T_CONS`/`T_CLOSURE`/`T_MACRO`; `T_SYM`/`T_PRIM` werden
  nicht traversiert (deren `a` ist Symtab-Index bzw. Primitiv-ID, kein Zeiger).
- **Roots:** (1) `gc_rootstack` (von eval/reader gepushte lebende obj),
  (2) alle internierten Symbole + ihre Wert- **und** Funktions-Zellen (`symval`/`symfn`).
- **`cons` ist self-protected** (GC_PUSH von car/cdr über die Allokation).
- **`-DGC_STRESS`** erzwingt vor *jeder* Allokation ein `gc_collect` → jeder nicht
  gerootete lebende Wert wird sofort eingesammelt und seine Zelle wiederverwendet.
  Das ist der definitive Root-Lücken-Test.

## Härtenachweis

### 1. Root-Lücken — GC bei jeder Allokation (`-DGC_STRESS`)

Alle Ergebnisse korrekt (Prelude geladen):

| Ausdruck | erwartet | Pfad |
|---|---|---|
| `(fact 7)` (rekursiv über Funktionszelle) | 5040 | Env-Ketten, Symbol-Funktionszelle |
| `(append (list 1 2 3) (list 4 5 6))` | `(1 2 3 4 5 6)` | Reader-Zwischenobjekte, %append2 |
| `(reverse (list 1 .. 8))` | `(8 .. 1)` | Akkumulator-Rooting |
| `(mapcar (lambda (x)(+ x 1)) (list 1..5))` | `(2 3 4 5 6)` | Closure + Listenaufbau |
| `(let* ((a 1)(b (+ a 1))(c (+ b 1))) (list a b c))` | `(1 2 3)` | verschachteltes Env |
| `` `(1 ,(+ 1 1) ,@(list 3 4) 5) `` | `(1 2 3 4 5)` | Quasiquote-Splice |
| `(cond ((eq 1 2) 'a)((eq 2 2) 'b)(t 'c))` | `b` | Makro-Expansion |
| `(assoc 2 (list (list 1 'a)(list 2 'b)))` | `(2 b)` | Alist |
| `(funcall (adder 10) 5)` | 15 | Closure-Capture (entkommt) |
| `(mapcar (lambda (f)(funcall f 3)) (list <2 lambdas>))` | `(6 103)` | Closures in Liste |
| `(car (build 80))` / `(nth 79 (build 80))` | 80 / 1 | tiefe Nicht-Tail-Rekursion (Tiefe 80) |
| `(length (append (build 40)(build 40)))` | 80 | tiefe Rekursion + append |

### 2. Reclaiming (normaler GC, Default-Heap)

`(churn 3000)` — tail-rekursive Schleife, die je Iteration Müll erzeugt
(`(list 1..8)` + `(mapcar ... (list 1 2 3))`), insgesamt ~45000 Allokationen ≫ Heap
(1536 Zellen) → **`done`**. Beweist, dass der GC den Müll tatsächlich zurückgewinnt
(kein Leck, kein OOM).

## Bekannte, NICHT-GC-Grenzen (zur Klarheit)

- **Symbole werden nie ge-GC't** (fixe Tabelle, `uint8_t`-Index, MAX_SYM=255). Das ist
  Designentscheidung, kein GC-Bug. Transiente Makro-Gensyms werden separat über
  `sym_mark`/`sym_reset` zurückgewonnen (siehe Commit-Historie). Siehe Memory
  `lisp65-symbol-constraints`.
- **Heap kleiner als die Prelude-Grundlast** (alle Prelude-Closures liegen permanent in
  Funktionszellen, also gerootet) → OOM beim Laden. Das ist erwartetes Verhalten, kein
  GC-Fehler (z. B. HEAP=600 + Prelude → alloc liefert NIL).

## Empfehlung an Lane T (Codex)

Das aktuelle `scripts/prelude-gc-stress-main.c` testet einen Fall
(`(length (reverse *xs*))` → 8). Vorschlag: um die obigen Fälle (Rekursion über
Funktionszelle, Closure-Capture, Quasiquote-Splice, tiefe Nicht-Tail-Rekursion)
erweitern — sie decken die Root-Pfade breiter ab. Fälle stehen oben bereit.
