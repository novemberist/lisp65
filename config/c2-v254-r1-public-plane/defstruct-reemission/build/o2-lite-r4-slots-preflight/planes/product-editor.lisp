(defun %rl-render (codes index column stop cursor row) (if (= row -1) (key-event 2) (if (< column stop) (let* ((present (if codes (quote t) nil)) (at-cursor (= index cursor)) (code (if present (car codes) 32))) (progn (screen-put-char column row code (if at-cursor 129 1)) (%rl-render (if present (cdr codes) nil) (+ index 1) (+ column 1) stop cursor row))) nil)))

(defun %rl-screen-tail (codes index stop cursor top columns row) (if (= row -2) (let ((text "lisp65> ")) (dotimes (at 8 nil) (screen-put-char at stop (string-ref text at) 1))) (let* ((native (< row -34)) (prompted (< row -2)) (origin (if native 8 (if prompted 5 0))) (base (- (if native (- -34 row) (if prompted (- -2 row) row)) top))) (if (and prompted (= cursor -1)) (let* ((width (car (screen-size)))) (%rl-rows nil 0 (* width (+ top 1)) -1 base width 0)) (let* ((column (mod index columns)) (want (- stop index))) (if (< (- columns column) want) (%rl-rows codes index stop cursor base columns origin) (%rl-render codes index (+ origin column) (+ origin (+ column want)) cursor (+ base (/ index columns)))))))))

(defun %rl-cut (state before removed)
  (let* ((head (car state))
         (tail (car (cdr (cdr state))))
         (position (car (cdr (cdr (cdr state)))))
         (next-length (- (car (cdr (cdr (cdr (cdr state))))) 1))
         (top (car (cdr (cdr (cdr (cdr (cdr state)))))))
         (columns (car (cdr (cdr (cdr (cdr (cdr (cdr state))))))))
         (row (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))))
         (next-position (if (eq removed (car (cdr state)))
                            (- position 1) position))
         (next-top (/ next-length columns)))
    (progn
      (if (eq removed (car (cdr state)))
          (rplaca head (cdr (car head))) nil)
      (rplacd before (cdr removed))
      (rplaca (cdr state) before)
      (if (eq removed tail) (rplaca (cdr (cdr state)) before) nil)
      (rplaca (cdr (cdr (cdr state))) next-position)
      (rplaca (cdr (cdr (cdr (cdr state)))) next-length)
      (rplaca (cdr (cdr (cdr (cdr (cdr state))))) next-top)
      (if (= next-top top)
          (%rl-screen-tail (cdr before) next-position
                           (+ next-length 2) next-position next-top columns row)
          (progn
            (%rl-lift row top next-top columns)
            (%rl-screen-tail (cdr head) 0 (* columns (+ next-top 1))
                             next-position next-top columns row)))
      (%read-line-loop state))))

(defun %rl-move (state next-cursor next-position)
  (let* ((head (car state))
         (old-cursor (car (cdr state)))
         (position (car (cdr (cdr (cdr state)))))
         (top (car (cdr (cdr (cdr (cdr (cdr state)))))))
         (columns (car (cdr (cdr (cdr (cdr (cdr (cdr state))))))))
         (row (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))
    (progn
      (if (= next-position position) nil
          (if (= next-position 0) (rplaca head nil)
              (if (= next-position (- position 1))
                  (rplaca head (cdr (car head)))
                  (if (= next-position (+ position 1))
                      (rplaca head (cons old-cursor (car head)))
                      (let ((at head))
                        (progn
                          (rplaca head nil)
                          (dotimes (i next-position nil)
                            (progn (rplaca head (cons at (car head)))
                                   (setq at (cdr at))))))))))
      (rplaca (cdr state) next-cursor)
      (rplaca (cdr (cdr (cdr state))) next-position)
      (%rl-screen-tail (cdr old-cursor) position (+ position 1)
                       next-position top columns row)
      (%rl-screen-tail (cdr next-cursor) next-position
                       (+ next-position 1) next-position top columns row)
      (%read-line-loop state))))

(defun %rl-put (code state cursor dirty anchor)
  (let* ((s1 (cdr state)) (s3 (cdr (cdr s1)))
         (s4 (cdr s3)) (s5 (cdr s4))
         (inserted (cons code (cdr cursor)))
         (next-position (+ (car s3) 1)))
    (progn
      (rplaca (car state) (cons cursor (car (car state))))
      (rplacd cursor inserted)
      (rplaca s1 inserted)
      (if (cdr inserted) nil (rplaca (cdr s1) inserted))
      (rplaca s3 next-position)
      (rplaca s4 (+ (car s4) 1))
      (let* ((next-code (if (= (car s4) 250) nil (key-event 3))))
        (if next-code
            (%rl-put next-code state inserted dirty anchor)
            (let* ((columns (car (cdr s5)))
                   (top (car s5))
                   (row (car (cdr (cdr s5))))
                   (next-top (/ (car s4) columns)))
            (progn
              (rplaca s5 next-top)
              (if (= next-top top)
                  (%rl-screen-tail
                   (cdr anchor) dirty (+ (car s4) 1)
                   next-position next-top columns row)
                  (progn
                    (%rl-lift row top next-top nil)
                    (%rl-screen-tail
                     (cdr (car state)) 0 (* columns (+ next-top 1))
                     next-position next-top columns row)))
              (%read-line-loop state))))))))

(defun %rl-dispatch (command state)
  (let* ((cursor (car (cdr state)))
         (position (car (cdr (cdr (cdr state)))))
         (length (car (cdr (cdr (cdr (cdr state)))))))
    (cond
      ((= command 1101)
       (if (> position 0)
           (%rl-cut state (car (car (car state))) cursor)
           (%rl-empty-backspace state length command)))
      ((= command 1102)
       (if (cdr cursor) (%rl-cut state cursor (cdr cursor))
           (%read-line-loop state)))
      ((= command 1106)
       (if (> position 0)
           (%rl-move state (car (car (car state))) (- position 1))
           (%read-line-loop state)))
      ((= command 1107)
       (if (< position length)
           (%rl-move state (cdr cursor) (+ position 1))
           (%read-line-loop state)))
      ((= command 1104) (%rl-move state (car state) 0))
      ((= command 1103) (%rl-move state (car (cdr (cdr state))) length))
      ((or (= command 1108) (= command 1003))
       (if (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))) command (%read-line-loop state)))
      (t (%read-line-loop state)))))

