; LISP 64 -- Array-Bibliothek (N-dimensional, als geschachtelte Listen)
; Salvage aus reference/.../samples/arrays.lsp. Semantik unveraendert.
;
; Arrays liegen als geschachtelte Listen auf der Property-Liste des Namens
; (Property 'ARRAY). Indizes sind 0-basiert (NTH liefert den Teil-Tail).
;
; API:
;   (ARRAY name initwert dim1 dim2 ...)   legt Array an, init in jeder Zelle
;   (STO   name wert     idx1 idx2 ...)   speichert
;   (LOD   name          idx1 idx2 ...)   liest
;
; Die Kontroll-Makros FOR/WHILE/IF aus dem Original sind hier entfernt; sie
; kommen aus lib-macros.lsp. Diese Datei nach lib-macros.lsp laden.

(DF ARRAY L
  (PUTPROP (CAR L) 'ARRAY
    (DIM (MAPCAR 'EVAL (CDDR L)) (EVAL (CADR L))))
  (CAR L))

(DF LOD L
  (LOD1 (GETPROP (CAR L) 'ARRAY)
    (MAPCAR 'EVAL (CDR L))))

(DF STO L
  (STO1 (GETPROP (CAR L) 'ARRAY)
    (EVAL (CADR L))
    (MAPCAR 'EVAL (CDDR L))))

(DE DIM (NLIS E)
  (COND ((ATOM NLIS) (COPY E))
        (T (BUILD (CAR NLIS) (DIM (CDR NLIS) E)))))

(DE BUILD (N E)
  (COND ((ZEROP N) NIL)
        (T (CONS (COPY E) (BUILD (SUB1 N) E)))))

(DE STO1 (L E DIMS)
  (COND ((ATOM DIMS) NIL)
        ((ATOM (CDR DIMS))
         (RPLACA (NTH L (CAR DIMS)) E))
        (T (STO1 (CAR (NTH L (CAR DIMS))) E (CDR DIMS)))))

(DE LOD1 (L DIMS)
  (COND ((ATOM DIMS) L)
        (T (LOD1 (CAR (NTH L (CAR DIMS))) (CDR DIMS)))))
