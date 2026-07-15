; case equivalence: disk macro route vs. compiler only; CONTROL_SF intentionally has no sf_case.
(case 2 (1 10) (2 20) (3 30))
(case 9 (1 10) (t 77))
(case (+ 1 1) (2 (+ 10 10)))
(case 5 (1 10))
(let ((x 3)) (case x (3 (* x x))))
(case (quote z) (a 1) (z 9) (t 3))
