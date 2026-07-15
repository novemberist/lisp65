(defun %ide-budget-string ()
  (string-append (number->string (symbol-count))
                 "/"
                 (number->string (symbol-max))))
