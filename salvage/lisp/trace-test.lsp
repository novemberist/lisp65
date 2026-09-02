; Test/Demonstration des salvagten TRACE/UNTRACE.
; Lauf:
;   python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-trace.lsp lisp/trace-test.lsp

(DE FACT (N)
  (COND ((ZEROP N) 1)
        (T (TIMES N (FACT (SUB1 N))))))

; vor TRACE: korrektes Ergebnis
(CHECK (FACT 4) 24)

(MSG T "--- TRACE FACT, dann (FACT 3) ---" T)
(TRACE FACT)
; getracter Aufruf gibt ENTERING/EXITING aus UND liefert weiter korrekt
(CHECK (FACT 3) 6)

(MSG "--- UNTRACE FACT, dann (FACT 3) ---" T)
(UNTRACE FACT)
; nach UNTRACE: keine Trace-Ausgabe mehr, Ergebnis unveraendert
(CHECK (FACT 3) 6)

(CHECK-REPORT)
