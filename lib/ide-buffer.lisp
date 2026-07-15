(defun ide-make-buffer (name lines)
  (list name nil lines (cons 0 0) nil nil 'lisp-mode nil nil))

(defun ide-buffer-name (buffer)
  (car buffer))

(defun ide-buffer-file-name (buffer)
  (car (cdr buffer)))

(defun ide-buffer-lines (buffer)
  (let* ((lines (car (cdr (cdr buffer))))
         (cache (ide-buffer-locals buffer)))
    (if cache
        (%ide-lines-replace lines
                            (car cache)
                            (list->string (reverse (car (cdr cache)))))
        lines)))

(defun ide-buffer-point (buffer)
  (car (cdr (cdr (cdr buffer)))))

(defun ide-buffer-mark (buffer)
  (car (cdr (cdr (cdr (cdr buffer))))))

(defun ide-buffer-modified-p (buffer)
  (car (cdr (cdr (cdr (cdr (cdr buffer)))))))

(defun ide-buffer-mode (buffer)
  (car (cdr (cdr (cdr (cdr (cdr (cdr buffer))))))))

(defun ide-buffer-locals (buffer)
  (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr buffer)))))))))

(defun ide-buffer-diagnostics (buffer)
  (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr buffer))))))))))

(defun %ide-buffer-flush-cache (buffer)
  (if (ide-buffer-locals buffer)
      (let* ((b1 (cdr buffer))
             (b2 (cdr b1))
             (b3 (cdr b2))
             (b4 (cdr b3))
             (b5 (cdr b4))
             (b6 (cdr b5))
             (b7 (cdr b6))
             (b8 (cdr b7)))
        (list (car buffer)
              (car b1)
              (ide-buffer-lines buffer)
              (car b3)
              (car b4)
              (car b5)
              (car b6)
              nil
              (car b8)))
      buffer))

(defun ide-point-line (point)
  (car point))

(defun ide-point-column (point)
  (cdr point))

(defun %ide-min (a b)
  (if (< a b) a b))

(defun %ide-clamp-line (line count)
  (if (< line 0)
      0
      (if (< line count) line (- count 1))))

(defun %ide-buffer-with-point (buffer point)
  (let* ((b1 (cdr buffer))
         (b2 (cdr b1))
         (b3 (cdr b2))
         (b4 (cdr b3))
         (b5 (cdr b4))
         (b6 (cdr b5))
         (b7 (cdr b6))
         (b8 (cdr b7)))
    (list (car buffer)
          (car b1)
          (car b2)
          point
          (car b4)
          (car b5)
          (car b6)
          (car b7)
          (car b8))))

(defun %ide-buffer-with-mark (buffer mark)
  (let* ((b1 (cdr buffer))
         (b2 (cdr b1))
         (b3 (cdr b2))
         (b4 (cdr b3))
         (b5 (cdr b4))
         (b6 (cdr b5))
         (b7 (cdr b6))
         (b8 (cdr b7)))
    (list (car buffer)
          (car b1)
          (car b2)
          (car b3)
          mark
          (car b5)
          (car b6)
          (car b7)
          (car b8))))

(defun %ide-buffer-with-lines-point (buffer lines point &rest maybe-locals)
  (let* ((b1 (cdr buffer))
         (b2 (cdr b1))
         (b3 (cdr b2))
         (b4 (cdr b3))
         (b5 (cdr b4))
         (b6 (cdr b5))
         (b7 (cdr b6))
         (b8 (cdr b7)))
    (list (car buffer)
          (car b1)
          lines
          point
          (car b4)
          't
          (car b6)
          (if maybe-locals (car maybe-locals) nil)
          (car b8))))

(defun ide-set-point (buffer line column)
  (%ide-buffer-with-point buffer (cons line column)))

(defun ide-line-count (buffer)
  (length (ide-buffer-lines buffer)))

(defun %ide-line-at (lines index)
  (if lines
      (if (= index 0)
          (car lines)
          (%ide-line-at (cdr lines) (- index 1)))
      ""))

