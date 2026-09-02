; lib-buffers -- Multi-Buffer-Verwaltung, Modeline, Minibuffer (Phase-8-Vorarbeit).
;
; Naechste Lisp-Schicht-Logik der IDE nach lib-edit-commands (siehe
; docs/onboard-ide.md, Feature-Matrix: "Mehrere Buffer ... wie C-x b" und
; "Modeline + Minibuffer"). Reine Logik (Zustand rein, Zustand raus); KEIN
; Rendering ins Screen-RAM -- das ist der native ASM-Hot-Path.
;
; Setzt editor-core voraus (Zustand (LINES ROW COL), take/drop, ed-row/ed-col).
; CL-vorwaertskompatibel; String-Bildung ueber pack/unpack (laeuft auch nativ).
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-buffers.lsp \
;       lisp/buffers-tests.lsp

; ---- String-Helfer (dialekt-robust: Zeichenlisten + pack) ----
(defun cat-chars (strs)
  (cond ((null strs) ()) (t (append (unpack (car strs)) (cat-chars (cdr strs))))))
(defun cat (strs) (pack (cat-chars strs)))        ; Liste von Strings -> String
(defun digit-char (d) (char (+ 48 d)))
(defun int->chars (n)
  (cond ((< n 10) (list (digit-char n)))
        (t (append (int->chars (quotient n 10))
                   (list (digit-char (remainder n 10)))))))
(defun int->str (n) (pack (int->chars n)))
(defun spaces (n) (cond ((< n 1) ()) (t (cons " " (spaces (1- n))))))
(defun pad-right (s width)
  (let ((cs (unpack s))) (pack (append cs (spaces (- width (length cs)))))))

; ---- Buffer = (NAME ED MODIFIED) ----
(defun buf-mk (name ed) (list name ed ()))
(defun buf-name (b) (car b))
(defun buf-ed (b) (car (cdr b)))
(defun buf-modified (b) (car (cdr (cdr b))))

; ---- Buffer-Set = (BUFFERS CURRENT-NAME) ----
(defun bs-mk (buffers current) (list buffers current))
(defun bs-buffers (bs) (car bs))
(defun bs-current-name (bs) (car (cdr bs)))

(defun bs-find (buffers name)
  (cond ((null buffers) ())
        ((equal (buf-name (car buffers)) name) (car buffers))
        (t (bs-find (cdr buffers) name))))
(defun bs-current (bs) (bs-find (bs-buffers bs) (bs-current-name bs)))
(defun bs-current-ed (bs) (buf-ed (bs-current bs)))

(defun bs-remove-buf (buffers name)
  (cond ((null buffers) ())
        ((equal (buf-name (car buffers)) name) (cdr buffers))
        (t (cons (car buffers) (bs-remove-buf (cdr buffers) name)))))

; add (oder ersetzt) Buffer und macht ihn aktuell (wie find-file/switch).
(defun bs-add (bs name ed)
  (bs-mk (append (bs-remove-buf (bs-buffers bs) name) (list (buf-mk name ed))) name))

; C-x b: zu vorhandenem Buffer wechseln; unbekannter Name -> unveraendert.
(defun bs-switch (bs name)
  (cond ((bs-find (bs-buffers bs) name) (bs-mk (bs-buffers bs) name)) (t bs)))

(defun bs-names-aux (buffers)
  (cond ((null buffers) ()) (t (cons (buf-name (car buffers)) (bs-names-aux (cdr buffers))))))
(defun bs-names (bs) (bs-names-aux (bs-buffers bs)))

; Buffer schliessen; aktueller -> erster verbleibender (oder "" wenn leer).
(defun bs-kill (bs name)
  (let ((rest (bs-remove-buf (bs-buffers bs) name)))
    (bs-mk rest (cond ((null rest) "")
                      ((equal (bs-current-name bs) name) (buf-name (car rest)))
                      (t (bs-current-name bs))))))

; ED des aktuellen Buffers ersetzen, MODIFIED-Flag explizit.
(defun bs-replace-ed (buffers name ed mod)
  (cond ((null buffers) ())
        ((equal (buf-name (car buffers)) name) (cons (list name ed mod) (cdr buffers)))
        (t (cons (car buffers) (bs-replace-ed (cdr buffers) name ed mod)))))
; Editierkommando: markiert MODIFIED.
(defun bs-update-ed (bs ed)
  (bs-mk (bs-replace-ed (bs-buffers bs) (bs-current-name bs) ed t) (bs-current-name bs)))
; Reine Cursor-Bewegung: MODIFIED-Flag des Buffers bleibt unveraendert.
(defun bs-move-ed (bs ed)
  (bs-mk (bs-replace-ed (bs-buffers bs) (bs-current-name bs) ed
                        (buf-modified (bs-current bs)))
         (bs-current-name bs)))

; Zyklisch zum naechsten Buffer (wrap).
(defun next-name (names cur first)
  (cond ((null names) first)
        ((equal (car names) cur)
         (cond ((null (cdr names)) first) (t (car (cdr names)))))
        (t (next-name (cdr names) cur first))))
(defun bs-next (bs)
  (let ((names (bs-names bs)))
    (cond ((null names) bs)
          (t (bs-mk (bs-buffers bs) (next-name names (bs-current-name bs) (car names)))))))

; ---- Modeline: "-- NAME [*]  (ROW,COL)" aus dem aktuellen Buffer ----
(defun modeline (bs)
  (let ((b (bs-current bs)))
    (cat (list "-- " (buf-name b)
               (cond ((buf-modified b) " * ") (t "   "))
               "(" (int->str (ed-row (buf-ed b))) ","
               (int->str (ed-col (buf-ed b))) ")"))))

; ---- Minibuffer = (PROMPT INPUT COL) ----
(defun mb-mk (prompt) (list prompt "" 0))
(defun mb-prompt (mb) (car mb))
(defun mb-input (mb) (car (cdr mb)))
(defun mb-col (mb) (car (cdr (cdr mb))))
(defun mb-text (mb) (mb-input mb))                ; bestaetigte Eingabe
(defun mb-render (mb) (cat (list (mb-prompt mb) (mb-input mb))))
(defun mb-insert (mb ch)
  (let ((cs (unpack (mb-input mb))) (col (mb-col mb)))
    (list (mb-prompt mb)
          (pack (append (take col cs) (cons ch (drop col cs)))) (1+ col))))
(defun mb-backspace (mb)
  (let ((cs (unpack (mb-input mb))) (col (mb-col mb)))
    (cond ((> col 0)
           (list (mb-prompt mb) (pack (append (take (1- col) cs) (drop col cs))) (1- col)))
          (t mb))))
