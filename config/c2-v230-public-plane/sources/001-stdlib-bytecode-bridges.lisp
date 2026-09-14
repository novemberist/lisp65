; Bytecode-only bridge entries for operators that the P0 compiler lowers
; directly, but the native REPL should reach as named compiled stdlib functions.

(defun consp (x)
  (consp x))

(defun atom (x)
  (not (consp x)))

(defun null (x)
  (if (atom x) (not x) nil))

(defun / (x y)
  (/ x y))

(defun mod (x y)
  (mod x y))

(defun remainder (x y)
  (remainder x y))

(defun screen-size ()
  (screen-size))

(defun screen-clear ()
  (screen-clear))

(defun screen-put-char (x y code &rest attr)
  (if attr
      (screen-put-char x y code (car attr))
      (screen-put-char x y code)))

(defun screen-write-string (x y text &rest attr)
  (if attr
      (screen-write-string x y text (car attr))
      (screen-write-string x y text)))

(defun read-key ()
  (read-key))

(defun poll-key ()
  (poll-key))

(defun equal (a b)
  (if (atom a)
      (eql a b)
      (if (atom b)
          nil
          (if (equal (car a) (car b))
              (equal (cdr a) (cdr b))
              nil))))
