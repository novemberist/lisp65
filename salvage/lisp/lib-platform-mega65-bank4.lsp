; lib-platform-mega65-bank4 -- sichtbarer MEGA65-Bank-4-Backend-Schnitt.
;
; Alternative zu lib-platform-mega65.lsp: Dieses Backend zielt auf den von
; BASIC65 `SCREEN 640,200,1` belegten 1-Bitplane-Framebuffer ab linear $40000.
; Der Geraetepfad initialisiert den sichtbaren Modus derzeit noch per BASIC65;
; hostseitig sind Adressierung, Clear und Plot ueber erweitertes PEEK/POKE-RAM
; testbar.
;
; Abhaengigkeit: lisp/lib-mega65hw.lsp zuerst laden.

(DE m65-platform-backend () M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4)

(DE m65-bank4-clear ()
  (PROG (A E)
    (SETQ A M65-SCREEN-BANK4-BASE)
    (SETQ E (PLUS M65-SCREEN-BANK4-BASE M65-SCREEN-BANK4-BYTES))
   LOOP
    (COND ((NOT (LESSP A E)) (RETURN T)))
    (POKE A 0)
    (SETQ A (ADD1 A))
    (GO LOOP)))

; ---- Grafik: sichtbares ROM-SCREEN-Bank-4-Pixel setzen/loeschen ---------
(DE plat-plot (X Y C)
  (PROG (A B)
    (SETQ A (m65-screen-bank4-addr X Y))
    (SETQ B (m65-screen-bank4-bit X))
    (COND ((ZEROP C) (POKE A (LOGAND (PEEK A) (LOGXOR 255 B))))
          (T (POKE A (LOGOR (PEEK A) B))))
    (RETURN T)))

; ---- Sichtbaren Bank-4-Framebuffer loeschen -----------------------------
(DE plat-clear (C)
  (PROG ()
    (POKE M65-VIC-KEY 71)   ; "G"
    (POKE M65-VIC-KEY 83)   ; "S"
    (POKE M65-VIC-BORDER C)
    (POKE M65-VIC-BACKGROUND C)
    (POKE M65-VIC4-CTRL-A 100)
    (POKE M65-VIC3-CTRL-B (LOGOR (PEEK M65-VIC3-CTRL-B) 240))
    (m65-bank4-clear)
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
