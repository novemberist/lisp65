; LISP 64 -- Makro-Bibliothek
; Salvage aus reference/.../samples/macros.lsp (Original Lisp 64, Rel. 2).
; Semantik unveraendert, nur lesbar umformatiert.
;
; DM-Konvention des Dialekts: das Formal (hier nospread `L`) ist an die GANZE
; Aufrufform gebunden; (CAR L) ist der Makroname, (CADR L) das erste Argument.
; REPLACE spleisst die Expansion destruktiv in die Aufrufform (Makro-Caching),
; gesteuert ueber MACRO-EXPANSION.
;
; HINWEIS (faithful quirk): FOR/REPEAT werten ihre Grenzen zur Expansionszeit
; aus und backen sie als Konstanten ein (durch das Caching nur einmal).

(SETQ MACRO-EXPANSION T)
(DE EXPAND () (SETQ MACRO-EXPANSION T))
(DE NO-EXPAND () (SETQ MACRO-EXPANSION NIL))

(DE REPLACE (X Y)
  (COND (MACRO-EXPANSION
         (RPLACA X (CAR Y))
         (RPLACD X (CDR Y)))
        (T Y)))

; (IF test then else...)
(DM IF L
  (REPLACE L
    (LIST 'COND
      (LIST (CADR L) (CAR (CDDR L)))
      (CONS 'T (CDR (CDDR L))))))

; (WHILE cond body...)
(DM WHILE L
  (REPLACE L
    (LIST 'PROG NIL
      'LOOP
      (LIST 'COND
        (LIST (LIST 'NOT (CADR L)) (LIST 'RETURN NIL))
        (CONS 'T (CDDR L)))
      '(GO LOOP))))

; (FOR var von nach body...)
(DM FOR L
  (REPLACE L
    (PROG (VAR VON NACH COUNT-FN TEST-FN)
      (SETQ VAR (CADR L))
      (SETQ VON (EVAL (CAR (CDDR L))))
      (SETQ NACH (EVAL (CADR (CDDR L))))
      (COND ((GREATERP VON NACH)
             (SETQ TEST-FN 'LESSP) (SETQ COUNT-FN 'SUB1))
            (T
             (SETQ TEST-FN 'GREATERP) (SETQ COUNT-FN 'ADD1)))
      (RETURN
        (LIST 'PROG (LIST VAR)
          (LIST 'SETQ VAR VON)
          'LOOP
          (LIST 'COND
            (LIST (LIST TEST-FN VAR NACH) '(RETURN NIL))
            (CONS 'T (CDDR (CDDR L))))
          (LIST 'SETQ VAR (LIST COUNT-FN VAR))
          '(GO LOOP))))))

; (REPEAT n body...)
(DM REPEAT L
  (REPLACE L
    (LIST 'PROG '(N)
      (LIST 'SETQ 'N (EVAL (CADR L)))
      'LOOP
      (LIST 'COND
        (LIST '(ZEROP N) '(RETURN NIL))
        (CONS 'T (CDDR L)))
      '(SETQ N (SUB1 N))
      '(GO LOOP))))

; (SELECTQ key (k1 . body1) (k2 . body2) defaultexpr)
(DM SELECTQ L
  (REPLACE L
    (CONS 'COND
      ((LABEL SELECTQ1
        (LAMBDA (X L)
          (COND ((ATOM (CDR L))
                 (LIST (LIST 'T (CAR L))))
                (T (CONS (CONS (LIST (COND ((ATOM (CAAR L)) 'EQ)
                                           (T 'MEMBER))
                                     X
                                     (LIST 'QUOTE (CAAR L)))
                               (CDAR L))
                         (SELECTQ1 X (CDR L)))))))
       (CADR L)
       (CDDR L)))))

; (LET ((v1 e1) (v2 e2)...) body...)  -> parallele Bindung via LAMBDA
(DM LET L
  (REPLACE L
    (CONS (CONS 'LAMBDA
            (CONS (MAPCAR 'CAR (CADR L)) (CDDR L)))
          (MAPCAR 'CADR (CADR L)))))

; (LOCAL (vars...) body...)  -> lokale, NIL-initialisierte Variablen
(DM LOCAL L
  (REPLACE L
    (CONS (CONS 'LAMBDA (CDR L)) NIL)))

(DM INCR L (REPLACE L (LIST 'SETQ (CADR L) (LIST 'ADD1 (CADR L)))))
(DM DECR L (REPLACE L (LIST 'SETQ (CADR L) (LIST 'SUB1 (CADR L)))))

; (PUSH place item) -> (SETQ place (CONS item place))
(DM PUSH L
  (REPLACE L
    (LIST 'SETQ (CADR L) (LIST 'CONS (CAR (CDDR L)) (CADR L)))))

; (POP place) -> (PROG1 (CAR place) (SETQ place (CDR place)))
(DM POP L
  (REPLACE L
    (LIST 'PROG1 (LIST 'CAR (CADR L))
      (LIST 'SETQ (CADR L) (LIST 'CDR (CADR L))))))

(DM NCONS L (REPLACE L (LIST 'CONS (CADR L) NIL)))
(DM XCONS L (REPLACE L (LIST 'CONS (CAR (CDDR L)) (CADR L))))
(DM FUNCTION L (REPLACE L (LIST 'QUOTE (CADR L))))
(DM NEQ L (REPLACE L (LIST 'NOT (LIST 'EQ (CADR L) (CAR (CDDR L))))))
