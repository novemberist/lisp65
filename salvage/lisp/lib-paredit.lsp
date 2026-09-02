; lib-paredit -- strukturiertes Editieren (Paredit-Subset), Phase-8-Vorarbeit.
;
; Aufbauend auf editor-core (take/drop/nth-elem/dq). Arbeitet auf einer FLACHEN
; Zeichenliste (1-Zeichen-Strings, inkl. Zeilenumbruch (char 10)) mit einem
; Index als Cursor -> der Scanner ist buffer-GLOBAL und string-/kommentar-bewusst
; (anders als editor-cores zeilenlokales paren-match-line).
;
; Operationen laufen in Menschentempo -> interpretiert/Lisp genuegt (kein nativer
; Code). Spec: docs/paredit-subset-spec.md.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;       lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp \
;       lisp/paredit-tests.lsp

; ---- Zeichen-Praedikate ----
(defun nlp (c) (equal c (char 10)))
(defun wsp (c) (cond ((equal c " ") t) ((nlp c) t) ((equal c (char 9)) t) (t ())))
(defun delimp (c)
  (cond ((wsp c) t) ((equal c "(") t) ((equal c ")") t)
        ((equal c (dq)) t) ((equal c ";") t) (t ())))

(defun sub (chars a b) (take (- b a) (drop a chars)))
(defun at-end (chars pos) (null (drop pos chars)))

; ---- Vorwaerts-Scanner ueber EINE Form ----
(defun str-fwd (chars pos)            ; pos hinter oeffnendem " ; bis hinter schliessendes "
  (cond ((at-end chars pos) pos)
        ((equal (nth-elem pos chars) (dq)) (1+ pos))
        (t (str-fwd chars (1+ pos)))))
(defun line-end (chars pos)           ; Index des naechsten Zeilenumbruchs (oder Ende)
  (cond ((at-end chars pos) pos)
        ((nlp (nth-elem pos chars)) pos)
        (t (line-end chars (1+ pos)))))
(defun atom-fwd (chars pos)
  (cond ((at-end chars pos) pos)
        ((delimp (nth-elem pos chars)) pos)
        (t (atom-fwd chars (1+ pos)))))
(defun list-fwd (chars pos depth)     ; pos hinter "(" ; gibt Index HINTER passendem ")"
  (cond ((at-end chars pos) pos)
        ((equal (nth-elem pos chars) (dq)) (list-fwd chars (str-fwd chars (1+ pos)) depth))
        ((equal (nth-elem pos chars) ";") (list-fwd chars (line-end chars pos) depth))
        ((equal (nth-elem pos chars) "(") (list-fwd chars (1+ pos) (1+ depth)))
        ((equal (nth-elem pos chars) ")")
         (cond ((= depth 1) (1+ pos)) (t (list-fwd chars (1+ pos) (1- depth)))))
        (t (list-fwd chars (1+ pos) depth))))
(defun sx-ws (chars pos)              ; ueberspringt Whitespace + ;-Kommentare
  (cond ((at-end chars pos) pos)
        ((wsp (nth-elem pos chars)) (sx-ws chars (1+ pos)))
        ((equal (nth-elem pos chars) ";") (sx-ws chars (line-end chars pos)))
        (t pos)))
(defun form-fwd (chars pos)           ; pos am Form-Anfang -> Index hinter der Form
  (let ((c (nth-elem pos chars)))
    (cond ((equal c "(") (list-fwd chars (1+ pos) 1))
          ((equal c (dq)) (str-fwd chars (1+ pos)))
          (t (atom-fwd chars pos)))))
(defun sx-fwd (chars pos)             ; forward-sexp: Cursor hinter naechste Form
  (let ((p (sx-ws chars pos)))
    (cond ((at-end chars p) p) (t (form-fwd chars p)))))

; ---- Rueckwaerts (vereinfacht; ignoriert Strings rueckwaerts) ----
(defun skip-ws-back (chars pos)
  (cond ((<= pos 0) 0)
        ((wsp (nth-elem (1- pos) chars)) (skip-ws-back chars (1- pos)))
        (t pos)))
(defun bal-bwd (chars pos depth)
  (cond ((< pos 0) 0)
        ((equal (nth-elem pos chars) ")") (bal-bwd chars (1- pos) (1+ depth)))
        ((equal (nth-elem pos chars) "(")
         (cond ((= depth 1) pos) (t (bal-bwd chars (1- pos) (1- depth)))))
        (t (bal-bwd chars (1- pos) depth))))
