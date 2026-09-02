; PROG/GO-Kontrollflussmatrix fuer Host-Semantik und native Regressionssicht.

(DE PG-LOCAL (N)
  (PROG (X)
    (SETQ X 0)
  L (SETQ X (ADD1 X))
    (COND ((LESSP X N) (GO L)))
    (RETURN X)))

(DE PG-CALLED (N) (PG-LOCAL N))

(DE PG-CALL-FROM-PROG (N)
  (PROG (X)
    (SETQ X (PG-LOCAL N))
    (RETURN X)))

(DE PG-TOP-FREEZE-SHAPE ()
  (PROG (X)
    (SETQ X 7)
  M (RETURN X)))

(CHECK (PROG (X) (SETQ X 0) L (SETQ X (ADD1 X)) (COND ((LESSP X 3) (GO L))) (RETURN X)) 3)
(CHECK (PG-LOCAL 4) 4)
(CHECK (PG-CALLED 5) 5)
(CHECK (PG-CALL-FROM-PROG 6) 6)
(CHECK (PG-TOP-FREEZE-SHAPE) 7)

(CHECK-REPORT)
