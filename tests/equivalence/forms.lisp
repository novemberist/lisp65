; lisp65 equivalence corpus (anti-drift rule 2): one form per line. Tree walk and
; device compiler must print identical lines (scripts/equivalence-check.sh).
; Self-contained: defines its own mini-library because bare tree walk has no blob
; stdlib. This also exercises defun machinery in both engines.
;
; Intentionally excluded from the agreement corpus (known non-overlap, 2026-07-05):
;   cond/case/and/or  — compiler lowers them natively; tree walk needs prelude macros
;   "/"               — tree-walk primitives do not include division (no P_DIV)
;   (< a b c) chains  — tree walk is variadic; compiler is binary
;   defmacro/quasiquote — M5 macro engine and M4 are absent from the compiler
;   eval/eval-string  — tree walk only (the v2a seam)
; The archived two-product workflow records these historical drift items.

; ---- Mini library part 1: list is not primitive in both engines, so define it here.
; Tree walk has P_LIST but the compiler does not; this defun unifies both paths.
(defun list (&rest r) r)

; ---- Literale ----
42
"ein string literal"
-7
(quote symbolwert)
(quote (1 2 3))
nil

; ---- Arithmetik + Vergleiche (2-stellig = Schnittmenge) ----
(+ 1 2)
(* 6 7)
(- 10 4)
(mod 17 5)
(< 1 2)
(> 1 2)
(= 5 5)
(<= 3 3)
(>= 2 3)

; ---- lisp65 truth: only nil is false; fixnum zero is true ----
(if 0 1 2)
(if nil 1 2)
(if (quote ()) 1 2)

; ---- Listen-Grundoperationen ----
(cons 1 2)
(car (quote (7 8 9)))
(cdr (quote (7 8 9)))
(list 1 2 3)
(eq (quote a) (quote a))
(eql 4 4)

; ---- Kontrollfluss ----
(progn 1 2 3)
(when (< 1 2) 99)
(when (> 1 2) 99)
(unless (> 1 2) 55)
(if (= 1 1) (+ 10 1) (+ 20 2))

; ---- let / let* / lokales setq ----
(let ((x 3) (y 4)) (+ x y))
(let* ((x 3) (y (+ x 1))) (* x y))
(let ((x 1)) (progn (setq x (+ x 41)) x))
(let ((x 2)) (let ((y (* x 5))) (- y x)))

; ---- loops (return a value through local setq) ----
(let ((s 0)) (progn (dotimes (i 5) (setq s (+ s i))) s))
(let ((s 0)) (progn (dolist (e (quote (4 5 6))) (setq s (+ s e))) s))

; ---- Mini-library: defun and recursion; both engines build the same library ----
(defun len (l) (if l (+ 1 (len (cdr l))) 0))
(len (quote (a b c d)))
(defun revi (l acc) (if l (revi (cdr l) (cons (car l) acc)) acc))
(revi (quote (1 2 3)) nil)
(defun fact (n) (if (< n 2) 1 (* n (fact (- n 1)))))
(fact 6)
(defun fib (n) (if (< n 2) n (+ (fib (- n 1)) (fib (- n 2)))))
(fib 10)

; ---- Redefinition ----
(defun twice (x) (+ x x))
(twice 21)
(defun twice (x) (* x 2))
(twice 21)

; ---- &rest ----
(defun count-args (a &rest r) (+ 1 (len r)))
(count-args 9)
(count-args 9 8 7 6)

; ---- Closures: flach, mutierbar, mehrstufig ----
(defun adder (n) (lambda (x) (+ x n)))
(funcall (adder 10) 5)
(defun make-counter () (let ((c 0)) (lambda () (progn (setq c (+ c 1)) c))))
(progn (setq zaehler (make-counter)) 0)
(funcall zaehler)
(funcall zaehler)
(defun outer3 (a) (lambda (b) (lambda (c) (+ a (+ b c)))))
(funcall (funcall (funcall (outer3 1) 2) 3))

; ---- funcall / apply ----
(funcall (function twice) 8)
(apply (function +) (quote (1 2 3 4)))
(defun map1 (f l) (if l (cons (funcall f (car l)) (map1 f (cdr l))) nil))
(map1 (function twice) (quote (1 2 3)))

; ---- Globale Variablen ----
(setq g 41)
(+ g 1)
(setq g (+ g 9))
g

; ---- Strings (geteilte Prims) ----
(string-length "abcde")
(len (string->list "xy"))

; ---- immediate lambda ----
((lambda (x y) (* x y)) 6 7)
((lambda (x) (let ((y (+ x 1))) (* y y))) 4)

; ---- cond / and / or (shared since LISP65_EVAL_CONTROL_SF) ----
(cond ((> 1 2) 10) ((> 2 1) 20) (t 30))
(cond ((> 1 2) 10))
(cond (42))
(cond ((= 1 1) (+ 1 1) (+ 2 2)))
(and 1 2 3)
(and 1 nil 3)
(or nil nil 7)
(or 5 nil)
(let ((x 5)) (and (> x 1) (< x 9)))

; ---- binary truncating division; division by zero must agree as an error ----
(/ 20 4)
(/ 7 2)
(/ -7 2)
(/ 7 -2)
(/ 5 0)

; ---- Function designators for opcode names (OPFN table, LISP65_VM_APPLY_OPFN gate).
; About 520 B of text made device availability a v2b budget decision. The harness
; protects semantics on the host while the device gate controls availability. ----
(funcall (function car) (quote (7 8)))
(funcall (function cdr) (quote (7 8)))
(funcall (function car) nil)
(apply (function cons) (quote (1 2)))
(map1 (function car) (quote ((1 2) (3 4))))
(funcall (function <) 1 2)
(funcall (function eql) 4 4)
(funcall (function mod) 17 5)
