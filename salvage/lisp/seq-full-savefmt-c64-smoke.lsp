; Full sequence SAVE-format LOAD smoke.
; Keep wrapper functions short enough for 79-byte SAVE-format entries.

(DE POSP (X) (GREATERP X 0))
(DE SF1 () (SORT (QUOTE (3 1 2)) (QUOTE LESSP)))
(DE SF2 () (FINDIF (QUOTE POSP) (LIST (DIFFERENCE 0 1) 2 3)))
(DE SF3 () (SUBSEQ (QUOTE (A B C D)) 1 3))
(DE SF4 () (REMOVEDUPS (QUOTE (A B A C))))
(DE SEQFULL () (LIST (SF1) (SF2) (SF3) (SF4)))
