(defun %list*-from (items)
  (if items
      (if (cdr items)
          (cons (car items) (%list*-from (cdr items)))
          (car items))
      nil))

(defun list* (&rest items)
  (%list*-from items))

(defun %reduce-from (fn acc xs)
  (if xs
      (%reduce-from fn (funcall fn acc (car xs)) (cdr xs))
      acc))

(defun reduce (fn xs)
  (if xs
      (%reduce-from fn (car xs) (cdr xs))
      nil))

(defun every (fn xs)
  (if xs
      (if (funcall fn (car xs))
          (every fn (cdr xs))
          nil)
      't))

(defun some (fn xs)
  (if xs
      ((lambda (r)
         (if r r (some fn (cdr xs))))
       (funcall fn (car xs)))
      nil))
