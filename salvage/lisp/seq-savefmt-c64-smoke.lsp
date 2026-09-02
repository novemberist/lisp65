; Short sequence helper that fits the historical LOAD line limit after
; conversion to LISP-64 SAVE format.

(DE SEQTAIL (L) (CDR L))
(DE SEQSECOND (L) (CAR (CDR L)))
