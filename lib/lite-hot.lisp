; Return-only lexical scan. Ordinary keys use the shared resident editor.
; Packed arithmetic avoids dividing and multiplying depth for each character.
; This step is privately inlined into the line scanner, so it never reloads
; a library object per character. The caller excludes comment state 1.
; The shared IDE scanner is unchanged.
(defun %sexp-step (c packed)
  (let ((state (mod packed 4)))
    (cond
      ((= state 3) (- packed 1))
      ((= state 2) (+ packed (if (= c 92) 1 (if (= c 34) -2 0))))
      ((= c 59) (+ packed 1))
      ((= c 34) (+ packed 2))
      (t (+ packed (if (= c 40) 4 (if (= c 41) -4 0)))))))

; Identical whole-line contract: negative depth is sticky, LF ends comments
; and consumes an escape at the end of an open string.
(defun %sexp-line-state (codes packed)
  (let* ((more (and codes (>= packed 0) (not (= (mod packed 4) 1))))
         (next (if more (%sexp-step (car codes) packed) packed)))
    (if more
        (%sexp-line-state (cdr codes) next)
        (if (< packed 0) packed
            (+ (- packed (mod packed 4))
               (if (>= (mod packed 4) 2) 2 0))))))
