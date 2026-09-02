; LISP 64 -- TRACE/UNTRACE-Debugger
; Salvage aus reference/.../samples/tracer.lsp (Doppeldefinitionen entfernt).
;
; Funktioniert, weil Funktionsdefinitionen introspizierbar als Listen auf der
; Property-Liste liegen (EXPR/FEXPR/MACRO): TRACE spleisst einen EVTRACE-Wrapper
; in den Rumpf, UNTRACE entfernt ihn wieder. Nutzt dynamisches Scoping, damit
; EVTRACE die aktuellen Parameterwerte per EVAL sieht.
;
; Setzt voraus: lib-macros.lsp NICHT noetig; benoetigt MSG/SPACES/PRIN1/PRINT.
; Abhaengigkeit auf das LAST-Verhalten des Dialekts (letztes ELEMENT) fuer UNTRACE.

(SETQ SINGLE-STEP-V NIL)
(SETQ TRACE-SPACES 0)

(DE SINGLE-STEP () (SETQ SINGLE-STEP-V T))
(DE NO-SINGLE-STEP () (SETQ SINGLE-STEP-V NIL))

(DF TRACE L
  (SETQ TRACE-SPACES 0)
  (NO-SINGLE-STEP)
  (MAPC '(LAMBDA (FUNC)
           (PROG (X)
             (SETQ X (OR (GETPROP FUNC 'EXPR)
                         (GETPROP FUNC 'FEXPR)
                         (GETPROP FUNC 'MACRO) NIL))
             (COND ((NULL X) (RETURN NIL)))
             (RPLACD (CDR X)
               (LIST (LIST 'EVTRACE FUNC (CADR X) (CDDR X))))))
        L)
  L)

(DF UNTRACE L
  (SETQ TRACE-SPACES 0)
  (MAPC '(LAMBDA (FUNC)
           (PROG (X)
             (SETQ X (OR (GETPROP FUNC 'EXPR)
                         (GETPROP FUNC 'FEXPR)
                         (GETPROP FUNC 'MACRO) NIL))
             (COND ((NULL X) (RETURN NIL)))
             (RPLACD (CDR X) (LAST (LAST X)))))
        L)
  L)

(DF EVTRACE (TRFUN TRVARS TRBODY)
  (PROG (TRRESULT)
    (PRINTENTRY TRFUN TRVARS)
    (SETQ TRRESULT (APPLY 'PROGN TRBODY))
    (PRINTEXIT TRFUN TRRESULT)
    (RETURN TRRESULT)))

(DE PRINTENTRY (TRFUN TRVARS)
  (SPACES (SETQ TRACE-SPACES (ADD1 TRACE-SPACES)))
  (MSG "ENTERING " TRFUN " [")
  (PRINTENTRY1 TRVARS)
  (MSG "]" T)
  (COND (SINGLE-STEP-V (WAITCHAR))))

(DE PRINTENTRY1 (TRVARS)
  (COND ((NULL TRVARS) NIL)
        ((ATOM TRVARS) (PRIN1 (EVAL TRVARS)))
        ((ATOM (CDR TRVARS)) (PRIN1 (EVAL (CAR TRVARS))))
        (T (PRIN1 (EVAL (CAR TRVARS)))
           (MSG ",")
           (PRINTENTRY1 (CDR TRVARS)))))

(DE PRINTEXIT (TRFUN TRRESULT)
  (SPACES (SETQ TRACE-SPACES (SUB1 TRACE-SPACES)))
  (MSG " EXITING  " TRFUN " = ")
  (PRINT TRRESULT)
  (COND (SINGLE-STEP-V (WAITCHAR))))
