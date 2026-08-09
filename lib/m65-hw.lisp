; Synchronous MEGA65 pilot.  All code stays in Bank 2 and reaches hardware
; only through the existing strict-byte and screen primitives.  Register
; addresses are private generated macros from m65-hw-registers.lisp.

(defun %m65-error ()
  (mod 1 0))

(defun %m65-byte-p (value)
  (if (numberp value)
      (and (>= value 0) (<= value 255))
      nil))

(defun m65-byte-read (high low)
  (peek high low))

(defun m65-byte-write (high low value)
  (poke high low value))

(defun m65-bit-set (high low mask)
  (if (%m65-byte-p mask)
      (m65-byte-write high low (logior (m65-byte-read high low) mask))
      (%m65-error)))

(defun m65-bit-clear (high low mask)
  (if (%m65-byte-p mask)
      (m65-byte-write high low
                      (logand (m65-byte-read high low) (logxor 255 mask)))
      (%m65-error)))

(defun m65-bit-test (high low mask)
  (if (%m65-byte-p mask)
      (if (= (logand (m65-byte-read high low) mask) 0) nil t)
      (%m65-error)))

(defun %m65-word-address-p (high low)
  (if (and (%m65-byte-p high) (%m65-byte-p low))
      (if (= high 255) (< low 255) t)
      nil))

(defun %m65-word-next-high (high low)
  (if (= low 255) (+ high 1) high))

(defun %m65-word-next-low (low)
  (if (= low 255) 0 (+ low 1)))

(defun m65-word-read (high low)
  (if (%m65-word-address-p high low)
      (cons (m65-byte-read high low)
            (m65-byte-read (%m65-word-next-high high low)
                           (%m65-word-next-low low)))
      (%m65-error)))

(defun m65-word-write (high low low-byte high-byte)
  (if (and (%m65-word-address-p high low)
           (%m65-byte-p low-byte)
           (%m65-byte-p high-byte))
      (progn
        (m65-byte-write high low low-byte)
        (m65-byte-write (%m65-word-next-high high low)
                        (%m65-word-next-low low)
                        high-byte)
        (cons low-byte high-byte))
      (%m65-error)))

(defun %m65-draw-point-p (x y columns rows)
  (and (numberp x)
       (numberp y)
       (>= x 0)
       (< x columns)
       (>= y 0)
       (< y rows)))

(defun %m65-draw-value-p (code color)
  (and (%m65-byte-p code)
       (numberp color)
       (>= color 0)
       (<= color 15)))

(defun m65-draw-plot (x y code color)
  (let* ((size (screen-size))
         (columns (car size))
         (rows (cadr size)))
    (if (and (%m65-draw-point-p x y columns rows)
             (%m65-draw-value-p code color))
        (progn (screen-put-char x y code color) t)
        (%m65-error))))

(defun %m65-sign (value)
  (if (< value 0) -1 (if (> value 0) 1 0)))

(defun %m65-abs (value)
  (if (< value 0) (- 0 value) value))

(defun %m65-draw-line-loop (x y x1 y1 dx dy sx sy err code color)
  (progn
    (screen-put-char x y code color)
    (if (and (= x x1) (= y y1))
        t
        (let* ((twice (* 2 err))
               (move-x (> twice (- 0 dy)))
               (next-x (if move-x (+ x sx) x))
               (after-x (if move-x (- err dy) err))
               (move-y (< twice dx))
               (next-y (if move-y (+ y sy) y))
               (next-error (if move-y (+ after-x dx) after-x)))
          (%m65-draw-line-loop next-x next-y x1 y1 dx dy sx sy
                               next-error code color)))))

(defun m65-draw-line (x0 y0 x1 y1 code color)
  (let* ((size (screen-size))
         (columns (car size))
         (rows (cadr size)))
    (if (and (%m65-draw-point-p x0 y0 columns rows)
             (%m65-draw-point-p x1 y1 columns rows)
             (%m65-draw-value-p code color))
        (%m65-draw-line-loop x0 y0 x1 y1
                             (%m65-abs (- x1 x0))
                             (%m65-abs (- y1 y0))
                             (%m65-sign (- x1 x0))
                             (%m65-sign (- y1 y0))
                             (- (%m65-abs (- x1 x0)) (%m65-abs (- y1 y0)))
                             code color)
        (%m65-error))))

(defun %m65-draw-fill-row (x x1 y code color)
  (if (<= x x1)
      (progn
        (screen-put-char x y code color)
        (%m65-draw-fill-row (+ x 1) x1 y code color))
      nil))

(defun %m65-draw-fill-rows (x0 x1 y y1 code color)
  (if (<= y y1)
      (progn
        (%m65-draw-fill-row x0 x1 y code color)
        (%m65-draw-fill-rows x0 x1 (+ y 1) y1 code color))
      t))

(defun m65-draw-fill (x0 y0 x1 y1 code color)
  (let* ((size (screen-size))
         (columns (car size))
         (rows (cadr size)))
    (if (and (%m65-draw-point-p x0 y0 columns rows)
             (%m65-draw-point-p x1 y1 columns rows)
             (<= x0 x1)
             (<= y0 y1)
             (%m65-draw-value-p code color))
        (%m65-draw-fill-rows x0 x1 y0 y1 code color)
        (%m65-error))))

