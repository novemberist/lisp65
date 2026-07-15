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
 * Scroll: Zeilen 1..rows-1 um eine Zeile hochkopieren, letzte Zeile leeren. Default:
 * CPU-Kopie; der EDMA-Scroll bleibt ein opt-in Messpfad
 * (-DLISP65_SCREEN_EDMA_SCROLL), bis Footprint und IDE-Hotpath-Gates gruen sind. */
#include "screen.h"

#ifndef __mos__
#include <string.h>
/* Host-Simulation: festes 80x25-Abbild fuer Tests. */
#define SIM_COLS 80
#define SIM_ROWS 25
static uint8_t sim[SIM_COLS * SIM_ROWS];
static uint8_t *scr_base = sim;
#else
#ifdef LISP65_SCREEN_EDMA_SCROLL
#include <mega65.h>
#endif
static uint8_t *scr_base;
#define VIC31   (*(volatile uint8_t *)0xD031)
#define SCRNPTRL (*(volatile uint8_t *)0xD060)
#define SCRNPTRH (*(volatile uint8_t *)0xD061)
#endif

/* Das CPU-sichtbare Farb-RAM-Fenster bei $D800 ist nur 1 KB gross ($D800-$DBFF). Ein Farb-Store
 * mit einem Offset >= 1024 laeuft daher NICHT in Farb-RAM, sondern in $DC00-$DFFF = CIA/VIC-I/O
 * (z.B. $DD00 = CIA2 VIC-Bank-Select). Auf einem 80x25-Schirm betrifft das die Zeilen >= 13. Ein
 * solcher Fehl-Store kippt die VIC-Bank -> falsche Anzeige-Region (der frueher gejagte "Scroll-
 * Muell", per HW-A/B 2026-07-08 als Root Cause bewiesen). Farb-Stores deshalb strikt auf dieses
 * Fenster begrenzen. Volle Farbe fuer die unteren Zeilen ist ein Follow-up ueber den 28-Bit-
 * Farbpfad ($FF80000, wie der EDMA-Scroll), nicht ueber das $D800-Fenster. */
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
#define M65_COLOR_RAM_28 0x0ff80000ul

struct screen_edma_job {
    uint8_t options[7];
    uint8_t end_option;
    uint8_t dmalist[12];
};

__attribute__((used)) static struct screen_edma_job screen_edma;

static void screen_edma_common(uint8_t cmd, uint32_t src, uint32_t dst,
                               uint16_t count, uint8_t fill_value) {
    screen_edma.options[0] = ENABLE_F018B_OPT;
    screen_edma.options[1] = SRC_ADDR_BITS_OPT;
    screen_edma.options[2] = (uint8_t)(src >> 20);
    screen_edma.options[3] = DST_ADDR_BITS_OPT;
    screen_edma.options[4] = (uint8_t)(dst >> 20);
    screen_edma.options[5] = DST_SKIP_RATE_OPT;
    screen_edma.options[6] = 1;
    screen_edma.end_option = 0;

    screen_edma.dmalist[0] = cmd;
    screen_edma.dmalist[1] = (uint8_t)count;
    screen_edma.dmalist[2] = (uint8_t)(count >> 8);
    if (cmd == DMA_FILL_CMD) {
        screen_edma.dmalist[3] = fill_value;
        screen_edma.dmalist[4] = 0;
        screen_edma.dmalist[5] = 0;
    } else {
        screen_edma.dmalist[3] = (uint8_t)src;
        screen_edma.dmalist[4] = (uint8_t)(src >> 8);
        screen_edma.dmalist[5] = (uint8_t)((src >> 16) & 0x0f);
    }
    screen_edma.dmalist[6] = (uint8_t)dst;
    screen_edma.dmalist[7] = (uint8_t)(dst >> 8);
    screen_edma.dmalist[8] = (uint8_t)((dst >> 16) & 0x0f);
    screen_edma.dmalist[9] = 0;
    screen_edma.dmalist[10] = 0;
    screen_edma.dmalist[11] = 0;

    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(screen_edma)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(screen_edma)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
}

static void screen_edma_copy(uint32_t src, uint32_t dst, uint16_t count) {
    screen_edma_common(DMA_COPY_CMD, src, dst, count, 0);
}

static void screen_edma_fill(uint32_t dst, uint8_t value, uint16_t count) {
    screen_edma_common(DMA_FILL_CMD, 0, dst, count, value);
}
#endif

static void scroll_up(void) {
    /* Eigenes Scrollen — genau das, was der KERNAL nicht crashfrei kann. */
    uint16_t n = (uint16_t)(rows_ - 1) * cols_;
#if defined(__mos__) && defined(LISP65_SCREEN_EDMA_SCROLL)
    uint32_t base = (uint32_t)(uintptr_t)scr_base;
    screen_edma_copy(base + cols_, base, n);
    screen_edma_fill(base + n, 0x20, cols_);
    screen_edma_copy(M65_COLOR_RAM_28 + cols_, M65_COLOR_RAM_28, n);
    screen_edma_fill(M65_COLOR_RAM_28 + n, 1, cols_);
#else
    uint16_t i;
    uint8_t *dst = scr_base, *src = scr_base + cols_;
    for (i = 0; i < n; i++) dst[i] = src[i];
    fill_row((uint8_t)(rows_ - 1));
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
    (void)attr;
#endif
}

/* Schneller Zeilen-Schreiber (2026-07-03): Basis-Zeiger EINMAL, dann lineare Stores.
 * scr_put_at je Zeichen kostete ~1500 Zyklen (Software-Mul y*cols_ + Checks) — bei
 * gepaddeten 80-Zeichen-Zeilen ~5 ms je Bulk-Write, gemessen in xemu ($D7FA-Frames).
 * chars: ASCII-Quelle oder NULL (nur padden); attr wie scr_put_at (Bit7=RVS, Bit6 hier
 * ohne Bedeutung — der Aufrufer uebergibt pad_to als explizite Grenze). */
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
#endif
