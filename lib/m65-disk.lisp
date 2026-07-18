;; Compact D81 copy-on-write persistence prototype.
;;
;; Public status ABI:
;;   0 ok, 1 bad-name, 2 duplicate-name, 3 too-large, 4 no-space,
;;   5 directory-full, 6 read-invalid, 7 write-verify-failed,
;;   8 needs-remount, 9 committed-with-leak, 10 product-media-read-only,
;;   11 retired wrong-work-media tombstone (never emitted by this version),
;;   12 media-changed-during-transaction (terminal; explicit restart only).
;;
;; The new chain is selected from exactly one BAM sector.  The visible commit
;; point is the directory-sector write; the old chain is released afterwards.

;; Container-private state reuses value cells of public function symbols.
;; Lisp-2 keeps those cells independent from the function bindings, avoiding
;; private state names and additional directory entries.

(defun %m65d-set (code latch)
  ;; Status 11 is retired and never emitted.  In the dense live status range,
  ;; 9 + 12 = 21 is therefore the unique overwrite pair that must be blocked:
  ;; a post-commit leak warning may not erase terminal media-change status.
  (if (= (+ code (m65d-status)) 21)
      12
      (progn
        (set-symbol-value (quote m65d-status) code)
        (if latch (set-symbol-value (quote m65d-remount) t) nil)
        code)))

;; In predicate failure branches, (not (%m65d-set ...)) both records the
;; non-NIL status code and returns NIL; this is the compact form of SET/DROP/NIL.

(defun %m65d-latched-p ()
  (eq (if (boundp (quote m65d-remount)) (symbol-value (quote m65d-remount)) t) t))

(defun m65d-status ()
  (if (boundp (quote m65d-status)) (symbol-value (quote m65d-status)) 0))

;; R3 single-drive media identity.  The 1581 header lives at T40/S0;
;; name bytes are +4..+19 and the two-byte disk id is +22/+23.  Passing base
;; -1 reuses the canonical 16-byte directory-name matcher at header offset 4.
;; Any structurally valid 1581 medium is writable except the product disk.
;; Product recognition is deliberately conjunctive: L65SYS,65 plus the L65B
;; boot-structure marker at header bytes 29..32.  The product packer emits that
;; marker only on a medium whose mandatory boot entries were verified.  This
;; keeps the device-side denylist cheap while binding it to packer-verified boot
;; structure.  Mount-level WP is an independent second line of defense only
;; when the active hardware profile provides it.  Stock-core SD-backed D81
;; images have no physical medium and no Freezer read-only attach control;
;; their product protection therefore rests on this denylist plus the guarded
;; transaction path, never on a synthetic WP claim.
;; Result: 0 = writable, 10 = product identity, 6 = invalid/unreadable; status
;; 11 is never emitted.
(defun %m65d-media-detail (index acc)
  (if (= index 18)
      (if (= (%disk-byte 29) 76)
          (if (= (%disk-byte 30) 54)
              (if (= (%disk-byte 31) 53) (= (%disk-byte 32) 66) nil)
              nil)
          nil)
      (if (< index 0)
          acc
          (%m65d-media-detail
           (- index 1)
           (cons (%disk-byte (+ 4 index))
                 acc)))))

(defun %m65d-media-kind ()
  (if (if (%disk-read-sector 40 0)
          (if (= (%disk-byte 2) 68)
              (if (= (%disk-byte 25) 51) (= (%disk-byte 26) 68) nil)
              nil)
          nil)
      (if (if (if (= (%disk-byte 22) 54) (= (%disk-byte 23) 53) nil)
              (if (%load-name-match-at (string->list "L65SYS") -1 0)
                  (%m65d-media-detail 18 nil)
                  nil)
              nil)
          10
          0)
      6))

;; Bind the complete canonical 16-byte 1581 name plus both exact ID bytes, not
;; a checksum.  The five-byte D68B..D68F token has one owner: the native
;; guarded-write path captures it at transaction start and checks it at every
;; F011 boundary.  Keeping a second Lisp list copy would duplicate the same
;; truth and consume Directory/EXT capacity without closing another window.
;; The canonical matcher normalizes only the 1581 high bit and A0 padding; all
;; name positions still participate.

