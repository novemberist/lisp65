; Tests fuer das Fehler-/Condition-Modell (Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/error-tests.lsp
; Modell: docs/error-model.md. (Break-Loop ist interaktiv -> hier nicht getestet.)

; ---- CATCH / THROW (nicht-lokaler Sprung, Tag per EQ) ----
(CHECK (CATCH :DONE 1 2 3) 3)                         ; ohne THROW: letzter Wert
(CHECK (CATCH :DONE (THROW :DONE 42) 99) 42)          ; THROW liefert Wert
(CHECK (CATCH :OUT (CATCH :IN (THROW :OUT 7)) 0) 7)   ; springt zum aeusseren Tag
; THROW mitten in Berechnung
(CHECK (CATCH :T (PLUS 1 (THROW :T 5))) 5)

; ---- UNWIND-PROTECT (Cleanup laeuft IMMER) ----
(SETQ CLEANED NIL)
(CHECK (UNWIND-PROTECT 10 (SETQ CLEANED T)) 10)       ; Normalfall
(CHECK CLEANED T)
; Cleanup laeuft auch beim Durch-Werfen
(SETQ CLEANED NIL)
(CHECK (CATCH :X (UNWIND-PROTECT (THROW :X 1) (SETQ CLEANED T))) 1)
(CHECK CLEANED T)

; ---- HANDLER-CASE (typ-dispatch) ----
(CHECK (HANDLER-CASE (PLUS 1 2) (ERROR (C) 'GEFANGEN)) 3)   ; kein Fehler -> Form
(CHECK (HANDLER-CASE (ERROR "kaputt") (ERROR (C) 'GEFANGEN)) 'GEFANGEN)
; Condition-Objekt inspizieren
(CHECK (HANDLER-CASE (ERROR "kaputt")
         (ERROR (C) (CONDITION-TYPE C)))
       'USER-ERROR)
(CHECK (HANDLER-CASE (ERROR "kaputt")
         (ERROR (C) (CONDITION-MESSAGE C)))
       "kaputt")
; Eigener Condition-Typ wird typgenau gefangen
(CHECK (HANDLER-CASE (ERROR 'TYPE-ERROR "x")
         (TYPE-ERROR (C) 'TYP)
         (ERROR (C) 'ALLG))
       'TYP)
; ERROR-Klausel faengt auch interne Fehler (unbound variable)
(CHECK (HANDLER-CASE NICHT-GEBUNDEN (ERROR (C) 'INTERN-GEFANGEN)) 'INTERN-GEFANGEN)

; ---- IGNORE-ERRORS ----
(CHECK (IGNORE-ERRORS (ERROR "egal")) NIL)
(CHECK (IGNORE-ERRORS 1 2 3) 3)

; ---- MAKE-CONDITION / SIGNAL ----
(CHECK (CONDITIONP (MAKE-CONDITION 'FOO-ERROR "msg")) T)
(CHECK (CONDITIONP 5) NIL)
(CHECK (HANDLER-CASE (SIGNAL (MAKE-CONDITION 'FOO-ERROR "m" 'DAT))
         (FOO-ERROR (C) (CONDITION-DATA C)))
       'DAT)

(CHECK-REPORT)
