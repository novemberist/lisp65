; Dialect-v2 emitter profile. The frozen v1 LCC remains byte-identical; loading
; this source replaces v2-only lambda-list/CodeObject construction and removed
; source-operation dispatch. Bit 1 is CO_FLAG_STRICT_ARITY.

; Complete v2 override: Prim-IDs 1/2/26/27 are permanent tombstones in this
; profile. The remaining %string-* codecs are compiler-internal and absent
; from the public dialect surface despite having stable CALLPRIM identities.
(defun %lcc-v2-prim2 (name)
  (cond ((eq name 'symbol-value) 19) ((eq name 'set-symbol-value) 20)
        ((eq name '%disk-poke) 21) ((eq name '%disk-write-sector) 22)
        ((eq name 'nreverse) 23) ((eq name 'rplaca) 24)
        ((eq name 'rplacd) 25)
        ((eq name '%string-codes) 28) ((eq name '%string-from-codes) 29)
        (t (%lcc-v2-prim3 name))))

(defun %lcc-v2-prim3 (name)
  (cond ((eq name '%cs-read-open) 30) ((eq name '%fasl-read-form) 31)
        ((eq name '%fasl-stage) 32) ((eq name '%fasl-stage-get) 33)
        ((eq name '%set-macro) 35)
        ((eq name 'function-kind) 36) ((eq name 'gensym) 37)
        ((eq name 'lcc-install) 38) ((eq name 'macroexpand-1) 39)
        ((eq name 'prin1) 41)
        (t (%lcc-v2-prim4 name))))

(defun %lcc-v2-prim4 (name)
  (cond ((eq name 'symbol-count) 42) ((eq name 'symbol-max) 43)
        ((eq name 'symbol-name) 44) ((eq name 'write-char) 45)
        ((eq name '%fasl-error-entries-overflow) 46)
        ((eq name '%fasl-error-nodes-overflow) 47)
        ((eq name '%fasl-error-not-a-defun) 48)
        ((eq name '%fasl-error-output-overflow) 49)
        ((eq name '%fasl-error-patches-overflow) 50)
        ((eq name '%fasl-error-strings-overflow) 51)
        ((eq name '%fasl-error-too-many-helpers) 52)
        ((eq name '%fasl-error-unsupported-literal) 53)
        ((eq name '%fasl-error-window-overflow) 54)
        ((eq name '%lcc-error-do-body-too-big) 55)
        ((eq name '%lcc-error-invalid-parameter-list) 56)
        ((eq name 'boundp) 57)
        ((eq name '%list-malformed-error) 58)
        ((eq name 'set) 59)
        ((eq name 'key-event) 60)
        ((eq name 'peek) 61)
        ((eq name 'poke) 62)
        (t nil)))

(defun %lcc-prim (name)
  (cond ((eq name 'stringp) 0)
        ((eq name 'string-length) 3) ((eq name 'string-ref) 4)
        ((eq name 'symbolp) 5) ((eq name 'numberp) 6)
        ((eq name 'apply) 7) ((eq name 'funcall) 8)
        ((eq name 'screen-size) 9) ((eq name 'screen-clear) 10)
        ((eq name 'screen-put-char) 11) ((eq name 'screen-write-string) 12)
        ((eq name 'read-key) 13) ((eq name 'poll-key) 14)
        ((eq name '%disk-read-sector) 15) ((eq name '%disk-byte) 16)
        ((eq name '%disk-load-file) 17) ((eq name '%disk-load-lib) 18)
        (t (%lcc-v2-prim2 name))))

(defun %lcc-finish (cs nargs)
  (cons nargs
        (cons (- (%lcc-max cs) nargs)
              (cons 2
                    (cons (%lcc-rev (%lcc-lits cs))
                          (cons (%lcc-rev (car (%lcc-st cs))) nil))))))

; v2 lambda lists are deliberately small: bare symbols, with optional and
; rest markers in that order. The parsed shape is (fixed optional-count rest),
; where fixed contains the required and optional parameter names.
(defun %lcc-v2-param-p (x)
  (if x
      (if (symbolp x)
          (if (eq x '&optional) nil (if (eq x '&rest) nil t))
          nil)
      nil))

(defun %lcc-v2-param-seen-p (x seen)
  (if seen
      (if (eq x (car seen)) t (%lcc-v2-param-seen-p x (cdr seen)))
      nil))

(defun %lcc-v2-param-error ()
  (%lcc-error-invalid-parameter-list))

(defun %lcc-v2-param-optional (ps in-optional fixed optional seen)
  (if in-optional
      (%lcc-v2-param-error)
      (%lcc-v2-params-walk (cdr ps) t fixed optional seen)))

(defun %lcc-v2-param-rest (ps fixed optional seen)
  (if (cdr ps)
      (if (cdr (cdr ps))
          (%lcc-v2-param-error)
          ((lambda (rest)
             (if (%lcc-v2-param-p rest)
                 (if (%lcc-v2-param-seen-p rest seen)
                     (%lcc-v2-param-error)
                     (list (%lcc-rev fixed) optional rest))
                 (%lcc-v2-param-error)))
           (car (cdr ps))))
      (%lcc-v2-param-error)))

(defun %lcc-v2-param-add (p ps in-optional fixed optional seen)
  (if (%lcc-v2-param-p p)
      (if (%lcc-v2-param-seen-p p seen)
          (%lcc-v2-param-error)
          (if (and in-optional (> optional 62))
              (%lcc-v2-param-error)
              (%lcc-v2-params-walk
               (cdr ps) in-optional (cons p fixed)
               (if in-optional (+ optional 1) optional)
               (cons p seen))))
      (%lcc-v2-param-error)))

(defun %lcc-v2-param-step (p ps in-optional fixed optional seen)
  (cond ((eq p '&optional)
         (%lcc-v2-param-optional ps in-optional fixed optional seen))
        ((eq p '&rest) (%lcc-v2-param-rest ps fixed optional seen))
        (t (%lcc-v2-param-add p ps in-optional fixed optional seen))))

(defun %lcc-v2-params-walk (ps in-optional fixed optional seen)
  (if ps
      (%lcc-v2-param-step (car ps) ps in-optional fixed optional seen)
      (list (%lcc-rev fixed) optional nil)))

(defun %lcc-v2-params (ps)
  (%lcc-v2-params-walk ps nil nil 0 nil))

(defun %lcc-v2-nargs (spec) (%lcc-len (car spec)))
(defun %lcc-v2-optional (spec) (car (cdr spec)))
(defun %lcc-v2-rest (spec) (car (cdr (cdr spec))))

(defun %lcc-v2-max0 (spec)
  (+ (%lcc-v2-nargs spec) (if (%lcc-v2-rest spec) 1 0)))

(defun %lcc-v2-env (spec)
  ((lambda (env)
     (if (%lcc-v2-rest spec)
         (cons (cons (%lcc-v2-rest spec)
                     (cons (%lcc-v2-nargs spec) (cons 'l nil)))
               env)
         env))
   (%lcc-params-env (car spec) 0 nil)))

(defun %lcc-v2-finish (cs spec)
  ((lambda (nargs flags)
     (cons nargs
           (cons (- (%lcc-max cs) nargs)
                 (cons flags
                       (cons (%lcc-rev (%lcc-lits cs))
                             (cons (%lcc-rev (car (%lcc-st cs))) nil))))))
   (%lcc-v2-nargs spec)
   (+ 2 (+ (* 4 (%lcc-v2-optional spec))
           (if (%lcc-v2-rest spec) 1 0)))))

; Immediate lambdas lower to let. Missing optional values become nil and an
; immediate rest parameter receives a freshly constructed list of extras.
(defun %lcc-v2-fixed-binds (ps as acc)
  (if ps
      (%lcc-v2-fixed-binds
       (cdr ps) (if as (cdr as) nil)
       (cons (cons (car ps) (cons (if as (car as) nil) nil)) acc))
      (%lcc-rev acc)))

(defun %lcc-v2-drop (xs n)
  (if (> n 0) (%lcc-v2-drop (if xs (cdr xs) nil) (- n 1)) xs))

(defun %lcc-v2-imm-binds (spec as acc)
  ((lambda (nargs argc required rest)
     (if (< argc required)
         (%lcc-v2-param-error)
         (if (if rest nil (> argc nargs))
             (%lcc-v2-param-error)
             ((lambda (fixed-binds)
                (if rest
                    (%lcc-rev
                     (cons (cons rest
                                 (cons (cons 'list (%lcc-v2-drop as nargs)) nil))
                           (%lcc-rev fixed-binds)))
                    fixed-binds))
              (%lcc-v2-fixed-binds (car spec) as acc)))))
   (%lcc-v2-nargs spec) (%lcc-len as)
   (- (%lcc-v2-nargs spec) (%lcc-v2-optional spec))
   (%lcc-v2-rest spec)))

(defun %lcc-imm-binds (ps as acc)
  (%lcc-v2-imm-binds (%lcc-v2-params ps) as acc))

; Override all three CodeObject construction paths. This leaves the frozen v1
; source untouched while also covering closure helpers, not just top-level defs.
(defun %lcc-compile-defun (params body fns)
  ((lambda (spec)
     (%lcc-v2-finish
      (%lcc-tail-seq
       (%lcc-cs (cons nil 0) nil (%lcc-v2-max0 spec) fns)
       (cons (cons (%lcc-v2-env spec) (cons nil 0)) nil)
       body)
      spec))
   (%lcc-v2-params params)))

(defun %lcc-compile-lambda (form fns)
  ((lambda (params body)
     ((lambda (spec)
        (%lcc-v2-finish
         (%lcc-emit-op
          (%lcc-seq
           (%lcc-cs (cons nil 0) nil (%lcc-v2-max0 spec) fns)
           (cons (cons (%lcc-v2-env spec) (cons nil 0)) nil)
           body)
          'ret)
         spec))
      (%lcc-v2-params params)))
   (car (cdr form)) (cdr (cdr form))))

(defun %lcc-lambda (cs lvls form)
  ((lambda (params body)
     ((lambda (spec uvbox)
        ((lambda (cs2)
           ((lambda (fnobj box)
              ((lambda (idx)
                 (progn
                   (rplaca box (cons fnobj (car box)))
                   (rplacd box (+ idx 1))
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
            (%lcc-v2-finish
             (%lcc-emit-op
              (%lcc-seq cs2 (cons (cons (%lcc-v2-env spec) uvbox) lvls) body)
              'ret)
             spec)
            (%lcc-fns cs)))
         (%lcc-cs (cons nil 0) nil (%lcc-v2-max0 spec) (%lcc-fns cs))))
      (%lcc-v2-params params) (cons nil 0)))
   (car (cdr form)) (cdr (cdr form))))

; Keep the native constant-stack implementations for dotimes/dolist, but do
; not classify the removed do/do* source names as compiler forms.
(defun %lcc-do-p (op)
  (cond ((eq op 'dotimes) t) ((eq op 'dolist) t) (t nil)))

; `remainder` remains an internal opcode mnemonic for decoding old P0
; artifacts. It is deliberately absent from the v2 source-operation dispatch.
(defun %lcc-expr-ops2 (cs lvls op args form)
  (cond ((eq op 'mod) (%lcc-binary cs lvls args 'mod))
        ((eq op 'cons) (%lcc-binary cs lvls args 'cons))
        ((eq op 'car)  (%lcc-unary cs lvls args 'car))
        ((eq op 'cdr)  (%lcc-unary cs lvls args 'cdr))
        ((eq op 'consp) (%lcc-unary cs lvls args 'consp))
        ((eq op 'not)  (%lcc-unary cs lvls args 'not))
        ((eq op 'null) (%lcc-unary cs lvls args 'not))
        ((%lcc-macro-p op) (%lcc-expr cs lvls (macroexpand-1 form)))
        (t (%lcc-call cs lvls op args))))

(defun %lcc-sf-p (op)
  (cond ((eq op 'quote) t) ((eq op 'progn) t) ((eq op 'if) t)
        ((eq op 'let) t) ((eq op 'let*) t) ((eq op 'setq) t)
        ((eq op 'function) t) ((eq op 'lambda) t)
        ((eq op 'quasiquote) t) ((eq op 'and) t) ((eq op 'or) t)
        ((eq op 'cond) t) ((eq op 'when) t) ((eq op 'unless) t)
        ((eq op 'dotimes) t) ((eq op 'dolist) t) (t nil)))

(defun %lcc-opform-p (op)
  (cond ((eq op '+) t) ((eq op '-) t) ((eq op '*) t) ((eq op '/) t)
        ((eq op '<) t) ((eq op '>) t) ((eq op '=) t) ((eq op 'eq) t)
        ((eq op 'eql) t) ((eq op 'mod) t) ((eq op 'cons) t)
        ((eq op 'car) t) ((eq op 'cdr) t) ((eq op 'consp) t)
        ((eq op 'not) t) ((eq op 'null) t) (t nil)))
