; First Mini-CLOS cross-compile source candidate.
; This file intentionally uses public Mini-CLOS macros; the host expansion
; output is audited before any native SAVE-format conversion consumes it.

(DEFCLASS SHAPE () NAME)
(DEFCLASS CIRCLE (SHAPE) RADIUS)

(DEFMETHOD AREA ((C CIRCLE))
  (TIMES 3 (TIMES (SLOT-VALUE C 'RADIUS) (SLOT-VALUE C 'RADIUS))))

(DEFMETHOD KIND ((S SHAPE)) 'SHAPE)
(DEFMETHOD KIND ((X T)) 'OTHER)

(DE CXOBJ () '(CIRCLE RADIUS 4 NAME C1))

(DE CXOK (A0 A1 KX K5)
  (AND (EQL A0 48) (EQL A1 12) (EQ KX 'SHAPE) (EQ K5 'OTHER)))

(DE CXTEST ()
  (PROG (X R)
    (CXCSET)
    (SETQ X (CXOBJ))
    (SETQ R (AREA X))
    (SET-SLOT-VALUE X 'RADIUS 2)
    (RETURN (COND ((CXOK R (AREA X) (KIND X) (KIND 5)) 'CXPASS)
                  (T 'CXFAIL)))))
