(defun %binding-var (binding)
  (car binding))

(defun %binding-init (binding)
  (cadr binding))

(defun %binding-step (binding)
  (if (cdr (cdr binding))
      (car (cdr (cdr binding)))
      (car binding)))

(defun %optional-third (spec)
  (if (cdr (cdr spec))
      (car (cdr (cdr spec)))
      nil))

(defmacro do (bindings endtest &rest body)
  ((lambda (binding)
     `((lambda (%%do-loop)
         (setq %%do-loop
               (lambda (,(%binding-var binding))
                 (if ,(car endtest)
                     (progn ,@(cdr endtest))
                     (progn ,@body
                            (funcall %%do-loop ,(%binding-step binding))))))
         (funcall %%do-loop ,(%binding-init binding)))
       nil))
   (car bindings)))

(defmacro dotimes (spec &rest body)
  `(do ((,(car spec) 0 (1+ ,(car spec))))
       ((>= ,(car spec) ,(cadr spec)) ,(%optional-third spec))
     ,@body))

(defmacro dolist (spec &rest body)
  `((lambda (%%dolist-loop)
      (setq %%dolist-loop
            (lambda (%%dolist-xs)
              (if %%dolist-xs
                     ((lambda (,(car spec))
                        (progn ,@body
                               (funcall %%dolist-loop (cdr %%dolist-xs))))
                      (car %%dolist-xs))
                  ,(%optional-third spec))))
      (funcall %%dolist-loop ,(cadr spec)))
    nil))
