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
        (list 'if (list 'consp 'value)
              (list 'eq (list 'car 'value) (list 'quote name))
              nil)))

(defun %defstruct-copy-form (name)
  (list 'defun (%defstruct-symbol "copy-" name "") (list 'value)
        (list 'cons (list 'car 'value)
              (list 'copy-list (list 'cdr 'value)))))

(defun %defstruct-update-values (slots selected index)
  (if slots
      (cons
       (if (eq (car slots) selected)
           'new-value
           (list 'nth index 'value))
       (%defstruct-update-values (cdr slots) selected (+ index 1)))
      nil))

(defun %defstruct-one-slot-forms (name all-slots slot index)
  (let ((reader (%defstruct-slot-symbol name "-" slot))
        (setter (%defstruct-slot-symbol name "-set-" slot))
        (updater (%defstruct-slot-symbol name "-with-" slot)))
    (list
     (list 'defun reader (list 'value)
           (list 'nth index 'value))
     (list 'defun setter (list 'value 'new-value)
           (list 'rplaca (list 'nthcdr index 'value) 'new-value))
     (list 'defun updater (list 'value 'new-value)
           (cons 'list
                 (cons (list 'quote name)
                       (%defstruct-update-values
                        all-slots slot 1)))))))

(defun %defstruct-slot-forms (name all-slots slots index)
  (if slots
      (append
       (%defstruct-one-slot-forms name all-slots (car slots) index)
       (%defstruct-slot-forms
        name all-slots (cdr slots) (+ index 1)))
      nil))

(defun %defstruct-register-forms (name slots)
  (if slots
      (let ((reader (%defstruct-slot-symbol name "-" (car slots)))
            (setter (%defstruct-slot-symbol name "-set-" (car slots))))
        (list 'if
              (list '%setf-register
                    (list 'quote reader) (list 'quote setter))
              (%defstruct-register-forms name (cdr slots))
              (list '%setf-register-abort)))
      (list '%setf-register-commit)))

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
