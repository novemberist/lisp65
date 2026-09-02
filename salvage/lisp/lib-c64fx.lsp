; lib-c64fx -- lispige High-Level-Abstraktionen (Phase-5-Vorarbeit): die REINEN
; Algorithmen hinter Mal-/Sound-/Sprite-Komfort. KEIN Hardwarezugriff -- liefert
; Punktlisten / Bytes / Frequenzen, die die native Schicht dann ausgibt (poke/SID).
; Aufgesetzt auf lib-c64hw. Ideenkatalog: docs/highlevel-api-ideas.md.
;
; BARE DIALEKT (nur native Primitive + PROG, KEIN LET) -> auf dem echten System
; ladbar. Braucht nur lib-c64hw (sid-note-name).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-c64hw.lsp \
;       lisp/lib-c64fx.lsp lisp/c64fx-tests.lsp

(DE fx-sgn (n) (COND ((GREATERP n 0) 1) ((LESSP n 0) -1) (T 0)))
(DE fx-take (n l) (COND ((ZEROP n) NIL) ((NULL l) NIL) (T (CONS (CAR l) (fx-take (SUB1 n) (CDR l))))))
(DE fx-drop (n l) (COND ((ZEROP n) l) ((NULL l) NIL) (T (fx-drop (SUB1 n) (CDR l)))))

; ---- line-points: Bresenham -> Liste von (x . y) ----
(DE line-step (x y x1 y1 dx dy sx sy err)
  (PROG (e2 nx e3 ny e4)
    (SETQ e2 (TIMES 2 err))
    (SETQ nx (COND ((GREATERP e2 (MINUS dy)) (PLUS x sx)) (T x)))
    (SETQ e3 (COND ((GREATERP e2 (MINUS dy)) (DIFFERENCE err dy)) (T err)))
    (SETQ ny (COND ((LESSP e2 dx) (PLUS y sy)) (T y)))
    (SETQ e4 (COND ((LESSP e2 dx) (PLUS e3 dx)) (T e3)))
    (RETURN (line-aux nx ny x1 y1 dx dy sx sy e4))))
(DE line-aux (x y x1 y1 dx dy sx sy err)
  (CONS (CONS x y)
    (COND ((AND (EQ x x1) (EQ y y1)) NIL)
          (T (line-step x y x1 y1 dx dy sx sy err)))))
(DE line-points (x0 y0 x1 y1)
  (PROG (dx dy)
    (SETQ dx (ABS (DIFFERENCE x1 x0)))
    (SETQ dy (ABS (DIFFERENCE y1 y0)))
    (RETURN (line-aux x0 y0 x1 y1 dx dy
              (fx-sgn (DIFFERENCE x1 x0)) (fx-sgn (DIFFERENCE y1 y0))
              (DIFFERENCE dx dy)))))

; ---- circle-points: Mittelpunkt-Algorithmus (8-fache Symmetrie) ----
(DE circ-octants (cx cy x y)
  (LIST (CONS (PLUS cx x) (PLUS cy y)) (CONS (DIFFERENCE cx x) (PLUS cy y))
        (CONS (PLUS cx x) (DIFFERENCE cy y)) (CONS (DIFFERENCE cx x) (DIFFERENCE cy y))
        (CONS (PLUS cx y) (PLUS cy x)) (CONS (DIFFERENCE cx y) (PLUS cy x))
        (CONS (PLUS cx y) (DIFFERENCE cy x)) (CONS (DIFFERENCE cx y) (DIFFERENCE cy x))))
(DE circ-aux (cx cy x y d)
  (COND ((GREATERP x y) NIL)
        (T (APPEND (circ-octants cx cy x y)
             (circ-aux cx cy (ADD1 x)
               (COND ((LESSP d 0) y) (T (SUB1 y)))
               (COND ((LESSP d 0) (PLUS d (PLUS (TIMES 2 x) 3)))
                     (T (PLUS d (PLUS (TIMES 2 (DIFFERENCE x y)) 5)))))))))
(DE circle-points (cx cy r) (circ-aux cx cy 0 r (DIFFERENCE 1 r)))

; ---- defshape: Text-Art -> Sprite-Bytes (Zeile -> Bits MSB-first -> Bytes) ----
(DE char-bit (c) (COND ((EQUAL c ".") 0) ((EQUAL c " ") 0) (T 1)))
(DE bits-byte (bits weight acc)
  (COND ((NULL bits) acc) ((ZEROP weight) acc)
        (T (bits-byte (CDR bits) (QUOTIENT weight 2) (PLUS acc (TIMES (CAR bits) weight))))))
(DE bits->bytes (bits)
  (COND ((NULL bits) NIL)
        (T (CONS (bits-byte (fx-take 8 bits) 128 0) (bits->bytes (fx-drop 8 bits))))))
(DE shape-row->bytes (s) (bits->bytes (MAPCAR (QUOTE char-bit) (UNPACK s))))
(DE shape->bytes (rows)
  (COND ((NULL rows) NIL)
        (T (APPEND (shape-row->bytes (CAR rows)) (shape->bytes (CDR rows))))))
(DM DEFSHAPE L (LIST 'SETQ (CADR L) (LIST 'SHAPE->BYTES (LIST 'QUOTE (CDDR L)))))

; ---- play: Melodie als Daten -> (Frequenzregister . Dauer) ----
; Note = (NAME OKTAVE DAUER) ; (REST DAUER) -> Frequenz 0
(DE note->freq (note)
  (COND ((EQ (CAR note) (QUOTE REST)) (CONS 0 (CADR note)))
        (T (CONS (sid-note-name (CAR note) (CADR note)) (CAR (CDDR note))))))
(DE melody->freqs (tune) (MAPCAR (QUOTE note->freq) tune))