(defun ide-line-at (buffer index)
  (%ide-line-at (ide-buffer-lines buffer) index))

(defun ide-current-line (buffer)
  (ide-line-at buffer (ide-point-line (ide-buffer-point buffer))))

;; TAIL-REKURSIV (2026-07-06): die alten Fassungen consten NACH dem Selbstaufruf
;; (kein TCO) -> O(index) VM-Frames. Beim RETURN-Spam wuchs die Einfuege-Tiefe mit
;; der Zeilennummer, riss bei ~Zeile 23 (Host) / ~13 (Geraet) das GC_ROOTS-Budget
;; und kaskadierte in "vm: type error". Jetzt: EIN Tail-Lauf sammelt den Praefix
;; umgedreht ein, ein zweiter Tail-Lauf const ihn zurueck -> Tiefe O(1).
(defun %ide-lines-split-at (lines index acc)
  (if (if (> index 0) lines nil)
      (%ide-lines-split-at (cdr lines) (- index 1) (cons (car lines) acc))
      (cons acc lines)))

(defun %ide-rev-onto (acc tail)
  (if acc
      (%ide-rev-onto (cdr acc) (cons (car acc) tail))
      tail))

(defun %ide-lines-replace (lines index line)
  ((lambda (s)
     (%ide-rev-onto (car s) (cons line (cdr (cdr s)))))
   (%ide-lines-split-at lines index nil)))

(defun %ide-lines-insert (lines index line)
  ((lambda (s)
     (%ide-rev-onto (car s) (cons line (cdr s))))
   (%ide-lines-split-at lines index nil)))

(defun %ide-lines-delete (lines index)
  ((lambda (s)
     (%ide-rev-onto (car s) (cdr (cdr s))))
   (%ide-lines-split-at lines index nil)))

(defun %ide-drop-lines (lines count)
  (if (> count 0)
      (if lines
          (%ide-drop-lines (cdr lines) (- count 1))
          nil)
      lines))

;; TAIL (2026-07-06, RETURN-Spam-Befund): die alte Fassung conste NACH dem
;; Selbstaufruf -> O(count) Frames JE RENDER (Sichtfenster waechst mit dem Buffer
;; bis 24) — zusammen mit der Aufrufkette riss das GC_ROOTS. Muster: Akku + rev-onto.
(defun %ide-take-into (lines count acc)
  (if (if (> count 0) lines nil)
      (%ide-take-into (cdr lines) (- count 1) (cons (car lines) acc))
      acc))

(defun %ide-take-lines (lines count)
  (%ide-rev-onto (%ide-take-into lines count nil) nil))

(defun ide-region-lines (buffer start end)
  (%ide-take-lines (%ide-drop-lines (ide-buffer-lines buffer) start)
                   (- end start)))

;; COMPUTE-LINES-ONCE (2026-07-07): Render-Variante, die die schon
;; materialisierte Zeilenliste als Parameter nimmt, statt sie erneut aus dem
;; Buffer-Cache zu rekonstruieren (ide-buffer-lines = ~80 Allokationen bei
;; getipptem Buffer). ide-render berechnet die Liste EINMAL am flachen Top und
;; faedelt sie hier durch -> nur noch eine Rekonstruktion pro Render.
;; Der spaetere Scroll-Muell war ein separater Color-RAM-Fenster-Bug; siehe
;; docs/ide-scroll-diagnostics-plan.md.
(defun ide-region-lines-from (lines start end)
  (%ide-take-lines (%ide-drop-lines lines start)
                   (- end start)))

(defun %ide-char-take-into (chars count acc)
  (if (> count 0)
      (if chars
          (%ide-char-take-into (cdr chars)
                               (- count 1)
                               (cons (car chars) acc))
          (reverse acc))
      (reverse acc)))

(defun %ide-char-take (chars count)
  (%ide-char-take-into chars count nil))

(defun %ide-char-drop (chars count)
  (if (> count 0)
      (if chars
          (%ide-char-drop (cdr chars) (- count 1))
          nil)
      chars))

