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

(defun %lt-read (prefix history history-index columns row reopen)
  (if (numberp prefix)
      (if (>= (length history) 10) (butlast history) history)
      (if (or (> (string-length prefix) 250)
              (and (> history-index 0)
                   (> (+ (string-length prefix) (string-length reopen)) 640))) -2
          (%lt-result (%lt-editor prefix history history-index columns row)
                      history history-index columns row reopen))))

; This boundary helper returns only after the resident editor has finished.
(defun %lt-editor (prefix history history-index columns row)
  (let* ((codes (%string-codes prefix))
         (length (length codes))
         (head (cons 0 codes))
         (tail (last head))
         (top (/ length columns))
         (state (list head tail tail length length top columns row
                      history history-index)))
    (%rl-screen-tail codes 0 (* columns (+ top 1)) length top columns row)
    ; The inlined caller survives polling: release deleted prefix chains for
    ; both reopen and history recall (the latter also affected 2.5.1).
    (setq codes nil)
    (%read-line-loop state)))

(defun %lt-result (result history history-index columns row reopen)
  (if (or (eq result 1108) (eq result 1003))
      (let* ((next-index
              (if (= result 1108)
                  (if (< history-index (length history))
                      (+ history-index 1) history-index)
                  (if (> history-index 0) (- history-index 1) 0)))
             (next-prefix
              (if (= next-index 0) ""
                  (car (nthcdr (- next-index 1) history)))))
        (%lt-read next-prefix history next-index columns row reopen))
      (if (eq result 1101)
          (if (> (string-length reopen) 0) result
              (%lt-read "" history history-index columns row reopen))
          result)))


; The product has no screen-write-string (CALLPRIM 12 is compiled out; the
; resident screen-bulk-p is a constant nil), so the prompt is five cells.
(defun %repl-prompt (row)
  (progn
    (screen-put-char 0 row 108 1)
    (screen-put-char 1 row 54 1)
    (screen-put-char 2 row 53 1)
    (screen-put-char 3 row 62 1)
    (screen-put-char 4 row 32 1)))

; packed carries depth and lexical state with pending; zero is a fresh prompt.
(defun %repl-read (prefix history history-index columns row)
  (%lt-read prefix history history-index columns row ""))

(defun %repl-step (history pending packed)
  (if (and (<= (length history) 10) (%lt-history history))
      (%lt-drive history pending packed nil)
      (progn (write-line "*** history limit") nil)))

; History is published before evaluation, so a native unwind preserves it.
(defun %repl-loop (history)
  (let ((source (%repl-step history "" 0)))
    (if source
        (let* ((ready (%comfort-request 1))
               (saved (set-symbol-value '%comfort-history
                       (if (<= (string-length source) 250)
                           (cons source (%repl-read -1 history nil 0 0))
                           (progn (write-line "*** history limit") history))))
               (form (read-from-string (%lt-cat "(progn " source "
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
