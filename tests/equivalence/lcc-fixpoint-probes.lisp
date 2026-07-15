; P5 fixed-point probes run after the lcc source. During the tree run it compiles
; TREEWALK-lcc; im lcc-Lauf wurden lccs defuns zuvor DURCH lcc zu Bytecode kompiliert
; and shadows the tree-walk closures in symfn, so the same probes run through
; bytecode lcc. Identical output proves lcc(lcc(source)) == lcc(source).
(lcc-compile-obj (quote (defun sq (x) (* x x))))
(lcc-compile-obj (quote (defun fact (n) (if (< n 2) 1 (* n (fact (- n 1)))))))
(lcc-compile-obj (quote (lambda (a) (let ((x 2)) (+ a x)))))
(lcc-compile-obj (quote (defun adder (n) (lambda (x) (+ x n)))))
(lcc-compile-obj (quote (lambda () (cond ((> 1 2) 10) ((> 2 1) 20) (t 30)))))
(lcc-compile-obj (quote (defun loopy (n acc) (if (< n 1) acc (loopy (- n 1) (+ acc n))))))
(lcc-compile-obj (quote (lambda () (or nil 5))))
(lcc-compile-obj (quote (lambda () (quasiquote (1 (unquote (+ 1 1)))))))
