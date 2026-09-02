; lib-edit-commands -- Kern-Editierkommandos der IDE-Lisp-Schicht (Phase-8-Vorarbeit).
;
; Fuellt die in docs/onboard-ide.md (Schicht-Tabelle + Feature-Matrix) der
; LISP-Schicht zugewiesenen, noch nicht prototypisierten Kommandos: Kill/Yank,
; Wort-Bewegung und naive Vorwaerts-Suche. Reine Logik (Zustand rein, Zustand
; raus) auf dem editor-core-Modell -- KEIN Rendering, kein Hot-Path (der ist
; nativer ASM).
;
; Setzt editor-core voraus (Zustand (LINES ROW COL), Zeile = Liste 1-Zeichen-
; Strings, plus take/drop/nth-elem/replace-at/cur-line/str->line/line->str).
;
; Kill-Kommandos liefern (NEUER-ZUSTAND . GEKILLTER-STRING), damit der
; Kill-Register beim Aufrufer (Integrationsschicht) liegt und das 3-Tupel des
; editor-core unveraendert bleibt. yank nimmt den String als Argument.
;
; CL-vorwaertskompatibel (defun/let/cond/...), wie editor-core.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;       lisp/edit-commands-tests.lsp

; ---- Wortzeichen: alles ausser Whitespace und Klammern ----
(defun word-char-p (c)
  (cond ((equal c " ") ()) ((equal c "(") ()) ((equal c ")") ()) (t t)))

; ---- Wort-Bewegung (zeilenlokal; Zeilenwechsel macht die Integrationsschicht) ----
(defun skip-nonword (line pos)
  (cond ((null (drop pos line)) pos)
        ((word-char-p (nth-elem pos line)) pos)
        (t (skip-nonword line (1+ pos)))))
(defun skip-word (line pos)
  (cond ((null (drop pos line)) pos)
        ((word-char-p (nth-elem pos line)) (skip-word line (1+ pos)))
        (t pos)))
; Ziel von forward-word: ueber fuehrende Nicht-Wortzeichen, dann ueber das Wort.
(defun fw-target (line col) (skip-word line (skip-nonword line col)))
(defun ed-forward-word (s)
  (mk-ed (ed-lines s) (ed-row s) (fw-target (cur-line s) (ed-col s))))

; backward-word: links ueber Nicht-Wortzeichen, dann an den Wortanfang.
(defun bw-nonword (line col)
  (cond ((< col 1) 0)
        ((word-char-p (nth-elem (1- col) line)) col)
        (t (bw-nonword line (1- col)))))
(defun bw-inword (line col)
  (cond ((< col 1) 0)
        ((word-char-p (nth-elem (1- col) line)) (bw-inword line (1- col)))
        (t col)))
(defun bw-target (line col) (bw-inword line (bw-nonword line col)))
(defun ed-backward-word (s)
  (mk-ed (ed-lines s) (ed-row s) (bw-target (cur-line s) (ed-col s))))

; ---- Kill / Yank ----
; chars im Bereich [from,to) als String.
(defun range-str (line from to) (line->str (take (- to from) (drop from line))))

; kill-to-eol: loescht ab COL bis Zeilenende -> (ZUSTAND . GEKILLT).
(defun ed-kill-to-eol (s)
  (let ((line (cur-line s)) (col (ed-col s)) (row (ed-row s)))
    (cons (mk-ed (replace-at (ed-lines s) row (take col line)) row col)
          (line->str (drop col line)))))

; kill-word: loescht ab COL bis Wortende -> (ZUSTAND . GEKILLT).
(defun ed-kill-word (s)
  (let ((line (cur-line s)) (col (ed-col s)) (row (ed-row s)))
    (let ((end (fw-target line col)))
      (cons (mk-ed (replace-at (ed-lines s) row
                     (append (take col line) (drop end line)))
                   row col)
            (range-str line col end)))))

; yank: fuegt STR an der Cursorposition ein, Cursor dahinter.
(defun ed-yank (s str)
  (let ((line (cur-line s)) (col (ed-col s)) (row (ed-row s)) (ins (str->line str)))
    (mk-ed (replace-at (ed-lines s) row
             (append (take col line) (append ins (drop col line))))
           row (+ col (length ins)))))

; ---- Naive Vorwaerts-Suche ueber den Buffer ----
(defun line-match-at (line pos target)
  (cond ((null target) t)
        ((null (drop pos line)) ())
        ((equal (nth-elem pos line) (car target))
         (line-match-at line (1+ pos) (cdr target)))
        (t ())))
(defun line-find-from (line col target)
  (cond ((> col (length line)) ())
        ((line-match-at line col target) col)
        (t (line-find-from line (1+ col) target))))
; Sucht ab (row,col); liefert (ROW . COL) des Treffers oder NIL.
(defun buf-find (lines row col target)
  (cond ((null (drop row lines)) ())
        (t (let ((hit (line-find-from (nth-elem row lines) col target)))
             (cond (hit (cons row hit))
                   (t (buf-find lines (1+ row) 0 target)))))))
; Bewegt den Cursor zum naechsten Vorkommen von STR NACH dem Cursor; bei
; keinem Treffer unveraendert.
(defun ed-search-forward (s str)
  (let ((hit (buf-find (ed-lines s) (ed-row s) (1+ (ed-col s)) (str->line str))))
    (cond (hit (mk-ed (ed-lines s) (car hit) (cdr hit))) (t s))))
