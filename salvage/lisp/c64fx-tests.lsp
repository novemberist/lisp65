; Tests fuer lib-c64fx (reine High-Level-Algorithmen).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-c64hw.lsp \
;       lisp/lib-c64fx.lsp lisp/c64fx-tests.lsp

(DE pt-member (p l)
  (COND ((NULL l) NIL) ((EQUAL p (CAR l)) T) (T (pt-member p (CDR l)))))

; ---- line-points ----
(check (line-points 0 0 3 0) (quote ((0 . 0) (1 . 0) (2 . 0) (3 . 0))))   ; horizontal
(check (line-points 0 0 0 2) (quote ((0 . 0) (0 . 1) (0 . 2))))            ; vertikal
(check (line-points 0 0 2 2) (quote ((0 . 0) (1 . 1) (2 . 2))))            ; diagonal
(check (line-points 0 0 3 3) (quote ((0 . 0) (1 . 1) (2 . 2) (3 . 3))))
(check (line-points 2 2 0 0) (quote ((2 . 2) (1 . 1) (0 . 0))))            ; rueckwaerts

; ---- circle-points: Kardinalpunkte muessen enthalten sein ----
(check (pt-member (quote (15 . 10)) (circle-points 10 10 5)) T)            ; cx+r
(check (pt-member (quote (5 . 10))  (circle-points 10 10 5)) T)            ; cx-r
(check (pt-member (quote (10 . 15)) (circle-points 10 10 5)) T)            ; cy+r
(check (pt-member (quote (10 . 5))  (circle-points 10 10 5)) T)            ; cy-r
(check (pt-member (quote (99 . 99)) (circle-points 10 10 5)) NIL)

; ---- defshape: Text-Art -> Bytes ----
(check (shape-row->bytes "X.......") (quote (128)))
(check (shape-row->bytes ".......X") (quote (1)))
(check (shape-row->bytes "XX......") (quote (192)))
(check (shape-row->bytes "XXXXXXXX") (quote (255)))
(check (shape-row->bytes "X.......X.......") (quote (128 128)))            ; 16 Bit -> 2 Bytes
(defshape box "XXXXXXXX" "X......X" "XXXXXXXX")
(check box (quote (255 129 255)))

; ---- play: Melodie -> Frequenzen ----
(check (note->freq (quote (A 4 2))) (quote (7488 . 2)))
(check (note->freq (quote (REST 1))) (quote (0 . 1)))
(check (melody->freqs (quote ((C 0 1) (A 4 2) (REST 1))))
       (quote ((278 . 1) (7488 . 2) (0 . 1))))

(check-report)