;; KANONISCHES ""-Objekt: Littab-Konstanten einer Funktion sind ueber Aufrufe hinweg
;; EQ-stabil -> alle Leerzeilen-Produzenten teilen DIESES Objekt, und der Dirty-Scan
;; des Renders (nacktes eq) erkennt Leer==Leer ohne string-length-Kosten.
(defun %ide-empty-str () "")

(defun ide-string-prefix (text count)
  (if (< count 1)
      (%ide-empty-str)
      (list->string (%ide-char-take (string->list text) count))))

(defun ide-string-suffix (text count)
  (if (< (string-length text) (+ count 1))
      (%ide-empty-str)
      (list->string (%ide-char-drop (string->list text) count))))

(defun ide-string-insert-code (text column code)
  ((lambda (chars)
     (list->string
      (append (%ide-char-take chars column)
              (cons code (%ide-char-drop chars column)))))
   (string->list text)))

(defun ide-string-delete-before (text column)
  (if (> column 0)
      ((lambda (chars)
         (list->string
          (append (%ide-char-take chars (- column 1))
                  (%ide-char-drop chars column))))
       (string->list text))
      text))

(defun ide-string-append (left right)
  (list->string (append (string->list left) (string->list right))))

(defun %ide-point<= (left right)
  (if (< (car left) (car right))
      't
      (if (= (car left) (car right))
          (<= (cdr left) (cdr right))
          nil)))

(defun %ide-region-bounds (buffer)
  ((lambda (mark point)
     (if mark
         (if (%ide-point<= mark point)
             (cons mark point)
             (cons point mark))
         nil))
   (ide-buffer-mark buffer)
   (ide-buffer-point buffer)))

(defun %ide-last-line (lines)
  (if (cdr lines)
      (%ide-last-line (cdr lines))
      (car lines)))

(defun %ide-lines-replace-range (lines start end new-lines)
  ((lambda (s)
     (%ide-rev-onto
      (car s)
      (append new-lines (%ide-drop-lines (cdr s) (+ (- end start) 1)))))
   (%ide-lines-split-at lines start nil)))

(defun %ide-region-parts-tail (lines end-column)
  (if (cdr lines)
      (cons (car lines) (%ide-region-parts-tail (cdr lines) end-column))
      (list (ide-string-prefix (car lines) end-column))))

(defun %ide-region-parts (lines start-line start-column end-line end-column)
  ((lambda (selected)
     (if (cdr selected)
         (cons (ide-string-suffix (car selected) start-column)
               (%ide-region-parts-tail (cdr selected) end-column))
         (list (ide-string-prefix
                (ide-string-suffix (car selected) start-column)
                (- end-column start-column)))))
   (ide-region-lines-from lines start-line (+ end-line 1))))

(defun %ide-yank-parts-tail (parts suffix)
  (if (cdr parts)
      (cons (car parts) (%ide-yank-parts-tail (cdr parts) suffix))
      (list (ide-string-append (car parts) suffix))))

(defun %ide-yank-parts-lines (prefix suffix parts)
  (if (cdr parts)
      (cons (ide-string-append prefix (car parts))
            (%ide-yank-parts-tail (cdr parts) suffix))
      (list (ide-string-append
             (ide-string-append prefix (car parts))
             suffix))))

(defun ide-region-text (buffer)
  ((lambda (bounds)
     (if (if bounds (= (car (car bounds)) (car (cdr bounds))) nil)
         ((lambda (line)
            (ide-string-prefix
             (ide-string-suffix line (cdr (car bounds)))
             (- (cdr (cdr bounds)) (cdr (car bounds)))))
          (ide-line-at buffer (car (car bounds))))
         (if bounds
             (%ide-region-parts (ide-buffer-lines buffer)
                                (car (car bounds))
                                (cdr (car bounds))
                                (car (cdr bounds))
                                (cdr (cdr bounds)))
             nil)))
   (%ide-region-bounds buffer)))

(defun ide-set-mark (buffer)
  (%ide-buffer-with-mark buffer (ide-buffer-point buffer)))

