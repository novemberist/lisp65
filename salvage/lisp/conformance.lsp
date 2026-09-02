; LISP 64 -- CL-Subset-Konformitaetssuite
;
; Ausfuehrbare Definition des garantierten Sprachumfangs. Nutzt CHECK aus
; prelude.lsp. Auf dem Host:  python3 tools/host-lisp/lisp64.py \
;   lisp/prelude.lsp lisp/conformance.lsp
; (CHECK-REPORT) am Ende meldet PASS/FAIL.
;
; Spaeter soll dieselbe Datei unveraendert auf dem echten C64 laufen.

; ---- Kern-Listenoperationen ----
(CHECK (CAR '(A B C)) 'A)
(CHECK (CDR '(A B C)) '(B C))
(CHECK (CONS 'A '(B)) '(A B))
(CHECK (CADR '(A B C)) 'B)
(CHECK (LENGTH '(A B C D)) 4)
(CHECK (REVERSE '(A B C)) '(C B A))
(CHECK (APPEND '(A B) '(C D)) '(A B C D))
(CHECK (LAST '(A B C)) 'C)   ; Dialekt-LAST = letztes ELEMENT, nicht letzte Cons
(CHECK (MEMBER 'B '(A B C)) '(B C))
(CHECK (ASSOC 'B '((A . 1) (B . 2))) '(B . 2))   ; ASSOC: EQ-Vergleich
(CHECK (NTH '(A B C D) 3) '(C D))                ; NTH 1-basiert: ab 3. Element
(CHECK (SASSOC '(A B) '(((A B) . 1))) '((A B) . 1))  ; SASSOC: EQUAL-Vergleich
(CHECK (MAPLIST 'CAR '(A B C)) '(A B C))         ; MAPLIST ueber Teil-Listen

; ---- Praedikate / Gleichheit ----
(CHECK (ATOM 'X) T)
(CHECK (ATOM '(X)) NIL)
(CHECK (NULL NIL) T)
(CHECK (EQ 'A 'A) T)
(CHECK (EQL 'A 'A) T)
(CHECK (EQL 4 4) T)
(CHECK (EQL '(A) '(A)) NIL)
(CHECK (EQUAL '(A (B)) '(A (B))) T)
(CHECK (NUMBERP 42) T)
(CHECK (CONSP '(A)) T)

; ---- Arithmetik (Original-Primitive) ----
(CHECK (PLUS 1 2 3) 6)
(CHECK (DIFFERENCE 10 3) 7)
(CHECK (TIMES 4 5) 20)
(CHECK (QUOTIENT 17 5) 3)
(CHECK (REMAINDER 17 5) 2)
(CHECK (ADD1 9) 10)
(CHECK (ABS (MINUS 7)) 7)
(CHECK (LESSP 2 3) T)
(CHECK (GREATERP 2 3) NIL)

; ---- Prelude: CL-Aliase ----
(CHECK (+ 1 2 3) 6)
(CHECK (- 10 3 2) 5)
(CHECK (TIMES 2 3 4) 24)        ; '*' ist Kommentar, nicht Multiplikation
(CHECK (* DIES IST EIN KOMMENTAR) NIL)   ; (* ...) wird ignoriert
(CHECK (/ 20 4) 5)
(CHECK (1+ 41) 42)
(CHECK (1- 1) 0)
(CHECK (< 1 2) T)
(CHECK (>= 3 3) T)
(CHECK (FIRST '(A B C)) 'A)
(CHECK (REST '(A B C)) '(B C))
(CHECK (SECOND '(A B C)) 'B)
(CHECK (EVENP 4) T)
(CHECK (ODDP 4) NIL)

; ---- Kontrollfluss ----
(CHECK (COND ((EQ 1 2) 'NO) (T 'YES)) 'YES)
(CHECK (AND 1 2 3) 3)
(CHECK (AND 1 NIL 3) NIL)
(CHECK (OR NIL NIL 5) 5)
(CHECK (PROGN 1 2 3) 3)
(CHECK (WHEN T 'A 'B) 'B)
(CHECK (UNLESS NIL 'A 'B) 'B)
(CHECK (WHEN NIL 'A) NIL)

; ---- Benutzerfunktionen, Rekursion, PROG ----
(DE FACT (N) (COND ((ZEROP N) 1) (T (TIMES N (FACT (SUB1 N))))))
(CHECK (FACT 5) 120)

(DEFUN SQR (N) (TIMES N N))
(CHECK (SQR 9) 81)

(DE SUMTO (N)
  (PROG (ACC I)
    (SETQ ACC 0)
    (SETQ I 1)
   LOOP
    (COND ((GREATERP I N) (RETURN ACC)))
    (SETQ ACC (PLUS ACC I))
    (SETQ I (ADD1 I))
    (GO LOOP)))
(CHECK (SUMTO 10) 55)

; ---- MAPCAR / LAMBDA ----
(CHECK (MAPCAR '(LAMBDA (X) (TIMES X X)) '(1 2 3)) '(1 4 9))
(CHECK (MAPCAR 'SQR '(2 3 4)) '(4 9 16))

; ---- Property-Listen ----
(PUTPROP 'FOO 'BAR 99)
(CHECK (GETPROP 'FOO 'BAR) 99)
(REMPROP 'FOO 'BAR)
(CHECK (GETPROP 'FOO 'BAR) NIL)

; ---- Handbuch-bestaetigte Dialekt-Eigenheiten ----
(CHECK F NIL)                              ; F = vordefiniertes Falsch-Atom
(CHECK (COND (F 'YES) (T 'NO)) 'NO)        ; F ist falsch
(CHECK (REMOVE 'A '(A B A C A A D)) '(B C D))  ; REMOVE: alle Vorkommen
(CHECK (MEMBER '(X) '((Y) (X) (Z))) '((X) (Z)))  ; MEMBER nutzt EQUAL (nicht EQ)

; ---- Keyword-Literale (selbstauswertend) + GENSYM ----
(CHECK :FOO :FOO)                          ; Keyword wertet auf sich selbst aus
(CHECK (EQ :FOO :FOO) T)                    ; interniert -> identisch
(CHECK (EQ :FOO :BAR) NIL)
(CHECK (EQ (GENSYM) (GENSYM)) NIL)          ; jedes GENSYM ist frisch
(SETQ G (GENSYM)) (CHECK (EQ G G) T)

(CHECK-REPORT)