;; With NIL track this is the identity check before sector preparation.  It
;; intentionally reads the media header first; the caller then reloads or
;; clears its target scratch sector.  With a track it is the physical write
;; boundary and consumes the native D68B..D68F guard status.  One function owns
;; both branches so the safety fix adds no Directory entry.
(defun %m65d-before-write (track sector)
  (if track
      (let ((status (%disk-write-sector track sector 1)))
        (if (= status 0) t (not (%m65d-set status t))))
      (let ((txn (symbol-value (quote m65d-save))))
        (if (if (consp txn)
                (eq (car txn) (symbol-value (quote m65d-remount)))
                nil)
            (let ((kind (%m65d-media-kind)))
              (if (= kind 0)
                  (if (if (= (car (cdr txn)) (%disk-byte 22))
                          (if (= (car (cdr (cdr txn))) (%disk-byte 23))
                              (%load-name-match-at (cdr (cdr (cdr txn))) -1 0)
                              nil)
                          nil)
                      t
                      (not (%m65d-set 12 t)))
                  (not (%m65d-set 12 t))))
            (not (%m65d-set 12 t))))))

(defun %m65d-valid-ts-p (track sector)
  (if (< track 1)
      nil
      (if (> track 80)
          nil
          (if (= track 40) nil (if (< sector 0) nil (< sector 40))))))

(defun %m65d-bam-sector (track)
  (if (< track 41) 1 2))

(defun %m65d-bam-base (track)
  (+ 16 (* 6 (if (< track 41) (- track 1) (- track 41)))))

(defun %m65d-mask (sector)
  (let ((r (mod sector 8)))
    (if (= r 0) 1
        (if (= r 1) 2
            (if (= r 2) 4
                (if (= r 3) 8
                    (if (= r 4) 16
                        (if (= r 5) 32
                            (if (= r 6) 64 128)))))))))

(defun %m65d-bitmap-off (track sector)
  (+ (+ (%m65d-bam-base track) 1)
     (if (< sector 8) 0
         (if (< sector 16) 1
             (if (< sector 24) 2 (if (< sector 32) 3 4))))))

(defun %m65d-bit-free-p (track sector)
  (let ((mask (%m65d-mask sector)))
    (>= (mod (%disk-byte (%m65d-bitmap-off track sector))
             (+ mask mask))
        mask)))

(defun %m65d-bam-header-ok-p (bam)
  (if (= bam 1)
      (if (= (%disk-byte 0) 40) (= (%disk-byte 1) 2) nil)
      (if (= (%disk-byte 0) 0) (= (%disk-byte 1) 255) nil)))

(defun %m65d-count-free (track sector count)
  (if (= sector 40)
      count
      (%m65d-count-free
       track
       (+ sector 1)
       (if (%m65d-bit-free-p track sector) (+ count 1) count))))

(defun %m65d-track-ok-p (track)
  (= (%disk-byte (%m65d-bam-base track)) (%m65d-count-free track 0 0)))

(defun %m65d-bam-validate-tracks (track last)
  (if (> track last)
      t
      (if (= track 40)
          (%m65d-bam-validate-tracks 41 last)
          (if (%m65d-track-ok-p track)
              (%m65d-bam-validate-tracks (+ track 1) last)
              nil))))

(defun %m65d-name-chars-ok-p (name index len)
  (if (= index len)
      t
      (let ((code (string-ref name index)))
        (if (< code 33)
            nil
            (if (> code 126)
                nil
                (if (= code 34)
                    nil
                    (if (= code 42)
                        nil
                        (if (= code 47)
                            nil
                            (if (= code 58)
                                nil
                                (if (= code 63)
                                    nil
                                    (if (= code 92)
                                        nil
                                        (%m65d-name-chars-ok-p
                                         name (+ index 1) len))))))))))))

(defun %m65d-name-ok-p (name)
  (if (stringp name)
      (let ((len (string-length name)))
        (if (< len 1) nil (if (> len 16) nil (%m65d-name-chars-ok-p name 0 len))))
      nil))

