; LISP 64 -- Demo-Algorithmen als Host-Testfaelle
;
; In Anlehnung an die Original-Samples perm.lsp, hanoi.lsp und symb-diff.lsp,
; aber zu REINEN, ergebnisliefernden Fassungen umgeschrieben (die Originale sind
; print-/zustandsgetrieben und eignen sich nicht direkt fuer CHECK). Sie ueben
; Rekursion, APPEND, MAPCAR und Listenaufbau breit aus.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/demos.lsp

; ===== Permutationen (funktional, in Anlehnung an perm.lsp) =====
(DE REMOVE-ONE (X L)
  (COND ((NULL L) NIL)
        ((EQUAL X (CAR L)) (CDR L))
        (T (CONS (CAR L) (REMOVE-ONE X (CDR L))))))

(DE PERMS (L)
  (COND ((NULL L) (LIST NIL))
        (T (PERM-EXPAND L L))))

(DE PERM-EXPAND (ELEMS L)
  (COND ((NULL ELEMS) NIL)
        (T (APPEND
             (MAPCAR '(LAMBDA (P) (CONS (CAR ELEMS) P))
                     (PERMS (REMOVE-ONE (CAR ELEMS) L)))
             (PERM-EXPAND (CDR ELEMS) L)))))

(CHECK (PERMS '(A)) '((A)))
(CHECK (PERMS '(1 2)) '((1 2) (2 1)))
(CHECK (LENGTH (PERMS '(1 2 3))) 6)
(CHECK (LENGTH (PERMS '(1 2 3 4))) 24)

; ===== Tuerme von Hanoi (funktional, in Anlehnung an hanoi.lsp) =====
(DE HANOI-MOVES (N FROM TO VIA)
  (COND ((ZEROP N) NIL)
        (T (APPEND
             (HANOI-MOVES (SUB1 N) FROM VIA TO)
             (LIST (LIST FROM TO))
             (HANOI-MOVES (SUB1 N) VIA TO FROM)))))

(CHECK (HANOI-MOVES 1 'A 'C 'B) '((A C)))
(CHECK (CAR (HANOI-MOVES 2 'A 'C 'B)) '(A B))
(CHECK (LENGTH (HANOI-MOVES 3 'A 'C 'B)) 7)
(CHECK (LENGTH (HANOI-MOVES 4 'A 'C 'B)) 15)

; ===== Symbolische Differentiation (kompakter Kern, in Anlehnung an symb-diff.lsp) =====
; Ausdruecke aus Zahlen, der Variablen X, (PLUS a b) und (TIMES a b).
(DE DIFF (E X)
  (COND ((NUMBERP E) 0)
        ((ATOM E) (COND ((EQ E X) 1) (T 0)))
        ((EQ (CAR E) 'PLUS)
         (LIST 'PLUS (DIFF (CADR E) X) (DIFF (CAR (CDDR E)) X)))
        ((EQ (CAR E) 'TIMES)
         (LIST 'PLUS
           (LIST 'TIMES (CADR E) (DIFF (CAR (CDDR E)) X))
           (LIST 'TIMES (DIFF (CADR E) X) (CAR (CDDR E)))))
        (T (ERROR '(UNKNOWN-TERM)))))

(CHECK (DIFF 'X 'X) 1)
(CHECK (DIFF '5 'X) 0)
(CHECK (DIFF '(PLUS X 5) 'X) '(PLUS 1 0))
(CHECK (DIFF '(TIMES X X) 'X) '(PLUS (TIMES X 1) (TIMES 1 X)))

(CHECK-REPORT)
