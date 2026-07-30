/* lisp65 — eigener Screen-Treiber (Lane K). Siehe screen.h fuer das Warum.
 *
 * Geraet (mega65): Geometrie aus VIC-IV — $D031 Bit7 (H640: 80 Spalten) und Bit3
 * (V400: 50 Zeilen); Screen-Basis aus SCRNPTR $D060/$D061 (VIC-IV, Bank-0-Annahme;
 * KERNAL-Default $0800). Zeichensatz: der KERNAL hat beim Boot Farb-RAM und Charset
 * initialisiert — wir schreiben nur Screen-Codes, Farben bleiben stehen (bewiesen:
 * die CLR-Diagnose schrieb direkt ins Screen-RAM, Zeichen erschienen weiss auf blau).
 *
 * ASCII -> Screen-Code (Mixed-Case-Charset, wie chr$(14)):
 *   'a'..'z' -> 0x01..0x1A  |  'A'..'Z' -> 0x41..0x5A  |  0x20..0x3F identisch
 * Scroll: Zeilen 1..rows-1 um eine Zeile hochkopieren, letzte Zeile leeren. Der
 * Enhanced-DMA-Pfad fuer getrennte Screen- und Farb-RAM-Jobs ist als isolierter
 * L-lite-Probe-Pfad verfuegbar. Nach den begrenzten Welle-3-Linkversuchen bleibt
 * das kanonische Workbench-Profil beim kleinen CPU-Fallback; die
 * Produktintegration ist als C2-Fracht dokumentiert. */
#include "screen.h"

/* Future product profiles that require the color-safe rider must opt into the
 * implementation explicitly.  Keeping the requirement separate lets the
 * current C2-deferred profile remain buildable while preserving the earned
 * fail-closed binding gate. */
#if defined(LISP65_SCREEN_EDMA_SCROLL_REQUIRED) && \
    !defined(LISP65_SCREEN_EDMA_SCROLL)
#error "Workbench color-safe scroll is required but LISP65_SCREEN_EDMA_SCROLL is absent"
#endif

#ifndef __mos__
#include <string.h>
/* Host-Simulation: festes 80x25-Abbild fuer Tests. */
#define SIM_COLS 80
#define SIM_ROWS 25
static uint8_t sim[SIM_COLS * SIM_ROWS];
static uint8_t sim_color[SIM_COLS * SIM_ROWS];
static uint8_t *scr_base = sim;
#else
static uint8_t *scr_base;
#define VIC31   (*(volatile uint8_t *)0xD031)
#define SCRNPTRL (*(volatile uint8_t *)0xD060)
#define SCRNPTRH (*(volatile uint8_t *)0xD061)
#endif

/* The CPU-visible colour RAM window at $D800 is only 1 KB in size ($D800-$DBFF). A colour store
 * at an offset >= 1024 therefore does NOT land in colour RAM but in $DC00-$DFFF = CIA/VIC I/O
 * (e.g. $DD00 = CIA2 VIC bank select). On an 80x25 screen that affects rows >= 13. Such a stray
 * store flips the VIC bank -> the wrong display region (the long-hunted "scroll garbage", proven
 * as the root cause by hardware A/B on 2026-07-08). Colour stores are therefore strictly bounded
 * to this window. Full colour for the lower rows is a follow-up through the 28-bit colour path
 * ($FF80000, as the EDMA scroll uses), not through the $D800 window. */
#define CRAM_WINDOW 1024u

static uint8_t cols_, rows_;
static uint8_t crow, ccol;
static uint8_t cursor_on;

static uint8_t *cell(uint8_t r, uint8_t c) {
    return scr_base + (uint16_t)r * cols_ + c;
}

static uint8_t to_screen(char ch) {
    uint8_t c = (uint8_t)ch;
    if (c >= 'a' && c <= 'z') return (uint8_t)(c - 0x60);   /* 0x01..0x1A */
    if (c >= 'A' && c <= 'Z') return c;                     /* 0x41..0x5A */
    if (c >= 0x20 && c <= 0x3F) return c;                   /* Ziffern/Interpunktion 1:1 */
    if (c == '[') return 0x1B;
    if (c == ']') return 0x1D;
    if (c == '@') return 0x00;
    return 0x20;                                            /* Unbekanntes: Leerzeichen */
}

