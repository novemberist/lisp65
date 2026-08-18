; C2 runtime eval is ordinary immutable bytecode.  The compiler image is part
; of the generation-bound C2 shelf, so no lease/load/retirement coordinator or
; legacy L65M carrier remains in the product closure.
(defun eval (form)
  (lcc-run form))

; Public strict-binary designators. Direct compilation lowers the body call
; to dialect-v2 opcodes 20..23; funcall/apply invoke the same compiled body.
(defun logand (a b) (logand a b))
(defun logior (a b) (logior a b))
(defun logxor (a b) (logxor a b))
(defun ash (value count) (ash value count))

(defun %c2-direct-quoted-value-p (form)
  (if (consp form)
      (if (eq (car form) 'quote)
          (if (consp (cdr form))
              (null (cdr (cdr form)))
              nil)
          nil)
      nil))

(defun %c2-direct-value-p (form)
  (if (numberp form)
      t
      (if (stringp form)
          t
          (if (eq form nil)
              t
              (if (eq form 't)
                  t
                  (%c2-direct-quoted-value-p form))))))

(defun %c2-direct-values-p (forms)
  (if forms
      (if (consp forms)
          (if (%c2-direct-expression-p (car forms))
              (%c2-direct-values-p (cdr forms))
              nil)
          nil)
      t))

(defun %c2-direct-value (form)
  (if (%c2-direct-quoted-value-p form) (car (cdr form)) form))

(defun %c2-direct-expression-p (form)
  (if (%c2-direct-value-p form)
      t
      (if (symbolp form)
          (boundp form)
          (%c2-published-direct-call-p form))))

(defun %c2-direct-expression (form)
  (if (%c2-direct-value-p form)
      (%c2-direct-value form)
      (if (symbolp form)
          (symbol-value form)
          (if (null (cdr form))
              (funcall (car form))
              (apply (car form) (%c2-direct-values (cdr form)))))))

(defun %c2-direct-values (forms)
  (if forms
      (cons (%c2-direct-expression (car forms))
            (%c2-direct-values (cdr forms)))
      nil))

(defun %c2-published-direct-call-p (form)
  (if (consp form)
      (if (symbolp (car form))
          (if (eq (function-kind (car form)) 'bytecode)
              (%c2-direct-values-p (cdr form))
              nil)
          nil)
      nil))

(defun %c2-top-level-expand (form)
  (if (if (consp form) (%lcc-macro-p (car form)) nil)
      (%c2-top-level-expand (macroexpand-1 form))
      form))

(defun %c2-top-level-run-forms (forms)
  (if forms
      (if (cdr forms)
          (progn (lcc-run (car forms))
                 (%c2-top-level-run-forms (cdr forms)))
          (lcc-run (car forms)))
      nil))

(defun %c2-run-expanded (form)
  ; A tree made solely of published bytecode calls, bound variable reads and
  ; already-direct values is a complete execution object.  Evaluate that tree
  ; left-to-right through the published cells instead of reopening the full
  ; transient append/publication/rollback transaction.  The CodeObject/VM
  ; remains the one arity authority.  Definitions, macros, special forms,
  ; malformed lists, unbound names and undefined operators retain the proven
  ; compiler path; no persistent form can enter this branch.
  (cond ((if (consp form) (eq (car form) 'progn) nil)
         (%c2-top-level-run-forms (cdr form)))
        ((%c2-published-direct-call-p form)
         (%c2-direct-expression form))
        (t
         (let ((compiled (%c2-compile-form form)))
           (cond ((if (consp form) (eq (car form) 'defmacro) nil)
                  (%set-macro (car (cdr form)) (lcc-install compiled nil)))
                 ((if (consp form) (eq (car form) 'defun) nil)
                  (lcc-install compiled (car (cdr form))))
                 (t (lcc-install compiled 't)))))))

(defun lcc-run (form)
  (%c2-run-expanded (%c2-top-level-expand form)))

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
