; Minimal native C64 LOOP smoke: loaded DM + GENSYM + PROG runtime.
; Uses short 0/1/2-arg helpers because long SAVE-format lines and wide
; loaded-userfun calls are separate C64 constraints. Labels are fixed here;
; GENSYM-as-GO-label is a separate follow-up from GENSYM-as-variable.
; The repeat stop condition returns directly; GO inside COND remains a
; separate interpreter-control-flow follow-up.
; DM receives the full macro call, so the expander uses (CDR L). The expansion
; must be returned explicitly because PROG discards ordinary body values.

(DE RA () (SETQ P (GENSYM)))
(DE RD (X) (CAR (CDR X)))
(DE RE (X) (CDR (CDDR X)))
(DE RF () (LIST (QUOTE PROG) P))
(DE RG () (LIST (LIST (QUOTE SETQ) P (RD X)) (QUOTE LP)))
(DE RH () (LIST (QUOTE ZEROP) P))
(DE RI () (LIST (QUOTE RETURN) NIL))
(DE RJ () (LIST (QUOTE COND) (LIST (RH) (RI))))
(DE RK () (LIST (QUOTE SETQ) P (LIST (QUOTE SUB1) P)))
(DE RM () (LIST (QUOTE GO) (QUOTE LP)))
(DE RN () (LIST (QUOTE LE) (LIST (QUOTE RETURN) NIL)))
(DE RO (U V) (APPEND U V))
(DE RU () (RO (RO (RF) (RG)) (LIST (RJ))))
(DE RV () (RO (RO (RE X) (LIST (RK) (RM))) (RN)))
(DE RW () (RO (RU) (RV)))
(DM LOOP L (PROG NIL (SETQ X (CDR L)) (RA) (RETURN (RW))))
