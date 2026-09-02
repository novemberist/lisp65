; lib-platform -- duenne, backend-agnostische Hardware-Abstraktion (Plattform-Layer).
; Idee (docs/Projektnotizen_Architektur_2026-06-24.md, Abschnitt 2 + docs/platform-layer.md):
; Anwendungen nutzen DIESELBE API auf PC (Host), C64 und spaeter MEGA65. Die
; High-Level-API (Linien, Rechtecke, Ton, Tasten, Laden) ist EINMAL hier definiert
; -- in Form von Algorithmen ueber wenige Backend-Primitive, die jedes Backend
; bereitstellt. Kein residenter .acme-Code: reine ladbare Lisp-Bibliothek.
;
; Backend-Vertrag -- ein Backend MUSS definieren (vor dem ersten API-Aufruf):
;   (plat-plot X Y C)        ; einen Punkt/Zelle (X,Y) in Farbe C setzen
;   (plat-clear C)           ; Bildschirm/Hintergrund in Farbe C loeschen
;   (plat-getkey)            ; naechste Taste als Code, 0 wenn keine
;   (plat-tone V FREQ WAVE)  ; Stimme V mit Frequenz FREQ/Wellenform WAVE toenen
;   (plat-load NAME)         ; Datei NAME laden
; Backends: lisp/lib-platform-c64.lsp (nativ, Geraet), Mock im Test (Host).
;
; Lauf (Host, mit Mock-Backend):
;   python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp \
;     lisp/platform-tests.lsp

; ---- kleine Integer-Helfer (backend-unabhaengig) ----
(DE plat-abs (N) (COND ((MINUSP N) (DIFFERENCE 0 N)) (T N)))
(DE plat-sign (N)
  (COND ((MINUSP N) (DIFFERENCE 0 1))
        ((ZEROP N) 0)
        (T 1)))
(DE plat-both-eq (A B C D)        ; T, wenn A=B UND C=D (vermeidet AND-Abhaengigkeit)
  (COND ((EQUAL A B) (EQUAL C D)) (T NIL)))

; ---- Eingabe ----
(DE read-key () (plat-getkey))

; ---- Grafik: ein Punkt ----
(DE plot (X Y C) (plat-plot X Y C))

; ---- Grafik: Linie (ganzzahliger Bresenham, einmal fuer alle Backends) ----
(DE draw-line (X0 Y0 X1 Y1 C)
  (PROG (DX DY SX SY ERR E2)
    (SETQ DX (plat-abs (DIFFERENCE X1 X0)))
    (SETQ DY (plat-abs (DIFFERENCE Y1 Y0)))
    (SETQ SX (plat-sign (DIFFERENCE X1 X0)))
    (SETQ SY (plat-sign (DIFFERENCE Y1 Y0)))
    (SETQ ERR (DIFFERENCE DX DY))
   LOOP
    (plat-plot X0 Y0 C)
    (COND ((plat-both-eq X0 X1 Y0 Y1) (RETURN T)))
    (SETQ E2 (TIMES 2 ERR))
    (COND ((GREATERP E2 (DIFFERENCE 0 DY))
           (SETQ ERR (DIFFERENCE ERR DY))
           (SETQ X0 (PLUS X0 SX))))
    (COND ((LESSP E2 DX)
           (SETQ ERR (PLUS ERR DX))
           (SETQ Y0 (PLUS Y0 SY))))
    (GO LOOP)))

; ---- Grafik: Rechteck-Umriss (vier Linien) ----
(DE draw-rectangle (X0 Y0 X1 Y1 C)
  (PROG ()
    (draw-line X0 Y0 X1 Y0 C)
    (draw-line X0 Y1 X1 Y1 C)
    (draw-line X0 Y0 X0 Y1 C)
    (draw-line X1 Y0 X1 Y1 C)
    (RETURN T)))

; ---- Grafik: gefuelltes Rechteck (Annahme Y1>=Y0) ----
(DE fill-rectangle (X0 Y0 X1 Y1 C)
  (PROG (Y)
    (SETQ Y Y0)
   LOOP
    (draw-line X0 Y X1 Y C)
    (COND ((NOT (LESSP Y Y1)) (RETURN T)))
    (SETQ Y (ADD1 Y))
    (GO LOOP)))

; ---- Bildschirm loeschen ----
(DE clear-screen (C) (plat-clear C))

; ---- Audio ----
(DE play-tone (VOICE FREQ WAVE) (plat-tone VOICE FREQ WAVE))
(DE play-sample (VOICE FREQ WAVE) (plat-tone VOICE FREQ WAVE))  ; Alias (Notiz: play-sample)

; ---- Dateien ----
(DE load-file (NAME) (plat-load NAME))
