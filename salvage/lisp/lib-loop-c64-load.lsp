; C64 LOAD variant of lib-loop.lsp.
; CADDR/CADDDR/CDDDR are not native on C64 -- define compact helpers here.
; Hyphen names are fine for the LOAD fixture (character-by-character read).

(DE CADDR (X) (CAR (CDDR X)))
(DE CADDDR (X) (CAR (CDR (CDDR X))))
(DE CDDDR (X) (CDR (CDDR X)))

(DE LOOP-KWP (X) (MEMBER X (QUOTE (DO COLLECT SUM COUNT WHILE UNTIL FINALLY))))

(DE LOOP-SPAN (CL)
  (COND ((NULL CL) (CONS NIL NIL))
        ((LOOP-KWP (CAR CL)) (CONS NIL CL))
        (T (PROG (R)
             (SETQ R (LOOP-SPAN (CDR CL)))
             (RETURN (CONS (CONS (CAR CL) (CAR R)) (CDR R)))))))

(DE LOOP-PB (CL GACC GEND)
  (COND
    ((NULL CL) (LIST NIL NIL NIL))
    ((EQ (CAR CL) (QUOTE DO))
       (PROG (SP R)
         (SETQ SP (LOOP-SPAN (CDR CL)))
         (SETQ R (LOOP-PB (CDR SP) GACC GEND))
         (RETURN (LIST (APPEND (CAR SP) (CAR R)) (CADR R) (CADDR R)))))
    ((EQ (CAR CL) (QUOTE COLLECT))
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST (QUOTE SETQ) GACC (LIST (QUOTE CONS) (CADR CL) GACC)) (CAR R))
                       (QUOTE COLLECT) (CADDR R)))))
    ((EQ (CAR CL) (QUOTE SUM))
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST (QUOTE SETQ) GACC (LIST (QUOTE PLUS) GACC (CADR CL))) (CAR R))
                       (QUOTE SUM) (CADDR R)))))
    ((EQ (CAR CL) (QUOTE COUNT))
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST (QUOTE COND) (LIST (CADR CL) (LIST (QUOTE SETQ) GACC (LIST (QUOTE ADD1) GACC)))) (CAR R))
                       (QUOTE COUNT) (CADDR R)))))
    ((EQ (CAR CL) (QUOTE WHILE))
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST (QUOTE COND) (LIST (LIST (QUOTE NOT) (CADR CL)) (LIST (QUOTE GO) GEND))) (CAR R))
                       (CADR R) (CADDR R)))))
    ((EQ (CAR CL) (QUOTE UNTIL))
       (PROG (R)
         (SETQ R (LOOP-PB (CDDR CL) GACC GEND))
         (RETURN (LIST (CONS (LIST (QUOTE COND) (LIST (CADR CL) (LIST (QUOTE GO) GEND))) (CAR R))
                       (CADR R) (CADDR R)))))
    ((EQ (CAR CL) (QUOTE FINALLY))
       (LIST NIL NIL (CDR CL)))
    (T (ERROR (LIST (QUOTE LOOP-BAD-CLAUSE) (CAR CL))))))

(DE LOOP-ACCINIT (K) (COND ((EQ K (QUOTE SUM)) 0) ((EQ K (QUOTE COUNT)) 0) (T NIL)))
(DE LOOP-ACCRES (K GACC)
  (COND ((EQ K (QUOTE COLLECT)) (LIST (QUOTE REVERSE) GACC))
        ((EQ K (QUOTE SUM)) GACC)
        ((EQ K (QUOTE COUNT)) GACC)
        (T NIL)))

; Build exit clause: FINALLY forms (if any) followed by (RETURN result).
; Used inline in COND to avoid GO-from-COND, which hangs on native C64.
(DE LOOP-EXIT (P GACC)
  (APPEND (CADDR P) (LIST (LIST (QUOTE RETURN) (LOOP-ACCRES (CADR P) GACC)))))

