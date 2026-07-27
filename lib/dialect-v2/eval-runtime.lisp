; C2 runtime eval is ordinary immutable bytecode.  The compiler image is part
; of the generation-bound C2 shelf, so no lease/load/retirement coordinator or
; legacy L65M carrier remains in the product closure.
(defun eval (form)
  (lcc-run form))

(defun lcc-run (form)
  ; A published nullary bytecode call is already a complete execution object.
  ; Recompiling it as a transient wrapper would reopen the full append,
  ; publication and rollback transaction without adding semantics.  Keep the
  ; fast path deliberately narrow: macros, primitives, argument evaluation,
  ; special forms and unbound names all retain the proven compiler path.
  (if (if (consp form)
          (if (null (cdr form))
              (eq (function-kind (car form)) 'bytecode)
              nil)
          nil)
      (funcall (car form))
      (let ((compiled (%c2-compile-form form)))
        (cond ((if (consp form) (eq (car form) 'defmacro) nil)
               (%set-macro (car (cdr form)) (lcc-install compiled nil)))
              ((if (consp form) (eq (car form) 'defun) nil)
               (lcc-install compiled (car (cdr form))))
              (t (lcc-install compiled 't))))))

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

; One emitter for born code. Each source definition is compiled by the same
; immutable compiler and appended to the one C2I-v2 image under construction.
(defun %c2-source-form (form)
  (cond ((if (consp form) (eq (car form) 'defmacro) nil)
         (%c2-control 1
           (cons (%c2-compile-form form)
             (cons (car (cdr form)) (cons 1 nil)))))
        ((if (consp form) (eq (car form) 'defun) nil)
         (%c2-control 1
           (cons (%c2-compile-form form)
             (cons (car (cdr form)) (cons 0 nil)))))
        (t (%fasl-error-not-a-defun))))

(defun %c2-source-forms ()
  (let ((form (%fasl-read-form)))
    (if (eq form '%fasl-eof)
        (%c2-control 2 nil)
        (if (%c2-source-form form) (%c2-source-forms) nil))))

(defun %c2-compile-source (source)
  (progn
    (%cs-read-open source)
    (if (%c2-control 0 nil) (%c2-source-forms) nil)))

; Compile into the detached C2I-v2 Buffer, then hand that Buffer to the one
; public M65D COW transaction.
(defun %c2-compile-save (source dst)
  (let ((output (%c2-compile-source source)))
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
            (%c2-compile-save source dst)
            (progn (set-symbol-value (quote %compile-error) "bad destination") nil))
        (progn (set-symbol-value (quote %compile-error) "bad source") nil))))
