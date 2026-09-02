; lib-seq NATIVE-SMOKE -- minimaler, host-verifizierter Fixture-Satz fuer den
; ersten Stufe-3-Portierungs-Smoke (GENSYM-FREI, kein DM, reine Funktionen).
;
; Zweck: NICHT die Voll-Suite (lisp/seq-tests.lsp), sondern die KLEINSTE Auswahl,
; die die nativen Abhaengigkeiten je einmal trifft -- als Vorlage fuer einen
; fokussierten On-C64-Smoke unter $D000. Jeder CHECK ist host-gruen; der erwartete
; Wert ist damit maschinell belegt, nicht handgerechnet.
; Mapping Fixture -> native Abhaengigkeit: docs/phase6-stufe3-native-smoke-spec.md
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/lib-seq.lsp lisp/seq-native-smoke.lsp

(DE POSP (X) (GREATERP X 0))

; PRIMARY: FUNCALL-Praedikat + Rekursion + CONS-Aufbau in EINER Form.
(CHECK (SORT (QUOTE (3 1 2)) (QUOTE LESSP)) (QUOTE (1 2 3)))

; FUNCALL eines per QUOTE uebergebenen Praedikat-Symbols (FIND-IF-Pfad).
(CHECK (FIND-IF (QUOTE POSP) (QUOTE (-1 2 3))) 2)

; Arithmetik (DIFFERENCE/SUB1/ZEROP) + CAR/CDR-Walk, OHNE FUNCALL.
(CHECK (SUBSEQ (QUOTE (A B C D)) 1 3) (QUOTE (B C)))

; EQL-basierte Mitgliedschaft (REMOVE-DUPLICATES, behaelt erstes Vorkommen).
(CHECK (REMOVE-DUPLICATES (QUOTE (A B A C))) (QUOTE (A B C)))
(CHECK (REMOVE-DUPLICATES (QUOTE ((A) (A) (B)))) (QUOTE ((A) (A) (B))))

(CHECK-REPORT)
