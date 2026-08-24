; Shared one-line S-expression depth scanner for the IDE and Comfort REPL.
; A negative depth is sticky: once a close parenthesis crosses the left edge,
; a later open parenthesis on the same line cannot hide the over-close.
(defun %ide-line-net-depth (codes st d)
  (if (< d 0)
      d
      (if codes
          ((lambda (c)
             (if (= st 2)
                 (%ide-line-net-depth (cdr codes) (if (= c 34) 0 2) d)
                 (if (= c 59)
                     d
                     (if (= c 34)
                         (%ide-line-net-depth (cdr codes) 2 d)
                         (%ide-line-net-depth
                          (cdr codes) 0
                          (if (= c 40) (+ d 1)
                              (if (= c 41) (- d 1) d)))))))
           (car codes))
          d)))
