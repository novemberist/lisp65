; lisp65 demo 03: simple screen output.
;
; This is intentionally small: it draws a title, two status lines and a tiny
; ruler.  It is useful after display-driver changes because it exercises
; SCREEN-PUT-CHAR without requiring the optional bulk string primitive.
;
;   (compile-file "dscr" "fscr")
;   (load "fscr")
;   (demo-screen-run)

(defun demo-screen-ruler (x y count)
  (if (> count 0)
      (progn
        (screen-put-char x y 42 7)
        (demo-screen-ruler (1+ x) y (1- count)))
      nil))

(defun demo-screen-string-at (x y codes attr)
  (if codes
      (progn
        (screen-put-char x y (car codes) attr)
        (demo-screen-string-at (1+ x) y (cdr codes) attr))
      nil))

(defun demo-screen-title ()
  (append (list 108 105 115 112 54 53 32 100 101 109 111 32)
          (list 115 117 105 116 101)))

(defun demo-screen-compiled ()
  (append (list 99 111 109 112 105 108 101 100 32 111 110 32)
          (list 109 101 103 97 54 53)))

(defun demo-screen-index ()
  (append (list 114 117 110 58 32 100 101 109 111 45 105 110)
          (list 100 101 120)))

(defun demo-screen-draw ()
  (screen-clear)
  (demo-screen-string-at 2 1 (demo-screen-title) 7)
  (demo-screen-string-at 2 3 (demo-screen-compiled) 5)
  (demo-screen-string-at 2 4 (demo-screen-index) 3)
  (demo-screen-ruler 2 6 18)
  42)

(defun demo-screen-run ()
  (progn
    (demo-screen-draw)
    42))
