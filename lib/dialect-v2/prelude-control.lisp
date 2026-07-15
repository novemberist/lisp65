; Dialect-v2 Prelude/Control delta. Public surface is contract-derived.

(defmacro defparameter (name init)
  `(progn (setq ,name ,init) ',name))

(defmacro defvar (name &rest init)
  (if init
      `(progn (if (boundp ',name) nil (setq ,name ,(car init))) ',name)
      `(progn (if (boundp ',name) nil nil) ',name)))

(defun null (x)
  (if x nil t))

(defun /= (a b)
  (null (= a b)))

(defun %v2-optional-third (spec)
  (if (cdr (cdr spec))
      (car (cdr (cdr spec)))
      nil))

; v2 keeps dotimes without retaining the public generic do macro.
(defmacro dotimes (spec &rest body)
  `((lambda (%%dotimes-loop)
      (setq %%dotimes-loop
            (lambda (,(car spec))
              (if (>= ,(car spec) ,(car (cdr spec)))
                  ,(%v2-optional-third spec)
                  (progn ,@body
                         (funcall %%dotimes-loop (+ ,(car spec) 1))))))
      (funcall %%dotimes-loop 0))
    nil))

(defmacro dolist (spec &rest body)
  `((lambda (%%dolist-loop)
      (setq %%dolist-loop
            (lambda (%%dolist-xs)
              (if %%dolist-xs
                  ((lambda (,(car spec))
                     (progn ,@body
                            (funcall %%dolist-loop (cdr %%dolist-xs))))
                   (car %%dolist-xs))
                  ,(%v2-optional-third spec))))
      (funcall %%dolist-loop ,(car (cdr spec))))
    nil))
