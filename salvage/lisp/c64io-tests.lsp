; Tests fuer lib-c64io: Komfort-Wrapper -> simuliertes RAM (PEEK/POKE), ohne VICE.
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp \
;   lisp/lib-c64hw.lsp lisp/lib-c64fx.lsp lisp/lib-c64io.lsp \
;   lisp/c64io-tests.lsp

(MEM-RESET)

; ---- Farben (Register-Pokes) ----
(border C64-RED)
(check (peek VIC-BORDER) 2)
(background C64-LIGHT-BLUE)
(check (peek VIC-BACKGROUND) 14)
(border 99)                              ; nur untere 4 Bit
(check (peek VIC-BORDER) 3)

; ---- Sprites (inkl. X-MSB-Bit in $D010) ----
(mem-reset)
(sprite-at 0 320 100)                    ; x>255 -> MSB-Bit 0
(check (peek (spr-x-reg 0)) 64)          ; 320 mod 256
(check (peek (spr-y-reg 0)) 100)
(check (peek VIC-SPRITE-XMSB) 1)         ; Bit 0 gesetzt
(sprite-at 1 100 50)                     ; x<256 -> MSB-Bit 1 bleibt 0
(check (peek VIC-SPRITE-XMSB) 1)
(sprite-on 2)
(check (peek VIC-SPRITE-ENABLE) 4)
(sprite-color 0 C64-WHITE)
(check (peek (spr-color-reg 0)) 1)

; ---- Bitmap-Malen ----
(mem-reset)
(plot 0 0)
(check (peek BITMAP-BASE) 128)           ; oberstes Bit der ersten Byte-Zelle
(plot 7 0)
(check (peek BITMAP-BASE) 129)           ; + unterstes Bit
(plot 8 0)
(check (peek (plus BITMAP-BASE 8)) 128)  ; naechste 8x8-Zelle
(plot 0 1)
(check (peek (plus BITMAP-BASE 1)) 128)  ; naechste Zeile in der Zelle

; circle poked die berechneten Punkte (Kardinalpunkt gesetzt)
(mem-reset)
(circle 100 100 10)
(check (peek (plot-addr 110 100)) (bit-n (difference 7 (logand 110 7))))  ; cx+r gesetzt

; ---- Sound (SID-Frequenzregister) ----
(mem-reset)
(sound 0 (quote A) 4)                    ; A4 = 7488
(check (peek SID-BASE) (addr-lo 7488))
(check (peek (plus SID-BASE 1)) (addr-hi 7488))

; ---- play schreibt die Frequenzsequenz (ueber Poke-Log pruefbar) ----
(mem-reset)
(poke-log-clear)
(play (quote ((C 0 1) (A 4 1))) 0)
; letzter gesetzter Frequenzwert = A4
(check (peek SID-BASE) (addr-lo 7488))
(check (peek (plus SID-BASE 1)) (addr-hi 7488))
; Poke-Log enthaelt 4 Pokes (2 Noten x lo/hi)
(check (length (poke-log)) 4)

(check-report)
