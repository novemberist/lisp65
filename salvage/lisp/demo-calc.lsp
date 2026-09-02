; demo-calc -- winziger Ausdrucks-Interpreter (MVP-Pfeiler "kleine, symbol-/
; listenlastige Programme"). Wertet eine Mini-Sprache aus:
;   Zahl            -> sich selbst
;   Symbol          -> Nachschlagen in der Umgebung (alist), unbekannt -> 0
;   (PLUS a b) / (DIFFERENCE a b) / (TIMES a b) / (QUOTIENT a b)
;   (IF c a b)      -> c=0 ? b : a
;   (LET (v expr) body) -> body mit v gebunden auswerten
; Zeigt CASE (Operator-Dispatch) + Alist-Umgebung (ACONS/ASSOC) aus cl-compat.
;
; Reines Dialekt-Lisp (prelude + cl-compat); host-getestet, spaeter C64-ladbar.
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/demo-calc.lsp lisp/demo-calc-tests.lsp

(DE calc-lookup (v env)           ; Variable in der Umgebung (alist) nachschlagen
  (PROG (p)
    (SETQ p (ASSOC v env))
    (RETURN (COND (p (CDR p)) (T 0)))))   ; unbekannt -> 0

(DE calc-eval (e env)
  (COND ((NUMBERP e) e)
        ((ATOM e) (calc-lookup e env))
        (T (calc-apply (CAR e) (CDR e) env))))

(DE calc-arg (n args env)         ; n-tes (0/1) Argument auswerten
  (COND ((ZEROP n) (calc-eval (CAR args) env))
        (T (calc-eval (CADR args) env))))

(DE calc-apply (op args env)
  (CASE op
    ((PLUS)       (PLUS       (calc-arg 0 args env) (calc-arg 1 args env)))
    ((DIFFERENCE) (DIFFERENCE (calc-arg 0 args env) (calc-arg 1 args env)))
    ((TIMES)      (TIMES      (calc-arg 0 args env) (calc-arg 1 args env)))
    ((QUOTIENT)   (QUOTIENT   (calc-arg 0 args env) (calc-arg 1 args env)))
    ((IF)   (calc-if  args env))
    ((LET)  (calc-let args env))
    (T 0)))

(DE calc-if (args env)            ; (IF c a b): c=0 -> b, sonst a
  (COND ((ZEROP (calc-eval (CAR args) env)) (calc-eval (CADDR args) env))
        (T (calc-eval (CADR args) env))))

(DE calc-let (args env)           ; (LET (v expr) body)
  (PROG (b v)
    (SETQ b (CAR args))           ; (v expr)
    (SETQ v (calc-eval (CADR b) env))
    (RETURN (calc-eval (CADR args) (ACONS (CAR b) v env)))))
