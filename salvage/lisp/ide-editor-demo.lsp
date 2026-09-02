; IDE-EDITOR-DEMO -- vorfuehrbarer End-to-End-Editor im Host-Interpreter.
;
; Treibt den VOLLEN IDE-Stack (Tasten-Token -> app-dispatch -> compose-screen)
; gegen einen simulierten Bildschirm und RENDERT die Frames sichtbar, plus CHECK-
; Assertions an den Schluesselstellen (damit die Demo zugleich Regressionstest
; ist). Das ist der Phase-8-Integrations-Schlussstein als greifbarer Meilenstein
; -- on-HOST heute lauffaehig; on-C64 fehlt nur Lib-Laden + Screen/Keyboard-I/O
; (s. docs/phase8-ide-native-readiness-audit.md).
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp \
;   lisp/lib-ide-view.lsp lisp/ide-editor-demo.lsp

(defun demo-w () 22)        ; Bildschirmbreite
(defun demo-h () 7)         ; Hoehe: 5 Edit-Zeilen + Modeline + Minibuffer

; ---- kleine Render-Helfer ----
(defun putln (s) (princ s) (terpri))
(defun rep-list (x n) (cond ((< n 1) ()) (t (cons x (rep-list x (1- n))))))
(defun bar (n) (cat (rep-list "-" n)))
(defun demo-ed (strs) (mk-ed (mapcar (quote str->line) strs) 0 0))
(defun cline (app) (line->str (cur-line (ss-ed (app-session app)))))
(defun cname (app) (bs-current-name (ss-bs (app-session app))))

; Eine gerahmte Momentaufnahme: Label, Bildschirm in einem |...|-Rahmen,
; Cursor-Caret unter der aktuellen Spalte, plus (row,col).
(defun caret-line (app)
  (cat (append (rep-list " " (+ 1 (cursor-screen-col (app-session app))))
               (list "^"))))
(defun frame (app label)
  (putln (cat (list "== " label " ==")))
  (putln (cat (list "+" (bar (demo-w)) "+")))
  (frame-rows (compose-screen (app-session app) 0 (demo-h) (demo-w)))
  (putln (cat (list "+" (bar (demo-w)) "+")))
  (putln (caret-line app))
  (terpri))
(defun frame-rows (rows)
  (cond ((null rows) ())
        (t (putln (cat (list "|" (clip (car rows) (demo-w)) "|")))
           (frame-rows (cdr rows)))))

; ---- Start: zwei Buffer "main" (2 Zeilen) und "notes" (1 Zeile); "main" aktiv ----
(setq *app*
  (app-new (ss-new
    (bs-add (bs-add (bs-mk () "")
                    "notes" (demo-ed (list "todo: ship it")))
            "main"  (demo-ed (list "alpha" "beta"))))))

(frame *app* "Start (Buffer main)")
(check (cname *app*) "main")
(check (cline *app*) "alpha")

; ---- Self-Insert am Zeilenende: C-e, dann "!" ----
(setq *app* (app-run *app* (list "C-e" "!")))
(frame *app* "C-e ! -> alpha!")
(check (cline *app*) "alpha!")

; ---- Kill-Line + Yank: C-a C-k loescht die Zeile, C-y stellt sie wieder her ----
(setq *app* (app-run *app* (list "C-a" "C-k")))
(frame *app* "C-a C-k -> Zeile gekillt")
(check (cline *app*) "")
(setq *app* (app-run *app* (list "C-y")))
(frame *app* "C-y -> wieder eingefuegt")
(check (cline *app*) "alpha!")

; ---- Undo: C-/ macht das Yank rueckgaengig (Zeile wieder leer) ----
(setq *app* (app-dispatch *app* "C-/"))
(frame *app* "C-/ -> Undo (Zeile leer)")
(check (cline *app*) "")

; ---- Buffer-Wechsel ueber den Minibuffer: C-x-b zeigt Prompt ... ----
(setq *app* (app-dispatch *app* "C-x-b"))
(frame *app* "C-x-b -> Minibuffer-Prompt")
(check (nth-elem 6 (compose-screen (app-session *app*) 0 (demo-h) (demo-w)))
       (clip "Switch to buffer: " (demo-w)))

; ---- ... Namen tippen + RET wechselt zu "notes" ----
(setq *app* (app-run *app* (list "n" "o" "t" "e" "s" "RET")))
(frame *app* "notes RET -> Buffer notes")
(check (cname *app*) "notes")
(check (cline *app*) "todo: ship it")

(check-report)
