(defun %format-readable-list (x)
  (if (stringp x)
      (cons 34 (append (string->list x) (list 34)))
      (%format-display-list x)))

(defun %format-display-code-p (c)
  (if (= c 65)
      't
      (if (= c 97)
          't
          (if (= c 68)
              't
              (if (= c 100) 't nil)))))

(defun %format-readable-code-p (c)
  (if (= c 83)
      't
      (if (= c 115) 't nil)))

(defun %format-directive (chars args)
  (if chars
      (if (%format-display-code-p (car chars))
          (append (%format-display-list (car args)) (%format-chars (cdr chars) (cdr args)))
          (if (%format-readable-code-p (car chars))
              (append (%format-readable-list (car args)) (%format-chars (cdr chars) (cdr args)))
              (if (= (car chars) 37)
                  (cons 10 (%format-chars (cdr chars) args))
                  (if (= (car chars) 126)
                      (cons 126 (%format-chars (cdr chars) args))
                      (cons (car chars) (%format-chars (cdr chars) args))))))
      nil))
