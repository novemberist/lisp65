; Compact runtime used by the Mini-CLOS cross-compile native smoke.
; Host-expanded lib-clos forms are lowered to these short C64-safe names.

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

(DE CADD (G C F)
  (PUTPROP G 'CMETH (CONS (CONS C F) (GETPROP G 'CMETH))))

; Hinweis: DEFCLASS/DEFMETHAD (lib-clos) expandieren host-seitig zu
; MCLOS-DEFINE-CLASS/MCLOS-DEFINE-METHOD; diese werden vom Lowering-Script
; (scripts/lower-mini-clos-to-c64-dispatch.py) in konstante CSUP/CMETH-PUTPROPs
; plus Dispatcher-DEs aufgeloest und brauchen daher keine C64-Runtime-Funktion.
; Grund: der native LOAD-Pfad korrumpiert param-basierte PUTPROP-Akkumulation in
; LOAD-Lambdas (siehe docs/architecture.md, Abschnitt 4).
