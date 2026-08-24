; Cold Bank-2 line input over the public key-event and screen primitives.
; The editor owns the last screen row.  Its mutable sentinel chain stays in
; logical order: CURSOR is the cell immediately before point.  The base state
; has eight cells; a shelf caller may append history and history-index cells.
; Only an accepted printable character allocates after a key-event boundary.

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
      (progn
        (write-char 19)
        (dotimes (line stop nil) (write-char 17)))
      (let* ((prompted (< row -2)))
        (if (and prompted (= cursor -1))
            (%rl-render nil 0 0 (car (screen-size)) -2
                        (- 0 (+ row 2)))
            (if (and prompted (< column 0))
                (%rl-screen-tail (if codes (cdr codes) nil)
                                 (+ index 1) (+ column 1) stop cursor row)
                (let* ((origin (if prompted 5 0)))
                  (%rl-render codes index (+ column origin) (+ stop origin)
                              cursor (if prompted (- 0 (+ row 2)) row))))))))

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

(defun read-line ()
  (let* ((size (screen-size))
         (columns (car size))
         (row (- (car (cdr size)) 1))
         (head (cons 0 nil))
         (state (list head head head 0 0 0 columns row)))
    (progn
      (%rl-screen-tail nil 0 0 columns 0 row)
      (%read-line-loop state))))
