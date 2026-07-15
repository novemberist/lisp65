(defun %max-from (best xs)
  (if xs
      (%max-from (if (> (car xs) best) (car xs) best) (cdr xs))
      best))

(defun max (x &rest xs)
  (%max-from x xs))

(defun %min-from (best xs)
  (if xs
      (%min-from (if (< (car xs) best) (car xs) best) (cdr xs))
      best))

(defun min (x &rest xs)
  (%min-from x xs))

(defun abs (x)
  (if (< x 0) (- 0 x) x))

(defun signum (x)
  (if (< x 0)
      -1
      (if (> x 0) 1 0)))

(defun evenp (x)
  (= (mod x 2) 0))

(defun oddp (x)
  (not (evenp x)))

(defun integerp (x)
  (numberp x))

(defun nonnegativep (x)
  (>= x 0))

(defun nonpositivep (x)
  (<= x 0))

(defun clamp (x low high)
  (if (< x low)
      low
      (if (> x high) high x)))
