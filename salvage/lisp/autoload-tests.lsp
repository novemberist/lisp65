; Tests fuer lib-autoload (lazy Laden). AUS DEM REPO-ROOT laufen lassen (LOAD-Pfad).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-autoload.lsp \
;       lisp/autoload-tests.lsp

(SETQ *AUTOLOAD-FIXTURE-LOADED* NIL)
(AUTOLOAD (QUOTE TRIPLE) "lisp/autoload-fixture.lsp")

; Vor dem ersten Aufruf: Fixture NICHT geladen (nur der Stub existiert).
(CHECK *AUTOLOAD-FIXTURE-LOADED* NIL)

; Erster Aufruf: laedt die Fixture und rechnet mit der echten Definition.
(CHECK (TRIPLE 5) 15)
(CHECK *AUTOLOAD-FIXTURE-LOADED* T)

; Beweis "genau einmal geladen": Flag zuruecksetzen, erneut aufrufen ->
; die echte Definition laeuft direkt, KEIN erneutes Laden.
(SETQ *AUTOLOAD-FIXTURE-LOADED* NIL)
(CHECK (TRIPLE 10) 30)
(CHECK *AUTOLOAD-FIXTURE-LOADED* NIL)

(CHECK-REPORT)
