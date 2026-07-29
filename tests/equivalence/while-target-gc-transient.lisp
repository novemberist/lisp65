; Link-77 hardware reproducer: two transient cons allocations per admitted
; iteration, no retained list.  The final false predicate still allocates its
; wrapper, so a NIL caused by OOM can masquerade as normal loop termination;
; the lane must therefore require both result 600 and mem_oom == 0.
(let ((i 0))
  (progn
    (while (car (cons (< i 600) nil))
      (car (cons i nil))
      (setq i (+ i 1)))
    i))
