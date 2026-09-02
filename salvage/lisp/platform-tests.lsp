; Tests fuer lib-platform -- beweisen die Backend-Austauschbarkeit auf dem Host:
; ein Mock-Backend zeichnet alle Low-Level-Operationen auf, sodass die
; High-Level-API (draw-line/draw-rectangle/read-key/play-tone/load-file)
; backend-unabhaengig verifizierbar ist.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp \
;       lisp/platform-tests.lsp

; ---- Mock-Backend (Host) -------------------------------------------------
(SETQ *OPS* NIL)                          ; aufgezeichnete Operationen (umgekehrt)
(DE mock-reset () (SETQ *OPS* NIL))
(DE mock-record (OP) (SETQ *OPS* (CONS OP *OPS*)))
(DE mock-ops () (REVERSE *OPS*))          ; in Aufrufreihenfolge

(DE plat-plot (X Y C) (mock-record (LIST 'PLOT X Y C)))
(DE plat-clear (C) (mock-record (LIST 'CLEAR C)))
(DE plat-tone (V F W) (mock-record (LIST 'TONE V F W)))
(DE plat-load (N) (mock-record (LIST 'LOAD N)))

(SETQ *KEYS* NIL)
(DE plat-getkey ()
  (PROG (K)
    (COND ((NULL *KEYS*) (RETURN 0)))
    (SETQ K (CAR *KEYS*))
    (SETQ *KEYS* (CDR *KEYS*))
    (RETURN K)))

; ---- Helfer ----
(DE first-op () (CAR (mock-ops)))
(DE last-op () (CAR (REVERSE (mock-ops))))
(DE op-count () (LENGTH (mock-ops)))
(DE plat-member (X L)                      ; T wenn X (EQUAL) in Liste L vorkommt
  (COND ((NULL L) NIL)
        ((EQUAL X (CAR L)) T)
        (T (plat-member X (CDR L)))))

; ---- Integer-Helfer ------------------------------------------------------
(CHECK (plat-abs 5) 5)
(CHECK (plat-abs (DIFFERENCE 0 5)) 5)
(CHECK (plat-sign 7) 1)
(CHECK (plat-sign (DIFFERENCE 0 7)) (DIFFERENCE 0 1))
(CHECK (plat-sign 0) 0)
(CHECK (plat-both-eq 3 3 4 4) T)
(CHECK (plat-both-eq 3 3 4 5) NIL)

; ---- read-key dispatcht ans Backend (FIFO-Queue) -------------------------
(SETQ *KEYS* (LIST 65 66))
(CHECK (read-key) 65)
(CHECK (read-key) 66)
(CHECK (read-key) 0)                       ; leer -> 0

; ---- horizontale Linie (0,0)->(3,0): 4 Punkte ----------------------------
(mock-reset)
(draw-line 0 0 3 0 1)
(CHECK (op-count) 4)
(CHECK (first-op) (LIST 'PLOT 0 0 1))
(CHECK (last-op) (LIST 'PLOT 3 0 1))

; ---- vertikale Linie (0,0)->(0,2): 3 Punkte ------------------------------
(mock-reset)
(draw-line 0 0 0 2 7)
(CHECK (op-count) 3)
(CHECK (first-op) (LIST 'PLOT 0 0 7))
(CHECK (last-op) (LIST 'PLOT 0 2 7))

; ---- diagonale Linie (0,0)->(2,2): exakt (0,0)(1,1)(2,2) -----------------
(mock-reset)
(draw-line 0 0 2 2 2)
(CHECK (op-count) 3)
(CHECK (mock-ops)
       (LIST (LIST 'PLOT 0 0 2) (LIST 'PLOT 1 1 2) (LIST 'PLOT 2 2 2)))

; ---- Rechteck-Umriss: Ecken kommen vor, kein Inneres ---------------------
(mock-reset)
(draw-rectangle 0 0 2 2 5)
; Umfang eines 3x3-Kastens = 8 Randzellen; vier Linien teilen sich die Ecken,
; daher >8 Plots durch Eckdopplung -- pruefe, dass alle vier Ecken gesetzt sind.
(CHECK (plat-member (LIST 'PLOT 0 0 5) (mock-ops)) T)
(CHECK (plat-member (LIST 'PLOT 2 0 5) (mock-ops)) T)
(CHECK (plat-member (LIST 'PLOT 0 2 5) (mock-ops)) T)
(CHECK (plat-member (LIST 'PLOT 2 2 5) (mock-ops)) T)
(CHECK (plat-member (LIST 'PLOT 1 1 5) (mock-ops)) NIL)   ; Inneres NICHT gefuellt

; ---- gefuelltes Rechteck (0,0)-(1,1): Inneres IST gesetzt ----------------
(mock-reset)
(fill-rectangle 0 0 1 1 3)
(CHECK (plat-member (LIST 'PLOT 0 0 3) (mock-ops)) T)
(CHECK (plat-member (LIST 'PLOT 1 1 3) (mock-ops)) T)

; ---- Audio/Datei dispatchen unveraendert ans Backend ---------------------
(mock-reset)
(play-tone 2 1234 33)
(CHECK (first-op) (LIST 'TONE 2 1234 33))
(play-sample 1 555 17)
(CHECK (last-op) (LIST 'TONE 1 555 17))
(mock-reset)
(load-file (QUOTE GAME))
(CHECK (first-op) (LIST 'LOAD (QUOTE GAME)))

; ---- clear-screen ---------------------------------------------------------
(mock-reset)
(clear-screen 6)
(CHECK (first-op) (LIST 'CLEAR 6))

(CHECK-REPORT)
