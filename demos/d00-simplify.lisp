; lisp65 demo 00: a tiny symbolic simplifier.
;
; The file is intentionally plain source.  It contains only top-level DEFUN
; forms, so it can be inspected in the IDE and compiled on the MEGA65 with
; COMPILE-FILE.  Try:
;
;   (compile-file "dsimp" "fsimp")
;   (load "fsimp")
;   (demo-simplify-run)

(defun demo-simplify-add (a b)
  (if (eql a 0)
      b
      (if (eql b 0)
          a
          (if (and (numberp a) (numberp b))
              (+ a b)
              (list '+ a b)))))

(defun demo-simplify-mul (a b)
  (if (eql a 0)
      0
      (if (eql b 0)
          0
          (if (eql a 1)
              b
              (if (eql b 1)
                  a
                  (if (and (numberp a) (numberp b))
                      (* a b)
                      (list '* a b)))))))

(defun demo-simplify-left (expr)
  (car (cdr expr)))

(defun demo-simplify-right (expr)
  (car (cdr (cdr expr))))

(defun demo-simplify (expr)
  (if (atom expr)
      expr
      (if (eq (car expr) '+)
          (demo-simplify-add (demo-simplify (demo-simplify-left expr))
                             (demo-simplify (demo-simplify-right expr)))
          (if (eq (car expr) '*)
              (demo-simplify-mul (demo-simplify (demo-simplify-left expr))
                                 (demo-simplify (demo-simplify-right expr)))
              expr))))

(defun demo-simplify-run ()
  (demo-simplify (list '+ 0 (list '* 1 (list '+ 20 22)))))
