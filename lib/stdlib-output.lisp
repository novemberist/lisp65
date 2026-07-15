; Output wrappers that do not need resident Treewalk primitive cases.
; The native base remains write-char/prin1.

(defun %write-string-codes (codes)
  (if codes
      (progn (write-char (car codes))
             (%write-string-codes (cdr codes)))
      nil))

(defun write-string (s)
  (%write-string-codes (string->list s))
  s)

(defun terpri ()
  (write-char 10)
  nil)

(defun princ (x)
  (if (stringp x)
      (write-string x)
      (prin1 x)))

(defun write (x)
  (prin1 x))

(defun print (x)
  (terpri)
  (prin1 x)
  (write-char 32)
  x)

(defun write-line (s)
  (write-string s)
  (terpri)
  s)
