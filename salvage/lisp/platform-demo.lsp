; platform-demo -- kleine, BACKEND-AGNOSTISCHE Beispiel-Apps gegen lib-platform.
; Der Sinn: die App-Logik kennt KEIN Backend; sie ruft ausschliesslich die
; Platform-API (clear-screen/draw-line/fill-rectangle). Dieselbe App laeuft so
; ueber das Host-Mock-Backend (host-testbar, platform-demo-tests) UND unveraendert
; ueber das C64-Backend (lib-platform-c64) bzw. spaeter MEGA65.
;
; Braucht nur prelude + lib-platform.

; ---- Balkendiagramm ----
(DE pd-bar (BX H YBASE W COLOR)          ; ein Balken: Breite W, Hoehe H ueber YBASE
  (fill-rectangle BX (DIFFERENCE YBASE H) (PLUS BX (SUB1 W)) YBASE COLOR))

(DE pd-bars (HS I X0 YBASE W COLOR)
  (COND ((NULL HS) T)
        (T (pd-bar (PLUS X0 (TIMES I (ADD1 W))) (CAR HS) YBASE W COLOR)
           (pd-bars (CDR HS) (ADD1 I) X0 YBASE W COLOR))))

(DE draw-bars (HEIGHTS X0 YBASE W COLOR)
  (pd-bars HEIGHTS 0 X0 YBASE W COLOR))

(DE bar-chart (HEIGHTS X0 YBASE W COLOR) ; Diagramm aus einer Hoehenliste
  (PROGN (clear-screen 0)
         (pd-bars HEIGHTS 0 X0 YBASE W COLOR)))

; ---- Liniendiagramm: verbindet aufeinanderfolgende (x . y)-Punkte ----
(DE line-graph (POINTS COLOR)
  (COND ((NULL POINTS) NIL)
        ((NULL (CDR POINTS)) T)          ; letzter Punkt: nichts mehr zu verbinden
        (T (draw-line (CAR (CAR POINTS)) (CDR (CAR POINTS))
                      (CAR (CAR (CDR POINTS))) (CDR (CAR (CDR POINTS))) COLOR)
           (line-graph (CDR POINTS) COLOR))))

; ---- Kleine portable Dashboard-App --------------------------------------
; Nur Platform-API: laeuft mit Mock-Backend, C64-Backend oder spaeter MEGA65.
(DE demo-dashboard ()
  (PROGN (clear-screen 0)
         (draw-rectangle 0 0 15 9 1)
         (fill-rectangle 1 1 14 1 2)
         (draw-bars '(2 4 1 3) 2 8 1 7)
         (line-graph '((1 . 7) (5 . 5) (9 . 6) (13 . 3)) 5)))

(DE demo-handle-key (K)
  (COND ((ZEROP K) (demo-dashboard))
        ((EQUAL K 76) (load-file 'DEMO))       ; L
        (T (play-tone 0 (PLUS 400 K) 17))))

(DE demo-step () (demo-handle-key (read-key)))
