; Function-cell tracing lives in Bank 2 as macros.  The macro expansion is
; evaluated by the treewalk top level: there (function NAME) returns the real
; function-cell value, so the wrapper closes over the original callable rather
; than recursively resolving NAME after installation.

(defun %comfort-trace-remove (name bindings)
  (if bindings
      (if (eq name (car (car bindings)))
          (cdr bindings)
          (cons (car bindings)
                (%comfort-trace-remove name (cdr bindings))))
      nil))

(defun %comfort-trace-wrapper-form (name)
  `(lambda (&rest %comfort-trace-arguments)
     (progn
       (write (cons 'trace-enter
                    (cons ',name %comfort-trace-arguments)))
       (terpri)
       ((lambda (%comfort-trace-result)
          (progn
            (write (list 'trace-exit ',name %comfort-trace-result))
            (terpri)
            %comfort-trace-result))
        (apply %comfort-trace-original %comfort-trace-arguments)))))

(defun %comfort-trace-install-form (name)
  `(progn
     (if (boundp '*comfort-trace-bindings*)
         nil
         (setq *comfort-trace-bindings* nil))
     (if (assoc ',name *comfort-trace-bindings*)
         ',name
         ((lambda (%comfort-trace-original)
            (progn
              (setq *comfort-trace-bindings*
                    (cons (cons ',name %comfort-trace-original)
                          *comfort-trace-bindings*))
              (set-symbol-function
               ',name ,(%comfort-trace-wrapper-form name))
              ',name))
          (function ,name)))))

(defmacro trace (name)
  (%comfort-trace-install-form name))

(defmacro untrace (name)
  `(if (boundp '*comfort-trace-bindings*)
       ((lambda (%comfort-trace-binding)
          (if %comfort-trace-binding
              (progn
                (set-symbol-function ',name
                                     (cdr %comfort-trace-binding))
                (setq *comfort-trace-bindings*
                      (%comfort-trace-remove
                       ',name *comfort-trace-bindings*))
                ',name)
              nil))
        (assoc ',name *comfort-trace-bindings*))
       nil))
