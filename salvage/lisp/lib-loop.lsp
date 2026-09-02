; LISP 64 -- LOOP-Subset (Host-Prototyp, Phase-6-Stufe-3-Bibliothek)
;
; Bewusst ein SUBSET der gaengigsten CL-LOOP-Klauseln, KEIN volles ANSI-LOOP.
; LOOP ist ein Makro -> expandiert zur Definitionszeit in normalen PROG/GO-Code;
; Laufzeitkosten = wie handgeschriebene Schleife (kein Per-Iteration-Overhead).
;
; HYGIENE: alle internen Namen (Akku, Tail, Counter, Labels) werden via GENSYM
; erzeugt -> LOOP ist beliebig schachtelbar (anders als DOTIMES/DOLIST mit festem
; Label LOOP). Details: docs/loop-subset-spec.md.
;
; Unterstuetzte Klauseln:
;   Treiber (einer pro LOOP): FOR v IN liste | FOR v FROM a TO b [BY s] | REPEAT n
;                             | (kein Treiber: nur WHILE/UNTIL/DO)
;   Rumpf: DO form... | COLLECT expr | SUM expr | COUNT expr | WHILE test
;          | UNTIL test | FINALLY form...

(DE LOOP-KWP (X) (MEMBER X '(DO COLLECT SUM COUNT WHILE UNTIL FINALLY)))

(DE LOOP-SPAN (CL)
  (COND ((NULL CL) (CONS NIL NIL))
        ((LOOP-KWP (CAR CL)) (CONS NIL CL))
        (T (PROG (R)
             (SETQ R (LOOP-SPAN (CDR CL)))
             (RETURN (CONS (CONS (CAR CL) (CAR R)) (CDR R)))))))

; Rumpf-Klauseln parsen -> (PERITEM-FORMEN AKK-ART FINALLY-FORMEN).
; GACC/GEND = gensym'te Akku-Variable / End-Label.
(DE LOOP-PB (CL GACC GEND)
  (COND
    ((NULL CL) (LIST NIL NIL NIL))
    ((EQ (CAR CL) 'DO)
       (PROG (SP R)
         (SETQ SP (LOOP-SPAN (CDR CL)))
         (SETQ R (LOOP-PB (CDR SP) GACC GEND))
         (RETURN (LIST (APPEND (CAR SP) (CAR R)) (CADR R) (CADDR R)))))
    ((EQ (CAR CL) 'COLLECT)
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST 'SETQ GACC (LIST 'CONS (CADR CL) GACC)) (CAR R))
                       'COLLECT (CADDR R)))))
    ((EQ (CAR CL) 'SUM)
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST 'SETQ GACC (LIST 'PLUS GACC (CADR CL))) (CAR R))
                       'SUM (CADDR R)))))
    ((EQ (CAR CL) 'COUNT)
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST 'COND (LIST (CADR CL) (LIST 'SETQ GACC (LIST 'ADD1 GACC)))) (CAR R))
                       'COUNT (CADDR R)))))
    ((EQ (CAR CL) 'WHILE)
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST 'COND (LIST (LIST 'NOT (CADR CL)) (LIST 'GO GEND))) (CAR R))
                       (CADR R) (CADDR R)))))
    ((EQ (CAR CL) 'UNTIL)
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST 'COND (LIST (CADR CL) (LIST 'GO GEND))) (CAR R))
                       (CADR R) (CADDR R)))))
    ((EQ (CAR CL) 'FINALLY)
       (LIST NIL NIL (CDR CL)))
    (T (ERROR (LIST 'LOOP-BAD-CLAUSE (CAR CL))))))

(DE LOOP-ACCINIT (K) (COND ((EQ K 'SUM) 0) ((EQ K 'COUNT) 0) (T NIL)))
(DE LOOP-ACCRES (K GACC)
  (COND ((EQ K 'COLLECT) (LIST 'REVERSE GACC))
        ((EQ K 'SUM) GACC)
        ((EQ K 'COUNT) GACC)
        (T NIL)))

(DE LOOP-IN (V SRC P GACC GLOOP GEND GTAIL)
  (CONS 'PROG
    (CONS (LIST V GTAIL GACC)
      (APPEND
        (LIST (LIST 'SETQ GTAIL SRC)
              (LIST 'SETQ GACC (LOOP-ACCINIT (CADR P)))
              GLOOP
              (LIST 'COND (LIST (LIST 'ATOM GTAIL) (LIST 'GO GEND)))
              (LIST 'SETQ V (LIST 'CAR GTAIL)))
        (CAR P)
        (LIST (LIST 'SETQ GTAIL (LIST 'CDR GTAIL)) (LIST 'GO GLOOP) GEND)
        (CADDR P)
        (LIST (LIST 'RETURN (LOOP-ACCRES (CADR P) GACC)))))))

(DE LOOP-FROM (V A B S P GACC GLOOP GEND)
  (CONS 'PROG
    (CONS (LIST V GACC)
      (APPEND
        (LIST (LIST 'SETQ V A)
              (LIST 'SETQ GACC (LOOP-ACCINIT (CADR P)))
              GLOOP
              (LIST 'COND (LIST (LIST 'GREATERP V B) (LIST 'GO GEND))))
        (CAR P)
        (LIST (LIST 'SETQ V (LIST 'PLUS V S)) (LIST 'GO GLOOP) GEND)
        (CADDR P)
        (LIST (LIST 'RETURN (LOOP-ACCRES (CADR P) GACC)))))))

(DE LOOP-REP (N P GACC GLOOP GEND GCNT)
  (CONS 'PROG
    (CONS (LIST GCNT GACC)
      (APPEND
        (LIST (LIST 'SETQ GCNT N)
              (LIST 'SETQ GACC (LOOP-ACCINIT (CADR P)))
              GLOOP
              (LIST 'COND (LIST (LIST 'NOT (LIST 'GREATERP GCNT 0)) (LIST 'GO GEND))))
        (CAR P)
        (LIST (LIST 'SETQ GCNT (LIST 'SUB1 GCNT)) (LIST 'GO GLOOP) GEND)
        (CADDR P)
        (LIST (LIST 'RETURN (LOOP-ACCRES (CADR P) GACC)))))))

(DE LOOP-BARE (P GACC GLOOP GEND)
  (CONS 'PROG
    (CONS (LIST GACC)
      (APPEND
        (LIST (LIST 'SETQ GACC (LOOP-ACCINIT (CADR P))) GLOOP)
        (CAR P)
        (LIST (LIST 'GO GLOOP) GEND)
        (CADDR P)
        (LIST (LIST 'RETURN (LOOP-ACCRES (CADR P) GACC)))))))

(DE LOOP-DISPATCH (CLS)
  (PROG (GACC GLOOP GEND GTAIL GCNT)
    (SETQ GACC (GENSYM "LACC"))
    (SETQ GLOOP (GENSYM "LOOP"))
    (SETQ GEND (GENSYM "LEND"))
    (SETQ GTAIL (GENSYM "LTAIL"))
    (SETQ GCNT (GENSYM "LCNT"))
    (RETURN
      (COND
        ((AND (EQ (CAR CLS) 'FOR) (EQ (CADDR CLS) 'IN))
           (LOOP-IN (CADR CLS) (CADDDR CLS)
                    (LOOP-PB (CDR (CDDDR CLS)) GACC GEND) GACC GLOOP GEND GTAIL))
        ((AND (EQ (CAR CLS) 'FOR) (EQ (CADDR CLS) 'FROM))
           (PROG (A AFT B AB S BODY)
             (SETQ A (CADDDR CLS))
             (SETQ AFT (CDR (CDDDR CLS)))
             (SETQ B (CADR AFT))
             (SETQ AB (CDDR AFT))
             (COND ((EQ (CAR AB) 'BY) (SETQ S (CADR AB)) (SETQ BODY (CDDR AB)))
                   (T (SETQ S 1) (SETQ BODY AB)))
             (RETURN (LOOP-FROM (CADR CLS) A B S
                                (LOOP-PB BODY GACC GEND) GACC GLOOP GEND))))
        ((EQ (CAR CLS) 'REPEAT)
           (LOOP-REP (CADR CLS) (LOOP-PB (CDDR CLS) GACC GEND) GACC GLOOP GEND GCNT))
        (T (LOOP-BARE (LOOP-PB CLS GACC GEND) GACC GLOOP GEND))))))

(DM LOOP L (LOOP-DISPATCH (CDR L)))
