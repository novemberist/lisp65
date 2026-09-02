; lib-seq -- Sequenz-Bibliothek (CL-Subset, Phase-6-Stufe-3).
;
; Ergaenzt die in cl-compat schon vorhandenen find/position/remove-if/reduce/
; every/some/count um die gaengigen restlichen Sequenz-Operationen. Rein in Lisp
; (ladbare Bibliothek), nutzt FUNCALL fuer Praedikate/Vergleicher.
; Hinweis: MAPCAR/MAPCAN sind Builtins; LISTE = einfach verkettete Liste.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/lib-seq.lsp lisp/seq-tests.lsp

; ---- -IF-Varianten ----
(DE MEMBER-IF (PRED L)
  (COND ((NULL L) NIL)
        ((FUNCALL PRED (CAR L)) L)
        (T (MEMBER-IF PRED (CDR L)))))

(DE FIND-IF (PRED L)
  (COND ((NULL L) NIL)
        ((FUNCALL PRED (CAR L)) (CAR L))
        (T (FIND-IF PRED (CDR L)))))

(DE SEQ-POSIF (PRED L N)
  (COND ((NULL L) NIL)
        ((FUNCALL PRED (CAR L)) N)
        (T (SEQ-POSIF PRED (CDR L) (ADD1 N)))))
(DE POSITION-IF (PRED L) (SEQ-POSIF PRED L 0))

(DE COUNT-IF (PRED L)
  (COND ((NULL L) 0)
        ((FUNCALL PRED (CAR L)) (ADD1 (COUNT-IF PRED (CDR L))))
        (T (COUNT-IF PRED (CDR L)))))

(DE ASSOC-IF (PRED AL)
  (COND ((NULL AL) NIL)
        ((FUNCALL PRED (CAR (CAR AL))) (CAR AL))
        (T (ASSOC-IF PRED (CDR AL)))))

; ---- remove-duplicates (EQL-Default, behaelt das ERSTE Vorkommen; CL-Default
;      behaelt das letzte -- bewusste, einfachere Wahl) ----
(DE SEQ-MEMBERP (X L)
  (COND ((NULL L) NIL) ((EQL X (CAR L)) T) (T (SEQ-MEMBERP X (CDR L)))))
(DE SEQ-RDAUX (L SEEN)
  (COND ((NULL L) NIL)
        ((SEQ-MEMBERP (CAR L) SEEN) (SEQ-RDAUX (CDR L) SEEN))
        (T (CONS (CAR L) (SEQ-RDAUX (CDR L) (CONS (CAR L) SEEN))))))
(DE REMOVE-DUPLICATES (L) (SEQ-RDAUX L NIL))

; ---- subseq [start, end) ; END NIL -> bis zum Ende ----
(DE SEQ-TAKE (N L)
  (COND ((ZEROP N) NIL) ((NULL L) NIL) (T (CONS (CAR L) (SEQ-TAKE (SUB1 N) (CDR L))))))
(DE SEQ-DROP (N L)
  (COND ((ZEROP N) L) ((NULL L) NIL) (T (SEQ-DROP (SUB1 N) (CDR L)))))
(DE SUBSEQ (L START END)
  (COND ((NULL END) (SEQ-DROP START L))
        (T (SEQ-TAKE (DIFFERENCE END START) (SEQ-DROP START L)))))

; ---- sort (Insertion-Sort, nicht-destruktiv, stabil); PRED: a vor b? ----
(DE SEQ-INSERT (X SORTED PRED)
  (COND ((NULL SORTED) (LIST X))
        ((FUNCALL PRED X (CAR SORTED)) (CONS X SORTED))
        (T (CONS (CAR SORTED) (SEQ-INSERT X (CDR SORTED) PRED)))))
(DE SORT (L PRED)
  (COND ((NULL L) NIL)
        (T (SEQ-INSERT (CAR L) (SORT (CDR L) PRED) PRED))))
