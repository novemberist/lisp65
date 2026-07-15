; lisp65 demo 05: scripted IDE buffer edits.
;
; On Dev-Core, load the IDE disk library before running the compiled FASL:
;
;   (load-lib "ide")
;   (compile-file "dide" "fide")
;   (load "fide")
;   (demo-ide-run)
;
; Profiles with resident IDE functions can skip LOAD-LIB.

(defun demo-ide-name ()
  (list->string (list 115 99 114 97 116 99 104)))

(defun demo-ide-abc ()
  (list->string (list 97 98 99)))

(defun demo-ide-def ()
  (list->string (list 100 101 102)))

(defun demo-ide-abc-bang ()
  (list->string (list 97 98 99 33)))

(defun demo-ide-open-paren ()
  (char->string 40))

(defun demo-ide-seed ()
  (ide-make-buffer (demo-ide-name) (list (demo-ide-abc) (demo-ide-def))))

(defun demo-ide-edit ()
  (let* ((b0 (ide-set-point (demo-ide-seed) 0 3))
         (b1 (ide-insert-char b0 33))
         (b2 (ide-split-line b1))
         (b3 (ide-insert-char b2 40)))
    b3))

(defun demo-ide-run ()
  (let ((buffer (demo-ide-edit)))
    (if (and (string= (ide-line-at buffer 0) (demo-ide-abc-bang))
             (string= (ide-line-at buffer 1) (demo-ide-open-paren))
             (= (ide-line-count buffer) 3)
             (= (ide-point-line (ide-buffer-point buffer)) 1)
             (= (ide-point-column (ide-buffer-point buffer)) 1))
        42
        0)))
