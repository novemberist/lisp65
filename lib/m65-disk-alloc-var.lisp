;; M7 prototype: create a new source file with a variable-length sector chain.
;;
;; Still intentionally narrow:
;; - directory entries are selected in T40/S4 only
;; - data sectors are selected from the BAM over tracks 1..80, skipping T40
;; - payload length is capped at four data sectors for this HW slice

(defun %m65dv-clear ()
  (dotimes (i 256 t) (%disk-poke i 0)))

(defun %m65dv-copy (src src0 dst0 n)
  (dotimes (i n t)
    (%disk-poke (+ dst0 i) (string-ref src (+ src0 i)))))

(defun %m65dv-mask (sector)
  (let ((r (mod sector 8)))
    (if (= r 0) 1
        (if (= r 1) 2
            (if (= r 2) 4
                (if (= r 3) 8
                    (if (= r 4) 16
                        (if (= r 5) 32
                            (if (= r 6) 64 128)))))))))

(defun %m65dv-sector-group (sector)
  (if (< sector 8)
      0
      (if (< sector 16)
          1
          (if (< sector 24)
              2
              (if (< sector 32) 3 4)))))

(defun %m65dv-bam-sector (track)
  (if (<= track 40) 1 2))

(defun %m65dv-bam-index (track)
  (if (<= track 40) (- track 1) (- track 41)))

(defun %m65dv-bam-base (track)
  (+ 16 (* 6 (%m65dv-bam-index track))))

(defun %m65dv-bitmap-offset (track sector)
  (+ (+ (%m65dv-bam-base track) 1) (%m65dv-sector-group sector)))

(defun %m65dv-bit-set-p (byte mask)
  (>= (mod byte (+ mask mask)) mask))

(defun %m65dv-sector-free-p (track sector)
  (%m65dv-bit-set-p (%disk-byte (%m65dv-bitmap-offset track sector))
                    (%m65dv-mask sector)))

(defun %m65dv-bam-ok (track)
  (if (<= track 40)
      (if (= (%disk-byte 0) 40)
          (if (= (%disk-byte 1) 2) t nil)
          nil)
      (if (= (%disk-byte 0) 0)
          (if (= (%disk-byte 1) 255) t nil)
          nil)))

(defun %m65dv-rev2 (xs acc)
  (if xs
      (%m65dv-rev2 (cdr xs) (cons (car xs) acc))
      acc))

(defun %m65dv-rev (xs)
  (%m65dv-rev2 xs nil))

(defun %m65dv-find-sector (track sector need acc)
  (if (= need 0)
      (%m65dv-rev acc)
      (if (> sector 39)
          (%m65dv-find-track (+ track 1) need acc)
          (if (%m65dv-sector-free-p track sector)
              (%m65dv-find-sector track (+ sector 1) (- need 1)
                                  (cons (cons track sector) acc))
              (%m65dv-find-sector track (+ sector 1) need acc)))))

(defun %m65dv-find-track (track need acc)
  (if (= need 0)
      (%m65dv-rev acc)
      (if (> track 80)
          nil
          (if (= track 40)
              (%m65dv-find-track 41 need acc)
              (if (%disk-read-sector 40 (%m65dv-bam-sector track))
                  (if (%m65dv-bam-ok track)
                      (%m65dv-find-sector track 0 need acc)
                      nil)
                  nil)))))

(defun %m65dv-find-chain (need)
  (%m65dv-find-track 1 need nil))

(defun %m65dv-claim-one (track sector)
  (let ((off (%m65dv-bitmap-offset track sector))
        (mask (%m65dv-mask sector)))
    (if (%m65dv-bit-set-p (%disk-byte off) mask)
        (progn
          (%disk-poke off (- (%disk-byte off) mask))
          t)
        nil)))

(defun %m65dv-claim-pair (pair)
  (let ((track (car pair))
        (sector (cdr pair)))
    (if (%disk-read-sector 40 (%m65dv-bam-sector track))
        (if (%m65dv-bam-ok track)
            (if (%m65dv-sector-free-p track sector)
                (let ((base (%m65dv-bam-base track)))
                  (if (> (%disk-byte base) 0)
                      (progn
                        (%disk-poke base (- (%disk-byte base) 1))
                        (%m65dv-claim-one track sector)
                        (%disk-write-sector 40 (%m65dv-bam-sector track)))
                      nil))
                nil)
            nil)
        nil)))

(defun %m65dv-claim-chain (chain)
  (if chain
      (if (%m65dv-claim-pair (car chain))
          (%m65dv-claim-chain (cdr chain))
          nil)
      t))

