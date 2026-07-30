; lisp65 -- setf MVP: places as BCODE macros (C-phase step 5, Lane K,
; 2026-07-06; docs/modularization-review-lane-k.md plus ansi-cl-inventory
; section Places). Pure Lisp library with ZERO Bank-0 cost; candidate for the
; "place" pilot library (PLACE on D81).
;
; v1 surface (fixed expanders plus ONE canonical extension table):
;   (setf sym v) (setf (car p) v) (setf (cdr p) v) (setf (getf sym k) v)
;   (incf place [n]) (decf place [n]) (push v place) (pop place)
; HONEST v1 boundaries (documented, CL-naive):
;   - Place subforms may be evaluated MULTIPLE times; there is no once-only
;     protection except where a gensym appears. This is correct for symbols
;     and ordinary car/cdr-on-variable cases.
;   - (setf (getf ...)) requires a SYMBOL as the plist carrier and writes back
;     through setq.
;   - Unknown place forms expand into a call to the undefined
;     %places-error-unsupported-place, producing a LOUD abort with the name in
;     the error message.
;
; Library extensions are registered publish-last. The visible table
; (*setf-place-registry*) changes only at %setf-register-commit. An aborted
; installation leaves at most invisible pending data, which the next begin
; discards. Thus a failed require/append can never expose a place from an
; unpublished library. Identical duplicate registration is idempotent;
; conflicting registration fails closed.

(defun %places-consp (x)
  (if x (if (numberp x) nil (if (symbolp x) nil (if (stringp x) nil t))) nil))

; plist update core for (setf (getf ...)): returns a NEW plist with k->v,
; replacing or adding it at the front.
(defun %putf (pl k v)
  (if pl
      (if (eq (car pl) k)
          (cons k (cons v (cdr (cdr pl))))
          (cons (car pl) (cons (car (cdr pl)) (%putf (cdr (cdr pl)) k v))))
      (cons k (cons v nil))))

(defun %setf-registry-find (reader rows)
  (if rows
      (if (eq reader (car (car rows)))
          (cdr (car rows))
          (%setf-registry-find reader (cdr rows)))
      nil))

(defun %setf-place-setter (reader)
  (%setf-registry-find
   reader
   (if (boundp '*setf-place-registry*)
       (symbol-value '*setf-place-registry*)
       nil)))

(defun %setf-register-begin ()
  ; A stale pending value is deliberately discarded: it can only belong to
  ; an aborted, never-published installation episode.
  (set-symbol-value
   '*setf-place-pending*
   (if (boundp '*setf-place-registry*)
       (symbol-value '*setf-place-registry*)
       nil))
  (set-symbol-value '*setf-place-open* t)
  t)

(defun %setf-register (reader setter)
  (if (if (symbolp reader) (symbolp setter) nil)
      (if (if (boundp '*setf-place-open*)
              (symbol-value '*setf-place-open*)
              nil)
          (let ((old
                  (%setf-registry-find
                   reader (symbol-value '*setf-place-pending*))))
            (if old
                (if (eq old setter) t nil)
                (progn
                  (set-symbol-value
                   '*setf-place-pending*
                   (cons (cons reader setter)
                         (symbol-value '*setf-place-pending*)))
                  t)))
          nil)
      nil))

(defun %setf-register-commit ()
  (if (if (boundp '*setf-place-open*)
          (symbol-value '*setf-place-open*)
          nil)
      (progn
        (set-symbol-value
         '*setf-place-registry*
         (symbol-value '*setf-place-pending*))
        (set-symbol-value '*setf-place-pending* nil)
        (set-symbol-value '*setf-place-open* nil)
        t)
      nil))

(defun %setf-register-abort ()
  (set-symbol-value '*setf-place-pending* nil)
  (set-symbol-value '*setf-place-open* nil)
  nil)

(defun %setf-expand-registered (place vform g)
  (let ((setter (%setf-place-setter (car place))))
    (if setter
        (list 'let (list (list g vform))
              (cons setter (append (cdr place) (list g)))
              g)
        (list '%places-error-unsupported-place))))

(defun %setf-expand-list (place vform)
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
                       (list '%putf
                             (car (cdr place))
                             (car (cdr (cdr place)))
                             g))
                 g))
          (t (%setf-expand-registered place vform g)))))

; Expander core: builds the assignment form for a place. The value form is
; bound in a GENSYM let so setf returns the VALUE and evaluates val only ONCE.
(defun %setf-expand (place vform)
  (if (symbolp place)
      (list 'setq place vform)
      (if (%places-consp place)   ; Dialekt-Falle: nicht jeder Traeger hat ein natives consp-Primitiv.
          (%setf-expand-list place vform)
          (list '%places-error-unsupported-place))))

(defmacro setf (place vform) (%setf-expand place vform))

; incf/decf: optional delta through &rest; lcc supports &rest in
; defun/defmacro expanders.
(defmacro incf (place &rest r)
  (%setf-expand place (list '+ place (if r (car r) 1))))
(defmacro decf (place &rest r)
  (%setf-expand place (list '- place (if r (car r) 1))))

; push/pop on places; ordinary variable cases and car/cdr places are supported.
(defmacro push (v place)
  (%setf-expand place (list 'cons v place)))
(defmacro pop (place)
  (let ((g (gensym)))
    (list 'let (list (list g (list 'car place)))
          (%setf-expand place (list 'cdr place))
          g)))
