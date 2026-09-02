; lib-ide-undo -- Undo/Redo-Ring fuer die IDE-Befehlsschicht (Phase-8-Vorarbeit).
;
; Letzter Lisp-Schicht-Baustein (docs/onboard-ide.md Feature-Matrix: "Kill/Yank,
; ... Single-Register ... Undo-Ring"). Liegt als App-Schicht UEBER lib-ide-session
; (ide-dispatch) -- der Session-Zustand selbst bleibt unveraendert.
;
; Ein Undo-Punkt entsteht nur bei echter INHALTSAENDERUNG; reine Cursor-Bewegung,
; Buffer-Wechsel und Minibuffer-Tippen erzeugen keinen (Vergleich ueber den
; Buffer-Inhalt, nicht die Cursorposition). Produktiv waere statt des
; equal-Vergleichs ein billiger Aenderungs-Zaehler -- fuer den Prototyp genuegt
; der Inhaltsvergleich.
;
; Setzt voraus: editor-core, lib-edit-commands, lib-buffers, lib-ide-session.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp \
;   lisp/ide-undo-tests.lsp

; ---- Inhalts-Signatur eines Buffer-Sets (ohne Cursor/MODIFIED) ----
(defun buf-content (b) (cons (buf-name b) (ed-lines (buf-ed b))))
(defun bs-content (bs) (mapcar (quote buf-content) (bs-buffers bs)))

; ---- App = (SESSION UNDO REDO) ; UNDO/REDO = Listen vergangener Sessions ----
(defun app-mk (session undo redo) (list session undo redo))
(defun app-session (a) (car a))
(defun app-undo-stack (a) (car (cdr a)))
(defun app-redo-stack (a) (car (cdr (cdr a))))
(defun app-new (session) (app-mk session () ()))

; Ein Token verarbeiten: Session weiterreichen; bei Inhaltsaenderung alte
; Session auf den Undo-Ring legen und Redo leeren.
(defun app-step (a key)
  (let ((old (app-session a)))
    (let ((new (ide-dispatch old key)))
      (cond ((equal (bs-content (ss-bs new)) (bs-content (ss-bs old)))
             (app-mk new (app-undo-stack a) (app-redo-stack a)))
            (t (app-mk new (cons old (app-undo-stack a)) ()))))))

(defun app-undo (a)
  (cond ((null (app-undo-stack a)) a)
        (t (app-mk (car (app-undo-stack a))
                   (cdr (app-undo-stack a))
                   (cons (app-session a) (app-redo-stack a))))))
(defun app-redo (a)
  (cond ((null (app-redo-stack a)) a)
        (t (app-mk (car (app-redo-stack a))
                   (cons (app-session a) (app-undo-stack a))
                   (cdr (app-redo-stack a))))))

; ---- Dispatch inkl. Undo/Redo-Tasten (nicht im Minibuffer) ----
(defun undo-key-p (key) (cond ((equal key "C-/") t) ((equal key "C-x-u") t) (t ())))
(defun redo-key-p (key) (equal key "C-_"))
(defun app-dispatch (a key)
  (cond ((ss-mb-active (app-session a)) (app-step a key))   ; im Minibuffer: kein Undo
        ((undo-key-p key) (app-undo a))
        ((redo-key-p key) (app-redo a))
        (t (app-step a key))))
(defun app-run (a keys)
  (cond ((null keys) a) (t (app-run (app-dispatch a (car keys)) (cdr keys)))))
