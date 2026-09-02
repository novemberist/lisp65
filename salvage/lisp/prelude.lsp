; LISP 64 -- CL-Kompatibilitaets-Prelude (Phase 6, Stufe 1)
;
; Reine Lisp-Bibliothek: definiert Common-Lisp-vertraute Namen als Aliase auf
; die vorhandenen LISP-64-Primitive. Beruehrt KEINE .acme-Quelle und nicht das
; Makefile -- kollisionsfrei zur Phase-3-Arbeit.
;
; Laeuft auf dem Host-Referenzinterpreter (tools/host-lisp/lisp64.py) und soll
; spaeter unveraendert auf dem echten C64 ueber LOAD ladbar sein.
;
; Annahme: Argumente von DE-Funktionen werden ausgewertet (EXPR). Wo eine Form
; unausgewertete Argumente braucht (defun, incf-artig), wird DF/Makro genutzt.

; ---- arithmetische Operatoren ----
; ACHTUNG: '*' ist im Dialekt die KOMMENTARKENNZEICHNUNG (siehe Handbuch),
; NICHT Multiplikation. Daher KEIN (DE * ...)-Alias -- fuer Multiplikation
; weiter TIMES verwenden. Konflikt CL '*' <-> Kommentar siehe docs/dialect-vs-cl.md.
(DE + L (COND ((NULL L) 0) (T (APPLY 'PLUS L))))
(DE - L (APPLY 'DIFFERENCE L))
(DE / L (APPLY 'QUOTIENT L))
(DE 1+ (X) (ADD1 X))
(DE 1- (X) (SUB1 X))
(DE MOD (X Y) (REMAINDER X Y))

; ---- Vergleiche ----
(DE < (X Y) (LESSP X Y))
(DE > (X Y) (GREATERP X Y))
(DE = (X Y) (EQUAL X Y))
(DE /= (X Y) (NOT (EQUAL X Y)))
(DE <= (X Y) (NOT (GREATERP X Y)))
(DE >= (X Y) (NOT (LESSP X Y)))
(DE EVENP (X) (ZEROP (REMAINDER X 2)))
(DE ODDP (X) (NOT (ZEROP (REMAINDER X 2))))

; ---- Listenzugriff mit CL-Namen ----
(DE FIRST (L) (CAR L))
(DE REST (L) (CDR L))
(DE SECOND (L) (CADR L))
(DE THIRD (L) (CAR (CDDR L)))
(DE ENDP (L) (NULL L))
(DE LISTP (L) (OR (NULL L) (CONSP L)))
(DE CONSP-CL (L) (CONSP L))

; ---- defun als Makro auf DE ----
; (DEFUN name (args) body...) -> (DE name (args) body...)
(DM DEFUN (FORM)
  (CONS 'DE (CDR FORM)))

; ---- when / unless ----
(DM WHEN (FORM)
  (LIST 'COND (CONS (CAR (CDR FORM)) (CDR (CDR FORM)))))
(DM UNLESS (FORM)
  (LIST 'COND (LIST (LIST 'NOT (CAR (CDR FORM)))
                    (CONS 'PROGN (CDR (CDR FORM))))))

; ---- Test-Helfer (auch auf echtem C64 nutzbar) ----
(SETQ PASSCOUNT 0)
(SETQ FAILCOUNT 0)

(DE CHECK (GOT EXPECTED)
  (COND ((EQUAL GOT EXPECTED)
         (SETQ PASSCOUNT (ADD1 PASSCOUNT)))
        (T
         (SETQ FAILCOUNT (ADD1 FAILCOUNT))
         (PRINC "FAIL: ")
         (PRIN1 GOT)
         (PRINC " != ")
         (PRINT EXPECTED))))

(DE CHECK-REPORT ()
  (PRINC "PASS=")
  (PRIN1 PASSCOUNT)
  (PRINC " FAIL=")
  (PRINT FAILCOUNT))
