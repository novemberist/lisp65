; Tests fuer lib-buffers (Multi-Buffer, Modeline, Minibuffer).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-buffers.lsp \
;       lisp/buffers-tests.lsp

(defun ed-from (strs row col) (mk-ed (mapcar (quote str->line) strs) row col))

; ---- String-Helfer ----
(check (cat (list "ab" "cd" "e")) "abcde")
(check (int->str 0) "0")
(check (int->str 7) "7")
(check (int->str 42) "42")
(check (int->str 305) "305")
(check (pad-right "hi" 5) "hi   ")

; ---- Buffer-Set aufbauen ----
(setq *bs* (bs-add (bs-mk () "") "scratch" (ed-from (list "()") 0 0)))
(setq *bs* (bs-add *bs* "main.lsp" (ed-from (list "(de f (x) x)") 0 4)))
(check (bs-current-name *bs*) "main.lsp")          ; add macht aktuell
(check (bs-names *bs*) (list "scratch" "main.lsp"))

; ---- Wechsel (C-x b) ----
(check (bs-current-name (bs-switch *bs* "scratch")) "scratch")
(check (bs-current-name (bs-switch *bs* "fehlt")) "main.lsp")   ; unbekannt -> unveraendert

; ---- Zyklus (wrap) ----
(check (bs-current-name (bs-next *bs*)) "scratch")             ; main.lsp -> scratch
(check (bs-current-name (bs-next (bs-switch *bs* "scratch"))) "main.lsp")

; ---- ED aktualisieren markiert MODIFIED ----
(check (buf-modified (bs-current *bs*)) ())                    ; frisch: nicht modifiziert
(setq *bs2* (bs-update-ed *bs* (ed-from (list "(de f (x) (g x))") 0 4)))
(check (buf-modified (bs-current *bs2*)) t)
(check (ed-col (bs-current-ed *bs2*)) 4)
; bs-move-ed: reine Bewegung laesst MODIFIED unveraendert.
(check (buf-modified (bs-current (bs-move-ed *bs* (ed-from (list "x") 0 1)))) ())
(check (buf-modified (bs-current (bs-move-ed *bs2* (ed-from (list "x") 0 1)))) t)

; ---- Modeline ----
(check (modeline *bs*) "-- main.lsp   (0,4)")                  ; unmodifiziert
(check (modeline *bs2*) "-- main.lsp * (0,4)")                 ; modifiziert

; ---- Buffer schliessen ----
(setq *bsk* (bs-kill *bs* "main.lsp"))
(check (bs-names *bsk*) (list "scratch"))
(check (bs-current-name *bsk*) "scratch")                      ; aktueller war zu -> erster Rest
(check (bs-current-name (bs-kill *bsk* "scratch")) "")         ; letzter zu -> leer

; ---- Minibuffer ----
(setq *mb* (mb-mk "Switch to buffer: "))
(setq *mb* (mb-insert *mb* "m"))
(setq *mb* (mb-insert *mb* "a"))
(setq *mb* (mb-insert *mb* "i"))
(check (mb-text *mb*) "mai")
(check (mb-render *mb*) "Switch to buffer: mai")
(check (mb-text (mb-backspace *mb*)) "ma")
; Einfuegen in der Mitte (Cursor nach 2x backspace bei col 1):
(setq *mb2* (mb-insert (list "P: " "ac" 1) "b"))
(check (mb-text *mb2*) "abc")

(check-report)
