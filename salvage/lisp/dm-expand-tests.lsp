; DM-Expand-Smoke (host-gepinnt) -- die Stufe-3-Portierungs-Voraussetzung.
;
; Der Stufe-3-Portierungs-Audit (docs/phase6-stufe3-port-audit.md) setzt voraus,
; dass DM-Makros auf dem nativen System expandieren. Dieser Test pinnt die
; DM-Mechanik mit MINIMALEN Faellen, die genau die von lib-loop/lib-struct/
; lib-clos genutzten Muster treffen. Die einfachen Faelle (DOUBLE, HSQ) doppeln
; als Spec fuer einen nativen DM-Expand-Smoke (s. Audit-Doc, Abschnitt
; "DM-Expand-Smoke").
;
; DM = MACRO: das eine Formal (L) ist an die GANZE Aufrufform gebunden,
; (CADR L) = 1. Argument-FORM (unausgewertet); die zurueckgegebene Expansion
; wird ausgewertet. (docs/dialect-vs-cl.md)
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/dm-expand-tests.lsp

; ---- 1. Einfache Expansion (DM ohne Hygiene) ----
(DM DOUBLE L (LIST (QUOTE PLUS) (CADR L) (CADR L)))
(check (DOUBLE 21) 42)

; ---- 2. Argument-FORM wird eingesetzt, dann ausgewertet ----
(DM SQ L (LIST (QUOTE TIMES) (CADR L) (CADR L)))
(check (SQ 7) 49)
(check (SQ (PLUS 1 2)) 9)            ; (TIMES (PLUS 1 2) (PLUS 1 2)) = 9

; ---- 3. Expansionszeit-Auswertung (FOR/REPEAT-Muster: Grenze als Konstante) ----
; (CADR L) ist hier eine ZAHL -> zur Expansionszeit ausgerechnet und gebacken.
(DM PRECOMP L (LIST (QUOTE QUOTE) (TIMES (CADR L) (CADR L))))
(check (PRECOMP 6) 36)

; ---- 4. Hygiene via GENSYM (das lib-loop/lib-clos-Muster) ----
; HSQ wertet sein Argument einmal in einen gensym'ten Temp aus -> kein Capture.
(DM HSQ L
  ((LAMBDA (G)
     (LIST (QUOTE PROG) (LIST G)
           (LIST (QUOTE SETQ) G (CADR L))
           (LIST (QUOTE RETURN) (LIST (QUOTE TIMES) G G))))
   (GENSYM)))
(check (HSQ 8) 64)
; Hygiene konkret: ein Aufrufer-G stoert nicht (gensym'ter Temp != G).
(SETQ G 99)
(check (HSQ 5) 25)
(check G 99)                         ; HSQ hat das aeussere G nicht angefasst

; ---- 5. Verschachtelte Expansion (Makro expandiert zu Makro-Aufruf) ----
(DM QUAD L (LIST (QUOTE DOUBLE) (LIST (QUOTE DOUBLE) (CADR L))))
(check (QUAD 5) 20)                  ; DOUBLE(DOUBLE(5)) = 20

(check-report)
