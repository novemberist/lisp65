; lisp65 demo 02: higher-order calls and non-capturing lambdas.
;
; P0 currently supports lambdas where no heap environment is needed.  This
; keeps the demo inside today's MVP while still exercising FUNCALL, MAPCAR and
; REDUCE.  Capturing closure objects are a deliberate post-MVP boundary.
;
;   (compile-file "dlam" "flam")
;   (load "flam")
;   (demo-lambda-run)

(defun demo-apply-twice (fn x)
  (funcall fn (funcall fn x)))

(defun demo-lambda-bump-list (xs)
  (mapcar (lambda (x) (+ x 1)) xs))

(defun demo-lambda-sum (xs)
  (reduce (function +) xs))

(defun demo-lambda-run ()
  (+ (demo-apply-twice (lambda (x) (+ x 11)) 19)
     (demo-lambda-sum (demo-lambda-bump-list (list -1 0)))))
