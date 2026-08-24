; Exact resident product helper needed by the host-only Comfort composition.
(defun %lcc-macro-p (op)
  (if (symbolp op) (eq (function-kind op) 'macro) nil))
