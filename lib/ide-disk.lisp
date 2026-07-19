;; lisp65 IDE — Disk-/Compile-Anbindung der Buffer.
;;
;; Oeffentliche schmale Workbench-API:
;;   (dir)                                -> Liste sichtbarer Dateinamen
;;   (load-file-to-buffer "src" ["buf"])   -> Disk-Quelle in Buffer laden
;;   (save-buffer-to "src" ["buf"])        -> Buffer-Text als Source speichern
;;   (eval-buffer "buf")                   -> Buffer transient in die laufende Session
;;   (compile-buffer-to-lib "fasl" ["b"])  -> Buffer -> L65M/FASL-Slot
;;   (compile-file-to-lib "src" "fasl")    -> Disk-Quelle -> L65M/FASL-Slot
;; Terminologie: docs/ide-api-terminology.md. "compile" ohne "to-lib"/"to-fasl"
;; ist fuer transiente Compile-APIs reserviert.
;;
;; Alte Namen bleiben im Quelltext als Aliase fuer breite/dev Suites:
;; (ide-open "name"), (ide-save ["name"]). Das Workbench-Disklib-Artefakt
;; entfernt sie zugunsten der aktuellen API-Namen, um Budget fuer die IDE-UX
;; zu behalten.
;; Schreiben laedt den separaten M65D-COW-Kern bei Bedarf und verwendet fuer neue
;; wie bestehende Source-Dateien denselben transaktionalen Pfad. Lesen nutzt den
;; Regel-B-Dir-Walk (Eintrags-Helfer aus stdlib-load.lisp) sowie
;; %disk-read-sector/%disk-byte.
;; Kettenende IMMER via (> next-track 0) pruefen — Fixnum 0 ist truthy (lisp65-Wahrheitswert)!

;; ---- Buffer-Zeilen -> EIN Quelltext-String (Zeilen mit \n verbunden) ----
(defun %ide-join-codes-into (lines acc)
  (if lines
      (%ide-join-codes-into
       (cdr lines)
       (if (cdr lines)
           (cons 10 (%ide-rev-onto (string->list (car lines)) acc))
           (%ide-rev-onto (string->list (car lines)) acc)))
      (%ide-rev-onto acc nil)))

(defun %ide-join-codes (lines)
  (%ide-join-codes-into lines nil))

(defun %ide-join (lines)
  (list->string (%ide-join-codes lines)))

(defun %ide-current-buffer ()
  ((lambda (alist) (if alist (cdr (car alist)) nil))
   (%ide-buffers-alist)))

(defun %ide-selected-buffer (name)
  (if name
      (%ide-buffers-find (car name) (%ide-buffers-alist))
      (%ide-current-buffer)))

(defun %ide-buffer-source (buffer)
  (%ide-join (ide-buffer-lines buffer)))

;; ---- Dir-Suche: Datei -> (track . sector) des Kettenstarts (oder nil) ----
;; Wie %load-scan-directory (stdlib-load.lisp), liefert aber Start statt zu evaluieren.
(defun %ide-disk-scan-entries (codes entry)
  (if (= entry 8)
      nil
      ((lambda (base)
         (if (%load-entry-match-p codes base)
             (cons (%load-entry-byte base 3) (%load-entry-byte base 4))
             (%ide-disk-scan-entries codes (1+ entry))))
       (* entry 32))))

(defun %ide-disk-find (codes track sector fuel)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          ((lambda (hit)
             (if hit
                 hit
                 ((lambda (nt ns)
                    (if (%disk-directory-link-valid-p track sector nt ns)
                        (if (> nt 0) (%ide-disk-find codes nt ns (1- fuel)) nil)
                        nil))
                  (%disk-byte 0) (%disk-byte 1))))
           (%ide-disk-scan-entries codes 0))
          nil)
      nil))

;; ---- Kette lesen: SAVE-Slots sind vorallokiert und rechts mit Spaces gepaddet.
;; Wir bestimmen deshalb erst die effektive Laenge ohne Cons-Zellen, dann lesen
;; wir nur diese Bytes in die Zeilenliste.
(defun %ide-disk-effective-sector (i limit count last)
  (if (> i limit)
      (cons count last)
      ((lambda (c)
         ((lambda (count2)
            (%ide-disk-effective-sector
             (1+ i) limit count2
             (if (= c 32)
                 last
                 (if (= c 10)
                     last
                     (if (= c 13) last count2)))))
          (1+ count)))
       (%disk-byte i))))

