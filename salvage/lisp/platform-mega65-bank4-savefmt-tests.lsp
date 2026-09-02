; Host-Tests fuer die MEGA65-Bank-4-LOAD-sichere Platform-Variante.

(MEM-RESET)
(DE GETKEY () 0)
(DE LOAD (NAME) (LIST 'LOAD NAME))
; Host-Interpreter hat keine Tail-Call-Optimierung; der echte BCL loescht 200
; Zeilen auf dem Geraet. Hier bleibt der CLEARSCREEN-Kontrollpfad erhalten,
; aber die Host-Range ist klein.
(DE BCL (R) (H 262144 262150 0))

(CLEARSCREEN 6)
(CHECK (PEEK 53280) 6)
(CHECK (PEEK 53281) 6)
(CHECK (PEEK 53296) 100)
(CHECK (PEEK 262144) 0)
(CHECK (PEEK 262149) 0)

(DRAWLINE 0 0 2 0 1)
(CHECK (PEEK 262144) 224)

(DRAWLINE 0 0 0 1 0)
(CHECK (PEEK 262144) 96)
(CHECK (PEEK 262224) 0)

(PLAT-TONE 1 7488 17)
(CHECK (PEEK 54296) 15)
(CHECK (PEEK 54279) (LBYTE 7488))
(CHECK (PEEK 54280) (HBYTE 7488))
(CHECK (PEEK 54283) 17)
(CHECK (PLAT-LOAD 'DEMO) '(LOAD DEMO))

(CHECK-REPORT)
