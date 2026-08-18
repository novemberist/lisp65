; Restorable tracing for the post-v1.4 inspect library.
;
; %function-cell is a private prebuilt-library capability over the unused
; arities of the restricted set-symbol-value carrier.  It returns the
; exact current function-cell value and, with a second argument, swaps in the
; replacement while returning the prior value.  The trace macro prepares the
; exact old value first, then emits a real top-level DEFUN for NAME.  C2 owns
; publication of that definition and the function-cell change in one journaled
; transaction; no transient helper can escape a rollback.

(defun %function-cell (name &rest replacement)
  (if replacement
      (set-symbol-value name (car replacement) 69)
      (set-symbol-value name)))

(defun %inspect-trace-remove (name bindings)
  (if bindings
      (if (eq name (car (car bindings)))
          (cdr bindings)
          (cons (car bindings)
                (%inspect-trace-remove name (cdr bindings))))
      nil))

(defun %inspect-trace-binding (name)
  (if (boundp '*inspect-trace-bindings*)
      (assoc name (symbol-value '*inspect-trace-bindings*))
      nil))

(defun %inspect-trace-original (name)
  ((lambda (binding)
     (if binding (car (cdr binding)) nil))
   (%inspect-trace-binding name)))

(defun %inspect-trace-prepare (name)
  (if (boundp '*inspect-trace-bindings*)
      nil
      (set-symbol-value '*inspect-trace-bindings* nil))
  ((lambda (binding current)
     (if binding
         ; A failed publication leaves NAME on OLD.  Retrying is safe.  A
         ; different current cell means the wrapper is already installed.
         (eq current (car (cdr binding)))
         (if current
             (progn
               (set-symbol-value
                '*inspect-trace-bindings*
                (cons (list name current nil)
                      (symbol-value '*inspect-trace-bindings*)))
               t)
             nil)))
   (%inspect-trace-binding name)
   (%function-cell name)))

(defun %inspect-trace-finish (name)
  ((lambda (binding)
     (if binding
         (progn
           (rplaca (cdr (cdr binding)) (%function-cell name))
           name)
         nil))
   (%inspect-trace-binding name)))

(defun %inspect-trace-call (name arguments)
  (progn
    (write (cons 'trace-enter (cons name arguments)))
    (terpri)
    ((lambda (result)
       (progn
         (write (list 'trace-exit name result))
         (terpri)
         result))
     (apply (%inspect-trace-original name) arguments))))

(defun %inspect-untrace (name)
  ((lambda (binding)
     (if binding
         ((lambda (old current)
            (if (eq current old)
                ; Recovery after a completed restore and before registry
                ; cleanup: never swap the old cell a second time.
                (progn
                  (set-symbol-value
                   '*inspect-trace-bindings*
                   (%inspect-trace-remove
                    name (symbol-value '*inspect-trace-bindings*)))
                  name)
                ((lambda (replaced)
                   (if (eq replaced current)
                       (progn
                         (set-symbol-value
                          '*inspect-trace-bindings*
                          (%inspect-trace-remove
                           name (symbol-value '*inspect-trace-bindings*)))
                         name)
                       ; Defensive rollback if the primitive ever violates
                       ; its exact swap contract.
                       (progn (%function-cell name replaced) nil)))
                 (%function-cell name old))))
          (car (cdr binding))
          (%function-cell name))
         nil))
   (%inspect-trace-binding name)))

(defun %inspect-trace-form (name)
  (list 'progn
        (list 'defun name '(&rest %inspect-trace-arguments)
              (list '%inspect-trace-call
                    (list 'quote name)
                    '%inspect-trace-arguments))
        (list '%inspect-trace-finish (list 'quote name))))

(defmacro trace (name)
  (if (%inspect-trace-prepare name)
      (%inspect-trace-form name)
      (list 'quote name)))

(defmacro untrace (name)
  (list '%inspect-untrace (list 'quote name)))