(DE LOOP-IN (V SRC P GACC GLOOP GEND GTAIL)
  (CONS (QUOTE PROG)
    (CONS (LIST V GTAIL GACC)
      (APPEND
        (LIST (LIST (QUOTE SETQ) GTAIL SRC)
              (LIST (QUOTE SETQ) GACC (LOOP-ACCINIT (CADR P)))
              GLOOP
              (CONS (QUOTE COND) (LIST (CONS (LIST (QUOTE ATOM) GTAIL) (LOOP-EXIT P GACC))))
              (LIST (QUOTE SETQ) V (LIST (QUOTE CAR) GTAIL)))
        (CAR P)
        (LIST (LIST (QUOTE SETQ) GTAIL (LIST (QUOTE CDR) GTAIL)) (LIST (QUOTE GO) GLOOP))))))

(DE LOOP-FROM (V A B S P GACC GLOOP GEND)
  (CONS (QUOTE PROG)
    (CONS (LIST V GACC)
      (APPEND
        (LIST (LIST (QUOTE SETQ) V A)
              (LIST (QUOTE SETQ) GACC (LOOP-ACCINIT (CADR P)))
              GLOOP
              (CONS (QUOTE COND) (LIST (CONS (LIST (QUOTE GREATERP) V B) (LOOP-EXIT P GACC)))))
        (CAR P)
        (LIST (LIST (QUOTE SETQ) V (LIST (QUOTE PLUS) V S)) (LIST (QUOTE GO) GLOOP))))))

(DE LOOP-REP (N P GACC GLOOP GEND GCNT)
  (CONS (QUOTE PROG)
    (CONS (LIST GCNT GACC)
      (APPEND
        (LIST (LIST (QUOTE SETQ) GCNT N)
              (LIST (QUOTE SETQ) GACC (LOOP-ACCINIT (CADR P)))
              GLOOP
              (CONS (QUOTE COND) (LIST (CONS (LIST (QUOTE NOT) (LIST (QUOTE GREATERP) GCNT 0)) (LOOP-EXIT P GACC)))))
        (CAR P)
        (LIST (LIST (QUOTE SETQ) GCNT (LIST (QUOTE SUB1) GCNT)) (LIST (QUOTE GO) GLOOP))))))

(DE LOOP-BARE (P GACC GLOOP GEND)
  (CONS (QUOTE PROG)
    (CONS (LIST GACC)
      (APPEND
        (LIST (LIST (QUOTE SETQ) GACC (LOOP-ACCINIT (CADR P))) GLOOP)
        (CAR P)
        (LIST (LIST (QUOTE GO) GLOOP) GEND)
        (CADDR P)
        (LIST (LIST (QUOTE RETURN) (LOOP-ACCRES (CADR P) GACC)))))))

(DE LOOP-DISPATCH (CLS)
  (PROG (GACC GLOOP GEND GTAIL GCNT)
    (SETQ GACC (GENSYM "LACC"))
    (SETQ GLOOP (GENSYM "LOOP"))
    (SETQ GEND (GENSYM "LEND"))
    (SETQ GTAIL (GENSYM "LTAIL"))
    (SETQ GCNT (GENSYM "LCNT"))
    (RETURN
      (COND
        ((AND (EQ (CAR CLS) (QUOTE FOR)) (EQ (CADDR CLS) (QUOTE IN)))
           (LOOP-IN (CADR CLS) (CADDDR CLS)
                    (LOOP-PB (CDR (CDDDR CLS)) GACC GEND) GACC GLOOP GEND GTAIL))
        ((AND (EQ (CAR CLS) (QUOTE FOR)) (EQ (CADDR CLS) (QUOTE FROM)))
           (PROG (A AFT B AB S BODY)
             (SETQ A (CADDDR CLS))
             (SETQ AFT (CDR (CDDDR CLS)))
             (SETQ B (CADR AFT))
             (SETQ AB (CDDR AFT))
             (COND ((EQ (CAR AB) (QUOTE BY)) (SETQ S (CADR AB)) (SETQ BODY (CDDR AB)))
                   (T (SETQ S 1) (SETQ BODY AB)))
             (RETURN (LOOP-FROM (CADR CLS) A B S
                                (LOOP-PB BODY GACC GEND) GACC GLOOP GEND))))
        ((EQ (CAR CLS) (QUOTE REPEAT))
           (LOOP-REP (CADR CLS) (LOOP-PB (CDDR CLS) GACC GEND) GACC GLOOP GEND GCNT))
        (T (LOOP-BARE (LOOP-PB CLS GACC GEND) GACC GLOOP GEND))))))

(DM LOOP L (LOOP-DISPATCH (CDR L)))
