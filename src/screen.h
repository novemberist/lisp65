/* lisp65 — eigener Screen-Treiber (Lane K, IDE-Fundament Phase 1)
 *
 * WARUM: Der KERNAL-Editor ist fuer uns unbrauchbar geworden — sein Scroll CRASHT jedes
 * llvm-mos-PRG (HW-bewiesen, docs/mvp-hw-findings.md), sein CLR ist zustandsfragil, und
 * die REPL musste deshalb mit einem Loesch-statt-Scroll-Guard leben. Dieser Treiber
 * schreibt direkt ins Screen-RAM, scrollt selbst (CPU-Kopie, bei 40 MHz unkritisch) und
 * liest die Geometrie beim Init aus den VIC-IV-Registern. Eingabe bleibt KERNAL-GETIN
 * (bewaehrt); NUR der Ausgabepfad wandert hierher.
 *
 * Gegatet -DLISP65_SCREEN_DRIVER: ohne das Flag bleibt alles beim alten CHROUT-Pfad.
 * Host-Builds: Puffer-Simulation (scr_host_dump fuer Tests). */
#ifndef LISP65_SCREEN_H
#define LISP65_SCREEN_H

#include <stdint.h>

void scr_init(void);          /* Geometrie lesen, loeschen, Cursor home */
void scr_clear(void);         /* Schirm leeren + Cursor home (ersetzt CHROUT 0x93) */
void scr_putc(char c);        /* ASCII-Zeichen am Cursor ausgeben; '\n'/'\r' = Zeilenwechsel */
void scr_backspace(void);     /* Zeichen links vom Cursor loeschen (DEL) */
void scr_cursor(uint8_t on);  /* Block-Cursor am aktuellen Ort zeigen/verstecken */
void scr_put_at(uint8_t x, uint8_t y, char c, int16_t attr);  /* Direktzelle; attr<0 = Farbe lassen */
void scr_write_span(uint8_t x, uint8_t y, const char *chars, uint8_t nchars,
                    uint8_t pad_to, int16_t attr);  /* schnelle Zeile: Basiszeiger + lineare Stores */

uint8_t scr_cols(void);       /* erkannte Geometrie (Diagnose/Tests) */
uint8_t scr_rows(void);
uint8_t scr_row(void);        /* aktuelle Cursorzeile (fuer REPL-Heuristiken) */

#ifndef __mos__
const uint8_t *scr_host_buf(void);   /* Host-Test: rohes Screen-Abbild (cols*rows) */
#endif

#endif /* LISP65_SCREEN_H */
