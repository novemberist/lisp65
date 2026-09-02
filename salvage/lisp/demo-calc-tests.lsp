; Tests fuer demo-calc (winziger Ausdrucks-Interpreter).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/demo-calc.lsp lisp/demo-calc-tests.lsp

; ---- Atome / Umgebung ----
(CHECK (calc-eval 5 NIL) 5)
(CHECK (calc-eval 'X '((X . 10))) 10)
(CHECK (calc-eval 'Y NIL) 0)              ; unbekannte Variable -> 0

; ---- Arithmetik ----
(CHECK (calc-eval '(PLUS 2 3) NIL) 5)
(CHECK (calc-eval '(PLUS X 1) '((X . 9))) 10)
(CHECK (calc-eval '(TIMES (PLUS 1 2) 4) NIL) 12)
(CHECK (calc-eval '(DIFFERENCE 10 (QUOTIENT 12 4)) NIL) 7)

; ---- IF ----
(CHECK (calc-eval '(IF 0 100 200) NIL) 200)
(CHECK (calc-eval '(IF 1 100 200) NIL) 100)
(CHECK (calc-eval '(IF (DIFFERENCE 5 5) 1 2) NIL) 2)

; ---- LET (Bindung + Schachtelung + Shadowing ueber das Alist) ----
(CHECK (calc-eval '(LET (X 5) (TIMES X X)) NIL) 25)
(CHECK (calc-eval '(LET (X 3) (LET (Y 4) (PLUS X Y))) NIL) 7)
(CHECK (calc-eval '(LET (X 2) (PLUS X (LET (X 10) X))) NIL) 12)  ; inneres X schattet

(CHECK-REPORT)