(defun atom-bwd (chars pos)
  (cond ((< pos 0) 0)
        ((delimp (nth-elem pos chars)) (1+ pos))
        (t (atom-bwd chars (1- pos)))))
(defun sx-bwd (chars pos)             ; backward-sexp: Cursor an Anfang der Form davor
  (let ((q (skip-ws-back chars pos)))
    (cond ((<= q 0) 0)
          ((equal (nth-elem (1- q) chars) ")") (bal-bwd chars (1- q) 1))
          (t (atom-bwd chars (1- q))))))

; ---- Umschliessende Liste finden ----
(defun opens-aux (chars i pos stack)  ; Liste offener "("-Indizes bei pos (innerste zuerst)
  (cond ((>= i pos) stack)
        ((at-end chars i) stack)
        ((equal (nth-elem i chars) (dq)) (opens-aux chars (str-fwd chars (1+ i)) pos stack))
        ((equal (nth-elem i chars) ";") (opens-aux chars (line-end chars i) pos stack))
        ((equal (nth-elem i chars) "(") (opens-aux chars (1+ i) pos (cons i stack)))
        ((equal (nth-elem i chars) ")") (opens-aux chars (1+ i) pos (cdr stack)))
        (t (opens-aux chars (1+ i) pos stack))))
(defun encl-open (chars pos) (car (opens-aux chars 0 pos ())))
(defun encl-close (chars open) (1- (list-fwd chars (1+ open) 1)))

; Start der letzten Kind-Form vor close
(defun lcs-aux (chars start close last)
  (cond ((>= start close) last)
        (t (lcs-aux chars (sx-ws chars (form-fwd chars start)) close start))))
(defun last-child-start (chars open close)
  (lcs-aux chars (sx-ws chars (1+ open)) close ()))
(defun ws-back (chars pos)            ; Index direkt hinter letztem Nicht-WS vor pos
  (cond ((<= pos 0) 0)
        ((wsp (nth-elem (1- pos) chars)) (ws-back chars (1- pos)))
        (t pos)))

; ---- Edit-Operationen (Zeichenliste rein -> Zeichenliste raus) ----

; slurp-forward: naechste Geschwister-Form in die Klammer ziehen
;   (a b| c) d  ->  (a b| c d)
(defun slurp2 (chars close)
  (let ((nstart (sx-ws chars (1+ close))))
    (let ((nend (cond ((at-end chars nstart) nstart) (t (form-fwd chars nstart)))))
      (cond ((= nstart nend) chars)
            (t (append (take close chars)
                       (append (sub chars (1+ close) nend)
                               (cons ")" (drop nend chars)))))))))
(defun slurp-forward (chars pos)
  (let ((open (encl-open chars pos)))
    (cond ((null open) chars)
          (t (slurp2 chars (encl-close chars open))))))

; barf-forward: letztes Kind aus der Klammer schieben
;   (a b c|)  ->  (a b|) c
(defun barf2 (chars open close)
  (let ((ls (last-child-start chars open close)))
    (cond ((null ls) chars)
          (t (append (take (ws-back chars ls) chars)
                     (append (list ")" " ")
                             (append (sub chars ls close)
                                     (drop (1+ close) chars))))))))
(defun barf-forward (chars pos)
  (let ((open (encl-open chars pos)))
    (cond ((null open) chars)
          (t (barf2 chars open (encl-close chars open))))))

; wrap-round: naechste Form in ( ) huellen
;   |foo bar  ->  (|foo) bar
(defun wrap2 (chars p)
  (let ((end (form-fwd chars p)))
    (append (take p chars)
            (append (cons "(" (sub chars p end))
                    (cons ")" (drop end chars))))))
(defun wrap-round (chars pos)
  (let ((p (sx-ws chars pos)))
    (cond ((at-end chars p) chars)
          (t (wrap2 chars p)))))

; splice: Klammern der umschliessenden Liste entfernen
;   (a (b| c) d)  ->  (a b| c d)
(defun splice2 (chars open close)
  (append (take open chars)
          (append (sub chars (1+ open) close)
                  (drop (1+ close) chars))))
(defun splice (chars pos)
  (let ((open (encl-open chars pos)))
    (cond ((null open) chars)
          (t (splice2 chars open (encl-close chars open))))))
