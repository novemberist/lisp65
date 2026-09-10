; v2.0 Tier 1: strict finite proper-list spines.

(defun %append2 (a b)
  (%append2-rev (reverse a) b))

(defun %append2-rev (ra b)
  (if (consp ra)
      (%append2-rev (cdr ra) (cons (car ra) b))
      (if ra (%list-malformed-error) b)))

(defun append (&rest lists)
  ((lambda (rev-lists)
     (if (consp rev-lists)
         (progn
           (length (car rev-lists))
           (%append-lists (cdr rev-lists) (car rev-lists)))
         (if rev-lists (%list-malformed-error) nil)))
   (reverse lists)))

(defun %append-lists (rev-lists acc)
  (if (consp rev-lists)
      (%append-lists (cdr rev-lists) (%append2 (car rev-lists) acc))
      (if rev-lists (%list-malformed-error) acc)))

(defun length (xs)
  (%length-from xs 0))

(defun %length-from (xs n)
  (if (consp xs)
      (%length-from (cdr xs) (1+ n))
      (if xs (%list-malformed-error) n)))

(defun nth (n xs)
  (if (numberp n)
      (if (< n 0)
          (%list-malformed-error)
          (if (zerop n)
              (if (consp xs) (car xs) (if xs (%list-malformed-error) nil))
              (if (consp xs)
                  (nth (1- n) (cdr xs))
                  (if xs (%list-malformed-error) nil))))
      (%list-malformed-error)))

(defun nthcdr (n xs)
  (if (numberp n)
      (if (< n 0)
          (%list-malformed-error)
          (if (zerop n)
              (progn (length xs) xs)
              (if (consp xs)
                  (nthcdr (1- n) (cdr xs))
                  (if xs (%list-malformed-error) nil))))
      (%list-malformed-error)))

(defun %reverse-into (xs acc)
  (if (consp xs)
      (%reverse-into (cdr xs) (cons (car xs) acc))
      (if xs (%list-malformed-error) acc)))

(defun reverse (xs)
  (%reverse-into xs nil))

(defun last (xs)
  (if (consp xs)
      (if (consp (cdr xs))
          (last (cdr xs))
          (if (cdr xs) (%list-malformed-error) xs))
      (if xs (%list-malformed-error) nil)))

(defun member (item xs)
  (if (consp xs)
      (if (eql item (car xs)) xs (member item (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun assoc (key alist)
  (if (consp alist)
      (if (consp (car alist))
          (if (eql key (car (car alist)))
              (car alist)
              (assoc key (cdr alist)))
          (%list-malformed-error))
      (if alist (%list-malformed-error) nil)))

(defun %any-null (lists)
  (if (consp lists)
      (if (consp (car lists))
          (%any-null (cdr lists))
          (if (car lists) (%list-malformed-error) 't))
      (if lists (%list-malformed-error) nil)))

(defun %cars (lists)
  (if (consp lists)
      (cons (car (car lists)) (%cars (cdr lists)))
      (if lists (%list-malformed-error) nil)))

(defun %cdrs (lists)
  (if (consp lists)
      (cons (cdr (car lists)) (%cdrs (cdr lists)))
      (if lists (%list-malformed-error) nil)))

(defun mapcar (fn &rest lists)
  (if (consp lists)
      (%mapcar-into fn lists nil)
      (if lists (%list-malformed-error) nil)))

(defun %mapcar-into (fn lists acc)
  (if (consp lists)
      (if (%any-null lists)
          (reverse acc)
          (%mapcar-into fn (%cdrs lists)
                        (cons (apply fn (%cars lists)) acc)))
      (if lists (%list-malformed-error) (reverse acc))))

(defun mapcan (fn &rest lists)
  (apply (function append) (apply (function mapcar) (cons fn lists))))

(defun %mapc (fn xs)
  (if (consp xs)
      (progn (funcall fn (car xs)) (%mapc fn (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun mapc (fn xs)
  (%mapc fn xs)
  xs)

(defun find (item xs)
  (if (consp xs)
      (if (eql item (car xs)) (car xs) (find item (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun %position-from (item xs n)
  (if (consp xs)
      (if (eql item (car xs)) n (%position-from item (cdr xs) (1+ n)))
      (if xs (%list-malformed-error) nil)))

(defun position (item xs)
  (%position-from item xs 0))

(defun butlast (xs &rest maybe-n)
  (%take xs (- (length xs) (if maybe-n (car maybe-n) 1))))

(defun copy-list (xs)
  (reverse (reverse xs)))

(defun count (item xs)
  (%count-from item xs 0))

(defun %count-from (item xs n)
  (if (consp xs)
      (%count-from item (cdr xs) (if (eql item (car xs)) (1+ n) n))
      (if xs (%list-malformed-error) n)))

(defun %reduce-from (fn acc xs)
  (if (consp xs)
      (%reduce-from fn (funcall fn acc (car xs)) (cdr xs))
      (if xs (%list-malformed-error) acc)))

(defun reduce (fn xs)
  (if (consp xs)
      (%reduce-from fn (car xs) (cdr xs))
      (if xs (%list-malformed-error) nil)))

(defun every (fn xs)
  (if (consp xs)
      (if (funcall fn (car xs)) (every fn (cdr xs)) nil)
      (if xs (%list-malformed-error) 't)))

(defun some (fn xs)
  (if (consp xs)
      ((lambda (r) (if r r (some fn (cdr xs)))) (funcall fn (car xs)))
      (if xs (%list-malformed-error) nil)))

(defun %getf (plist key default)
  (if (consp plist)
      (if (consp (cdr plist))
          (if (eql (car plist) key)
              (car (cdr plist))
              (%getf (cdr (cdr plist)) key default))
          (%list-malformed-error))
      (if plist (%list-malformed-error) default)))

(defun getf (plist key &rest default)
  (%getf plist key (if default (car default) nil)))

(defun remf (plist key)
  (%remf-into plist key nil))

(defun %remf-into (plist key acc)
  (if (consp plist)
      (if (consp (cdr plist))
          (if (eql (car plist) key)
              (%append2-rev acc (cdr (cdr plist)))
              (%remf-into (cdr (cdr plist)) key
                          (cons (car (cdr plist)) (cons (car plist) acc))))
          (%list-malformed-error))
      (if plist (%list-malformed-error) (reverse acc))))
