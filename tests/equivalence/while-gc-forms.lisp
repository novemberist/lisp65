; Both the test and the body allocate.  The retained list remains live across
; every collection, while the one-cell test wrapper becomes garbage.
(let ((i 0) (kept nil))
  (progn
    (while (car (cons (< i 5000) nil))
      (setq kept (cons i kept))
      (setq i (+ i 1)))
    (+ i (car kept))))
