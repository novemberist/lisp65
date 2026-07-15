; lisp65 — setf-MVP: Places als BCODE-Makros (C-Phase Schritt 5, Lane K 2026-07-06;
; docs/modularization-review-lane-k.md + ansi-cl-inventory §Places). Reine Lisp-Lib —
; NULL Bank-0-Kosten; Kandidat für die "place"-Pilot-Lib (PLACE auf D81).
;
; v1-Fläche (feste Expander, KEINE generalisierten setf-Expander):
;   (setf sym v) (setf (car p) v) (setf (cdr p) v) (setf (getf sym k) v)
;   (incf place [n]) (decf place [n]) (push v place) (pop place)
; EHRLICHE v1-Grenzen (dokumentiert, CL-naiv):
;   - Subformen der Place werden ggf. MEHRFACH ausgewertet (kein once-only ausser wo gensym
;     steht) — für Symbole/car/cdr-auf-Variablen der Alltagsfälle korrekt.
;   - (setf (getf ...)) verlangt ein SYMBOL als plist-Träger (schreibt via setq zurück).
;   - Unbekannte Place-Formen expandieren zu einem Aufruf der undefinierten
;     %places-error-unsupported-place -> LAUTER Abort mit Namen in der Fehlermeldung.

(defun %places-consp (x)
  (if x (if (numberp x) nil (if (symbolp x) nil (if (stringp x) nil t))) nil))

; plist-Update-Kern für (setf (getf ...)): liefert NEUE plist mit k->v (vorn ersetzt/ergänzt).
(defun %putf (pl k v)
  (if pl
      (if (eq (car pl) k)
          (cons k (cons v (cdr (cdr pl))))
          (cons (car pl) (cons (car (cdr pl)) (%putf (cdr (cdr pl)) k v))))
      (cons k (cons v nil))))

; Expander-Kern: baut die Zuweisungs-Form für eine Place. Wert-Form wird als GENSYM-let
; gebunden, damit setf den WERT zurückgibt und val nur EINMAL ausgewertet wird.
(defun %setf-expand (place vform)
  (if (symbolp place)
      (list 'setq place vform)
      (if (%places-consp place)   ; Dialekt-Falle: nicht jeder Traeger hat ein natives consp-Primitiv.
          (let ((g (gensym)))
            (cond ((eq (car place) 'car)
                   (list 'let (list (list g vform))
                         (list 'rplaca (car (cdr place)) g) g))
                  ((eq (car place) 'cdr)
                   (list 'let (list (list g vform))
                         (list 'rplacd (car (cdr place)) g) g))
                  ((eq (car place) 'getf)
                   (list 'let (list (list g vform))
                         (list 'setq (car (cdr place))
                               (list '%putf (car (cdr place)) (car (cdr (cdr place))) g))
                         g))
                  (t (list '%places-error-unsupported-place))))
          (list '%places-error-unsupported-place))))

(defmacro setf (place vform) (%setf-expand place vform))

; incf/decf: optionales Delta via &rest (lcc kann &rest in defun/defmacro-Expandern).
(defmacro incf (place &rest r)
  (%setf-expand place (list '+ place (if r (car r) 1))))
(defmacro decf (place &rest r)
  (%setf-expand place (list '- place (if r (car r) 1))))

; push/pop auf Places (Alltagsfälle: Variable; car/cdr-Places gehen mit).
(defmacro push (v place)
  (%setf-expand place (list 'cons v place)))
(defmacro pop (place)
  (let ((g (gensym)))
    (list 'let (list (list g (list 'car place)))
          (%setf-expand place (list 'cdr place))
          g)))