(defun %ide-disk-link-valid-p (track sector next-track next-sector)
  (if (= next-track 0)
      (> next-sector 0)
      (if (and (<= next-track 80) (< next-sector 40))
          (not (and (= next-track track) (= next-sector sector)))
          nil)))

(defun %ide-disk-effective-count (track sector fuel count last)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          ((lambda (nt ns)
             (if (%ide-disk-link-valid-p track sector nt ns)
                 ((lambda (pair)
                    (if (> nt 0)
                        (%ide-disk-effective-count nt ns (1- fuel) (car pair) (cdr pair))
                        (cdr pair)))
                  (%ide-disk-effective-sector 2 (if (> nt 0) 255 ns) count last))
                 -1))
           (%disk-byte 0) (%disk-byte 1))
          -1)
      -1))

;; Sektoren direkt in Zeilen umsetzen. Der alte Pfad hielt erst die komplette
;; Datei als Byte-Cons-Liste und danach zusaetzlich die Zeilen im Heap. Diese
;; Fassung haelt nur die aktuelle Zeile; nreverse vermeidet eine zweite
;; Zeichenliste beim Materialisieren des Arena-Strings.
(defun %ide-disk-sector-into (i limit remaining cur acc)
  (if (or (= remaining 0) (> i limit))
      (cons remaining (cons cur acc))
      ((lambda (c)
         (if (= c 10)
             (%ide-disk-sector-into
              (1+ i) limit (1- remaining) nil
              (cons (list->string (nreverse cur)) acc))
             (if (= c 13)
                 (%ide-disk-sector-into
                  (1+ i) limit (1- remaining) cur acc)
                 (%ide-disk-sector-into
                  (1+ i) limit (1- remaining) (cons c cur) acc))))
       (%disk-byte i))))

(defun %ide-disk-read-chain (track sector fuel remaining cur acc)
  (if (= remaining 0)
      (reverse (cons (list->string (nreverse cur)) acc))
      (if (> fuel 0)
          (if (%disk-read-sector track sector)
              ((lambda (nt ns)
                 (if (%ide-disk-link-valid-p track sector nt ns)
                     ((lambda (state)
                        ((lambda (remaining2 cur2 acc2)
                           (if (and (> remaining2 0) (> nt 0))
                               (%ide-disk-read-chain
                                nt ns (1- fuel) remaining2 cur2 acc2)
                               (reverse (cons (list->string (nreverse cur2)) acc2))))
                         (car state) (car (cdr state)) (cdr (cdr state))))
                      (%ide-disk-sector-into
                       2 (if (> nt 0) 255 ns) remaining cur acc))
                     nil))
               (%disk-byte 0) (%disk-byte 1))
              nil)
          nil)))

;; Save-Padding abstreifen: Spaces/Zeilenenden am DATEIENDE = KOPF der reversed Liste.
(defun %ide-disk-trim-rev (rcodes)
  (if rcodes
      ((lambda (c)
         (if (= c 32) (%ide-disk-trim-rev (cdr rcodes))
             (if (= c 10) (%ide-disk-trim-rev (cdr rcodes))
                 (if (= c 13) (%ide-disk-trim-rev (cdr rcodes))
                     rcodes))))
       (car rcodes))
      nil))

;; ---- Datei lesen: Disk -> Zeilen/String ----
(defun %ide-disk-read-lines (name)
  ((lambda (start)
     (if start
         ((lambda (keep)
            (if (< keep 0)
                nil
                (%ide-disk-read-chain (car start) (cdr start) 255 keep nil nil)))
          (%ide-disk-effective-count (car start) (cdr start) 255 0 0))
         nil))
   (%ide-disk-find (string->list name) 40 3 64)))

(defun %ide-disk-read-string (name)
  ((lambda (lines)
     (if lines (%ide-join lines) nil))
   (%ide-disk-read-lines name)))

;; ---- COW-Persistenz: M65D wird erst beim ersten Save geladen ----
(defun %ide-m65d-message (status)
  (if (if (> status 0) (< status 13) nil)
      (nth
       (1- status)
       (quote ("bad name" "duplicate name" "too large" "no space"
               "directory full" "disk invalid" "write/verify failed"
               "remount required" "saved; old space leaked"
               "product media is read-only" "persistence failed"
               "medium changed during write; check both disks")))
      "persistence failed"))

