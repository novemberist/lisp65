; End-to-End-Integrationstest der IDE-Lisp-Schicht (Phase-8-Vorarbeit).
;
; Treibt den GESAMTEN Stack als Einheit -- editor-core + lib-edit-commands +
; lib-buffers + lib-ide-session + lib-ide-undo + lib-ide-view -- ueber eine
; realistische Edit-Session aus Tastentokens und prueft an Meilensteinen den
; komponierten Vollbild-Schirm und den Zustand. Das ist zugleich der
; ausfuehrbare Blueprint fuer die native Dispatch-Schleife:
;   Token -> app-dispatch -> compose-screen + (cursor-screen-row/col).
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp \
;   lisp/lib-ide-view.lsp lisp/ide-integration-tests.lsp

(defun ed1 (str) (mk-ed (list (str->line str)) 0 0))
; Zwei Buffer: "b" und "a"; aktuell "a" (zuletzt hinzugefuegt).
(defun mk-app2 ()
  (app-new (ss-new (bs-add (bs-add (bs-mk () "") "b" (ed1 "beta gamma"))
                           "a" (ed1 "alpha")))))
(defun line0 (app) (line->str (cur-line (ss-ed (app-session app)))))
(defun curname (app) (bs-current-name (ss-bs (app-session app))))
(defun scr (app) (compose-screen (app-session app) 0 4 16))

; ---- Startbild: 2 Edit-Zeilen + Modeline + (leerer) Minibuffer ----
(setq *a* (mk-app2))
(check (length (scr *a*)) 4)
(check (nth-elem 0 (scr *a*)) (clip "alpha" 16))
(check (nth-elem 2 (scr *a*)) (clip "-- a   (0,0)" 16))   ; Modeline, unmodifiziert
(check (nth-elem 3 (scr *a*)) (clip "" 16))               ; Minibuffer leer

; ---- Self-Insert am Zeilenende -> Inhalt + MODIFIED-Stern in der Modeline ----
(setq *a* (app-run *a* (list "C-e" "!")))
(check (line0 *a*) "alpha!")
(check (nth-elem 2 (scr *a*)) (clip "-- a * (0,6)" 16))

; ---- Buffer-Wechsel ueber den Minibuffer (C-x b, "b", RET) ----
(setq *a* (app-run *a* (list "C-x-b" "b" "RET")))
(check (curname *a*) "b")
(check (nth-elem 0 (scr *a*)) (clip "beta gamma" 16))     ; jetzt Buffer b sichtbar

; ---- Suche im Minibuffer (C-s, "gamma", RET) bewegt nur den Cursor ----
(setq *a* (app-run *a* (list "C-s" "g" "a" "m" "m" "a" "RET")))
(check (cursor-screen-col (app-session *a*)) 5)
(check (cursor-screen-row (app-session *a*) 0) 0)
(check (nth-elem 2 (scr *a*)) (clip "-- b   (0,5)" 16))   ; Suche aendert nicht -> kein Stern

; ---- Minibuffer-Render waehrend eines Prompts ----
(setq *p* (app-dispatch (mk-app2) "C-x-b"))
(check (nth-elem 3 (scr *p*)) (clip "Switch to buffer: " 16))
(setq *p* (app-run *p* (list "x" "y")))
(check (nth-elem 3 (scr *p*)) (clip "Switch to buffer: xy" 16))

; ---- Kill/Yank-Round-Trip ueber den App-Stack ----
(setq *k* (app-run (mk-app2) (list "C-a" "C-k")))         ; home, kill bis EOL
(check (line0 *k*) "")
(check (ss-kill (app-session *k*)) "alpha")
(setq *k* (app-dispatch *k* "C-y"))                       ; yank
(check (line0 *k*) "alpha")

; ---- Undo/Redo ueber den App-Stack ----
(setq *u* (app-run (mk-app2) (list "C-e" "X" "Y")))       ; "alphaXY" (2 Edits)
(check (line0 *u*) "alphaXY")
(setq *u* (app-dispatch *u* "C-/"))                       ; undo -> "alphaX"
(check (line0 *u*) "alphaX")
(setq *u* (app-dispatch *u* "C-/"))                       ; undo -> "alpha"
(check (line0 *u*) "alpha")
(check (line0 (app-dispatch *u* "C-_")) "alphaX")         ; redo -> "alphaX"

; ---- Cursor-Bewegung allein erzeugt KEINEN Undo-Punkt (Integration) ----
(setq *m* (app-run (mk-app2) (list "C-e" "C-a")))         ; ans Ende, zurueck nach Hause
(check (line0 (app-undo *m*)) "alpha")                    ; nichts rueckgaengig zu machen

(check-report)
