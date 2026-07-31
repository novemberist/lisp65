; Host dry-run for the exact product-side soak helpers.
(defun %s (n)
  (let ((i 0))
    (progn
      (while (< i n)
        (if (= 4 (length (eval (quote (list 1 2 3 4)))))
            nil
            (setq *sm* (+ *sm* 1)))
        (setq *sc* (+ *sc* 1))
        (setq i (+ i 1)))
      t)))
(defun %sr ()
  (list *sc* *sm*
        (peek 185 240) (peek 185 241)
        (peek 0 143) (peek 0 63) (peek 0 64)))
