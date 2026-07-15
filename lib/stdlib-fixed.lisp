(defun fx-scale ()
  128)

(defun integer->fx (n)
  (* n (fx-scale)))

(defun fx (whole &rest frac)
  (+ (integer->fx whole) (if frac (car frac) 0)))

(defun %fx-nonnegative-quotient (n d q)
  (if (< n d)
      q
      (%fx-nonnegative-quotient (- n d) d (1+ q))))

(defun %fx-abs (x)
  (if (< x 0) (- 0 x) x))

(defun fx->integer (x)
  (if (< x 0)
      (- 0 (%fx-nonnegative-quotient (%fx-abs x) (fx-scale) 0))
      (%fx-nonnegative-quotient x (fx-scale) 0)))

(defun fx+ (&rest xs)
  (apply (function +) xs))

(defun %fx-subtract-from (acc xs)
  (if xs
      (%fx-subtract-from (- acc (car xs)) (cdr xs))
      acc))

(defun fx- (x &rest xs)
  (if xs
      (%fx-subtract-from x xs)
      (- 0 x)))

(defun %fx-mul-unsigned-loop (a b acc rem)
  (if (> b 0)
      ((lambda (sum)
         (%fx-mul-unsigned-loop a
                                (1- b)
                                (+ acc (%fx-nonnegative-quotient sum (fx-scale) 0))
                                (mod sum (fx-scale))))
       (+ rem a))
      acc))

(defun %fx-mul-unsigned (a b)
  (%fx-mul-unsigned-loop a b 0 0))

(defun fx* (a b)
  ((lambda (mag)
     (if (< a 0)
         (if (< b 0) mag (- 0 mag))
         (if (< b 0) (- 0 mag) mag)))
   (%fx-mul-unsigned (%fx-abs a) (%fx-abs b))))

(defun %fx-div-scale-loop (a b n acc rem)
  (if (> n 0)
      ((lambda (sum)
         (%fx-div-scale-loop a
                             b
                             (1- n)
                             (+ acc (%fx-nonnegative-quotient sum b 0))
                             (mod sum b)))
       (+ rem a))
      acc))

(defun %fx-div-unsigned (a b)
  (%fx-div-scale-loop a b (fx-scale) 0 0))

(defun fx/ (a b)
  ((lambda (mag)
     (if (< a 0)
         (if (< b 0) mag (- 0 mag))
         (if (< b 0) (- 0 mag) mag)))
   (%fx-div-unsigned (%fx-abs a) (%fx-abs b))))

(defun fx< (a b)
  (< a b))