static void fill_row(uint8_t r) {
    uint8_t *p = cell(r, 0);
    uint8_t i;
    for (i = 0; i < cols_; i++) p[i] = 0x20;
}

#if defined(__mos__) && defined(LISP65_SCREEN_EDMA_SCROLL)
#include "screen_scroll_overlay.h"
#if defined(LISP65_RUNTIME_OVERLAY)
#include "vm_runtime_overlay.h"
#endif
#endif

static void scroll_up(void) {
    /* Eigenes Scrollen — genau das, was der KERNAL nicht crashfrei kann. */
    uint16_t n = (uint16_t)(rows_ - 1) * cols_;
#if defined(__mos__) && defined(LISP65_SCREEN_EDMA_SCROLL)
    lisp65_screen_scroll_context context;
    uint8_t result = 1;
    context.screen_base = (uint16_t)(uintptr_t)scr_base;
    context.copy_bytes = n;
    context.columns = cols_;
#if defined(LISP65_RUNTIME_OVERLAY)
    if (vm_runtime_overlay_exec(LISP65_SCREEN_SCROLL_OVERLAY_SLOT,
                                &context, &result) != VM_RUNTIME_OVERLAY_OK ||
        result != 0) {
        /* Fail closed: lose the visible page instead of separating screen and
         * color state after a transport failure. */
        scr_clear();
    }
#else
    result = lisp65_screen_scroll_overlay_entry(&context);
    if (result != 0) scr_clear();
#endif
#else
    uint16_t i;
    uint8_t *dst = scr_base, *src = scr_base + cols_;
    for (i = 0; i < n; i++) dst[i] = src[i];
    fill_row((uint8_t)(rows_ - 1));
#ifndef __mos__
    for (i = 0; i < n; i++) sim_color[i] = sim_color[i + cols_];
    for (i = n; i < (uint16_t)(n + cols_); i++) sim_color[i] = 1;
#endif
#endif
}

void scr_init(void) {
#ifdef __mos__
    uint16_t i, n;
    scr_base = (uint8_t *)(uintptr_t)((uint16_t)SCRNPTRL | ((uint16_t)SCRNPTRH << 8));
    if (scr_base == 0) scr_base = (uint8_t *)0x0800;        /* Fallback: KERNAL-Default */
    cols_ = (VIC31 & 0x80) ? 80 : 40;
    rows_ = (VIC31 & 0x08) ? 50 : 25;
    /* Farb-RAM einmalig auf Weiss: wir scrollen nur Screen-Codes — Boot-Logo-Farben blieben sonst
     * als bunte Flecken stehen (HW-Probe 2026-07-02). NUR das 1-KB-Fenster $D800-$DBFF anfassen —
     * darueber liegt CIA/VIC-I/O, kein Farb-RAM (s. CRAM_WINDOW). */
    n = (uint16_t)cols_ * rows_;
    if (n > CRAM_WINDOW) n = CRAM_WINDOW;
    for (i = 0; i < n; i++) ((volatile uint8_t *)0xD800)[i] = 1;
#else
    cols_ = SIM_COLS; rows_ = SIM_ROWS;
    memset(sim_color, 1, sizeof(sim_color));
#endif
    cursor_on = 0;
    scr_clear();
}

void scr_clear(void) {
    uint8_t r;
    for (r = 0; r < rows_; r++) fill_row(r);
    crow = 0; ccol = 0;
}

void scr_cursor(uint8_t on) {
    uint8_t *p = cell(crow, ccol);
    if (on) { *p |= 0x80; } else { *p &= 0x7F; }
    cursor_on = on;
}

static void newline(void) {
    ccol = 0;
    if (crow + 1 >= rows_) scroll_up();
    else crow++;
}

