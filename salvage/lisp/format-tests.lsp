; Tests fuer das FORMAT-Subset (Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/format-tests.lsp
;
; FORMAT liefert hier einen String (wie CL (format nil ...)), damit Tests ihn
; per CHECK vergleichen koennen. Strings via (CHAR 34) gebaut, da der Reader
; keine Escapes kennt -- hier reichen einfache Literale.

; ---- ~A / ~S / ~D ----
(CHECK (FORMAT "Wert: ~A" 42) "Wert: 42")
(CHECK (FORMAT "~A und ~A" 'FOO 'BAR) "FOO und BAR")
; ~S lesbar (mit Quotes) -- erwarteten String via (CHAR 34) bauen (kein Escape)
(CHECK (FORMAT "~S" "hi") (PACK (LIST (CHAR 34) "hi" (CHAR 34))))
(CHECK (FORMAT "~A" "hi") "hi")              ; ~A aesthetisch (ohne Quotes)
(CHECK (FORMAT "n=~D" 17) "n=17")
(CHECK (FORMAT "~D" -5) "-5")

; ---- ~X (Hex) ----
(CHECK (FORMAT "~X" 255) "FF")
(CHECK (FORMAT "$~X" 4096) "$1000")

; ---- ~% (Zeilenumbruch) und ~~ (literale Tilde) ----
(CHECK (FORMAT "a~%b") "a
b")
(CHECK (FORMAT "100~~") "100~")

; ---- ~C (Zeichen) ----
(CHECK (FORMAT "~C~C" (CHAR 72) (CHAR 73)) "HI")

; ---- Mindestbreite-Padding ----
(CHECK (FORMAT "~5D" 42) "   42")           ; rechtsbuendig
(CHECK (FORMAT "~3D" 12345) "12345")        ; breiter als n -> unveraendert
(CHECK (FORMAT "~5A!" 'AB) "AB   !")        ; ~A linksbuendig
(CHECK (FORMAT "~4X" 255) "  FF")           ; ~X rechtsbuendig

; ---- Tabellen-artige Kombination ----
(CHECK (FORMAT "~5A~5D" 'X 7) "X        7")

(CHECK-REPORT)
