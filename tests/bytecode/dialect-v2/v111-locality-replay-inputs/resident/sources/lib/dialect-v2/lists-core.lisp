; Generated from lib/dialect-v2/lists-core.lisp; do not edit.

(defun %v2-reverse-into (xs acc)
  (if (consp xs)
      (%v2-reverse-into (cdr xs) (cons (car xs) acc))
      acc))

(defun %v2-filter-into (predicate xs acc)
  (if (consp xs)
      (if (funcall predicate (car xs))
          (%v2-filter-into predicate (cdr xs) (cons (car xs) acc))
          (%v2-filter-into predicate (cdr xs) acc))
      (if xs (%list-malformed-error) (%v2-reverse-into acc nil))))

(defun filter (predicate xs)
  (%v2-filter-into predicate xs nil))
