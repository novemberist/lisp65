; Dialect-v2 on-demand string library. Character-code lists are private
; construction intermediates; the public representation remains packed strings.

(defun %v2-upcase-code (code)
  (if (and (>= code 97) (<= code 122))
      (- code 32)
      code))

(defun %v2-downcase-code (code)
  (if (and (>= code 65) (<= code 90))
      (+ code 32)
      code))

(defun %v2-map-codes-into (function codes acc)
  (if codes
      (%v2-map-codes-into function (cdr codes)
                          (cons (funcall function (car codes)) acc))
      (nreverse acc)))

(defun %v2-case-fold-codes (string)
  (%v2-map-codes-into (function %v2-upcase-code)
                      (%string-codes string) nil))

(defun %v2-code-list= (left right)
  (if left
      (if right
          (if (= (car left) (car right))
              (%v2-code-list= (cdr left) (cdr right))
              nil)
          nil)
      (null right)))

(defun string-equal (left right)
  (%v2-code-list= (%v2-case-fold-codes left)
                  (%v2-case-fold-codes right)))

(defun %v2-code-prefix-p (prefix codes)
  (if prefix
      (if codes
          (if (= (car prefix) (car codes))
              (%v2-code-prefix-p (cdr prefix) (cdr codes))
              nil)
          nil)
      t))

(defun string-prefix-p (prefix string)
  (%v2-code-prefix-p (%string-codes prefix) (%string-codes string)))

(defun %v2-drop-codes (codes count)
  (if (> count 0)
      (%v2-drop-codes (cdr codes) (- count 1))
      codes))

(defun string-suffix-p (suffix string)
  (if (> (string-length suffix) (string-length string))
      nil
      (%v2-code-list=
       (%string-codes suffix)
       (%v2-drop-codes (%string-codes string)
                       (- (string-length string) (string-length suffix))))))

(defun %v2-search-codes (needle codes index)
  (if needle
      (if codes
          (if (%v2-code-prefix-p needle codes)
              index
              (%v2-search-codes needle (cdr codes) (+ index 1)))
          nil)
      0))

(defun search (needle string)
  (%v2-search-codes (%string-codes needle) (%string-codes string) 0))

(defun %v2-code-member-p (code codes)
  (if codes
      (if (= code (car codes))
          t
          (%v2-code-member-p code (cdr codes)))
      nil))

(defun %v2-trim-left-codes (codes bag)
  (if codes
      (if (%v2-code-member-p (car codes) bag)
          (%v2-trim-left-codes (cdr codes) bag)
          codes)
      nil))

(defun %v2-trim-right-codes (codes bag)
  (nreverse (%v2-trim-left-codes (nreverse codes) bag)))

(defun string-trim (bag string)
  ((lambda (bag-codes)
     (%string-from-codes
      (%v2-trim-right-codes
       (%v2-trim-left-codes (%string-codes string) bag-codes)
       bag-codes)))
   (%string-codes bag)))

(defun string-upcase (string)
  (%string-from-codes
   (%v2-map-codes-into (function %v2-upcase-code)
                       (%string-codes string) nil)))

(defun string-downcase (string)
  (%string-from-codes
   (%v2-map-codes-into (function %v2-downcase-code)
                       (%string-codes string) nil)))

(defun char-upcase (code)
  (%v2-upcase-code code))

(defun char-downcase (code)
  (%v2-downcase-code code))

(defun char (string index)
  (string-ref string index))

(defun char->string (code)
  (%string-from-codes (cons code nil)))
