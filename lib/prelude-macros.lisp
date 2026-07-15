; lisp65 — cond/and/or/case als PRELUDE-MAKROS für den Treewalk (Dialekt-Route (c), 2026-07-05).
; Schließt die Werkbank-REPL-Löcher mit NULL Bank-0-Kosten: die Definitionen leben als Quelle
; auf der DISK ("macros") und werden per (load "macros") in T_MACRO-Objekte evaluiert (Heap =
; EXT, symfn = GC-Root). Alternative zur .text-Route LISP65_EVAL_CONTROL_SF (694 B) — beide
; Routen sind ÄQUIVALENZ-VERIFIZIERT gegen das Compiler-Lowering (scripts/equivalence-check.sh
; fährt diesen File als tree-Preload gegen dieselben Formen).
; Semantik-Kontrakt (= Compiler): (and)->t, (or)->nil, letztes Glied/Klausel-Body in Tail-
; Position der Expansion, (cond (x))->x einmal ausgewertet (gensym-let gegen Doppel-Eval),
; case vergleicht per eql, Listen-Keys expandieren zu or/eql-Ketten, t-Klausel = Default.
; Expansions-Helfer nutzen nur Treewalk-Prims (list/cons/gensym); Makros expandieren rekursiv
; (and/or/cond in der eigenen Expansion). Helper-Namen sind bewusst lokal praefigiert: diese
; Datei wird in ein laufendes Produkt geladen und darf keine bestehenden Stdlib-%case-Helfer
; ueberschreiben.

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

; case-Expansions-Helfer: Klauselliste -> if-eql-Kette ueber die einmal gebundene tmp-Variable.
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
