; lisp65 -- lcc: the self-hosted bytecode compiler (self-hosting, Lane K;
; started 2026-07-05). Plan: docs/self-hosting-plan.md. Target ABI:
; docs/bytecode-abi.md (P0, PINNED). Byte oracle: scripts/lcc-oracle.py,
; byte-exact against bytecode_p0_compiler.py and enforced by the make check.
;
; P3 closure state on top of P2: a lambda used as a value is compiled as a
; HELPER function. Free variables resolve transitively through the LEVELS list
; (resolve_uv analogue: outer local via=0, outer upvalue via=1). The creation
; site pushes the upvalue values plus OP_CLOSURE(63); the body reads through
; OP_UPVAL(64), and setq of a free variable uses OP_SETUPVAL(65). Helper
; references are MARKER literals (%lcc-helper <idx>) in the literal table; the
; run harness replaces them with MK_BCODE(di) during registration
; (OP_CLOSURE/funcall accept BCODE immediates directly). No captures means
; PUSHLIT <marker>, the same fast path as C. An immediate lambda
; ((lambda ..) args) lowers like let, matching the reference behavior.
; PREVIOUSLY (P2): P0 expressions plus BINDINGS (let/let*/local setq with
; monotonically allocated slots and no slot reuse after scope end, like the
; reference); CALLS (CALLPRIM table, generic CALL with a callee-symbol literal,
; funcall/apply through PRIMS); parameters (PUSHARG0-2/PUSHARGN); and GLOBALS
; like the C compiler (read -> CALLPRIM 19, setq -> CALLPRIM 20). The Python
; reference compiler has no globals, so the byte oracle excludes them and VM
; semantics verifies P2.
;
; Representations:
;   st   = (bytes-rev . length)                 emission state, O(1) append
;   cs   = (st lits-rev maxslot fnsbox)         compiler state; mutable helper list in fnsbox
;   lvls = ((name slot kind) ...)               one level; kind = a (parameter) | l (local)
;   lvls = ((lvls . uvbox) ...)                 levels, youngest first; uvbox = (uvs-rev . n),
;                                               uv = (name src via), via 0=local, 1=upvalue
; Branch patching: the newly emitted acc cell IS the offset byte, so use
; (rplaca cell d).