(defun ide-exchange-point-and-mark (buffer)
  ((lambda (mark)
     (if mark
         (%ide-buffer-with-mark (%ide-buffer-with-point buffer mark)
                                (ide-buffer-point buffer))
         buffer))
   (ide-buffer-mark buffer)))

(defun %ide-kill-region-single (buffer bounds)
  (let* ((line-index (car (car bounds)))
         (start-column (cdr (car bounds)))
         (end-column (cdr (cdr bounds)))
         (lines (ide-buffer-lines buffer))
         (line (%ide-line-at lines line-index))
         (killed (ide-string-prefix
                  (ide-string-suffix line start-column)
                  (- end-column start-column))))
    (progn
      (set-symbol-value (quote *ide-kill-ring*) killed)
      (%ide-buffer-with-mark
       (%ide-buffer-with-lines-point
        buffer
        (%ide-lines-replace
         lines
         line-index
         (ide-string-append (ide-string-prefix line start-column)
                            (ide-string-suffix line end-column)))
        (car bounds))
       nil))))

(defun %ide-kill-region-lines (buffer bounds)
  (let* ((start-line (car (car bounds)))
         (start-column (cdr (car bounds)))
         (end-line (car (cdr bounds)))
         (end-column (cdr (cdr bounds)))
         (lines (ide-buffer-lines buffer))
         (first-line (%ide-line-at lines start-line))
         (last-line (%ide-line-at lines end-line))
         (killed (%ide-region-parts lines
                                    start-line
                                    start-column
                                    end-line
                                    end-column))
         (joined (ide-string-append
                  (ide-string-prefix first-line start-column)
                  (ide-string-suffix last-line end-column))))
    (progn
      (set-symbol-value (quote *ide-kill-ring*) killed)
      (%ide-buffer-with-mark
       (%ide-buffer-with-lines-point
        buffer
        (%ide-lines-replace-range lines start-line end-line (list joined))
        (car bounds))
       nil))))

(defun ide-kill-region (buffer)
  ((lambda (bounds)
     (if (if bounds (= (car (car bounds)) (car (cdr bounds))) nil)
         (%ide-kill-region-single buffer bounds)
         (if bounds
             (%ide-kill-region-lines buffer bounds)
             buffer)))
   (%ide-region-bounds buffer)))

(defun ide-copy-region-as-kill (buffer)
  (progn
    ((lambda (text)
       (if text (set-symbol-value (quote *ide-kill-ring*) text) nil))
     (ide-region-text buffer))
    buffer))

(defun ide-insert-char (buffer code)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (raw-lines (car (cdr (cdr buffer))))
         (cache (ide-buffer-locals buffer))
         (cached (and cache
                      (= (car cache) line-index)
                      (= (car (cdr (cdr cache))) column)))
         (new-column (+ column 1)))
    (if cached
        (%ide-buffer-with-lines-point
         buffer
         raw-lines
         (cons line-index new-column)
         (list line-index (cons code (car (cdr cache))) new-column))
        (let* ((lines (ide-buffer-lines buffer))
               (line (%ide-line-at lines line-index)))
          (if (= column (string-length line))
              (%ide-buffer-with-lines-point
               buffer
               lines
               (cons line-index new-column)
               (list line-index (cons code (reverse (string->list line))) new-column))
              (%ide-buffer-with-lines-point
               buffer
               (%ide-lines-replace lines
                                   line-index
                                   (ide-string-insert-code line column code))
               (cons line-index new-column)))))))

(defun ide-split-line (buffer)
  ((lambda (point)
     ((lambda (line)
        ((lambda (prefix)
           ((lambda (suffix)
              (%ide-buffer-with-lines-point
               buffer
               (%ide-lines-insert
                (%ide-lines-replace (ide-buffer-lines buffer)
                                    (ide-point-line point)
                                    prefix)
                (+ (ide-point-line point) 1)
                suffix)
               (cons (+ (ide-point-line point) 1) 0)))
            (ide-string-suffix line (ide-point-column point))))
         (if (= (ide-point-column point) (string-length line))
             line
             (ide-string-prefix line (ide-point-column point)))))
      (ide-line-at buffer (ide-point-line point))))
   (ide-buffer-point buffer)))

