; Dialect-v2 resident list-search surface. Circular lists are outside the
; contract; finite malformed spines and non-cons alist entries cannot match.

(defun list (&rest xs)
  xs)

(defun %v2-reverse-into (xs acc)
  (if (consp xs)
      (%v2-reverse-into (cdr xs) (cons (car xs) acc))
      acc))

(defun %v2-prepend-reversed (reversed tail)
  (if (consp reversed)
      (%v2-prepend-reversed (cdr reversed) (cons (car reversed) tail))
      tail))

(defun %v2-append2 (left right)
  (%v2-prepend-reversed (%v2-reverse-into left nil) right))

(defun append (&rest lists)
  (if (consp lists)
      (if (consp (cdr lists))
          (%v2-append2 (car lists) (apply (function append) (cdr lists)))
          (car lists))
      nil))

(defun %v2-length-from (xs n)
  (if (consp xs)
      (%v2-length-from (cdr xs) (+ n 1))
      n))

(defun length (xs)
  (%v2-length-from xs 0))

(defun %v2-nth (n xs)
  (if (= n 0)
      (car xs)
      (%v2-nth (- n 1) (cdr xs))))

(defun nth (n xs)
  (if (numberp n)
      (if (< n 0) (%list-malformed-error) (%v2-nth n xs))
      (%list-malformed-error)))

(defun %v2-nthcdr (n xs)
  (if (= n 0)
      xs
      (%v2-nthcdr (- n 1) (cdr xs))))

(defun nthcdr (n xs)
  (if (numberp n)
      (if (< n 0) (%list-malformed-error) (%v2-nthcdr n xs))
      (%list-malformed-error)))

(defun %v2-any-null (lists)
  (if (consp lists)
      (if (consp (car lists)) (%v2-any-null (cdr lists)) t)
      nil))

(defun %v2-cars (lists)
  (if (consp lists)
      (cons (car (car lists)) (%v2-cars (cdr lists)))
      nil))

(defun %v2-cdrs (lists)
  (if (consp lists)
      (cons (cdr (car lists)) (%v2-cdrs (cdr lists)))
      nil))

(defun %v2-mapcar-into (function lists acc)
  (if (consp lists)
      (if (%v2-any-null lists)
          (%v2-reverse-into acc nil)
          (%v2-mapcar-into function
                           (%v2-cdrs lists)
                           (cons (apply function (%v2-cars lists)) acc)))
      (%v2-reverse-into acc nil)))

(defun mapcar (function &rest lists)
  (%v2-mapcar-into function lists nil))

(defun %v2-mapc (function xs)
  (if (consp xs)
      (progn (funcall function (car xs))
             (%v2-mapc function (cdr xs)))
      nil))

(defun mapc (function xs)
  (%v2-mapc function xs)
  xs)

(defun member (item xs &optional test)
  (if (consp xs)
      (if (funcall (if test test (function eq)) item (car xs))
          xs
          (member item (cdr xs) test))
      (if xs (%list-malformed-error) nil)))

(defun assoc (key alist &optional test)
  (if (consp alist)
      ((lambda (entry)
         (if (consp entry)
             (if (funcall (if test test (function eq)) key (car entry))
                 entry
                 (assoc key (cdr alist) test))
             (%list-malformed-error)))
       (car alist))
      (if alist (%list-malformed-error) nil)))

(defun find (predicate xs)
  (if (consp xs)
      (if (funcall predicate (car xs))
          (car xs)
          (find predicate (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun %v2-filter-into (predicate xs acc)
  (if (consp xs)
      (if (funcall predicate (car xs))
          (%v2-filter-into predicate (cdr xs) (cons (car xs) acc))
          (%v2-filter-into predicate (cdr xs) acc))
      (if xs (%list-malformed-error) (%v2-reverse-into acc nil))))

(defun filter (predicate xs)
  (%v2-filter-into predicate xs nil))
