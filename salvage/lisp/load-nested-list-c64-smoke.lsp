; SAVE-format LOAD smoke for a loaded user function used as a list-primitive argument.

(DE SEQTAIL (L) (CDR L))
(DE SEQSECOND (L) (CAR (SEQTAIL L)))
