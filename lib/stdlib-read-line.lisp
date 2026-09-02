; Cold Bank-2 line input over the public key-event and screen primitives.
; The editor owns the last screen row.  Its mutable sentinel chain stays in
; logical order: CURSOR is the cell immediately before point.  The base state
; has eight cells; a shelf caller may append history and history-index cells.
; Only an accepted printable character allocates after a key-event boundary.

; One software phase owner over the existing product frame byte.  MARKED says
; that the cursor cell is also one of the delimiter cells: hidden cursor paint
; must then preserve the delimiter attribute instead of erasing it.
(defun %frame-low ()
  (peek 255 131))

(defun %cursor-blink (cursor position start row idle force)
  (let* ((blink (car idle)))
    (if force
        (progn
          (rplaca blink (%frame-low))
          (rplacd blink 't)
          (screen-put-char (- position start) row
                           (if (cdr cursor) (car (cdr cursor)) 32) 129)
          nil)
        (let* ((now (%frame-low))
               (elapsed (mod (- now (car blink)) 256))
               (visible (if (>= elapsed 32) (not (cdr blink)) (cdr blink))))
          (if (< elapsed 32)
              nil
              (progn
                (rplaca blink now)
                (rplacd blink visible)
                (screen-put-char (- position start) row
                                 (if (cdr cursor) (car (cdr cursor)) 32)
                                 (if visible 129
                                     (if (car (cdr (cdr (cdr (cdr (cdr
                                         (cdr (cdr (cdr (cdr (cdr idle)))))))))))
                                         7 1)))
                nil))))))

; Derive a new line-editor job without scanning a code unit.  Ordinary cells
; settle immediately; only a delimiter enters the prefix pass.
(defun %rl-start (state)
  (let* ((idle (car (nthcdr 10 state)))
         (position (car (nthcdr 3 state)))
         (length (car (nthcdr 4 state)))
         (cursor (car (cdr state)))
         (point (if (< position length) position
                    (if (> position 0) (- position 1) -1)))
         (cell (if (< position length) (cdr cursor) cursor))
         (code (if (>= point 0) (car cell) 0)))
    (progn
      (rplaca (nthcdr 2 idle) point)
      (rplaca (nthcdr 3 idle) 0)
      (rplaca (nthcdr 4 idle) 0)
      (rplaca (nthcdr 5 idle) (cdr (car state)))
      (rplaca (cdr idle)
              (if (or (= code 40) (or (= code 41) (= code 34))) 1 0))
      nil)))

; Complete the prefix-to-partner transition after the final prefix chunk.
(defun %rl-kind (state result next-codes)
  (let* ((idle (car (nthcdr 10 state)))
         (point (car (nthcdr 2 idle)))
         (kind (%sexp-match (car next-codes) result)))
    (progn
      (rplaca (cdr idle) (if (= kind 0) 0 (+ kind 1)))
      (rplaca (nthcdr 3 idle) (if (= (mod kind 2) 1) (+ point 1) 0))
      (rplaca (nthcdr 4 idle) (if (= kind 1) 4 (if (= kind 3) 2 0)))
      (rplaca (nthcdr 5 idle)
              (if (= (mod kind 2) 1) (cdr next-codes) (cdr (car state))))
      (rplaca (nthcdr 6 idle) (if (= kind 2) (/ result 4) 0))
      nil)))

; Exactly one self-capped prefix chunk.
(defun %rl-scan (state)
  (let* ((idle (car (nthcdr 10 state)))
         (point (car (nthcdr 2 idle)))
         (i (car (nthcdr 3 idle)))
         (codes-at-i (car (nthcdr 5 idle)))
         (result (%rl-idle 0 (cdr (car state)) codes-at-i point i
                           (car (nthcdr 4 idle)) nil nil nil))
         (next (if (< (+ i 3) point) (+ i 3) point))
         (next-codes (nthcdr (- next i) codes-at-i)))
    (progn
      (rplaca (nthcdr 3 idle) next)
      (rplaca (nthcdr 4 idle) result)
      (rplaca (nthcdr 5 idle) next-codes)
      (if (= next point) (%rl-kind state result next-codes) nil))))

; Exactly one self-capped forward partner chunk.  NIL means incomplete;
; zero means complete without a partner; partner+1 preserves index zero.
(defun %rl-close (state)
  (let* ((idle (car (nthcdr 10 state)))
         (kind (- (car (cdr idle)) 1))
         (i (car (nthcdr 3 idle)))
         (codes-at-i (car (nthcdr 5 idle)))
         (limit (car (nthcdr 4 state)))
         (result (%rl-idle 1 (cdr (car state)) codes-at-i limit i
                           (car (nthcdr 4 idle))
                           (if (= kind 1) 41 34) nil nil))
         (next (if (< (+ i 3) limit) (+ i 3) limit)))
    (if (< result 0)
        (progn (rplaca (cdr idle) 0) (- 0 result))
        (if (= next limit)
            (progn (rplaca (cdr idle) 0) 0)
            (progn
              (rplaca (nthcdr 3 idle) next)
              (rplaca (nthcdr 4 idle) result)
              (rplaca (nthcdr 5 idle)
                      (nthcdr (- next i) codes-at-i))
              nil)))))

; Exactly one self-capped opening replay chunk, with the same result encoding.
(defun %rl-open (state)
  (let* ((idle (car (nthcdr 10 state)))
         (kind (- (car (cdr idle)) 1))
         (i (car (nthcdr 3 idle)))
         (codes-at-i (car (nthcdr 5 idle)))
         (limit (car (nthcdr 2 idle)))
         (result (%rl-idle 2 (cdr (car state)) codes-at-i limit i
                           (car (nthcdr 4 idle)) (car (nthcdr 6 idle))
                           (if (= kind 2) 40 34) nil))
         (next (if (< (+ i 3) limit) (+ i 3) limit)))
    (if (= next limit)
        (progn (rplaca (cdr idle) 0) (mod result 256))
        (progn
          (rplaca (nthcdr 3 idle) next)
          (rplaca (nthcdr 4 idle) result)
          (rplaca (nthcdr 5 idle) (nthcdr (- next i) codes-at-i))
          nil))))

; The line surface's sole seam into every shared matcher pass and the composed
; paint transition.  MODE 0/1/2 selects scan/close/open; 3 selects paint.
(defun %rl-idle (mode a b c d e f g h)
  (if (= mode 0)
      (%sexp-scan a b c d e nil)
      (if (= mode 1)
          (%sexp-close a b c d e f nil)
          (if (= mode 2)
              (%sexp-open a b c d e f g nil)
              (%sexp-paint a b c d e f g 0)))))

; Clear the surface-owned pair at an input handoff or unmatched completion.
(defun %rl-clear (codes cursor position start columns row idle event)
  (let* ((i7 (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle))))))))
         (active (car i7))
         (pair-a (car (cdr i7)))
         (pair-b (car (cdr (cdr i7))))
         (old (if (= active 1) pair-a (if (= active 2) pair-b nil)))
         (marked (cdr (cdr (cdr i7)))))
    (progn
      (if old
          (%rl-idle 3 codes old nil start row
                    columns position nil) nil)
      (rplaca i7 0)
      (rplaca marked nil)
      (if event (rplaca (cdr idle) -1) nil)
      (if event (%cursor-blink cursor position start row idle 't) nil)
      (if event event (if old 't nil)))))

; Install one completed partner result (ANSWER is partner+1).
(defun %rl-paint (state answer)
  (let* ((idle (car (nthcdr 10 state)))
         (active (car (nthcdr 7 idle)))
         (pair-a (car (nthcdr 8 idle)))
         (pair-b (car (nthcdr 9 idle)))
         (old (if (= active 1) pair-a (if (= active 2) pair-b nil)))
         (new (if (= active 1) pair-b pair-a))
         (found (- answer 1))
         (position (car (nthcdr 3 state))))
    (progn
      (rplaca new (car (nthcdr 2 idle)))
      (rplacd new found)
      (%rl-idle 3 (cdr (car state)) old new (car (nthcdr 5 state))
                (car (nthcdr 7 state)) (car (nthcdr 6 state)) position nil)
      (rplaca (nthcdr 7 idle) (if (= active 1) 2 1))
      (rplaca (nthcdr 10 idle)
              (if (or (= position (car new)) (= position found)) 't nil))
      't)))

; Card-2 polling owner.  States without slot 10 are parked Comfort/history
; callers and retain their prior scalar or blocking input path.
(defun %rl-wait (state s1 s3 s5 s7 idle)
  (let* ((phase (car (cdr idle)))
         (painted
          (if (< phase 0)
              (%rl-start state)
              (if (= phase 1)
                  (%rl-scan state)
                  (if (> phase 1)
                      (let* ((answer
                              (if (= (mod phase 2) 0)
                                  (%rl-close state)
                                  (%rl-open state))))
                        (if answer
                            (if (= answer 0)
                                (%rl-clear (cdr (car state))
                                           (car s1) (car s3) (car s5)
                                           (car (cdr s5)) (car s7) idle nil)
                                (%rl-paint state answer))
                            nil))
                      nil)))))
    (progn (%cursor-blink (car s1) (car s3) (car s5)
                          (car s7) idle painted)
           nil)))

(defun %rl-poll (state)
  (let* ((s1 (cdr state))
         (s3 (cdr (cdr s1)))
         (s5 (cdr (cdr s3)))
         (s7 (cdr (cdr s5)))
         (tail (cdr s7))
         (idle (car (cdr (cdr tail)))))
    (if (not idle)
        (if tail
            (%rl-render nil 0 0 0 0 -1)
            (key-event 1))
        (let* ((event (key-event 2)))
          (if event
              (%rl-clear (cdr (car state)) (car s1) (car s3) (car s5)
                         (car (cdr s5)) (car s7) idle event)
              (%rl-wait state s1 s3 s5 s7 idle))))))

(defun %rl-render (codes index column stop cursor row)
  (if (= row -1)
      (key-event 2)
      (if (< column stop)
          (let* ((present (if codes 't nil))
                 (at-cursor (= index cursor))
                 (code (if present (car codes) 32)))
            (progn
              (screen-put-char column row code (if at-cursor 129 1))
              (%rl-render (if present (cdr codes) nil)
                          (+ index 1) (+ column 1) stop cursor row)))
          nil)))

(defun %rl-screen-tail (codes index column stop cursor row)
  (if (= row -2)
      (let ((text "lisp65> "))
        (dotimes (at 8 nil)
          (screen-put-char at stop (string-ref text at) 1)))
      (let* ((native (< row -34))
             (prompted (< row -2))
             (actual-row (if native (- 0 (+ row 34)) (- 0 (+ row 2)))))
        (if (and prompted (= cursor -1))
            (%rl-render nil 0 0 (car (screen-size)) -2 actual-row)
            (if (and prompted (< column 0))
                (%rl-screen-tail (if codes (cdr codes) nil)
                                 (+ index 1) (+ column 1) stop cursor row)
                (let* ((origin (if native 8 (if prompted 5 0))))
                  (%rl-render codes index (+ column origin) (+ stop origin)
                              cursor (if prompted actual-row row))))))))

(defun %rl-cut (state before removed)
  (let* ((head (car state))
         (tail (car (nthcdr 2 state)))
         (position (car (nthcdr 3 state)))
         (length (car (nthcdr 4 state)))
         (start (car (nthcdr 5 state)))
         (columns (car (nthcdr 6 state)))
         (next-position (if (eq removed (car (cdr state)))
                            (- position 1) position))
         (full (and (< next-position position) (= position start)))
         (next-start (if full next-position start))
         (from (if full next-start next-position))
         (edge (+ (- length start) 1)))
    (progn
      (rplacd before (cdr removed))
      (rplaca (nthcdr 1 state) before)
      (if (eq removed tail) (rplaca (nthcdr 2 state) before) nil)
      (rplaca (nthcdr 3 state) next-position)
      (rplaca (nthcdr 4 state) (- length 1))
      (rplaca (nthcdr 5 state) next-start)
      (%rl-screen-tail
       (nthcdr from (cdr head)) from (- from next-start)
       (if (< edge columns) edge columns)
       next-position (car (nthcdr 7 state)))
      (%read-line-loop state))))

(defun %rl-move (state next-cursor next-position)
  (let* ((head (car state))
         (position (car (nthcdr 3 state)))
         (start (car (nthcdr 5 state)))
         (columns (car (nthcdr 6 state)))
         (next-start
          (if (< next-position start)
              next-position
              (if (>= next-position (+ start columns))
                  (- next-position (- columns 1)) start)))
         (full (not (= next-start start)))
         (from (if full next-start
                   (if (< next-position position) next-position position)))
         (last (if (> next-position position) next-position position)))
    (progn
      (rplaca (nthcdr 1 state) next-cursor)
      (rplaca (nthcdr 3 state) next-position)
      (rplaca (nthcdr 5 state) next-start)
      (%rl-screen-tail
       (nthcdr from (cdr head)) from (- from next-start)
       (if full columns (+ (- last start) 1))
       next-position (car (nthcdr 7 state)))
      (%read-line-loop state))))

(defun %rl-put (code state cursor dirty)
  (let* ((s1 (cdr state)) (s2 (cdr s1)) (s3 (cdr s2))
         (s4 (cdr s3)) (s5 (cdr s4)) (s6 (cdr s5))
         (start (car s5))
         (inserted (cons code (cdr cursor)))
         (next-position (+ (car s3) 1))
         (next-start
          (if (>= next-position (+ start (car s6)))
              (- next-position (- (car s6) 1)) start)))
    (progn
      (rplacd cursor inserted)
      (rplaca s1 inserted)
      (if (eq cursor (car s2)) (rplaca s2 inserted) nil)
      (rplaca s3 next-position)
      (rplaca s4 (+ (car s4) 1))
      (rplaca s5 next-start)
      (let* ((next-code (if (= (car s4) 250) nil (key-event 3))))
        (if next-code
            (%rl-put next-code state inserted dirty)
            (let* ((edge (+ (- (car s4) next-start) 1)))
            (progn
              (%rl-screen-tail
               (nthcdr dirty (cdr (car state))) dirty (- dirty next-start)
               (if (< edge (car s6)) edge (car s6))
               next-position (car (cdr s6)))
              (%read-line-loop state))))))))

(defun %rl-dispatch (command state)
  (let* ((cursor (car (cdr state)))
         (position (car (nthcdr 3 state)))
         (length (car (nthcdr 4 state))))
    (cond
      ((= command 1101)
       (if (> position 0)
           (%rl-cut state (nthcdr (- position 1) (car state)) cursor)
           (%read-line-loop state)))
      ((= command 1102)
       (if (cdr cursor) (%rl-cut state cursor (cdr cursor))
           (%read-line-loop state)))
      ((= command 1106)
       (if (> position 0)
           (%rl-move state (nthcdr (- position 1) (car state)) (- position 1))
           (%read-line-loop state)))
      ((= command 1107)
       (if (< position length)
           (%rl-move state (cdr cursor) (+ position 1))
           (%read-line-loop state)))
      ((= command 1104) (%rl-move state (car state) 0))
      ((= command 1103) (%rl-move state (car (nthcdr 2 state)) length))
      ((or (= command 1108) (= command 1003))
       (if (car (nthcdr 8 state)) command (%read-line-loop state)))
      (t (%read-line-loop state)))))

(defun %read-line-loop (state)
  (let* ((event (%rl-poll state))
         (code (if (numberp event) event (if event (cadr event) 0))))
    (if (and (>= code 32) (<= code 126))
        (if (< (car (nthcdr 4 state)) 250)
            (%rl-put code state (car (cdr state))
                     (car (nthcdr 3 state)))
            (%read-line-loop state))
        (let* ((command
;; BEGIN GENERATED REPL LINE KEYMAP
          ((lambda (binding) (if binding (cdr binding) 0))
           (assoc code
                  (quote ((13 . 1109) (20 . 1101) (157 . 1106) (29 . 1107) (145 . 1108) (17 . 1003) (4 . 1102) (6 . 1107) (2 . 1106) (1 . 1104) (5 . 1103) (127 . 1101)))))
;; END GENERATED REPL LINE KEYMAP
               ))
          (if (= command 1109)
              (let* ((head (car state))
                     (position (car (nthcdr 3 state)))
                     (start (car (nthcdr 5 state)))
                     (row (car (nthcdr 7 state)))
                     (codes (cdr head)))
                (progn
                  (%rl-screen-tail
                   (nthcdr position codes) position (- position start)
                   (+ (- position start) 1) -1 row)
                  (write-char 10)
                  (%string-from-codes codes)))
              (%rl-dispatch command state))))))

(defun %native-prompt (row)
  (%rl-screen-tail nil 0 0 row nil -2))

(defun %native-read-line () (read-line (quote native)))

(defun %rl-session (native)
  (let* ((size (screen-size))
         (full-columns (car size))
         (screen-row (- (car (cdr size)) 1))
         (columns (if native (- full-columns 8) full-columns))
         (row (if native (- 0 (+ screen-row 34)) screen-row))
         (head (cons 0 nil))
         (blink (cons (%frame-low) 't))
         (idle (list blink -1 0 0 0 nil 0 0
                     (cons 0 0) (cons 0 0) nil))
         (state (list head head head 0 0 0 columns row nil nil idle)))
    (progn
      (if native (%native-prompt screen-row) nil)
      (%rl-screen-tail nil 0 0 columns 0 row)
      (%read-line-loop state))))

(defun read-line (&rest prompt)
  (progn
    (poke 255 141 255)
    (poke 255 140 0)
    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))
    (poke 255 141 0)
    (let* ((answer (%rl-session (if prompt 't nil))))
      (progn
        (poke 255 141 255)
        answer))))