(defun %ide-cow-save (file source)
  (if (if (eq (function-kind (quote m65d-save)) (quote bytecode))
          t
          (load-lib "m65d"))
      ((lambda (status)
         (if (= status 0)
             (progn (set-symbol-value (quote ide-error) nil) t)
             (progn
               (set-symbol-value (quote ide-error) (%ide-m65d-message status))
               (if (= status 9) t nil))))
       ;; R3 one-drive flow: only pre-transaction status 8 authorizes one
       ;; remount and retry.  Mid-transaction status 12 is terminal: no code
       ;; may choose the destination medium on the user's behalf.
       ((lambda (status)
          (if (= status 8)
              ((lambda (remount-status)
                 (if (= remount-status 0)
                     (m65d-save file source)
                     remount-status))
               (m65d-remount))
              status))
        (m65d-save file source)))
      (progn
        (set-symbol-value (quote ide-error) "persistence unavailable")
        nil)))

;; ---- Directory: Disk -> Dateinamenliste ----
(defun %ide-dir-code (raw)
  (if (> raw 127) (- raw 128) raw))

(defun %ide-dir-entry-name-codes (base index acc)
  (if (= index 16)
      (%ide-rev-onto (%ide-disk-trim-rev acc) nil)
      (%ide-dir-entry-name-codes
       base
       (1+ index)
       (cons (%ide-dir-code (%load-entry-byte base (+ 5 index))) acc))))

(defun %ide-dir-scan-entries (entry acc)
  (if (= entry 8)
      acc
      ((lambda (base)
         (%ide-dir-scan-entries
          (1+ entry)
          (if (%load-entry-used-p base)
              (cons (list->string (%ide-dir-entry-name-codes base 0 nil)) acc)
              acc)))
       (* entry 32))))

(defun %ide-dir-first-entry (track sector)
  (if (= track 40)
      (if (= sector 0) 8 0)
      0))

(defun %ide-dir-scan-directory (track sector fuel acc)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          ((lambda (acc2)
             ((lambda (nt ns)
                (if (%disk-directory-link-valid-p track sector nt ns)
                    (if (> nt 0)
                        (%ide-dir-scan-directory nt ns (1- fuel) acc2)
                        (%ide-rev-onto acc2 nil))
                    nil))
              (%disk-byte 0) (%disk-byte 1)))
           (%ide-dir-scan-entries (%ide-dir-first-entry track sector) acc))
          (%ide-rev-onto acc nil))
      (%ide-rev-onto acc nil)))

(defun dir ()
  (%ide-dir-scan-directory 40 0 64 nil))

;; ---- Public API: Disk <-> Buffer ----
(defun ide-error ()
  (if (boundp (quote ide-error)) (symbol-value (quote ide-error)) nil))

(defun %ide-compile-error-message ()
  ((lambda (err) (if err err "compile failed"))
   (compile-error)))

