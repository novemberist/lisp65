; Tests fuer platform-demo gegen ein Mock-Backend -- beweist, dass dieselbe
; App-Logik backend-unabhaengig laeuft (die Operationsfolge ist pruefbar).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp \
;       lisp/platform-demo.lsp lisp/platform-demo-tests.lsp

; ---- Mock-Backend (zeichnet Operationen auf) ----
(SETQ *OPS* NIL)
(SETQ *KEYS* NIL)
(DE plat-plot (X Y C) (SETQ *OPS* (CONS (LIST 'PLOT X Y C) *OPS*)))
(DE plat-clear (C) (SETQ *OPS* (CONS (LIST 'CLEAR C) *OPS*)))
(DE plat-tone (V F W) (SETQ *OPS* (CONS (LIST 'TONE V F W) *OPS*)))
(DE plat-load (N) (SETQ *OPS* (CONS (LIST 'LOAD N) *OPS*)))
(DE plat-getkey ()
  (PROG (K)
    (COND ((NULL *KEYS*) (RETURN 0)))
    (SETQ K (CAR *KEYS*))
    (SETQ *KEYS* (CDR *KEYS*))
    (RETURN K)))
(DE pd-reset () (PROGN (SETQ *OPS* NIL) (SETQ *KEYS* NIL)))
(DE pd-ops () (REVERSE *OPS*))
(DE pd-mem (X L) (COND ((NULL L) NIL) ((EQUAL X (CAR L)) T) (T (pd-mem X (CDR L)))))
(DE pd-has (X) (pd-mem X (pd-ops)))

; ---- Balkendiagramm: zwei Balken (Hoehen 2 und 1), Breite 1, Basis y=5 ----
(pd-reset)
(bar-chart '(2 1) 0 5 1 7)
(CHECK (LENGTH (pd-ops)) 6)            ; 1 CLEAR + 5 Zellen
(CHECK (CAR (pd-ops)) '(CLEAR 0))      ; zuerst geloescht
(CHECK (pd-has '(PLOT 0 5 7)) T)       ; Balken 0 unten
(CHECK (pd-has '(PLOT 0 3 7)) T)       ; Balken 0 oben (H=2 -> y=5,4,3)
(CHECK (pd-has '(PLOT 2 5 7)) T)       ; Balken 1 unten
(CHECK (pd-has '(PLOT 2 3 7)) NIL)     ; Balken 1 nur H=1 -> nur y=5,4

; ---- Liniendiagramm: horizontale Verbindung (0,0)-(2,0) ----
(pd-reset)
(line-graph '((0 . 0) (2 . 0)) 1)
(CHECK (LENGTH (pd-ops)) 3)            ; (0,0) (1,0) (2,0)
(CHECK (pd-has '(PLOT 0 0 1)) T)
(CHECK (pd-has '(PLOT 1 0 1)) T)
(CHECK (pd-has '(PLOT 2 0 1)) T)

; ---- Backend-Austauschbarkeit: leere/Ein-Punkt-Faelle ----
(pd-reset)
(line-graph NIL 1)
(CHECK (LENGTH (pd-ops)) 0)
(pd-reset)
(line-graph '((4 . 4)) 1)
(CHECK (LENGTH (pd-ops)) 0)            ; einzelner Punkt -> keine Linie

; ---- Dashboard: kompletter Screen nutzt nur Platform-API-Operationen ----
(pd-reset)
(demo-dashboard)
(CHECK (CAR (pd-ops)) '(CLEAR 0))
(CHECK (pd-has '(PLOT 0 0 1)) T)       ; Rahmen
(CHECK (pd-has '(PLOT 14 1 2)) T)      ; Kopfleiste
(CHECK (pd-has '(PLOT 4 4 7)) T)       ; zweiter Balken oben
(CHECK (pd-has '(PLOT 13 3 5)) T)      ; Liniengraph-Ende

; ---- Ein App-Step: kein Key zeichnet, Taste spielt Ton, L laedt Demo -------
(pd-reset)
(demo-step)
(CHECK (CAR (pd-ops)) '(CLEAR 0))
(pd-reset)
(SETQ *KEYS* '(65))
(demo-step)
(CHECK (pd-ops) '((TONE 0 465 17)))
(pd-reset)
(SETQ *KEYS* '(76))
(demo-step)
(CHECK (pd-ops) '((LOAD DEMO)))

(CHECK-REPORT)