(defun %m65-sprite-number-p (sprite)
  (and (numberp sprite) (>= sprite 0) (<= sprite 7)))

(defun %m65-vic-open ()
  (progn
    (m65-byte-write (%m65-reg-vic-key-hi) (%m65-reg-vic-key-lo) 71)
    (m65-byte-write (%m65-reg-vic-key-hi) (%m65-reg-vic-key-lo) 83)))

(defun m65-sprite-enable (sprite enabled)
  (if (%m65-sprite-number-p sprite)
      (let ((mask (ash 1 sprite)))
        (progn
          (if enabled
              (m65-bit-set (%m65-reg-vic-sprite-enable-hi)
                           (%m65-reg-vic-sprite-enable-lo) mask)
              (m65-bit-clear (%m65-reg-vic-sprite-enable-hi)
                             (%m65-reg-vic-sprite-enable-lo) mask))
          enabled))
      (%m65-error)))

(defun m65-sprite-position (sprite x y)
  (if (and (%m65-sprite-number-p sprite)
           (numberp x) (>= x 0) (<= x 511)
           (%m65-byte-p y))
      (let* ((mask (ash 1 sprite))
             (low (+ (%m65-reg-vic-sprite-xy-base-lo) (* 2 sprite))))
        (progn
          (m65-byte-write (%m65-reg-vic-sprite-xy-base-hi) low (mod x 256))
          (m65-byte-write (%m65-reg-vic-sprite-xy-base-hi) (+ low 1) y)
          (if (> x 255)
              (m65-bit-set (%m65-reg-vic-sprite-x-msb-hi)
                           (%m65-reg-vic-sprite-x-msb-lo) mask)
              (m65-bit-clear (%m65-reg-vic-sprite-x-msb-hi)
                             (%m65-reg-vic-sprite-x-msb-lo) mask))
          t))
      (%m65-error)))

(defun %m65-sprite-write-shape (shape index)
  (if (< index 63)
      (progn
        (m65-byte-write (%m65-sprite-shape-slot-hi)
                        (+ (%m65-sprite-shape-slot-lo) index)
                        (string-ref shape index))
        (%m65-sprite-write-shape shape (+ index 1)))
      (m65-byte-write (%m65-sprite-shape-slot-hi) 255 0)))

(defun m65-sprite-shape (sprite shape)
  (if (and (%m65-sprite-number-p sprite)
           (stringp shape)
           (= (string-length shape) 63))
      (progn
        (%m65-vic-open)
        (let* ((table-low
                 (m65-byte-read
                   (%m65-reg-vic-sprite-pointer-address-low-hi)
                   (%m65-reg-vic-sprite-pointer-address-low-lo)))
               (table-mid
                 (m65-byte-read
                   (%m65-reg-vic-sprite-pointer-address-mid-hi)
                   (%m65-reg-vic-sprite-pointer-address-mid-lo)))
               (table-high
                 (m65-byte-read
                   (%m65-reg-vic-sprite-pointer-address-high-hi)
                   (%m65-reg-vic-sprite-pointer-address-high-lo))))
          (if (and (= table-high 0) (<= table-low 248))
              (progn
                (%m65-sprite-write-shape shape 0)
                (m65-byte-write table-mid (+ table-low sprite)
                                (%m65-sprite-shape-pointer))
                t)
              (%m65-error))))
      (%m65-error)))

(defun m65-sprite-color (sprite color)
  (if (and (%m65-sprite-number-p sprite)
           (numberp color) (>= color 0) (<= color 15))
      (m65-byte-write (%m65-reg-vic-sprite-color-base-hi)
                      (+ (%m65-reg-vic-sprite-color-base-lo) sprite)
                      color)
      (%m65-error)))

(defun %m65-sid-voice-p (voice)
  (and (numberp voice) (>= voice 0) (<= voice 2)))

(defun m65-sid-voice
    (voice frequency-low frequency-high control attack-decay sustain-release volume)
  (if (and (%m65-sid-voice-p voice)
           (%m65-byte-p frequency-low)
           (%m65-byte-p frequency-high)
           (%m65-byte-p control)
           (%m65-byte-p attack-decay)
           (%m65-byte-p sustain-release)
           (numberp volume) (>= volume 0) (<= volume 15))
      (let ((base (+ (%m65-reg-sid-voice-base-lo) (* voice 7))))
        (progn
          (m65-byte-write (%m65-reg-sid-voice-base-hi) base
                          frequency-low)
          (m65-byte-write (%m65-reg-sid-voice-base-hi) (+ base 1)
                          frequency-high)
          (m65-byte-write (%m65-reg-sid-voice-base-hi) (+ base 5)
                          attack-decay)
          (m65-byte-write (%m65-reg-sid-voice-base-hi) (+ base 6)
                          sustain-release)
          (m65-byte-write (%m65-reg-sid-volume-hi)
                          (%m65-reg-sid-volume-lo) volume)
          (m65-byte-write (%m65-reg-sid-voice-base-hi) (+ base 4) control)
          t))
      (%m65-error)))
