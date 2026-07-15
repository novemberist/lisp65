(defun %private-inline-leaf (value)
  (+ value (symbol-value (quote private-inline-global))))

(defun %private-inline-middle (value)
  (%private-inline-leaf (+ value 1)))

(defun %private-inline-pair (left right)
  (cons left (cons right nil)))

(defun private-inline-run (private-inline-global)
  (%private-inline-middle private-inline-global))

(defun private-inline-order ()
  (let ((value 0))
    (%private-inline-pair
      (progn (setq value (+ value 1)) value)
      (progn (setq value (+ value 1)) value))))

(defun private-inline-binder ()
  (let ((%private-inline-leaf 7))
    (cons %private-inline-leaf (cons (%private-inline-leaf 1) nil))))