(defun %m65d-entry-valid-p (base)
  (let ((kind (mod (%load-entry-byte base 2) 8))
        (track (%load-entry-byte base 3))
        (sector (%load-entry-byte base 4))
        (blocks (+ (%load-entry-byte base 30)
                   (* (%load-entry-byte base 31) 256))))
    (if (< kind 1)
        nil
        (if (> kind 4)
            nil
            (if (%m65d-valid-ts-p track sector)
                (if (< blocks 1) nil (<= blocks 3160))
                nil)))))

(defun %m65d-dir-entries (codes entry track sector free)
  (if (= entry 8)
      free
      (let ((base (* entry 32)))
        (if (%load-entry-used-p base)
            (if (%m65d-entry-valid-p base)
                (if (%load-entry-match-p codes base)
                    (if (if free (= (car free) 1) nil)
                        (not (%m65d-set 6 nil))
                        (%m65d-dir-entries
                         codes (+ entry 1) track sector
                         (list 1 track sector entry
                               (%load-entry-byte base 3)
                               (%load-entry-byte base 4)
                               (%load-entry-byte base 30)
                               (%load-entry-byte base 31))))
                    (%m65d-dir-entries codes (+ entry 1) track sector free))
                (not (%m65d-set 6 nil)))
            (%m65d-dir-entries
             codes (+ entry 1) track sector
             (if free free (list 0 track sector entry)))))))

(defun %m65d-dir-scan (codes track sector fuel free)
  (if (= fuel 0)
      (not (%m65d-set 6 nil))
      (if (%disk-read-sector track sector)
          (let ((found (%m65d-dir-entries
                        codes
                        ;; T40/S0 is the 1581 header and only links to the
                        ;; first directory sector.  None of its eight
                        ;; 32-byte regions is a directory slot.
                        (if (if (= track 40) (= sector 0) nil) 8 0)
                        track sector free)))
            (if (= (m65d-status) 6)
                nil
                (let ((next-track (%disk-byte 0))
                      (next-sector (%disk-byte 1)))
                  (if (= next-track 0)
                      found
                      (if (= next-track 40)
                          (if (< next-sector 40)
                              (if (= next-sector sector)
                                  (not (%m65d-set 6 nil))
                                  (%m65d-dir-scan
                                   codes 40 next-sector (- fuel 1) found))
                              (not (%m65d-set 6 nil)))
                          (not (%m65d-set 6 nil)))))))
          (not (%m65d-set 6 nil)))))

(defun %m65d-find-dir (name)
  (%m65d-dir-scan (string->list name) 40 0 40 nil))

(defun %m65d-bam-find (track last sector need acc)
  (if (= need 0)
      (reverse acc)
      (if (> track last)
          nil
          (if (= track 40)
              (%m65d-bam-find 41 last 0 need acc)
              (if (= sector 40)
                  (%m65d-bam-find (+ track 1) last 0 need acc)
                  (if (if (= sector 0) (not (%m65d-track-ok-p track)) nil)
                      (not (%m65d-set 6 nil))
                      (%m65d-bam-find
                       track last (+ sector 1)
                       (if (%m65d-bit-free-p track sector) (- need 1) need)
                       (if (%m65d-bit-free-p track sector)
                           (cons (cons track sector) acc)
                           acc))))))))

(defun %m65d-find-new-chain (blocks)
  (if (%disk-read-sector 40 1)
      (if (%m65d-bam-header-ok-p 1)
          (let ((chain (%m65d-bam-find 1 39 0 blocks nil)))
            (if chain
                chain
                (if (= (m65d-status) 6)
                    nil
                    (if (%disk-read-sector 40 2)
                        (if (%m65d-bam-header-ok-p 2)
                            (%m65d-bam-find 41 80 0 blocks nil)
                            (not (%m65d-set 6 nil)))
                        (not (%m65d-set 6 nil))))))
          (not (%m65d-set 6 nil)))
      (not (%m65d-set 6 nil))))

