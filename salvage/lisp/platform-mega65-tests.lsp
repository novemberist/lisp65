; Tests fuer lib-platform-mega65 gegen simuliertes Host-RAM.
; Belegt den ersten MEGA65-Backend-Schnitt: H640-Bitplane-Adressierung,
; Bit-Setzen/Loeschen, Mode-Register und SID0-Dispatch.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp \
;       lisp/lib-mega65hw.lsp lisp/lib-platform-mega65.lsp \
;       lisp/platform-mega65-tests.lsp

(MEM-RESET)

; ---- H640-Geometrie ------------------------------------------------------
(CHECK (m65-h640-addr 0 0) M65-BITPLANE-BASE)
(CHECK (m65-h640-addr 7 0) M65-BITPLANE-BASE)
(CHECK (m65-h640-addr 8 0) (PLUS M65-BITPLANE-BASE 1))
(CHECK (m65-h640-addr 0 1) (PLUS M65-BITPLANE-BASE 80))
(CHECK (m65-h640-addr 639 199) 24191)
(CHECK (m65-h640-bit 0) 128)
(CHECK (m65-h640-bit 7) 1)
(CHECK (m65-h640-bit 8) 128)
(CHECK (m65-bitplane-reg-byte M65-BITPLANE-BASE) 34) ; $22: beide Adressfelder
(CHECK (m65-platform-backend) M65-PLATFORM-BACKEND-DIRECT-H640)
(CHECK (m65-visible-screen-backend) M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4)

; ---- ROM-SCREEN-Bank-4-Geometrie ----------------------------------------
(CHECK M65-SCREEN-BANK4-BASE 262144)
(CHECK M65-SCREEN-BANK4-BYTES 16000)
(CHECK (m65-screen-bank4-byte-offset 0 0) 0)
(CHECK (m65-screen-bank4-byte-offset 8 0) 1)
(CHECK (m65-screen-bank4-byte-offset 0 1) 80)
(CHECK (m65-screen-bank4-byte-offset 639 199) 15999)
(CHECK (m65-screen-bank4-addr 0 0) M65-SCREEN-BANK4-BASE)
(CHECK (m65-screen-bank4-addr 7 0) M65-SCREEN-BANK4-BASE)
(CHECK (m65-screen-bank4-addr 8 0) (PLUS M65-SCREEN-BANK4-BASE 1))
(CHECK (m65-screen-bank4-addr 0 1) (PLUS M65-SCREEN-BANK4-BASE 80))
(CHECK (m65-screen-bank4-addr 639 199) (m65-screen-bank4-end))
(CHECK (m65-screen-bank4-bit 0) 128)
(CHECK (m65-screen-bank4-bit 7) 1)
(CHECK (m65-screen-bank4-bit 8) 128)

; ---- plat-plot: monochrome Bitplane setzen und loeschen -----------------
(plat-plot 0 0 M65-WHITE)
(CHECK (PEEK M65-BITPLANE-BASE) 128)

(plat-plot 7 0 M65-WHITE)
(CHECK (PEEK M65-BITPLANE-BASE) 129)

(plat-plot 8 0 M65-RED)
(CHECK (PEEK (PLUS M65-BITPLANE-BASE 1)) 128)

(plat-plot 0 1 M65-GREEN)
(CHECK (PEEK (PLUS M65-BITPLANE-BASE 80)) 128)

(plat-plot 0 0 M65-BLACK)
(CHECK (PEEK M65-BITPLANE-BASE) 1)

; ---- generische Platform-API ueber MEGA65-Backend -----------------------
(MEM-RESET)
(clear-screen M65-CYAN)
(CHECK (PEEK M65-VIC-BORDER) M65-CYAN)
(CHECK (PEEK M65-VIC4-CTRL-A) 100)
(CHECK (PEEK M65-VIC3-CTRL-B) 240)

(draw-line 0 0 2 0 M65-WHITE)
(CHECK (PEEK M65-BITPLANE-BASE) 224)    ; Bits 7,6,5

(draw-line 0 0 0 1 M65-BLACK)
(CHECK (PEEK M65-BITPLANE-BASE) 96)     ; Bit 7 geloescht, 6+5 bleiben

(MEM-RESET)
(play-tone 0 1024 17)
(CHECK (PEEK M65-SID0-VOLUME) 15)
(CHECK (PEEK M65-SID0-BASE) (LBYTE 1024))
(CHECK (PEEK (PLUS M65-SID0-BASE 1)) (HBYTE 1024))
(CHECK (PEEK (PLUS M65-SID0-BASE 4)) 17)

; ---- plat-clear: VIC-IV-Key, H640/BPM und Bitplane-0-Basis ---------------
(MEM-RESET)
(POKE M65-VIC3-CTRL-B 8)
(plat-clear M65-BLUE)
(CHECK (PEEK M65-VIC-KEY) 83)
(CHECK (PEEK M65-VIC-BORDER) M65-BLUE)
(CHECK (PEEK M65-VIC-BACKGROUND) M65-BLUE)
(CHECK (PEEK M65-VIC4-CTRL-A) 100)
(CHECK (PEEK M65-VIC3-CTRL-B) 248)      ; altes Bit 3 + ROM-kompatible $F0-Bits
(CHECK (PEEK M65-BP-ENABLE) 1)
(CHECK (PEEK M65-BP0-ADDR) 34)

; ---- SID0-Dispatch -------------------------------------------------------
(MEM-RESET)
(plat-tone 1 7488 17)
(CHECK (PEEK M65-SID0-VOLUME) 15)
(CHECK (PEEK (PLUS M65-SID0-BASE 7)) (LBYTE 7488))
(CHECK (PEEK (PLUS M65-SID0-BASE 8)) (HBYTE 7488))
(CHECK (PEEK (PLUS M65-SID0-BASE 11)) 17)

(CHECK-REPORT)
