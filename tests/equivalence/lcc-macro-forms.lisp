; P4 macro corpus: tree vs. lcc, not vm. The C compiler has no M5/defmacro; the
; self-hosted compiler closes that gap. Expanders live in the carrier (T_MACRO),
; and lcc expands uses through function-kind/macroexpand-1 before compiling them.
;
; BEFUND (2026-07-05, ausgespart + als Traeger-Bug gemeldet): quasiquote IM MAKRO-BODY
; bricht im TREEWALK selbst ((qe 5) -> !error; via P_MEXP1 sogar Segfault) -- eigener
; The tree-walk quasiquote-in-macro behavior is not lcc-specific. Direct
; quasiquote forms below and macros with list/cons expanders run on both sides.
(defmacro swap-args (f a b) (list f b a))
(swap-args - 10 2)
(defmacro twice+ (x) (list (quote +) x x))
(twice+ 21)
(defun append (a b) (if a (cons (car a) (append (cdr a) b)) b))
(quasiquote (1 (unquote (+ 1 1)) 3))
(quasiquote (kopf (unquote-splicing (quote (a b))) ende))
(quasiquote atomwert)
(defmacro inc! (v) (list (quote setq) v (list (quote +) v 1)))
(setq zz 5)
(inc! zz)
zz
(defun f10 (x) (twice+ (+ x 1)))
(f10 20)
(defmacro mit-let (v e b) (list (quote let) (list (list v e)) b))
(mit-let q 6 (* q 7))
(setq nq 7)
(quasiquote (a (quasiquote (b (unquote (unquote nq))))))
(quasiquote (a (quasiquote (b (unquote (c (unquote nq)))))))
(quasiquote (x (quasiquote (y (unquote-splicing (unquote (list nq nq)))))))
(quasiquote ((unquote nq) (quasiquote (unquote (quasiquote tief)))))
(dotimes (i 6 i) nil)
(let ((s 0)) (dotimes (i 5 s) (setq s (+ s i))))
(let ((s 0)) (dolist (x (quote (10 20 12)) s) (setq s (+ s x))))
(let ((s 0)) (dotimes (i 4 s) (dotimes (j 3) (setq s (+ s 1)))))
