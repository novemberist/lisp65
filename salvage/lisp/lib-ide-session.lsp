; lib-ide-session -- IDE-Befehlsschicht: Keymap + Dispatch (Phase-8-Vorarbeit).
;
; Bindet die prototypisierte Logik (editor-core, lib-edit-commands, lib-buffers)
; zu einer bedienbaren Befehlsschicht zusammen -- eine SLIME/Emacs-artige
; Keymap + Dispatch ueber einen Session-Zustand. Reine Logik (Zustand rein,
; Zustand raus); KEIN Rendering und kein Tastenscan -- die liefert der native
; ASM-Hot-Path als Token-Strom ("C-f", "a", "RET", "C-x-b", ...).
;
; Setzt voraus: editor-core, lib-edit-commands, lib-buffers.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;       lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/ide-session-tests.lsp

; ---- Session = (BS KILL MB ACTION) ----
; BS=Buffer-Set, KILL=Kill-Register (String), MB=Minibuffer-Zustand oder NIL,
; ACTION=ausstehende Minibuffer-Aktion (Symbol) oder NIL.
(defun ss-mk (bs kill mb action) (list bs kill mb action))
(defun ss-bs (s) (car s))
(defun ss-kill (s) (car (cdr s)))
(defun ss-mb (s) (car (cdr (cdr s))))
(defun ss-action (s) (car (cdr (cdr (cdr s)))))
(defun ss-new (bs) (ss-mk bs "" () ()))
(defun ss-set-bs (s bs) (ss-mk bs (ss-kill s) (ss-mb s) (ss-action s)))
(defun ss-ed (s) (bs-current-ed (ss-bs s)))         ; ED des aktuellen Buffers

; ---- Anwendung von ed-Funktionen auf den aktuellen Buffer ----
(defun ss-move (s f)                                  ; Cursor-Bewegung (kein MODIFIED)
  (ss-set-bs s (bs-move-ed (ss-bs s) (funcall f (ss-ed s)))))
(defun ss-edit (s f)                                  ; Inhaltsaenderung (MODIFIED)
  (ss-set-bs s (bs-update-ed (ss-bs s) (funcall f (ss-ed s)))))
(defun ss-kill-cmd (s f)                              ; f: ed -> (ed . gekillt)
  (let ((r (funcall f (ss-ed s))))
    (ss-mk (bs-update-ed (ss-bs s) (car r)) (cdr r) (ss-mb s) (ss-action s))))

; ---- Kommandos (Session -> Session) ----
(defun cmd-forward-char (s)  (ss-move s (quote ed-right)))
(defun cmd-backward-char (s) (ss-move s (quote ed-left)))
(defun cmd-home (s)          (ss-move s (quote ed-home)))
(defun cmd-end (s)           (ss-move s (quote ed-end)))
(defun cmd-forward-word (s)  (ss-move s (quote ed-forward-word)))
(defun cmd-backward-word (s) (ss-move s (quote ed-backward-word)))
(defun cmd-kill-line (s)     (ss-kill-cmd s (quote ed-kill-to-eol)))
(defun cmd-kill-word (s)     (ss-kill-cmd s (quote ed-kill-word)))
(defun cmd-newline (s)       (ss-edit s (quote ed-newline)))
(defun cmd-backspace (s)     (ss-edit s (quote ed-backspace)))
(defun cmd-yank (s)
  (ss-set-bs s (bs-update-ed (ss-bs s) (ed-yank (ss-ed s) (ss-kill s)))))
(defun cmd-next-buffer (s) (ss-set-bs s (bs-next (ss-bs s))))
(defun cmd-switch-buffer (s) (ss-start-mb s "Switch to buffer: " (quote switch-buffer)))
(defun cmd-search-forward (s) (ss-start-mb s "Search: " (quote search-forward)))

; ---- Default-Keymap (Token -> Kommando-Symbol) ----
(setq *ide-keymap*
  (list (cons "C-f" (quote cmd-forward-char))
        (cons "C-b" (quote cmd-backward-char))
        (cons "C-a" (quote cmd-home))
        (cons "C-e" (quote cmd-end))
        (cons "M-f" (quote cmd-forward-word))
        (cons "M-b" (quote cmd-backward-word))
        (cons "C-k" (quote cmd-kill-line))
        (cons "M-d" (quote cmd-kill-word))
        (cons "C-y" (quote cmd-yank))
        (cons "RET" (quote cmd-newline))
        (cons "DEL" (quote cmd-backspace))
        (cons "C-x-b" (quote cmd-switch-buffer))
        (cons "C-s" (quote cmd-search-forward))
        (cons "C-x-RIGHT" (quote cmd-next-buffer))))

; ---- Minibuffer-Modus ----
(defun printablep (key) (= (length (unpack key)) 1))   ; Token = einzelnes Zeichen
(defun ss-start-mb (s prompt action)
  (ss-mk (ss-bs s) (ss-kill s) (mb-mk prompt) action))
(defun ss-mb-active (s) (cond ((ss-mb s) t) (t ())))
(defun run-action (bs action text)
  (cond ((eq action (quote switch-buffer)) (bs-switch bs text))
        ((eq action (quote search-forward))
         (bs-move-ed bs (ed-search-forward (bs-current-ed bs) text)))
        (t bs)))
(defun ss-mb-confirm (s)
  (ss-mk (run-action (ss-bs s) (ss-action s) (mb-text (ss-mb s))) (ss-kill s) () ()))
(defun ss-mb-cancel (s) (ss-mk (ss-bs s) (ss-kill s) () ()))
(defun ss-mb-key (s key)
  (cond ((equal key "RET") (ss-mb-confirm s))
        ((equal key "C-g") (ss-mb-cancel s))
        ((equal key "DEL")
         (ss-mk (ss-bs s) (ss-kill s) (mb-backspace (ss-mb s)) (ss-action s)))
        ((printablep key)
         (ss-mk (ss-bs s) (ss-kill s) (mb-insert (ss-mb s) key) (ss-action s)))
        (t s)))

; ---- Haupt-Dispatch: ein Token -> neue Session ----
(defun ss-self-insert (s key)
  (ss-set-bs s (bs-update-ed (ss-bs s) (ed-insert (ss-ed s) key))))
(defun ide-dispatch (s key)
  (cond ((ss-mb-active s) (ss-mb-key s key))
        (t (let ((cmd (km-lookup key *ide-keymap*)))
             (cond (cmd (funcall cmd s))
                   ((printablep key) (ss-self-insert s key))
                   (t s))))))

; Eine ganze Token-Folge nacheinander dispatchen (Test-/Skript-Komfort).
(defun ide-run (s keys)
  (cond ((null keys) s) (t (ide-run (ide-dispatch s (car keys)) (cdr keys)))))
