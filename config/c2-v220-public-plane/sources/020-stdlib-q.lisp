; Q8.7 fixed-point values are ordinary signed fixnums scaled by 128.
; The math-unit transaction is deliberately visible here: all operand bytes
; are computed before the first poke, and no arithmetic is performed between
; that poke and the final result-byte peek.

(defun %q-error ()
  (mod 1 0))

(defun %q-add2 (a b)
  (if (> b 0)
      (if (> a (- 16383 b)) (%q-error) (+ a b))
      (if (< b 0)
          (if (< a (- -16384 b)) (%q-error) (+ a b))
          (+ a b))))

(defun int->q (n)
  (if (if (>= n -128) (<= n 127) nil)
      (* n 128)
      (%q-error)))

(defun q (whole &optional fraction)
  (%q-add2 (int->q whole) (if fraction fraction 0)))

(defun q->int (value)
  (if (= value -16384)
      -128
      (if (< value 0)
          (- 0 (/ (- 0 value) 128))
          (/ value 128))))

(defun q+ (left right)
  (%q-add2 left right))

(defun q- (left right)
  (if (= right -16384)
      (if (< left 0) (+ (+ left 16383) 1) (%q-error))
      (%q-add2 left (- 0 right))))

(defun %q-negative-product-p (left right)
  (if (< left 0)
      (if (< right 0) nil t)
      (if (< right 0) t nil)))

(defun %q-mag-low (value)
  (if (= value -16384)
      0
      (mod (if (< value 0) (- 0 value) value) 256)))

(defun %q-mag-high (value)
  (if (= value -16384)
      64
      (/ (if (< value 0) (- 0 value) value) 256)))

(defun %q-write-inputs (a0 a1 a2 a3 b0 b1 b2 b3)
  (progn
    (poke 215 112 a0)
    (poke 215 113 a1)
    (poke 215 114 a2)
    (poke 215 115 a3)
    (poke 215 116 b0)
    (poke 215 117 b1)
    (poke 215 118 b2)
    (poke 215 119 b3)))

(defun %q-wait-multiply ()
  (if (= (logand (peek 215 15) 64) 0)
      t
      (%q-wait-multiply)))

(defun %q-wait-divide ()
  (if (= (logand (peek 215 15) 128) 0)
      t
      (%q-wait-divide)))

(defun %q-finish-magnitude (magnitude edge negative)
  (if edge
      (if negative -16384 (%q-error))
      (if negative (- 0 magnitude) magnitude)))

(defun %q-round-magnitude (magnitude remainder negative)
  (if (>= remainder 64)
      (if (= magnitude 16383)
          (%q-finish-magnitude 0 t negative)
          (%q-finish-magnitude (+ magnitude 1) nil negative))
      (%q-finish-magnitude magnitude nil negative)))

(defun %q-product-result (p0 p1 p2 p3 p4 p5 p6 p7 negative)
  (if (if (= p3 0)
          (if (= p4 0)
              (if (= p5 0) (if (= p6 0) (= p7 0) nil) nil)
              nil)
          nil)
      (if (> p2 32)
          (%q-error)
          (if (= p2 32)
              (if (if (= p1 0) (< p0 64) nil)
                  (%q-finish-magnitude 0 t negative)
                  (%q-error))
              (%q-round-magnitude
                (+ (ash p2 9) (+ (ash p1 1) (ash p0 -7)))
                (logand p0 127)
                negative)))
      (%q-error)))

(defun %q-read-product (negative)
  (let* ((p0 (peek 215 120))
         (p1 (peek 215 121))
         (p2 (peek 215 122))
         (p3 (peek 215 123))
         (p4 (peek 215 124))
         (p5 (peek 215 125))
         (p6 (peek 215 126))
         (p7 (peek 215 127)))
    (%q-product-result p0 p1 p2 p3 p4 p5 p6 p7 negative)))

(defun q* (left right)
  (let* ((negative (%q-negative-product-p left right))
         (a0 (%q-mag-low left))
         (a1 (%q-mag-high left))
         (b0 (%q-mag-low right))
         (b1 (%q-mag-high right)))
    (progn
      (%q-write-inputs a0 a1 0 0 b0 b1 0 0)
      (%q-wait-multiply)
      (%q-read-product negative))))

(defun %q-scaled-low (value)
  (if (= value -16384)
      0
      (if (= (mod (if (< value 0) (- 0 value) value) 2) 0)
          0
          128)))

(defun %q-scaled-mid (value)
  (if (= value -16384)
      0
      (mod (/ (if (< value 0) (- 0 value) value) 2) 256)))

(defun %q-scaled-high (value)
  (if (= value -16384)
      32
      (/ (if (< value 0) (- 0 value) value) 512)))

(defun %q-division-result (q0 q1 q2 q3 fraction-high negative)
  (if (if (= q2 0) (= q3 0) nil)
      (if (> q1 64)
          (%q-error)
          (if (= q1 64)
              (if (if (= q0 0) (< fraction-high 128) nil)
                  (%q-finish-magnitude 0 t negative)
                  (%q-error))
              (%q-round-magnitude
                (+ (ash q1 8) q0)
                (ash fraction-high -1)
                negative)))
      (%q-error)))

(defun %q-read-division (negative)
  (let* ((q0 (peek 215 108))
         (q1 (peek 215 109))
         (q2 (peek 215 110))
         (q3 (peek 215 111))
         (fraction-high (peek 215 107)))
    (%q-division-result q0 q1 q2 q3 fraction-high negative)))

(defun q/ (left right)
  (if (= right 0)
      (%q-error)
      (let* ((negative (%q-negative-product-p left right))
             (a0 (%q-scaled-low left))
             (a1 (%q-scaled-mid left))
             (a2 (%q-scaled-high left))
             (b0 (%q-mag-low right))
             (b1 (%q-mag-high right)))
        (progn
          (%q-write-inputs a0 a1 a2 0 b0 b1 0 0)
          (%q-wait-divide)
          (%q-read-division negative)))))

(defun %q-fraction-string (remainder)
  (if (= remainder 0)
      (char->string 48)
      (let* ((scaled (* remainder 10))
             (next (mod scaled 128))
             (digit (char->string (+ 48 (/ scaled 128)))))
        (if (= next 0)
            digit
            (string-append digit (%q-fraction-string next))))))

(defun q->string (value)
  (if (= value -16384)
      (string-append
        (char->string 45)
        (number->string 128)
        (char->string 46)
        (char->string 48))
      (let* ((negative (< value 0))
             (magnitude (if negative (- 0 value) value))
             (body
               (string-append
                 (number->string (/ magnitude 128))
                 (char->string 46)
                 (%q-fraction-string (mod magnitude 128)))))
        (if negative
            (string-append (char->string 45) body)
            body))))
