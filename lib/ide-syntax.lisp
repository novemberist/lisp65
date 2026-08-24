;; lisp65 IDE: narrow S-expression helpers for automatic indentation and
;; delta rendering. The former syntax-overpaint path is removed from the
;; Workbench profile: highlighting was disabled, expensive in the render hot
;; path, and occupied several disk-library slots. The active surface remains
;; plain rendering plus indentation.

;; Render a CODE line. Syntax overpainting is removed from the Workbench
;; profile; the product path draws only the base line in default white.
(defun %ide-render-code-line-at (text y columns attr)
  ;; HIGHLIGHTING OFF and attr=1: no syntax colors, just the same base color as
  ;; scr_init. This preserves the fast bulk-padding path; attr=-1 would retain
  ;; color but cannot express pad-to-EOL in the current screen-write-string ABI.
  (ide-render-line-at text y columns 1))

;; Parenthesis depth BEFORE line n is the sum of the net depths of lines
;; 0..n-1, never negative.
(defun %ide-depth-above (lines n d)
  (if (and lines (> n 0))
      (%ide-depth-above (cdr lines) (- n 1)
                        (%ide-line-net-depth (string->list (car lines)) 0 d))
      (if (> d 0) d 0)))

;; Insert n spaces at point (functional; ide-insert-char uses the O(1) line cache).
(defun %ide-insert-spaces (buffer n)
  (if (> n 0)
      (%ide-insert-spaces (ide-insert-char buffer 32) (- n 1))
      buffer))

;; RETURN with automatic indentation: split the line, then indent the NEW line
;; to twice the parenthesis depth (simple lisp-mode depth rule, capped at 10
;; levels = 20 columns). The depth scan runs ONLY on RETURN (O(buffer)), never
;; on each keystroke.
(defun ide-split-line-indented (buffer)
  ((lambda (split)
     ((lambda (d)
        (%ide-insert-spaces split (* 2 (if (> d 10) 10 d))))
      (%ide-depth-above (ide-buffer-lines split)
                        (ide-point-line (ide-buffer-point split))
                        0)))
   (ide-split-line buffer)))

;; Draw the suffix from column `from` plus (pad+1) erasure spaces: pad is the
;; line shrinkage from deletes in the burst, and +1 covers the cell AFTER the
;; old line end where the previous render left its cursor block. Without it,
;; backspace left one white block per key (user finding 2026-07-06). At the
;; boundary, the driver clips x.
(defun %ide-render-code-suffix-at (text y from pad)
  ((lambda (len)
     (progn
       (%ide-render-string-codes-at text from y 1 len)
       (%ide-pad-eol len (+ len (+ pad 1)) y 1)))
   (string-length text)))
