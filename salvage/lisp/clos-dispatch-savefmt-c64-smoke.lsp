; SAVE-format C64 smoke for the Mini-CLOS resident dispatch core.
; Uses short names to keep historical LOAD records small.

(DE CGETF (PL K)
  (COND ((NULL PL) NIL)
        ((EQ (CAR PL) K) (CADR PL))
        (T (CGETF (CDDR PL) K))))

(DE CCLASS (OBJ)
  (COND ((CONSP OBJ) (CAR OBJ)) (T T)))

(DE CPREC (C)
  (COND ((NULL C) (LIST T))
        ((EQ C T) (LIST T))
        (T (CONS C (CPREC (GETPROP C 'CSUP))))))

(DE CFIND (M P)
  (COND ((NULL P) NIL)
        (T (PROG (X)
             (SETQ X (ASSOC (CAR P) M))
             (RETURN (COND (X (CDR X)) (T (CFIND M (CDR P)))))))))

(DE CDISPATCH (G A)
  (PROG (F)
    (SETQ F (CFIND (GETPROP G 'CMETH) (CPREC (CCLASS (CAR A)))))
    (RETURN (COND (F (APPLY F A)) (T NIL)))))

(DE CSLOT (O S) (CGETF (CDR O) S))

(DE CSETSLOT (O S V)
  (PROG (PL)
    (SETQ PL (CDR O))
   L
    (COND ((NULL PL) (RETURN NIL))
          ((EQ (CAR PL) S) (RPLACA (CDR PL) V) (RETURN V))
          (T (SETQ PL (CDDR PL)) (GO L)))))

(DE CAREA (C)
  (TIMES 3 (TIMES (CSLOT C 'RADIUS) (CSLOT C 'RADIUS))))

(DE CBAREA (S) 5)

(DE CKIND (S) 'SHAPE)

(DE CTKIND (X) 'ANY)

(DE CSET1 ()
  (PROG NIL
    (PUTPROP 'CIRCLE 'CSUP 'SHAPE)
    (PUTPROP 'SHAPE 'CSUP NIL)
    (RETURN T)))

(DE CSETA ()
  (PUTPROP 'AREA 'CMETH (LIST (CONS 'SHAPE 'CBAREA) (CONS 'CIRCLE 'CAREA))))

(DE CSETK ()
  (PUTPROP 'KIND 'CMETH (LIST (CONS T 'CTKIND) (CONS 'SHAPE 'CKIND))))

(DE CSET2 ()
  (PROG NIL
    (CSETA)
    (CSETK)
    (RETURN T)))

(DE COBJ () '(CIRCLE RADIUS 4 NAME C1))

(DE CSOBJ () '(SHAPE NAME S1))

(DE CDOAREA (X) (CDISPATCH 'AREA (LIST X)))

(DE CDOKIND (X) (CDISPATCH 'KIND (LIST X)))

(DE COK1 (X)
  (AND (EQL (CDOAREA X) 12) (EQ (CDOKIND X) 'SHAPE)))

(DE COK2 ()
  (AND (EQL (CDOAREA (CSOBJ)) 5) (EQ (CDOKIND 42) 'ANY)))

(DE MCLOSTEST ()
  (PROG (X)
    (CSET1)
    (CSET2)
    (SETQ X (COBJ))
    (CSETSLOT X 'RADIUS 2)
    (RETURN (COND ((AND (COK1 X) (COK2)) 'CDPASS)
                  (T 'CDFAIL)))))
