; Tests fuer lib-platform-mega65-bank4 gegen erweitertes Host-RAM.
; Belegt den sichtbaren ROM-SCREEN-Bank-4-Backend-Modus separat zum direkten
; $2000-H640-Prototyp.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp \
;       lisp/lib-mega65hw.lsp lisp/lib-platform-mega65-bank4.lsp \
;       lisp/platform-mega65-bank4-tests.lsp

(MEM-RESET)

; ---- Backend-Contract ----------------------------------------------------
(CHECK (m65-platform-backend) M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4)
(CHECK (m65-visible-screen-backend) M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4)

; ---- plat-clear: sichtbarer Bank-4-Framebuffer ---------------------------
(POKE M65-SCREEN-BANK4-BASE 255)
(POKE (m65-screen-bank4-end) 255)
(POKE M65-VIC3-CTRL-B 8)
(clear-screen M65-BLUE)
(CHECK (PEEK M65-VIC-KEY) 83)
(CHECK (PEEK M65-VIC-BORDER) M65-BLUE)
(CHECK (PEEK M65-VIC-BACKGROUND) M65-BLUE)
(CHECK (PEEK M65-VIC4-CTRL-A) 100)
(CHECK (PEEK M65-VIC3-CTRL-B) 248)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 0)
(CHECK (PEEK (m65-screen-bank4-end)) 0)

; ---- plat-plot: Bank-4-Bits setzen und loeschen -------------------------
(plat-plot 0 0 M65-WHITE)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 128)

(plat-plot 7 0 M65-WHITE)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 129)

(plat-plot 8 0 M65-RED)
(CHECK (PEEK (PLUS M65-SCREEN-BANK4-BASE 1)) 128)

(plat-plot 0 1 M65-GREEN)
(CHECK (PEEK (PLUS M65-SCREEN-BANK4-BASE 80)) 128)

(plat-plot 0 0 M65-BLACK)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 1)

; ---- generische Platform-API ueber Bank-4-Backend -----------------------
(MEM-RESET)
(draw-line 0 0 2 0 M65-WHITE)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 224)

(draw-line 0 0 0 1 M65-BLACK)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 96)

; ---- SID0-Dispatch bleibt kompatibel ------------------------------------
(MEM-RESET)
(play-tone 1 7488 17)
(CHECK (PEEK M65-SID0-VOLUME) 15)
(CHECK (PEEK (PLUS M65-SID0-BASE 7)) (LBYTE 7488))
(CHECK (PEEK (PLUS M65-SID0-BASE 8)) (HBYTE 7488))
(CHECK (PEEK (PLUS M65-SID0-BASE 11)) 17)

(CHECK-REPORT)
