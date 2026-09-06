; The already-guarded compiled/VM setters must retain their behavior.
(setq x 7)
(setq 5 x)
(set 5 x)
(setq y 9)
(set (quote y) 11)
y
