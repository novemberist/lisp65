; LISP 64 -- Mengen-Bibliothek
; Salvage aus reference/.../samples/sets.lsp. Semantik unveraendert.
; Mengen sind Listen ohne Duplikate (EQUAL-Vergleich via MEMBER).
;
; Hinweis: REMOVE ist im Dialekt bereits ein Builtin (nicht-destruktiv,
; EQUAL-Vergleich; Handbuch: (REMOVE 'A '(A B A C A A D)) = (B C D)) -- daher
; hier nicht neu definiert.

(DE MEM1 (L1 L2)
  (COND ((ATOM L1) NIL)
        ((MEMBER (CAR L1) L2))
        (T (MEM1 (CDR L1) L2))))

(DE SUBSET (FUN L)
  (COND ((ATOM L) NIL)
        ((APPLY* FUN (CAR L))
         (CONS (CAR L) (SUBSET FUN (CDR L))))
        (T (SUBSET FUN (CDR L)))))

(DE SYMM-DIFF (L1 L2)
  (COND ((ATOM L1) NIL)
        ((MEMBER (CAR L1) L2) (SYMM-DIFF (CDR L1) L2))
        (T (CONS (CAR L1) (SYMM-DIFF (CDR L1) L2)))))

(DE UNION (L1 L2)
  (COND ((ATOM L1) L2)
        ((MEMBER (CAR L1) L2) (UNION (CDR L1) L2))
        (T (CONS (CAR L1) (UNION (CDR L1) L2)))))

(DE INTERSECTION (L1 L2)
  (COND ((ATOM L1) NIL)
        ((MEMBER (CAR L1) L2)
         (CONS (CAR L1) (INTERSECTION (CDR L1) L2)))
        (T (INTERSECTION (CDR L1) L2))))

; CL-Name fuer die asymmetrische Differenz L1 \ L2 (Elemente von L1, nicht in L2).
(DE SET-DIFFERENCE (L1 L2)
  (COND ((ATOM L1) NIL)
        ((MEMBER (CAR L1) L2) (SET-DIFFERENCE (CDR L1) L2))
        (T (CONS (CAR L1) (SET-DIFFERENCE (CDR L1) L2)))))

(DE MAKESET (L1)
  (COND ((ATOM L1) NIL)
        ((NOT (MEMBER (CAR L1) (CDR L1)))
         (CONS (CAR L1) (MAKESET (CDR L1))))
        (T (MAKESET (CDR L1)))))

(DE SETEQ (L1 L2)
  (COND ((EQUAL L1 L2))
        ((ATOM L1) (ATOM L2))
        ((MEMBER (CAR L1) L2)
         (SETEQ (CDR L1) (REMOVE (CAR L1) L2)))))

(DE SETP (L1)
  (COND ((NULL L1) T)
        ((MEMBER (CAR L1) (CDR L1)) NIL)
        (T (SETP (CDR L1)))))

(DE SUBSETP (L1 L2)
  (COND ((EQUAL L1 L2))
        ((ATOM L1))
        ((MEMBER (CAR L1) L2) (SUBSETP (CDR L1) L2))))
