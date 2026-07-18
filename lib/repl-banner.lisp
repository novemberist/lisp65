; Workbench startup banner. The run stream is ASCII-only: three bytes encode
; x, y, and kind/length for each lambda, block-letter, or separator run.
; Lambda and letter cells use reverse spaces so their appearance is independent
; of the active mixed-case charset. Only the horizontal separator needs a raw
; screen code; screen-put-char owns its matching color cell first.

(defun %banner-separator ()
  (dotimes (cell 66 nil)
    (let* ((column (+ cell 1))
           (address (+ 2048 (+ (* 6 80) column))))
      (screen-put-char column 6 32 15)
      (poke (/ address 256) (mod address 256) 64))))

(defun %banner-run (runs run)
  (let* ((offset (* run 3))
         (x (- (string-ref runs offset) 36))
         (y (- (string-ref runs (+ offset 1)) 65))
         (tag (- (string-ref runs (+ offset 2)) 65))
         (kind (/ tag 8))
         (length (mod tag 8)))
    (if (= kind 3)
        (%banner-separator)
        (let ((attr (if (< kind 2) 135 129)))
          (dotimes (cell length nil)
            (screen-put-char (+ x cell) y 32 attr))))))

(defun %banner-runs ()
  (let ((runs "&AC'BC(CC)DC*EC+FC(DJ&EK%FK3AS3BS3CS3DS3ES3FW;AU<BS<CS<DS<ES;FUAAWABSACWEDSEESAFWIAWIBSMBSICWIDSIESIFSQAWQBSQCWQDSUDSQESUESQFWYAWYBSYCW]DS]ESYFW%GY"))
    (dotimes (run 49 nil)
      (%banner-run runs run))))

(defun %banner-subtitle ()
  (let ((text "WORKBENCH - DIALECT V2"))
    (dotimes (index 22 nil)
      (screen-put-char (+ 44 index) 7 (string-ref text index) 15))))

(defun %repl-banner ()
  (%banner-runs)
  (%banner-subtitle)
  ; Direct-at writes do not move the cursor. Put the first prompt on row 9.
  (dotimes (row 9 nil)
    (write-char 10)))
