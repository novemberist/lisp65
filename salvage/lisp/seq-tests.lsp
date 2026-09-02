; Tests fuer lib-seq.
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/lib-seq.lsp lisp/seq-tests.lsp

(DE POSP (X) (GREATERP X 0))

; ---- -IF-Varianten ----
(CHECK (MEMBER-IF (QUOTE POSP) (QUOTE (-1 -2 3 4))) (QUOTE (3 4)))
(CHECK (FIND-IF (QUOTE POSP) (QUOTE (-1 -2 3 4))) 3)
(CHECK (POSITION-IF (QUOTE POSP) (QUOTE (-1 -2 3 4))) 2)
(CHECK (COUNT-IF (QUOTE POSP) (QUOTE (-1 2 -3 4 5))) 3)
(CHECK (ASSOC-IF (QUOTE POSP) (QUOTE ((-1 . A) (2 . B) (3 . C)))) (QUOTE (2 . B)))

; ---- remove-duplicates (erstes Vorkommen) ----
(CHECK (REMOVE-DUPLICATES (QUOTE (A B A C B A))) (QUOTE (A B C)))
(CHECK (REMOVE-DUPLICATES (QUOTE (1 2 3))) (QUOTE (1 2 3)))
(CHECK (REMOVE-DUPLICATES (QUOTE ((A) (A) (B)))) (QUOTE ((A) (A) (B))))

; ---- subseq ----
(CHECK (SUBSEQ (QUOTE (A B C D E)) 1) (QUOTE (B C D E)))
(CHECK (SUBSEQ (QUOTE (A B C D E)) 1 3) (QUOTE (B C)))
(CHECK (SUBSEQ (QUOTE (A B C D E)) 0 2) (QUOTE (A B)))

; ---- sort (aufsteigend / absteigend) ----
(CHECK (SORT (QUOTE (3 1 4 1 5 2)) (QUOTE LESSP)) (QUOTE (1 1 2 3 4 5)))
(CHECK (SORT (QUOTE (3 1 4 1 5 2)) (QUOTE GREATERP)) (QUOTE (5 4 3 2 1 1)))
(CHECK (SORT NIL (QUOTE LESSP)) NIL)

; ---- Zusammenspiel mit Builtins (MAPCAN) ----
(DE DUP (X) (LIST X X))
(CHECK (MAPCAN (QUOTE DUP) (QUOTE (1 2))) (QUOTE (1 1 2 2)))

(CHECK-REPORT)
