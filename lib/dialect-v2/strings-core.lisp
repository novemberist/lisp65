; Dialect-v2 string core. string-length/string-ref remain native primitives;
; construction uses the private code-list codecs. Prim 26/27 are tombstones.

(defun %v2-string-bounds-error ()
  (string-ref "" -1))

(defun %v2-substring-codes (codes start end index acc)
  (if (= index end)
      (nreverse acc)
      (if codes
          (if (< index start)
              (%v2-substring-codes (cdr codes) start end (+ index 1) acc)
              (%v2-substring-codes (cdr codes) start end (+ index 1)
                                   (cons (car codes) acc)))
          (%v2-string-bounds-error))))

(defun substring (string start &optional end)
  ((lambda (limit length)
     (if (< start 0)
         (%v2-string-bounds-error)
         (if (< limit start)
             (%v2-string-bounds-error)
             (if (> limit length)
                 (%v2-string-bounds-error)
                 (%string-from-codes
                  (%v2-substring-codes (%string-codes string)
                                       start limit 0 nil))))))
   (if end end (string-length string))
   (string-length string)))

(defun %v2-string-reverse-onto (codes acc)
  (if codes
      (%v2-string-reverse-onto (cdr codes) (cons (car codes) acc))
      acc))

(defun %v2-string-append-codes (strings acc)
  (if strings
      (%v2-string-append-codes
       (cdr strings)
       (%v2-string-reverse-onto (%string-codes (car strings)) acc))
      (nreverse acc)))

(defun string-append (&rest strings)
  (%string-from-codes (%v2-string-append-codes strings nil)))

(defun %v2-string=-at (left right index length)
  (if (= index length)
      t
      (if (= (string-ref left index) (string-ref right index))
          (%v2-string=-at left right (+ index 1) length)
          nil)))

(defun string= (left right)
  (if (= (string-length left) (string-length right))
      (%v2-string=-at left right 0 (string-length left))
      nil))

(defun %v2-string<-at (left right index left-length right-length)
  (if (= index left-length)
      (< left-length right-length)
      (if (= index right-length)
          nil
          (if (= (string-ref left index) (string-ref right index))
              (%v2-string<-at left right (+ index 1) left-length right-length)
              (< (string-ref left index) (string-ref right index))))))

(defun string< (left right)
  (%v2-string<-at left right 0 (string-length left) (string-length right)))
