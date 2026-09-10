; Pure-Lisp base-composition PRNG.  The state represents the last 55
; recurrence values; %random-index names the oldest slot X(n-55), while the
; slot 31 positions ahead is X(n-24).  No resident/native state shadows it.

(defun %random-add14 (a b)
  ; (a+b) mod 16384 without ever constructing 16384 or overflowing the
  ; signed-15-bit fixnum range.
  (let ((room (- 16383 a)))
    (if (> b room)
        (- b (+ room 1))
        (+ a b))))

(defun %random-seed-step (value)
  ; value + 9973 mod 16384, expressed as two in-range branches.
  (if (>= value 6411) (- value 6411) (+ value 9973)))

(defun %random-normalize-seed (seed)
  ; Negative signed fixnums map to their low 14 bits.  The two additions keep
  ; the -16384 edge representable without a 16384 literal.
  (if (< seed 0) (+ 16383 (+ seed 1)) seed))

(defun %random-fill (count value result)
  (if (= count 0)
      (reverse result)
      (let ((next (%random-seed-step value)))
        (%random-fill (- count 1) next (cons next result)))))

(defun random-seed (seed)
  (let ((normalized (%random-normalize-seed seed)))
    (progn
      (set-symbol-value '%random-state
                        (%random-fill 55 normalized nil))
      (set-symbol-value '%random-index 0)
      normalized)))

(defun %random-hardware-seed ()
  ; Read-only, non-consuming entropy.  CIA timer values include the elapsed
  ; human input delay that led to the first call; the typed queue stays intact.
  (%random-add14
    (peek 208 18)
    (%random-add14
      (ash (peek 220 4) 6)
      (%random-add14 (peek 221 4) (peek 212 27)))))

(defun %random-ensure-state ()
  (if (boundp '%random-state)
      (if (boundp '%random-index)
          t
          (random-seed (%random-hardware-seed)))
      (random-seed (%random-hardware-seed))))

(defun %random-next ()
  (progn
    (%random-ensure-state)
    (let* ((index (symbol-value '%random-index))
           (state (symbol-value '%random-state))
           (oldest (nthcdr index state))
           (lag24 (nthcdr (mod (+ index 31) 55) state))
           (value (%random-add14 (car oldest) (car lag24))))
      (progn
        (rplaca oldest value)
        (set-symbol-value '%random-index (mod (+ index 1) 55))
        value))))

(defun %random-16384-remainder (n)
  ; 16384 mod n without an out-of-range 16384 literal.
  (let ((rest (mod 16383 n)))
    (if (= rest (- n 1)) 0 (+ rest 1))))

(defun %random-draw-below (n last-accepted)
  (let ((value (%random-next)))
    (if (<= value last-accepted)
        (mod value n)
        (%random-draw-below n last-accepted))))

(defun random (n)
  (if (if (numberp n) (if (> n 0) (<= n 16383) nil) nil)
      (%random-draw-below n (- 16383 (%random-16384-remainder n)))
      ; Preserve the existing numeric error surface without a new native
      ; primitive, status code or resident error string.
      (mod n 0)))
