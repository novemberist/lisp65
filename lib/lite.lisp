; Pending is ONE accepted-source string with a trailing LF per segment.
; No pending records or checkpoint lists survive while the resident editor runs.
(defun %lt-line (history pending packed prefix)
  (let* ((state (mod packed 4))
         (depth (/ (- packed state) 4))
         (size (screen-size))
         (columns (car size))
         (row (- (car (cdr size)) 1))
         (top (and (= (string-length pending) 0) (not prefix)))
         (indent (if prefix prefix
                   (substring "                    " 0
                     (* 2 (if (= state 2) 0 (if (> depth 10) 10 depth)))))))
    (if top (%repl-prompt row) nil)
    (%lt-read indent history 0 (if top (- columns 5) columns)
              (if top (- 0 (+ row 2)) row) pending)))

(defun %lt-drive (history pending packed prefix)
  (let* ((line (%lt-line history pending packed prefix))
         (next (if (numberp line) 0
                   (%sexp-line-state (%string-codes line) packed))))
    (cond
      ((eq line -2)
       (progn (write-line "*** input limit") (%lt-drive history "" 0 nil)))
      ((eq line 1101) (%lt-reopen history pending))
      ((< next 0)
       (progn (write-line "*** reader: unmatched close parenthesis")
              (%lt-drive history "" 0 nil)))
      ((or (> (+ (string-length pending)
                 (+ (string-length line) (if (> next 0) 1 0))) 640)
           (> (+ (%lt-count pending) (%lt-count line))
              (if (> next 0) 31 32)))
       (progn (write-line "*** input limit") (%lt-drive history "" 0 nil)))
      ((> next 0) (%lt-drive history (%lt-cat pending line "
") next nil))
      ((and (= (string-length pending) 0) (= (string-length line) 0)) nil)
      (t (%lt-cat pending line "")))))

(defun %lt-count (pending)
  (let ((n 0))
    (dotimes (i (string-length pending) nil)
      (if (= (string-ref pending i) 10) (setq n (+ n 1)) nil))
    n))

; Recompute checkpoints only at the reopen boundary, one bounded line at a time.
(defun %lt-checkpoint (pending start at packed)
  (dotimes (i (- (string-length pending) at) nil)
    (if (= (string-ref pending (+ at i)) 10)
        (progn
          (setq packed (%sexp-line-state
                         (%string-codes (%lt-slice pending start (+ at i))) packed))
          (setq start (+ (+ at i) 1))) nil))
  packed)

(defun %lt-reopen (history pending)
  (let* ((end (- (string-length pending) 1))
         (start 0))
    (dotimes (i end nil)
      (if (= (string-ref pending i) 10) (setq start (+ i 1)) nil))
    (let* ((prefix (%lt-slice pending start end))
           (rest (%lt-slice pending 0 start))
           (packed (%lt-checkpoint rest 0 0 0)))
      (write-line "[edit previous line]")
      (%lt-drive history rest packed prefix))))

; Short sources use the resident slice; large sources keep the descriptor-only
; buffer copy. Never materialise a source-sized list above the proved bound.
(defun %lt-slice (source start end)
  (if (<= (string-length source) 250)
      (substring source start end)
      (%lt-buffer-slice source start end)))

(defun %lt-buffer-slice (source start end)
  (let ((out (%buffer-alloc 0 (- end start))))
    (dotimes (i (- end start) nil)
      (%buffer-write out i (string-ref source (+ start i))))
    (%buffer-read 3 out)))

; Preserve the accepted single line without copying. Short joins use resident
; string-append; only heap-critical joins pay the per-byte buffer overlay cost.
(defun %lt-cat (a b c)
  (if (= (+ (string-length a) (string-length c)) 0) b
  (if (<= (+ (string-length a) (+ (string-length b) (string-length c))) 259)
      (string-append a b c)
      (%lt-buffer-cat a b c))))

(defun %lt-buffer-cat (a b c)
  (let* ((strings (list a b c))
         (out (%buffer-alloc 0 (+ (string-length a) (+ (string-length b) (string-length c)))))
         (at 0))
    (dolist (s strings nil)
      (dotimes (i (string-length s) nil)
        (%buffer-write out at (string-ref s i))
        (setq at (+ at 1))))
    (%buffer-read 3 out)))

(defun %lt-history (history)
  (if history
      (and (<= (string-length (car history)) 250) (%lt-history (cdr history)))
      't))