(defun %ide-source-file-p (file)
  (if (or (string-equal file "ide")
          (string-equal file "idex")
          (string-equal file "m65d")
          (string-equal file "an")
          (string-equal file "out")
          (if (>= (string-length file) 4)
              (string-equal (substring file 0 4) "fasl")
              nil))
      nil
      't))

(defun %ide-fasl-slot-p (file)
  (if (>= (string-length file) 4)
      (string-equal (substring file 0 4) "fasl")
      nil))

(defun load-file-to-buffer (file &rest buffer-name)
  (if (%ide-source-file-p file)
      ((lambda (lines)
         (if lines
             (progn
               (set-symbol-value (quote ide-error) nil)
               (%ide-store-buffer
                (%ide-disk-clean-buffer
                 (ide-make-buffer (if buffer-name (car buffer-name) file) lines)
                 file))
               't)
             (progn
               (set-symbol-value (quote ide-error) "source missing")
               nil)))
       (%ide-disk-read-lines file))
      (progn
        (set-symbol-value (quote ide-error) "not source")
        nil)))

(defun save-buffer-to (file &rest buffer-name)
  ((lambda (buf)
     (if buf
         (if (%ide-source-file-p file)
             ((lambda (source)
                (if (%ide-cow-save file source)
                    (progn
                      (%ide-store-buffer (%ide-disk-clean-buffer buf file))
                      't)
                    nil))
              (%ide-buffer-source buf))
             (progn
               (set-symbol-value (quote ide-error) "not source")
               nil))
         (progn
           (set-symbol-value (quote ide-error) "buffer missing")
           nil)))
   (%ide-selected-buffer buffer-name)))

;; ---- Public API: Buffer/Datei -> FASL/L65M-Slot ----
(defun compile-buffer-to-lib (dst &rest buffer-name)
  ((lambda (buf)
     (if buf
         (if (%ide-fasl-slot-p dst)
             (if (%ide-disk-find (string->list dst) 40 3 64)
                 (if (compile-string (%ide-buffer-source buf) dst)
                     (progn (set-symbol-value (quote ide-error) nil) 't)
                     (progn (set-symbol-value (quote ide-error) (%ide-compile-error-message)) nil))
                 (progn (set-symbol-value (quote ide-error) "slot missing") nil))
             (progn (set-symbol-value (quote ide-error) "not fasl") nil))
         (progn (set-symbol-value (quote ide-error) "buffer missing") nil)))
   (%ide-selected-buffer buffer-name)))

(defun compile-file-to-lib (src dst)
  (if (%ide-source-file-p src)
      ((lambda (source)
         (if source
             (if (%ide-fasl-slot-p dst)
                 (if (%ide-disk-find (string->list dst) 40 3 64)
                     (if (compile-string source dst)
                         (progn (set-symbol-value (quote ide-error) nil) 't)
                         (progn (set-symbol-value (quote ide-error) (%ide-compile-error-message)) nil))
                     (progn (set-symbol-value (quote ide-error) "slot missing") nil))
                 (progn (set-symbol-value (quote ide-error) "not fasl") nil))
             (progn (set-symbol-value (quote ide-error) "source missing") nil)))
       (%ide-disk-read-string src))
      (progn (set-symbol-value (quote ide-error) "not source") nil)))

;; ---- Public API: Buffer -> transiente laufende Session ----
(defun eval-buffer (buffer-name)
  (if (eq buffer-name 0)
      ((lambda (form)
         (if (eq form (quote %fasl-eof))
             't
             (progn (lcc-run form) (eval-buffer 0))))
       (%fasl-read-form))
      ((lambda (buf)
         (if buf
             (progn
               (set-symbol-value (quote ide-error) nil)
               (%cs-read-open (%ide-buffer-source buf))
               (eval-buffer 0))
             (progn
               (set-symbol-value (quote ide-error) "buffer missing")
               nil)))
       (%ide-buffers-find buffer-name (%ide-buffers-alist)))))

;; ---- Editor-Keybindings: C-x C-s / C-x C-f / C-x C-w ----
(defun %ide-disk-current-file (buffer)
  (if (stringp (ide-buffer-file-name buffer))
      (ide-buffer-file-name buffer)
      (if (stringp (ide-buffer-name buffer))
          (ide-buffer-name buffer)
          nil)))

(defun %ide-disk-clean-buffer (buffer file)
  ((lambda (b)
     (let* ((b1 (cdr b))
            (b2 (cdr b1))
            (b3 (cdr b2))
            (b4 (cdr b3))
            (b5 (cdr b4))
            (b6 (cdr b5))
            (b7 (cdr b6))
            (b8 (cdr b7)))
       (list (car b)
             file
             (car b2)
             (car b3)
             (car b4)
             nil
             (car b6)
             nil
             (car b8))))
   (%ide-buffer-flush-cache buffer)))

(defun %ide-save-message ()
  (if (ide-error) (ide-error) "saved"))

(defun %ide-save-key (state)
  ((lambda (buffer)
     ((lambda (file)
        (if file
            (progn
              (%ide-store-buffer buffer)
              (if (save-buffer-to file (ide-buffer-name buffer))
                  (%ide-state-with-message
                   (%ide-state-with-buffer state (%ide-resume-buffer (ide-buffer-name buffer)))
                   (%ide-save-message))
                  (%ide-state-with-message state (ide-error))))
            (%ide-state-with-message state "no file")))
      (%ide-disk-current-file buffer)))
   (ide-state-buffer state)))

(defun %ide-find-file-named (state file)
  (if file
      (if (load-file-to-buffer file file)
          (%ide-state-with-message
           (%ide-state-with-buffer state (%ide-resume-buffer file))
           "loaded")
          (%ide-state-with-message state (ide-error)))
      (%ide-state-with-message state "no file")))

(defun %ide-write-file-named (state file)
  ((lambda (buffer)
     (if file
         (progn
           (%ide-store-buffer buffer)
           (if (save-buffer-to file (ide-buffer-name buffer))
               (%ide-state-with-message
                (%ide-state-with-buffer state (%ide-resume-buffer (ide-buffer-name buffer)))
                (%ide-save-message))
               (%ide-state-with-message state (ide-error))))
         (%ide-state-with-message state "no file")))
   (ide-state-buffer state)))

(defun %ide-search-lines-from (needle lines target col index)
  (if lines
      (if (< index target)
          (%ide-search-lines-from needle (cdr lines) target col (+ index 1))
          ((lambda (text)
             (if (= index target)
                 ((lambda (hit)
                    (if hit
                        (cons index (+ col hit))
                        (%ide-search-lines needle (cdr lines) (+ index 1))))
                  (if (< col (string-length text))
                      (search needle (substring text col (string-length text)))
                      nil))
                 (%ide-search-lines needle lines index)))
           (car lines)))
      nil))

(defun %ide-mini-search-submit (state action file)
  (if (> (string-length file) 0)
      ((lambda (hit)
         (if hit
             (%ide-state-with-message
              (%ide-state-with-buffer
               state
               (ide-set-point (ide-state-buffer state) (car hit) (cdr hit)))
              "found")
             (%ide-state-with-message state "not found")))
       ((lambda (point)
          (%ide-search-lines-from
           file
           (ide-buffer-lines (ide-state-buffer state))
           (car point)
           (if (eq action 'search-next) (+ (cdr point) 1) (cdr point))
           0))
        (ide-buffer-point (ide-state-buffer state))))
      (%ide-state-with-message state "no search")))

(defun %ide-decimal-value-from (text index value)
  (if (< index (string-length text))
      ((lambda (code)
         (if (and (>= code 48) (<= code 57))
             (%ide-decimal-value-from text (+ index 1)
                                      (+ (* value 10) (- code 48)))
             nil))
       (string-ref text index))
      value))

(defun %ide-mini-motion-submit (state action file)
  (if (eq action 1012)
      (if (> (string-length file) 0)
          ((lambda (n)
             (if n
                 ((lambda (max)
                    ((lambda (line)
                       (%ide-state-with-message
                        (%ide-state-with-buffer
                         state
                         (ide-set-point (ide-state-buffer state) line 0))
                        "moved"))
                     (if (< n 1)
                         0
                         (if (< n max) (- n 1) (- max 1)))))
                  (ide-line-count (ide-state-buffer state)))
                 (%ide-state-with-message state "invalid line")))
           (%ide-decimal-value-from file 0 0))
          (%ide-state-with-message state "no line"))
      (%ide-state-with-message state "unknown command")))

(defun %ide-find-key (state)
  (%ide-mini-start
   state
   1002
   "Find file: "
   ""
   (%ide-disk-current-file (ide-state-buffer state))
   (remove-if-not (function %ide-source-file-p) (cdr (dir)))))

(defun %ide-write-key (state)
  (%ide-mini-start
   state
   1004
   "Write file: "
   ""
   (%ide-disk-current-file (ide-state-buffer state))
   (remove-if-not (function %ide-source-file-p) (cdr (dir)))))

(defun %ide-mini-file-submit (state action file)
  (cond ((eq action 1002)
         (%ide-find-file-named state file))
        ((eq action 1004)
         (%ide-write-file-named state file))
        ((eq action 1006)
         (if file
             (progn
               (%ide-store-buffer (ide-state-buffer state))
               (%ide-state-with-message
                (%ide-state-with-buffer state (%ide-resume-buffer file))
                "switched"))
             (%ide-state-with-message state "no buffer")))
        ((eq action 1008)
         (if file
             (progn
               (%ide-store-buffer (ide-state-buffer state))
               (if (compile-buffer-to-lib file (ide-buffer-name (ide-state-buffer state)))
                   (if (load-lib file)
                       (%ide-state-with-message state "compiled")
                       (progn
                         (set-symbol-value (quote ide-error) "load failed")
                         (%ide-state-with-message state "load failed")))
                   (%ide-state-with-message state (ide-error))))
             (%ide-state-with-message state "no file")))
        (t nil)))

(defun %ide-mini-submit (state action input default)
  ((lambda (file)
     ((lambda (handled)
        (if handled
            handled
            (cond ((eq action 'execute-command)
                   (%ide-x 'mini state action file))
                  ((eq action 'search)
                   (%ide-x
                    'mini state
                    (if (> (string-length input) 0) action 'search-next)
                    file))
                  ((eq action 1012)
                   (%ide-mini-motion-submit state action file))
                  (t (%ide-state-with-message state "unknown command")))))
      (%ide-mini-file-submit state action file)))
   (if (> (string-length input) 0) input default)))

;; ---- Historische IDE-Namen ----
(defun ide-save (&rest name)
  ((lambda (buf)
     (if buf
         (funcall (function save) (ide-buffer-name buf) (%ide-buffer-source buf))
         nil))
   (%ide-selected-buffer name)))

(defun ide-open (name)
  (load-file-to-buffer name))