(defun %m65dv-fold-ascii (code)
  (if (>= code 97)
      (if (<= code 122) (- code 32) code)
      code))

(defun %m65dv-fold-dir (code)
  (%m65dv-fold-ascii (if (> code 127) (- code 128) code)))

(defun %m65dv-name-code (name len i)
  (if (< i len)
      (%m65dv-fold-ascii (string-ref name i))
      32))

(defun %m65dv-name-ok-p (len)
  (if (< len 1) nil (<= len 16)))

(defun %m65dv-name-match-at (name len base i)
  (if (= i 16)
      t
      (if (= (%m65dv-fold-dir (%disk-byte (+ base (+ 5 i))))
             (%m65dv-name-code name len i))
          (%m65dv-name-match-at name len base (+ i 1))
          nil)))

(defun %m65dv-dir-scan (name len entry free)
  (if (= entry 8)
      free
      (let ((base (* entry 32)))
        (if (= (%disk-byte (+ base 2)) 0)
            (%m65dv-dir-scan name len (+ entry 1)
                             (if (< free 0) entry free))
            (if (%m65dv-name-match-at name len base 0)
                -2
                (%m65dv-dir-scan name len (+ entry 1) free))))))

(defun %m65dv-dir-slot (name len)
  (if (%disk-read-sector 40 4)
      (if (= (%disk-byte 0) 0)
          (if (= (%disk-byte 1) 255)
              (let ((slot (%m65dv-dir-scan name len 0 -1)))
                (if (< slot 0) nil slot))
              nil)
          nil)
      nil))

(defun %m65dv-dir-clear (base)
  (dotimes (i 32 t) (%disk-poke (+ base i) 0)))

(defun %m65dv-dir-name (base name len)
  (dotimes (i 16 t)
    (%disk-poke (+ base (+ 5 i))
                (if (< i len)
                    (%m65dv-fold-ascii (string-ref name i))
                    160))))

(defun %m65dv-write-dir (name len first blocks slot)
  (if (%disk-read-sector 40 4)
      (let ((base (* slot 32)))
        (if (= (%disk-byte (+ base 2)) 0)
            (progn
              (%m65dv-dir-clear base)
              (%disk-poke (+ base 2) 129)
              (%disk-poke (+ base 3) (car first))
              (%disk-poke (+ base 4) (cdr first))
              (%m65dv-dir-name base name len)
              (%disk-poke (+ base 30) blocks)
              (%disk-poke (+ base 31) 0)
              (%disk-write-sector 40 4))
            nil))
      nil))

(defun %m65dv-blocks-for (len acc)
  (if (<= len 0)
      acc
      (%m65dv-blocks-for (- len 254) (+ acc 1))))

(defun %m65dv-write-link (src pos track sector next)
  (progn
    (%m65dv-clear)
    (%disk-poke 0 (car next))
    (%disk-poke 1 (cdr next))
    (%m65dv-copy src pos 2 254)
    (%disk-write-sector track sector)))

(defun %m65dv-write-tail (src len pos track sector)
  (let ((tail (- len pos)))
    (progn
      (%m65dv-clear)
      (%disk-poke 0 0)
      (%disk-poke 1 (+ tail 1))
      (%m65dv-copy src pos 2 tail)
      (%disk-write-sector track sector))))

(defun %m65dv-write-chain (src len chain pos)
  (if chain
      (let ((pair (car chain))
            (rest (cdr chain)))
        (let ((track (car pair))
              (sector (cdr pair)))
          (if rest
              (if (%m65dv-write-link src pos track sector (car rest))
                  (%m65dv-write-chain src len rest (+ pos 254))
                  nil)
              (%m65dv-write-tail src len pos track sector))))
      t))

(defun m65d-save-new (name src)
  (let ((len (string-length src))
        (nlen (string-length name)))
    (if (< len 1)
        nil
        (if (> len 1016)
            nil
            (if (%m65dv-name-ok-p nlen)
                (let ((slot (%m65dv-dir-slot name nlen)))
                  (if slot
                      (let ((blocks (%m65dv-blocks-for len 0)))
                        (let ((chain (%m65dv-find-chain blocks)))
                          (if chain
                              (if (%m65dv-write-chain src len chain 0)
                                  (if (%m65dv-claim-chain chain)
                                      (%m65dv-write-dir name nlen (car chain) blocks slot)
                                      nil)
                                  nil)
                              nil)))
                      nil))
                nil)))))
