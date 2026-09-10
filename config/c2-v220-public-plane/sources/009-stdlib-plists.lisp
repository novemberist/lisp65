(defun %getf (plist key default)
  (if plist
      (if (eql (car plist) key)
          (cadr plist)
          (%getf (cdr (cdr plist)) key default))
      default))

(defun getf (plist key &rest default)
  (%getf plist key (if default (car default) nil)))

(defun remf (plist key)
  (%remf-into plist key nil))

(defun %remf-into (plist key acc)
  (if plist
      (if (eql (car plist) key)
          (%append2-rev acc (cdr (cdr plist)))
          (%remf-into (cdr (cdr plist))
                      key
                      (cons (cadr plist) (cons (car plist) acc))))
      (reverse acc)))
