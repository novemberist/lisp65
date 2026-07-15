; lisp65 demo 06: fixnum and numeric Stdlib surface.
;
; This intentionally touches division, signed MOD semantics, ABS/SIGNUM,
; predicates and CLAMP.  It is small enough to run often after arithmetic or VM
; opcode changes.
;
;   (compile-file "dnum" "fnum")
;   (load "fnum")
;   (demo-numbers-run)

(defun demo-number-row (x)
  (list x
        (abs x)
        (signum x)
        (evenp x)
        (oddp x)
        (clamp x 0 10)
        (/ (* x 6) 3)
        (mod x 5)))

(defun demo-number-score ()
  (+ (+ (+ (/ 64 4)
           (abs -9))
        (+ (clamp 20 0 6)
           (mod -3 5)))
     (+ (if (evenp 8) 4 0)
        (if (oddp 7) 5 0))))

(defun demo-numbers-run ()
  (demo-number-score))
