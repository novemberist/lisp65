; Treewalk mutation witness: x must be bound before the malformed SETQ so
; removing the symbol-domain guard reaches the historical sidx() write.
(setq x 7)
(setq 5 x)
(set-symbol-function 5 nil)
(%set-macro 5 nil)
