;; Container-private IDE state reuses the value cells of public function
;; symbols. Lisp-2 keeps those cells independent from the function bindings,
;; so no private state name consumes an interned symbol or directory entry.

(defun ide-make-state (buffer)
  (list buffer nil 0 nil nil nil nil (%ide-budget-string)))

(defun ide-state-buffer (state)
  (car state))

(defun ide-state-message (state)
  (car (cdr state)))

(defun ide-state-row-offset (state)
  (car (cdr (cdr state))))

;; Optional convenience-library seam. IDEX later redefines exactly this hook;
;; symbolic CALL resolution then sees the current function cell without a
;; special runtime or ABI case. The core remains usable without IDEX.
(defun %ide-x (kind state a b)
  (cond ((and (eq kind 'apply) (eq a 1118))
         (%ide-state-with-buffer state (ide-kill-line (ide-state-buffer state))))
        ((and (eq kind 'apply) (eq a 1119))
         (%ide-state-with-buffer state (ide-yank (ide-state-buffer state))))
        (t (%ide-state-with-message state "load idex"))))

(defun %ide-state-with-message (state message)
  (let* ((s1 (cdr state))
         (s2 (cdr s1))
         (s3 (cdr s2))
         (s4 (cdr s3))
         (s5 (cdr s4))
         (s6 (cdr s5))
         (s7 (cdr s6)))
    (list (car state)
          message
          (car s2)
          (car s3)
          (car s4)
          (car s5)
          (car s6)
          (car s7))))

(defun %ide-mini-status-line ()
  ((lambda (mini)
     ((lambda (prompt input default)
        (if (> (string-length input) 0)
            (string-append prompt input)
            (if (> (string-length default) 0)
                (string-append prompt (string-append "[" (string-append default "]")))
                prompt)))
      (car (cdr mini))
      (car (cdr (cdr mini)))
      (car (cdr (cdr (cdr mini))))))
   (symbol-value (quote ide-step))))

(defun %ide-mini-set (state action prompt input default options)
  (progn
    (set-symbol-value (quote ide-step) (list action prompt input default options))
    (%ide-state-with-message state 1005)))

(defun %ide-mini-start (state action prompt input default options)
  (%ide-mini-set state action prompt (if input input "") (if default default "") options))

(defun %ide-mini-tab-value (input default options first seen)
  (if options
      ((lambda (opt current)
         (if (if seen
                 't
                 (if (> (string-length input) 0)
                 (if (> (string-length input) (string-length opt))
                     nil
                     (string-equal input (substring opt 0 (string-length input))))
                     't))
             (if seen
                 opt
                 (%ide-mini-tab-value input default (cdr options)
                                      (if first first opt)
                                      (string-equal current opt)))
             (%ide-mini-tab-value input default (cdr options) first seen)))
       (car options)
       (if (> (string-length input) 0) input default))
      (if first first input)))

(defun %ide-mini-history-input (action fallback)
  ((lambda (hist)
     (if (if hist (eq action (car hist)) nil)
         (car (cdr hist))
         fallback))
   (symbol-value (quote %ide-mini-history))))

(defun %ide-mini-input-value (code action input default options)
  (cond ((= code 9)
         (%ide-mini-tab-value input default options nil nil))
        ((or (= code 20) (= code 127))
         (if (> (string-length input) 0)
             (ide-string-prefix input (- (string-length input) 1))
             input))
        ((= code 21) "")
        ((or (= code 16) (= code 145))
         (%ide-mini-history-input action input))
        ((or (= code 14) (= code 17)) "")
        ((ide-printable-code-p code)
         (list->string (append (string->list input) (list code))))
        (t nil)))

(defun %ide-mini-step (state event)
  ((lambda (code mini)
     ((lambda (action prompt input default options)
        (if (or (= code 13) (or (= code 10) (and (eq action 'search) (= code 19))))
            (progn
              ((lambda (chosen)
                 (if (> (string-length chosen) 0)
                     (set-symbol-value (quote %ide-mini-history)
                                       (list action chosen))
                     nil))
               (if (> (string-length input) 0) input default))
              (set-symbol-value (quote ide-step) nil)
              (%ide-mini-submit (%ide-state-with-message state nil) action input default))
            (if (if (= code 7) 't (= code 27))
                (progn
                  (set-symbol-value (quote ide-step) nil)
                  (%ide-state-with-message state "cancelled"))
                ((lambda (next)
                   (if next
                       (%ide-mini-set state action prompt next default options)
                       state))
                 (%ide-mini-input-value code action input default options)))))
      (car mini)
      (car (cdr mini))
      (car (cdr (cdr mini)))
      (car (cdr (cdr (cdr mini))))
      (car (cdr (cdr (cdr (cdr mini)))))))
   (ide-event-code event)
   ;; This path is reached only after %ide-mini-start initialized the carrier;
   ;; the invariant also keeps the compiled object below its 255-byte cap.
   (symbol-value (quote ide-step))))

;; SCROLLING (2026-07-07, user request): clamp row-offset so the cursor remains
;; visible in the body (rows-1 lines). Runs BEFORE every render; an offset
;; change affects all visible lines, so the dirty comparison forces a full
;; redraw while the fast path remains unchanged for non-scroll keys.
(defun %ide-state-with-row-offset (state off)
  ;; CAUTION: changing the offset MUST invalidate the render cache
  ;; (render-lines nil). When the cursor stays on the same screen row while
  ;; scrolling at the top or bottom edge, the fast path would otherwise take
  ;; its shortcut and leave every other line showing OLD shifted content
  ;; (user report: corrupted screen).
  (cons (car state)
        (cons (car (cdr state))
              (cons off
                    (cons nil
                          (cdr (cdr (cdr (cdr state)))))))))

(defun %ide-scrolled (state rows)
  ;; SCROLLING RE-ENABLED (2026-07-08): the previously suspected "garbage at
  ;; row-offset>0" was NOT the full-redraw/stack gap. It was a 1 KiB Color-RAM
  ;; window escape in the C driver: color stores for rows >=13 hit CIA2 $DD00,
  ;; the VIC bank register. Fixed in src/screen.c (CRAM_WINDOW). Clamp row-offset
  ;; so the cursor remains in the body (rows-1).
  (let* ((line (car (ide-buffer-point (ide-state-buffer state))))
         (off (ide-state-row-offset state))
         (body (- rows 1)))
    (if (< line off)
        (%ide-state-with-row-offset state line)
        (if (< line (+ off body))
            state
            (%ide-state-with-row-offset state (+ (- line body) 1))))))

(defun ide-state-render-lines (state)
  (car (cdr (cdr (cdr state)))))

(defun ide-state-render-cursor-row (state)
  (car (cdr (cdr (cdr (cdr state))))))

(defun ide-state-render-columns (state)
  (car (cdr (cdr (cdr (cdr (cdr state)))))))

(defun ide-state-render-rows (state)
  (car (cdr (cdr (cdr (cdr (cdr (cdr state))))))))

(defun %ide-state-with-buffer (state buffer)
  (let* ((s1 (cdr state))
         (s2 (cdr s1))
         (s3 (cdr s2))
         (s4 (cdr s3))
         (s5 (cdr s4))
         (s6 (cdr s5))
         (s7 (cdr s6)))
    (list buffer
          (car s1)
          (car s2)
          (car s3)
          (car s4)
          (car s5)
          (car s6)
          (car s7))))

(defun %ide-state-with-render-cache (state lines cursor-row columns rows)
  (let* ((s1 (cdr state))
         (s2 (cdr s1))
         (s3 (cdr s2))
         (s4 (cdr s3))
         (s5 (cdr s4))
         (s6 (cdr s5))
         (s7 (cdr s6)))
    (list (car state)
          (car s1)
          (car s2)
          lines
          cursor-row
          columns
          rows
          (car s7))))

(defun ide-state-render-lines-for-size (state columns rows)
  (let* ((render-columns (ide-state-render-columns state))
         (render-rows (ide-state-render-rows state)))
    (if (and render-columns
             (= render-columns columns)
             (= render-rows rows))
        (ide-state-render-lines state)
        nil)))

(defun ide-event-code (event)
  (car (cdr event)))

;; Event-to-command mapping is generated from config/v11-l-lite-keymap.json in
;; lib/ide-keymap-generated.lisp. The same source also generates the tests and
;; user-facing table, so a documented binding cannot drift from this dispatcher.

;; Automatic wrapping while typing (2026-07-03): strings are character lists,
;; so each self-insert rebuilds the line (O(column)). At line end this grew
;; without bound; after about 40-50 characters one key took about one second
;; (user report: "the more I type, the slower it gets"). Fill column 79 places
;; a hard bound on n: when the cursor reaches the penultimate column, the next
;; self-insert first splits the line (classic margin wrapping) and continues
;; on the new line, giving an O(1) ceiling. The middle of an already-full line
;; is the rare exception.
(defun %ide-fill-column () 79)

;; Dirty hint for delta rendering (global %ide-hint): (column . pad), or nil
;; means the next render paints the FULL line. Rendering CONSUMES the hint.
;; With render coalescing (%ide-drain-pending: multiple steps per render), the
;; steps merge their hints: minimum column and summed erase padding. Otherwise
;; the one render paints only the suffix of the LAST character and cells from
;; earlier burst characters retain old screen content (user report: ghost
;; spaces and cursor imprints during fast typing).
(defun %ide-hint-merge (col pad)
  (set-symbol-value
   (quote ide-render)
   ((lambda (h)
      (cons (if (if h (< (car h) col) nil) (car h) col)
            (+ pad (if h (cdr h) 0))))
    (if (boundp (quote ide-render)) (symbol-value (quote ide-render)) nil))))

(defun %ide-self-insert (state event)
  ((lambda (buffer)
     ((lambda (col split)
        (progn
          (if split
              (set-symbol-value (quote ide-render) nil)
              (%ide-hint-merge col 0))
          (%ide-state-with-buffer
           state
           (ide-insert-char
            (if split (ide-split-line buffer) buffer)
            (ide-event-code event)))))
     (ide-point-column (ide-buffer-point buffer))
     (>= (ide-point-column (ide-buffer-point buffer)) (%ide-fill-column))))
   (ide-state-buffer state)))

(defun %ide-newline-command (state)
  (if (string= (ide-buffer-name (ide-state-buffer state)) "*directory*")
      (%ide-find-file-named state (ide-current-line (ide-state-buffer state)))
      ;; Automatic indentation (ide-syntax.lisp): split and indent the new line
      ;; to the parenthesis depth.
      (%ide-state-with-buffer state (ide-split-line-indented (ide-state-buffer state)))))

(defun %ide-delete-forward-command (state)
  (progn
    ((lambda (buffer)
       ((lambda (point line)
          (if (< (cdr point) (string-length line))
              (%ide-hint-merge (cdr point) 1)
              (set-symbol-value (quote ide-render) nil)))
        (ide-buffer-point buffer)
        (ide-current-line buffer)))
     (ide-state-buffer state))
    (%ide-state-with-buffer state
                            (ide-delete-forward-char (ide-state-buffer state)))))

(defun %ide-line-edge-command (state endp)
  (progn
    (set-symbol-value (quote ide-render) nil)
    ((lambda (buffer)
       ((lambda (point)
          (%ide-state-with-buffer
           state
           (ide-set-point buffer
                          (car point)
                          (if endp
                              (string-length (ide-current-line buffer))
                              0))))
        (ide-buffer-point buffer)))
     (ide-state-buffer state))))

(defun %ide-search-lines (needle lines index)
  (if lines
      ((lambda (col)
         (if col
             (cons index col)
             (%ide-search-lines needle (cdr lines) (+ index 1))))
       (search needle (car lines)))
      nil))

;; Exact M-x spelling and lookup are generated with the keymap. Prefix-only
;; matches are deliberately rejected.

(defun %ide-execute-command-key (state)
  (%ide-mini-start
   state
   'execute-command
   "M-x "
   ""
   (%ide-mini-history-input 'execute-command "find-file")
   (ide-command-names)))

(defun %ide-execute-command-submit (state name)
  ((lambda (command)
     (if command
         (%ide-dispatch-command state command nil)
         (%ide-state-with-message state "unknown command")))
   (%ide-command-named name)))

(defun %ide-page-rows (state)
  ((lambda (rows)
     (if rows
         (if (> rows 2) (- rows 2) 1)
         20))
   (ide-state-render-rows state)))

(defun %ide-word-edit-command-p (command)
  (and (>= command 1111)
       (or (<= command 1114) (and (>= command 1118) (<= command 1119)))))

(defun %ide-region-command-p (command)
  (or (eq command 1115) (and (>= command 1122) (<= command 1124))))

(defun %ide-page-command-p (command)
  (and (>= command 1116) (<= command 1121)))

(defun %ide-apply-word-edit-command (state command)
  (cond ((eq command 1111)
         (%ide-state-with-buffer state
                                 (ide-move-word-right (ide-state-buffer state))))
        ((eq command 1112)
         (%ide-state-with-buffer state
                                 (ide-move-word-left (ide-state-buffer state))))
        ((eq command 1113)
         (%ide-state-with-buffer state
                                 (ide-kill-word (ide-state-buffer state))))
        ((eq command 1114)
         (%ide-state-with-buffer state
                                 (ide-backward-kill-word (ide-state-buffer state))))
        ((eq command 1118)
         (%ide-state-with-buffer state
                                 (ide-kill-line (ide-state-buffer state))))
        ((eq command 1119)
         (%ide-state-with-buffer state
                                 (ide-yank (ide-state-buffer state))))
        (t state)))

(defun %ide-apply-region-command (state command)
  (cond
        ((eq command 1115)
         (%ide-state-with-message
          (%ide-state-with-buffer state
                                  (ide-set-mark (ide-state-buffer state)))
          "mark"))
        ((eq command 1123)
         (%ide-state-with-buffer state
                                 (ide-exchange-point-and-mark (ide-state-buffer state))))
        ((eq command 1122)
         (%ide-state-with-buffer state
                                 (ide-kill-region (ide-state-buffer state))))
        ((eq command 1124)
         (%ide-state-with-message
          (%ide-state-with-buffer state
                                  (ide-copy-region-as-kill (ide-state-buffer state)))
          "copied"))
        (t state)))

(defun %ide-apply-page-command (state command)
  (cond
        ((eq command 1116)
         (%ide-state-with-buffer
          state
          (ide-page-down (ide-state-buffer state) (%ide-page-rows state))))
        ((eq command 1117)
         (%ide-state-with-buffer
          state
          (ide-page-up (ide-state-buffer state) (%ide-page-rows state))))
        ((eq command 1120)
         (%ide-state-with-buffer state
                                 (ide-buffer-start (ide-state-buffer state))))
        ((eq command 1121)
         (%ide-state-with-buffer state
                                 (ide-buffer-end (ide-state-buffer state))))
        (t state)))

(defun %ide-apply-rare-edit-command (state command)
  (if (%ide-word-edit-command-p command)
      (%ide-apply-word-edit-command state command)
      (if (%ide-region-command-p command)
          (%ide-apply-region-command state command)
          (if (%ide-page-command-p command)
              (%ide-apply-page-command state command)
              state))))

(defun ide-apply-command (state command event)
  (progn
    (if (eq command 1110)
        nil
        (if (eq command 1101)
            nil
            (set-symbol-value (quote ide-render) nil)))
    (if (eq command 1110)
        (%ide-self-insert state event)
      (if (eq command 1109)
          (%ide-newline-command state)
          (if (eq command 1101)
              (progn
                ((lambda (c)
                   (if (> c 0)
                       (%ide-hint-merge (- c 1) 1)
                       (set-symbol-value (quote ide-render) nil)))
                 (cdr (ide-buffer-point (ide-state-buffer state))))
                (%ide-state-with-buffer state
                                        (ide-delete-backward-char (ide-state-buffer state))))
              (if (eq command 1102)
                  (%ide-delete-forward-command state)
                  (if (eq command 1106)
                      (%ide-state-with-buffer state (ide-move-left (ide-state-buffer state)))
                      (if (eq command 1107)
                          (%ide-state-with-buffer state (ide-move-right (ide-state-buffer state)))
                          (if (eq command 1108)
                              (%ide-state-with-buffer state (ide-move-up (ide-state-buffer state)))
                              (if (eq command 1003)
                                  (%ide-state-with-buffer state (ide-move-down (ide-state-buffer state)))
                                  (%ide-x 'apply state command event)))))))))))

(defun %ide-switch-key (state)
  (progn
    (%ide-store-buffer (ide-state-buffer state))
    ((lambda (alist)
       (%ide-mini-start
        state
        1006
        "Buffer: "
        ""
        (if (cdr alist)
            (car (car (cdr alist)))
            (if alist
                (car (car alist))
                (ide-buffer-name (ide-state-buffer state))))
        (%ide-buffers-names alist)))
     (%ide-buffers-alist))))

(defun %ide-last-buffer (alist last)
  (if alist
      (%ide-last-buffer (cdr alist) (cdr (car alist)))
      last))

(defun %ide-cycle-buffer-find (name clean alist previous wrap forward acc)
  (if alist
      (if (string= name (car (car alist)))
          (cons
           (if forward
               (if (cdr alist) (cdr (car (cdr alist))) wrap)
               (if previous previous wrap))
           (%ide-rev-onto
            acc
            (cons (cons name clean) (cdr alist))))
          (%ide-cycle-buffer-find
           name
           clean
           (cdr alist)
           (cdr (car alist))
           wrap
           forward
           (cons (car alist) acc)))
      nil))

(defun %ide-cycle-buffer (state forward)
  ((lambda (current)
     ((lambda (clean)
        ((lambda (alist)
           ((lambda (found)
              (if found
                  (progn
                    (set-symbol-value (quote ide-buffers) (cdr found))
                    (%ide-state-with-message
                     (%ide-state-with-buffer state (car found))
                     "switched"))
                  (progn
                    (set-symbol-value
                     (quote ide-buffers)
                     (cons (cons (ide-buffer-name clean) clean) alist))
                    state)))
            (if alist
                (%ide-cycle-buffer-find
                 (ide-buffer-name clean)
                 clean
                 alist
                 nil
                 (if forward (cdr (car alist)) (%ide-last-buffer alist nil))
                 forward
                 nil)
                nil)))
         (%ide-buffers-alist)))
      (%ide-buffer-flush-cache current)))
   (ide-state-buffer state)))

(defun %ide-compile-key (state)
  (%ide-mini-start
   state
   1008
   "Compile+load: "
   ""
   "fasl0"
   (remove-if-not (function %ide-fasl-slot-p) (dir))))

(defun %ide-motion-key (state command)
  (cond ((eq command 1012)
         (%ide-mini-start state 1012 "Goto line: " "" "" nil))
        ((eq command 1014)
         (progn
           (%ide-store-buffer (ide-state-buffer state))
           (if (eval-buffer (ide-buffer-name (ide-state-buffer state)))
               (%ide-state-with-message state "evaluated")
               (%ide-state-with-message state (ide-error)))))
        (t (%ide-x 'motion state command nil))))

(defun %ide-directory-key (state)
  (%ide-state-with-message
   (%ide-state-with-buffer
    state
    (ide-make-buffer
     "*directory*"
     (remove-if-not (function %ide-source-file-p) (cdr (dir)))))
   "sources"))

(defun %ide-dispatch-route-low (state command event route)
  (cond ((eq route 1) (ide-apply-command state command event))
        ((eq route 2) (%ide-line-edge-command state nil))
        ((eq route 3) (%ide-line-edge-command state 't))
        (t state)))

(defun %ide-dispatch-route-mid (state route)
  (cond ((eq route 4) (%ide-save-key state))
        ((eq route 5) (%ide-find-key state))
        ((eq route 6) (%ide-write-key state))
        ((eq route 7) (%ide-switch-key state))
        ((eq route 8) (%ide-directory-key state))
        (t state)))

(defun %ide-dispatch-route-high (state command route)
  (cond ((eq route 9) (%ide-compile-key state))
        ((eq route 10) (%ide-cycle-buffer state 't))
        ((eq route 11) (%ide-cycle-buffer state nil))
        ((eq route 12) (%ide-motion-key state command))
        ((eq route 13) (%ide-state-with-message state 1015))
        (t state)))

(defun %ide-dispatch-command (state command event)
  (if command
      ((lambda (route)
         (if (<= route 3)
             (%ide-dispatch-route-low state command event route)
             (if (<= route 8)
                 (%ide-dispatch-route-mid state route)
                 (%ide-dispatch-route-high state command route))))
       (%ide-command-route command))
      state))

(defun ide-step (state event)
  (if (eq (car (cdr state)) 1005)
      (%ide-mini-step state event)
      (%ide-dispatch-command state (ide-event-command event) event)))

(defun ide-buffer-display-name (buffer)
  (if (stringp (ide-buffer-name buffer))
      (ide-buffer-name buffer)
      "*buffer*"))

(defun ide-status-line (state width)
  (let* ((buffer (car state))
         (message (car (cdr state)))
         (budget (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))))
         (name (car buffer))
         (point (car (cdr (cdr (cdr buffer)))))
         (modified (car (cdr (cdr (cdr (cdr (cdr buffer)))))))
         (display-name (if (stringp name) name "*buffer*")))
    (if (eq message 1005)
        (%ide-mini-status-line)
        (if message
            (string-append "-- "
                           display-name
                           (if modified " *" "")
                           " "
                           message
                           " L"
                           (number->string (+ (car point) 1))
                           " -- "
                           budget)
            (string-append "-- "
                           display-name
                           (if modified " *" "")
                           " L"
                           (number->string (+ (car point) 1))
                           " -- "
                           budget)))))

(defun %ide-blank-lines-into (count acc)
  (if (> count 0)
      (%ide-blank-lines-into (- count 1) (cons (%ide-empty-str) acc))
      acc))

(defun ide-blank-lines (count)
  (%ide-blank-lines-into count nil))

(defun ide-visible-line (text columns)
  (if (> (string-length text) columns)
      (substring text 0 columns)
      text))

(defun %ide-visible-lines-into (lines columns acc)
  (if lines
      (%ide-visible-lines-into
       (cdr lines)
       columns
       (cons (ide-visible-line (car lines) columns) acc))
      (reverse acc)))

;; COMPUTE-LINES-ONCE (2026-07-07): like ide-visible-frame-lines, but accepts
;; the already materialized line list (ide-render computes it once at its flat
;; top). Avoids the second ide-buffer-lines reconstruction during rendering.
(defun ide-visible-frame-lines-from (state lines columns rows)
  (if (> rows 0)
      (let* ((body-rows (- rows 1))
             (row-offset (ide-state-row-offset state))
             (body (ide-region-lines-from lines
                                          row-offset
                                          (+ row-offset body-rows))))
        (append (%ide-visible-lines-into body
                                         columns
                                         nil)
                (ide-blank-lines (- body-rows (length body)))
                (list (ide-visible-line (ide-status-line state columns)
                                        columns))))
      nil))

(defun %ide-render-visible-body-into (lines count columns acc)
  (if (and lines (> count 0))
      (%ide-render-visible-body-into
       (cdr lines)
       (- count 1)
       columns
       (cons (ide-visible-line (car lines) columns) acc))
      acc))

(defun %ide-render-blank-body-into (count acc)
  (if (> count 0)
      (%ide-render-blank-body-into
       (- count 1) (cons (%ide-empty-str) acc))
      acc))

(defun %ide-last-cell (lines)
  (if (cdr lines) (%ide-last-cell (cdr lines)) lines))

(defun %ide-render-frame-lines-from (state lines columns rows)
  (if (> rows 0)
      (let* ((body-rows (- rows 1))
             (row-offset (ide-state-row-offset state))
             (body-reversed (%ide-render-visible-body-into
                             (%ide-drop-lines lines row-offset)
                             body-rows
                             columns
                             nil))
             (padded-reversed (%ide-render-blank-body-into
                               (- body-rows (length body-reversed))
                               body-reversed))
             (body (nreverse padded-reversed))
             (status (list (%ide-empty-str))))
        (if body
            (progn
              ;; Both lists were allocated by this call and are therefore
              ;; exclusively owned by the render cache.
              (rplacd (%ide-last-cell body) status)
              body)
            status))
      nil))

(defun ide-cursor-row (state rows)
  (if (eq (car (cdr state)) 1005)
      nil
      (let* ((buffer (ide-state-buffer state))
             (point (ide-buffer-point buffer))
             (y (- (car point) (ide-state-row-offset state))))
        (if (and (>= y 0) (< y (- rows 1))) y nil))))

(defun %ide-dirty-line-indices-from (old-lines new-lines i cursor-row previous-cursor-row acc)
  (if new-lines
      (%ide-dirty-line-indices-from
       (if old-lines (cdr old-lines) nil)
       (cdr new-lines)
       (+ i 1)
       cursor-row
       previous-cursor-row
       (if (or (and cursor-row (= i cursor-row))
               (and previous-cursor-row (= i previous-cursor-row))
               (if old-lines (not (eq (car old-lines) (car new-lines))) 't))
           (cons i acc)
           acc))
      (reverse acc)))

(defun ide-dirty-line-indices (old-lines new-lines cursor-row previous-cursor-row)
  (%ide-dirty-line-indices-from old-lines new-lines 0 cursor-row previous-cursor-row nil))

(defun %ide-render-codes-at (codes x y attr)
  (if codes
      (progn
        (screen-put-char x y (car codes) attr)
        (%ide-render-codes-at (cdr codes) (+ x 1) y attr))
      nil))

(defun %ide-render-string-codes-at (text x y attr len)
  (if (< x len)
      (progn
        (screen-put-char x y (string-ref text x) attr)
        (%ide-render-string-codes-at text (+ x 1) y attr len))
      nil))

(defun %ide-render-string-part-at (text source x y attr len)
  (if (< source len)
      (progn
        (screen-put-char x y (string-ref text source) attr)
        (%ide-render-string-part-at
         text (+ source 1) (+ x 1) y attr len))
      nil))

(defun %ide-pad-eol (col columns y attr)
  (if (< col columns)
      (progn
        (screen-put-char col y 32 attr)
        (%ide-pad-eol (+ col 1) columns y attr))
      nil))

;; Plain renderer for the status line and similar content, deliberately
;; WITHOUT syntax scanning to preserve the dynamic budget. CODE lines go
;; through %ide-render-code-line-at (ide-syntax.lisp): bulk plus overpaint.
(defun ide-render-line-at (text y columns attr)
  (if (screen-bulk-p)
      (screen-write-string 0 y text (+ attr 64))
      (progn
        (%ide-render-string-codes-at text 0 y attr (string-length text))
        (%ide-pad-eol (string-length text) columns y attr))))

;; hlmax is the first non-code line (the status line): syntax overpaint below
;; it, plain rendering from there onward.
(defun %ide-render-dirty-lines-at (lines dirty y columns attr hlmax)
  (if lines
      (let* ((dirty-here (and dirty (= y (car dirty)))))
        (progn
          (if dirty-here
              (if (< y hlmax)
                  (%ide-render-code-line-at (car lines) y columns attr)
                  (ide-render-line-at (car lines) y columns attr))
              nil)
          (%ide-render-dirty-lines-at
           (cdr lines)
           (if dirty-here (cdr dirty) dirty)
           (+ y 1)
           columns
           attr
           hlmax)))
      nil))

;; Cell i of the line list, used for destructive rplaca in the render cache.
(defun %ide-nth-cell (lines i)
  (if (> i 0) (%ide-nth-cell (cdr lines) (- i 1)) lines))

;; Status-line cache (delta rendering): cache only the four-value identity,
;; then paint stable string components directly.  The old implementation
;; repeatedly concatenated those components into a temporary string (about
;; 140 heap cells on every vertical move).
(defun %ide-status-current-p (state)
  (let* ((buffer (car state))
         (cache (if (boundp (quote ide-status-line)) (symbol-value (quote ide-status-line)) nil))
         (name (car buffer))
         (line (car (car (cdr (cdr (cdr buffer))))))
         (mod (car (cdr (cdr (cdr (cdr (cdr buffer)))))))
         (msg (car (cdr state))))
    (if cache
        (if (eq name (car cache))
            (if (eq mod (car (cdr cache)))
                (if (eq msg (car (cdr (cdr cache))))
                    (= line (car (cdr (cdr (cdr cache)))))
                    nil)
                nil)
            nil)
        nil)))

;; Compatibility query for the existing IDE surface.  The renderer no longer
;; consumes a materialized status string per key, but callers of this private
;; diagnostic helper still receive the same text.
(defun %ide-status-cached (state width)
  (ide-status-line state width))

(defun %ide-render-status-part (text x y)
  (progn
    (%ide-render-string-part-at text 0 x y 7 (string-length text))
    (+ x (string-length text))))

(defun %ide-render-status-prefix (name modified y)
  (let* ((display-name (if (stringp name) name "*buffer*"))
         (x1 (%ide-render-status-part "-- " 0 y))
         (x2 (%ide-render-status-part display-name x1 y)))
    (if modified (%ide-render-status-part " *" x2 y) x2)))

(defun %ide-render-status-finish (budget x width y)
  (let* ((x1 (%ide-render-status-part " -- " x y))
         (x2 (%ide-render-status-part budget x1 y)))
    (%ide-pad-eol x2 width y 7)))

(defun %ide-render-status-line-direct
    (name modified point budget width y)
  (let* ((x1 (%ide-render-status-prefix name modified y))
         (x2 (%ide-render-status-part " L" x1 y))
         (x3 (%ide-render-status-part
              (number->string (+ (car point) 1)) x2 y)))
    (%ide-render-status-finish budget x3 width y)))

(defun %ide-render-status-msg-direct
    (name modified message point budget width y)
  (let* ((x1 (%ide-render-status-prefix name modified y))
         (x2 (%ide-render-status-part " " x1 y))
         (x3 (%ide-render-status-part message x2 y))
         (x4 (%ide-render-status-part " L" x3 y))
         (x5 (%ide-render-status-part
              (number->string (+ (car point) 1)) x4 y)))
    (%ide-render-status-finish budget x5 width y)))

(defun %ide-render-status-mini-direct
    (name modified budget width y)
  (let* ((x1 (%ide-render-status-prefix name modified y))
         (x2 (%ide-render-status-part " M-x " x1 y))
         (x3 (%ide-render-status-part (%ide-mini-status-line) x2 y)))
    (%ide-render-status-finish budget x3 width y)))

(defun %ide-render-status-direct (state width y)
  (let* ((buffer (car state))
         (message (car (cdr state)))
         (budget (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr state)))))))))
         (name (car buffer))
         (point (car (cdr (cdr (cdr buffer)))))
         (modified (car (cdr (cdr (cdr (cdr (cdr buffer))))))))
    (if (eq message 1005)
        (%ide-render-status-mini-direct
         name modified budget width y)
        (if message
            (%ide-render-status-msg-direct
             name modified message point budget width y)
            (%ide-render-status-line-direct
             name modified point budget width y)))))

(defun %ide-render-status-cached (state width y)
  (if (%ide-status-current-p state)
      nil
      (let* ((buffer (car state))
             (name (car buffer))
             (line (car (car (cdr (cdr (cdr buffer))))))
             (mod (car (cdr (cdr (cdr (cdr (cdr buffer)))))))
             (msg (car (cdr state))))
        (progn
          (set-symbol-value (quote ide-status-line)
                            (list name mod msg line))
          (%ide-render-status-direct state width y)))))

;; FAST PATH per key (DESTRUCTIVE in the render cache, only two rplaca calls):
;;  - Status line: paint only when its text changes (cache EQ test).
;;  - Cursor line: with a dirty hint, paint only the suffix from the edit
;;    column (delta rendering in ide-syntax.lisp); without a hint (movement,
;;    etc.), paint the whole line as before.
;; COMPUTE-LINES-ONCE (2026-07-07): `lines` is the line list materialized ONCE
;; during rendering, instead of two ide-buffer-lines reconstructions in the
;; fast path: here and in ide-render-cursor-from.
(defun %ide-render-fast-same-row (state lines old-lines cursor-row columns rows)
  (let* ((row-offset (ide-state-row-offset state))
         (line-index (+ row-offset cursor-row))
         (visible (ide-visible-line
                   (%ide-line-at lines line-index)
                   columns))
         (status-row (- rows 1))
         (hint (if (boundp (quote ide-render)) (symbol-value (quote ide-render)) nil)))
    (progn
      (rplaca (%ide-nth-cell old-lines cursor-row) visible)
      (%ide-render-status-cached state columns status-row)
      (if hint
          (%ide-render-code-suffix-at visible cursor-row (car hint) (cdr hint))
          (%ide-render-code-line-at visible cursor-row columns 7))
      (set-symbol-value (quote ide-render) nil)
      (ide-render-cursor-from state lines columns rows 129)
      (%ide-state-with-render-cache state old-lines cursor-row columns rows))))

;; The ordinary append-at-EOL cache stores the typed line in reverse order.
;; Draw it right-to-left directly: screen cells are random-access, so neither a
;; forward list nor a temporary string is needed.  This is the v1.2.6 hot-path
;; boundary—typing may update the cache, but redisplay must not materialize it.
(defun %ide-render-reverse-codes-at (codes x y from attr)
  (if (and codes (>= x from))
      (progn
        (screen-put-char x y (car codes) attr)
        (%ide-render-reverse-codes-at (cdr codes) (- x 1) y from attr))
      nil))

(defun %ide-render-cached-line-at (cache y columns)
  (let* ((len (car (cdr (cdr cache))))
         (last (- (%ide-min len columns) 1)))
    (progn
      (%ide-render-reverse-codes-at (car (cdr cache)) last y 0 1)
      (%ide-pad-eol len columns y 1))))

(defun %ide-render-cached-suffix-at (cache y from pad columns)
  (let* ((len (car (cdr (cdr cache))))
         (last (- (%ide-min len columns) 1)))
    (progn
      (%ide-render-reverse-codes-at (car (cdr cache)) last y from 1)
      (%ide-pad-eol len (%ide-min columns (+ len (+ pad 1))) y 1))))

(defun %ide-cached-code-at (cache column)
  (let* ((len (car (cdr (cdr cache)))))
    (if (< column len)
        (car (%ide-nth-cell (car (cdr cache))
                            (- len (+ column 1))))
        95)))

(defun %ide-render-fast-cached-row
    (state cache old-lines cursor-row columns rows)
  (let* ((status-row (- rows 1))
         (hint (if (boundp (quote ide-render))
                   (symbol-value (quote ide-render))
                   nil))
         (column (cdr (ide-buffer-point (ide-state-buffer state)))))
    (progn
      (%ide-render-status-cached state columns status-row)
      (if hint
          (%ide-render-cached-suffix-at
           cache cursor-row (car hint) (cdr hint) columns)
          (%ide-render-cached-line-at cache cursor-row columns))
      (set-symbol-value (quote ide-render) nil)
      (if (< column columns)
          (screen-put-char column
                           cursor-row
                           (%ide-cached-code-at cache column)
                           129)
          nil)
      ;; The old line string deliberately remains stale.  Repeated same-row
      ;; cached renders do not read it; the next full redraw compares it
      ;; against a freshly materialized line and therefore repaints it.
      (%ide-state-with-render-cache state old-lines cursor-row columns rows))))

(defun %ide-render-cached-next-row
    (state buffer cache old-lines cursor-row previous-cursor-row columns rows)
  (let* ((line-index (car (ide-buffer-point buffer)))
         (previous (ide-visible-line
                    (%ide-line-at (car (cdr (cdr buffer)))
                                  (- line-index 1))
                    columns))
         (column (cdr (ide-buffer-point buffer))))
    (progn
      (rplaca (%ide-nth-cell old-lines previous-cursor-row) previous)
      (%ide-render-code-line-at
       previous previous-cursor-row columns 7)
      (%ide-render-cached-line-at cache cursor-row columns)
      (%ide-render-status-cached state columns (- rows 1))
      (set-symbol-value (quote ide-render) nil)
      (if (< column columns)
          (screen-put-char column
                           cursor-row
                           (%ide-cached-code-at cache column)
                           129)
          nil)
      (%ide-state-with-render-cache state old-lines cursor-row columns rows))))

;; COMPUTE-LINES-ONCE (2026-07-07): accepts the already materialized line list
;; instead of reconstructing (ide-buffer-lines buffer) again.
(defun ide-render-cursor-from (state lines columns rows attr)
  (if (eq (car (cdr state)) 1005)
      ((lambda (x)
         (screen-put-char (if (< x columns) x (- columns 1)) (- rows 1) 95 attr))
       (string-length (ide-status-line state columns)))
      (let* ((buffer (ide-state-buffer state))
             (point (ide-buffer-point buffer))
             (line-index (car point))
             (column (cdr point))
             (x column)
             (y (- line-index (ide-state-row-offset state)))
             (body-rows (- rows 1)))
        (if (and (>= x 0)
                 (< x columns)
                 (>= y 0)
                 (< y body-rows))
            (let* ((line (%ide-line-at lines line-index))
                   (code (if (< column (string-length line))
                             (string-ref line column)
                             95)))
              (screen-put-char x y code attr))
            nil))))

(defun %ide-render-materialized-fast
    (state buffer old-lines cursor-row columns rows)
  (%ide-render-fast-same-row
   state
   (ide-buffer-lines buffer)
   old-lines
   cursor-row
   columns
   rows))

(defun %ide-render-fast-dispatch
    (state buffer cache old-lines cursor-row columns rows)
  (if (and cache
           (= (car cache)
              (+ (ide-state-row-offset state) cursor-row)))
      (%ide-render-fast-cached-row
       state cache old-lines cursor-row columns rows)
      (%ide-render-materialized-fast
       state buffer old-lines cursor-row columns rows)))

(defun %ide-render-changed-lines-at
    (old-lines lines y cursor-row previous-cursor-row columns hlmax)
  (if (and lines (< y hlmax))
      (let* ((dirty (or (and cursor-row (= y cursor-row))
                        (and previous-cursor-row
                             (= y previous-cursor-row))
                        (if old-lines
                            (not (eq (car old-lines) (car lines)))
                            't))))
        (progn
          (if dirty
              (%ide-render-code-line-at (car lines) y columns 7)
              nil)
          (%ide-render-changed-lines-at
           (if old-lines (cdr old-lines) nil)
           (cdr lines)
           (+ y 1)
           cursor-row
           previous-cursor-row
           columns
           hlmax)))
      nil))

(defun %ide-render-materialized-full
    (state buffer old-lines cursor-row previous-cursor-row columns rows)
  (let* ((buffer-lines (ide-buffer-lines buffer))
         (lines (%ide-render-frame-lines-from
                 state buffer-lines columns rows)))
    (progn
      (set-symbol-value (quote ide-render) nil)
      (%ide-render-changed-lines-at
       old-lines lines 0 cursor-row previous-cursor-row columns (- rows 1))
      (%ide-render-status-cached state columns (- rows 1))
      (ide-render-cursor-from state buffer-lines columns rows 129)
      (%ide-state-with-render-cache
       state lines cursor-row columns rows))))

;; STACK HYGIENE (2026-07-07): full redraw sits deep in the IDE call chain.
;; Although the earlier scrolling root cause was Color RAM rather than the
;; stack, flat let* slots remain mandatory here because extra immediate-lambda
;; frames create real stack and GC pressure.
(defun ide-render (state)
  (let* ((size (screen-size))
         (columns (car size))
         (rows (car (cdr size)))
         (state (%ide-scrolled state rows))
         (buffer (ide-state-buffer state))
         (cache (ide-buffer-locals buffer))
         (old-lines (ide-state-render-lines-for-size state columns rows))
         (cursor-row (ide-cursor-row state rows))
         (previous-cursor-row (ide-state-render-cursor-row state)))
    (if (and old-lines
             cursor-row
             previous-cursor-row
             (= cursor-row previous-cursor-row))
        (%ide-render-fast-dispatch
         state buffer cache old-lines cursor-row columns rows)
        (if (and old-lines
                 cache
                 cursor-row
                 previous-cursor-row
                 (= cursor-row (+ previous-cursor-row 1))
                 (= (car cache)
                    (+ (ide-state-row-offset state) cursor-row)))
            (%ide-render-cached-next-row
             state
             buffer
             cache
             old-lines
             cursor-row
             previous-cursor-row
             columns
             rows)
            (%ide-render-materialized-full
             state
             buffer
             old-lines
             cursor-row
             previous-cursor-row
             columns
             rows)))))

;; Render coalescing prevents lagging behind during fast typing: while more
;; keys wait in the queue (poll-key), run only ide-step (about 600 steps)
;; instead of step+render (about 2,400 steps). Render ONCE when the queue is
;; empty.
(defun %ide-drain-pending (state)
  (if (eq (ide-state-message state) 1015)
      state
      ((lambda (k)
         (if k
             (%ide-drain-pending (ide-step state k))
             state))
       (poll-key))))

;; C-x C-c is the only editor exit. RUN/STOP remains exclusively the global
;; evaluation abort, and ESC remains a minibuffer cancel key. The exit marker
;; stops queue draining before a later key can consume it; persistence happens
;; before returning to the REPL.
(defun ide-run (state)
  ((lambda (saved-state)
     ((lambda (key)
        ((lambda (next)
           (if (eq (ide-state-message next) 1015)
               (%ide-persist-state (%ide-state-with-message next nil))
               (ide-run (ide-render next))))
         (%ide-drain-pending (ide-step saved-state key))))
      (read-key)))
   (%ide-persist-state state)))

;; ---- Buffer persistence plus MULTIPLE named buffers (hardware user finding/request,
;; 2026-07-05) ----
;; All open buffers live between (ide) calls in the value cell of the existing
;; function symbol ide-buffers: an alist ((name . buffer) ...), most recently
;; active first. symval cells are GC roots, so buffers survive REPL work and
;; GC; lines, name, and cursor position remain intact for each buffer.
;; API: (ide) selects the most recently active buffer (or a fresh "scratch");
;; (ide "name") switches to buffer "name", creating it if needed; (ide-buffers)
;; returns names, most recent first.
;; Global access is NATIVE through CALLPRIM 19/20
;; (symbol-value/set-symbol-value). The old eval detour from the v2a era broke
;; in the development core because there was no eval primitive and no budget.
;; C-x C-c
;; persists through this same path, preserving the historical B4 guarantee.
(defun %ide-buffers-alist ()
  (symbol-value (quote ide-buffers)))

(defun %ide-buffers-find (name alist)
  (if alist
      (if (string= name (car (car alist)))
          (cdr (car alist))
          (%ide-buffers-find name (cdr alist)))
      nil))

;; Alist without the `name` entry (not tail-recursive; the buffer count is small).
;; TAIL (2026-07-06): accumulator pattern instead of cons after recursion, to
;; preserve the GC_ROOTS budget.
(defun %ide-buffers-remove-into (name alist acc)
  (if alist
      (%ide-buffers-remove-into
       name
       (cdr alist)
       (if (string= name (car (car alist))) acc (cons (car alist) acc)))
      acc))

(defun %ide-buffers-remove (name alist)
  (%ide-rev-onto (%ide-buffers-remove-into name alist nil) nil))

;; Insert a buffer under its name (front = most recently active) and save it globally.
(defun %ide-store-buffer (buf)
  ((lambda (buf)
     ((lambda (name alist)
        (if (and alist (string= name (car (car alist))))
            (progn (rplacd (car alist) buf) 't)
            (progn
              (set-symbol-value (quote ide-buffers)
                                (cons (cons name buf)
                                      (%ide-buffers-remove name alist)))
              't)))
      (ide-buffer-name buf)
      (%ide-buffers-alist)))
   (%ide-buffer-flush-cache buf)))

(defun %ide-persist-state (state)
  (progn
    (%ide-store-buffer (ide-state-buffer state))
    state))

;; name=nil selects the most recently active buffer (alist head), or a fresh
;; "scratch"; a string name selects the existing buffer or creates a new empty
;; buffer with that name.
(defun %ide-resume-buffer (name)
  (if name
      ((lambda (found) (if found found (ide-make-buffer name (list ""))))
       (%ide-buffers-find name (%ide-buffers-alist)))
      ((lambda (alist)
         (if alist (cdr (car alist)) (ide-make-buffer "scratch" (list ""))))
       (%ide-buffers-alist))))

;; Dedicated walker instead of (mapcar (function car) ...): car is an OPCODE,
;; not CALLPRIM. Opcode function designators deliberately cannot be applied,
;; so mapcar would produce TYPEERROR.
(defun %ide-buffers-names (alist)
  (%ide-buffers-names-into alist nil))

(defun %ide-buffers-names-into (alist acc)
  (if alist
      (%ide-buffers-names-into (cdr alist) (cons (car (car alist)) acc))
      (%ide-rev-onto acc nil)))

(defun ide-buffers ()
  (%ide-buffers-names (%ide-buffers-alist)))

(defun ide (&rest name)
  (%ide-store-buffer
   (ide-state-buffer
    (ide-run (ide-render (ide-make-state
                          (%ide-resume-buffer (if name (car name) nil))))))))
