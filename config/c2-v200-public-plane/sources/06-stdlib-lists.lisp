(defun assq (key alist)
  (assoc key alist))

(defun %take (xs n)
  (%take-into xs n nil))

(defun %take-into (xs n acc)
  (if (<= n 0)
      (reverse acc)
      (if xs
          (%take-into (cdr xs) (1- n) (cons (car xs) acc))
          (reverse acc))))

(defun butlast (xs &rest maybe-n)
  (%take xs (- (length xs) (if maybe-n (car maybe-n) 1))))

(defun %any-null (lists)
  (if lists
      (if (car lists)
          (%any-null (cdr lists))
          't)
      nil))

(defun %cars (lists)
  (if lists
      (cons (car (car lists)) (%cars (cdr lists)))
      nil))

(defun %cdrs (lists)
  (if lists
      (cons (cdr (car lists)) (%cdrs (cdr lists)))
      nil))

(defun mapcar (fn &rest lists)
  (if lists
      (%mapcar-into fn lists nil)
      nil))

(defun %mapcar-into (fn lists acc)
  (if lists
      (if (%any-null lists)
          (reverse acc)
          (%mapcar-into fn
                        (%cdrs lists)
                        (cons (apply fn (%cars lists)) acc)))
      (reverse acc)))

(defun mapcan (fn &rest lists)
  (apply (function append) (apply (function mapcar) (cons fn lists))))

(defun remove-if (pred xs)
  (%remove-if-into pred xs nil))

(defun %remove-if-into (pred xs acc)
  (if xs
      (if (funcall pred (car xs))
          (%remove-if-into pred (cdr xs) acc)
          (%remove-if-into pred (cdr xs) (cons (car xs) acc)))
      (reverse acc)))

(defun remove-if-not (pred xs)
  (%remove-if-not-into pred xs nil))

(defun %remove-if-not-into (pred xs acc)
  (if xs
      (if (funcall pred (car xs))
          (%remove-if-not-into pred (cdr xs) (cons (car xs) acc))
          (%remove-if-not-into pred (cdr xs) acc))
      (reverse acc)))

(defun copy-list (xs)
  (reverse (reverse xs)))

(defun find-if (pred xs)
  (if xs
      (if (funcall pred (car xs))
          (car xs)
          (find-if pred (cdr xs)))
      nil))

(defun %position-if-from (pred xs n)
  (if xs
      (if (funcall pred (car xs))
          n
          (%position-if-from pred (cdr xs) (1+ n)))
      nil))

(defun position-if (pred xs)
  (%position-if-from pred xs 0))

(defun count (item xs)
  (%count-from item xs 0))

(defun %count-from (item xs n)
  (if xs
      (%count-from item
                   (cdr xs)
                   (if (eql item (car xs)) (1+ n) n))
      n))

(defun count-if (pred xs)
  (%count-if-from pred xs 0))

(defun %count-if-from (pred xs n)
  (if xs
      (%count-if-from pred
                      (cdr xs)
                      (if (funcall pred (car xs)) (1+ n) n))
      n))
