; Cold Bank-2 line input over the public key-event and screen primitives.
; The editor owns its own screen row and, once the line is longer than one
; row, the rows directly above it.  Its mutable sentinel chain stays in
; logical order: CURSOR is the cell immediately before point.  The base state
; has eight cells; a shelf caller may append history and history-index cells.
; Sentinel CAR is a reverse stack of cells strictly before CURSOR.  A numeric
; CAR marks a newly constructed/recalled line, initialized once before polling.
; Insert and Right push one link; Backspace and Left pop it. Home clears it;
; End rebuilds it. Links are ordinary traced heap conses, never resident data.
; Length/position/tail stay in their existing slots; wrap does not invalidate
; logical links. History/continuation construct a fresh sentinel as before.
;
; Soft wrap (v2.1 line-wrap card).  State cell 5 is TOP: how many screen rows
; the line is lifted above its own row, i.e. LENGTH/COLUMNS.  Logical index I
; lives on screen row ROW-TOP+I/COLUMNS at column ORIGIN+I mod COLUMNS, so the
; last wrapped row always stays on the editor's own row and the line grows
; upward.  There is no screen-scroll primitive on this surface, and no row
; exists below the editor's row, so growth cannot go downward; rows lifted
; above row 0 are simply dropped by screen-put-char, which keeps point and the
; line's tail visible.  The 250-code input cap needs at most four rows.

; One software phase owner over the existing product frame byte.  MARKED says
; that the cursor cell is also one of the delimiter cells: hidden cursor paint
; must then preserve the delimiter attribute instead of erasing it.
(defun %frame-low ()
  (peek 255 131))

(defun %cursor-blink (cursor position top columns row idle force)
  (let* ((blink (car idle))
         (now (%frame-low))
         (elapsed (mod (- now (car blink)) 256)))
    (if (if force 't (>= elapsed 32))
        (let* ((visible (if force 't (not (cdr blink)))))
          (progn
            (rplaca blink now)
            (rplacd blink visible)
            (screen-put-char (mod position columns)
                             (if (< row 0) row
                                 (+ (- row top) (/ position columns)))
                             (if (cdr cursor) (car (cdr cursor)) 32)
                             (if visible 129
                                 (if (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle))))))))))) 7 1)))
            nil))
        nil)))

