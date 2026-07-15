; Small standalone bytecode library for the disk-lib packaging path.

(defun sq (x)
  (* x x))

(defun disk-add3 (a b c)
  (+ (+ a b) c))

(defun disk-tag ()
  '(disk-lib "ok" 7))
