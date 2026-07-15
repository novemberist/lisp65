(defun ide-apropos (needle names)
  (if names
      (if (search needle (car names))
          (cons (car names) (ide-apropos needle (cdr names)))
          (ide-apropos needle (cdr names)))
      nil))

(defun ide-prefix-matches (prefix names)
  (if names
      (if (string-prefix-p prefix (car names))
          (cons (car names) (ide-prefix-matches prefix (cdr names)))
          (ide-prefix-matches prefix (cdr names)))
      nil))

(defun %ide-common-char-prefix (left right)
  (if left
      (if right
          (if (= (car left) (car right))
              (cons (car left)
                    (%ide-common-char-prefix (cdr left) (cdr right)))
              nil)
          nil)
      nil))

(defun %ide-common-prefix-from (chars names)
  (if names
      (%ide-common-prefix-from
       (%ide-common-char-prefix chars (string->list (car names)))
       (cdr names))
      (list->string chars)))

(defun ide-complete-symbol (prefix names)
  ((lambda (matches)
     (if matches
         (%ide-common-prefix-from (string->list (car matches)) (cdr matches))
         nil))
   (ide-prefix-matches prefix names)))

(defun ide-describe-symbol (name entries)
  (if entries
      (if (string= name (car (car entries)))
          (car entries)
          (ide-describe-symbol name (cdr entries)))
      nil))

(defun ide-describe-kind (entry)
  (cadr entry))

(defun ide-describe-arity (entry)
  (cadr (cdr entry)))

(defun ide-describe-doc (entry)
  (cadr (cdr (cdr entry))))
