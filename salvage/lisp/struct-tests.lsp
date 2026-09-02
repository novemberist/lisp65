; Tests fuer DEFSTRUCT-light (Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;         lisp/lib-struct.lsp lisp/struct-tests.lsp

(DEFSTRUCT POINT X Y)

(SETQ P (MAKE-POINT :X 3 :Y 4))
(CHECK (POINT-P P) T)
(CHECK (POINT-X P) 3)
(CHECK (POINT-Y P) 4)

; Praedikat lehnt Nicht-Structs / falschen Tag ab
(CHECK (POINT-P 5) NIL)
(CHECK (POINT-P '(FOO 1 2)) NIL)

; Mutation via SETF (setf-faehiger Akzessor)
(SETF (POINT-X P) 10)
(CHECK (POINT-X P) 10)
(SETF (POINT-Y P) 20)
(CHECK (POINT-Y P) 20)

; Kopierer ist unabhaengig (flache Kopie)
(SETQ Q (COPY-POINT P))
(SETF (POINT-Y Q) 99)
(CHECK (POINT-Y P) 20)
(CHECK (POINT-Y Q) 99)

; Drei Slots, gemischte Typen
(DEFSTRUCT PERSON NAME AGE CITY)
(SETQ A (MAKE-PERSON :NAME 'ALICE :AGE 30 :CITY 'NYC))
(CHECK (PERSON-NAME A) 'ALICE)
; Keyword-Reihenfolge egal, fehlender Slot -> NIL
(SETQ A2 (MAKE-PERSON :CITY 'NYC :NAME 'BOB))
(CHECK (PERSON-NAME A2) 'BOB)
(CHECK (PERSON-AGE A2) NIL)
(CHECK (PERSON-AGE A) 30)
(CHECK (PERSON-CITY A) 'NYC)
(SETF (PERSON-CITY A) 'BOSTON)
(CHECK (PERSON-CITY A) 'BOSTON)
(CHECK (PERSON-NAME A) 'ALICE)
(CHECK (PERSON-P A) T)
(CHECK (POINT-P A) NIL)

(CHECK-REPORT)
