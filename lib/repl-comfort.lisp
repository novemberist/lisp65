; Heap-backed input loop for interactive work.  The native C REPL remains the
; boot and fail-closed fallback; this shelf only owns input assembly.

(defun %repl-read (prefix history history-index columns row)
  (if (numberp prefix)
      (if (>= (length history) 10) (butlast history) history)
      (let* ((codes (%string-codes prefix))
         (length (length codes))
         (head (cons 0 codes))
         (tail (last head))
         (start (if (>= length columns)
                    (- length (- columns 1)) 0))
         (state (list head tail tail length length start columns row
                      history history-index))
         (result
          (progn
            (%rl-screen-tail (nthcdr start codes) start 0 columns length row)
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
                (progn
            (%rl-screen-tail nil 0 0 (- row 1) 0 -2)
                  (screen-write-string 0 row "l65> "))
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
      (t (repl 'eval source history)))))

(defun repl (&rest state)
  (cond
    ((and state (eq (car state) 'eval))
     (let* ((source (car (cdr state)))
            (history (car (cdr (cdr state))))
            (form (read-from-string (string-append "(progn " source ")")))
            (result (progn (poke 255 141 255) (lcc-run form)))
            (older (%repl-read -1 history nil 0 0)))
       (poke 255 140 0)
       (poke 255 141 0)
       (write result)
       (terpri)
       (%repl-step (cons source older) "" 0)))
    (t
     (let* ((answer
             (progn
               ; The negative tail closes capture while head and all four
               ; counters acquire one bound origin.  The final tail store is
               ; the single activation/commit edge seen by the IRQ producer.
               (poke 255 141 255)
               (poke 255 140 0)
               (dotimes (counter 4 nil)
                 (poke 188 (+ 252 counter) 0))
               (poke 255 141 0)
               (%repl-step nil "" 0))))
       (poke 255 141 255)
       answer))))
