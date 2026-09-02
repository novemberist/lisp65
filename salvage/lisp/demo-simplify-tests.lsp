; Tests fuer demo-simplify (kleines symbolisches Algebra-Programm).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/demo-simplify.lsp lisp/demo-simplify-tests.lsp

; ---- Atome ----
(CHECK (simplify 5) 5)
(CHECK (simplify 'X) 'X)

; ---- Identitaeten ----
(CHECK (simplify '(PLUS X 0)) 'X)
(CHECK (simplify '(PLUS 0 X)) 'X)
(CHECK (simplify '(TIMES X 1)) 'X)
(CHECK (simplify '(TIMES 1 X)) 'X)
(CHECK (simplify '(TIMES X 0)) 0)
(CHECK (simplify '(TIMES 0 X)) 0)
(CHECK (simplify '(DIFFERENCE X 0)) 'X)
(CHECK (simplify '(DIFFERENCE X X)) 0)
(CHECK (simplify '(QUOTIENT X 1)) 'X)
(CHECK (simplify '(QUOTIENT X X)) 1)

; ---- Konstantenfaltung ----
(CHECK (simplify '(PLUS 2 3)) 5)
(CHECK (simplify '(TIMES 4 5)) 20)
(CHECK (simplify '(DIFFERENCE 10 4)) 6)

; ---- Rekursiv: Teilbaeume zuerst vereinfachen ----
(CHECK (simplify '(PLUS (TIMES X 0) (PLUS Y 0))) 'Y)
(CHECK (simplify '(TIMES (PLUS 1 2) X)) '(TIMES 3 X))
(CHECK (simplify '(PLUS (TIMES 2 3) (DIFFERENCE 10 4))) 12)
(CHECK (simplify '(DIFFERENCE (TIMES X 1) (TIMES X 1))) 0)

; ---- Nicht reduzierbar bleibt strukturell erhalten ----
(CHECK (simplify '(PLUS X Y)) '(PLUS X Y))

(CHECK-REPORT)
