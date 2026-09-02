; lib-ide -- IDE-Kommandoschicht (Phase-8-Vorarbeit): eval-defun + Paredit-Keymap.
;
; Verbindet die vorhandenen Prototypen: editor-cores Keymap-Dispatch + lib-paredits
; buffer-globalen S-Expr-Scanner. Arbeitet auf einem FLACHEN Buffer-Zustand
; (CHARS POS) -- dieselbe Repraesentation wie lib-paredit (1-Zeichen-Strings +
; Index). Spec/Einordnung: docs/paredit-subset-spec.md, docs/ide-ux-design.md.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp \
;       lisp/lib-ide.lsp lisp/ide-tests.lsp

; ---- Flacher Buffer-Zustand (CHARS POS) ----
(defun fb-mk (chars pos) (list chars pos))
(defun fb-chars (s) (car s))
(defun fb-pos (s) (car (cdr s)))

; ---- eval-defun: Top-Level-Form bei/vor dem Cursor finden + auswerten ----
; Liefert (START . END) der Top-Level-Form, in der der Cursor steht, sonst die
; zuletzt davor liegende.
(defun ed-tl-aux (chars start pos last)
  (let ((s (sx-ws chars start)))
    (cond ((at-end chars s) last)
          (t (let ((e (form-fwd chars s)))
               (cond ((and (<= s pos) (<= pos e)) (cons s e))
                     ((> s pos) last)
                     (t (ed-tl-aux chars e pos (cons s e)))))))))
(defun ed-toplevel-bounds (chars pos) (ed-tl-aux chars 0 pos ()))

; Form als String extrahieren (fuer Anzeige/Transport)
(defun ed-toplevel-string (chars pos)
  (let ((b (ed-toplevel-bounds chars pos)))
    (cond ((null b) "") (t (pack (sub chars (car b) (cdr b)))))))

; eval-defun: extrahieren -> READ -> EVAL -> Wert (SLIME f5)
(defun ed-eval-defun (chars pos)
  (let ((b (ed-toplevel-bounds chars pos)))
    (cond ((null b) ())
          (t (eval (read-from-string (pack (sub chars (car b) (cdr b)))))))))

; ---- Flache Kommandos (Zustand -> Zustand) ----
(defun fb-forward-sexp (s) (fb-mk (fb-chars s) (sx-fwd (fb-chars s) (fb-pos s))))
(defun fb-backward-sexp (s) (fb-mk (fb-chars s) (sx-bwd (fb-chars s) (fb-pos s))))
(defun fb-slurp (s) (fb-mk (slurp-forward (fb-chars s) (fb-pos s)) (fb-pos s)))
(defun fb-barf (s) (fb-mk (barf-forward (fb-chars s) (fb-pos s)) (fb-pos s)))
(defun fb-wrap (s) (fb-mk (wrap-round (fb-chars s) (fb-pos s)) (fb-pos s)))
(defun fb-splice (s) (fb-mk (splice (fb-chars s) (fb-pos s)) (fb-pos s)))

; ---- Starter-Keymap (SLIME/Paredit-Bindings als Daten) ----
; Tasten als Strings (Emacs-/Paredit-Notation); Kommandos = Funktionssymbole.
; ed-dispatch/km-lookup stammen aus editor-core (key per EQUAL, cmd per funcall).
(setq *ide-keymap*
  (list
    (cons "C-M-f" (quote fb-forward-sexp))
    (cons "C-M-b" (quote fb-backward-sexp))
    (cons "C-)"   (quote fb-slurp))
    (cons "C-}"   (quote fb-barf))
    (cons "M-("   (quote fb-wrap))
    (cons "M-s"   (quote fb-splice))))
