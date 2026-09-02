; lib-c64hw -- Phase-5-Vorarbeit: REINE Mathematik + Konstanten fuer die
; C64-Hardware-Anbindung. KEIN echter Hardwarezugriff (der ist nativer .acme-Code
; via peek/poke/sys, Phase 5) -- hier nur die rechenbaren Teile, host-testbar:
; SID-Notentabelle, Sprite-Koordinaten-Logik, Hi-Res-Bitmap-Adress-/Bit-Mathe,
; Adress-Split, Register-/Farbkonstanten.
; Spec: docs/phase5-hardware.md.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-c64hw.lsp \
;       lisp/c64hw-tests.lsp

; ---- Farbkonstanten (0..15) ----
(SETQ C64-BLACK 0) (SETQ C64-WHITE 1) (SETQ C64-RED 2) (SETQ C64-CYAN 3)
(SETQ C64-PURPLE 4) (SETQ C64-GREEN 5) (SETQ C64-BLUE 6) (SETQ C64-YELLOW 7)
(SETQ C64-ORANGE 8) (SETQ C64-BROWN 9) (SETQ C64-LIGHT-RED 10) (SETQ C64-DARK-GREY 11)
(SETQ C64-GREY 12) (SETQ C64-LIGHT-GREEN 13) (SETQ C64-LIGHT-BLUE 14) (SETQ C64-LIGHT-GREY 15)

; ---- Register-Adressen (VIC-II $D000, SID $D400) ----
(SETQ VIC-BORDER 53280)         ; $D020
(SETQ VIC-BACKGROUND 53281)     ; $D021
(SETQ VIC-SPRITE-ENABLE 53269)  ; $D015
(SETQ VIC-SPRITE-XMSB 53264)    ; $D010  (Bit 8 der X-Position, 1 Bit pro Sprite)
(SETQ VIC-CONTROL1 53265)       ; $D011  (Bit 5 = Bitmap-Modus)
(SETQ VIC-RASTER 53266)         ; $D012
(SETQ VIC-MEMORY 53272)         ; $D018  (Screen-/Bitmap-Basis im VIC-Bankfenster)
(SETQ SID-BASE 54272)           ; $D400
(SETQ SID-VOLUME 54296)         ; $D418

; ---- Hi-Res-Bitmap-Geometrie ($2000 Bitmap, $0400 Screen-RAM) ----
(SETQ BITMAP-BASE 8192)         ; $2000
(SETQ SCREEN-BASE 1024)         ; $0400

; Sprite-n-Register
(DE spr-x-reg (n) (PLUS 53248 (TIMES 2 n)))   ; $D000 + 2n
(DE spr-y-reg (n) (PLUS 53249 (TIMES 2 n)))   ; $D001 + 2n
(DE spr-color-reg (n) (PLUS 53287 n))         ; $D027 + n

; ---- Hilfen ----
(DE pow2 (n) (COND ((ZEROP n) 1) (T (TIMES 2 (pow2 (SUB1 n))))))
(DE bit-n (n) (pow2 n))
(DE hw-nth (n l) (COND ((ZEROP n) (CAR l)) (T (hw-nth (SUB1 n) (CDR l)))))
(DE addr-lo (a) (LBYTE a))      ; niederwertiges Byte (fuer 2-Byte-poke)
(DE addr-hi (a) (HBYTE a))      ; hoeherwertiges Byte

(DE hires-cell-offset (x y)
  (PLUS (TIMES (QUOTIENT y 8) 40) (QUOTIENT x 8)))
(DE hires-plot-addr (x y)
  (PLUS BITMAP-BASE
    (PLUS (TIMES (QUOTIENT y 8) 320)
      (PLUS (TIMES (QUOTIENT x 8) 8) (LOGAND y 7)))))
(DE hires-plot-bit (x) (bit-n (DIFFERENCE 7 (LOGAND x 7))))
(DE hires-color-byte (fg bg)
  (LOGOR (TIMES (LOGAND fg 15) 16) (LOGAND bg 15)))

; ---- Sprite-X-Koordinate (9 Bit: 8-Bit-Register + MSB-Bit in $D010) ----
(DE spr-x-lo (x) (LOGAND x 255))
(DE spr-x-hibit (x) (COND ((GREATERP x 255) 1) (T 0)))
; $D010-Wert fuer Sprite n bei X-Position x aktualisieren (Bit n setzen/loeschen)
(DE spr-set-xmsb (d010 n x)
  (COND ((GREATERP x 255) (LOGOR d010 (bit-n n)))
        (T (LOGAND d010 (LOGXOR 255 (bit-n n))))))

; ---- SID-Frequenz: Note -> 16-Bit-Frequenzregisterwert ----
; Tabelle fuer Oktave 0 (C..B), PAL (Reg = f * 16777216 / 985248). Hoehere
; Oktaven per Verdopplung (Linksshift) -> reine Integer-Arithmetik.
; Hinweis: produktiv besser eine volle 8-Oktaven-Tabelle (vermeidet Rundungsdrift).
(SETQ *SID-OCT0* (LIST 278 295 313 331 351 372 394 417 442 468 496 526))
(SETQ *NOTE-NAMES*
  (LIST (CONS (QUOTE C) 0) (CONS (QUOTE CS) 1) (CONS (QUOTE D) 2) (CONS (QUOTE DS) 3)
        (CONS (QUOTE E) 4) (CONS (QUOTE F) 5) (CONS (QUOTE FS) 6) (CONS (QUOTE G) 7)
        (CONS (QUOTE GS) 8) (CONS (QUOTE A) 9) (CONS (QUOTE AS) 10) (CONS (QUOTE B) 11)))

(DE sid-note (semitone octave) (TIMES (hw-nth semitone *SID-OCT0*) (pow2 octave)))
(DE note-index (name) (CDR (ASSOC name *NOTE-NAMES*)))
(DE sid-note-name (name octave) (sid-note (note-index name) octave))