; ---- Opcodes (ABI truth in src/vm.h; checked by the byte oracle) ----
; DEVICE LIMIT (enforced by the P5 fixed-point test): code objects <=255 B
; (dir_len uint8), so large cond dispatches are split in half; the t clause is
; a tail call into part 2.
(defun %lcc-op (name)
  (cond ((eq name 'pushi8) 1) ((eq name 'add) 2) ((eq name 'ret) 5) ((eq name 'pushlit) 6)
        ((eq name 'sub) 14) ((eq name 'mul) 15) ((eq name 'div) 16) ((eq name 'mod) 17)
        ((eq name 'less) 18) ((eq name 'greater) 19) ((eq name 'remainder) 24)
        ((eq name 'jmprel) 28) ((eq name 'jfalserel) 29) ((eq name 'eq) 30)
        ((eq name 'not) 42) ((eq name 'pushnil) 43) ((eq name 'pusht) 44)
        (t (%lcc-op2 name nil))))

; The second dispatcher carries two explicitly separate tails so both code
; objects remain under 255 B without consuming another standard-library or
; symbol entry.
(defun %lcc-op2 (name prim)
  (if prim
      (cond ((eq name 'symbol-value) 19) ((eq name 'set-symbol-value) 20)
            ((eq name '%disk-poke) 21) ((eq name '%disk-write-sector) 22)
            (t nil))
      (cond ((eq name 'cons) 51) ((eq name 'car) 52) ((eq name 'cdr) 53)
            ((eq name 'consp) 54) ((eq name 'eql) 55)
            ((eq name 'pushargn) 56) ((eq name 'loadl) 57) ((eq name 'storel) 58)
            ((eq name 'drop) 59) ((eq name 'call) 60) ((eq name 'callprim) 61)
            ((eq name 'tailcall) 62) ((eq name 'closure) 63) ((eq name 'upval) 64)
            ((eq name 'setupval) 65)
            (t nil))))

; CALLPRIM table (identical to PRIMS in src/compile.c; ABI section 4a, IDs pinned)
(defun %lcc-prim (name)
  (cond ((eq name 'stringp) 0) ((eq name 'string->list) 1) ((eq name 'list->string) 2)
        ((eq name 'string-length) 3) ((eq name 'string-ref) 4)
        ((eq name 'symbolp) 5) ((eq name 'numberp) 6)
        ((eq name 'apply) 7) ((eq name 'funcall) 8)
        ((eq name 'screen-size) 9) ((eq name 'screen-clear) 10)
        ((eq name 'screen-put-char) 11) ((eq name 'screen-write-string) 12)
        ((eq name 'read-key) 13) ((eq name 'poll-key) 14)
        ((eq name '%disk-read-sector) 15) ((eq name '%disk-byte) 16)
        ((eq name '%disk-load-file) 17) ((eq name '%disk-load-lib) 18)
        (t (%lcc-op2 name t))))

; ---- Self-contained helpers (length/reverse/consp/null are NOT Treewalk primitives) ----
(defun %lcc-len (l) (if l (+ 1 (%lcc-len (cdr l))) 0))
(defun %lcc-rev-into (l acc) (if l (%lcc-rev-into (cdr l) (cons (car l) acc)) acc))
(defun %lcc-rev (l) (%lcc-rev-into l nil))
(defun %lcc-consp (x)
  (if x (if (numberp x) nil (if (symbolp x) nil (if (stringp x) nil t))) nil))
(defun %lcc-equal (a b)
  (if (eql a b)
      t
      (if (%lcc-consp a)
          (if (%lcc-consp b)
              (if (%lcc-equal (car a) (car b)) (%lcc-equal (cdr a) (cdr b)) nil)
              nil)
          nil)))

; ---- cs accessors/constructor ----
(defun %lcc-cs (st lits maxslot fns) (cons st (cons lits (cons maxslot (cons fns nil)))))
(defun %lcc-st (cs) (car cs))
(defun %lcc-lits (cs) (car (cdr cs)))
(defun %lcc-max (cs) (car (cdr (cdr cs))))
(defun %lcc-fns (cs) (car (cdr (cdr (cdr cs)))))   ; mutierbare Box (fns-rev . zaehler)

; ---- Emission ----
(defun %lcc-emit-st (st b) (cons (cons b (car st)) (+ (cdr st) 1)))
(defun %lcc-emit (cs b)
  (%lcc-cs (%lcc-emit-st (%lcc-st cs) b) (%lcc-lits cs) (%lcc-max cs) (%lcc-fns cs)))
(defun %lcc-emit-op (cs name) (%lcc-emit cs (%lcc-op name)))
(defun %lcc-emit2 (cs name b) (%lcc-emit (%lcc-emit-op cs name) b))

; ---- Literal table (STRUCTURAL deduplication like the reference) ----
(defun %lcc-lit-find (lits-rev o n)
  (if lits-rev
      (if (%lcc-equal (car lits-rev) o)
          (- n 1)
          (%lcc-lit-find (cdr lits-rev) o (- n 1)))
      nil))

; Allocate/find a literal-table slot WITHOUT emission: -> (cs . index)
(defun %lcc-lit-slot (cs o)
  ((lambda (n)
     ((lambda (hit)
        (if hit
            (cons cs hit)
            (cons (%lcc-cs (%lcc-st cs) (cons o (%lcc-lits cs)) (%lcc-max cs) (%lcc-fns cs)) n)))
      (%lcc-lit-find (%lcc-lits cs) o n)))
   (%lcc-len (%lcc-lits cs))))

(defun %lcc-push-lit (cs o)
  ((lambda (r) (%lcc-emit2 (car r) 'pushlit (cdr r)))
   (%lcc-lit-slot cs o)))

(defun %lcc-push-value (cs o)
  (cond ((eq o nil) (%lcc-emit-op cs 'pushnil))
        ((eq o 't) (%lcc-emit-op cs 'pusht))
        ((numberp o)
         (if (and (> o -129) (< o 128))
             (%lcc-emit2 cs 'pushi8 (if (< o 0) (+ o 256) o))
             (%lcc-push-lit cs o)))
        (t (%lcc-push-lit cs o))))

; ---- One-level environment: ((name slot kind) ...) ----
(defun %lcc-env-find (e name)
  (if e
      (if (eq (car (car e)) name) (car e) (%lcc-env-find (cdr e) name))
      nil))

; ---- Levels (P3): lvls = ((lvls . uvbox) ...), youngest first;
; uvbox = (uvs-rev . n), uv = (name src via kind). Mutate uvbox with
; rplaca/rplacd because the collection grows while resolving in the middle of
; body compilation; the C analogue is cc_lvl[]. ----
(defun %lcc-top-env (lvls) (car (car lvls)))
(defun %lcc-uvbox (lvl) (cdr lvl))
(defun %lcc-with-top-env (lvls e) (cons (cons e (%lcc-uvbox (car lvls))) (cdr lvls)))

(defun %lcc-uv-index (uvs name n)
  (if uvs
      (if (eq (car (car uvs)) name) (- n 1) (%lcc-uv-index (cdr uvs) name (- n 1)))
      nil))

(defun %lcc-uv-add (box name src via kind)
  ((lambda (n)
     (progn
       (rplaca box (cons (cons name (cons src (cons via (cons kind nil)))) (car box)))
       (rplacd box (+ n 1))
       n))
   (cdr box)))

; Transitive resolve_uv analogue: resolve name as an upvalue of the TOP level,
; returning an index or nil. Deduplicate in uvbox. An outer local in the level
; below uses via=0 plus kind for the creation site; deeper references resolve
; recursively as an upvalue of the outer level and use via=1.
(defun %lcc-resolve-uv (name lvls)
  (if (cdr lvls)
      ((lambda (box)
         ((lambda (hit)
            (if hit
                hit
                ((lambda (e)
                   (if e
                       (%lcc-uv-add box name (car (cdr e)) 0 (car (cdr (cdr e))))
                       ((lambda (up)
                          (if up (%lcc-uv-add box name up 1 'l) nil))
                        (%lcc-resolve-uv name (cdr lvls)))))
                 (%lcc-env-find (%lcc-top-env (cdr lvls)) name))))
          (%lcc-uv-index (car box) name (cdr box))))
       (%lcc-uvbox (car lvls)))
      nil))

; Slot access by kind (emit_arg analogue): parameter slot<3 uses PUSHARG0+slot,
; otherwise PUSHARGN; locals use LOADL.
(defun %lcc-emit-slot (cs slot kind)
  (if (eq kind 'a)
      (if (< slot 3)
          (%lcc-emit cs (+ 11 slot))
          (%lcc-emit2 cs 'pushargn slot))
      (%lcc-emit2 cs 'loadl slot)))

; Variable access: local level -> slot; free variable -> transitive upvalue
; through OP_UPVAL; otherwise global read through PUSHLIT sym plus
; CALLPRIM 19 1, as in src/compile.c.
(defun %lcc-var (cs lvls name)
  ((lambda (e)
     (if e
         (%lcc-emit-slot cs (car (cdr e)) (car (cdr (cdr e))))
         ((lambda (uvi)
            (if uvi
                (%lcc-emit2 cs 'upval uvi)
                (%lcc-emit (%lcc-emit (%lcc-emit-op (%lcc-push-lit cs name) 'callprim) 19) 1)))
          (%lcc-resolve-uv name lvls))))
   (%lcc-env-find (%lcc-top-env lvls) name)))

; ---- Lowering: and/or/cond/when/unless -> if/let/progn forms, identical to
; both the reference compiler and our prelude macros. Single-clause or/cond
; binds the test value in a gensym temporary; the reference allocates a real
; slot for it. list/gensym are Treewalk primitives. ----
(defun %lcc-lower-and (args)
  (if args
      (if (cdr args)
          (list 'if (car args) (cons 'and (cdr args)) nil)
          (car args))
      't))

(defun %lcc-lower-or (args)
  (if args
      (if (cdr args)
          ((lambda (tmp)
             (list 'let (list (list tmp (car args)))
                   (list 'if tmp tmp (cons 'or (cdr args)))))
           (gensym))
          (car args))
      nil))

(defun %lcc-lower-when (args) (list 'if (car args) (cons 'progn (cdr args)) nil))
(defun %lcc-lower-unless (args) (list 'if (car args) nil (cons 'progn (cdr args))))

(defun %lcc-lower-cond (cls)
  (if cls
      ((lambda (cl rest)
         (if (eq (car cl) 't)
             (if (cdr cl) (cons 'progn (cdr cl)) 't)   ; t-Klausel = direktes else (Referenz!)
             (if (cdr cl)
             (list 'if (car cl) (cons 'progn (cdr cl)) (cons 'cond rest))
             ((lambda (tmp)
                (list 'let (list (list tmp (car cl)))
                      (list 'if tmp tmp (cons 'cond rest))))
              (gensym)))))
       (car cls) (cdr cls))
      nil))

; ---- Sequence/progn ----
(defun %lcc-seq (cs lvls body)
  (if body
      (if (cdr body)
          (%lcc-seq (%lcc-emit-op (%lcc-expr cs lvls (car body)) 'drop) lvls (cdr body))
          (%lcc-expr cs lvls (car body)))
      (%lcc-push-value cs nil)))

; ---- if (rel8 patching) ----
(defun %lcc-rel8 (d)
  (if (< d -128)
      (%lcc-error-do-body-too-big)
      (if (> d 127) (%lcc-error-do-body-too-big) (mod d 256))))
(defun %lcc-if (cs lvls args)
  ((lambda (cs2)
     ((lambda (hole1 len1)
        ((lambda (cs4)
           ((lambda (hole2 len2)
              ((lambda (cs5)
                 (progn
                   (rplaca hole1 (%lcc-rel8 (- len2 len1)))
                   (rplaca hole2 (%lcc-rel8 (- (cdr (%lcc-st cs5)) len2)))
                   cs5))
               (%lcc-expr cs4 lvls (if (cdr (cdr args)) (car (cdr (cdr args))) nil))))
            (car (%lcc-st cs4)) (cdr (%lcc-st cs4))))
         (%lcc-emit (%lcc-emit-op (%lcc-expr cs2 lvls (car (cdr args))) 'jmprel) 0)))
      (car (%lcc-st cs2)) (cdr (%lcc-st cs2))))
   (%lcc-emit (%lcc-emit-op (%lcc-expr cs lvls (car args)) 'jfalserel) 0)))

; ---- NATIVE do/do*/dotimes/dolist (C-phase fix (b), d097468): a real loop
; through backward JMPREL gives a CONSTANT stack. The macro templates used
; funcall recursion and consumed about 15 VM slots per iteration, while blob
; macros do not yet exist on the device. JMPREL is int8; test+result+body+steps
; over about 120 B fail LOUDLY. do uses parallel binds/steps (push all values,
; then STOREL in reverse); do* is sequential. dotimes/dolist are sugar whose
; count/list gensym temporary is evaluated ONCE. ----
(defun %lcc-expr-do (cs lvls op args)   ; Dispatch-Stufe (255-B-Gate: sf2 war 263 B)
  (cond ((eq op 'do)   (%lcc-do cs lvls args nil))
        ((eq op 'do*)  (%lcc-do cs lvls args t))
        ((eq op 'dotimes) (%lcc-do cs lvls (%lcc-lower-dotimes (car args) (cdr args)) nil))
        ((eq op 'dolist) (%lcc-do cs lvls (%lcc-lower-dolist (car args) (cdr args)) nil))
        (t (%lcc-while cs lvls args))))
(defun %lcc-do-p (op)
  (cond ((eq op 'do) t) ((eq op 'do*) t) ((eq op 'dotimes) t)
        ((eq op 'dolist) t) ((eq op 'while) t) (t nil)))
(defun %lcc-proper-list-p (x)
  (if x (if (%lcc-consp x) (%lcc-proper-list-p (cdr x)) nil) t))
(defun %lcc-while (cs lvls args)
  (if (and (%lcc-consp args) (%lcc-proper-list-p args))
      (let ((top (cdr (%lcc-st cs))))
        (let ((cs2 (%lcc-emit
                    (%lcc-emit-op (%lcc-expr cs lvls (car args)) 'jfalserel) 0)))
          (let ((hexit (car (%lcc-st cs2))) (lexit (cdr (%lcc-st cs2))))
            (let ((cs3 (%lcc-do-body cs2 lvls (cdr args))))
              (let ((cs4 (%lcc-emit-op cs3 'jmprel)))
                (let ((d (- top (+ (cdr (%lcc-st cs4)) 1))))
                  (let ((cs5 (%lcc-emit cs4 (%lcc-rel8 d))))
                    (rplaca hexit
                            (%lcc-rel8 (- (cdr (%lcc-st cs5)) lexit)))
                    (%lcc-emit-op cs5 'pushnil))))))))
      (%lcc-error-invalid-parameter-list)))
(defun %lcc-do-norm (bs)
  (if bs
      (cons (if (%lcc-consp (car bs)) (car bs) (cons (car bs) nil))
            (%lcc-do-norm (cdr bs)))
      nil))
(defun %lcc-do-body (cs lvls body)
  (if body
      (%lcc-do-body (%lcc-emit-op (%lcc-expr cs lvls (car body)) 'drop) lvls (cdr body))
      cs))
(defun %lcc-storel-name (cs lvls name)
  (%lcc-emit2 cs 'storel (car (cdr (%lcc-env-find (%lcc-top-env lvls) name)))))
(defun %lcc-do-steps (cs lvls bs star)
  (if bs
      (if (cdr (cdr (car bs)))
          ((lambda (cs2)
             (%lcc-do-steps (if star (%lcc-storel-name cs2 lvls (car (car bs))) cs2)
                            lvls (cdr bs) star))
           (%lcc-expr cs lvls (car (cdr (cdr (car bs))))))
          (%lcc-do-steps cs lvls (cdr bs) star))
      cs))
(defun %lcc-do-store-rev (cs lvls bs)
  (if bs
      ((lambda (cs2)
         (if (cdr (cdr (car bs))) (%lcc-storel-name cs2 lvls (car (car bs))) cs2))
       (%lcc-do-store-rev cs lvls (cdr bs)))
      cs))
(defun %lcc-do-loop (cs1 lvls2 bs endc body star top)
  (let ((cs2 (%lcc-emit (%lcc-emit-op (%lcc-expr cs1 lvls2 (car endc)) 'jfalserel) 0)))
    (let ((hbody (car (%lcc-st cs2))) (lbody (cdr (%lcc-st cs2))))
      (let ((cs3 (%lcc-emit (%lcc-emit-op
                             (%lcc-seq cs2 lvls2 (if (cdr endc) (cdr endc) (cons nil nil)))
                             'jmprel) 0)))
        (let ((hexit (car (%lcc-st cs3))) (lexit (cdr (%lcc-st cs3))))
          (let ((cs5 (if star
                         (%lcc-do-steps (%lcc-do-body cs3 lvls2 body) lvls2 bs t)
                         (%lcc-do-store-rev (%lcc-do-steps (%lcc-do-body cs3 lvls2 body)
                                                           lvls2 bs nil)
                                            lvls2 bs))))
            (let ((cs6 (%lcc-emit-op cs5 'jmprel)))
              (let ((d (- top (+ (cdr (%lcc-st cs6)) 1))))
                (let ((cs7 (%lcc-emit cs6 (%lcc-rel8 d))))
                  (rplaca hbody (%lcc-rel8 (- lexit lbody)))
                  (rplaca hexit
                          (%lcc-rel8 (- (cdr (%lcc-st cs7)) lexit)))
                  cs7)))))))))
(defun %lcc-do (cs lvls args star)
  (let ((bs (%lcc-do-norm (car args))))
    (let ((r (%lcc-let-binds cs lvls lvls bs star)))
      (%lcc-do-loop (car r) (cdr r) bs (car (cdr args))
                    (cdr (cdr args)) star (cdr (%lcc-st (car r)))))))
(defun %lcc-lower-dotimes (spec body)
  (let ((v (car spec)) (n (gensym)))
    (cons (list (list v 0 (list '+ v 1)) (list n (car (cdr spec))))
          (cons (cons (list '>= v n)
                      (if (cdr (cdr spec)) (cons (car (cdr (cdr spec))) nil) nil))
                body))))
(defun %lcc-lower-dolist (spec body)
  (let ((xs (gensym)))
    (cons (list (list xs (car (cdr spec)) (list 'cdr xs)))
          (cons (cons (list 'eq xs nil)
                      (if (cdr (cdr spec)) (cons (car (cdr (cdr spec))) nil) nil))
                (cons (cons 'let (cons (list (list (car spec) (list 'car xs))) body)) nil)))))

; ---- let/let*: initializers plus STOREL into consecutive slots (monotonic,
; no reuse). star=nil compiles initializers in the OUTER levels (parallel let);
; star=t uses the growing levels (let*). Returns (cs . levels-with-bindings).
(defun %lcc-let-binds (cs lvls0 lvls bs star)
  (if bs
      ((lambda (name init)
         ((lambda (slot)
            ((lambda (cs2)
               (%lcc-let-binds
                (%lcc-cs (%lcc-st cs2) (%lcc-lits cs2) (+ slot 1) (%lcc-fns cs2))
                lvls0
                (%lcc-with-top-env lvls
                                   (cons (cons name (cons slot (cons 'l nil)))
                                         (%lcc-top-env lvls)))
                (cdr bs) star))
             (%lcc-emit2 (%lcc-expr cs (if star lvls lvls0) init) 'storel slot)))
          (%lcc-max cs)))
       (if (%lcc-consp (car bs)) (car (car bs)) (car bs))
       (if (%lcc-consp (car bs)) (car (cdr (car bs))) nil))
      (cons cs lvls)))

(defun %lcc-let (cs lvls args star)
  ((lambda (r)
     (%lcc-seq (car r) (cdr r) (cdr args)))
   (%lcc-let-binds cs lvls lvls (car args) star)))

; ---- setq: local/parameter -> expr + STOREL + LOADL (reload the value, like
; the reference); unbound -> GLOBAL through PUSHLIT sym, expr, CALLPRIM 20 2,
; as in src/compile.c. ----
(defun %lcc-setq (cs lvls args)
  ((lambda (e)
     (if e
         (%lcc-emit2 (%lcc-emit2 (%lcc-expr cs lvls (car (cdr args)))
                                 'storel (car (cdr e)))
                     'loadl (car (cdr e)))
         ((lambda (uvi)
            (if uvi
                (%lcc-emit2 (%lcc-emit2 (%lcc-expr cs lvls (car (cdr args)))
                                        'setupval uvi)
                            'upval uvi)
                (%lcc-emit (%lcc-emit (%lcc-emit-op (%lcc-expr (%lcc-push-lit cs (car args)) lvls (car (cdr args)))
                                                    'callprim)
                                      20)
                           2)))
          (%lcc-resolve-uv (car args) lvls))))
   (%lcc-env-find (%lcc-top-env lvls) (car args))))

; ---- Calls: arguments first, then CALLPRIM pid n or CALL <callee-lit> n ----
(defun %lcc-args (cs lvls args n)
  (if args
      (%lcc-args (%lcc-expr cs lvls (car args)) lvls (cdr args) (+ n 1))
      (cons cs n)))

(defun %lcc-call (cs lvls op args)
  ((lambda (r)
     ((lambda (pid)
        (if pid
            (%lcc-emit (%lcc-emit2 (car r) 'callprim pid) (cdr r))
            ((lambda (rl)
               (%lcc-emit (%lcc-emit2 (car rl) 'call (cdr rl)) (cdr r)))
             (%lcc-lit-slot (car r) op))))
      (%lcc-prim op)))
   (%lcc-args cs lvls args 0)))

; ---- P3: lambda as a VALUE -> compile helper function and emit creation site ----
; The helper enters the fns box in completion order, innermost first, so the
; run harness can assemble in that order and markers always point backward.
; Reference semantics: non-tail body plus RET; compile_lambda_helper uses
; compile_sequence.
(defun %lcc-emit-uv-values (cs uvs)
  (if uvs
      ((lambda (uv)
         (%lcc-emit-uv-values
          (if (eq (car (cdr (cdr uv))) 1)
              (%lcc-emit2 cs 'upval (car (cdr uv)))
              (%lcc-emit-slot cs (car (cdr uv)) (car (cdr (cdr (cdr uv))))))
          (cdr uvs)))
       (car uvs))
      cs))

(defun %lcc-lambda (cs lvls form)
  ((lambda (params body)
     ((lambda (nargs uvbox)
        ((lambda (cs2)
           ; Finish helper function and append it to the box; idx is the
           ; counter BEFORE appending.
           ((lambda (fnobj box)
              ((lambda (idx)
                 (progn
                   (rplaca box (cons fnobj (car box)))
                   (rplacd box (+ idx 1))
                   ; Creation site in the OUTER cs: push upvalue values plus
                   ; CLOSURE/PUSHLIT.
                   ((lambda (marker uvs n)
                      (if (> n 0)
                          ((lambda (cs3)
                             ((lambda (r)
                                (%lcc-emit (%lcc-emit2 (car r) 'closure (cdr r)) n))
                              (%lcc-lit-slot cs3 marker)))
                           (%lcc-emit-uv-values cs uvs))
                          (%lcc-push-lit cs marker)))
                    (cons '%lcc-helper (cons idx nil))
                    (%lcc-rev (car uvbox))
                    (cdr uvbox))))
               (cdr box)))
            (%lcc-finish (%lcc-emit-op (%lcc-seq cs2
                                                 (cons (cons (%lcc-params-env params 0 nil) uvbox) lvls)
                                                 body)
                                       'ret)
                         nargs)
            (%lcc-fns cs)))
         ; Fresh inner cs: private st/lits/maxslot, SHARED fns box.
         (%lcc-cs (cons nil 0) nil nargs (%lcc-fns cs))))
      (%lcc-len params) (cons nil 0)))
   (car (cdr form)) (cdr (cdr form))))

; Immediate lambda ((lambda (p..) body) a..) equals
; (let ((p a)..) body), matching reference lowering.
(defun %lcc-imm-binds (ps as acc)
  (if ps
      (%lcc-imm-binds (cdr ps) (if as (cdr as) nil)
                      (cons (cons (car ps) (cons (if as (car as) nil) nil)) acc))
      (%lcc-rev acc)))

; ---- P4: macro expansion plus quasiquote lowering ----
; lcc runs ON a Lisp system (Treewalk in the harness), so macros expand by
; asking the HOST: (function-kind op)='macro plus (macroexpand-1 form).
; On the device (P6), funcall of a compiled BCODE expander replaces the same
; seam; see docs/self-hosting-plan.md.
(defun %lcc-macro-p (op)
  (if (symbolp op) (eq (function-kind op) 'macro) nil))

; quasiquote -> cons/append forms. NESTED CL semantics use d as depth: inner `
; increments it and , decrements it; evaluation occurs only at d=1, otherwise
; syntax is REBUILT as data. This mirrors Treewalk qq in eval.c, with a macro
; corpus as drift guard. For d=1 input without nested `, output is
; BYTE-IDENTICAL to the old single-level version, as checked by the byte oracle.
(defun %lcc-qq-d (x d)
  (cond ((if (%lcc-consp x) (eq (car x) 'unquote) nil)
         (if (= d 1)
             (car (cdr x))
             (list 'list (list 'quote 'unquote) (%lcc-qq-d (car (cdr x)) (- d 1)))))
        ((if (%lcc-consp x) (eq (car x) 'quasiquote) nil)
         (list 'list (list 'quote 'quasiquote) (%lcc-qq-d (car (cdr x)) (+ d 1))))
        ((%lcc-consp x)
         (if (if (%lcc-consp (car x)) (eq (car (car x)) 'unquote-splicing) nil)
             (if (= d 1)
                 (list 'append (car (cdr (car x))) (%lcc-qq-d (cdr x) d))
                 (list 'cons
                       (list 'list (list 'quote 'unquote-splicing)
                             (%lcc-qq-d (car (cdr (car x))) (- d 1)))
                       (%lcc-qq-d (cdr x) d)))
             (list 'cons (%lcc-qq-d (car x) d) (%lcc-qq-d (cdr x) d))))
        (t (list 'quote x))))
(defun %lcc-lower-qq (x) (%lcc-qq-d x 1))

; ---- Expression dispatch ----
(defun %lcc-expr (cs lvls form)
  (cond ((numberp form) (%lcc-push-value cs form))
        ((eq form nil) (%lcc-push-value cs nil))
        ((eq form 't) (%lcc-push-value cs 't))
        ((symbolp form) (%lcc-var cs lvls form))
        ((%lcc-consp form)
         (%lcc-expr-form cs lvls (car form) (cdr form) form))
        (t (%lcc-push-lit cs form))))   ; String-Literal u. ae.

; Dispatch cascade split by object size, each <=255 B:
; form -> sf1 -> sf2 -> ops -> ops2
(defun %lcc-expr-form (cs lvls op args form)
  (cond ((%lcc-consp op)
         (if (eq (car op) 'lambda)
             (%lcc-expr cs lvls
                        (cons 'let (cons (%lcc-imm-binds (car (cdr op)) args nil)
                                    (cdr (cdr op)))))
             (%lcc-push-value cs nil)))
        ((eq op 'lambda) (%lcc-lambda cs lvls form))
        ((eq op 'quote) (%lcc-push-value cs (car args)))
        ((eq op 'progn) (%lcc-seq cs lvls args))
        ((eq op 'if)    (%lcc-if cs lvls args))
        ((eq op 'let)   (%lcc-let cs lvls args nil))
        ((eq op 'let*)  (%lcc-let cs lvls args t))
        ((eq op 'setq)  (%lcc-setq cs lvls args))
        (t (%lcc-expr-sf2 cs lvls op args form))))

(defun %lcc-expr-sf2 (cs lvls op args form)
  (cond ((eq op 'and)   (%lcc-expr cs lvls (%lcc-lower-and args)))
        ((eq op 'or)    (%lcc-expr cs lvls (%lcc-lower-or args)))
        ((eq op 'cond)  (%lcc-expr cs lvls (%lcc-lower-cond args)))
        ((eq op 'when)  (%lcc-expr cs lvls (%lcc-lower-when args)))
        ((eq op 'unless) (%lcc-expr cs lvls (%lcc-lower-unless args)))
        ((eq op 'quasiquote) (%lcc-expr cs lvls (%lcc-lower-qq (car args))))
        ((%lcc-do-p op) (%lcc-expr-do cs lvls op args))
        ((eq op 'function)
         (if (%lcc-consp (car args))
             (%lcc-lambda cs lvls (car args))
             (%lcc-push-lit cs (car args))))
        (t (%lcc-expr-ops cs lvls op args form))))

; Part 2 of expression dispatch (object-size split): opcode forms, macros, and
; generic calls. Exact-two-argument predicate for the opcode fast path of
; VARIADIC operations.
(defun %lcc-2args-p (args)
  (if (%lcc-consp args)
      (if (%lcc-consp (cdr args)) (eq (cdr (cdr args)) nil) nil)
      nil))

; Variadic operations: opcode name ONLY as a fast-path candidate, with the
; arity guard in %lcc-expr-ops.
(defun %lcc-vop (op)
  (cond ((eq op '+) 'add) ((eq op '-) 'sub) ((eq op '*) 'mul) ((eq op '/) 'div)
        ((eq op '<) 'less) ((eq op '>) 'greater) ((eq op '=) 'eq) (t nil)))

; Opcode fast path ONLY with exactly two arguments. Variadic and unary cases
; use a GENERIC call to the variadic bridge (Ein suite) or the C primitive
; (host bridge): ONE semantic path, with no more silent argument dropping.
; (- 9 2 3) once returned 7 instead of 4, found by the M3 hardware self-test.
; eq/eql remain unguarded because exact-two is also their primitive semantics
; (extra arguments are ignored).
(defun %lcc-expr-ops (cs lvls op args form)
  ((lambda (vop)
     (cond ((if vop (%lcc-2args-p args) nil) (%lcc-binary cs lvls args vop))
           (vop (%lcc-call cs lvls op args))
           ((eq op 'eq)  (%lcc-binary cs lvls args 'eq))
           ((eq op 'eql) (%lcc-binary cs lvls args 'eql))
           (t (%lcc-expr-ops2 cs lvls op args form))))
   (%lcc-vop op)))

(defun %lcc-expr-ops2 (cs lvls op args form)
  (cond ((eq op 'mod) (%lcc-binary cs lvls args 'mod))
        ((eq op 'remainder) (%lcc-binary cs lvls args 'remainder))
        ((eq op 'cons) (%lcc-binary cs lvls args 'cons))
        ((eq op 'car)  (%lcc-unary cs lvls args 'car))
        ((eq op 'cdr)  (%lcc-unary cs lvls args 'cdr))
        ((eq op 'consp) (%lcc-unary cs lvls args 'consp))
        ((eq op 'not)  (%lcc-unary cs lvls args 'not))
        ((eq op 'null) (%lcc-unary cs lvls args 'not))
        ((%lcc-macro-p op) (%lcc-expr cs lvls (macroexpand-1 form)))
        (t (%lcc-call cs lvls op args))))

(defun %lcc-binary (cs lvls args opname)
  (%lcc-emit-op (%lcc-expr (%lcc-expr cs lvls (car args)) lvls (car (cdr args))) opname))

(defun %lcc-unary (cs lvls args opname)
  (%lcc-emit-op (%lcc-expr cs lvls (car args)) opname))

; ---- Tail compilation (ONLY in defun context; reference: defun_tail=True) ----
; Rules observed empirically against the reference compiler on 2026-07-05:
;  - generic CALL in tail position -> TAILCALL(62) WITHOUT a following RET,
;    including calls to other functions
;  - CALLPRIM/opcode forms in tail position -> normal form plus RET
;  - if in tail position: NO JMPREL; each branch terminates itself with
;    RET or TAILCALL
;  - in progn/let/let*, only the LAST form is in tail position
(defun %lcc-sf-p (op)
  (cond ((eq op 'quote) t) ((eq op 'progn) t) ((eq op 'if) t) ((eq op 'let) t)
        ((eq op 'let*) t) ((eq op 'setq) t) ((eq op 'function) t) ((eq op 'lambda) t) ((eq op 'quasiquote) t)
        ((eq op 'and) t) ((eq op 'or) t) ((eq op 'cond) t)
        ((eq op 'when) t) ((eq op 'unless) t)
        ((eq op 'do) t) ((eq op 'do*) t) ((eq op 'dotimes) t) ((eq op 'dolist) t) (t nil)))

(defun %lcc-opform-p (op)
  (cond ((eq op '+) t) ((eq op '-) t) ((eq op '*) t) ((eq op '/) t)
        ((eq op '<) t) ((eq op '>) t) ((eq op '=) t) ((eq op 'eq) t) ((eq op 'eql) t)
        ((eq op 'mod) t) ((eq op 'remainder) t) ((eq op 'cons) t) ((eq op 'car) t)
        ((eq op 'cdr) t) ((eq op 'consp) t) ((eq op 'not) t) ((eq op 'null) t) (t nil)))

; Does op use the generic CALL rule (not special form, opcode, or primitive)?
(defun %lcc-callform-p (op)
  (if (%lcc-sf-p op) nil (if (%lcc-opform-p op) nil (if (%lcc-prim op) nil t))))

(defun %lcc-tailcall (cs lvls op args)
  ((lambda (r)
     ((lambda (rl)
        (%lcc-emit (%lcc-emit2 (car rl) 'tailcall (cdr rl)) (cdr r)))
      (%lcc-lit-slot (car r) op)))
   (%lcc-args cs lvls args 0)))

(defun %lcc-tail-seq (cs lvls body)
  (if body
      (if (cdr body)
          (%lcc-tail-seq (%lcc-emit-op (%lcc-expr cs lvls (car body)) 'drop) lvls (cdr body))
          (%lcc-tail cs lvls (car body)))
      (%lcc-emit-op (%lcc-push-value cs nil) 'ret)))

(defun %lcc-tail-let (cs lvls args star)
  ((lambda (r)
     (%lcc-tail-seq (car r) (cdr r) (cdr args)))
   (%lcc-let-binds cs lvls lvls (car args) star)))

; tail-if: branches terminate themselves, so only ONE patch is needed
; (JFALSEREL to the start of else).
(defun %lcc-tail-if (cs lvls args)
  ((lambda (cs2)
     ((lambda (hole1 len1)
        ((lambda (cs3)
           (progn
             (rplaca hole1 (- (cdr (%lcc-st cs3)) len1))
             (%lcc-tail cs3 lvls (if (cdr (cdr args)) (car (cdr (cdr args))) nil))))
         (%lcc-tail cs2 lvls (car (cdr args)))))
      (car (%lcc-st cs2)) (cdr (%lcc-st cs2))))
   (%lcc-emit (%lcc-emit-op (%lcc-expr cs lvls (car args)) 'jfalserel) 0)))

(defun %lcc-tail (cs lvls form)
  (if (%lcc-consp form)
      ((lambda (op args)
         (cond ((%lcc-consp op)
                (if (eq (car op) 'lambda)
                    (%lcc-tail cs lvls
                               (cons 'let (cons (%lcc-imm-binds (car (cdr op)) args nil)
                                           (cdr (cdr op)))))
                    (%lcc-emit-op (%lcc-expr cs lvls form) 'ret)))
               ((eq op 'if)    (%lcc-tail-if cs lvls args))
               ((eq op 'progn) (%lcc-tail-seq cs lvls args))
               ((eq op 'let)   (%lcc-tail-let cs lvls args nil))
               ((eq op 'let*)  (%lcc-tail-let cs lvls args t))
               (t (%lcc-tail2 cs lvls op args form))))
       (car form) (cdr form))
      (%lcc-emit-op (%lcc-expr cs lvls form) 'ret)))

; Part 2 of tail dispatch (object-size split): lowerings, macros, tailcall/RET.
(defun %lcc-tail2 (cs lvls op args form)
  (cond ((eq op 'and)   (%lcc-tail cs lvls (%lcc-lower-and args)))
        ((eq op 'or)    (%lcc-tail cs lvls (%lcc-lower-or args)))
        ((eq op 'cond)  (%lcc-tail cs lvls (%lcc-lower-cond args)))
        ((eq op 'when)  (%lcc-tail cs lvls (%lcc-lower-when args)))
        ((eq op 'unless) (%lcc-tail cs lvls (%lcc-lower-unless args)))
        ((eq op 'quasiquote) (%lcc-tail cs lvls (%lcc-lower-qq (car args))))
        ; do family BEFORE macro-p: native lowering with a constant stack wins
        ; over any legacy macro of the same name (stdlib control templates
        ; using funcall recursion).
        ((%lcc-do-p op) (%lcc-emit-op (%lcc-expr-do cs lvls op args) 'ret))
        ((%lcc-macro-p op) (%lcc-tail cs lvls (macroexpand-1 form)))
        ((%lcc-callform-p op) (%lcc-tailcall cs lvls op args))
        (t (%lcc-emit-op (%lcc-expr cs lvls form) 'ret))))

; ---- Parameters -> levels ((name slot a) ...), slots 0.. ----
(defun %lcc-params-env (ps slot acc)
  (if ps
      (%lcc-params-env (cdr ps) (+ slot 1)
                       (cons (cons (car ps) (cons slot (cons 'a nil))) acc))
      acc))

; ---- Public seam: (lambda (params) body...) -> CodeObject components ----
; Returns (nargs nlocals flags littab bytes), with literal table and bytes in
; allocation/emission order.
(defun %lcc-finish (cs nargs)
  (cons nargs
        (cons (- (%lcc-max cs) nargs)
              (cons 0
                    (cons (%lcc-rev (%lcc-lits cs))
                          (cons (%lcc-rev (car (%lcc-st cs))) nil))))))

; (defun name (params) body...) -> tail mode with TAILCALL/self-terminating branches
(defun %lcc-compile-defun (params body fns)
  ((lambda (nargs)
     (%lcc-finish (%lcc-tail-seq (%lcc-cs (cons nil 0) nil nargs fns)
                                 (cons (cons (%lcc-params-env params 0 nil) (cons nil 0)) nil)
                                 body)
                  nargs))
   (%lcc-len params)))

; Output: LIST of functions in assembly order: helpers innermost first, MAIN
; LAST. Helper references in literal tables are markers
; (%lcc-helper <idx>), where idx is the position in this list.
(defun lcc-compile-obj (form)
  ((lambda (fns)
     ((lambda (main)
        (%lcc-rev (cons main (car fns))))
      (if (eq (car form) 'defun)
          (%lcc-compile-defun (car (cdr (cdr form))) (cdr (cdr (cdr form))) fns)
          (%lcc-compile-lambda form fns))))
   (cons nil 0)))

(defun %lcc-compile-lambda (form fns)
  ((lambda (params body)
     ((lambda (nargs)
        (%lcc-finish (%lcc-emit-op (%lcc-seq (%lcc-cs (cons nil 0) nil nargs fns)
                                             (cons (cons (%lcc-params-env params 0 nil) (cons nil 0)) nil)
                                             body)
                                   'ret)
                     nargs))
      (%lcc-len params)))
   (car (cdr form)) (cdr (cdr form))))

; Convenience seams for expressions, P0-compatible: (lambda () expr)
(defun lcc-compile (form)
  (car (cdr (cdr (cdr (cdr (lcc-compile-obj (cons 'lambda (cons nil (cons form nil))))))))))

(defun lcc-lits (form)
  (car (cdr (cdr (cdr (lcc-compile-obj (cons 'lambda (cons nil (cons form nil)))))))))

; ---- P6: lcc-first REPL core (docs/lcc-device-design.md) ----
; (lcc-run form): defmacro compiles the expander as a lambda, installs it
; anonymously, then attaches it to the symbol as a BCODE macro through
; %set-macro (C seam, convergence M2); eval_env no longer appears in the
; defmacro path. defun compiles and installs under its name through the
; lcc-install C seam. An expression compiles as (lambda () form), installs
; anonymously, and runs through funcall; the eval-to-VM bridge executes the
; BCODE value.
(defun %lcc-wrap (form) (cons 'lambda (cons nil (cons form nil))))

; 1.1-C1 shelf export.  The returned CodeObject list is ordinary detached heap
; data: the resident coordinator retires this compiler tier before handing the
; value to the already-proven lcc-install transaction.
(defun %c2-compile-form (form)
  (cond ((if (%lcc-consp form) (eq (car form) 'defmacro) nil)
         (lcc-compile-obj (cons 'lambda (cdr (cdr form)))))
        ((if (%lcc-consp form) (eq (car form) 'defun) nil)
         (lcc-compile-obj form))
        (t (lcc-compile-obj (%lcc-wrap form)))))

(defun lcc-run (form)
  (cond ((if (%lcc-consp form) (eq (car form) 'defmacro) nil)
         (%set-macro (car (cdr form))
                     (lcc-install (lcc-compile-obj (cons 'lambda (cdr (cdr form)))) nil)))
        ((if (%lcc-consp form) (eq (car form) 'defun) nil)
         (lcc-install (lcc-compile-obj form) (car (cdr form))))
        ; Expression: name=t denotes a TRANSIENT main. lcc-install runs it
        ; immediately and returns the VALUE, with no funcall and no
        ; region/directory leak per input (M4 finding).
        (t (lcc-install (lcc-compile-obj (%lcc-wrap form)) t))))
