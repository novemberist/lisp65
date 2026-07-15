; Extra bytecode bridges for the P6c Ein-Suite diet. These names are supplied
; by compiled stdlib entries there, so the resident Treewalk C primitive cases
; can be gated out without losing the REPL-visible function surface.

(defun %add-list (xs acc)
  (if xs
      (%add-list (cdr xs) (+ acc (car xs)))
      acc))

(defun + (&rest xs)
  (%add-list xs 0))

(defun %mul-list (xs acc)
  (if xs
      (%mul-list (cdr xs) (* acc (car xs)))
      acc))

(defun * (&rest xs)
  (%mul-list xs 1))

(defun %sub-list (xs acc)
  (if xs
      (%sub-list (cdr xs) (- acc (car xs)))
      acc))

(defun - (&rest xs)
  (if xs
      (if (cdr xs)
          (%sub-list (cdr xs) (car xs))
          (- 0 (car xs)))
      0))

(defun %lt-chain (prev xs)
  (if xs
      (if (< prev (car xs))
          (%lt-chain (car xs) (cdr xs))
          nil)
      t))

(defun < (&rest xs)
  (if xs (%lt-chain (car xs) (cdr xs)) t))

(defun %gt-chain (prev xs)
  (if xs
      (if (> prev (car xs))
          (%gt-chain (car xs) (cdr xs))
          nil)
      t))

(defun > (&rest xs)
  (if xs (%gt-chain (car xs) (cdr xs)) t))

(defun %num=-chain (prev xs)
  (if xs
      (if (= prev (car xs))
          (%num=-chain (car xs) (cdr xs))
          nil)
      t))

(defun = (&rest xs)
  (if xs (%num=-chain (car xs) (cdr xs)) t))

(defun %le-chain (prev xs)
  (if xs
      (if (<= prev (car xs))
          (%le-chain (car xs) (cdr xs))
          nil)
      t))

(defun <= (&rest xs)
  (if xs (%le-chain (car xs) (cdr xs)) t))

(defun %ge-chain (prev xs)
  (if xs
      (if (>= prev (car xs))
          (%ge-chain (car xs) (cdr xs))
          nil)
      t))

(defun >= (&rest xs)
  (if xs (%ge-chain (car xs) (cdr xs)) t))

(defun cons (a b)
  (cons a b))

(defun car (x)
  (car x))

(defun cdr (x)
  (cdr x))

(defun eq (a b)
  (eq a b))

(defun eql (a b)
  (eql a b))

(defun stringp (x)
  (stringp x))

(defun numberp (x)
  (numberp x))

(defun symbolp (x)
  (symbolp x))

(defun string->list (s)
  (string->list s))

(defun list->string (xs)
  (list->string xs))

(defun string-length (s)
  (string-length s))

(defun string-ref (s i)
  (string-ref s i))
