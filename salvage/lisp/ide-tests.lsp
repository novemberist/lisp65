; Tests fuer lib-ide (eval-defun + Paredit-Keymap).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp \
;       lisp/lib-ide.lsp lisp/ide-tests.lsp

; ---- Top-Level-Form finden ----
; Buffer: "(setq x 1) (plus x 40)" ; Cursor (Index 14) in der zweiten Form
(check (ed-toplevel-string (unpack "(setq x 1) (plus x 40)") 14) "(plus x 40)")
; Cursor in der ersten Form
(check (ed-toplevel-string (unpack "(setq x 1) (plus x 40)") 3) "(setq x 1)")

; ---- eval-defun: extrahieren -> read -> eval ----
(check (ed-eval-defun (unpack "(plus 1 2)") 3) 3)
; zwei Forms: erste setzt X, zweite nutzt sie (Cursor in der zweiten)
(progn
  (ed-eval-defun (unpack "(setq x 5) (plus x 40)") 2)        ; wertet (setq x 5)
  (check (ed-eval-defun (unpack "(setq x 5) (plus x 40)") 14) 45))

; ---- Keymap-Dispatch (SLIME/Paredit-Bindings als Daten) ----
; km-lookup findet das Kommando
(check (km-lookup "C-)" *ide-keymap*) (quote fb-slurp))
(check (km-lookup "nope" *ide-keymap*) ())

; ed-dispatch fuehrt slurp ueber die Taste C-) aus
(check (fb-chars (ed-dispatch *ide-keymap* "C-)" (fb-mk (unpack "(a b) c") 2)))
       (unpack "(a b c)"))
; forward-sexp bewegt den Cursor
(check (fb-pos (ed-dispatch *ide-keymap* "C-M-f" (fb-mk (unpack "(a b) c") 0))) 5)
; wrap ueber M-(
(check (fb-chars (ed-dispatch *ide-keymap* "M-(" (fb-mk (unpack "foo bar") 0)))
       (unpack "(foo) bar"))
; unbekannte Taste -> Zustand unveraendert
(check (fb-pos (ed-dispatch *ide-keymap* "xx" (fb-mk (unpack "abc") 1))) 1)

(check-report)
