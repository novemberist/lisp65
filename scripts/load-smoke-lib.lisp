(defparameter *loaded-xs* (list 3 4 5))

(defun loaded-sum (xs)
  (if xs
      (+ (car xs) (loaded-sum (cdr xs)))
      0))

(defun loaded-final ()
  (+ (loaded-sum *loaded-xs*) (length (reverse *loaded-xs*))))

(defmacro loaded-when (test &rest body)
  `(when ,test ,@body))
