; Tests fuer lib-paredit (Paredit-Subset, Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp \
;       lisp/paredit-tests.lsp
;
; Helfer: src = (unpack "..."), Ergebnis zurueck mit (pack ...). Cursor = Index.

(defun pe (op s pos) (pack (funcall op (unpack s) pos)))

; ---- forward-sexp / backward-sexp (Cursor-Index) ----
(check (sx-fwd (unpack "foo bar") 0) 3)          ; hinter "foo"
(check (sx-fwd (unpack "  foo") 0) 5)            ; ueberspringt fuehrendes WS
(check (sx-fwd (unpack "(a (b) c) x") 0) 9)      ; hinter ganze Liste
(check (sx-bwd (unpack "(a b c)") 7) 0)          ; vom Ende an den Listenanfang
(check (sx-bwd (unpack "foo bar") 7) 4)          ; an den Anfang von "bar"

; ---- slurp-forward ----
(check (pe (quote slurp-forward) "(a b) c" 2) "(a b c)")
(check (pe (quote slurp-forward) "(foo) bar baz" 1) "(foo bar) baz")
(check (pe (quote slurp-forward) "(a) b" 1) "(a b)")
(check (pe (quote slurp-forward) "(a b)" 2) "(a b)")    ; nichts zu slurpen -> unveraendert

; ---- barf-forward ----
(check (pe (quote barf-forward) "(a b c)" 2) "(a b) c")
(check (pe (quote barf-forward) "(foo bar)" 1) "(foo) bar")

; ---- wrap-round ----
(check (pe (quote wrap-round) "foo bar" 0) "(foo) bar")
(check (pe (quote wrap-round) "a (b c) d" 2) "a ((b c)) d")  ; huellt die Liste

; ---- splice ----
(check (pe (quote splice) "(a (b c) d)" 4) "(a b c d)")   ; Cursor in innerer Liste
(check (pe (quote splice) "(a b c)" 3) "a b c")           ; aeussere Liste

; ---- string-/kommentar-bewusst: Klammern in "..." und ; zaehlen nicht ----
; String via (dq) bauen (Reader kennt keine Escapes): " a ) b " <space> x
; -> die ) im String darf den Form-Scan nicht beenden.
(check (sx-fwd (append (cons (dq) (unpack "a)b")) (cons (dq) (unpack " x"))) 0) 5)
; ) in einem ;-Kommentar darf die Liste nicht schliessen (mehrzeilig):
(check (sx-fwd (unpack "(a ; )
 b)") 0) 10)

; ---- mehrzeilig (Zeilenumbruch im Form-Scan) ----
(check (sx-fwd (unpack "(a
b)") 0) 5)                                                 ; Liste ueber Zeilengrenze

(check-report)