(defun %m65d-pair-member-p (track sector pairs)
  (if pairs
      (if (= track (car (car pairs)))
          (if (= sector (cdr (car pairs)))
              t
              (%m65d-pair-member-p track sector (cdr pairs)))
          (%m65d-pair-member-p track sector (cdr pairs)))
      nil))

(defun %m65d-read-old-chain (track sector fuel acc)
  (if (= fuel 0)
      (not (%m65d-set 6 nil))
      (if (%m65d-valid-ts-p track sector)
          (if (%m65d-pair-member-p track sector acc)
              (not (%m65d-set 6 nil))
              (if (%disk-read-sector track sector)
                  (let ((next-track (%disk-byte 0))
                        (next-sector (%disk-byte 1))
                        (next-acc (cons (cons track sector) acc)))
                    (if (= next-track 0)
                        (if (< next-sector 1)
                            (not (%m65d-set 6 nil))
                            (if (> next-sector 255)
                                (not (%m65d-set 6 nil))
                                (reverse next-acc)))
                        (%m65d-read-old-chain next-track next-sector
                                              (- fuel 1) next-acc)))
                  (not (%m65d-set 6 nil))))
          (not (%m65d-set 6 nil)))))

(defun %m65d-chain-state (chain bam free seen)
  (if chain
      (let ((pair (car chain)))
        (if (= (%m65d-bam-sector (car pair)) bam)
            (if (%m65d-track-ok-p (car pair))
                (if (eq (%m65d-bit-free-p (car pair) (cdr pair)) free)
                    (%m65d-chain-state (cdr chain) bam free 1)
                    nil)
                nil)
            (%m65d-chain-state (cdr chain) bam free seen)))
      seen))

(defun %m65d-check-old-half (chain bam)
  (if (%disk-read-sector 40 bam)
      (if (%m65d-bam-header-ok-p bam)
          (if (%m65d-chain-state chain bam nil 0) t nil)
          nil)
      nil))

(defun %m65d-clear ()
  (dotimes (i 256 t) (%disk-poke i 0)))

(defun %m65d-copy (src pos count buffer)
  (dotimes (i count t)
    (%disk-poke (+ i 2)
                (if buffer
                    (%fasl-stage-get (+ pos i))
                    (string-ref src (+ pos i))))))

(defun %m65d-write-chain (src len chain pos buffer)
  (if chain
      (let ((pair (car chain))
            (rest (cdr chain)))
        (let ((count (if rest 254 (- len pos))))
          (if (%m65d-before-write nil nil)
              (progn
                (%m65d-clear)
                (if rest
                    (progn
                      (%disk-poke 0 (car (car rest)))
                      (%disk-poke 1 (cdr (car rest))))
                    (progn (%disk-poke 0 0) (%disk-poke 1 (+ count 1))))
                (%m65d-copy src pos count buffer)
                (if (%m65d-before-write (car pair) (cdr pair))
                    (%m65d-write-chain src len rest (+ pos count) buffer)
                    nil))
              nil)))
      t))

(defun %m65d-bam-change (chain bam delta)
  (if chain
      (let ((pair (car chain)))
        (if (= (%m65d-bam-sector (car pair)) bam)
            (let ((base (%m65d-bam-base (car pair)))
                  (off (%m65d-bitmap-off (car pair) (cdr pair)))
                  (mask (%m65d-mask (cdr pair))))
              (progn
                (%disk-poke base (+ (%disk-byte base) delta))
                (%disk-poke off (+ (%disk-byte off) (* delta mask)))
                (%m65d-bam-change (cdr chain) bam delta)))
            (%m65d-bam-change (cdr chain) bam delta)))
      t))

(defun %m65d-claim-new (chain)
  (let ((bam (%m65d-bam-sector (car (car chain)))))
    (if (if (%m65d-before-write nil nil) (%disk-read-sector 40 bam) nil)
        (if (%m65d-bam-header-ok-p bam)
            (if (%m65d-chain-state chain bam t 0)
                (progn
                  (%m65d-bam-change chain bam -1)
                  (if (%m65d-before-write 40 bam)
                      t
                      nil))
                (not (%m65d-set 6 t)))
            (not (%m65d-set 6 t)))
        (not (%m65d-set 6 t)))))