(defun ide-delete-backward-char (buffer)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (raw-lines (car (cdr (cdr buffer))))
         (cache (ide-buffer-locals buffer))
         (cached (and cache
                      (> column 0)
                      (= (car cache) line-index)
                      (= (car (cdr (cdr cache))) column)))
         (new-column (- column 1)))
    (if cached
        (%ide-buffer-with-lines-point
         buffer
         raw-lines
         (cons line-index new-column)
         (list line-index (cdr (car (cdr cache))) new-column))
        (if (> column 0)
            ((lambda (line)
               (%ide-buffer-with-lines-point
                buffer
                (%ide-lines-replace (ide-buffer-lines buffer)
                                    line-index
                                    (ide-string-delete-before line column))
                (cons line-index new-column)))
             (ide-line-at buffer line-index))
            (if (> line-index 0)
                ((lambda (prev)
                   ((lambda (current)
                      (%ide-buffer-with-lines-point
                       buffer
                       (%ide-lines-delete
                        (%ide-lines-replace (ide-buffer-lines buffer)
                                            (- line-index 1)
                                            (ide-string-append prev current))
                        line-index)
                       (cons (- line-index 1) (string-length prev))))
                    (ide-line-at buffer line-index)))
                 (ide-line-at buffer (- line-index 1)))
                buffer)))))

(defun ide-delete-forward-char (buffer)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (lines (ide-buffer-lines buffer))
         (line (%ide-line-at lines line-index)))
    (if (< column (string-length line))
        (%ide-buffer-with-lines-point
         buffer
         (%ide-lines-replace lines
                             line-index
                             (ide-string-delete-before line (+ column 1)))
         point)
        (if (< (+ line-index 1) (length lines))
            ((lambda (next)
               (%ide-buffer-with-lines-point
                buffer
                (%ide-lines-delete
                 (%ide-lines-replace lines
                                     line-index
                                     (ide-string-append line next))
                 (+ line-index 1))
                point))
             (%ide-line-at lines (+ line-index 1)))
            buffer))))

(defun ide-kill-line (buffer)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (lines (ide-buffer-lines buffer))
         (line (%ide-line-at lines line-index)))
    (if (< column (string-length line))
        ((lambda (killed)
           (progn
             (set-symbol-value (quote *ide-kill-ring*) killed)
             (%ide-buffer-with-lines-point
              buffer
              (%ide-lines-replace lines
                                  line-index
                                  (ide-string-prefix line column))
              point)))
         (ide-string-suffix line column))
        (if (< (+ line-index 1) (length lines))
            ((lambda (next)
               (progn
                 (set-symbol-value (quote *ide-kill-ring*) (list->string (list 10)))
                 (%ide-buffer-with-lines-point
                  buffer
                  (%ide-lines-delete
                   (%ide-lines-replace lines
                                       line-index
                                       (ide-string-append line next))
                   (+ line-index 1))
                  point)))
             (%ide-line-at lines (+ line-index 1)))
            (progn
              (set-symbol-value (quote *ide-kill-ring*) (%ide-empty-str))
              buffer)))))

(defun %ide-yank-string (buffer text)
  (if (> (string-length text) 0)
      (if (if (= (string-length text) 1)
              (= (string-ref text 0) 10)
              nil)
          (ide-split-line buffer)
          (let* ((point (ide-buffer-point buffer))
                 (line-index (car point))
                 (column (cdr point))
                 (lines (ide-buffer-lines buffer))
                 (line (%ide-line-at lines line-index)))
            (%ide-buffer-with-lines-point
             buffer
             (%ide-lines-replace
              lines
              line-index
              (ide-string-append
               (ide-string-append (ide-string-prefix line column) text)
               (ide-string-suffix line column)))
             (cons line-index (+ column (string-length text))))))
      buffer))

