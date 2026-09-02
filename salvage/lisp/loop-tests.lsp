; Tests fuer das LOOP-Subset (Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;         lisp/lib-loop.lsp lisp/loop-tests.lsp

; ---- FOR ... IN ----
(CHECK (LOOP FOR X IN '(1 2 3) COLLECT (TIMES X X)) '(1 4 9))
(CHECK (LOOP FOR X IN '(1 2 3 4) SUM X) 10)
(CHECK (LOOP FOR X IN '(1 -1 2 -2 3) COUNT (GREATERP X 0)) 3)

; ---- FOR ... FROM ... TO [BY] ----
(CHECK (LOOP FOR I FROM 1 TO 5 SUM I) 15)
(CHECK (LOOP FOR I FROM 0 TO 10 BY 2 COLLECT I) '(0 2 4 6 8 10))
(CHECK (LOOP FOR I FROM 1 TO 4 COLLECT I) '(1 2 3 4))

; ---- REPEAT ----
(CHECK (LOOP REPEAT 3 COLLECT 'X) '(X X X))

; ---- WHILE / UNTIL ----
(CHECK (LOOP FOR X IN '(1 2 3 4 5) WHILE (LESSP X 4) COLLECT X) '(1 2 3))
(CHECK (LOOP FOR X IN '(1 2 3 4 5) UNTIL (GREATERP X 3) COLLECT X) '(1 2 3))

; ---- DO (Seiteneffekt) + Variable von aussen ----
(SETQ LACC-TEST 0)
(LOOP FOR X IN '(1 2 3) DO (SETQ LACC-TEST (PLUS LACC-TEST X)))
(CHECK LACC-TEST 6)

; ---- FINALLY mit eigenem RETURN ----
(CHECK (LOOP FOR I FROM 1 TO 3 DO (SETQ LACC-TEST I) FINALLY (RETURN (TIMES LACC-TEST 10))) 30)

; ---- DO + COLLECT kombiniert ----
(SETQ LACC-TEST 0)
(CHECK (LOOP FOR X IN '(10 20 30)
            DO (SETQ LACC-TEST (PLUS LACC-TEST 1))
            COLLECT X)
       '(10 20 30))
(CHECK LACC-TEST 3)

; ---- Schachtelung (dank GENSYM-Hygiene) ----
(CHECK (LOOP FOR I FROM 1 TO 3 COLLECT (LOOP FOR J FROM 1 TO I COLLECT J))
       '((1) (1 2) (1 2 3)))
(CHECK (LOOP FOR I FROM 1 TO 3 SUM (LOOP FOR J FROM 1 TO I SUM J))
       10)

(CHECK-REPORT)
