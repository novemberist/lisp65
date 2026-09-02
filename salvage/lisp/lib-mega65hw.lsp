; lib-mega65hw -- kleine, host-testbare MEGA65-Hardware-Helfer fuer den
; Plattform-Layer. Kein Geraete-Smoke: nur Konstanten und Adress-Mathematik fuer
; den ersten H640-Bitplane-Schnitt und den ROM-SCREEN-Bank-4-Pfad.
;
; Quellenstand fuer Register:
;   MEGA65/mega65-core iomap.txt: VIC-IV-Key $D02F, VIC-III Control B $D031,
;   Bitplane Enable $D032, Bitplane-Adressen $D033-$D03A.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-mega65hw.lsp \
;       lisp/platform-mega65-tests.lsp

; ---- Farb-/Kompatibilitaetskonstanten -----------------------------------
(SETQ M65-BLACK 0) (SETQ M65-WHITE 1) (SETQ M65-RED 2) (SETQ M65-CYAN 3)
(SETQ M65-PURPLE 4) (SETQ M65-GREEN 5) (SETQ M65-BLUE 6) (SETQ M65-YELLOW 7)
(SETQ M65-ORANGE 8) (SETQ M65-BROWN 9) (SETQ M65-LIGHT-RED 10) (SETQ M65-DARK-GREY 11)
(SETQ M65-GREY 12) (SETQ M65-LIGHT-GREEN 13) (SETQ M65-LIGHT-BLUE 14) (SETQ M65-LIGHT-GREY 15)

; ---- Register-Adressen ---------------------------------------------------
(SETQ M65-VIC-KEY 53295)        ; $D02F, $47/$53 schalten VIC-IV-Register frei
(SETQ M65-VIC-BORDER 53280)     ; $D020
(SETQ M65-VIC-BACKGROUND 53281) ; $D021
(SETQ M65-VIC4-CTRL-A 53296)    ; $D030, ROM SCREEN 640,200,1 setzt $64
(SETQ M65-VIC3-CTRL-B 53297)    ; $D031, ROM SCREEN 640,200,1 setzt $F0
(SETQ M65-BP-ENABLE 53298)      ; $D032
(SETQ M65-BP0-ADDR 53299)       ; $D033
(SETQ M65-SID0-BASE 54272)      ; $D400, kompatibler erster SID
(SETQ M65-SID0-VOLUME 54296)    ; $D418

; ---- H640-Bitplane-Geometrie --------------------------------------------
(SETQ M65-PLATFORM-BACKEND-DIRECT-H640 'DIRECT-H640)
(SETQ M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4 'ROM-SCREEN-BANK4)

(SETQ M65-BITPLANE-BASE 8192)   ; $2000, erste 8K-Bitplane
(SETQ M65-H640-BYTES-PER-ROW 80)
(SETQ M65-H640-WIDTH 640)
(SETQ M65-H640-HEIGHT 200)

; ROM SCREEN 640,200,1 alloziert 16000 Bytes ab linear $40000 (Bank 4).
(SETQ M65-SCREEN-BANK4-BASE 262144)
(SETQ M65-SCREEN-BANK4-BYTES-PER-ROW 80)
(SETQ M65-SCREEN-BANK4-WIDTH 640)
(SETQ M65-SCREEN-BANK4-HEIGHT 200)
(SETQ M65-SCREEN-BANK4-BYTES 16000)

(DE m65-pow2 (N) (COND ((ZEROP N) 1) (T (TIMES 2 (m65-pow2 (SUB1 N))))))
(DE m65-bit-n (N) (m65-pow2 N))

(DE m65-h640-addr (X Y)
  (PLUS M65-BITPLANE-BASE
    (PLUS (TIMES Y M65-H640-BYTES-PER-ROW) (QUOTIENT X 8))))

(DE m65-h640-bit (X) (m65-bit-n (DIFFERENCE 7 (LOGAND X 7))))

(DE m65-platform-backend () M65-PLATFORM-BACKEND-DIRECT-H640)

(DE m65-visible-screen-backend () M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4)

(DE m65-screen-bank4-byte-offset (X Y)
  (PLUS (TIMES Y M65-SCREEN-BANK4-BYTES-PER-ROW) (QUOTIENT X 8)))

(DE m65-screen-bank4-addr (X Y)
  (PLUS M65-SCREEN-BANK4-BASE
    (m65-screen-bank4-byte-offset X Y)))

(DE m65-screen-bank4-bit (X) (m65-bit-n (DIFFERENCE 7 (LOGAND X 7))))

(DE m65-screen-bank4-end ()
  (SUB1 (PLUS M65-SCREEN-BANK4-BASE M65-SCREEN-BANK4-BYTES)))

; C65/VIC-III-Bitplane-Adressen kodieren Basisbits 15:13 in Registerbits 1:3
; und 5:7. Fuer $2000 (Basisindex 1) ergibt das $22.
(DE m65-bitplane-reg-byte (ADDR)
  (TIMES 34 (LOGAND (QUOTIENT ADDR 8192) 7)))