(defun %read-line-loop (state)
  (let* ((event (progn (if (numberp (car (car state))) (let ((head (car state)) (at (car state))) (progn (rplaca head nil) (dotimes (i (car (cdr (cdr (cdr state)))) nil) (progn (rplaca head (cons at (car head))) (setq at (cdr at)))))) nil) (if (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))) (%rl-render nil 0 0 0 0 -1) (key-event 1))))
         (code (if (numberp event) event (if event (car (cdr event)) 0))))
    (if (and (>= code 32) (<= code 126))
        (if (< (car (cdr (cdr (cdr (cdr state))))) 250)
            (%rl-put code state (car (cdr state))
                     (car (cdr (cdr (cdr state)))) (car (cdr state)))
            (%read-line-loop state))
        (let* ((command
;; BEGIN GENERATED REPL LINE KEYMAP
          ((lambda (binding) (if binding (cdr binding) 0))
           (assoc code
                  (quote ((13 . 1109) (20 . 1101) (157 . 1106) (29 . 1107) (145 . 1108) (17 . 1003) (4 . 1102) (6 . 1107) (2 . 1106) (1 . 1104) (5 . 1103) (127 . 1101)))))
;; END GENERATED REPL LINE KEYMAP
               ))
          (if (= command 1109)
              (%rl-end state)
              (%rl-dispatch command state))))))

(defun %native-prompt (row) (%rl-screen-tail nil 0 row nil 0 0 -2))

(defun %native-read-line () (read-line (quote native)))

(defun read-line (&rest prompt) (progn (poke 255 141 255) (poke 255 140 0) (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0)) (poke 255 141 0) (let* ((size (screen-size)) (full-columns (car size)) (screen-row (- (car (cdr size)) 1)) (native (if prompt (quote t) nil)) (columns (if native (- full-columns 8) full-columns)) (row (if native (- 0 (+ screen-row 34)) screen-row)) (head (cons 0 nil)) (state (list head head head 0 0 0 columns row nil)) (answer (progn (if native (%native-prompt screen-row) nil) (%rl-screen-tail nil 0 columns 0 0 columns row) (%read-line-loop state)))) (progn (poke 255 141 255) answer))))

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
          (progn
            (dotimes (i rest nil) (setq codes (cdr codes)))
            (%rl-rows codes (+ index rest) stop cursor base columns origin))
          nil))))

(defun %rl-end (state)
  ; Point will not move again. Release predecessor links before output copying.
  (rplaca (car state) nil)
  (let* ((codes (cdr (car state)))
         (row (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))))
         (text (%string-from-codes codes)))
    (progn
      (if (or (< row -2) (numberp (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
          (progn
            (%rl-screen-tail nil 0
                             (* (car (cdr (cdr (cdr (cdr (cdr (cdr state)))))))
                                (+ (car (cdr (cdr (cdr (cdr (cdr state)))))) 1)) -1 (car (cdr (cdr (cdr (cdr (cdr state))))))
                             (car (cdr (cdr (cdr (cdr (cdr (cdr state))))))) row)
            (if (< row -2)
                (write-string (if (< row -34) "lisp65> " "l65> "))
                nil)
            (write-string text))
          (let ((position (car (cdr (cdr (cdr state))))))
            (%rl-screen-tail (cdr (car (cdr state))) position (+ position 1)
                             -1 (car (cdr (cdr (cdr (cdr (cdr state))))))
                             (car (cdr (cdr (cdr (cdr (cdr (cdr state))))))) row)))
      (write-char 10)
      text)))

(defun %rl-lift (row top next-top columns) (progn (%rl-label row top (quote t)) (%rl-label row next-top nil) (if columns (%rl-screen-tail nil 0 columns -2 top columns row) nil)))

(defun %rl-label (row top clear) (if (< row -2) (let* ((native (< row -34)) (text (if native "lisp65> " "l65> ")) (base (- (if native (- -34 row) (- -2 row)) top))) (dotimes (at (string-length text) nil) (screen-put-char at base (if clear 32 (string-ref text at)) 1))) nil))

(defun %rl-empty-backspace (state length command)
  (if (and (= length 0) (numberp (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
      command
      (%read-line-loop state)))
