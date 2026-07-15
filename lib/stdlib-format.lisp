(defun %quotient (n d q)
  (if (< n d)
      q
      (%quotient (- n d) d (1+ q))))

(defun %nonnegative-digits (n acc)
  (if (< n 10)
      (cons (+ 48 n) acc)
      (%nonnegative-digits (%quotient n 10 0)
                           (cons (+ 48 (mod n 10)) acc))))

(defun integer->string (n)
  (list->string
   (if (< n 0)
       (cons 45 (%nonnegative-digits (- 0 n) nil))
       (%nonnegative-digits n nil))))

(defun %format-display-list (x)
  (if (stringp x)
      (string->list x)
      (string->list (integer->string x))))

(defun %format-directive (chars args)
  (if chars
      (if (= (car chars) 65)
          (append (%format-display-list (car args)) (%format-chars (cdr chars) (cdr args)))
          (if (= (car chars) 97)
              (append (%format-display-list (car args)) (%format-chars (cdr chars) (cdr args)))
              (if (= (car chars) 126)
                  (cons 126 (%format-chars (cdr chars) args))
                  (cons (car chars) (%format-chars (cdr chars) args)))))
      nil))

(defun %format-chars (chars args)
  (if chars
      (if (= (car chars) 126)
          (%format-directive (cdr chars) args)
          (cons (car chars) (%format-chars (cdr chars) args)))
      nil))

(defun format (destination control &rest args)
  (if destination
      (progn
        (write-string (list->string (%format-chars (string->list control) args)))
        nil)
      (list->string (%format-chars (string->list control) args))))
