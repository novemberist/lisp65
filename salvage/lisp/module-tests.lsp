; Tests fuer lib-modules (require/provide).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-modules.lsp \
;       lisp/module-tests.lsp
;
; LOAD-MODULE wird durch einen Stub ersetzt (statt echter Datei-I/O), der das
; Laden protokolliert und eine Abhaengigkeit simuliert: Modul A braucht B.

(SETQ *PROVIDED* NIL)
(SETQ *LOG* NIL)
(DE LOAD-MODULE (NAME)
  (SETQ *LOG* (CONS NAME *LOG*))
  (COND ((EQ NAME (QUOTE A)) (REQUIRE (QUOTE B))) (T NIL)))

; ---- provide / provided-p ----
(CHECK (PROVIDED-P (QUOTE B)) NIL)
(REQUIRE (QUOTE B))
(CHECK (PROVIDED-P (QUOTE B)) T)

; ---- require laedt nur einmal ----
(REQUIRE (QUOTE B))                 ; schon da -> kein erneutes Laden
(CHECK *LOG* (QUOTE (B)))

; ---- Abhaengigkeit: A braucht B (B schon geladen -> nicht erneut) ----
(REQUIRE (QUOTE A))
(CHECK *LOG* (QUOTE (A B)))         ; A geladen, B NICHT noch einmal
(CHECK (PROVIDED-P (QUOTE A)) T)
(CHECK (REQUIRE (QUOTE A)) NIL)     ; nochmaliges require -> nichts

; ---- provide ist idempotent ----
(PROVIDE (QUOTE C))
(SETQ N1 (LENGTH *PROVIDED*))
(PROVIDE (QUOTE C))
(CHECK (LENGTH *PROVIDED*) N1)      ; unveraendert

; ---- Pfad-Konvention ----
(CHECK (MODULE-FILE (QUOTE UTILS)) "UTILS.lsp")

(CHECK-REPORT)