(defun %ide-yank-line-list (buffer parts)
  (if parts
      (let* ((point (ide-buffer-point buffer))
             (line-index (car point))
             (column (cdr point))
             (lines (ide-buffer-lines buffer))
             (line (%ide-line-at lines line-index))
             (last-part (%ide-last-line parts)))
        (%ide-buffer-with-lines-point
         buffer
         (%ide-lines-replace-range
          lines
          line-index
          line-index
          (%ide-yank-parts-lines
           (ide-string-prefix line column)
           (ide-string-suffix line column)
           parts))
         (if (cdr parts)
             (cons (+ line-index (- (length parts) 1))
                   (string-length last-part))
             (cons line-index (+ column (string-length (car parts)))))))
      buffer))

(defun ide-yank (buffer)
  ((lambda (text)
     (if (stringp text)
         (%ide-yank-string buffer text)
         (%ide-yank-line-list buffer text)))
   (if (funcall (function boundp) (quote *ide-kill-ring*))
       (symbol-value (quote *ide-kill-ring*))
       (%ide-empty-str))))

(defun ide-move-left (buffer)
  ((lambda (point)
     (if (> (ide-point-column point) 0)
         (ide-set-point buffer (ide-point-line point) (- (ide-point-column point) 1))
         (if (> (ide-point-line point) 0)
             ((lambda (prev-line)
                (ide-set-point buffer
                               (- (ide-point-line point) 1)
                               (string-length prev-line)))
              (ide-line-at buffer (- (ide-point-line point) 1)))
             buffer)))
   (ide-buffer-point buffer)))

(defun ide-move-right (buffer)
  ((lambda (point)
     ((lambda (line)
        (if (< (ide-point-column point) (string-length line))
            (ide-set-point buffer (ide-point-line point) (+ (ide-point-column point) 1))
            (if (< (+ (ide-point-line point) 1) (ide-line-count buffer))
                (ide-set-point buffer (+ (ide-point-line point) 1) 0)
                buffer)))
      (ide-line-at buffer (ide-point-line point))))
   (ide-buffer-point buffer)))

(defun ide-move-line-relative (buffer delta)
  ((lambda (point)
     ((lambda (target)
        ((lambda (line)
           (ide-set-point buffer target (%ide-min (cdr point) (string-length line))))
         (ide-line-at buffer target)))
      (%ide-clamp-line (+ (car point) delta) (ide-line-count buffer))))
   (ide-buffer-point buffer)))

(defun ide-buffer-start (buffer)
  (ide-set-point buffer 0 0))

(defun ide-buffer-end (buffer)
  ((lambda (last)
     (ide-set-point buffer last (string-length (ide-line-at buffer last))))
   (- (ide-line-count buffer) 1)))

(defun ide-page-down (buffer rows)
  (ide-move-line-relative buffer rows))

(defun ide-page-up (buffer rows)
  (ide-move-line-relative buffer (- 0 rows)))

