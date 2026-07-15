; lisp65 demo 01: string utilities in a small data-cleaning pipeline.
;
; The demo uses only portable, visible Stdlib pieces: trim, substring, search,
; prefix/suffix tests, case folding and concatenation.  Strings are built from
; character codes because the current device FASL emitter accepts only
; fixnum/NIL/T/symbol literals in compiled functions.
;
;   (compile-file "dstr" "fstr")
;   (load "fstr")
;   (demo-strings-run)

(defun demo-str-space ()
  (list->string (list 32)))

(defun demo-str-colon ()
  (list->string (list 58)))

(defun demo-str-ok ()
  (list->string (list 111 107)))

(defun demo-str-low ()
  (list->string (list 108 111 119)))

(defun demo-str-lisp65 ()
  (list->string (list 108 105 115 112 54 53)))

(defun demo-str-lisp ()
  (list->string (list 76 73 83 80)))

(defun demo-str-65 ()
  (list->string (list 54 53)))

(defun demo-str-ok-suffix ()
  (string-append (demo-str-colon) (demo-str-ok)))

(defun demo-str-demo-suite-padded ()
  (list->string
   (append (list 32 32 100 101 109 111 45 115 117 105 116 101)
           (list 32 32))))

(defun demo-str-demo ()
  (list->string (list 100 101 109 111)))

(defun demo-string-label (name score)
  (string-append (string-upcase name)
                 (demo-str-colon)
                 (if (> score 9) (demo-str-ok) (demo-str-low))))

(defun demo-string-window (text)
  (substring (string-trim (demo-str-space) text) 0 4))

(defun demo-string-good-p (text)
  (and (string-prefix-p (demo-str-lisp) text)
       (string-suffix-p (demo-str-ok-suffix) text)
       (= (search (demo-str-65) text) 4)))

(defun demo-strings-run ()
  (let ((label (demo-string-label (demo-str-lisp65) 12)))
    (if (and (demo-string-good-p label)
             (string= (demo-string-window (demo-str-demo-suite-padded))
                      (demo-str-demo)))
        42
        0)))