(defun %m65d-release-half (chain bam)
  (if (if (%m65d-before-write nil nil) (%disk-read-sector 40 bam) nil)
      (if (%m65d-bam-header-ok-p bam)
          (let ((state (%m65d-chain-state chain bam nil 0)))
            (if state
                (if (= state 0)
                    t
                    (progn
                      (%m65d-bam-change chain bam 1)
                      (%m65d-before-write 40 bam)))
                nil))
          nil)
      nil))

(defun %m65d-release-old (chain)
  (if (%m65d-release-half chain 1)
      (%m65d-release-half chain 2)
      nil))

(defun %m65d-dir-write-name (base name len index)
  (if (= index 16)
      t
      (progn
        (%disk-poke (+ base (+ 5 index))
                    (if (< index len)
                        (%load-fold-code (string-ref name index))
                        160))
        (%m65d-dir-write-name base name len (+ index 1)))))

(defun %m65d-dir-target-ok-p (record base name)
  (if (= (car record) 1)
      (if (%load-entry-used-p base)
          (if (%load-entry-match-p (string->list name) base)
              (if (= (%load-entry-byte base 3)
                     (car (cdr (cdr (cdr (cdr record))))))
                  (= (%load-entry-byte base 4)
                     (car (cdr (cdr (cdr (cdr (cdr record)))))))
                  nil)
              nil)
          nil)
      (not (%load-entry-used-p base))))

(defun %m65d-dir-fill (base name first blocks)
  (progn
    (dotimes (i 32 nil) (%disk-poke (+ base i) 0))
    (%disk-poke (+ base 2) 129)
    (%disk-poke (+ base 3) (car first))
    (%disk-poke (+ base 4) (cdr first))
    (%m65d-dir-write-name base name (string-length name) 0)
    (%disk-poke (+ base 30) blocks)
    (%disk-poke (+ base 31) 0)
    t))

(defun %m65d-commit-dir (record name first blocks)
  (let ((track (car (cdr record)))
        (sector (car (cdr (cdr record))))
        (entry (car (cdr (cdr (cdr record)))))
        (replace (car record)))
    (if (if (%m65d-before-write nil nil) (%disk-read-sector track sector) nil)
        (let ((base (* entry 32)))
          (if (%m65d-dir-target-ok-p record base name)
              (progn
                (%m65d-dir-fill base name first blocks)
                (if (%m65d-before-write track sector)
                    t
                    nil))
              (not (%m65d-set 6 t))))
        (not (%m65d-set 6 t)))))

(defun %m65d-blocks-for (len blocks)
  (if (<= len 254)
      (+ blocks 1)
      (%m65d-blocks-for (- len 254) (+ blocks 1))))

(defun %m65d-old-validated (old blocks)
  (if old
      (if (= (length old) blocks)
          (if (%m65d-check-old-half old 1)
              (if (%m65d-check-old-half old 2)
                  old
                  (not (%m65d-set 6 nil)))
              (not (%m65d-set 6 nil)))
          (not (%m65d-set 6 nil)))
      nil))

(defun %m65d-old-plan (record)
  (if (= (car record) 1)
      (let ((blocks (car (cdr (cdr (cdr (cdr (cdr (cdr record))))))))
            (high (car (cdr (cdr (cdr (cdr (cdr (cdr (cdr record))))))))))
        (if (if (= high 0) (if (> blocks 0) (<= blocks 33) nil) nil)
            (let ((old (%m65d-read-old-chain
                        (car (cdr (cdr (cdr (cdr record)))))
                        (car (cdr (cdr (cdr (cdr (cdr record))))))
                        33 nil)))
              (%m65d-old-validated old blocks))
            (not (%m65d-set 6 nil))))
      t))

