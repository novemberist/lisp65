; Cold Bank-2 line input over the public key-event and screen primitives.
; The editor owns the last screen row and keeps a one-row tail viewport there;
; this gives Workbench and Ship Runtime one implementation without a native
; cursor seam.  Codes stay reversed, so DEL is a constant-time cdr and RETURN
; can hand the owned chain to nreverse without allocating a second list.

(defun %read-line-clear-from (column columns row)
  (if (< column columns)
      (progn
        (screen-put-char column row 32 1)
        (%read-line-clear-from (+ column 1) columns row))
      nil))

(defun %read-line-render-reverse (codes column row)
  (if (and codes (>= column 0))
      (progn
        (screen-put-char column row (car codes) 1)
        (%read-line-render-reverse (cdr codes) (- column 1) row))
      nil))

(defun %read-line-finish (codes)
  (progn
    (write-char 10)
    (%string-from-codes (nreverse codes))))

(defun %read-line-loop (codes length columns row)
  (let* ((event (key-event 1))
         (code (cadr event)))
    (if (= code 13)
        (%read-line-finish codes)
        (if (or (= code 20) (= code 127))
            (if (> length 0)
                (let* ((next-codes (cdr codes))
                       (next-length (- length 1)))
                  (progn
                    (if (>= next-length columns)
                        (%read-line-render-reverse next-codes (- columns 1) row)
                        (screen-put-char next-length row 32 1))
                    (%read-line-loop
                     next-codes next-length columns row)))
                (%read-line-loop codes length columns row))
            (if (and (>= code 32) (<= code 126))
                (if (< length 250)
                    (let* ((next-codes (cons code codes))
                           (next-length (+ length 1)))
                      (progn
                        (if (<= next-length columns)
                            (screen-put-char length row code 1)
                            (%read-line-render-reverse next-codes (- columns 1) row))
                        (%read-line-loop
                         next-codes next-length columns row)))
                    (%read-line-loop codes length columns row))
                (%read-line-loop codes length columns row))))))

(defun read-line ()
  (let* ((size (screen-size))
         (columns (car size))
         (row (- (car (cdr size)) 1)))
    (progn
      (%read-line-clear-from 0 columns row)
      (%read-line-loop nil 0 columns row))))
