; LISP 64 -- Benchmark-Programme (Lisp-Fassung)
;
; Vier Faelle aus docs/performance-notes.md. Auf dem Host dient diese Datei der
; KORREKTHEITS-Pruefung (CHECK aus prelude.lsp); die eigentliche Performance-
; Messung Tree-Walker vs. BASIC laeuft spaeter unter VICE (siehe README.md /
; bench-basic.bas).
;
; Host:  python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/benchmarks/bench.lsp

; --- 1. FIB: call-/bind-lastig (Worst Case Tree-Walker) ---
(DE FIB (N)
  (COND ((LESSP N 2) N)
        (T (PLUS (FIB (SUB1 N)) (FIB (DIFFERENCE N 2))))))

; --- 2. SUMTO: PROG-Loop, integer-/kontrollflusslastig ---
(DE SUMTO (N)
  (PROG (ACC I)
    (SETQ ACC 0)
    (SETQ I 1)
   LOOP
    (COND ((GREATERP I N) (RETURN ACC)))
    (SETQ ACC (PLUS ACC I))
    (SETQ I (ADD1 I))
    (GO LOOP)))

; --- 3. LISTSUM: Pointer + etwas Consing ---
(DE IOTA (N)
  (PROG (OUT)
    (SETQ OUT NIL)
   LOOP
    (COND ((ZEROP N) (RETURN OUT)))
    (SETQ OUT (CONS N OUT))
    (SETQ N (SUB1 N))
    (GO LOOP)))

(DE LISTSUM (L)
  (COND ((NULL L) 0)
        (T (PLUS (CAR L) (LISTSUM (CDR L))))))

; --- 4. COUNT-PRIMES: integer-/branchy (Sieb-Ersatz ohne Arrays) ---
(DE DIVIDESP (D N) (ZEROP (REMAINDER N D)))

(DE PRIMEP (N)
  (PROG (D)
    (COND ((LESSP N 2) (RETURN NIL)))
    (SETQ D 2)
   LOOP
    (COND ((GREATERP (TIMES D D) N) (RETURN T)))
    (COND ((DIVIDESP D N) (RETURN NIL)))
    (SETQ D (ADD1 D))
    (GO LOOP)))

(DE COUNT-PRIMES (N)
  (PROG (C I)
    (SETQ C 0)
    (SETQ I 2)
   LOOP
    (COND ((GREATERP I N) (RETURN C)))
    (COND ((PRIMEP I) (SETQ C (ADD1 C))))
    (SETQ I (ADD1 I))
    (GO LOOP)))

; ---- Korrektheits-Checks (Host) ----
(CHECK (FIB 10) 55)
(CHECK (FIB 15) 610)
(CHECK (SUMTO 100) 5050)
(CHECK (LISTSUM (IOTA 50)) 1275)
(CHECK (COUNT-PRIMES 50) 15)
(CHECK (COUNT-PRIMES 100) 25)

(CHECK-REPORT)
