; Tests fuer lib-c64-autoload: granulares (lazy) Laden der C64-Komfortschicht.
; AUS DEM REPO-ROOT laufen lassen (wegen LOAD-Pfaden).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-autoload.lsp \
;       lisp/lib-c64-autoload.lsp lisp/c64-autoload-tests.lsp

(DE LOADED? (F) (COND ((MEMBER F *AUTOLOAD-LOADED*) T) (T NIL)))

; ---- Direkt nach Laden der Registry ----
; lib-c64hw ist eager geladen -> Konstanten verfuegbar.
(CHECK C64-RED 2)
(CHECK VIC-BORDER 53280)
(CHECK (LOADED? "lisp/lib-c64hw.lsp") T)
; fx/io sind NUR Stubs -> Dateien noch nicht geladen.
(CHECK (LOADED? "lisp/lib-c64fx.lsp") NIL)
(CHECK (LOADED? "lisp/lib-c64io.lsp") NIL)

; ---- Erster Aufruf einer fx-Funktion laedt lib-c64fx nach ----
(CHECK (line-points 0 0 2 0) (QUOTE ((0 . 0) (1 . 0) (2 . 0))))
(CHECK (LOADED? "lisp/lib-c64fx.lsp") T)
(CHECK (LOADED? "lisp/lib-c64io.lsp") NIL)        ; io weiterhin nur Stub

; ---- Erster Aufruf einer io-Funktion laedt lib-c64io nach ----
; (hw + fx sind schon geladen -> der Lade-einmal-Schutz ueberspringt sie)
(MEM-RESET)
(border C64-RED)
(CHECK (PEEK VIC-BORDER) 2)
(CHECK (LOADED? "lisp/lib-c64io.lsp") T)

; ---- Weitere io-Stubs nutzen die bereits geladene Komfortschicht ----
(background C64-BLUE)
(CHECK (PEEK VIC-BACKGROUND) 6)
(MEM-RESET)
(sprite-at 1 300 42)
(CHECK (PEEK (spr-x-reg 1)) 44)
(CHECK (PEEK (spr-y-reg 1)) 42)
(CHECK (PEEK VIC-SPRITE-XMSB) 2)
(sprite-on 1)
(CHECK (PEEK VIC-SPRITE-ENABLE) 2)
(sprite-color 1 C64-YELLOW)
(CHECK (PEEK (spr-color-reg 1)) 7)

; ---- io-Funktion mit fx-Abhaengigkeit funktioniert (circle -> circle-points) ----
(MEM-RESET)
(circle 100 100 10)
(CHECK (PEEK (plot-addr 110 100)) (bit-n (DIFFERENCE 7 (LOGAND 110 7))))

; ---- Lazy-Wert: sound nutzt hw (sid) + io; nach Aufruf korrektes Register ----
(MEM-RESET)
(sound 0 (QUOTE A) 4)                             ; A4 = 7488
(CHECK (PEEK SID-BASE) (addr-lo 7488))

(CHECK-REPORT)
