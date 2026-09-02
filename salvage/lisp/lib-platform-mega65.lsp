; lib-platform-mega65 -- erster MEGA65-Backend-Schnitt fuer lib-platform.
; Prototyp: monochrome H640-Bitplane 0. (plat-plot X Y 0) loescht ein Bit,
; jeder andere Farbwert setzt es. Volle Farbebenen/Palette und Geraete-Smoke
; folgen erst mit MEGA65-Buildpfad.
;
; Abhaengigkeit: lisp/lib-mega65hw.lsp zuerst laden.
; Host: mit simuliertem PEEK/POKE-RAM testbar.

; ---- Grafik: H640-Bitplane-0-Pixel setzen/loeschen ----------------------
(DE plat-plot (X Y C)
  (PROG (A B)
    (SETQ A (m65-h640-addr X Y))
    (SETQ B (m65-h640-bit X))
    (COND ((ZEROP C) (POKE A (LOGAND (PEEK A) (LOGXOR 255 B))))
          (T (POKE A (LOGOR (PEEK A) B))))
    (RETURN T)))

; ---- VIC-IV freischalten und monochromen H640-Bitplane-Modus waehlen ----
(DE plat-clear (C)
  (PROG ()
    (POKE M65-VIC-KEY 71)   ; "G"
    (POKE M65-VIC-KEY 83)   ; "S"
    (POKE M65-VIC-BORDER C)
    (POKE M65-VIC-BACKGROUND C)
    (POKE M65-VIC4-CTRL-A 100) ; ROM SCREEN 640,200,1 setzt $64
    (POKE M65-VIC3-CTRL-B (LOGOR (PEEK M65-VIC3-CTRL-B) 240))
    (POKE M65-BP-ENABLE 1)
    (POKE M65-BP0-ADDR (m65-bitplane-reg-byte M65-BITPLANE-BASE))
    (RETURN T)))

; ---- Taste/Audio/Datei ---------------------------------------------------
(DE plat-getkey () (GETKEY))

(DE plat-tone (V FREQ WAVE)
  (PROG (B)
    (SETQ B (PLUS M65-SID0-BASE (TIMES 7 V)))
    (POKE M65-SID0-VOLUME 15)
    (POKE (PLUS B 5) 9)
    (POKE (PLUS B 6) 240)
    (POKE B (LBYTE FREQ))
    (POKE (PLUS B 1) (HBYTE FREQ))
    (POKE (PLUS B 4) WAVE)
    (RETURN T)))

(DE plat-load (NAME) (LOAD NAME))
