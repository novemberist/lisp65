; demo-combined-smoke -- laedt alle MVP-Beispielprogramme GEMEINSAM und prueft,
; dass sie kollisionsfrei koexistieren UND ueber Feature-Grenzen hinweg
; zusammenspielen. Kapstein der Sample-Sammlung (docs/mvp-sample-programs.md).
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/lib-diff.lsp lisp/demo-simplify.lsp lisp/demo-calc.lsp \
;       lisp/demo-db.lsp lisp/demo-combined-smoke.lsp

; ---- Jedes Programm einzeln intakt (keine Ueberschreibung durch ein anderes) ----
(CHECK (DIFF '(PLUS X 5) 'X) '(PLUS 1 0))
(CHECK (simplify '(TIMES X 1)) 'X)
(CHECK (calc-eval '(LET (X 5) (TIMES X X)) NIL) 25)
(SETQ SMOKE-TBL (LIST (rec '(N R) '(A DEV)) (rec '(N R) '(B DEV))))
(CHECK (db-count SMOKE-TBL 'R 'DEV) 2)

; ---- Diff + Simplify komponieren ----
(CHECK (simplify (DIFF '(TIMES X X) 'X)) '(PLUS X X))   ; d/dx x^2 = 2x = x+x
(CHECK (simplify (DIFF '(PLUS X 5) 'X)) 1)

; ---- Cross-Feature: calc-Ergebnis in einen DB-Record ----
(CHECK (rec-get (rec '(VAL) (LIST (calc-eval '(PLUS 2 3) NIL))) 'VAL) 5)

; ---- Cross-Feature: simplify liefert eine Variable, calc wertet sie aus ----
(CHECK (calc-eval (simplify '(PLUS X 0)) '((X . 7))) 7)

(CHECK-REPORT)
