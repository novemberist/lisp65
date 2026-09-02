; editor-core -- rein funktionaler Editor-LOGIK-Kern (Phase-8-Vorarbeit).
;
; Modelliert die Lisp-Schicht der IDE (siehe docs/onboard-ide.md, Schicht-
; Tabelle): Buffer/Cursor, Insert/Delete/Newline, Cursor-Bewegung,
; Auto-Einrueckung, Klammer-Matching, Keymap-Dispatch. KEIN Rendering und keine
; Echtzeit -- das ist der native ASM-Hot-Path und wird hier nicht modelliert.
;
; CL-VORWAERTSKOMPATIBEL geschrieben: nur Konstrukte, die heute ueber prelude/
; lib-macros/cl-compat laufen UND in einem CL-naeheren Dialekt nativ waeren
; (defun/let/let*/cond/when, + - < > = 1+ 1-, first/rest). BEWUSST OHNE die
; Semantik-Fallen NTH/LAST/MAP -- stattdessen eigene take/drop.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/editor-tests.lsp
;
; Zustand: (LINES ROW COL); Zeile = Liste von 1-Zeichen-Strings.

(defun ed-lines (s) (car s))
(defun ed-row (s) (car (cdr s)))
(defun ed-col (s) (car (cdr (cdr s))))
(defun mk-ed (lines row col) (list lines row col))

; ---- Listen-Helfer ohne NTH/LAST (dialekt-robust) ----
(defun take (n l)
  (cond ((zerop n) ()) ((null l) ()) (t (cons (car l) (take (1- n) (cdr l))))))
(defun drop (n l)
  (cond ((zerop n) l) ((null l) ()) (t (drop (1- n) (cdr l)))))
(defun nth-elem (n l) (car (drop n l)))
(defun replace-at (l n new)
  (cond ((null l) ())
        ((zerop n) (cons new (cdr l)))
        (t (cons (car l) (replace-at (cdr l) (1- n) new)))))
(defun insert-at (l n new)
  (cond ((zerop n) (cons new l))
        ((null l) (cons new ()))
        (t (cons (car l) (insert-at (cdr l) (1- n) new)))))
(defun remove-at (l n)
  (cond ((null l) ())
        ((zerop n) (cdr l))
        (t (cons (car l) (remove-at (cdr l) (1- n))))))

(defun cur-line (s) (nth-elem (ed-row s) (ed-lines s)))

; ---- String <-> Zeile ----
(defun str->line (str) (unpack str))
(defun line->str (line) (cond ((null line) "") (t (pack line))))
(defun ed-render (s) (mapcar (quote line->str) (ed-lines s)))

; ---- Editier-Kommandos (rein funktional: Zustand rein, Zustand raus) ----
(defun ed-insert (s ch)
  (let ((line (cur-line s)) (col (ed-col s)))
    (mk-ed (replace-at (ed-lines s) (ed-row s)
             (append (take col line) (cons ch (drop col line))))
           (ed-row s) (1+ col))))

(defun ed-backspace (s)
  (let ((line (cur-line s)) (col (ed-col s)) (row (ed-row s)))
    (cond ((> col 0)
           (mk-ed (replace-at (ed-lines s) row
                    (append (take (1- col) line) (drop col line)))
                  row (1- col)))
          ((> row 0)
           (let ((prev (nth-elem (1- row) (ed-lines s))))
             (mk-ed (remove-at (replace-at (ed-lines s) (1- row) (append prev line)) row)
                    (1- row) (length prev))))
          (t s))))

(defun ed-newline (s)
  (let ((line (cur-line s)) (col (ed-col s)) (row (ed-row s)))
    (mk-ed (insert-at (replace-at (ed-lines s) row (take col line))
                      (1+ row) (drop col line))
           (1+ row) 0)))

(defun ed-left (s)
  (cond ((> (ed-col s) 0) (mk-ed (ed-lines s) (ed-row s) (1- (ed-col s)))) (t s)))
(defun ed-right (s)
  (cond ((< (ed-col s) (length (cur-line s)))
         (mk-ed (ed-lines s) (ed-row s) (1+ (ed-col s)))) (t s)))
