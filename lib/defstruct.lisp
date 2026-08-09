; defstruct v1 — tagged-list records, positional and option-free.
; This is probe source.  The target preflight deliberately proves that its
; two named compile-time seams (`intern`, `%setf-register`) exist before the
; first L65P artifact may be emitted.

(defun %defstruct-symbol (prefix name suffix)
  (intern
   (string-append prefix (symbol-name name) suffix)))

(defun %defstruct-slot-symbol (name infix slot)
  (intern
   (string-append
    (symbol-name name)
    (string-append infix (symbol-name slot)))))

(defun %defstruct-member (item values)
  (if values
      (if (eq item (car values))
          t
          (%defstruct-member item (cdr values)))
      nil))

(defun %defstruct-slots-valid-p (slots seen)
  (if slots
      (if (symbolp (car slots))
          (if (%defstruct-member (car slots) seen)
              nil
              (%defstruct-slots-valid-p
               (cdr slots) (cons (car slots) seen)))
          nil)
      t))

(defun %defstruct-names-free-p (names)
  (if names
      (if (function-kind (car names))
          nil
          (%defstruct-names-free-p (cdr names)))
      t))

(defun %defstruct-slot-names (name slots)
  (if slots
      (cons (%defstruct-slot-symbol name "-" (car slots))
            (cons (%defstruct-slot-symbol
                   name "-set-" (car slots))
                  (cons (%defstruct-slot-symbol
                         name "-with-" (car slots))
                        (%defstruct-slot-names
                         name (cdr slots)))))
      nil))

(defun %defstruct-generated-names (name slots)
  (append
   (list (%defstruct-symbol "make-" name "")
         (%defstruct-symbol "" name "-p")
         (%defstruct-symbol "copy-" name ""))
   (%defstruct-slot-names name slots)))

(defun %defstruct-constructor-form (name slots)
  (list 'defun (%defstruct-symbol "make-" name "") slots
        (cons 'list (cons (list 'quote name) slots))))

(defun %defstruct-predicate-form (name)
  (list 'defun (%defstruct-symbol "" name "-p") (list 'value)
        (list '%defstruct-instance-p (list 'quote name) 'value)))

(defun %defstruct-copy-form (name)
  (list 'defun (%defstruct-symbol "copy-" name "") (list 'value)
        (list '%defstruct-copy 'value)))

; Keep generated functions small: the shared operations live in Bank 2
; instead of being recompiled into every persistent definition.
(defun %defstruct-instance-p (name value)
  (if (consp value)
      (eq (car value) name)
      nil))

(defun %defstruct-copy (value)
  (cons (car value) (copy-list (cdr value))))

(defun %defstruct-read (index value)
  (nth index value))

(defun %defstruct-set (index value new-value)
  (rplaca (nthcdr index value) new-value))

(defun %defstruct-with (name count selected value new-value)
  (let ((index 1)
        (values nil))
    (while (not (> index count))
      (setq values
            (cons (if (= index selected)
                      new-value
                      (nth index value))
                  values))
      (setq index (+ index 1)))
    (cons name (reverse values))))

(defun %defstruct-one-slot-forms (name all-slots slot index)
  (let ((reader (%defstruct-slot-symbol name "-" slot))
        (setter (%defstruct-slot-symbol name "-set-" slot))
        (updater (%defstruct-slot-symbol name "-with-" slot)))
    (list
     (list 'defun reader (list 'value)
           (list '%defstruct-read index 'value))
     (list 'defun setter (list 'value 'new-value)
           (list '%defstruct-set index 'value 'new-value))
     (list 'defun updater (list 'value 'new-value)
           (list '%defstruct-with
                 (list 'quote name) (length all-slots) index
                 'value 'new-value)))))

(defun %defstruct-slot-forms (name all-slots slots index)
  (if slots
      (append
       (%defstruct-one-slot-forms name all-slots (car slots) index)
       (%defstruct-slot-forms
        name all-slots (cdr slots) (+ index 1)))
      nil))

(defun %defstruct-register-forms (name slots)
  (let ((rest slots)
        (pairs nil))
    (while rest
      (setq pairs
            (cons
             (list (%defstruct-slot-symbol name "-" (car rest))
                   (%defstruct-slot-symbol name "-set-" (car rest)))
             pairs))
      (setq rest (cdr rest)))
    (list '%defstruct-register-layout
          (list 'quote (reverse pairs)))))

(defun %defstruct-register-layout (pairs)
  (let ((rest pairs)
        (valid t))
    (while (if rest valid nil)
      (let ((pair (car rest)))
        (if (%setf-register (car pair) (car (cdr pair)))
            nil
            (setq valid nil)))
      (setq rest (cdr rest)))
    (if valid
        (%setf-register-commit)
        (%setf-register-abort))))

(defun %defstruct-expansion (name slots)
  (cons 'progn
        (cons (list '%setf-register-begin)
              (cons (%defstruct-constructor-form name slots)
                    (cons (%defstruct-predicate-form name)
                          (cons (%defstruct-copy-form name)
                                (append
                                 (%defstruct-slot-forms
                                  name slots slots 1)
                                 (list
                                  (%defstruct-register-forms
                                   name slots)))))))))

(defmacro defstruct (name &rest slots)
  (if (if (symbolp name)
          (if (%defstruct-slots-valid-p slots nil)
              (%defstruct-names-free-p
               (%defstruct-generated-names name slots))
              nil)
          nil)
      (%defstruct-expansion name slots)
      (list '%defstruct-error-invalid-layout)))
