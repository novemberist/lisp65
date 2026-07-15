; Optional v2 output helpers. The resident base remains write-char/prin1;
; character-list conversion is private through the v2 codec capability.

(defun %v2-write-codes (codes)
  (if (consp codes)
      (progn
        (write-char (car codes))
        (%v2-write-codes (cdr codes)))
      nil))

(defun write-string (string)
  (%v2-write-codes (%string-codes string))
  string)

(defun write (value)
  (prin1 value))

(defun write-line (string)
  (write-string string)
  (terpri)
  string)
