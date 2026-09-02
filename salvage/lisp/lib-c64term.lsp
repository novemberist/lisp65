; lib-c64term -- Text-Ausgabe-Bruecke C64-Screen-RAM (Phase 5, ladbar).
;
; Schliesst die Phase-8-Ausgabe-Luecke KOLLISIONSFREI: rein ladbares Lisp auf den
; schon vorhandenen nativen Primitiven (PEEK/POKE via lib-c64io screen-poke).
; KEIN Eingriff in den nativen Baum, KEIN neues OBLIST-Primitiv -> keine Kollision
; mit Codex' aktueller Arbeit (s. docs/phase5-native-readiness-audit.md).
;
; Bietet: ASCII/PETSCII -> C64-Screen-Code-Konvertierung, String-Ausgabe an (x,y),
; Modell-Blit (Liste von Strings -> Screen-RAM) und die direkte Bruecke
; compose-screen-Frame -> echtes Screen-RAM (term-render-app).
;
; Lauf (Bruecke + IDE-Render): siehe lisp/c64term-tests.lsp
; Abhaengigkeit: lib-c64hw + lib-c64io (screen-poke/screen-at/SCREEN-BASE).

; LOAD-Vertrag fuer das kleine MVP-Paket: die Runtime setzt nur die Adresse, die
; POKE-Funktionen kommen aus dem SAVEFMT-Terminalprofil.
(DE C64TERMINIT ()
  (SETQ SCREEN-BASE 1024))

; ---- Char -> C64-Screen-Code (kanonische PETSCII->Screencode-Abbildung) ----
;   0..31   -> +128    (reverse Steuerbereich)
;   32..63  -> unveraendert (Space, Ziffern, Satzzeichen)
;   64..95  -> -64      (@ A-Z [ \ ] ^ _  ->  0..31)
;   96..127 -> -32
;   sonst   -> unveraendert
(DE ascii->screencode (c)
  (COND ((LESSP c 32)  (PLUS c 128))
        ((LESSP c 64)  c)
        ((LESSP c 96)  (DIFFERENCE c 64))
        ((LESSP c 128) (DIFFERENCE c 32))
        (T c)))

(DE char->screencode (ch) (ascii->screencode (ASC ch)))

; ---- String an Spalte x, Zeile y in Screen-RAM schreiben ----
(DE term-puts-aux (x y chars)
  (COND ((NULL chars) NIL)
        (T (screen-poke x y (char->screencode (CAR chars)))
           (term-puts-aux (ADD1 x) y (CDR chars)))))
(DE term-puts (x y str) (term-puts-aux x y (UNPACK str)))

; ---- Modell (Liste von Zeilen-Strings) ab Zeile 0 blitten ----
(DE term-blit-aux (y rows)
  (COND ((NULL rows) NIL)
        (T (term-puts 0 y (CAR rows))
           (term-blit-aux (ADD1 y) (CDR rows)))))
(DE term-blit (rows) (term-blit-aux 0 rows))

; ---- Phase-8<->5-Bruecke: eine IDE-Frame in echtes Screen-RAM rendern ----
; (compose-screen liefert HEIGHT width-breite Zeilen; term-blit pokt sie.)
(DE term-render-app (app width height)
  (term-blit (compose-screen (app-session app) 0 height width)))
