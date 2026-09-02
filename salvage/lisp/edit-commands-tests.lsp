; Tests fuer lib-edit-commands (Kill/Yank, Wort-Bewegung, Suche).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;       lisp/edit-commands-tests.lsp

; Buffer aus Strings bauen.
(defun ed-from (strs row col) (mk-ed (mapcar (quote str->line) strs) row col))
(defun row1 (s) (line->str (cur-line s)))     ; aktuelle Zeile als String

; ---- Wort-Bewegung ----
; "foo bar baz", Cursor 0 -> forward-word ans Ende von "foo" (Spalte 3).
(check (ed-col (ed-forward-word (ed-from (list "foo bar baz") 0 0))) 3)
; aus Wortmitte/Leerzeichen: Spalte 3 -> ueberspringt " ", Ende "bar" = 7.
(check (ed-col (ed-forward-word (ed-from (list "foo bar baz") 0 3))) 7)
; backward-word: Spalte 7 (Ende "bar") -> Wortanfang "bar" = 4.
(check (ed-col (ed-backward-word (ed-from (list "foo bar baz") 0 7))) 4)
; backward-word aus Wortanfang heraus -> voriges Wort.
(check (ed-col (ed-backward-word (ed-from (list "foo bar baz") 0 4))) 0)

; ---- Kill-to-eol + Yank (Round-Trip) ----
(setq *k* (ed-kill-to-eol (ed-from (list "hello world") 0 6)))
(check (cdr *k*) "world")                       ; gekillter Text
(check (row1 (car *k*)) "hello ")               ; Zeile gekuerzt
; an den Anfang und zuruueck-yanken:
(check (row1 (ed-yank (ed-home (car *k*)) (cdr *k*))) "worldhello ")
; Cursor steht hinter dem eingefuegten Text.
(check (ed-col (ed-yank (ed-home (car *k*)) (cdr *k*))) 5)

; ---- Kill-word ----
(setq *w* (ed-kill-word (ed-from (list "foo bar") 0 0)))
(check (cdr *w*) "foo")
(check (row1 (car *w*)) " bar")

; ---- Naive Vorwaerts-Suche ----
; "abc def abc", Cursor 0 -> naechstes "abc" NACH Cursor = Spalte 8.
(setq *s1* (ed-search-forward (ed-from (list "abc def abc") 0 0) "abc"))
(check (ed-row *s1*) 0)
(check (ed-col *s1*) 8)
; ueber Zeilengrenze: Treffer in Zeile 1.
(setq *s2* (ed-search-forward (ed-from (list "alpha" "beta gamma") 0 0) "gamma"))
(check (ed-row *s2*) 1)
(check (ed-col *s2*) 5)
; kein Treffer -> Zustand unveraendert.
(setq *s3* (ed-search-forward (ed-from (list "abc") 0 0) "xyz"))
(check (ed-row *s3*) 0)
(check (ed-col *s3*) 0)

(check-report)
