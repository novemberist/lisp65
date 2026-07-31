; L65P-v1 cold library-index resolver.
;
; The generated L65INDEX file is data, never evaluated.  Its fixed-width rows
; bind one canonical name to one L65S combined CRC, dependency ordinals,
; artifact locator, and exact W1 deltas.  Loaded truth is queried from the
; generation-bound C2D image rows through the existing one-argument
; %disk-load-lib seam; there is deliberately no *loaded-libs* registry here.

(defun %l65i-open-sector (track sector)
  (if (%disk-read-sector track sector)
      (progn
        (set-symbol-value '*l65i-track* track)
        (set-symbol-value '*l65i-sector* sector)
        (set-symbol-value '*l65i-next-track* (%disk-byte 0))
        (set-symbol-value '*l65i-next-sector* (%disk-byte 1))
        (set-symbol-value '*l65i-offset* 2)
        t)
      nil))

(defun %l65i-next-byte ()
  (if (= (symbol-value '*l65i-offset*) 256)
      (if (> (symbol-value '*l65i-next-track*) 0)
          (if (%disk-directory-link-valid-p
               (symbol-value '*l65i-track*)
               (symbol-value '*l65i-sector*)
               (symbol-value '*l65i-next-track*)
               (symbol-value '*l65i-next-sector*))
              (%l65i-open-sector
                (symbol-value '*l65i-next-track*)
                (symbol-value '*l65i-next-sector*))
              nil)
          nil)
      t)
  (if (< (symbol-value '*l65i-offset*) 256)
      (let ((value (%disk-byte (symbol-value '*l65i-offset*))))
        (set-symbol-value '*l65i-offset*
                          (1+ (symbol-value '*l65i-offset*)))
        value)
      nil))

(defun %l65i-crc-bits (count)
  (if (> count 0)
      (let ((hi (symbol-value '*l65i-crc-hi*))
            (lo (symbol-value '*l65i-crc-lo*)))
        (let ((top (> hi 127))
              (next-hi (mod (+ (* hi 2) (if (> lo 127) 1 0)) 256))
              (next-lo (mod (* lo 2) 256)))
          (set-symbol-value '*l65i-crc-hi*
            (if top (logxor next-hi 16) next-hi))
          (set-symbol-value '*l65i-crc-lo*
            (if top (logxor next-lo 33) next-lo))
          (%l65i-crc-bits (1- count))))
      t))

(defun %l65i-crc-byte (value)
  (set-symbol-value '*l65i-crc-hi*
                    (logxor (symbol-value '*l65i-crc-hi*) value))
  (%l65i-crc-bits 8)
  value)

(defun %l65i-next-crc ()
  (let ((value (%l65i-next-byte)))
    (if (numberp value) (%l65i-crc-byte value) nil)))

(defun %l65i-row-crc-byte (value)
  (let ((overall-hi (symbol-value '*l65i-crc-hi*))
        (overall-lo (symbol-value '*l65i-crc-lo*)))
    (set-symbol-value '*l65i-crc-hi* (symbol-value '*l65i-row-hi*))
    (set-symbol-value '*l65i-crc-lo* (symbol-value '*l65i-row-lo*))
    (%l65i-crc-byte value)
    (set-symbol-value '*l65i-row-hi* (symbol-value '*l65i-crc-hi*))
    (set-symbol-value '*l65i-row-lo* (symbol-value '*l65i-crc-lo*))
    (set-symbol-value '*l65i-crc-hi* overall-hi)
    (set-symbol-value '*l65i-crc-lo* overall-lo)
    (%l65i-crc-byte value)))

(defun %l65i-next-row ()
  (let ((value (%l65i-next-byte)))
    (if (numberp value) (%l65i-row-crc-byte value) nil)))

(defun %l65i-u16 (row-p)
  (let ((lo (if row-p (%l65i-next-row) (%l65i-next-crc))))
    (let ((hi (if row-p (%l65i-next-row) (%l65i-next-crc))))
      (if (if (numberp lo) (numberp hi) nil)
          (cons lo hi)
          nil))))

(defun %l65i-read-bytes (count row-p acc)
  (if (> count 0)
      (let ((value (if row-p (%l65i-next-row) (%l65i-next-crc))))
        (if (numberp value)
            (%l65i-read-bytes (1- count) row-p (cons value acc))
            nil))
      (reverse acc)))

(defun %l65i-name-bytes (count acc ended)
  (if (> count 0)
      (let ((value (%l65i-next-row)))
        (if (numberp value)
            (if ended
                (if (= value 0)
                    (%l65i-name-bytes (1- count) acc t)
                    nil)
                (if (= value 0)
                    (%l65i-name-bytes (1- count) acc t)
                    (if (if (> value 32) (< value 127) nil)
                        (%l65i-name-bytes
                          (1- count) (cons value acc) nil)
                        nil)))
            nil))
      (if acc (%string-from-codes (reverse acc)) nil)))

(defun %l65i-dependencies (left count rows acc)
  (if (> left 0)
      (let ((ordinal (%l65i-next-row)))
        (if (numberp ordinal)
            (if (> count 0)
                (if (< ordinal rows)
                    (%l65i-dependencies
                      (1- left) (1- count) rows (cons ordinal acc))
                    nil)
                (if (= ordinal 255)
                    (%l65i-dependencies (1- left) 0 rows acc)
                    nil))
            nil))
      (if (= count 0) (cons t (reverse acc)) nil)))

; Row shape:
;   name identity-bytes track sector dependency-ordinals
;   bank2 images entries resolutions roots scratch artifact-bytes
(defun %l65i-row-base-p
  (name track sector identity dependencies source)
  (if name
      (if (if (numberp track) (> track 0) nil)
          (if (if (numberp sector) (< sector 40) nil)
              (if (if identity (= (length identity) 4) nil)
                  (if dependencies (= source 2) nil)
                  nil)
              nil)
          nil)
      nil))

(defun %l65i-row-capacity-p
  (artifact-bytes bank2 images entries resolutions roots scratch)
  (if artifact-bytes
      (if bank2
          (if (if (numberp images) (> images 0) nil)
              (if entries
                  (if resolutions
                      (if roots scratch nil)
                      nil)
                  nil)
              nil)
          nil)
      nil))

(defun %l65i-row-crc-p (lo hi reserved)
  (if (= reserved 0)
      (if (= lo (symbol-value '*l65i-row-lo*))
          (= hi (symbol-value '*l65i-row-hi*))
          nil)
      nil))

(defun %l65i-row-crc-reset ()
  (set-symbol-value '*l65i-row-hi* 255)
  (set-symbol-value '*l65i-row-lo* 255))

(defun %l65i-read-row-fixed (rows)
  (%l65i-row-crc-reset)
  (let ((name (%l65i-name-bytes 16 nil nil)))
    (let ((track (%l65i-next-row))
          (sector (%l65i-next-row))
          (identity (%l65i-read-bytes 4 t nil))
          (dependency-count (%l65i-next-row)))
      (let ((dependencies
              (if (if (numberp dependency-count)
                      (<= dependency-count 8)
                      nil)
                  (%l65i-dependencies 8 dependency-count rows nil)
                  nil))
            (source (%l65i-next-row))
            (artifact-bytes (%l65i-u16 t))
            (bank2 (%l65i-u16 t))
            (images (%l65i-next-row))
            (entries (%l65i-u16 t))
            (resolutions (%l65i-u16 t))
            (roots (%l65i-u16 t))
            (scratch (%l65i-u16 t)))
        (let ((row-crc-lo (%l65i-next-crc))
              (row-crc-hi (%l65i-next-crc))
              (reserved (%l65i-next-crc)))
          (if (if (%l65i-row-base-p
                    name track sector identity dependencies source)
                  (if (%l65i-row-capacity-p
                        artifact-bytes bank2 images entries resolutions
                        roots scratch)
                      (%l65i-row-crc-p row-crc-lo row-crc-hi reserved)
                      nil)
                  nil)
              (list name identity track sector (cdr dependencies)
                    bank2 (cons images 0) entries resolutions roots scratch
                    artifact-bytes)
              nil))))))

(defun %l65i-read-rows (left rows acc)
  (if (> left 0)
      (let ((row (%l65i-read-row-fixed rows)))
        (if row
            (%l65i-read-rows (1- left) rows (cons row acc))
            nil))
      (reverse acc)))

(defun %l65i-zeroes (count)
  (if (> count 0)
      (if (= (%l65i-next-byte) 0) (%l65i-zeroes (1- count)) nil)
      t))

(defun %l65i-header ()
  (let ((magic (%l65i-read-bytes 4 nil nil)))
    (let ((version (%l65i-next-crc))
          (header-bytes (%l65i-next-crc))
          (row-bytes (%l65i-next-crc))
          (max-dependencies (%l65i-next-crc))
          (rows (%l65i-next-crc))
          (records-bytes (%l65i-u16 nil))
          (crc-lo (%l65i-next-crc))
          (crc-hi (%l65i-next-crc))
          (identity (%l65i-read-bytes 4 nil nil)))
      (let ((header-crc-lo (%l65i-next-byte))
            (header-crc-hi (%l65i-next-byte)))
      (if (if (equal magic '(76 54 53 73))
              (if (= version 1)
                  (if (= header-bytes 32)
                      (if (= row-bytes 48)
                          (if (= max-dependencies 8)
                              (if (if (> rows 0) (<= rows 32) nil)
                                  (if (= (+ (car records-bytes)
                                            (* (cdr records-bytes) 256))
                                         (* rows 48))
                                      (if (= header-crc-lo
                                             (symbol-value '*l65i-crc-lo*))
                                          (if (= header-crc-hi
                                                 (symbol-value
                                                   '*l65i-crc-hi*))
                                              (%l65i-zeroes 13)
                                              nil)
                                          nil)
                                      nil)
                                  nil)
                              nil)
                          nil)
                      nil)
                  nil)
              nil)
          (list rows crc-lo crc-hi identity)
          nil)))))

(defun %l65i-entry (codes entry)
  (if (= entry 8)
      nil
      (let ((base (* entry 32)))
        (if (%load-entry-match-p codes base)
            (cons (%load-entry-byte base 3) (%load-entry-byte base 4))
            (%l65i-entry codes (1+ entry))))))

(defun %l65i-find (codes track sector fuel)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((entry (%l65i-entry codes 0)))
            (if entry
                entry
                (let ((next-track (%disk-byte 0))
                      (next-sector (%disk-byte 1)))
                  (if (%disk-directory-link-valid-p
                       track sector next-track next-sector)
                      (if (> next-track 0)
                          (%l65i-find
                            codes next-track next-sector (1- fuel))
                          nil)
                      nil))))
          nil)
      nil))

(defun %l65i-parse ()
  (let ((entry (%l65i-find (%string-codes "l65index") 40 3 64)))
    (if entry
        (if (%l65i-open-sector (car entry) (cdr entry))
            (progn
              (set-symbol-value '*l65i-crc-hi* 255)
              (set-symbol-value '*l65i-crc-lo* 255)
              (let ((header (%l65i-header)))
              (if header
                  (progn
                    (set-symbol-value '*l65i-crc-hi* 255)
                    (set-symbol-value '*l65i-crc-lo* 255)
                    (let ((rows (%l65i-read-rows
                                  (car header) (car header) nil)))
                      (if (if rows
                              (if (= (symbol-value '*l65i-crc-lo*)
                                     (car (cdr header)))
                                  (= (symbol-value '*l65i-crc-hi*)
                                     (car (cdr (cdr header))))
                                  nil)
                              nil)
                          (cons
                            (cons (car (cdr header))
                              (cons (car (cdr (cdr header)))
                                (car (cdr (cdr (cdr header))))))
                            rows)
                          nil)))
                  nil)))
            nil)
        nil)))

; The one native require operation reads one byte from the authenticated C2D
; plane.  Everything below it -- identities, active-universe validation,
; transient fronts and capacity arithmetic -- is Lisp orchestration.
(defun %require-c2d-byte (address)
  (let ((value (%c2d-byte (car address) (cdr address))))
    (if (numberp value) value nil)))

(defun %require-u16-zero-p (value)
  (if (= (car value) 0) (= (cdr value) 0) nil))

(defun %require-u16= (left right)
  (if (= (car left) (car right))
      (= (cdr left) (cdr right))
      nil))

(defun %require-u16<= (left right)
  (if (< (cdr left) (cdr right))
      t
      (if (= (cdr left) (cdr right))
          (<= (car left) (car right))
          nil)))

(defun %require-u16-add-wide (left right)
  (let ((wide (+ (car left) (car right))))
    (let ((lo (mod wide 256)))
      (let ((hi (+ (+ (cdr left) (cdr right))
                   (/ (- wide lo) 256))))
        (if (<= hi 256) (cons lo hi) nil)))))

(defun %require-number-pair (value)
  (let ((lo (mod value 256)))
    (cons lo (/ (- value lo) 256))))

(defun %require-address (base index width)
  (let ((index-lo (mod index 256)))
    (let ((index-hi (/ (- index index-lo) 256)))
      (let ((wide (+ (car base) (* index-lo width))))
        (let ((lo (mod wide 256)))
          (cons lo
            (+ (+ (cdr base) (/ (- wide lo) 256))
               (* index-hi width))))))))

(defun %require-c2d-u16 (address)
  (let ((lo (%require-c2d-byte address)))
    (let ((hi (%require-c2d-byte (%require-address address 1 1))))
      (if (if (numberp lo) (numberp hi) nil)
          (cons lo hi)
          nil))))

(defun %require-u16-value (value)
  (if value (+ (car value) (* (cdr value) 256)) nil))

(defun %require-c2d-bytes= (address values)
  (if values
      (if (= (%require-c2d-byte address) (car values))
          (%require-c2d-bytes=
            (%require-address address 1 1) (cdr values))
          nil)
      t))

(defun %require-c2d-header-shape-p ()
  (%require-c2d-bytes=
    (cons 0 0) '(67 50 68 0 6 48 32 10)))

(defun %require-c2d-header-caps-p ()
  (if (%require-c2d-bytes= (cons 14 0) '(64 0))
      (if (%require-c2d-bytes= (cons 18 0) '(0 8))
          (if (%require-c2d-bytes= (cons 22 0) '(0 16))
              (%require-c2d-bytes= (cons 26 0) '(0 6))
              nil)
          nil)
      nil))

(defun %require-c2d-header-layout-p ()
  (%require-c2d-bytes=
    (cons 28 0)
    '(48 0 48 8 48 88 48 120 48 132 6 0)))

(defun %require-c2d-state-core-p (generation images entries)
  (if generation
      (if (%require-u16-zero-p generation)
          nil
          (if (if (numberp images)
                  (if (>= images 6) (<= images 64) nil)
                  nil)
              (if (numberp entries) (<= entries 2048) nil)
              nil))
      nil))

(defun %require-c2d-state-tail-p (resolutions roots watermark)
  (if (if (numberp resolutions) (<= resolutions 4096) nil)
      (if (if (numberp roots) (<= roots 1536) nil)
          (if (numberp watermark)
              (if (>= watermark 2048) (<= watermark 4096) nil)
              nil)
          nil)
      nil))

(defun %require-c2d-state-values ()
  (let ((generation (%require-c2d-u16 (cons 10 0)))
        (images (%require-u16-value (%require-c2d-u16 (cons 12 0))))
        (entries (%require-u16-value (%require-c2d-u16 (cons 16 0)))))
    (let ((resolutions
            (%require-u16-value (%require-c2d-u16 (cons 20 0))))
          (roots (%require-u16-value (%require-c2d-u16 (cons 24 0))))
          (watermark (%require-u16-value (%require-c2d-u16 (cons 8 0)))))
      (if (%require-c2d-state-core-p generation images entries)
          (if (%require-c2d-state-tail-p resolutions roots watermark)
              (list generation images entries resolutions roots watermark)
              nil)
          nil))))

(defun %require-c2d-state ()
  (if (%require-c2d-header-shape-p)
      (if (%require-c2d-header-caps-p)
          (if (%require-c2d-header-layout-p)
              (%require-c2d-state-values)
              nil)
          nil)
      nil))

(defun %require-row-byte (base field)
  (%require-c2d-byte (%require-address base field 1)))

(defun %require-row-u16 (base field)
  (%require-c2d-u16 (%require-address base field 1)))

(defun %require-row-zeroes-p (base fields)
  (if fields
      (if (= (%require-row-byte base (car fields)) 0)
          (%require-row-zeroes-p base (cdr fields))
          nil)
      t))

(defun %require-image-identity-p (base identity field)
  (if identity
      (if (= (%require-row-byte base field) (car identity))
          (%require-image-identity-p base (cdr identity) (1+ field))
          nil)
      (= field 32)))

(defun %require-images-same-p (left right field)
  (if (< field 32)
      (if (= (%require-row-byte left field)
             (%require-row-byte right field))
          (%require-images-same-p left right (1+ field))
          nil)
      t))

(defun %require-image-duplicate-before-p (slot prior)
  (if (< prior slot)
      (let ((current (%require-address (cons 48 0) slot 32))
            (before (%require-address (cons 48 0) prior 32)))
        (if (%require-images-same-p current before 28)
            t
            (%require-image-duplicate-before-p slot (1+ prior))))
      nil))

(defun %require-index-row-for-image (rows base)
  (if rows
      (if (%require-image-identity-p base (car (cdr (car rows))) 28)
          (car rows)
          (%require-index-row-for-image (cdr rows) base))
      nil))

(defun %require-static-row-p
  (base slot generation code-low)
  (if (= (%require-row-byte base 0) 0)
      (if (%require-row-zeroes-p base '(1 3 20 23 24 25 26 27))
          (if (= (%require-row-byte base 2) slot)
              (if (%require-u16= (%require-row-u16 base 4) generation)
                  (if (%require-u16=
                        (%require-row-u16 base 18) code-low)
                      (let ((size (%require-row-u16 base 21)))
                        (if (%require-u16-zero-p size) nil size))
                      nil)
                  nil)
              nil)
          nil)
      nil))

(defun %require-static-prefix
  (slot generation code-low)
  (if (< slot 6)
      (let ((base (%require-address (cons 48 0) slot 32)))
        (let ((size
                (%require-static-row-p
                  base slot generation code-low)))
          (if size
              (let ((next (%require-u16-add-wide code-low size)))
                (if next
                    (%require-static-prefix
                      (1+ slot) generation next)
                    nil))
              nil)))
      code-low))

(defun %require-persistent-row-size
  (base slot generation code-low)
  (if (= (%require-row-byte base 0) 1)
      (if (%require-row-zeroes-p base '(1 3 20 23 24 25 26 27))
          (if (= (%require-row-byte base 2) (- slot 6))
              (if (%require-u16= (%require-row-u16 base 4) generation)
                  (if (%require-u16=
                        (%require-row-u16 base 18) code-low)
                      (let ((size (%require-row-u16 base 21)))
                        (if (%require-u16-zero-p size) nil size))
                      nil)
                  nil)
              nil)
          nil)
      nil))

(defun %require-persistent-row-p
  (base row size)
  (if (%require-u16= size (nth 5 row))
      (if (%require-image-identity-p base (car (cdr row)) 28)
          t
          nil)
      nil))

(defun %require-active-prefix
  (slot end rows generation code-low)
  (if (< slot end)
      (let ((base (%require-address (cons 48 0) slot 32)))
        (let ((size
                (%require-persistent-row-size
                  base slot generation code-low)))
          (if size
              (let ((row (%require-index-row-for-image rows base)))
                (if (if row
                        (if (%require-image-duplicate-before-p slot 6)
                            nil
                            (%require-persistent-row-p base row size))
                        t)
                    (let ((next
                            (%require-u16-add-wide code-low size)))
                      (if next
                          (%require-active-prefix
                            (1+ slot) end rows generation next)
                          nil))
                    nil))
              nil)))
      code-low))

(defun %require-identity-loaded-at-value (identity slot end generation)
  (if (< slot end)
      (let ((base (%require-address (cons 48 0) slot 32)))
        (if (if (= (%require-row-byte base 0) 1)
                (if (%require-u16=
                      (%require-row-u16 base 4) generation)
                    (%require-image-identity-p
                      base identity 28)
                    nil)
                nil)
            t
            (%require-identity-loaded-at-value
              identity (1+ slot) end generation)))
      nil))

(defun %require-identity-loaded-at (row slot end generation)
  (%require-identity-loaded-at-value
    (car (cdr row)) slot end generation))

(defun %require-identity-loaded-p (row)
  (let ((state (%require-c2d-state)))
    (if state
        (%require-identity-loaded-at
          row 6 (nth 1 state) (nth 0 state))
        nil)))

(defun %require-active-identities-at (slot end generation acc)
  (if (< slot end)
      (let ((base (%require-address (cons 48 0) slot 32)))
        (if (if (= (%require-row-byte base 0) 1)
                (%require-u16= (%require-row-u16 base 4) generation)
                nil)
            (%require-active-identities-at
              (1+ slot) end generation
              (cons
                (list
                  (%require-row-byte base 28)
                  (%require-row-byte base 29)
                  (%require-row-byte base 30)
                  (%require-row-byte base 31))
                acc))
            nil))
      (reverse acc)))

(defun %require-transient-row-counts-p
  (base entries resolutions roots)
  (let ((entry-base (%require-u16-value (%require-row-u16 base 6)))
        (entry-count (%require-u16-value (%require-row-u16 base 8))))
    (let ((res-base (%require-u16-value (%require-row-u16 base 10)))
          (res-count (%require-u16-value (%require-row-u16 base 12))))
      (let ((root-base (%require-u16-value (%require-row-u16 base 14)))
            (root-count (%require-u16-value (%require-row-u16 base 16))))
        (if (= (+ entry-base entry-count) entries)
            (if (= (+ res-base res-count) resolutions)
                (if (= (+ root-base root-count) roots)
                    (list entry-base res-base root-base)
                    nil)
                nil)
            nil)))))

(defun %require-transient-row-p
  (base depth generation entries resolutions roots code-high)
  (if (%require-row-zeroes-p base '(1 3 20 23 24 25 26 27))
      (if (= (%require-row-byte base 2) depth)
          (if (%require-u16= (%require-row-u16 base 4) generation)
              (let ((counts
                      (%require-transient-row-counts-p
                        base entries resolutions roots)))
                (let ((code-base (%require-row-u16 base 18))
                      (code-size (%require-row-u16 base 21)))
                  (if (if counts
                          (if (%require-u16-zero-p code-size)
                              nil
                              (%require-u16=
                                (%require-u16-add-wide
                                  code-base code-size)
                                code-high))
                          nil)
                      (cons code-base counts)
                      nil)))
              nil)
          nil)
      nil))

(defun %require-transient-fronts-at
  (depth generation watermark entries resolutions roots code-high)
  (if (< depth 4)
      (let ((base
              (%require-address (cons 48 0) (- 63 depth) 32)))
        (if (= (%require-row-byte base 0) 2)
            (let ((row
                    (%require-transient-row-p
                      base depth generation entries resolutions
                      roots code-high)))
              (if row
                  (%require-transient-fronts-at
                    (1+ depth) generation watermark
                    (nth 1 row) (nth 2 row) (nth 3 row) (car row))
                  nil))
            (if (= watermark (+ entries 2048))
                (list depth entries resolutions roots code-high)
                nil)))
      (if (= watermark (+ entries 2048))
          (list depth entries resolutions roots code-high)
          nil)))

(defun %require-transient-fronts (state)
  (%require-transient-fronts-at
    0 (nth 0 state) (nth 5 state) 2048 4096 1536 (cons 0 256)))

(defun %require-index-name (rows name ordinal)
  (if rows
      (if (string= (car (car rows)) name)
          ordinal
          (%require-index-name (cdr rows) name (1+ ordinal)))
      nil))

(defun %require-unique-row-p (row rows)
  (if rows
      (if (string= (car row) (car (car rows)))
          nil
          (if (equal (car (cdr row)) (car (cdr (car rows))))
              nil
              (%require-unique-row-p row (cdr rows))))
      t))

(defun %require-unique-index-p (rows)
  (if rows
      (if (%require-unique-row-p (car rows) (cdr rows))
          (%require-unique-index-p (cdr rows))
          nil)
      t))

(defun %require-visit-dependencies (dependencies rows)
  (if dependencies
      (if (%require-visit (car dependencies) rows)
          (%require-visit-dependencies (cdr dependencies) rows)
          nil)
      t))

(defun %require-visit (ordinal rows)
  (if (member ordinal (symbol-value '*require-visited*))
      t
      (if (member ordinal (symbol-value '*require-visiting*))
          nil
          (let ((row (nth ordinal rows)))
            (if row
                (progn
                  (set-symbol-value
                    '*require-visiting*
                    (cons ordinal (symbol-value '*require-visiting*)))
                  (if (%require-visit-dependencies
                        (car (cdr (cdr (cdr (cdr row))))) rows)
                      (progn
                        (set-symbol-value
                          '*require-visiting*
                          (cdr (symbol-value '*require-visiting*)))
                        (set-symbol-value
                          '*require-visited*
                          (cons ordinal (symbol-value '*require-visited*)))
                        (set-symbol-value
                          '*require-order*
                          (cons ordinal (symbol-value '*require-order*)))
                        t)
                      nil))
                nil)))))

(defun %require-u16-add (a b)
  (let ((low (+ (car a) (car b))))
    (let ((high (+ (+ (cdr a) (cdr b)) (if (> low 255) 1 0))))
      (if (> high 255)
          nil
          (cons (mod low 256) high)))))

(defun %require-add-currencies (total values acc)
  (if values
      (let ((next (%require-u16-add (car total) (car values))))
        (if next
            (%require-add-currencies
              (cdr total) (cdr values) (cons next acc))
            nil))
      (reverse acc)))

(defun %require-total-add (total row)
  (if total
      (%require-add-currencies
        total
        (list (nth 5 row) (nth 6 row) (nth 7 row)
              (nth 8 row) (nth 9 row) (nth 10 row))
        nil)
      nil))

(defun %require-plan-totals (order rows total)
  (if order
      (let ((row (nth (car order) rows)))
        (if row
            (if (%require-identity-loaded-p row)
                (%require-plan-totals (cdr order) rows total)
                (%require-plan-totals
                  (cdr order) rows (%require-total-add total row)))
            nil))
      total))

(defun %require-space-p (current delta limit)
  (let ((next
          (%require-u16-add-wide
            (%require-number-pair current) delta)))
    (if next
        (%require-u16<= next (%require-number-pair limit))
        nil)))

(defun %require-directory-capacities-p (total state fronts)
  (if (%require-space-p
        (nth 1 state) (nth 1 total) (- 64 (nth 0 fronts)))
      (if (%require-space-p
            (nth 2 state) (nth 2 total) (nth 1 fronts))
          (if (%require-space-p
                (nth 3 state) (nth 3 total) (nth 2 fronts))
              (%require-space-p
                (nth 4 state) (nth 4 total) (nth 3 fronts))
              nil)
          nil)
      nil))

(defun %require-capacities-p (total state fronts code-low)
  (let ((bank2 (%require-u16-add-wide code-low (nth 0 total))))
    (if (if bank2 (%require-u16<= bank2 (nth 4 fronts)) nil)
        (if (%require-directory-capacities-p total state fronts)
            (%require-u16<= (nth 5 total) (cons 208 56))
            nil)
        nil)))

(defun %require-load-plan (order rows)
  (if order
      (let ((row (nth (car order) rows)))
        (if row
            (if (%require-identity-loaded-p row)
                (%require-load-plan (cdr order) rows)
                (if (%disk-load-lib (nth 2 row) (nth 3 row))
                    (if (%require-identity-loaded-p row)
                        (%require-load-plan (cdr order) rows)
                        nil)
                    nil))
            nil))
      t))

(defun %require-zero-totals ()
  (list (cons 0 0) (cons 0 0) (cons 0 0)
        (cons 0 0) (cons 0 0) (cons 0 0)))

(defun %require-run-plan
  (ordinal rows lock state fronts code-low)
  (set-symbol-value '*require-visiting* nil)
  (set-symbol-value '*require-visited* nil)
  (set-symbol-value '*require-order* nil)
  (if (%require-visit ordinal rows)
      (let ((order (reverse (symbol-value '*require-order*))))
        (let ((totals
                (%require-plan-totals order rows (%require-zero-totals))))
          (if (if totals
                  (%require-capacities-p
                    totals state fronts code-low)
                  nil)
              (progn
                (if (symbol-value '*require-index-lock*)
                    t
                    (set-symbol-value '*require-index-lock* lock))
                (%require-load-plan order rows))
              nil)))
      nil))

(defun %require-world (rows)
  (let ((state (%require-c2d-state)))
    (if state
        (let ((static-low
                (%require-static-prefix
                  0 (nth 0 state) (cons 0 0))))
          (let ((code-low
                  (if static-low
                      (%require-active-prefix
                        6 (nth 1 state) rows (nth 0 state) static-low)
                      nil))
                (fronts (%require-transient-fronts state)))
            (if (if code-low fronts nil)
                (list state code-low fronts)
                nil)))
        nil)))

(defun %require-fast-note (library row lock rows)
  (let ((world (%require-world rows)))
    (if world
        (let ((state (nth 0 world))
              (identity (car (cdr row))))
          (let ((identities
                  (%require-active-identities-at
                    6 (nth 1 state) (nth 0 state) nil)))
            (if (if identities
                    (%require-identity-loaded-at-value
                      identity 6 (nth 1 state) (nth 0 state))
                    nil)
                (progn
                  (set-symbol-value
                    '*require-fast*
                    (list library lock identity state identities))
                  t)
                nil)))
        nil)))

(defun %require-fast-loaded-p (library)
  (let ((cache (symbol-value '*require-fast*)))
    (if cache
        (if (equal library (nth 0 cache))
            (if (if (symbol-value '*require-index-lock*)
                    (equal
                      (symbol-value '*require-index-lock*)
                      (nth 1 cache))
                    nil)
                (let ((state (%require-c2d-state-values)))
                  (if (equal state (nth 3 cache))
                      (equal
                        (%require-active-identities-at
                          6 (nth 1 state) (nth 0 state) nil)
                        (nth 4 cache))
                      nil))
                nil)
            nil)
        nil)))

(defun %require-resolve (library index)
  (let ((lock (car index))
        (rows (cdr index)))
    (if (if (%require-unique-index-p rows)
            (if (symbol-value '*require-index-lock*)
                (equal lock (symbol-value '*require-index-lock*))
                t)
            nil)
        (let ((world (%require-world rows))
              (ordinal (%require-index-name
                         rows (symbol-name library) 0)))
          (if (if world ordinal nil)
              (if (%require-run-plan
                    ordinal rows lock (nth 0 world)
                    (nth 2 world) (nth 1 world))
                  (%require-fast-note
                    library (nth ordinal rows) lock rows)
                  nil)
              nil))
        nil)))

(defun require (library)
  (if (symbolp library)
      (if (%require-fast-loaded-p library)
          t
          (let ((index (%l65i-parse)))
            (if index (%require-resolve library index) nil)))
      nil))
