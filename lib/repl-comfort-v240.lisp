; Heap-backed input loop for interactive work.  The native C REPL remains the
; boot and fail-closed fallback; this shelf only owns input assembly.
;
; The editor soft-wraps: state cell 5 is the wrap lift LENGTH/COLUMNS, not a
; horizontal viewport start, and a prefix longer than one row therefore opens
; on as many rows as it needs, ending on the owned input row.
;
; Resident row protocol (no additional Comfort tags):
;   row >= 0: explicit read-line row, origin column 0.
;   row = -1: private key-event read in %rl-render, not a screen row.
;   row = -2: native "lisp65> " painter; stop is its screen row.
;   -34 <= row < -2: prompted Comfort row = -row-2, origin 5.
;   row < -34: native prompted row = -row-34, origin 8.
; Return clears the owned input row through the resident editor; sequential
; output keeps its own cursor and scrolls before the next input row is drawn.
; Comfort paints only l65> on that input row. It must never call the -2
; native painter on the preceding output row (that overwrites diagnostics).

(defun %repl-read (prefix history history-index columns row)
  (if (numberp prefix)
      (if (>= (length history) 10) (butlast history) history)
      (let* ((codes (%string-codes prefix))
         (length (length codes))
         (head (cons 0 codes))
         (tail (last head))
         (top (/ length columns))
         (state (list head tail tail length length top columns row
                      history history-index))
         (result
          (progn
            (%rl-screen-tail codes 0 (* columns (+ top 1)) length top
                             columns row)
            (%read-line-loop state))))
    (progn
      (if (numberp result)
          (let* ((next-index
                  (if (= result 1108)
                      (if (< history-index (length history))
                          (+ history-index 1) history-index)
                      (if (> history-index 0) (- history-index 1) 0)))
                 (next-prefix
                  (if (= next-index 0) ""
                      (car (nthcdr (- next-index 1) history)))))
            (%repl-read next-prefix history next-index columns row))
          result)))))


; The product has no screen-write-string (CALLPRIM 12 is compiled out; the
; resident screen-bulk-p is a constant nil), so the prompt is five cells.
(defun %repl-prompt (row)
  (progn
    (screen-put-char 0 row 108 1)
    (screen-put-char 1 row 54 1)
    (screen-put-char 2 row 53 1)
    (screen-put-char 3 row 62 1)
    (screen-put-char 4 row 32 1)))

(defun %repl-step (history pending depth)
  (let* ((size (screen-size))
         (columns (car size))
         (row (- (car (cdr size)) 1))
         (top (= depth 0))
         (indent (substring "                    " 0
                            (* 2 (if (> depth 10) 10 depth))))
         (line
          (progn
            (if top
                (%repl-prompt row)
                nil)
            (%repl-read indent history 0
                        (if top (- columns 5) columns)
                        (if top (- 0 (+ row 2)) row))))
         (next-depth (%ide-line-net-depth (%string-codes line) 0 depth))
         (source
          (if (> (string-length pending) 0)
              (string-append pending (%string-from-codes (list 10)) line)
              line)))
    (cond
      ((< next-depth 0)
       (progn
         (write-line "*** reader: unmatched close parenthesis")
         (%repl-step history "" 0)))
      ((> next-depth 0) (%repl-step history source next-depth))
      ((= (string-length source) 0) nil)
      (t source))))

; One loop frame.  The entry arm tail-calls the loop arm, and the loop arm
; tail-calls itself after each evaluation, so while user code runs the only
; suspended Comfort activation is this one, waiting on lcc-run.  %repl-step
; returns the balanced source (or nil for an empty line) and holds no frame
; during evaluation.  The capture epilogue runs where the loop ends.
(defun repl (&rest state)
  (cond
    ((and state (eq (car state) 'eval))
     (let* ((history (car (cdr state)))
            (source (%repl-step history "" 0)))
       (if source
           ; The closing parenthesis follows a newline so that a ';' comment
           ; ending the last input line cannot swallow it (comfort-library
           ; card, emulator row c4-comment-paren).
           (let* ((form (read-from-string (string-append "(progn " source "
)")))
                  (result (progn (poke 255 141 255) (lcc-run form))))
             (poke 255 140 0)
             (poke 255 141 0)
             (write result)
             (terpri)
             (repl 'eval (cons source (%repl-read -1 history nil 0 0))))
           (progn (poke 255 141 255) nil))))
    (t
     (progn
       ; The negative tail closes capture while head and all four
       ; counters acquire one bound origin.  The final tail store is
       ; the single activation/commit edge seen by the IRQ producer.
       (poke 255 141 255)
       (poke 255 140 0)
       (dotimes (counter 4 nil)
         (poke 188 (+ 252 counter) 0))
       (poke 255 141 0)
       (repl 'eval nil)))))
