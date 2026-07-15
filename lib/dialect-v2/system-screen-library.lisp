; Optional user-facing screen surface. These wrappers compile to the native
; CALLPRIMs; IDE rendering remains independent of this library's symbols.

(defun screen-size ()
  (screen-size))

(defun screen-clear ()
  (screen-clear))

(defun screen-put-char (x y code &optional attr)
  (if attr
      (screen-put-char x y code attr)
      (screen-put-char x y code)))

(defun screen-write-string (x y string &optional attr)
  (if attr
      (screen-write-string x y string attr)
      (screen-write-string x y string)))