; Derive a new line-editor job without scanning a code unit.  Ordinary cells
; settle immediately; only a delimiter enters the prefix pass.
(defun %rl-start (state)
  (let* ((idle (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
         (position (car (cdr (cdr (cdr state)))))
         (length (car (cdr (cdr (cdr (cdr state))))))
         (cursor (car (cdr state)))
         (point (if (< position length) position
                    (if (> position 0) (- position 1) -1)))
         (cell (if (< position length) (cdr cursor) cursor))
         (code (if (>= point 0) (car cell) 0)))
    (progn
      (rplaca (cdr (cdr idle)) point)
      (rplaca (cdr (cdr (cdr idle))) 0)
      (rplaca (cdr (cdr (cdr (cdr idle)))) 0)
      (rplaca (cdr (cdr (cdr (cdr (cdr idle))))) (cdr (car state)))
      (rplaca (cdr idle)
              (if (or (= code 40) (or (= code 41) (= code 34))) 1 0))
      nil)))

; Complete the prefix-to-partner transition after the final prefix chunk.
(defun %rl-kind (state result next-codes)
  (let* ((idle (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
         (point (car (cdr (cdr idle))))
         (kind (%sexp-match (car next-codes) result)))
    (progn
      (rplaca (cdr idle) (if (= kind 0) 0 (+ kind 1)))
      (rplaca (cdr (cdr (cdr idle))) (if (= (mod kind 2) 1) (+ point 1) 0))
      (rplaca (cdr (cdr (cdr (cdr idle)))) (if (= kind 1) 4 (if (= kind 3) 2 0)))
      (rplaca (cdr (cdr (cdr (cdr (cdr idle)))))
              (if (= (mod kind 2) 1) (cdr next-codes) (cdr (car state))))
      (rplaca (cdr (cdr (cdr (cdr (cdr (cdr idle)))))) (if (= kind 2) (/ result 4) 0))
      nil)))

; Exactly one self-capped prefix chunk.
(defun %rl-scan (state)
  (let* ((idle (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
         (point (car (cdr (cdr idle))))
         (i (car (cdr (cdr (cdr idle)))))
         (codes-at-i (car (cdr (cdr (cdr (cdr (cdr idle)))))))
         (result (%rl-idle 0 (cdr (car state)) codes-at-i point i
                           (car (cdr (cdr (cdr (cdr idle))))) nil nil nil))
         (next (if (< (+ i 3) point) (+ i 3) point))
         (next-codes (nthcdr (- next i) codes-at-i)))
    (progn
      (rplaca (cdr (cdr (cdr idle))) next)
      (rplaca (cdr (cdr (cdr (cdr idle)))) result)
      (rplaca (cdr (cdr (cdr (cdr (cdr idle))))) next-codes)
      (if (= next point) (%rl-kind state result next-codes) nil))))

; Exactly one self-capped forward partner chunk.  NIL means incomplete;
; zero means complete without a partner; partner+1 preserves index zero.
(defun %rl-close (state)
  (let* ((idle (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
         (kind (- (car (cdr idle)) 1))
         (i (car (cdr (cdr (cdr idle)))))
         (codes-at-i (car (cdr (cdr (cdr (cdr (cdr idle)))))))
         (limit (car (cdr (cdr (cdr (cdr state))))))
         (result (%rl-idle 1 (cdr (car state)) codes-at-i limit i
                           (car (cdr (cdr (cdr (cdr idle)))))
                           (if (= kind 1) 41 34) nil nil))
         (next (if (< (+ i 3) limit) (+ i 3) limit)))
    (if (< result 0)
        (progn (rplaca (cdr idle) 0) (- 0 result))
        (if (= next limit)
            (progn (rplaca (cdr idle) 0) 0)
            (progn
              (rplaca (cdr (cdr (cdr idle))) next)
              (rplaca (cdr (cdr (cdr (cdr idle)))) result)
              (rplaca (cdr (cdr (cdr (cdr (cdr idle)))))
                      (nthcdr (- next i) codes-at-i))
              nil)))))

; Exactly one self-capped opening replay chunk, with the same result encoding.
(defun %rl-open (state)
  (let* ((idle (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
         (kind (- (car (cdr idle)) 1))
         (i (car (cdr (cdr (cdr idle)))))
         (codes-at-i (car (cdr (cdr (cdr (cdr (cdr idle)))))))
         (limit (car (cdr (cdr idle))))
         (result (%rl-idle 2 (cdr (car state)) codes-at-i limit i
                           (car (cdr (cdr (cdr (cdr idle))))) (car (cdr (cdr (cdr (cdr (cdr (cdr idle)))))))
                           (if (= kind 2) 40 34) nil))
         (next (if (< (+ i 3) limit) (+ i 3) limit)))
    (if (= next limit)
        (progn (rplaca (cdr idle) 0) (mod result 256))
        (progn
          (rplaca (cdr (cdr (cdr idle))) next)
          (rplaca (cdr (cdr (cdr (cdr idle)))) result)
          (rplaca (cdr (cdr (cdr (cdr (cdr idle))))) (nthcdr (- next i) codes-at-i))
          nil))))

; The line surface's sole seam into every shared matcher pass and the composed
; paint transition.  MODE 0/1/2 selects scan/close/open; 3 fans the shared pair
; painter over the wrapped rows, taking A/B/C/D/E/F/G/H as source, old pair,
; new pair, wrap lift, columns, cursor, row and row counter.  Screen row K of
; the owned block carries exactly the logical window [K*COLUMNS,(K+1)*COLUMNS),
; which is also the window base the shared painter takes as its origin, so an
; origin-0 surface needs no further mapping.  A negative row is one of the
; indented native/prompted encodings; those never reached a real screen row
; through this seam and keep that single inert historical call.
(defun %rl-idle (mode a b c d e f g h)
  (if (= mode 0)
      (%sexp-scan a b c d e nil)
      (if (= mode 1)
          (%sexp-close a b c d e f nil)
          (if (= mode 2)
              (%sexp-open a b c d e f g nil)
              (if (< g 0)
                  (%sexp-paint a b c 0 g e f 0)
                  (if (> h d)
                      nil
                      (progn
                        (%sexp-paint a b c (* h e) (+ (- g d) h) e f 0)
                        (%rl-idle 3 a b c d e f g (+ h 1)))))))))

; Clear the surface-owned pair at an input handoff or unmatched completion.
(defun %rl-clear (codes cursor position top columns row idle event)
  (let* ((i7 (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle))))))))
         (active (car i7))
         (pair-a (car (cdr i7)))
         (pair-b (car (cdr (cdr i7))))
         (old (if (= active 1) pair-a (if (= active 2) pair-b nil)))
         (marked (cdr (cdr (cdr i7)))))
    (progn
      (if old
          (%rl-idle 3 codes old nil top
                    columns position row 0) nil)
      (rplaca i7 0)
      (rplaca marked nil)
      (if event (rplaca (cdr idle) -1) nil)
      (if event (%cursor-blink cursor position top columns row idle 't) nil)
      (if event event (if old 't nil)))))

; Install one completed partner result (ANSWER is partner+1).
(defun %rl-paint (state answer)
  (let* ((idle (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr state))))))))))))
         (active (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle)))))))))
         (pair-a (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle))))))))))
         (pair-b (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle)))))))))))
         (old (if (= active 1) pair-a (if (= active 2) pair-b nil)))
         (new (if (= active 1) pair-b pair-a))
         (found (- answer 1))
         (position (car (cdr (cdr (cdr state))))))
    (progn
      (rplaca new (car (cdr (cdr idle))))
      (rplacd new found)
      (%rl-idle 3 (cdr (car state)) old new (car (cdr (cdr (cdr (cdr (cdr state))))))
                (car (cdr (cdr (cdr (cdr (cdr (cdr state))))))) position (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))) 0)
      (rplaca (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle))))))) (if (= active 1) 2 1))
      (rplaca (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr idle))))))))))
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
    (progn (%cursor-blink (car s1) (car s3) (car s5) (car (cdr s5))
                          (car s7) idle painted)
           nil)))

