; Dialect-v2 on-demand lists library. Public exports are contract-derived;
; percent-prefixed helpers remain private to the artifact.

(defun %v2-library-reverse-into (xs acc)
  (if (consp xs)
      (%v2-library-reverse-into (cdr xs) (cons (car xs) acc))
      acc))

(defun reverse (xs)
  (%v2-library-reverse-into xs nil))

(defun %v2-take-into (xs n acc)
  (if (> n 0)
      (if (consp xs)
          (%v2-take-into (cdr xs) (- n 1) (cons (car xs) acc))
          (reverse acc))
      (reverse acc)))

(defun butlast (xs &optional n)
  (%v2-take-into xs (- (length xs) (if n n 1)) nil))

(defun copy-list (xs)
  (reverse (reverse xs)))

(defun every (predicate xs)
  (if (consp xs)
      (if (funcall predicate (car xs))
          (every predicate (cdr xs))
          nil)
      t))

(defun %v2-getf (plist key default)
  (if (consp plist)
      (if (consp (cdr plist))
          (if (eq (car plist) key)
              (car (cdr plist))
              (%v2-getf (cdr (cdr plist)) key default))
          default)
      default))

(defun getf (plist key &optional default)
  (%v2-getf plist key default))

(defun last (xs)
  (if (consp xs)
      (if (consp (cdr xs)) (last (cdr xs)) xs)
      nil))

(defun list* (&rest items)
  (if (consp items)
      (if (consp (cdr items))
          (cons (car items) (apply (function list*) (cdr items)))
          (car items))
      nil))

(defun mapcan (function &rest lists)
  (apply (function append)
         (apply (function mapcar) (cons function lists))))

(defun %v2-reduce-from (function acc xs)
  (if (consp xs)
      (%v2-reduce-from function
                       (funcall function acc (car xs))
                       (cdr xs))
      acc))

(defun reduce (function xs)
  (if (consp xs)
      (%v2-reduce-from function (car xs) (cdr xs))
      nil))

(defun %v2-append2-rev (reversed tail)
  (if (consp reversed)
      (%v2-append2-rev (cdr reversed) (cons (car reversed) tail))
      tail))

(defun %v2-remf-into (plist key acc)
  (if (consp plist)
      (if (consp (cdr plist))
          (if (eq (car plist) key)
              (%v2-append2-rev acc (cdr (cdr plist)))
              (%v2-remf-into (cdr (cdr plist))
                             key
                             (cons (car (cdr plist))
                                   (cons (car plist) acc))))
          (reverse acc))
      (reverse acc)))

(defun remf (plist key)
  (%v2-remf-into plist key nil))

(defun some (predicate xs)
  (if (consp xs)
      ((lambda (result)
         (if result result (some predicate (cdr xs))))
       (funcall predicate (car xs)))
      nil))

(defun %v2-count-from (predicate xs count)
  (if (consp xs)
      (%v2-count-from predicate
                      (cdr xs)
                      (if (funcall predicate (car xs)) (+ count 1) count))
      (if xs (%list-malformed-error) count)))

(defun count (predicate xs)
  (%v2-count-from predicate xs 0))

(defun %v2-position-from (predicate xs index)
  (if (consp xs)
      (if (funcall predicate (car xs))
          index
          (%v2-position-from predicate (cdr xs) (+ index 1)))
      (if xs (%list-malformed-error) nil)))

(defun position (predicate xs)
  (%v2-position-from predicate xs 0))
