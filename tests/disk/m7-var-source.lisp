; m7 variable-chain payload, intentionally spans three sectors.
; It stays readable because this file is copied verbatim onto the D81.
(defun m7-var-a () 400)
(defun m7-var-b () 452)
(defun m7-var-c () (+ (m7-var-a) (m7-var-b)))
(defun m7-var-sum (n acc)
  (if (< n 1)
      acc
      (m7-var-sum (- n 1) (+ acc n))))
(defun m7-var-pad (n)
  (if (< n 1)
      0
      (+ 1 (m7-var-pad (- n 1)))))
(defun m7-var-run ()
  (+ (m7-var-c) (m7-var-sum 10 0)))
; Padding comments keep the source above two sectors while remaining harmless.
; The saved file should therefore require a three-sector D81 chain.
; The Workbench load oracle checks that all forms survived the round-trip.
