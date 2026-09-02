; demo-simplify -- kleines symbolisches Algebra-Beispiel (MVP-Pfeiler "kleine,
; symbol-/listenlastige Programme"). Vereinfacht arithmetische Ausdruecke ueber
; PLUS/DIFFERENCE/TIMES/QUOTIENT: Konstanten falten + algebraische Identitaeten
; (x+0=x, x*1=x, x*0=0, x-x=0, ...). Zeigt, dass die Sprache + die CL-Subset-
; Schicht (CASE) reale kleine Programme tragen.
;
; Reines Dialekt-Lisp (prelude + cl-compat); host-getestet, spaeter C64-ladbar.
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/demo-simplify.lsp lisp/demo-simplify-tests.lsp

(DE simp-both-num (a b)           ; T, wenn beide Operanden Zahlen sind
  (COND ((NUMBERP a) (NUMBERP b)) (T NIL)))

(DE simp-const (op a b)           ; beide Operanden Zahlen -> falten
  (CASE op
    ((PLUS) (PLUS a b))
    ((DIFFERENCE) (DIFFERENCE a b))
    ((TIMES) (TIMES a b))
    ((QUOTIENT) (QUOTIENT a b))
    (T (LIST op a b))))

(DE simp-plus (a b)
  (COND ((EQUAL a 0) b)
        ((EQUAL b 0) a)
        (T (LIST 'PLUS a b))))

(DE simp-diff (a b)
  (COND ((EQUAL b 0) a)
        ((EQUAL a b) 0)
        (T (LIST 'DIFFERENCE a b))))

(DE simp-times (a b)
  (COND ((EQUAL a 0) 0)
        ((EQUAL b 0) 0)
        ((EQUAL a 1) b)
        ((EQUAL b 1) a)
        (T (LIST 'TIMES a b))))

(DE simp-quot (a b)
  (COND ((EQUAL a 0) 0)
        ((EQUAL b 1) a)
        ((EQUAL a b) 1)
        (T (LIST 'QUOTIENT a b))))

(DE simp-op (op a b)              ; Regeln nach dem Vereinfachen der Operanden
  (COND ((simp-both-num a b) (simp-const op a b))
        (T (CASE op
             ((PLUS) (simp-plus a b))
             ((DIFFERENCE) (simp-diff a b))
             ((TIMES) (simp-times a b))
             ((QUOTIENT) (simp-quot a b))
             (T (LIST op a b))))))

(DE simplify (e)                  ; Zahl/Variable = Atom; sonst binaerer Operator
  (COND ((ATOM e) e)
        (T (simp-op (CAR e)
                    (simplify (CADR e))
                    (simplify (CADDR e))))))
