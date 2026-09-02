; Tests fuer String-/Symbol-/Property-Builtins (Handbuch-Semantik).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/string-symbol-tests.lsp

; ---- ASC / CHAR ----
(CHECK (ASC "A") 65)
(CHECK (CHAR 65) "A")

; ---- PACK / UNPACK ----
(CHECK (PACK '(A B C D)) 'ABCD)
(CHECK (PACK '("TE" "ST" 44)) "TEST44")   ; mit String-Anteil -> String
(CHECK (UNPACK 'ABCD) '(A B C D))
(CHECK (UNPACK "A4") '("A" "4"))

; ---- Properties / Definitionen ----
(PUTPROP 'AUTO 'BAUJAHR 1982)
(CHECK (GETPROPLIST 'AUTO) '(BAUJAHR 1982))

(DE TST (X Y) (CONS X Y))
(CHECK (GETDEF TST) '(DE TST (X Y) (CONS X Y)))   ; GETDEF rekonstruiert die Form

(DF FST L (CAR L))
(CHECK (GETDEF FST) '(DF FST L (CAR L)))

; ---- PRINL (Seiteneffekt, liefert NIL) ----
(CHECK (PRINL '(A (B C) D)) NIL)

(CHECK-REPORT)
