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

;; Optionale Komfort-Lib-Naht. IDEX definiert genau diesen Hook spaeter neu;
;; symbolische CALL-Aufloesung sieht dann ohne Runtime-/ABI-Sonderfall die
;; aktuelle Funktionszelle. Der Core bleibt bei fehlendem IDEX benutzbar.
(defun %ide-x (kind state a b)
  (cond ((and (eq kind 'apply) (eq a 'kill-line))
         (%ide-state-with-buffer state (ide-kill-line (ide-state-buffer state))))
        ((and (eq kind 'apply) (eq a 'yank))
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

;; SCROLLING (2026-07-07, Nutzerauftrag): row-offset so clampen, dass der Cursor
;; im Body (rows-1 Zeilen) sichtbar ist. Laeuft VOR jedem Render; ein Versatz
;; aendert alle sichtbaren Zeilen -> der Dirty-Vergleich erzwingt den Voll-Redraw,
;; der Fast-Path bleibt fuer Nicht-Scroll-Tasten unberuehrt.
(defun %ide-state-with-row-offset (state off)
  ;; ACHTUNG: Offset-Wechsel MUSS den Render-Cache invalidieren (render-lines nil):
  ;; bleibt der Cursor beim Scrollen in derselben Schirmzeile (oberster/unterster
  ;; Rand), naehme der Fast-Path sonst seinen Kurzweg und liesse alle uebrigen
  ;; Zeilen mit dem ALTEN, verschobenen Inhalt stehen (Nutzerbefund "Muell-Schirm").
  (cons (car state)
        (cons (car (cdr state))
              (cons off
                    (cons nil
                          (cdr (cdr (cdr (cdr state)))))))))

(defun %ide-scrolled (state rows)
  ;; SCROLLING WIEDER AKTIV (2026-07-08): Der frueher hier vermutete "Zeichenmuell bei
  ;; row-offset>0" war NICHT der Full-Redraw/Stack-Gap, sondern der Farb-RAM-1KB-Fenster-
  ;; Escape im C-Treiber (Farb-Store fuer Zeilen >=13 traf CIA2 $DD00 = VIC-Bank). Gefixt in
  ;; src/screen.c (CRAM_WINDOW). row-offset so clampen, dass der Cursor im Body (rows-1) bleibt.
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

(defun ide-printable-code-p (code)
  (and (>= code 32) (<= code 126)))

(defun %ide-prefix-command (code)
  (cond ((= code 19) (progn (set-symbol-value (quote ide-event-command) nil) 1001))
        ((= code 6) (progn (set-symbol-value (quote ide-event-command) nil) 1002))
        ((= code 23) (progn (set-symbol-value (quote ide-event-command) nil) 1004))
        ((= code 2) (progn (set-symbol-value (quote ide-event-command) nil) 1006))
        ((= code 4) (progn (set-symbol-value (quote ide-event-command) nil) 1007))
        ((= code 11) (progn (set-symbol-value (quote ide-event-command) nil) 1008))
        ((= code 14) (progn (set-symbol-value (quote ide-event-command) nil) 1009))
        ((= code 16) (progn (set-symbol-value (quote ide-event-command) nil) 1010))
        ((= code 1) (progn (set-symbol-value (quote ide-event-command) nil) 'buffer-start))
        ((= code 5) (progn (set-symbol-value (quote ide-event-command) nil) 'buffer-end))
        ((= code 18) (progn (set-symbol-value (quote ide-event-command) nil) 'kill-region))
        ((= code 24) (progn (set-symbol-value (quote ide-event-command) nil) 'exchange-point-and-mark))
        ((= code 25) (progn (set-symbol-value (quote ide-event-command) nil) 'copy-region-as-kill))
        (t nil)))

(defun %ide-control-command (code)
  (cond ((= code 4) 1102)
        ((= code 6) 1107)
        ((= code 2) 1106)
        ((= code 19) 1011)
        ((= code 12) 1012)
        ((= code 14) 1003)
        ((= code 16) 1108)
        ((= code 10) 1109)
        ((= code 1) 1104)
        ((= code 5) 1103)
        ((= code 15) 'move-word-right)
        ((= code 21) 'move-word-left)
        ((= code 23) 'kill-word)
        ((= code 18) 'backward-kill-word)
        ((= code 0) 'set-mark)
        ((= code 22) 'page-down)
        ((= code 26) 'page-up)
        ((= code 11) 'kill-line)
        ((= code 25) 'yank)
        (t nil)))

(defun ide-event-command (event)
  ((lambda (code)
     (cond ((eq (symbol-value (quote ide-event-command)) 24)
            (if (or (= code 120) (= code 13))
                (progn (set-symbol-value (quote ide-event-command) nil) 1013)
                (%ide-prefix-command code)))
           ((= code 13) 1109)
           ((= code 20) 1101)
           ((= code 157) 1106)
           ((= code 29) 1107)
           ((= code 145) 1108)
           ((= code 17) 1003)
           ((ide-printable-code-p code) 1110)
           ((= code 24) (progn (set-symbol-value (quote ide-event-command) 24) nil))
           (t (%ide-control-command code))))
   (ide-event-code event)))

;; Auto-Umbruch beim Tippen (2026-07-03): Strings sind Zeichenlisten -> jeder
;; self-insert baut die Zeile neu (O(Spalte)). Am Zeilenende waechst das ohne
;; Grenze -> nach ~40-50 Zeichen ist eine Taste ~1 s (Nutzerbefund: "je mehr
;; getippt, desto langsamer"). Fill-Column 79 deckelt n hart: erreicht der Cursor
;; die vorletzte Spalte, splittet der naechste self-insert die Zeile zuerst
;; (klassischer Rand-Umbruch) und tippt auf der neuen Zeile weiter -> O(1)-Deckel.
;; (Zeilenmitte einer bereits vollen Zeile ist der seltene Ausnahmefall.)
(defun %ide-fill-column () 79)

;; Dirty-Hint fuers Delta-Render (global %ide-hint): (spalte . pad) oder nil =
;; naechster Render malt die VOLLE Zeile. Der Render KONSUMIERT den Hint; bei
;; Render-Koaleszenz (%ide-drain-pending: mehrere Steps je Render!) verschmelzen
;; die Steps ihre Hints: minimale Spalte, Loesch-Pads summieren -- sonst malt der
;; eine Render nur das Suffix des LETZTEN Zeichens und die Zellen der frueheren
;; Burst-Zeichen behalten alten Schirm-Inhalt (Nutzerbefund: Geister-Leerzeichen +
;; Cursor-Abdruecke beim Schnelltippen).
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
      ;; Auto-Einrückung (ide-syntax.lisp): spalten + neue Zeile auf Klammertiefe.
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

(defun ide-command-names ()
  (list "find-file" "save-buffer" "compile-load" "goto-line" "eval-buffer"))

(defun %ide-command-named (name)
  (if (> (string-length name) 1)
      ((lambda (a b)
         (cond ((and (= a 102) (= b 105)) 1002)
               ((and (= a 115) (= b 97)) 1001)
               ((and (= a 99) (= b 111)) 1008)
               ((and (= a 103) (= b 111)) 1012)
               ((and (= a 101) (= b 118)) 1014)
               (t nil)))
       (string-ref name 0)
       (string-ref name 1))
      nil))

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

(defun %ide-direct-p (command)
  (cond ((eq command 1110) 't)
        ((eq command 1003) 't)
        ((eq command 1101) 't)
        ((eq command 1102) 't)
        ((eq command 1106) 't)
        ((eq command 1107) 't)
        ((eq command 1108) 't)
        ((eq command 1109) 't)
        ((eq command 'move-word-right) 't)
        ((eq command 'move-word-left) 't)
        ((eq command 'kill-word) 't)
        ((eq command 'backward-kill-word) 't)
        ((eq command 'kill-line) 't)
        ((eq command 'yank) 't)
        ((eq command 'set-mark) 't)
        ((eq command 'exchange-point-and-mark) 't)
        ((eq command 'kill-region) 't)
        ((eq command 'copy-region-as-kill) 't)
        ((eq command 'page-down) 't)
        ((eq command 'page-up) 't)
        ((eq command 'buffer-start) 't)
        ((eq command 'buffer-end) 't)
        (t nil)))

(defun %ide-page-rows (state)
  ((lambda (rows)
     (if rows
         (if (> rows 2) (- rows 2) 1)
         20))
   (ide-state-render-rows state)))

(defun %ide-word-edit-command-p (command)
  (or (eq command 'move-word-right)
      (or (eq command 'move-word-left)
          (or (eq command 'kill-word)
              (or (eq command 'backward-kill-word)
                  (or (eq command 'kill-line)
                      (eq command 'yank)))))))

(defun %ide-region-command-p (command)
  (or (eq command 'set-mark)
      (or (eq command 'exchange-point-and-mark)
          (or (eq command 'kill-region)
              (eq command 'copy-region-as-kill)))))

(defun %ide-page-command-p (command)
  (or (eq command 'page-down)
      (or (eq command 'page-up)
          (or (eq command 'buffer-start)
              (eq command 'buffer-end)))))

(defun %ide-apply-word-edit-command (state command)
  (cond ((eq command 'move-word-right)
         (%ide-state-with-buffer state
                                 (ide-move-word-right (ide-state-buffer state))))
        ((eq command 'move-word-left)
         (%ide-state-with-buffer state
                                 (ide-move-word-left (ide-state-buffer state))))
        ((eq command 'kill-word)
         (%ide-state-with-buffer state
                                 (ide-kill-word (ide-state-buffer state))))
        ((eq command 'backward-kill-word)
         (%ide-state-with-buffer state
                                 (ide-backward-kill-word (ide-state-buffer state))))
        ((eq command 'kill-line)
         (%ide-state-with-buffer state
                                 (ide-kill-line (ide-state-buffer state))))
        ((eq command 'yank)
         (%ide-state-with-buffer state
                                 (ide-yank (ide-state-buffer state))))
        (t state)))

(defun %ide-apply-region-command (state command)
  (cond
        ((eq command 'set-mark)
         (%ide-state-with-message
          (%ide-state-with-buffer state
                                  (ide-set-mark (ide-state-buffer state)))
          "mark"))
        ((eq command 'exchange-point-and-mark)
         (%ide-state-with-buffer state
                                 (ide-exchange-point-and-mark (ide-state-buffer state))))
        ((eq command 'kill-region)
         (%ide-state-with-buffer state
                                 (ide-kill-region (ide-state-buffer state))))
        ((eq command 'copy-region-as-kill)
         (%ide-state-with-message
          (%ide-state-with-buffer state
                                  (ide-copy-region-as-kill (ide-state-buffer state)))
          "copied"))
        (t state)))

(defun %ide-apply-page-command (state command)
  (cond
        ((eq command 'page-down)
         (%ide-state-with-buffer
          state
          (ide-page-down (ide-state-buffer state) (%ide-page-rows state))))
        ((eq command 'page-up)
         (%ide-state-with-buffer
          state
          (ide-page-up (ide-state-buffer state) (%ide-page-rows state))))
        ((eq command 'buffer-start)
         (%ide-state-with-buffer state
                                 (ide-buffer-start (ide-state-buffer state))))
        ((eq command 'buffer-end)
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

(defun %ide-cmd-action (state command event)
  (if (eq command 1001)
      (%ide-save-key state)
      (if (eq command 1002)
          (%ide-find-key state)
          (if (eq command 1004)
              (%ide-write-key state)
              (if (eq command 1006)
                  (%ide-switch-key state)
                  (if (eq command 1007)
                      (%ide-directory-key state)
                      (if (eq command 1008)
                          (%ide-compile-key state)
                          (if (eq command 1009)
                              (%ide-cycle-buffer state 't)
                              (if (eq command 1010)
                                  (%ide-cycle-buffer state nil)
                                  (if (> command 1010)
                                      (%ide-motion-key state command)
                                      (ide-apply-command state command event)))))))))))

(defun %ide-dispatch-command (state command event)
  (if command
      (if (%ide-direct-p command)
          (ide-apply-command state command event)
          (if (eq command 1104)
              (%ide-line-edge-command state nil)
              (if (eq command 1103)
                  (%ide-line-edge-command state 't)
                  (%ide-cmd-action state command event))))
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

;; COMPUTE-LINES-ONCE (2026-07-07): wie ide-visible-frame-lines, aber
;; mit der schon materialisierten Zeilenliste (ide-render berechnet sie einmal am
;; flachen Top). Vermeidet die zweite ide-buffer-lines-Rekonstruktion im Render.
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

(defun %ide-pad-eol (col columns y attr)
  (if (< col columns)
      (progn
        (screen-put-char col y 32 attr)
        (%ide-pad-eol (+ col 1) columns y attr))
      nil))

;; Plain-Renderer (Statuszeile u. ä. — bewusst OHNE Syntax-Scan; Dynamik-Budget!).
;; CODE-Zeilen gehen über %ide-render-code-line-at (ide-syntax.lisp) = Bulk + Overpaint.
(defun ide-render-line-at (text y columns attr)
  (if (screen-bulk-p)
      (screen-write-string 0 y text (+ attr 64))
      (progn
        (%ide-render-codes-at (string->list text) 0 y attr)
        (%ide-pad-eol (string-length text) columns y attr))))

;; hlmax = erste NICHT-Code-Zeile (Statuszeile): darunter Syntax-Overpaint, ab dort plain.
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

;; Zelle i der Zeilenliste (fuer destruktives rplaca im Render-Cache).
(defun %ide-nth-cell (lines i)
  (if (> i 0) (%ide-nth-cell (cdr lines) (- i 1)) lines))

;; Statuszeilen-Cache (Delta-Render): der Text haengt nur an (name modified message line)
;; -- der Budget-String ist im State vorberechnet. Cache global (Muster Render-Cache):
;; %ide-stcache = ((name modified message . line) . text). Cache-Treffer => Text ist EQ zum
;; zuletzt gemalten -> der Fast-Path unten ueberspringt das Statuszeilen-Malen komplett.
(defun %ide-status-cached (state width)
  (let* ((buffer (car state))
         (cache (if (boundp (quote ide-status-line)) (symbol-value (quote ide-status-line)) nil))
         (name (car buffer))
         (line (car (car (cdr (cdr (cdr buffer))))))
         (mod (car (cdr (cdr (cdr (cdr (cdr buffer)))))))
         (msg (car (cdr state))))
    (if (if cache
            (if (eq name (car (car cache)))
                (if (eq mod (car (cdr (car cache))))
                    (if (eq msg (car (cdr (cdr (car cache)))))
                        (= line (cdr (cdr (cdr (car cache)))))
                        nil)
                    nil)
                nil)
            nil)
        (cdr cache)
        ((lambda (text)
           (progn
             (set-symbol-value (quote ide-status-line)
                               (cons (cons name (cons mod (cons msg line))) text))
             text))
         (ide-status-line state width)))))

;; FAST-PATH je Taste (DESTRUKTIV im Render-Cache, nur 2 rplaca):
;;  - Statuszeile: nur bei Textwechsel malen (Cache-EQ-Test).
;;  - Cursor-Zeile: mit Dirty-Hint nur das Suffix ab Editier-Spalte (Delta-Render,
;;    ide-syntax.lisp) -- ohne Hint (Move etc.) wie bisher die ganze Zeile.
;; COMPUTE-LINES-ONCE (2026-07-07): `lines` = die im Render EINMAL
;; materialisierte Zeilenliste (statt zwei ide-buffer-lines-Rekonstruktionen im
;; Fast-Path: hier + in ide-render-cursor-from).
(defun %ide-render-fast-same-row (state lines old-lines cursor-row columns rows)
  (let* ((row-offset (ide-state-row-offset state))
         (line-index (+ row-offset cursor-row))
         (visible (ide-visible-line
                   (%ide-line-at lines line-index)
                   columns))
         (status-row (- rows 1))
         (old-status (%ide-line-at old-lines status-row))
         (status (%ide-status-cached state columns))
         (hint (if (boundp (quote ide-render)) (symbol-value (quote ide-render)) nil)))
    (progn
      (rplaca (%ide-nth-cell old-lines cursor-row) visible)
      (if (eq status old-status)
          nil
          (progn
            (rplaca (%ide-nth-cell old-lines status-row) status)
            (ide-render-line-at status status-row columns 7)))
      (if hint
          (%ide-render-code-suffix-at visible cursor-row (car hint) (cdr hint))
          (%ide-render-code-line-at visible cursor-row columns 7))
      (set-symbol-value (quote ide-render) nil)
      (ide-render-cursor-from state lines columns rows 129)
      (%ide-state-with-render-cache state old-lines cursor-row columns rows))))

;; COMPUTE-LINES-ONCE (2026-07-07): nimmt die schon materialisierte
;; Zeilenliste statt (ide-buffer-lines buffer) erneut zu rekonstruieren.
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

;; STACK-HYGIENE (2026-07-07): der Full-Redraw haengt tief in der IDE-
;; Aufrufkette. Die fruehere Scroll-Root-Cause war zwar Color-RAM, nicht Stack;
;; flache let*-Slots bleiben hier trotzdem Pflicht, weil zusaetzliche
;; Immediate-Lambda-Frames realen Stack-/GC-Druck erzeugen.
(defun ide-render (state)
  (let* ((size (screen-size))
         (columns (car size))
         (rows (car (cdr size)))
         (state (%ide-scrolled state rows))
         ;; COMPUTE-LINES-ONCE (2026-07-07): die getippte Buffer-Zeilen-
         ;; liste EINMAL pro Render materialisieren (ide-buffer-lines = ~80 Allok.)
         ;; und flach durch die Render-Helfer faedeln — statt sie in Frame-/Cursor-
         ;; Render je erneut zu rekonstruieren. Haelt den Full-Redraw allok-arm
         ;; und vermeidet unnoetigen Stack-/GC-Druck.
         (buffer-lines (ide-buffer-lines (ide-state-buffer state)))
         (old-lines (ide-state-render-lines-for-size state columns rows))
         (cursor-row (ide-cursor-row state rows))
         (previous-cursor-row (ide-state-render-cursor-row state)))
    (if (and old-lines
             cursor-row
             previous-cursor-row
             (= cursor-row previous-cursor-row))
        (%ide-render-fast-same-row state buffer-lines old-lines cursor-row columns rows)
        (let* ((lines (ide-visible-frame-lines-from state buffer-lines columns rows))
               (dirty (ide-dirty-line-indices old-lines
                                               lines
                                               cursor-row
                                               previous-cursor-row)))
          (progn
            (set-symbol-value (quote ide-render) nil)
            (%ide-render-dirty-lines-at lines dirty 0 columns 7 (- rows 1))
            (ide-render-cursor-from state buffer-lines columns rows 129)
            (%ide-state-with-render-cache state lines cursor-row columns rows))))))

;; Render-Koaleszenz gegen das "Nachziehen" beim Schnelltippen: solange weitere
;; Tasten in der Queue warten (poll-key), nur ide-step (~600 Steps) statt
;; step+render (~2400 Steps); gerendert wird EINMAL, wenn die Queue leer ist.
(defun %ide-drain-pending (state)
  ((lambda (k)
     (if k
         (%ide-drain-pending (ide-step state k))
         state))
   (poll-key)))

;; Quit: Run/Stop (PETSCII 3) beendet immer die Command-Loop; ESC (27) nur
;; ausserhalb des Minibuffers. Im Minibuffer ist ESC ein Abbruch wie C-g.
;; (Ohne Exit war ide-run endlos -> nur per Reset verlassbar.)
(defun %ide-quit-key-p (event)
  ((lambda (code) (if (= code 3) 't (= code 27)))
   (ide-event-code event)))

;; Interaktive Command-Loop: read-key -> Quit? -> sonst step -> drain (Koaleszenz) -> render, wiederholen.
(defun ide-run (state)
  ((lambda (saved-state)
     ((lambda (key)
        (if (if (eq (ide-state-message saved-state) 1005)
                (= (ide-event-code key) 3)
                (%ide-quit-key-p key))
            saved-state
            (ide-run (ide-render (%ide-drain-pending (ide-step saved-state key))))))
      (read-key)))
   (%ide-persist-state state)))

;; ---- Buffer-Persistenz + MEHRERE benannte Buffer (Nutzer-Befund/-Wunsch HW 2026-07-05) ----
;; Alle offenen Buffer leben zwischen (ide)-Aufrufen in der Wertzelle des
;; bestehenden Funktionssymbols ide-buffers
;; — eine Alist ((name . buffer) …), der zuletzt aktive vorn. symval-Zellen sind GC-Roots ->
;; überlebt REPL-Arbeit und GC; Zeilen/Name/Cursor-Position bleiben je Buffer erhalten.
;; API: (ide) = zuletzt aktiver Buffer (bzw. frischer "scratch"); (ide "name") = zu Buffer
;; "name" wechseln, bei Bedarf anlegen; (ide-buffers) = Namen, jüngster zuerst.
;; Global-Zugriff NATIV via CALLPRIM 19/20 (symbol-value/set-symbol-value) — der alte
;; eval-Umweg (v2a-Ära) brach im Dev-Core (kein eval-Prim, Budget) und verlor beim
;; RUN/STOP-Exit den Buffer (B4-Handtest-Fund). Null Bank-0: beides ABI-CALLPRIMs.
(defun %ide-buffers-alist ()
  (symbol-value (quote ide-buffers)))

(defun %ide-buffers-find (name alist)
  (if alist
      (if (string= name (car (car alist)))
          (cdr (car alist))
          (%ide-buffers-find name (cdr alist)))
      nil))

;; Alist ohne den Eintrag `name` (nicht-tail; Bufferzahl ist klein).
;; TAIL (2026-07-06): Akku-Muster statt cons-nach-Selbstaufruf (GC_ROOTS-Budget).
(defun %ide-buffers-remove-into (name alist acc)
  (if alist
      (%ide-buffers-remove-into
       name
       (cdr alist)
       (if (string= name (car (car alist))) acc (cons (car alist) acc)))
      acc))

(defun %ide-buffers-remove (name alist)
  (%ide-rev-onto (%ide-buffers-remove-into name alist nil) nil))

;; Buffer unter seinem Namen einsortieren (vorn = zuletzt aktiv) und global sichern.
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

;; name=nil -> zuletzt aktiver (Alist-Kopf) bzw. frischer "scratch";
;; name=String -> vorhandenen holen oder neuen leeren Buffer dieses Namens anlegen.
(defun %ide-resume-buffer (name)
  (if name
      ((lambda (found) (if found found (ide-make-buffer name (list ""))))
       (%ide-buffers-find name (%ide-buffers-alist)))
      ((lambda (alist)
         (if alist (cdr (car alist)) (ide-make-buffer "scratch" (list ""))))
       (%ide-buffers-alist))))

;; Eigener Walker statt (mapcar (function car) …): car ist ein OPCODE, kein CALLPRIM —
;; Opcode-Funktions-Designatoren sind (bewusst) nicht apply-bar -> TYPEERROR.
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
