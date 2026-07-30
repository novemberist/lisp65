; Q8.7 fixed-point values are ordinary signed fixnums scaled by 128.
; The math-unit transaction is deliberately visible here: all operand bytes
; are computed before the first poke, and no arithmetic is performed between
; that poke and the final result-byte peek.

(defun %fx-error ()
  (mod 1 0))

(defun %fx-add2 (a b)
  (if (> b 0)
      (if (> a (- 16383 b)) (%fx-error) (+ a b))
      (if (< b 0)
          (if (< a (- -16384 b)) (%fx-error) (+ a b))
          (+ a b))))

(defun int->fx (n)
  (if (if (>= n -128) (<= n 127) nil)
      (* n 128)
      (%fx-error)))

(defun fx (whole &optional fraction)
  (%fx-add2 (int->fx whole) (if fraction fraction 0)))

(defun fx->int (value)
  (if (= value -16384)
      -128
      (if (< value 0)
          (- 0 (/ (- 0 value) 128))
          (/ value 128))))

(defun fx+ (left right)
  (%fx-add2 left right))

(defun fx- (left right)
  (if (= right -16384)
      (if (< left 0) (+ (+ left 16383) 1) (%fx-error))
      (%fx-add2 left (- 0 right))))

(defun %fx-negative-product-p (left right)
  (if (< left 0)
      (if (< right 0) nil t)
      (if (< right 0) t nil)))

(defun %fx-mag-low (value)
  (if (= value -16384)
      0
      (mod (if (< value 0) (- 0 value) value) 256)))

(defun %fx-mag-high (value)
  (if (= value -16384)
      64
      (/ (if (< value 0) (- 0 value) value) 256)))

(defun %fx-write-inputs (a0 a1 a2 a3 b0 b1 b2 b3)
  (progn
    (poke 215 112 a0)
    (poke 215 113 a1)
    (poke 215 114 a2)
    (poke 215 115 a3)
    (poke 215 116 b0)
    (poke 215 117 b1)
    (poke 215 118 b2)
    (poke 215 119 b3)))

(defun %fx-wait-multiply ()
  (if (= (logand (peek 215 15) 64) 0)
      t
      (%fx-wait-multiply)))

(defun %fx-wait-divide ()
  (if (= (logand (peek 215 15) 128) 0)
      t
      (%fx-wait-divide)))

(defun %fx-finish-magnitude (magnitude edge negative)
  (if edge
      (if negative -16384 (%fx-error))
      (if negative (- 0 magnitude) magnitude)))

(defun %fx-round-magnitude (magnitude remainder negative)
  (if (>= remainder 64)
      (if (= magnitude 16383)
          (%fx-finish-magnitude 0 t negative)
          (%fx-finish-magnitude (+ magnitude 1) nil negative))
      (%fx-finish-magnitude magnitude nil negative)))

(defun %fx-product-result (p0 p1 p2 p3 p4 p5 p6 p7 negative)
  (if (if (= p3 0)
          (if (= p4 0)
              (if (= p5 0) (if (= p6 0) (= p7 0) nil) nil)
              nil)
          nil)
      (if (> p2 32)
          (%fx-error)
          (if (= p2 32)
              (if (if (= p1 0) (< p0 64) nil)
                  (%fx-finish-magnitude 0 t negative)
                  (%fx-error))
              (%fx-round-magnitude
                (+ (ash p2 9) (+ (ash p1 1) (ash p0 -7)))
                (logand p0 127)
                negative)))
      (%fx-error)))

(defun %fx-read-product (negative)
  (let* ((p0 (peek 215 120))
         (p1 (peek 215 121))
         (p2 (peek 215 122))
         (p3 (peek 215 123))
         (p4 (peek 215 124))
         (p5 (peek 215 125))
         (p6 (peek 215 126))
         (p7 (peek 215 127)))
    (%fx-product-result p0 p1 p2 p3 p4 p5 p6 p7 negative)))

(defun fx* (left right)
  (let* ((negative (%fx-negative-product-p left right))
         (a0 (%fx-mag-low left))
         (a1 (%fx-mag-high left))
         (b0 (%fx-mag-low right))
         (b1 (%fx-mag-high right)))
    (progn
      (%fx-write-inputs a0 a1 0 0 b0 b1 0 0)
      (%fx-wait-multiply)
      (%fx-read-product negative))))

(defun %fx-scaled-low (value)
  (if (= value -16384)
      0
      (if (= (mod (if (< value 0) (- 0 value) value) 2) 0)
          0
          128)))

(defun %fx-scaled-mid (value)
  (if (= value -16384)
      0
      (mod (/ (if (< value 0) (- 0 value) value) 2) 256)))

(defun %fx-scaled-high (value)
  (if (= value -16384)
      32
      (/ (if (< value 0) (- 0 value) value) 512)))

(defun %fx-division-result (q0 q1 q2 q3 fraction-high negative)
  (if (if (= q2 0) (= q3 0) nil)
      (if (> q1 64)
          (%fx-error)
          (if (= q1 64)
              (if (if (= q0 0) (< fraction-high 128) nil)
                  (%fx-finish-magnitude 0 t negative)
                  (%fx-error))
              (%fx-round-magnitude
                (+ (ash q1 8) q0)
                (ash fraction-high -1)
                negative)))
      (%fx-error)))

(defun %fx-read-division (negative)
  (let* ((q0 (peek 215 108))
         (q1 (peek 215 109))
         (q2 (peek 215 110))
         (q3 (peek 215 111))
         (fraction-high (peek 215 107)))
    (%fx-division-result q0 q1 q2 q3 fraction-high negative)))

(defun fx/ (left right)
  (if (= right 0)
      (%fx-error)
      (let* ((negative (%fx-negative-product-p left right))
             (a0 (%fx-scaled-low left))
             (a1 (%fx-scaled-mid left))
             (a2 (%fx-scaled-high left))
             (b0 (%fx-mag-low right))
             (b1 (%fx-mag-high right)))
        (progn
          (%fx-write-inputs a0 a1 a2 0 b0 b1 0 0)
          (%fx-wait-divide)
          (%fx-read-division negative)))))

(defun %fx-fraction-string (remainder)
  (if (= remainder 0)
      (char->string 48)
      (let* ((scaled (* remainder 10))
             (next (mod scaled 128))
             (digit (char->string (+ 48 (/ scaled 128)))))
        (if (= next 0)
            digit
            (string-append digit (%fx-fraction-string next))))))

(defun fx->string (value)
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
                 (%fx-fraction-string (mod magnitude 128)))))
        (if negative
            (string-append (char->string 45) body)
            body))))
