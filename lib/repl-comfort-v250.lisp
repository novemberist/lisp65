; Heap-backed input loop for interactive work.  The native C REPL remains the
; fail-closed fallback. The v250 successor owns the sticky handshake/history.
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

; History is published before evaluation, so a native unwind preserves it.
(defun %repl-loop (history)
  (let ((source (%repl-step history "" 0)))
    (if source
        (let* ((ready (%comfort-request 1))
               (saved (set-symbol-value '%comfort-history
                       (cons source (%repl-read -1 history nil 0 0))))
               (form (read-from-string (string-append "(progn " source "
)")))
               (result (progn (poke 255 141 255) (lcc-run form))))
          (poke 255 140 0)
          (poke 255 141 0)
          (write result)
          (terpri)
          (%repl-loop saved))
        (progn (poke 255 141 255)
               (%comfort-request 0)
               nil))))

; lib/comfort-state-address.lisp supplies privately inlined address constants
; generated from the successor's high-BSS owner by comfort_state_address.py.
(defun %comfort-request (state)
  (poke (%comfort-state-hi) (%comfort-state-lo) state))

; Explicit entry and submitted-input acknowledgement request recovery.
(defun repl ()
  (%comfort-request 1)
  (if (boundp '%comfort-history) nil (set-symbol-value '%comfort-history nil))
  (poke 255 141 255)
  (poke 255 140 0)
  (dotimes (counter 4 nil)
    (poke 188 (+ 252 counter) 0))
  (poke 255 141 0)
  (%repl-loop (symbol-value '%comfort-history)))
