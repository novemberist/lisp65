; LISP 64 -- Mini-CLOS (Single-Dispatch, Host-Prototyp, Phase-6-Stufe-3)
;
; Der GRENZFALL aus docs/optional-feature-tier.md / docs/dispatch-models.md:
; Klassen/Methoden + Generator sind Bibliothek (Makros), aber der DISPATCH-KERN
; (MCLOS-DISPATCH/-PREC/-FIND) laeuft zur Laufzeit RESIDENT -> nicht ganz gratis.
; Single-Dispatch auf die Klasse des ERSTEN Arguments; flache Vererbungskette
; (eine Superklasse), Methodensuche entlang der Klassen-Praezedenz bis T.
;
; Oberflaeche: DEFCLASS, MAKE-INSTANCE (Keyword-Initargs), SLOT-VALUE (setf-faehig),
; DEFGENERIC (optional), DEFMETHOD, CLASS-OF.
; GRENZE: keine Multimethoden (siehe dispatch-models.md), kein :initform, keine
; Mehrfachvererbung, kein call-next-method.

; ---- Laufzeit-Kern (resident) ----
(DE MCLOS-GETF (PL K)
  (COND ((NULL PL) NIL)
        ((EQ (CAR PL) K) (CADR PL))
        (T (MCLOS-GETF (CDDR PL) K))))

(DE CLASS-OF (OBJ) (COND ((CONSP OBJ) (CAR OBJ)) (T T)))

; Klassen-Praezedenzliste: C, super(C), ... , T
(DE MCLOS-PREC (C)
  (COND ((NULL C) (LIST T))
        ((EQ C T) (LIST T))
        (T (CONS C (MCLOS-PREC (GETPROP C 'CLOS-SUPER))))))

; Erste passende Methode entlang der Praezedenz (most-specific-first)
(DE MCLOS-FIND (METHS PREC)
  (COND ((NULL PREC) NIL)
        (T (PROG (M)
             (SETQ M (ASSOC (CAR PREC) METHS))
             (RETURN (COND (M (CDR M)) (T (MCLOS-FIND METHS (CDR PREC)))))))))

(DE MCLOS-DISPATCH (GNAME ARGS)
  (PROG (FN)
    (SETQ FN (MCLOS-FIND (GETPROP GNAME 'CLOS-METHODS)
                         (MCLOS-PREC (CLASS-OF (CAR ARGS)))))
    (RETURN (COND (FN (APPLY FN ARGS))
                  (T (ERROR GNAME))))))

; alle Slots: eigene + ererbte
(DE MCLOS-ALL-SLOTS (C)
  (COND ((NULL C) NIL)
        ((EQ C T) NIL)
        (T (APPEND (GETPROP C 'CLOS-SLOTS) (MCLOS-ALL-SLOTS (GETPROP C 'CLOS-SUPER))))))

(DE MCLOS-KW (S) (PACK (LIST ': S)))

(DE MCLOS-BUILD-SLOTS (SLOTS INITARGS)
  (COND ((NULL SLOTS) NIL)
        (T (CONS (CAR SLOTS)
                 (CONS (MCLOS-GETF INITARGS (MCLOS-KW (CAR SLOTS)))
                       (MCLOS-BUILD-SLOTS (CDR SLOTS) INITARGS))))))

; Instanz = (KLASSE slot1 v1 slot2 v2 ...)
(DE MAKE-INSTANCE ARGS
  (CONS (CAR ARGS)
        (MCLOS-BUILD-SLOTS (MCLOS-ALL-SLOTS (CAR ARGS)) (CDR ARGS))))

(DE SLOT-VALUE (OBJ S) (MCLOS-GETF (CDR OBJ) S))

(DE SET-SLOT-VALUE (OBJ S V)
  (PROG (PL)
    (SETQ PL (CDR OBJ))
   LOOP
    (COND ((NULL PL) (RETURN NIL))
          ((EQ (CAR PL) S) (RPLACA (CDR PL) V) (RETURN V))
          (T (SETQ PL (CDDR PL)) (GO LOOP)))))

; SLOT-VALUE als setf-Place (nutzt SETF-FN-Pfad aus cl-compat)
(PUTPROP 'SLOT-VALUE 'SETF-FN 'SET-SLOT-VALUE)

(DE MCLOS-REMASSOC (K AL)
  (COND ((NULL AL) NIL)
        ((EQ (CAR (CAR AL)) K) (MCLOS-REMASSOC K (CDR AL)))
        (T (CONS (CAR AL) (MCLOS-REMASSOC K (CDR AL))))))

(DE MCLOS-ADD-METHOD (GNAME CLS FN)
  (PUTPROP GNAME 'CLOS-METHODS
    (CONS (CONS CLS FN)
          (MCLOS-REMASSOC CLS (GETPROP GNAME 'CLOS-METHODS)))))

; ---- Makros (Generator, PC-seitig) ----

(DE MCLOS-DEFINE-CLASS (NAME SUPER SLOTS)
  (PUTPROP NAME 'CLOS-SUPER SUPER)
  (PUTPROP NAME 'CLOS-SLOTS SLOTS))

; (DEFCLASS NAME (SUPER) slot...)  -- SUPER optional (() = keine)
(DM DEFCLASS L
  (PROG (NAME SUPERSPEC SLOTS SUPER)
    (SETQ NAME (CADR L))
    (SETQ SUPERSPEC (CADDR L))
    (SETQ SUPER (COND ((CONSP SUPERSPEC) (CAR SUPERSPEC))
                      (T NIL)))
    (SETQ SLOTS (CDDDR L))
    (RETURN (LIST 'MCLOS-DEFINE-CLASS
                  (LIST 'QUOTE NAME)
                  (LIST 'QUOTE SUPER)
                  (LIST 'QUOTE SLOTS)))))

(DE MCLOS-DEFINE-METHOD (GNAME CLASS FN)
  ; support both fully-built lambda forms and legacy split-style callers
  (COND ((AND (CONSP FN) (EQ (CAR FN) 'LAMBDA))
         (MCLOS-ADD-METHOD GNAME CLASS FN))
        ((CONSP FN)
         (MCLOS-ADD-METHOD GNAME CLASS (CONS 'LAMBDA FN)))
        (T (MCLOS-ADD-METHOD GNAME CLASS FN)))
  (PUTPROP GNAME 'EXPR
    (LIST GNAME 'MCLOS-L (LIST 'MCLOS-DISPATCH (LIST 'QUOTE GNAME) 'MCLOS-L))))

(DM DEFGENERIC L
  (LIST 'DE (CADR L) 'MCLOS-L
        (LIST 'MCLOS-DISPATCH (LIST 'QUOTE (CADR L)) 'MCLOS-L)))

; (DEFMETHOD GNAME ((var CLASS) more-args...) body...)
(DM DEFMETHOD L
  (PROG (GNAME ARGLIST SPEC CLASS PARAMS BODY)
    (SETQ GNAME (CADR L))
    (SETQ ARGLIST (CADDR L))
    (SETQ SPEC (CAR ARGLIST))
    (SETQ CLASS (CADR SPEC))
    (SETQ PARAMS (CONS (CAR SPEC) (CDR ARGLIST)))
    (SETQ BODY (CDDDR L))
    (RETURN
      (LIST 'MCLOS-DEFINE-METHOD
            (LIST 'QUOTE GNAME)
            (LIST 'QUOTE CLASS)
            (LIST 'QUOTE (CONS 'LAMBDA (CONS PARAMS BODY)))))))
