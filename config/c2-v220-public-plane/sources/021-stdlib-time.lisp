; Cold Bank-2 timing form over the product-owned raster frame counter.
; The counter is read high/low/high so an IRQ between the byte reads cannot
; synthesize a torn timestamp.  A timestamp is kept as a two-cell pair because
; the full unsigned 16-bit domain does not fit in one Lisp65 fixnum.

(defun %time-read ()
  (let* ((high-before (peek 255 132))
         (low (peek 255 131))
         (high-after (peek 255 132)))
    (if (= high-before high-after)
        (cons high-before low)
        (%time-read))))

(defun %time-delta (start finish)
  (let* ((start-low (cdr start))
         (finish-low (cdr finish))
         (borrow (if (< finish-low start-low) 1 0))
         (low (if (= borrow 1)
                  (+ (- finish-low start-low) 256)
                  (- finish-low start-low)))
         (raw-high (- (car finish) (car start)))
         (wrapped-high (if (< raw-high 0) (+ raw-high 256) raw-high))
         (high (if (= borrow 1)
                   (if (= wrapped-high 0) 255 (- wrapped-high 1))
                   wrapped-high)))
    (if (>= high 64)
        (%time-error-duration-overflow)
        (+ (* high 256) low))))

; Product-owned fail-closed edge.  Keeping the named helper published makes
; both TIME and WAIT independent of an accidental DIRMISS boundary.
(defun %time-error-duration-overflow ()
  (mod 1 0))

(defmacro time (form)
  (let* ((start (gensym))
         (value (gensym))
         (finish (gensym)))
    `(let* ((,start (%time-read))
            (,value ,form)
            (,finish (%time-read)))
       (progn
         (print (%time-delta ,start ,finish))
         ,value))))
