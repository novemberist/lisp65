(defun %ide-lines-source-list (lines)
  (if lines
      (if (cdr lines)
          (append (string->list (car lines))
                  (cons 10 (%ide-lines-source-list (cdr lines))))
          (string->list (car lines)))
      nil))

(defun ide-lines->source (lines)
  (list->string (%ide-lines-source-list lines)))

(defun ide-region-source (buffer start end)
  (ide-lines->source (ide-region-lines buffer start end)))

(defun ide-make-eval-request (buffer start end source)
  (list 'eval-source (ide-buffer-name buffer) start end source))

(defun ide-region-eval-request (buffer start end)
  (ide-make-eval-request buffer
                         start
                         end
                         (ide-region-source buffer start end)))

(defun ide-defun-eval-request (buffer line)
  ((lambda (span)
     (if span
         (ide-region-eval-request buffer (car span) (cdr span))
         nil))
   (ide-defun-region buffer line)))

(defun ide-eval-request-buffer (request)
  (nth 1 request))

(defun ide-eval-request-start (request)
  (nth 2 request))

(defun ide-eval-request-end (request)
  (nth 3 request))

(defun ide-eval-request-source (request)
  (nth 4 request))
