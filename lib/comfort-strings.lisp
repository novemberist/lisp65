; Host-first comfort string freight.  This file deliberately uses only the
; delivered dialect-v2 string surface; the string/list converter tombstones
; are not construction tools.

(defun capitalize (string)
  (if (= (string-length string) 0)
      string
      (string-append
       (char->string (char-upcase (string-ref string 0)))
       (string-downcase (substring string 1)))))

(defun %comfort-string-split-from (string separator start acc)
  ((lambda (relative)
     (if relative
         ((lambda (at)
            (%comfort-string-split-from
             string separator (+ at (string-length separator))
             (cons (substring string start at) acc)))
          (+ start relative))
         (nreverse (cons (substring string start) acc))))
   (search separator (substring string start))))

(defun string-split (string separator)
  (if (= (string-length separator) 0)
      (list string)
      (%comfort-string-split-from string separator 0 nil)))
