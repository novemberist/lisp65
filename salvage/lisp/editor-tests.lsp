; Tests fuer editor-core (Editor-Logik-Schicht, Phase-8-Vorarbeit).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/editor-tests.lsp

; ---- Insert / Cursor / Render ----
(let* ((s (mk-ed (list ()) 0 0))
       (s (ed-insert s "a"))
       (s (ed-insert s "b"))
       (s (ed-insert s "c")))
  (check (ed-render s) (list "abc"))
  (check (ed-col s) 3)
  (let* ((s (ed-left s)) (s (ed-insert s "X")))
    (check (ed-render s) (list "abXc"))))

; ---- Newline (Zeile splitten) ----
(let* ((s (mk-ed (list (str->line "abcd")) 0 2))
       (s (ed-newline s)))
  (check (ed-render s) (list "ab" "cd"))
  (check (ed-row s) 1)
  (check (ed-col s) 0))

; ---- Backspace mit Zeilen-Join ----
(let* ((s (mk-ed (list (str->line "ab") (str->line "cd")) 1 0))
       (s (ed-backspace s)))
  (check (ed-render s) (list "abcd"))
  (check (ed-row s) 0)
  (check (ed-col s) 2))

; ---- Auto-Einrueckung (Klammertiefe vor Cursor) ----
(let* ((s (mk-ed (list (str->line "(a (b")) 0 5)))
  (check (ed-indent-level s) 2))
(let* ((s (mk-ed (list (str->line "(defun f ()") (str->line "")) 1 0)))
  (check (ed-indent-level s) 1))

; ---- Klammer-Matching innerhalb einer Zeile ----
(let ((line (str->line "(a (b) c)")))
  (check (paren-match-line line 0) 8)     ; aeussere ( -> )
  (check (paren-match-line line 3) 5)     ; innere  ( -> )
  (check (paren-match-line line 8) 0)     ; )  -> aeussere (
  (check (paren-match-line line 1) ()))   ; kein Paren -> NIL

; ---- Keymap-Dispatch (Taste -> Kommando) ----
(let ((km (list (cons "R" (quote ed-right))
                (cons "L" (quote ed-left))
                (cons "E" (quote ed-end)))))
  (let* ((s (mk-ed (list (str->line "abc")) 0 0))
         (s (ed-dispatch km "R" s)))      ; ein Schritt nach rechts
    (check (ed-col s) 1)
    (let ((s (ed-dispatch km "E" s)))     ; ans Zeilenende
      (check (ed-col s) 3))
    (let ((s (ed-dispatch km "Z" s)))     ; unbekannte Taste -> unveraendert
      (check (ed-col s) 1))))

; ---- Syntax-Highlight-Klassifizierer ----
; Zeile (+ 1"h") -- Double-Quotes via (dq), da der Reader keine Escapes kennt.
(check (classify (list "(" "+" " " "1" (dq) "h" (dq) ")"))
       (list 'paren 'symbol 'space 'number 'string 'string 'string 'paren))
; Zeilenkommentar
(check (classify (list "a" ";" "b" "c"))
       (list 'symbol 'comment 'comment 'comment))

(check-report)
