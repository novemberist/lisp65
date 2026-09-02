; Tests fuer cl-compat.lsp. Lauf:
;   python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp lisp/cl-compat-tests.lsp

; ---- C*R / funcall ----
(CHECK (CADDR '(A B C D)) 'C)
(CHECK (CDDDR '(A B C D)) '(D))
(CHECK (CADDDR '(A B C D)) 'D)
(CHECK (FUNCALL 'ADD1 9) 10)
(CHECK (FUNCALL 'PLUS 1 2 3) 6)

; ---- CL-Begleiter zu den Fallen ----
(CHECK (NTHCDR 2 '(A B C D)) '(C D))    ; CL 0-basiert
(CHECK (CAR (NTHCDR 0 '(A B C))) 'A)    ; CL (nth 0 l) = A
(CHECK (LASTCONS '(A B C)) '(C))        ; CL last = letzte Cons
(CHECK (BUTLAST '(A B C)) '(A B))

; ---- Suchen / Filtern ----
(CHECK (FIND 'B '(A B C)) 'B)
(CHECK (FIND 'Z '(A B C)) NIL)
(CHECK (FIND '(B) '((A) (B) (C))) NIL)
(CHECK (POSITION 'C '(A B C D)) 2)
(CHECK (POSITION '(C) '((A) (B) (C) (D))) NIL)
(CHECK (REMOVE-IF 'ZEROP '(0 1 0 2 3)) '(1 2 3))
(CHECK (REMOVE-IF-NOT 'ZEROP '(0 1 0 2)) '(0 0))

; ---- incf / decf ----
(SETQ K 10)
(INCF K)
(CHECK K 11)
(DECF K)
(CHECK K 10)

; ---- let* (sequentiell) ----
(CHECK (LET* ((A 1) (B (ADD1 A))) (PLUS A B)) 3)

; ---- dotimes / dolist ----
(SETQ S 0)
(DOTIMES (I 5) (SETQ S (PLUS S I)))
(CHECK S 10)                              ; 0+1+2+3+4

(SETQ ACC NIL)
(DOLIST (X '(A B C)) (SETQ ACC (CONS X ACC)))
(CHECK ACC '(C B A))

; ---- setf-light ----
(SETQ P (CONS 1 2))
(SETF (CAR P) 9)
(CHECK (CAR P) 9)
(SETF (CDR P) 8)
(CHECK (CDR P) 8)
(SETF (GET 'AUTO 'YR) 1982)
(CHECK (GET 'AUTO 'YR) 1982)
(CHECK (GETPROP 'AUTO 'YR) 1982)
(SETQ Z 0)
(SETF Z 7)
(CHECK Z 7)

; ---- reduce / every / some / count ----
(CHECK (REDUCE '+ '(1 2 3 4)) 10)
(CHECK (REDUCE '(LAMBDA (A B) (TIMES A B)) '(2 3 4)) 24)
(CHECK (EVERY 'NUMBERP '(1 2 3)) T)
(CHECK (EVERY 'NUMBERP '(1 A 3)) NIL)
(CHECK (SOME 'ZEROP '(1 0 2)) T)
(CHECK (SOME 'ZEROP '(1 2 3)) NIL)
(CHECK (COUNT 'A '(A B A C A)) 3)
(CHECK (COUNT '(A) '((A) (B) (A))) 0)

; ---- CASE / ECASE ----
(CHECK (CASE 2 ((1) 'a) ((2) 'b) (T 'c)) 'b)        ; Listen-Schluessel
(CHECK (CASE 9 ((1) 'a) ((2) 'b) (T 'c)) 'c)        ; Default
(CHECK (CASE 'X (Y 'no) (X 'yes)) 'yes)             ; Atom-Schluessel (EQL)
(CHECK (CASE 3 ((1 2 3) 'lo) ((4 5 6) 'hi)) 'lo)    ; Mehrfach-Schluessel
(CHECK (CASE 7 ((1) 'a) (OTHERWISE 'd)) 'd)         ; OTHERWISE = Default
(CHECK (CASE 5 ((1) 'a)) NIL)                       ; kein Treffer, kein Default -> NIL
(CHECK (CASE 2 ((2) (SETQ CL-CASE-N 0) (1+ 40))) 41) ; mehrere Body-Formen
; Schluessel wird genau einmal ausgewertet:
(SETQ CL-CASE-CNT 0)
(DE CL-CASE-BUMP () (SETQ CL-CASE-CNT (1+ CL-CASE-CNT)) 2)
(CHECK (CASE (CL-CASE-BUMP) ((2) 'ok)) 'ok)
(CHECK CL-CASE-CNT 1)
; Verschachtelung (LAMBDA-gebunden, nicht marken-kollidierend):
(CHECK (CASE 1 ((1) (CASE 2 ((2) 'inner))) (T 'x)) 'inner)
(CHECK (ECASE 2 ((1) 'a) ((2) 'b)) 'b)

; ---- IDENTITY / GETF / ACONS / PAIRLIS ----
(CHECK (IDENTITY 42) 42)
(CHECK (GETF '(A 1 B 2 C 3) 'B) 2)
(CHECK (GETF '(A 1 B 2) 'Z) NIL)
(CHECK (ACONS 'K 9 '((X . 1))) '((K . 9) (X . 1)))
(CHECK (PAIRLIS '(A B) '(1 2) NIL) '((A . 1) (B . 2)))

; ---- Listen-Konstruktoren / Kopierer ----
(CHECK (COPY-LIST '(1 2 3)) '(1 2 3))
(CHECK (COPY-TREE '(1 (2 3) 4)) '(1 (2 3) 4))
(CHECK (COPY-ALIST '((A . 1) (B . 2))) '((A . 1) (B . 2)))
(CHECK (REVAPPEND '(1 2 3) '(A B)) '(3 2 1 A B))
(CHECK (REVAPPEND NIL '(A)) '(A))
(CHECK (LIST* 1 2 '(3 4)) '(1 2 3 4))
(CHECK (LIST* 1 2 3) '(1 2 . 3))            ; dotted tail
(CHECK (LIST* 'A) 'A)
(CHECK (MAKE-LIST 3) '(NIL NIL NIL))
(CHECK (MAKE-LIST 0) NIL)
(CHECK (ADJOIN 1 '(2 3)) '(1 2 3))          ; nicht enthalten -> voranstellen
(CHECK (ADJOIN 2 '(2 3)) '(2 3))            ; enthalten -> unveraendert
(CHECK (SUBST 'X 'B '(A B (C B))) '(A X (C X)))
(CHECK (SUBST 9 9 5) 5)                      ; kein Treffer im Atom

; ---- Zahlen-Helfer ----
(CHECK (PLUSP 3) T)
(CHECK (PLUSP 0) NIL)
(CHECK (REM 7 3) 1)
(CHECK (SIGNUM -4) -1)
(CHECK (SIGNUM 0) 0)
(CHECK (SIGNUM 9) 1)
(CHECK (EXPT 2 10) 1024)
(CHECK (EXPT 5 0) 1)
(CHECK (MAX 3 1 4 1 5 9 2) 9)
(CHECK (MAX 7) 7)
(CHECK (MIN 3 1 4 1 5) 1)
(CHECK (GCD 12 8) 4)
(CHECK (GCD -12 8) 4)
(CHECK (LCM 4 6) 12)
(CHECK (LCM 0 5) 0)

; ---- Higher-order-Ergaenzungen ----
(CHECK (MAPCON 'LIST '(1 2)) '((1 2) (2)))
(CHECK (NOTANY 'ZEROP '(1 2 3)) T)
(CHECK (NOTANY 'ZEROP '(1 0 3)) NIL)
(CHECK (NOTEVERY 'ZEROP '(0 1 0)) T)
(CHECK (NOTEVERY 'ZEROP '(0 0)) NIL)
(CHECK (DELETE-IF 'ZEROP '(0 1 0 2)) '(1 2))

; ---- Typ-Praedikate / TYPEP / RASSOC ----
(CHECK (SYMBOLP 'A) T)
(CHECK (SYMBOLP NIL) T)
(CHECK (SYMBOLP 3) NIL)
(CHECK (SYMBOLP '(A)) NIL)
(CHECK (TYPEP 3 'NUMBER) T)
(CHECK (TYPEP 'A 'SYMBOL) T)
(CHECK (TYPEP '(1) 'CONS) T)
(CHECK (TYPEP NIL 'LIST) T)
(CHECK (TYPEP 3 'SYMBOL) NIL)
(CHECK (TYPEP 3 'FROB) NIL)                  ; unbekannter Typ -> NIL
(CHECK (RASSOC 2 '((A . 1) (B . 2))) '(B . 2))
(CHECK (RASSOC 9 '((A . 1))) NIL)

(CHECK-REPORT)
