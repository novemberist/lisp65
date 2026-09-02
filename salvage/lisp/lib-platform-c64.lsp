; lib-platform-c64 -- C64-Backend fuer den Plattform-Layer (lib-platform).
; Bindet die Backend-Primitive an echte C64-Hardware. Prototyp:
;  - Grafik = Hi-Res-Bitmap-Plot ($2000) plus Screen-RAM-Farbbyte ($0400) via POKE.
;  - Ton = direkte SID-Registerschreibung via POKE (kein gegatetes Natives noetig).
;  - Tasten = GETKEY (Phase-5-Natives; Build mit TERM_TEST_PHASE5_GETKEY_NATIVE).
;  - Laden = LOAD.
;
; Abhaengigkeit: lisp/lib-c64hw.lsp (Register-/Farbkonstanten) zuerst laden.
; Geraet/REPL: (LOAD lib-c64hw) (LOAD lib-platform) (LOAD lib-platform-c64).
; Host: laedt/definiert sauber; Aufrufe brauchen echte POKE/GETKEY/LOAD (Geraet).

; ---- Grafik: Hi-Res-Pixel setzen ----------------------------------------
(DE plat-plot (X Y C)
  (PROG (A CELL)
    (SETQ A (hires-plot-addr X Y))
    (POKE A (LOGOR (PEEK A) (hires-plot-bit X)))
    (SETQ CELL (PLUS SCREEN-BASE (hires-cell-offset X Y)))
    (POKE CELL (hires-color-byte C C64-BLACK))
    (RETURN T)))

; ---- Bildschirm/Rahmen faerben und Bitmap-Modus waehlen -----------------
(DE plat-clear (C)
  (PROG ()
    (POKE VIC-BORDER C)
    (POKE VIC-BACKGROUND C)
    (POKE VIC-CONTROL1 (LOGOR (PEEK VIC-CONTROL1) 32)) ; Bitmap-Modus an
    (POKE VIC-MEMORY 24)                               ; Screen $0400, Bitmap $2000
    (RETURN T)))

; ---- Taste lesen (nativ) -------------------------------------------------
(DE plat-getkey () (GETKEY))

; ---- Ton: SID-Stimme V (0..2) per direkter Registerschreibung ------------
(DE plat-tone (V FREQ WAVE)
  (PROG (B)
    (SETQ B (PLUS SID-BASE (TIMES 7 V)))  ; Stimmen-Registerbasis
    (POKE SID-VOLUME 15)                   ; max. Lautstaerke
    (POKE (PLUS B 5) 9)                     ; Attack/Decay
    (POKE (PLUS B 6) 240)                   ; Sustain/Release
    (POKE B (LBYTE FREQ))                   ; Frequenz low
    (POKE (PLUS B 1) (HBYTE FREQ))          ; Frequenz high
    (POKE (PLUS B 4) WAVE)                  ; Control (Wellenform + Gate)
    (RETURN T)))

; ---- Datei laden ---------------------------------------------------------
(DE plat-load (NAME) (LOAD NAME))
