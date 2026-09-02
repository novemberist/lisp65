; Pinning-Tests: nageln das AKTUELLE LISP-64-Dialektverhalten fest, das von
; Common Lisp ABWEICHT. Diese Tests sind ABSICHTLICH nicht CL-konform -- sie
; machen die Divergenzen sichtbar und fangen unbeabsichtigte Aenderungen ab.
; Wenn Phase 6 Stufe 2 (P2) den CL-konformen Schnitt macht, MUESSEN sie sich
; aendern. Referenz/Begruendung: docs/dialect-vs-cl.md.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/dialect-vs-cl-tests.lsp

; ---- LAST: liefert das letzte ELEMENT (CL: den letzten Cons (3)) ----
(CHECK (LAST '(1 2 3)) 3)
(CHECK (LAST '(A)) 'A)

; ---- NTH: (NTH liste n), 1-basiert, liefert die TEILLISTE ab Position n ----
; CL ist (NTH n liste): nulltes Element 0-basiert. Hier umgekehrte Argumente,
; 1-basiert, und Rueckgabe der Restliste statt des Elements.
(CHECK (NTH '(A B C D) 1) '(A B C D))
(CHECK (NTH '(A B C D) 2) '(B C D))
(CHECK (NTH '(A B C D) 3) '(C D))
(CHECK (CAR (NTH '(A B C D) 2)) 'B)        ; Element n erhaelt man via CAR

; ---- MOD = REMAINDER (Vorzeichen des Dividenden) ----
; CL: (MOD -7 3) = 2 (Vorzeichen des Divisors), (REM -7 3) = -1.
; Dialekt: MOD ist REMAINDER -> -1. cl-compat REM ist konsistent dazu definiert.
(CHECK (MOD -7 3) -1)
(CHECK (REMAINDER -7 3) -1)
(CHECK (REM -7 3) -1)

; ---- Multiplikation ist TIMES ----
; '*' ist im Dialekt das Kommentarzeichen, KEINE Multiplikation (CL: '*' = mal).
(CHECK (TIMES 2 3) 6)

; ---- Subtraktion = DIFFERENCE (binaer); MINUS = unaere Negation ----
; CL: '-' ist beides. Dialekt: getrennte Operatoren -> haeufige Stolperfalle.
(CHECK (DIFFERENCE 10 4) 6)
(CHECK (MINUS 7) -7)
(CHECK (MINUS 10 4) -10)     ; MINUS ist unaer: negiert das erste Arg, ignoriert Rest

(CHECK-REPORT)
