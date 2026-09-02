; Heap workload fuer tools/host-lisp/compact-model.py (--heap-profile).
; Baut einen repraesentativen, nicht-trivialen Heap aus Kern-Primitiven
; (kein Prelude noetig): Assoc-Liste, Binaerbaum, Property-Listen, Strings.
; Ziel: genug Cons-Paare, dass der Heapgroessen-Effekt aussagekraeftig ist.

; --- Hilfsfunktionen (Kern-Dialekt) ---
(DE HP-PAIRS (N ACC)
  (COND ((ZEROP N) ACC)
        (T (HP-PAIRS (SUB1 N)
                     (CONS (CONS N (CONS 'ITEM (CONS N NIL))) ACC)))))

(DE HP-TREE (D)
  (COND ((ZEROP D) 'LEAF)
        (T (CONS (HP-TREE (SUB1 D)) (HP-TREE (SUB1 D))))))

; --- Datenstrukturen ---
; HP-ASSOC: 120 Eintraege a 3 Cons = 360 Cons
(SETQ HP-ASSOC (HP-PAIRS 120 NIL))
; HP-TREE7: Binaerbaum Tiefe 7 = 127 innere Cons
(SETQ HP-TREE7 (HP-TREE 7))

(SETQ HP-STRING-A "PROFILE-STRING-PAYLOAD-ALPHANUMERIC-AND-SYMBOL-LIKE-DATA-FOR-HEAP-TRAVERSAL-ANALYSIS")
(SETQ HP-STRING-B "SECOND-PROFILE-STRING-WITH-DIFFERENT-CONTENT-TO-EXERCISE-STRING-PAYLOAD-ACCOUNTING")

; Property-Listen auf mehreren Symbolen (typische Symboltabellen-Nutzung)
(PUTPROP 'HP-NODE-A 'SLOTS HP-ASSOC)
(PUTPROP 'HP-NODE-A 'NAME HP-STRING-A)
(PUTPROP 'HP-NODE-A 'NEIGHBOR 'HP-NODE-B)
(PUTPROP 'HP-NODE-B 'TREE HP-TREE7)
(PUTPROP 'HP-NODE-B 'NAME HP-STRING-B)
(PUTPROP 'HP-NODE-B 'NEIGHBOR 'HP-NODE-A)
(PUTPROP 'HP-NODE-C 'LINKS (CONS (CONS 'L 'R) (CONS HP-TREE7 (CONS HP-ASSOC NIL))))

; --- Wurzeln fuer den Profiler ---
(SETQ HEAP-PROFILE-ROOTS
  (LIST HP-ASSOC HP-TREE7 'HP-NODE-A 'HP-NODE-B 'HP-NODE-C HP-STRING-A HP-STRING-B))
