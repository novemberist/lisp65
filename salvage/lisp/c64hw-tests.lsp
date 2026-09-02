; Tests fuer lib-c64hw (reine Phase-5-Mathematik/Konstanten).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-c64hw.lsp \
;       lisp/c64hw-tests.lsp

; ---- Konstanten ----
(check C64-BLACK 0)
(check C64-WHITE 1)
(check C64-LIGHT-GREY 15)
(check VIC-BORDER 53280)
(check VIC-CONTROL1 53265)
(check VIC-MEMORY 53272)
(check SID-BASE 54272)
(check BITMAP-BASE 8192)
(check SCREEN-BASE 1024)

; ---- Bit-Helfer ----
(check (bit-n 0) 1)
(check (bit-n 3) 8)
(check (addr-lo 53520) 16)
(check (addr-hi 53520) 209)
(check (hires-cell-offset 0 0) 0)
(check (hires-cell-offset 8 0) 1)
(check (hires-cell-offset 0 8) 40)
(check (hires-plot-addr 0 0) BITMAP-BASE)
(check (hires-plot-addr 7 0) BITMAP-BASE)
(check (hires-plot-addr 8 0) (PLUS BITMAP-BASE 8))
(check (hires-plot-addr 0 1) (PLUS BITMAP-BASE 1))
(check (hires-plot-bit 0) 128)
(check (hires-plot-bit 7) 1)
(check (hires-color-byte C64-WHITE C64-BLACK) 16)
(check (hires-color-byte C64-RED C64-BLUE) 38)

; ---- Sprite-Register ----
(check (spr-x-reg 0) 53248)
(check (spr-x-reg 1) 53250)
(check (spr-y-reg 0) 53249)
(check (spr-color-reg 0) 53287)
(check (spr-color-reg 7) 53294)

; ---- Sprite-X 9-Bit (Low-Byte + MSB-Bit in $D010) ----
(check (spr-x-lo 320) 64)              ; 320 mod 256
(check (spr-x-hibit 320) 1)            ; >255 -> Bit gesetzt
(check (spr-x-hibit 100) 0)
(check (spr-set-xmsb 0 2 320) 4)       ; Bit 2 setzen (x>255)
(check (spr-set-xmsb 255 2 100) 251)   ; Bit 2 loeschen (x<=255): 255 - 4
(check (spr-set-xmsb 1 0 300) 1)       ; Bit 0 schon gesetzt, x>255 -> bleibt 1

; ---- SID-Noten ----
(check (sid-note 9 4) 7488)            ; A4 = Tabelle[A] << 4 (468*16)
(check (sid-note 9 5) 14976)          ; A5 = 2 * A4 (Oktav-Verdopplung)
(check (sid-note-name (quote A) 4) 7488)
(check (sid-note-name (quote C) 0) 278)
(check (note-index (quote G)) 7)

(check-report)
