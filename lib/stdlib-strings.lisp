(defun %char-list= (a b)
  (if a
      (if b
          (and (= (car a) (car b)) (%char-list= (cdr a) (cdr b)))
          nil)
      (if b nil 't)))

(defun string= (a b)
  (%char-list= (string->list a) (string->list b)))

(defun string/= (a b)
  (not (string= a b)))

(defun %char-list< (a b)
  (if a
      (if b
          (if (= (car a) (car b))
              (%char-list< (cdr a) (cdr b))
              (< (car a) (car b)))
          nil)
      (if b 't nil)))

(defun string< (a b)
  (%char-list< (string->list a) (string->list b)))

(defun string> (a b)
  (string< b a))

(defun string<= (a b)
  (not (string< b a)))

(defun string>= (a b)
  (not (string< a b)))

(defun string-append (&rest strings)
  (list->string (apply (function append) (mapcar (function string->list) strings))))

(defun %subseq-list (xs start end i)
  (%subseq-list-into xs start end i nil))

(defun %subseq-list-into (xs start end i acc)
  (if xs
      (if (< i start)
          (%subseq-list-into (cdr xs) start end (1+ i) acc)
          (if (< i end)
              (%subseq-list-into (cdr xs) start end (1+ i) (cons (car xs) acc))
              (reverse acc)))
      (reverse acc)))

(defun substring (s start &rest maybe-end)
  (list->string
   (%subseq-list (string->list s)
                 start
                 (if maybe-end (car maybe-end) (string-length s))
                 0)))

(defun %upcase-code (c)
  (if (and (>= c 97) (<= c 122))
      (- c 32)
      c))

(defun %downcase-code (c)
  (if (and (>= c 65) (<= c 90))
      (+ c 32)
      c))

(defun %case-fold-list (xs)
  (%case-fold-list-into xs nil))

(defun %case-fold-list-into (xs acc)
  (if xs
      (%case-fold-list-into (cdr xs) (cons (%upcase-code (car xs)) acc))
      (reverse acc)))

(defun string-equal (a b)
  (%char-list= (%case-fold-list (string->list a))
               (%case-fold-list (string->list b))))

(defun %char-list-prefix-p (prefix xs)
  (if prefix
      (if xs
          (if (= (car prefix) (car xs))
              (%char-list-prefix-p (cdr prefix) (cdr xs))
              nil)
          nil)
      't))

(defun string-prefix-p (prefix s)
  (%char-list-prefix-p (string->list prefix) (string->list s)))

(defun %drop-list (xs n)
  (if (> n 0)
      (%drop-list (cdr xs) (1- n))
      xs))

(defun string-suffix-p (suffix s)
  (if (> (string-length suffix) (string-length s))
      nil
      (%char-list= (string->list suffix)
                   (%drop-list (string->list s)
                               (- (string-length s) (string-length suffix))))))

(defun %char-list-search (needle xs i)
  (if needle
      (if xs
          (if (%char-list-prefix-p needle xs)
              i
              (%char-list-search needle (cdr xs) (1+ i)))
          nil)
      0))

(defun search (needle s)
  (%char-list-search (string->list needle) (string->list s) 0))

(defun string-contains-p (needle s)
  (if (search needle s) 't nil))

(defun %char-member-p (code chars)
  (if chars
      (if (= code (car chars))
          't
          (%char-member-p code (cdr chars)))
      nil))

(defun %trim-left-list (chars bag)
  (if chars
      (if (%char-member-p (car chars) bag)
          (%trim-left-list (cdr chars) bag)
          chars)
      nil))

(defun %trim-right-list (chars bag)
  (reverse (%trim-left-list (reverse chars) bag)))

(defun string-trim (bag s)
  (list->string
   (%trim-right-list
    (%trim-left-list (string->list s) (string->list bag))
    (string->list bag))))

(defun string-upcase (s)
  (list->string (mapcar (function %upcase-code) (string->list s))))

(defun string-downcase (s)
  (list->string (mapcar (function %downcase-code) (string->list s))))

(defun char-upcase (code)
  (%upcase-code code))

(defun char-downcase (code)
  (%downcase-code code))

(defun char (s i)
  (string-ref s i))

(defun char->string (code)
  (list->string (list code)))
