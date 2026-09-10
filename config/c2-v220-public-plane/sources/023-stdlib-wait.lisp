; Cold Bank-2 frame wait over the same atomic raster counter as (time form).
; The VM's standing lisp_poll cadence makes every loop RUN/STOP-abortable.

(defun %wait-until (start frames)
  (if (>= (%time-delta start (%time-read)) frames)
      nil
      (%wait-until start frames)))

(defun wait (frames)
  (if (or (< frames 0) (> frames 16383))
      (%time-error-duration-overflow)
      (%wait-until (%time-read) frames)))