(defun %m65d-write-plan (record name src len blocks old buffer)
  (let ((chain (%m65d-find-new-chain blocks)))
    (if chain
        (if (%m65d-write-chain src len chain 0 buffer)
            (if (%m65d-claim-new chain)
                (if (%m65d-commit-dir record name (car chain) blocks)
                    (if (if (= (car record) 1)
                            (%m65d-release-old old)
                            t)
                        (%m65d-set 0 nil)
                        (%m65d-set 9 t))
                    (m65d-status))
                (m65d-status))
            (m65d-status))
        (if (= (m65d-status) 6) 6 (%m65d-set 4 nil)))))

(defun %m65d-run-record (record name src len new-only buffer)
  (if (if new-only (= (car record) 1) nil)
      (%m65d-set 2 nil)
      (let ((blocks (%m65d-blocks-for len 0))
            (old (%m65d-old-plan record)))
        (if (if (= (car record) 1) (not old) nil)
            (m65d-status)
            (%m65d-write-plan record name src len blocks old buffer)))))

(defun %m65d-run-source (name src new-only buffer)
  (let ((len (if buffer (%buffer-alloc 3 src) (string-length src))))
    (if (< len 1)
        (%m65d-set 3 nil)
        (if (> len 8192)
            (%m65d-set 3 nil)
            (let ((record (%m65d-find-dir name)))
              (if record
                  (%m65d-run-record record name src len new-only buffer)
                  (if (= (m65d-status) 6) 6 (%m65d-set 5 nil))))))))

(defun %m65d-run-authorized (name src new-only)
  (if (%m65d-name-ok-p name)
      (let ((buffer (not (stringp src))))
        (if (if buffer (%buffer-read 0 src) t)
            (%m65d-run-source name src new-only buffer)
            (%m65d-set 3 nil)))
      (%m65d-set 1 nil)))

(defun %m65d-run-unlatched (name src new-only)
  (progn
    (%m65d-set 0 nil)
    (let ((kind (%m65d-media-kind)))
      (if (= kind 0)
          (progn
            (%disk-write-sector)
            (set-symbol-value
             (quote m65d-save)
             (cons (symbol-value (quote m65d-remount))
                   (cons (%disk-byte 22)
                         (cons (%disk-byte 23)
                               (%m65d-media-detail 15 nil)))))
            ;; A Freezer swap can interpose during read-only planning after
            ;; token capture.  The one-argument capability reclassifies only
            ;; read-invalid with a changed native token from 6 to terminal 12;
            ;; genuine read failures on the bound medium remain 6.
            ;; The classifier result is the single status truth: publish the
            ;; exact value returned to the caller through m65d-status as well.
            ;; Planning still precedes every write, so status 12 is terminal
            ;; for this call but does not require the partial-write latch.
            (%m65d-set
             (%disk-write-sector (%m65d-run-authorized name src new-only))
             nil))
          (%m65d-set kind t)))))

(defun %m65d-run (name src new-only)
  (if (%m65d-latched-p)
      (let ((kind (%m65d-media-kind)))
        (if (= kind 0)
            (%m65d-set 8 nil)
            (%m65d-set kind t)))
      (%m65d-run-unlatched name src new-only)))

(defun m65d-save (name src)
  (%m65d-run name src nil))

(defun m65d-save-new (name src)
  (if (stringp src) (%m65d-run name src t) (%m65d-set 3 nil)))

(defun %m65d-remount-finish ()
  (if (%m65d-dir-scan (list 0) 40 0 40 nil)
      (progn
        (set-symbol-value (quote m65d-remount) (cons nil nil))
        (%m65d-set 0 nil))
      (%m65d-set 6 nil)))

(defun %m65d-remount-work ()
  (if (if (%disk-read-sector 40 1)
          (if (%m65d-bam-header-ok-p 1)
              (if (%m65d-bam-validate-tracks 1 39)
                  (if (%disk-read-sector 40 2)
                      (if (%m65d-bam-header-ok-p 2)
                          (%m65d-bam-validate-tracks 41 80)
                          nil)
                      nil)
                  nil)
              nil)
          nil)
      (%m65d-remount-finish)
      (%m65d-set 6 nil)))

(defun m65d-remount ()
  (let ((kind (%m65d-media-kind)))
    (if (= kind 0)
        (%m65d-remount-work)
        (%m65d-set kind t))))
