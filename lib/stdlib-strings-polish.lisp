(defun string-left-trim (bag s)
  (list->string (%trim-left-list (string->list s) (string->list bag))))

(defun string-right-trim (bag s)
  (list->string (%trim-right-list (string->list s) (string->list bag))))
