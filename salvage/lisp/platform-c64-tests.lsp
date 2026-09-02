; Tests fuer lib-platform-c64 gegen simuliertes Host-RAM.
; Beweist das C64-Backend ohne VICE: plat-plot setzt Hi-Res-Bitmapbits und das
; zugehoerige Screen-RAM-Farbbyte; plat-clear waehlt die Bitmap-Anzeige.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-c64hw.lsp \
;       lisp/lib-platform-c64.lsp lisp/platform-c64-tests.lsp

(MEM-RESET)

; ---- Hi-Res plat-plot ----------------------------------------------------
(plat-plot 0 0 C64-WHITE)
(CHECK (PEEK BITMAP-BASE) 128)
(CHECK (PEEK SCREEN-BASE) 16)           ; fg=white, bg=black

(plat-plot 7 0 C64-WHITE)
(CHECK (PEEK BITMAP-BASE) 129)          ; Bit 7 und Bit 0 im ersten Bitmap-Byte

(plat-plot 8 0 C64-RED)
(CHECK (PEEK (PLUS BITMAP-BASE 8)) 128)
(CHECK (PEEK (PLUS SCREEN-BASE 1)) 32)  ; fg=red, bg=black

(plat-plot 0 1 C64-GREEN)
(CHECK (PEEK (PLUS BITMAP-BASE 1)) 128)
(CHECK (PEEK SCREEN-BASE) 80)           ; letzte Farbe fuer dieselbe 8x8-Zelle

; ---- plat-clear: Farben + Bitmap-Modus ----------------------------------
(MEM-RESET)
(POKE VIC-CONTROL1 8)
(plat-clear C64-BLUE)
(CHECK (PEEK VIC-BORDER) C64-BLUE)
(CHECK (PEEK VIC-BACKGROUND) C64-BLUE)
(CHECK (PEEK VIC-CONTROL1) 40)          ; altes Bit 3 + Bitmap-Bit 5
(CHECK (PEEK VIC-MEMORY) 24)            ; Screen $0400, Bitmap $2000

; ---- SID-Dispatch bleibt unveraendert -----------------------------------
(MEM-RESET)
(plat-tone 1 7488 17)
(CHECK (PEEK SID-VOLUME) 15)
(CHECK (PEEK (PLUS SID-BASE 7)) (LBYTE 7488))
(CHECK (PEEK (PLUS SID-BASE 8)) (HBYTE 7488))
(CHECK (PEEK (PLUS SID-BASE 11)) 17)

(CHECK-REPORT)
