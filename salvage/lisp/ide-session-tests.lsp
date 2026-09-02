; Tests fuer lib-ide-session (Keymap + Dispatch ueber Session-Zustand).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/ide-session-tests.lsp

(defun ed-from (strs row col) (mk-ed (mapcar (quote str->line) strs) row col))
(defun cur-str (s) (line->str (cur-line (ss-ed s))))   ; aktuelle Zeile als String

; Session mit zwei Buffern.
(defun mk-sess ()
  (ss-new (bs-add (bs-add (bs-mk () "") "scratch" (ed-from (list "") 0 0))
                  "main" (ed-from (list "hello world") 0 0))))

; ---- Self-insert (unbelegte druckbare Taste) ----
(setq *s* (ide-run (mk-sess) (list "X" "Y")))
(check (cur-str *s*) "XYhello world")
(check (ed-col (ss-ed *s*)) 2)
(check (buf-modified (bs-current (ss-bs *s*))) t)       ; Inhalt geaendert

; ---- Cursor-Bewegung markiert NICHT modifiziert ----
(setq *m* (ide-run (mk-sess) (list "C-e")))            ; ans Zeilenende
(check (ed-col (ss-ed *m*)) 11)
(check (buf-modified (bs-current (ss-bs *m*))) ())     ; Bewegung != Aenderung
(check (ed-col (ss-ed (ide-dispatch *m* "C-a"))) 0)
; Wort-Bewegung
(check (ed-col (ss-ed (ide-dispatch (mk-sess) "M-f"))) 5)

; ---- Kill-line + Yank (C-k, C-a, C-y) ----
; Cursor auf 6 (vor "world"): C-k killt "world", dann C-a, C-y fuegt es vorne ein.
(setq *k* (ide-run (ss-new (bs-add (bs-mk () "") "b" (ed-from (list "hello world") 0 6)))
                   (list "C-k" "C-a" "C-y")))
(check (ss-kill *k*) "world")
(check (cur-str *k*) "worldhello ")

; ---- C-x b: Minibuffer -> Buffer-Wechsel ----
(setq *b* (ide-dispatch (mk-sess) "C-x-b"))
(check (ss-mb-active *b*) t)                            ; Minibuffer offen
(check (mb-render (ss-mb *b*)) "Switch to buffer: ")
(setq *b* (ide-run *b* (list "s" "c" "r" "a" "t" "c" "h" "RET")))
(check (ss-mb-active *b*) ())                           ; geschlossen
(check (bs-current-name (ss-bs *b*)) "scratch")         ; gewechselt

; ---- C-g bricht den Minibuffer ab (kein Wechsel) ----
(setq *g* (ide-run (mk-sess) (list "C-x-b" "x" "C-g")))
(check (ss-mb-active *g*) ())
(check (bs-current-name (ss-bs *g*)) "main")            ; unveraendert

; ---- C-s: Suche ueber Minibuffer, Cursor bewegt, nicht modifiziert ----
(setq *f* (ide-run (mk-sess) (list "C-s" "w" "o" "r" "l" "d" "RET")))
(check (ed-col (ss-ed *f*)) 6)                          ; "world" ab Spalte 6
(check (buf-modified (bs-current (ss-bs *f*))) ())      ; Suche aendert nicht

; ---- Zyklischer Buffer-Wechsel ----
(check (bs-current-name (ss-bs (ide-dispatch (mk-sess) "C-x-RIGHT"))) "scratch")

(check-report)
