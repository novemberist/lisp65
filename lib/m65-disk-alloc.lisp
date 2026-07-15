;; M6 prototype: create a two-sector source file by scanning one BAM track and
;; one directory sector. Still intentionally narrow:
;; - data sectors are selected on track 45, starting at sector 20
;; - directory entries are selected in T40/S4
;; - payload length must be 255..508 bytes

(defun %m65d-clear ()
  (dotimes (i 256 t) (%disk-poke i 0)))

(defun %m65d-copy (src src0 dst0 n)
  (dotimes (i n t)
    (%disk-poke (+ dst0 i) (string-ref src (+ src0 i)))))

(defun %m65d-mask (sector)
  (let ((r (mod sector 8)))
    (if (= r 0) 1
        (if (= r 1) 2
            (if (= r 2) 4
                (if (= r 3) 8
                    (if (= r 4) 16
                        (if (= r 5) 32
                            (if (= r 6) 64 128)))))))))

(defun %m65d-bitmap-offset (sector)
  (if (< sector 8)
      41
      (if (< sector 16)
          42
          (if (< sector 24)
              43
              (if (< sector 32) 44 45)))))

(defun %m65d-bit-set-p (byte mask)
  (>= (mod byte (+ mask mask)) mask))

(defun %m65d-sector-free-p (sector)
  (%m65d-bit-set-p (%disk-byte (%m65d-bitmap-offset sector))
                   (%m65d-mask sector)))

(defun %m65d-bam-ok ()
  (if (= (%disk-byte 0) 0)
      (if (= (%disk-byte 1) 255)
          (>= (%disk-byte 40) 2)
          nil)
      nil))

(defun %m65d-find-second (sector)
  (if (> sector 39)
      nil
      (if (%m65d-sector-free-p sector)
          sector
          (%m65d-find-second (+ sector 1)))))

(defun %m65d-find-pair-from (sector)
  (if (> sector 38)
      nil
      (if (%m65d-sector-free-p sector)
          (let ((second (%m65d-find-second (+ sector 1))))
            (if second
                (cons sector (cons second nil))
                (%m65d-find-pair-from (+ sector 1))))
          (%m65d-find-pair-from (+ sector 1)))))

(defun %m65d-find-pair ()
  (if (%disk-read-sector 40 2)
      (if (%m65d-bam-ok)
          (%m65d-find-pair-from 20)
          nil)
      nil))

(defun %m65d-claim-one (sector)
  (let ((off (%m65d-bitmap-offset sector))
        (mask (%m65d-mask sector)))
    (if (%m65d-bit-set-p (%disk-byte off) mask)
        (progn
          (%disk-poke off (- (%disk-byte off) mask))
          t)
        nil)))

(defun %m65d-claim-two (first second)
  (if (%disk-read-sector 40 2)
      (if (%m65d-bam-ok)
          (if (%m65d-sector-free-p first)
              (if (%m65d-sector-free-p second)
                  (progn
                    (%disk-poke 40 (- (%disk-byte 40) 2))
                    (%m65d-claim-one first)
                    (%m65d-claim-one second)
                    (%disk-write-sector 40 2))
                  nil)
              nil)
          nil)
      nil))

(defun %m65d-fold-ascii (code)
  (if (>= code 97)
      (if (<= code 122) (- code 32) code)
      code))

(defun %m65d-fold-dir (code)
  (%m65d-fold-ascii (if (> code 127) (- code 128) code)))

(defun %m65d-name-code (name len i)
  (if (< i len)
      (%m65d-fold-ascii (string-ref name i))
      32))

(defun %m65d-name-ok-p (len)
  (if (< len 1) nil (<= len 16)))

(defun %m65d-name-match-at (name len base i)
  (if (= i 16)
      t
      (if (= (%m65d-fold-dir (%disk-byte (+ base (+ 5 i))))
             (%m65d-name-code name len i))
          (%m65d-name-match-at name len base (+ i 1))
          nil)))

(defun %m65d-dir-scan (name len entry free)
  (if (= entry 8)
      free
      (let ((base (* entry 32)))
        (if (= (%disk-byte (+ base 2)) 0)
            (%m65d-dir-scan name len (+ entry 1)
                            (if (< free 0) entry free))
            (if (%m65d-name-match-at name len base 0)
                -2
                (%m65d-dir-scan name len (+ entry 1) free))))))

(defun %m65d-dir-slot (name len)
  (if (%disk-read-sector 40 4)
      (if (= (%disk-byte 0) 0)
          (if (= (%disk-byte 1) 255)
              (let ((slot (%m65d-dir-scan name len 0 -1)))
                (if (< slot 0) nil slot))
              nil)
          nil)
      nil))

(defun %m65d-dir-clear (base)
  (dotimes (i 32 t) (%disk-poke (+ base i) 0)))

(defun %m65d-dir-name (base name len)
  (dotimes (i 16 t)
    (%disk-poke (+ base (+ 5 i))
                (if (< i len)
                    (%m65d-fold-ascii (string-ref name i))
                    160))))

(defun %m65d-write-dir (name len first slot)
  (if (%disk-read-sector 40 4)
      (let ((base (* slot 32)))
        (if (= (%disk-byte (+ base 2)) 0)
            (progn
              (%m65d-dir-clear base)
              (%disk-poke (+ base 2) 129)
              (%disk-poke (+ base 3) 45)
              (%disk-poke (+ base 4) first)
              (%m65d-dir-name base name len)
              (%disk-poke (+ base 30) 2)
              (%disk-poke (+ base 31) 0)
              (%disk-write-sector 40 4))
            nil))
      nil))

(defun %m65d-first (src first second)
  (progn
    (%m65d-clear)
    (%disk-poke 0 45)
    (%disk-poke 1 second)
    (%m65d-copy src 0 2 254)
    (%disk-write-sector 45 first)))

(defun %m65d-second (src len second)
  (let ((tail (- len 254)))
    (progn
      (%m65d-clear)
      (%disk-poke 0 0)
      (%disk-poke 1 (+ tail 1))
      (%m65d-copy src 254 2 tail)
      (%disk-write-sector 45 second))))

(defun m65d-save-new-2 (name src)
  (let ((len (string-length src))
        (nlen (string-length name)))
    (if (< len 255)
        nil
        (if (> len 508)
            nil
            (if (%m65d-name-ok-p nlen)
                (let ((slot (%m65d-dir-slot name nlen)))
                  (if slot
                      (let ((pair (%m65d-find-pair)))
                        (if pair
                            (let ((first (car pair))
                                  (second (car (cdr pair))))
                              (if (%m65d-first src first second)
                                  (if (%m65d-second src len second)
                                      (if (%m65d-claim-two first second)
                                          (%m65d-write-dir name nlen first slot)
                                          nil)
                                      nil)
                                  nil))
                            nil))
                      nil))
                nil)))))