(defun ed-home (s) (mk-ed (ed-lines s) (ed-row s) 0))
(defun ed-end (s) (mk-ed (ed-lines s) (ed-row s) (length (cur-line s))))

; ---- Auto-Einrueckung: Klammertiefe aller Zeichen VOR dem Cursor ----
(defun paren-bal (chars)
  (cond ((null chars) 0)
        ((equal (car chars) "(") (1+ (paren-bal (cdr chars))))
        ((equal (car chars) ")") (1- (paren-bal (cdr chars))))
        (t (paren-bal (cdr chars)))))
(defun lines-bal (lines)
  (cond ((null lines) 0) (t (+ (paren-bal (car lines)) (lines-bal (cdr lines))))))
(defun ed-indent-level (s)
  (+ (lines-bal (take (ed-row s) (ed-lines s)))
     (paren-bal (take (ed-col s) (cur-line s)))))

; ---- Klammer-Matching innerhalb einer Zeile ----
(defun scan-fwd (line pos depth)
  (cond ((null (drop pos line)) ())
        ((equal (nth-elem pos line) "(") (scan-fwd line (1+ pos) (1+ depth)))
        ((equal (nth-elem pos line) ")")
         (cond ((= depth 1) pos) (t (scan-fwd line (1+ pos) (1- depth)))))
        (t (scan-fwd line (1+ pos) depth))))
(defun scan-bwd (line pos depth)
  (cond ((< pos 0) ())
        ((equal (nth-elem pos line) ")") (scan-bwd line (1- pos) (1+ depth)))
        ((equal (nth-elem pos line) "(")
         (cond ((= depth 1) pos) (t (scan-bwd line (1- pos) (1- depth)))))
        (t (scan-bwd line (1- pos) depth))))
(defun paren-match-line (line col)
  (let ((c (nth-elem col line)))
    (cond ((equal c "(") (scan-fwd line (1+ col) 1))
          ((equal c ")") (scan-bwd line (1- col) 1))
          (t ()))))

; ---- Keymap-Dispatch (Emacs-Modell: Taste -> Kommando) ----
(defun km-lookup (key km)
  (cond ((null km) ())
        ((equal key (car (car km))) (cdr (car km)))
        (t (km-lookup key (cdr km)))))
(defun ed-dispatch (km key s)
  (let ((cmd (km-lookup key km)))
    (cond (cmd (funcall cmd s)) (t s))))

; ---- Syntax-Highlight-Klassifizierer (Referenz-Semantik fuer ASM-Faerbepass) ----
; classify: Zeichenliste -> Liste von Kategorien (gleiche Laenge).
; Kategorien: PAREN STRING COMMENT NUMBER SPACE SYMBOL.
; Hinweis: ';' als Zeilenkommentar ist Host-/Editor-Komfort; der echte Dialekt-
; Kommentar ist die Form (* ...). Double-Quote via (char 34), da der Reader
; keine Escapes kennt.
(defun dq () (char 34))
(defun digitp (c)
  (cond ((< (asc c) 48) ()) ((> (asc c) 57) ()) (t t)))
(defun cl-class (chars state)
  (cond ((null chars) ())
        ((eq state (quote comment))
         (cons (quote comment) (cl-class (cdr chars) (quote comment))))
        ((eq state (quote string))
         (cond ((equal (car chars) (dq))
                (cons (quote string) (cl-class (cdr chars) (quote normal))))
               (t (cons (quote string) (cl-class (cdr chars) (quote string))))))
        ((equal (car chars) ";")
         (cons (quote comment) (cl-class (cdr chars) (quote comment))))
        ((equal (car chars) (dq))
         (cons (quote string) (cl-class (cdr chars) (quote string))))
        ((equal (car chars) "(") (cons (quote paren) (cl-class (cdr chars) (quote normal))))
        ((equal (car chars) ")") (cons (quote paren) (cl-class (cdr chars) (quote normal))))
        ((equal (car chars) " ") (cons (quote space) (cl-class (cdr chars) (quote normal))))
        ((digitp (car chars)) (cons (quote number) (cl-class (cdr chars) (quote normal))))
        (t (cons (quote symbol) (cl-class (cdr chars) (quote normal))))))
(defun classify (chars) (cl-class chars (quote normal)))
