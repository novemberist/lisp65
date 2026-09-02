; Tests fuer die salvagten Bibliotheken (Makros, Arrays, Mengen).
; Lauf:
;   python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;     lisp/lib-arrays.lsp lisp/lib-sets.lsp lisp/lib-tests.lsp

; ---- Makros ----
(CHECK (IF T 1 2) 1)
(CHECK (IF NIL 1 2) 2)
(CHECK (LET ((X 2) (Y 3)) (PLUS X Y)) 5)
(CHECK (SELECTQ 'B (A 10) (B 20) 99) 20)
(CHECK (SELECTQ 'Z (A 10) (B 20) 99) 99)
(CHECK (NEQ 1 2) T)

; INCR/DECR
(SETQ K 5)
(INCR K)
(CHECK K 6)
(DECR K)
(CHECK K 5)

; PUSH/POP (place first)
(SETQ S NIL)
(PUSH S 'A)
(PUSH S 'B)
(CHECK S '(B A))
(CHECK (POP S) 'B)
(CHECK S '(A))

; FOR / WHILE summieren (bauen ihre Schleife als PROG)
(SETQ ACC 0)
(FOR I 1 5 (SETQ ACC (PLUS ACC I)))
(CHECK ACC 15)

(SETQ N 3)
(SETQ W 0)
(WHILE (GREATERP N 0) (SETQ W (ADD1 W)) (SETQ N (SUB1 N)))
(CHECK W 3)

; ---- Arrays (NTH ist 1-basiert: Index 1 = erstes Element) ----
(ARRAY V 0 5)
(STO V 9 2)
(CHECK (LOD V 2) 9)
(CHECK (LOD V 1) 0)
(ARRAY M 0 2 3)
(STO M 7 1 2)
(CHECK (LOD M 1 2) 7)
(CHECK (LOD M 1 1) 0)

; ---- Mengen ----
(CHECK (UNION '(A B) '(B C)) '(A B C))
(CHECK (INTERSECTION '(A B C) '(B C D)) '(B C))
(CHECK (SET-DIFFERENCE '(A B C) '(B)) '(A C))
(CHECK (SET-DIFFERENCE '(A B) '(A B)) NIL)
; MAKESET behaelt das LETZTE Vorkommen (Original-Semantik): (A A B A) -> (B A)
(CHECK (MAKESET '(A A B A)) '(B A))
(CHECK (SUBSETP '(A) '(A B)) T)
(CHECK (REMOVE 'B '(A B C B)) '(A C))

(CHECK-REPORT)
