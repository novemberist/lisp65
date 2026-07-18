; Public 1.1 first-class byte-buffer API. The native carriers are deliberately
; private and non-designator-capable; this shelf library is the public surface.

(defun bufferp (value)
  (if (%buffer-read 0 value) t nil))

(defun make-buffer (length)
  (%buffer-alloc 0 length))

(defun buffer-length (buffer)
  (%buffer-read 1 buffer))

(defun buffer-ref (buffer index)
  (%buffer-read 2 buffer index))

(defun buffer-set! (buffer index value)
  (%buffer-write buffer index value))

; Ownership is transferred: the same nonmoving arena allocation becomes a
; string atomically, and the old buffer identity is no longer a buffer.
(defun buffer->string (buffer)
  (%buffer-read 3 buffer))

(defun string->buffer (string)
  (%buffer-alloc 1 string))
