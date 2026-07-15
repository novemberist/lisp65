; Dialect-v2 runtime eval is ordinary resident bytecode. lcc-run is the single
; semantic engine after the native Treewalk carrier is removed.
(defun eval (form)
  (lcc-run form))

(defun %number->string-result (negative codes)
  (%string-from-codes (if negative (cons 45 codes) codes)))

(defun number->string (number)
  (if (= number -16384)
      (%number->string-result
        t (cons 49 (cons 54 (cons 51 (cons 56 (cons 52 nil))))))
      (let* ((negative (< number 0))
             (value (if negative (- 0 number) number))
             (codes nil))
        (if (= value 0)
            (%number->string-result negative (cons 48 nil))
            (progn
              (dotimes (index 5)
                (if (> value 0)
                    (progn
                      (setq codes (cons (+ 48 (mod value 10)) codes))
                      (setq value (/ value 10)))
                    nil))
              (%number->string-result negative codes))))))

; v2 Workbench FASL persistence. The fixed slot chain is immutable; bytecode
; only replaces its payload through the existing verified sector primitives.
; The first four payload bytes are the L65M length prefix, so invalidating them
; before the tail write and committing the complete first sector last makes a
; stopped transaction fail closed on reload.
(defun %compile-slot-capacity (track sector fuel cap)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((next-track (%disk-byte 0))
                (next-sector (%disk-byte 1)))
            (if (> next-track 0)
                (%compile-slot-capacity next-track next-sector (1- fuel) (+ cap 254))
                (if (> next-sector 0) (+ cap (- next-sector 1)) -1)))
          -1)
      -1))

(defun %fasl-save-sector (position length use)
  (dotimes (index use t)
    (%disk-poke (+ index 2)
      (if (< (+ position index) length)
          (%fasl-stage-get (+ position index))
          32))))

(defun %fasl-save-tail (track sector length position fuel)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((next-track (%disk-byte 0))
                (next-sector (%disk-byte 1)))
            (let ((use (if (> next-track 0) 254 (- next-sector 1))))
              (if (if (> next-track 0) t (> next-sector 0))
                  (progn
                    (%fasl-save-sector position length use)
                    (if (%disk-write-sector track sector)
                        (if (> next-track 0)
                            (%fasl-save-tail next-track next-sector length
                              (+ position use) (- fuel 1))
                            t)
                        nil))
                  nil)))
          nil)
      nil))

(defun %fasl-commit-first (track sector length next-track next-sector use)
  (if (%disk-read-sector track sector)
      (if (if (= (%disk-byte 0) next-track)
              (= (%disk-byte 1) next-sector)
              nil)
          (progn
            (%fasl-save-sector 0 length use)
            (%disk-write-sector track sector))
          nil)
      nil))

(defun %fasl-save-staged-v2 (track sector length)
  (let ((capacity (%compile-slot-capacity track sector 255 0)))
    (if (if (>= capacity 0) (<= length capacity) nil)
        (if (%disk-read-sector track sector)
            (let ((next-track (%disk-byte 0))
                  (next-sector (%disk-byte 1)))
              (let ((use (if (> next-track 0) 254 (- next-sector 1))))
                (progn
                  (%disk-poke 2 0)
                  (%disk-poke 3 0)
                  (%disk-poke 4 0)
                  (%disk-poke 5 0)
                  (if (%disk-write-sector track sector)
                      (if (if (> next-track 0)
                              (%fasl-save-tail next-track next-sector length use 254)
                              t)
                          (%fasl-commit-first track sector length
                            next-track next-sector use)
                          nil)
                      nil))))
            nil)
        (quote %fasl-too-large))))

; v2 override of the shared v1 definition. The emitter and slot lookup stay
; unchanged; only the final persistence step moves from Prim 34 to bytecode.
(defun compile-string (source dst)
  (progn
    (set-symbol-value (quote %compile-error) nil)
    (if (stringp source)
        (if (stringp dst)
            (let ((slot (%compile-slot-find (%string-codes dst) 40 0 64)))
              (if slot
                  (progn
                    (%cs-read-open source)
                    (let ((fs (%fasl-fs 0)))
                      (%fasl-stream-forms fs)
                      (let ((saved (%fasl-save-staged-v2
                                     (car slot) (cdr slot) (%fasl-finish fs))))
                        (if (eq saved 't)
                            (progn (set-symbol-value (quote %compile-error) nil) 't)
                            (if (eq saved '%fasl-too-large)
                                (progn (set-symbol-value (quote %compile-error) "too large") nil)
                                (progn (set-symbol-value (quote %compile-error) "save failed") nil))))))
                  (progn (set-symbol-value (quote %compile-error) "slot missing") nil)))
            (progn (set-symbol-value (quote %compile-error) "bad slot") nil))
        (progn (set-symbol-value (quote %compile-error) "bad source") nil))))