(defun %ide-word-scan (chars count seen)
  (if chars
      ((lambda (c)
         ((lambda (wordp)
            (if wordp
                (%ide-word-scan (cdr chars) (+ count 1) 't)
                (if seen
                    count
                    (%ide-word-scan (cdr chars) (+ count 1) nil))))
          (and (> c 32)
               (if (= c 40) nil
                   (if (= c 41) nil
                       (if (= c 34) nil
                           (if (= c 39) nil
                               (if (= c 96) nil
                                   (if (= c 44) nil
                                       (if (= c 59) nil 't))))))))))
       (car chars))
      count))

(defun ide-move-word-right (buffer)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (line (ide-line-at buffer line-index))
         (chars (%ide-char-drop (string->list line) column))
         (count (%ide-word-scan chars 0 nil)))
    (if (> count 0)
        (ide-set-point buffer line-index (+ column count))
        (if (< (+ line-index 1) (ide-line-count buffer))
            (ide-move-word-right (ide-set-point buffer (+ line-index 1) 0))
            (ide-set-point buffer line-index (string-length line))))))

(defun ide-move-word-left (buffer)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (line (ide-line-at buffer line-index))
         (chars (reverse (%ide-char-take (string->list line) column)))
         (count (%ide-word-scan chars 0 nil)))
    (if (> count 0)
        (ide-set-point buffer line-index (- column count))
        (if (> line-index 0)
            (ide-move-word-left
             (ide-set-point buffer
                            (- line-index 1)
                            (string-length (ide-line-at buffer (- line-index 1)))))
            (ide-set-point buffer line-index 0)))))

(defun ide-kill-word (buffer)
  (let* ((point (ide-buffer-point buffer))
         (line-index (car point))
         (column (cdr point))
         (target (ide-buffer-point (ide-move-word-right buffer)))
         (target-column (if (= (car target) line-index)
                            (cdr target)
                            (string-length (ide-line-at buffer line-index)))))
    (if (> target-column column)
        (let* ((lines (ide-buffer-lines buffer))
               (line (%ide-line-at lines line-index))
               (killed (ide-string-prefix
                        (ide-string-suffix line column)
                        (- target-column column))))
          (progn
            (set-symbol-value (quote *ide-kill-ring*) killed)
            (%ide-buffer-with-lines-point
             buffer
             (%ide-lines-replace
              lines
              line-index
              (ide-string-append (ide-string-prefix line column)
                                 (ide-string-suffix line target-column)))
             point)))
        buffer)))

(defun ide-backward-kill-word (buffer)
  (let* ((point (ide-buffer-point buffer))
         (target (ide-buffer-point (ide-move-word-left buffer)))
         (line-index (car point))
         (column (cdr point))
         (target-column (cdr target)))
    (if (if (= (car target) line-index) (> column target-column) nil)
        (let* ((lines (ide-buffer-lines buffer))
               (line (%ide-line-at lines line-index))
               (killed (ide-string-prefix
                        (ide-string-suffix line target-column)
                        (- column target-column))))
          (progn
            (set-symbol-value (quote *ide-kill-ring*) killed)
            (%ide-buffer-with-lines-point
             buffer
             (%ide-lines-replace
              lines
              line-index
              (ide-string-append (ide-string-prefix line target-column)
                                 (ide-string-suffix line column)))
             (cons line-index target-column))))
        buffer)))

(defun ide-move-up (buffer)
  ((lambda (point)
     (if (> (ide-point-line point) 0)
         ((lambda (line)
            (ide-set-point buffer
                           (- (ide-point-line point) 1)
                           (%ide-min (ide-point-column point) (string-length line))))
          (ide-line-at buffer (- (ide-point-line point) 1)))
         buffer))
   (ide-buffer-point buffer)))

(defun ide-move-down (buffer)
  ((lambda (point)
     (if (< (+ (ide-point-line point) 1) (ide-line-count buffer))
         ((lambda (line)
            (ide-set-point buffer
                           (+ (ide-point-line point) 1)
                           (%ide-min (ide-point-column point) (string-length line))))
          (ide-line-at buffer (+ (ide-point-line point) 1)))
         buffer))
   (ide-buffer-point buffer)))

(defun %ide-top-level-line-p (line)
  (if (> (string-length line) 0)
      (= (string-ref line 0) 40)
      nil))

(defun %ide-find-defun-start (lines target index current)
  (if lines
      (%ide-find-defun-start (cdr lines)
                             target
                             (+ index 1)
                             (if (and (<= index target)
                                      (%ide-top-level-line-p (car lines)))
                                 index
                                 current))
      current))

(defun %ide-find-defun-end (lines start index fallback)
  (if lines
      (if (and (> index start) (%ide-top-level-line-p (car lines)))
          index
          (%ide-find-defun-end (cdr lines) start (+ index 1) fallback))
      fallback))

(defun ide-defun-region (buffer line)
  ((lambda (lines)
     ((lambda (start)
        (if start
            (cons start (%ide-find-defun-end lines start 0 (length lines)))
            nil))
      (%ide-find-defun-start lines line 0 nil)))
   (ide-buffer-lines buffer)))