void scr_putc(char c) {
    if (cursor_on) scr_cursor(0);                 /* Cursor nie "festdrucken" */
    if (c == '\n' || c == '\r') { newline(); return; }
    *cell(crow, ccol) = to_screen(c);
    if (++ccol >= cols_) newline();
}

/* Direkte Zelle setzen (IDE-Frame-Rendering, Codex-Vertrag docs/editor-architecture.md):
 * c = ASCII (Treiber mappt), attr: Bits 0-3 = Farbe ins $D800-Fenster (deckt 80x25 ab),
 * Bit 7 = REVERSE-VIDEO (RVS-Bit im Screen-Code — farbunabhaengig sichtbarer Cursor);
 * attr < 0 laesst Farbe UND RVS unangetastet. Cursorposition bleibt unberuehrt. */
void scr_put_at(uint8_t x, uint8_t y, char c, int16_t attr) {
    uint16_t off;
    uint8_t sc;
    if (x >= cols_ || y >= rows_) return;
    off = (uint16_t)y * cols_ + x;
    sc = to_screen(c);
    if (attr >= 0 && (attr & 0x80)) sc |= 0x80;
    scr_base[off] = sc;
#ifdef __mos__
    if (attr >= 0 && off < CRAM_WINDOW) ((volatile uint8_t *)0xD800)[off] = (uint8_t)(attr & 0x0F);
#else
    if (attr >= 0) sim_color[off] = (uint8_t)(attr & 0x0F);
#endif
}

/* Fast span writer (2026-07-03): compute the base pointer ONCE, then do linear stores.
 * scr_put_at per character cost about 1500 cycles (software multiply y*cols_ plus checks) —
 * roughly 5 ms per bulk write on padded 80-character rows, measured in xemu ($D7FA frames).
 * chars: an ASCII source or NULL (pad only); attr as in scr_put_at (bit 7 = RVS, bit 6 has no
 * meaning here — the caller passes pad_to as an explicit bound). */
void scr_write_span(uint8_t x, uint8_t y, const char *chars, uint8_t nchars,
                    uint8_t pad_to, int16_t attr) {
    uint8_t *p; uint8_t i, n, rvs;
    uint16_t off;
    if (y >= rows_ || x >= cols_) return;
    if (pad_to > cols_) pad_to = cols_;
    off = (uint16_t)y * cols_ + x;
    p = scr_base + off;
    n = (uint8_t)((nchars < (uint8_t)(cols_ - x)) ? nchars : (uint8_t)(cols_ - x));
    rvs = (attr >= 0 && (attr & 0x80)) ? 0x80 : 0;
    for (i = 0; i < n; i++) p[i] = (uint8_t)(to_screen(chars[i]) | rvs);
    for (; (uint8_t)(x + i) < pad_to; i++) p[i] = (uint8_t)(0x20 | rvs);
#ifdef __mos__
    if (attr >= 0 && off < CRAM_WINDOW) {
        volatile uint8_t *cp = (volatile uint8_t *)0xD800 + off;
        uint8_t col = (uint8_t)(attr & 0x0F), k;
        uint16_t room = (uint16_t)(CRAM_WINDOW - off);      /* nur bis zum Fensterende faerben */
        uint8_t lim = (i < room) ? i : (uint8_t)room;       /* Rest liegt in I/O -> nicht anfassen */
        for (k = 0; k < lim; k++) cp[k] = col;
    }
#else
    if (attr >= 0) {
        uint8_t col = (uint8_t)(attr & 0x0F), k;
        for (k = 0; k < i; k++) sim_color[off + k] = col;
    }
#endif
}

void scr_backspace(void) {
    if (cursor_on) scr_cursor(0);
    if (ccol > 0) ccol--;
    else if (crow > 0) { crow--; ccol = (uint8_t)(cols_ - 1); }
    *cell(crow, ccol) = 0x20;
}

uint8_t scr_cols(void) { return cols_; }
uint8_t scr_rows(void) { return rows_; }
uint8_t scr_row(void)  { return crow; }

#ifndef __mos__
const uint8_t *scr_host_buf(void) { return sim; }
const uint8_t *scr_host_color_buf(void) { return sim_color; }
#endif
