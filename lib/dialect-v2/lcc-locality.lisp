; Promoted v1.4 compiler-locality overlay.  The complete product carrier is
; still lib/lcc.lisp plus lcc-profile.lisp; this file only replaces the hot
; emission seams whose host equivalence and pricing closed in v1.11.

; Carrier-local emission fusion.  %lcc-emit remains the representation
; authority and fallback for branch-sensitive bodies.  The release packer
; privately inlines this raw equivalent only at the hot seams below.
(defun %lcc-emit-local (cs b)
  (cons (cons (cons b (car (car cs))) (+ (cdr (car cs)) 1))
        (cons (car (cdr cs))
              (cons (car (cdr (cdr cs)))
                    (cons (car (cdr (cdr (cdr cs)))) nil)))))

(defun %lcc-emit-op (cs name)
  (%lcc-emit-local cs (%lcc-op name)))

(defun %lcc-emit2 (cs name b)
  (%lcc-emit-local (%lcc-emit-op cs name) b))

(defun %lcc-emit-slot (cs slot kind)
  (if (eq kind 'a)
      (if (< slot 3)
          (%lcc-emit-local cs (+ 11 slot))
          (%lcc-emit2 cs 'pushargn slot))
      (%lcc-emit2 cs 'loadl slot)))

(defun %lcc-tailcall (cs lvls op args)
  ((lambda (r)
     ((lambda (rl)
        (%lcc-emit-local
         (%lcc-emit2 (car rl) 'tailcall (cdr rl)) (cdr r)))
      (%lcc-lit-slot (car r) op)))
   (%lcc-args cs lvls args 0)))

; Profiled order only: macro and generic-call exits are the hot path for the
; persistent workload.  Predicates and lowerings are unchanged, so this
; changes carrier work, never emitted CodeObject semantics.
(defun %lcc-tail2 (cs lvls op args form)
  (cond ((%lcc-macro-p op) (%lcc-tail cs lvls (macroexpand-1 form)))
        ((%lcc-callform-p op) (%lcc-tailcall cs lvls op args))
        ((eq op 'and)   (%lcc-tail cs lvls (%lcc-lower-and args)))
        ((eq op 'or)    (%lcc-tail cs lvls (%lcc-lower-or args)))
        ((eq op 'cond)  (%lcc-tail cs lvls (%lcc-lower-cond args)))
        ((eq op 'when)  (%lcc-tail cs lvls (%lcc-lower-when args)))
        ((eq op 'unless) (%lcc-tail cs lvls (%lcc-lower-unless args)))
        ((eq op 'quasiquote) (%lcc-tail cs lvls (%lcc-lower-qq (car args))))
        ((%lcc-do-p op) (%lcc-emit-op (%lcc-expr-do cs lvls op args) 'ret))
        (t (%lcc-emit-op (%lcc-expr cs lvls form) 'ret))))
