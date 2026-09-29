; Derived native-only line-wrap projection; no Block-3 entry.
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

; Paint a wrapped range that spans more than one window.  Window K, the logical
; range [K*COLUMNS, (K+1)*COLUMNS), lands on screen row BASE+K from screen
; column ORIGIN: one shared row painter per touched window, no division per
; cell, and the walk is a self tail call.  A paint that stays inside one window
; is finished by the seam itself, so a keystroke pays this only across a wrap.

(defun %rl-screen-tail (codes index stop cursor top columns row)
  (if (= row -2)
      (let ((text "lisp65> "))
        (dotimes (at 8 nil)
          (screen-put-char at stop (string-ref text at) 1)))
      (let* ((native (< row -34))
             (prompted (< row -2))
             (origin (if native 8 (if prompted 5 0)))
             (base (- (if native (- -34 row) (if prompted (- -2 row) row))
                      top)))
        (if (and prompted (= cursor -1))
            (let* ((width (car (screen-size))))
              (%rl-rows nil 0 (* width (+ top 1)) -1 base width 0))
            (let* ((column (mod index columns))
                   (want (- stop index)))
              (if (< (- columns column) want)
                  (%rl-rows codes index stop cursor base columns origin)
                  (%rl-render codes index (+ origin column)
                              (+ origin (+ column want)) cursor
                              (+ base (/ index columns)))))))))

; Removal shrinks the line by one cell.  While the wrap lift is unchanged only
; the tail from point through the vacated cell is redrawn; when the lift drops
; the whole block moves down one row, so the row the block gives up is blanked
; first and the block is then redrawn whole, trailing blanks included.

(defun %rl-cut (state before removed)
  (let* ((head (car state))
         (tail (car (nthcdr 2 state)))
         (position (car (nthcdr 3 state)))
         (next-length (- (car (nthcdr 4 state)) 1))
         (top (car (nthcdr 5 state)))
         (columns (car (nthcdr 6 state)))
         (row (car (nthcdr 7 state)))
         (next-position (if (eq removed (car (cdr state)))
                            (- position 1) position))
         (next-top (/ next-length columns)))
    (progn
      (rplacd before (cdr removed))
      (rplaca (nthcdr 1 state) before)
      (if (eq removed tail) (rplaca (nthcdr 2 state) before) nil)
      (rplaca (nthcdr 3 state) next-position)
      (rplaca (nthcdr 4 state) next-length)
      (rplaca (nthcdr 5 state) next-top)
      (if (= next-top top)
          (%rl-screen-tail (nthcdr next-position (cdr head)) next-position
                           (+ next-length 2) next-position next-top columns row)
          (progn
            (%rl-screen-tail nil 0 columns -2 top columns row)
            (%rl-screen-tail (cdr head) 0 (* columns (+ next-top 1))
                             next-position next-top columns row)))
      (%read-line-loop state))))

; Point moves never change the wrap lift or any code, so exactly the two cells
; that change reverse video are redrawn, on whichever rows they fall.
(defun %rl-move (state next-cursor next-position)
  (let* ((head (car state))
         (position (car (nthcdr 3 state)))
         (top (car (nthcdr 5 state)))
         (columns (car (nthcdr 6 state)))
         (row (car (nthcdr 7 state))))
    (progn
      (rplaca (nthcdr 1 state) next-cursor)
      (rplaca (nthcdr 3 state) next-position)
      (%rl-screen-tail (nthcdr position (cdr head)) position (+ position 1)
                       next-position top columns row)
      (%rl-screen-tail (nthcdr next-position (cdr head)) next-position
                       (+ next-position 1) next-position top columns row)
      (%read-line-loop state))))

; The batch loop touches no screen cell and no wrap state; cell 5 is settled
; once, after the last code of the batch.  A batch that did not change the
; wrap lift redraws only from the first dirty index through the cell after the
; new end; a batch that lifted the block redraws every owned row, because all
; of them moved up by one.

(defun %rl-put (code state cursor dirty)
  (let* ((s1 (cdr state)) (s2 (cdr s1)) (s3 (cdr s2))
         (s4 (cdr s3)) (s5 (cdr s4)) (s6 (cdr s5))
         (inserted (cons code (cdr cursor)))
         (next-position (+ (car s3) 1)))
    (progn
      (rplacd cursor inserted)
      (rplaca s1 inserted)
      (if (eq cursor (car s2)) (rplaca s2 inserted) nil)
      (rplaca s3 next-position)
      (rplaca s4 (+ (car s4) 1))
      (let* ((next-code (if (= (car s4) 250) nil (key-event 3))))
        (if next-code
            (%rl-put next-code state inserted dirty)
            (let* ((columns (car s6))
                   (top (car s5))
                   (next-top (/ (car s4) columns)))
            (progn
              (rplaca s5 next-top)
              (if (= next-top top)
                  (%rl-screen-tail
                   (nthcdr dirty (cdr (car state))) dirty (+ (car s4) 1)
                   next-position next-top columns (car (cdr s6)))
                  (%rl-screen-tail
                   (cdr (car state)) 0 (* columns (+ next-top 1))
                   next-position next-top columns (car (cdr s6))))
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
  (let* ((event (if (nthcdr 8 state)
                    (%rl-render nil 0 0 0 0 -1)
                    (key-event 1)))
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
                     (top (car (nthcdr 5 state)))
                     (columns (car (nthcdr 6 state)))
                     (row (car (nthcdr 7 state)))
                     (codes (cdr head)))
                (progn
                  (%rl-screen-tail
                   (nthcdr position codes) position (+ position 1)
                   -1 top columns row)
                  (write-char 10)
                  (%string-from-codes codes)))
              (%rl-dispatch command state))))))


(defun %native-prompt (row)
  (%rl-screen-tail nil 0 row nil 0 0 -2))


(defun %native-read-line () (read-line (quote native)))


(defun read-line (&rest prompt)
  (progn
    (poke 255 141 255)
    (poke 255 140 0)
    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))
    (poke 255 141 0)
    (let* ((size (screen-size))
           (full-columns (car size))
           (screen-row (- (car (cdr size)) 1))
           (native (if prompt 't nil))
           (columns (if native (- full-columns 8) full-columns))
           (row (if native (- 0 (+ screen-row 34)) screen-row))
           (head (cons 0 nil))
           (state (list head head head 0 0 0 columns row nil))
           (answer
            (progn
              (if native (%native-prompt screen-row) nil)
              (%rl-screen-tail nil 0 columns 0 0 columns row)
              (%read-line-loop state))))
      (progn
        (poke 255 141 255)
        answer))))

(defun %rl-rows (codes index stop cursor base columns origin)
  (let* ((column (mod index columns))
         (rest (- columns column))
         (want (- stop index))
         (left (+ origin column))
         (spill (< rest want)))
    (progn
      (%rl-render codes index left (+ left (if spill rest want)) cursor
                  (+ base (/ index columns)))
      (if spill
          (%rl-rows (nthcdr rest codes) (+ index rest) stop cursor base
                    columns origin)
          nil))))

; The surface's sole screen seam.  ROW is the historical encoded row and TOP
; the wrap lift, so the first touched window is painted here and only a paint
; that spills past it walks on.  CURSOR -1 on an indented origin still clears
; every owned row across the full screen width, which is how an accepted line
; hands its rows back to sequential output.
