; lisp65 -- cond/and/or/case as PRELUDE MACROS for Treewalk (dialect route (c),
; 2026-07-05). Closes the Workbench REPL gaps at ZERO Bank-0 cost: definitions
; live as source on DISK ("macros") and (load "macros") evaluates them into
; T_MACRO objects (heap = EXT, symfn = GC root). Alternative to the 694-byte
; .text route LISP65_EVAL_CONTROL_SF; both routes are EQUIVALENCE-VERIFIED
; against compiler lowering. scripts/equivalence-check.sh loads this file as
; the Treewalk prelude for the same forms.
; Semantic contract, identical to the compiler: (and)->t, (or)->nil; the last
; member/clause body remains in tail position in the expansion;
; (cond (x))->x evaluates x once through a gensym let; case compares with eql,
; list keys expand into or/eql chains, and a t clause is the default.
; Expansion helpers use only Treewalk primitives (list/cons/gensym); macros
; expand recursively, including and/or/cond inside their own expansions.
; Helper names deliberately carry a local prefix because this file is loaded
; into a running product and must not overwrite existing stdlib %case helpers.

(defmacro and (&rest fs)
  (if fs
      (if (cdr fs)
          (list (quote if) (car fs) (cons (quote and) (cdr fs)) nil)
          (car fs))
      (quote t)))

(defmacro or (&rest fs)
  (if fs
      (if (cdr fs)
          ((lambda (tmp)
             (list (quote let) (list (list tmp (car fs)))
                   (list (quote if) tmp tmp (cons (quote or) (cdr fs)))))
           (gensym))
          (car fs))
      nil))

(defmacro cond (&rest cls)
  (if cls
      ((lambda (cl rest)
         (if (cdr cl)
             (list (quote if) (car cl)
                   (cons (quote progn) (cdr cl))
                   (cons (quote cond) rest))
             ((lambda (tmp)
                (list (quote let) (list (list tmp (car cl)))
                      (list (quote if) tmp tmp (cons (quote cond) rest))))
              (gensym))))
       (car cls) (cdr cls))
      nil))

; case expansion helper: clause list -> if/eql chain over the once-bound tmp variable.
(defun %prelude-macros-case-key-tests (tmp keys)
  (if keys
      (if (cdr keys)
          (list (quote or)
                (list (quote eql) tmp (list (quote quote) (car keys)))
                (%prelude-macros-case-key-tests tmp (cdr keys)))
          (list (quote eql) tmp (list (quote quote) (car keys))))
      nil))

(defun %prelude-macros-case-key-test (tmp key)
  (if (eq key (quote t))
      (quote t)
      (if (eq key (quote otherwise))
          (quote t)
          (if (car key)
              (%prelude-macros-case-key-tests tmp key)
              (list (quote eql) tmp (list (quote quote) key))))))

(defun %prelude-macros-case-clauses (tmp cls)
  (if cls
      ((lambda (cl)
         (if (eq (car cl) (quote t))
             (cons (quote progn) (cdr cl))
             (list (quote if)
                   (%prelude-macros-case-key-test tmp (car cl))
                   (cons (quote progn) (cdr cl))
                   (%prelude-macros-case-clauses tmp (cdr cls)))))
       (car cls))
      nil))

(defmacro case (expr &rest cls)
  ((lambda (tmp)
     (list (quote let) (list (list tmp expr)) (%prelude-macros-case-clauses tmp cls)))
   (gensym)))
