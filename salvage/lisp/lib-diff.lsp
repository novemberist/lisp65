; LISP 64 -- Symbolische Differentiation (Kern)
; Salvage aus reference/.../samples/symb-diff.lsp. Semantik unveraendert,
; reformatiert. Ohne die READ-Schleife/INFIX-Ausgabe des Originals.
;
; Stresstest fuer DYNAMISCHES SCOPING: die Ableitungsregeln DPLUS/DTIMES/...
; referenzieren ein FREIES X, das DIFF als Parameter bindet und das nur ueber
; dynamische Bindung sichtbar ist. Ebenso EXPT/CONSTP.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/lib-diff.lsp lisp/diff-tests.lsp

(DE CADDR (X) (CAR (CDDR X)))

(DE CONSTP (L X)
  (COND ((ATOM L) (NOT (EQ L X)))
        ((CONSTP (CAR L) X) (CONSTP (CDR L) X))))

(DE DIFF (Y X)
  (COND ((CONSTP Y X) 0)
        ((EQ Y X) 1)
        (T (APPLY (DIFF-FUNCTION (CAR Y)) (CDR Y)))))

(DE DIFF-FUNCTION (FN)
  (OR (CDR (ASSOC FN SYSTEM-FUNCTIONS))
      (GETPROP FN 'DFUN)
      (ERROR '(NON-DIFFERENTIAL TERM))))

(SETQ SYSTEM-FUNCTIONS
  '((PLUS . DPLUS) (TIMES . DTIMES) (QUOTIENT . DQUOTIENT) (MINUS . DMINUS)))

; ---- Ableitungsregeln (X ist frei -> dynamisch von DIFF) ----
(DE DPLUS (A B)
  (LIST 'PLUS (DIFF A X) (DIFF B X)))

(DE DMINUS (A)
  (LIST 'MINUS (DIFF A X)))

(DE DTIMES (A B)
  (LIST 'PLUS
    (LIST 'TIMES (DIFF A X) B)
    (LIST 'TIMES (DIFF B X) A)))

(DE DQUOTIENT (A B)
  (LIST 'QUOTIENT
    (LIST 'PLUS
      (LIST 'TIMES (DIFF A X) B)
      (LIST 'MINUS (LIST 'TIMES (DIFF B X) A)))
    (LIST 'EXPT B 2)))

(DE EXPT (A B)
  (COND ((CONSTP B X)
         (LIST 'TIMES B
           (LIST 'TIMES (DIFF A X)
             (LIST 'EXPT A (LIST 'PLUS B -1)))))
        (T (LIST 'TIMES
             (LIST 'EXPT A B)
             (LIST 'PLUS
               (LIST 'TIMES (DIFF B X) (LIST 'LN A))
               (LIST 'TIMES B (LIST 'QUOTIENT (DIFF A X) A)))))))
(DEFPROP EXPT DFUN EXPT)

; ---- Vereinfacher ----
(DE SIMPLE (X)
  (COND ((ATOM X) X)
        ((ASSOC (CAR X) SIASSOC)
         (APPLY (CDR (ASSOC (CAR X) SIASSOC)) (MAPCAR 'SIMPLE (CDR X))))
        (T (CONS (CAR X) (MAPCAR 'SIMPLE (CDR X))))))

(SETQ SIASSOC
  '((PLUS . SPLUS) (TIMES . STIMES) (QUOTIENT . SQUOTIENT)
    (MINUS . SMINUS) (EXPT . SEXPT)))

(DE PLN (A B)
  (COND ((ZEROP A) B)
        ((NUMBERP B) (PLUS A B))
        ((AND (EQ (CAR B) 'MINUS) (NUMBERP (CADR B)))
         (DIFFERENCE A (CADR B)))
        ((EQ (CAR B) 'PLUS)
         (COND ((NUMBERP (CADR B))
                (LIST 'PLUS (PLUS A (CADR B)) (CADDR B)))
               ((NUMBERP (CADDR B))
                (LIST 'PLUS (PLUS A (CADDR B)) (CADR B)))
               (T (LIST 'PLUS A B))))
        (T (LIST 'PLUS A B))))

(DE TIN (A B)
  (COND ((NUMBERP B) (TIMES A B))
        ((EQ A 0) 0)
        ((EQ A 1) B)
        ((MINUSP A)
         (SIMPLE (LIST 'MINUS (LIST 'TIMES (MINUS A) B))))
        ((EQ (CAR B) 'TIMES)
         (COND ((NUMBERP (CADR B))
                (LIST 'TIMES (TIMES A (CADR B)) (CADDR B)))
               ((NUMBERP (CADDR B))
                (LIST 'TIMES (TIMES A (CADDR B)) (CADR B)))
               (T (LIST 'TIMES A B))))
        (T (LIST 'TIMES A B))))

(DE SPLUS (X Y)
  (COND ((NUMBERP X) (PLN X Y))
        ((NUMBERP Y) (PLN Y X))
        ((EQUAL X Y) (SIMPLE (LIST 'TIMES 2 X)))
        ((EQ (CAR Y) 'MINUS)
         (COND ((EQUAL X (CADR Y)) 0)
               (T (LIST 'PLUS X Y))))
        ((EQ (CAR Y) 'PLUS)
         (COND ((EQ X (CADR Y))
                (SIMPLE (LIST 'PLUS (LIST 'TIMES 2 X) (CADDR Y))))
               ((EQ X (CADDR Y))
                (SIMPLE (LIST 'PLUS (LIST 'TIMES 2 X) (CADR Y))))
               (T (LIST 'PLUS X Y))))
        (T (LIST 'PLUS X Y))))

(DE SMINUS (X)
  (COND ((NUMBERP X) (MINUS X))
        ((EQ (CAR X) 'MINUS) (CADR X))
        ((EQ (CAR X) 'PLUS)
         (SIMPLE (LIST 'PLUS (LIST 'MINUS (CADR X)) (LIST 'MINUS (CADDR X)))))
        (T (LIST 'MINUS X))))

(DE STIMES (X Y)
  (COND ((NUMBERP X) (TIN X Y))
        ((NUMBERP Y) (TIN Y X))
        ((EQUAL X Y) (LIST 'EXPT X 2))
        ((EQ (CAR Y) 'TIMES)
         (COND ((EQUAL X (CADR Y))
                (SIMPLE (LIST 'TIMES (CADDR Y) (LIST 'EXPT X 2))))
               ((EQUAL X (CADDR Y))
                (SIMPLE (LIST 'TIMES (CADR Y) (LIST 'EXPT X 2))))
               (T (LIST 'TIMES X Y))))
        ((EQ (CAR Y) 'MINUS)
         (SIMPLE (LIST 'MINUS (LIST 'TIMES X (CADR Y)))))
        ((EQ (CAR X) 'MINUS)
         (SIMPLE (LIST 'MINUS (LIST 'TIMES Y (CADR X)))))
        ((AND (EQ (CAR Y) 'EXPT) (EQUAL X (CADR Y)))
         (LIST 'EXPT X (ADD1 (CADDR Y))))
        (T (LIST 'TIMES X Y))))

(DE SQUOTIENT (A B)
  (COND ((EQUAL A B) 1)
        ((AND (NUMBERP A) (NUMBERP B))
         (COND ((ZEROP (REMAINDER A B)) (QUOTIENT A B))
               (T (LIST 'QUOTIENT A B))))
        ((EQ (CAR A) 'TIMES)
         (COND ((EQUAL (CADR A) B) (CADDR A))
               ((EQUAL (CADDR A) B) (CADR A))
               (T (LIST 'QUOTIENT A B))))
        ((EQ (CAR B) 'TIMES)
         (COND ((EQUAL (CADR B) A) (LIST 'QUOTIENT 1 (CADDR B)))
               ((EQUAL (CADDR B) A) (LIST 'QUOTIENT 1 (CADR B)))
               (T (LIST 'QUOTIENT A B))))
        (T (LIST 'QUOTIENT A B))))

(DE SEXPT (X Y)
  (COND ((NUMBERP X) (EXPT X Y))
        ((EQ Y 0) 1)
        ((EQ Y 1) X)
        ((EQ (CAR X) 'EXPT)
         (SIMPLE (LIST 'EXPT (CADR X) (LIST 'TIMES Y (CADDR X)))))
        (T (LIST 'EXPT X Y))))
