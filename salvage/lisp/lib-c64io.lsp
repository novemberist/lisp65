; lib-c64io -- Komfort-Wrapper, die in das simulierte C64-RAM poken (PEEK/POKE).
; Macht die Phase-5-Ausgabeschicht END-TO-END host-testbar: Berechnung (lib-c64fx)
; UND die erzeugten Poke-Bytes -- ohne VICE. Auf echtem C64 sind es dieselben
; Pokes. Spec: docs/phase5-hardware.md, docs/highlevel-api-ideas.md.
;
; BARE DIALEKT (nur native Primitive + PROG, KEIN LET) -> auf dem echten System
; ladbar. Braucht: lib-c64hw (Konstanten/Register/SID) + lib-c64fx
; (line-points/circle-points/shape/melody). PEEK/POKE existieren resident.

; ---- Screen / Farben ----
(DE border (c) (POKE VIC-BORDER (LOGAND c 15)))
(DE background (c) (POKE VIC-BACKGROUND (LOGAND c 15)))
(DE screen-poke (x y code) (POKE (PLUS SCREEN-BASE (PLUS (TIMES y 40) x)) code))
(DE screen-at (x y) (PEEK (PLUS SCREEN-BASE (PLUS (TIMES y 40) x))))

; ---- Sprites ----
(DE sprite-at (n x y)
  (POKE (spr-x-reg n) (spr-x-lo x))
  (POKE (spr-y-reg n) y)
  (POKE VIC-SPRITE-XMSB (spr-set-xmsb (PEEK VIC-SPRITE-XMSB) n x)))
(DE sprite-color (n c) (POKE (spr-color-reg n) (LOGAND c 15)))
(DE sprite-on (n) (POKE VIC-SPRITE-ENABLE (LOGOR (PEEK VIC-SPRITE-ENABLE) (bit-n n))))
(DE sprite-off (n) (POKE VIC-SPRITE-ENABLE (LOGAND (PEEK VIC-SPRITE-ENABLE) (LOGXOR 255 (bit-n n)))))

; ---- Bitmap-Malen (C64-Hi-Res-Layout: 8x8-Zellen, byte = y&7) ----
(DE plot-addr (x y) (hires-plot-addr x y))
(DE plot (x y)
  (PROG (a)
    (SETQ a (plot-addr x y))
    (RETURN (POKE a (LOGOR (PEEK a) (hires-plot-bit x))))))
(DE plot-pt (pt) (plot (CAR pt) (CDR pt)))
(DE draw-points (pts)
  (COND ((NULL pts) NIL) (T (plot-pt (CAR pts)) (draw-points (CDR pts)))))
(DE line (x0 y0 x1 y1) (draw-points (line-points x0 y0 x1 y1)))
(DE circle (cx cy r) (draw-points (circle-points cx cy r)))

; ---- Sound (SID-Frequenzregister setzen; Voice 0..2 -> SID-BASE + 7*voice) ----
(DE voice-base (voice) (PLUS SID-BASE (TIMES 7 voice)))
(DE sound (voice name octave)
  (PROG (f vb)
    (SETQ f (sid-note-name name octave))
    (SETQ vb (voice-base voice))
    (POKE vb (addr-lo f))
    (RETURN (POKE (PLUS vb 1) (addr-hi f)))))
; Melodie der Reihe nach in die Frequenzregister schreiben (Poke-Log = Sequenz)
(DE play-note (voice nf) (POKE (voice-base voice) (addr-lo (CAR nf)))
                         (POKE (PLUS (voice-base voice) 1) (addr-hi (CAR nf))))
(DE play (tune voice) (play-aux tune voice))
(DE play-aux (tune voice)
  (COND ((NULL tune) NIL)
        (T (play-note voice (note->freq (CAR tune))) (play-aux (CDR tune) voice))))
