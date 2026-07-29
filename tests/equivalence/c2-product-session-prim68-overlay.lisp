(defun %is (n) (if (> n 0) (progn (intern "abc") (%is (- n 1))) t))
(%is 3)
