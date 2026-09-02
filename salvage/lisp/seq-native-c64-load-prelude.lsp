; Minimal C64-safe support for the on-device seq LOAD smoke.

(SETQ PASSCOUNT 0)
(SETQ FAILCOUNT 0)

(DE CHECK (GOT EXPECTED)
  (COND ((EQUAL GOT EXPECTED)
         (SETQ PASSCOUNT (ADD1 PASSCOUNT)))
        (T
         (SETQ FAILCOUNT (ADD1 FAILCOUNT))
         (PRINC "FAIL: ")
         (PRIN1 GOT)
         (PRINC " != ")
         (PRINT EXPECTED))))

(DE CHECKREPORT ()
  (PRINC "PASS=")
  (PRIN1 PASSCOUNT)
  (PRINC " FAIL=")
  (PRINT FAILCOUNT))

(DE FUNCALL L (APPLY (CAR L) (CDR L)))