(defun %rl-poll (state)
  (let* ((s1 (cdr state))
         (s3 (cdr (cdr s1)))
         (s5 (cdr (cdr s3)))
         (s7 (cdr (cdr s5)))
         (tail (cdr s7))
         (idle (car (cdr (cdr tail)))))
    (if (numberp (car (car state)))
        (let ((head (car state)) (at (car state)))
          (progn
            (rplaca head nil)
            (dotimes (i (car s3) nil)
              (progn (rplaca head (cons at (car head)))
                     (setq at (cdr at))))))
        nil)
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

; Paint a wrapped range that spans more than one window.  Window K, the logical
; range [K*COLUMNS, (K+1)*COLUMNS), lands on screen row BASE+K from screen
; column ORIGIN: one shared row painter per touched window, no division per
; cell, and the walk is a self tail call.  A paint that stays inside one window
; is finished by the seam itself, so a keystroke pays this only across a wrap.
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

; The surface's sole screen seam.  ROW is the historical encoded row and TOP
; the wrap lift, so the first touched window is painted here and only a paint
; that spills past it walks on.  CURSOR -1 on an indented origin still clears
; every owned row across the full screen width, which is how an accepted line
; hands its rows back to sequential output.
(defun %rl-label (row top clear)
  (if (< row -2)
      (let* ((native (< row -34))
             (text (if native "lisp65> " "l65> "))
             (base (- (if native (- -34 row) (- -2 row)) top)))
        (dotimes (at (string-length text) nil)
          (screen-put-char at base (if clear 32 (string-ref text at)) 1)))
      nil))

(defun %rl-lift (row top next-top columns)
  (progn
    (%rl-label row top 't)
    (%rl-label row next-top nil)
    (if columns (%rl-screen-tail nil 0 columns -2 top columns row) nil)))

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

; Removal shrinks the line by one cell.  While the wrap lift is unchanged the
; tail from point through the cell AFTER the old end is redrawn -- stop is
; NEXT-LENGTH + 2, i.e. one past the old end.  A Backspace at the end of the
; line leaves point one cell to its left, and the cell point just gave up was
; carrying the cursor as a reverse space (attr 129, bit 7 of the screen code);
; a range that stopped at the old length never repainted it, so every Backspace
; left a reverse block standing (owner device report).  The lift cannot have
; stayed put when the old end sat on the last column of its window, so the
; widened stop always lands inside a row this line still owns.  When the lift
; drops the whole block moves down one row, so the row the block gives up is
; blanked first and the block is then redrawn whole, trailing blanks included.
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

; Point moves never change the wrap lift or any code, so exactly the two cells
; that change reverse video are redrawn, on whichever rows they fall.
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

; The batch loop touches no screen cell and no wrap state; cell 5 is settled
; once, after the last code of the batch.  A batch that did not change the
; wrap lift redraws only from the first dirty index through the cell after the
; new end; a batch that lifted the block redraws every owned row, because all
; of them moved up by one.
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
           (%read-line-loop state)))
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

; Direct painting and sequential output have distinct cursors. Clear the
; temporary input surface, then hand the accepted line to sequential output
; with its prompt first. Comfort continuations have the tenth history-index
; cell set to a number: clear and echo even with no label or indentation.
; Plain unprompted read-line retains its existing direct-screen contract.
; No cursor positioning escape or native ABI is added.
(defun %rl-end (state)
  (let* ((codes (cdr (car state)))
         (row (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))))
         (text (%string-from-codes codes)))
    (progn
      (if (or (< row -2) (numberp (car (nthcdr 9 state))))
          (progn
            (%rl-screen-tail nil 0
                             (* (car (nthcdr 6 state))
                                (+ (car (nthcdr 5 state)) 1)) -1 (car (cdr (cdr (cdr (cdr (cdr state))))))
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

(defun %read-line-loop (state)
  (let* ((event (%rl-poll state))
         (code (if (numberp event) event (if event (cadr event) 0))))
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

(defun %native-prompt (row)
  (%rl-screen-tail nil 0 row nil 0 0 -2))

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
      (%rl-screen-tail nil 0 columns 0 0 columns row)
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
