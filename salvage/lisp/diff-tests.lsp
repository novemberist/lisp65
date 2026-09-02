; Tests fuer den symbolischen Differenzierer (lib-diff.lsp).
; Prueft v.a. dynamisches Scoping (freies X in DPLUS/DTIMES/...).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-diff.lsp lisp/diff-tests.lsp

; ---- rohe Ableitung ----
(CHECK (DIFF 'X 'X) 1)
(CHECK (DIFF '5 'X) 0)
(CHECK (DIFF '(PLUS X 5) 'X) '(PLUS 1 0))
(CHECK (DIFF '(MINUS X) 'X) '(MINUS 1))
(CHECK (DIFF '(TIMES X X) 'X) '(PLUS (TIMES 1 X) (TIMES 1 X)))

; ---- mit Vereinfachung ----
(CHECK (SIMPLE (DIFF '(PLUS X 5) 'X)) 1)          ; d/dx (x+5) = 1
(CHECK (SIMPLE (DIFF '(MINUS X) 'X)) -1)          ; d/dx (-x) = -1
(CHECK (SIMPLE (DIFF '(TIMES X X) 'X)) '(TIMES 2 X))   ; d/dx (x*x) = 2x
(CHECK (SIMPLE (DIFF '(PLUS (TIMES 3 X) 5) 'X)) 3)     ; d/dx (3x+5) = 3

; ---- Vereinfacher-Regeln direkt ----
(CHECK (SIMPLE '(TIMES X X)) '(EXPT X 2))         ; x*x -> x^2
(CHECK (SIMPLE '(QUOTIENT X X)) 1)                ; x/x -> 1

(CHECK-REPORT)
