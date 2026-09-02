; Tests fuer lib-ide-undo (Undo/Redo-Ring ueber der Befehlsschicht).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp \
;   lisp/ide-undo-tests.lsp

(defun ed-from (strs row col) (mk-ed (mapcar (quote str->line) strs) row col))
(defun mk-app () (app-new (ss-new (bs-add (bs-mk () "") "b" (ed-from (list "") 0 0)))))
(defun app-line (a) (line->str (cur-line (ss-ed (app-session a)))))

; ---- Schrittweises Undo nach mehreren Einfuegungen ----
(setq *a* (app-run (mk-app) (list "a" "b" "c")))
(check (app-line *a*) "abc")
(setq *u1* (app-undo *a*))
(check (app-line *u1*) "ab")
(setq *u2* (app-undo *u1*))
(check (app-line *u2*) "a")
(check (app-line (app-undo *u2*)) "")             ; bis zum Anfang
(check (app-line (app-undo (app-undo *u2*))) "")  ; leerer Undo-Ring -> No-Op

; ---- Redo ----
(check (app-line (app-redo *u2*)) "ab")
(check (app-line (app-redo (app-redo *u2*))) "abc")
(check (app-line (app-redo *a*)) "abc")           ; leerer Redo-Ring -> No-Op

; ---- Cursor-Bewegung erzeugt KEINEN Undo-Punkt ----
(setq *m* (app-run (mk-app) (list "a" "C-a" "C-e")))   ; tippe a, dann bewege
(check (app-line (app-undo *m*)) "")                   ; ein Undo entfernt nur das "a"

; ---- Neue Aenderung nach Undo leert den Redo-Ring ----
(setq *r* (app-run (app-undo (app-run (mk-app) (list "a" "b"))) (list "z")))
(check (app-line *r*) "az")                            ; "ab" -> undo -> "a" -> "z"
(check (app-line (app-redo *r*)) "az")                 ; Redo wurde geleert -> No-Op

; ---- Undo/Redo ueber Tasten (C-/ und C-_) ----
(setq *k* (app-run (mk-app) (list "x" "y" "C-/")))     ; tippe xy, C-/ = undo
(check (app-line *k*) "x")
(check (app-line (app-dispatch *k* "C-_")) "xy")       ; C-_ = redo
; C-x u ist ebenfalls Undo
(check (app-line (app-dispatch (app-run (mk-app) (list "q" "w")) "C-x-u")) "q")

; ---- Buffer-Wechsel erzeugt keinen Undo-Punkt (Inhalt unveraendert) ----
(setq *bs2* (app-new (ss-new (bs-add (bs-add (bs-mk () "") "one" (ed-from (list "") 0 0))
                                     "two" (ed-from (list "") 0 0)))))
(setq *sw* (app-run *bs2* (list "C-x-RIGHT")))         ; nur Buffer-Wechsel
(check (app-undo-stack *sw*) ())                       ; kein Undo-Punkt

(check-report)
