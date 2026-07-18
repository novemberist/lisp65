; Dialect-v2 runtime eval is ordinary resident bytecode. lcc-run is the single
; semantic engine after the native Treewalk carrier is removed.
(defun eval (form)
  (lcc-run form))

; 1.1-C1 resident control surface. The one compiler export exists as a literal
; before the transaction starts. Private %c1-control operations 0/1/2 own
; checkpoint, validation and retirement; operation 2 returns its second value
; only after the old function cell and code/directory watermarks are restored.
(defun %c1-compile-detached (mode first second)
  (if (%c1-control 0 (quote %c1-compile))
      (if (%disk-load-lib "lcc")
          (if (%c1-control 1 nil)
              (%c1-control 2 (%c1-compile mode first second))
              (progn (%c1-control 2 nil) nil))
          (progn (%c1-control 2 nil) nil))
      nil))

(defun lcc-run (form)
  (let ((compiled (%c1-compile-detached 0 form nil)))
    (cond ((if (consp form) (eq (car form) 'defmacro) nil)
           (%set-macro (car (cdr form)) (lcc-install compiled nil)))
          ((if (consp form) (eq (car form) 'defun) nil)
           (lcc-install compiled (car (cdr form))))
          (t (lcc-install compiled 't)))))

(defun %number->string-result (negative codes)
  (%string-from-codes (if negative (cons 45 codes) codes)))

(defun number->string (number)
  (if (= number -16384)
      (%number->string-result
        t (cons 49 (cons 54 (cons 51 (cons 56 (cons 52 nil))))))
      (let* ((negative (< number 0))
             (value (if negative (- 0 number) number))
             (codes nil))
        (if (= value 0)
            (%number->string-result negative (cons 48 nil))
            (progn
              (dotimes (index 5)
                (if (> value 0)
                    (progn
                      (setq codes (cons (+ 48 (mod value 10)) codes))
                      (setq value (/ value 10)))
                    nil))
              (%number->string-result negative codes))))))

; Read exactly one object from a String through the already resident compiler
; reader.  The explicit predicate keeps the public type contract stable while
; malformed input continues through the existing reader error channel.
(defun read-from-string (source)
  (if (stringp source)
      (progn (%cs-read-open source) (%fasl-read-form))
      (string-length source)))

; v2 Workbench FASL persistence. The compiler returns one detached Buffer;
; M65D owns allocation, media binding, verified writes and directory publish.
; There is no preallocated-slot writer beside the M65D COW transaction.
(defun compile-error ()
  (symbol-value (quote %compile-error)))

; Compile into the detached staging Buffer, then hand that Buffer to the one
; public persistence transaction. The buffer predicate stays resident through
; %buffer-read; no optional comfort library is required.
(defun %c1-compile-save (source dst)
  (let ((output (%c1-compile-detached 1 source nil)))
    (if (%buffer-read 0 output)
        (let ((saved (m65d-save dst output)))
          (if (= saved 0)
              (progn (set-symbol-value (quote %compile-error) nil) 't)
              (if (= saved 3)
                  (progn (set-symbol-value (quote %compile-error) "too large") nil)
                  (progn (set-symbol-value (quote %compile-error) "save failed") nil))))
        (progn (set-symbol-value (quote %compile-error) "compile failed") nil))))

(defun compile-string (source dst)
  (progn
    (set-symbol-value (quote %compile-error) nil)
    (if (stringp source)
        (if (stringp dst)
            (%c1-compile-save source dst)
            (progn (set-symbol-value (quote %compile-error) "bad destination") nil))
        (progn (set-symbol-value (quote %compile-error) "bad source") nil))))
