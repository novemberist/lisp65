(defmacro defun (name params &rest body)
  `(set-symbol-function ',name (lambda ,params ,@body)))

(defmacro defparameter (name init)
  `(progn (setq ,name ,init) ',name))

(defmacro defvar (name &rest init)
  (if init
      `(progn (if (boundp ',name) nil (setq ,name ,(car init))) ',name)
      `(progn (if (boundp ',name) nil nil) ',name)))

(defmacro when (test &rest body)
  `(if ,test (progn ,@body) nil))

(defmacro unless (test &rest body)
  `(if ,test nil (progn ,@body)))

(defmacro and (&rest forms)
  (if forms
      (if (cdr forms)
          `(if ,(car forms) (and ,@(cdr forms)) nil)
          (car forms))
      't))

(defmacro or (&rest forms)
  (if forms
      (if (cdr forms)
          ((lambda (g)
             `((lambda (,g) (if ,g ,g (or ,@(cdr forms)))) ,(car forms)))
           (gensym))
          (car forms))
      nil))

(defmacro cond (&rest clauses)
  (if clauses
      (if (cdr (car clauses))
          `(if ,(car (car clauses))
               (progn ,@(cdr (car clauses)))
               (cond ,@(cdr clauses)))
          `(or ,(car (car clauses)) (cond ,@(cdr clauses))))
      nil))

(defun %case-key-tests (g keys)
  (if keys
      (if (cdr keys)
          `(or (eql ,g ',(car keys)) ,(%case-key-tests g (cdr keys)))
          `(eql ,g ',(car keys)))
      nil))

(defun %case-key-test (g key-spec)
  (if (eq key-spec 'otherwise)
      't
      (if (eq key-spec 't)
          't
          (if (car key-spec)
              (%case-key-tests g key-spec)
              `(eql ,g ',key-spec)))))

(defun %case-clauses (g clauses)
  (if clauses
      (cons (cons (%case-key-test g (car (car clauses))) (cdr (car clauses)))
            (%case-clauses g (cdr clauses)))
      nil))

(defmacro case (keyform &rest clauses)
  ((lambda (g)
     `(let ((,g ,keyform)) (cond ,@(%case-clauses g clauses))))
   (gensym)))

(defun not (x)
  (if x nil 't))

(defun identity (x)
  x)

(defun list (&rest xs)
  xs)

(defun caar (x)
  (car (car x)))

(defun cadr (x)
  (car (cdr x)))

(defun cdar (x)
  (cdr (car x)))

(defun cddr (x)
  (cdr (cdr x)))

(defun first (x)
  (car x))

(defun rest (x)
  (cdr x))

(defun second (x)
  (cadr x))

(defun 1+ (x)
  (+ x 1))

(defun 1- (x)
  (- x 1))

(defun zerop (x)
  (= x 0))

(defun plusp (x)
  (> x 0))

(defun minusp (x)
  (< x 0))

(defun %distinct-from-all (x xs)
  (if xs
      (and (not (= x (car xs))) (%distinct-from-all x (cdr xs)))
      't))

(defun /= (&rest xs)
  (if xs
      (and (%distinct-from-all (car xs) (cdr xs)) (apply (function /=) (cdr xs)))
      't))

(defun %append2 (a b)
  (%append2-rev (reverse a) b))

(defun %append2-rev (ra b)
  (if ra
      (%append2-rev (cdr ra) (cons (car ra) b))
      b))

(defun append (&rest lists)
  ((lambda (rev-lists)
     (if rev-lists
         (%append-lists (cdr rev-lists) (car rev-lists))
         nil))
   (reverse lists)))

(defun %append-lists (rev-lists acc)
  (if rev-lists
      (%append-lists (cdr rev-lists) (%append2 (car rev-lists) acc))
      acc))

(defun length (xs)
  (%length-from xs 0))

(defun %length-from (xs n)
  (if xs
      (%length-from (cdr xs) (1+ n))
      n))

(defun nth (n xs)
  (if (zerop n)
      (car xs)
      (nth (1- n) (cdr xs))))

(defun nthcdr (n xs)
  (if (zerop n)
      xs
      (nthcdr (1- n) (cdr xs))))

(defun %reverse-into (xs acc)
  (if xs
      (%reverse-into (cdr xs) (cons (car xs) acc))
      acc))

(defun reverse (xs)
  (%reverse-into xs nil))

(defun last (xs)
  (if (cdr xs)
      (last (cdr xs))
      xs))

(defun member (item xs)
  (if xs
      (if (eql item (car xs))
          xs
          (member item (cdr xs)))
      nil))

(defun assoc (key alist)
  (if alist
      (if (eql key (car (car alist)))
          (car alist)
          (assoc key (cdr alist)))
      nil))

(defun mapcar (fn xs)
  (if xs
      (cons (funcall fn (car xs)) (mapcar fn (cdr xs)))
      nil))

(defun %mapc (fn xs)
  (if xs
      (progn (funcall fn (car xs)) (%mapc fn (cdr xs)))
      nil))

(defun mapc (fn xs)
  (%mapc fn xs)
  xs)

(defun remove (item xs)
  (%remove-into item xs nil))

(defun %remove-into (item xs acc)
  (if xs
      (if (eql item (car xs))
          (%remove-into item (cdr xs) acc)
          (%remove-into item (cdr xs) (cons (car xs) acc)))
      (reverse acc)))

(defun find (item xs)
  (if xs
      (if (eql item (car xs))
          (car xs)
          (find item (cdr xs)))
      nil))

(defun %position-from (item xs n)
  (if xs
      (if (eql item (car xs))
          n
          (%position-from item (cdr xs) (1+ n)))
      nil))

(defun position (item xs)
  (%position-from item xs 0))

(defun %let-vars (bindings)
  (if bindings
      (cons (car (car bindings)) (%let-vars (cdr bindings)))
      nil))

(defun %let-vals (bindings)
  (if bindings
      (cons (if (cdr (car bindings)) (car (cdr (car bindings))) nil)
            (%let-vals (cdr bindings)))
      nil))

(defmacro let (bindings &rest body)
  `((lambda ,(%let-vars bindings) ,@body) ,@(%let-vals bindings)))

(defmacro let* (bindings &rest body)
  (if bindings
      `(let (,(car bindings)) (let* ,(cdr bindings) ,@body))
      `(let () ,@body)))
