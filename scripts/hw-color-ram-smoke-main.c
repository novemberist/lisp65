/* lisp65 -- MEGA65 Color-RAM EDMA smoke/probe.
 *
 * Required result: EDMA can fill/read back the 28-bit Color-RAM range at
 * $FF80000 without CRAM2K. Flat write is recorded separately as exploratory.
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

enum {
    HW_COLOR_EDMA_FILL = 0,
    HW_COLOR_EDMA_PATTERN,
    HW_COLOR_FLAT_CELL_OBS,
    HW_COLOR_CASES
};

__attribute__((used)) volatile uint8_t hw_color_pass;
__attribute__((used)) volatile uint8_t hw_color_total;
__attribute__((used)) volatile uint8_t hw_color_results[HW_COLOR_CASES];
__attribute__((used)) volatile uint16_t hw_color_got[HW_COLOR_CASES];
__attribute__((used)) volatile uint16_t hw_color_want[HW_COLOR_CASES];

static uint8_t color_back[32];
static uint8_t color_pattern[16] = {
    1, 2, 3, 4, 5, 6, 7, 8,
    9, 10, 11, 12, 13, 14, 15, 1
};

static void puts_scr(const char *s) {
    while (*s) scr_putc(*s++);
}

static void put_u8(uint8_t n) {
    if (n >= 100) {
        scr_putc((char)('0' + n / 100));
        n = (uint8_t)(n % 100);
        scr_putc((char)('0' + n / 10));
    } else if (n >= 10) {
        scr_putc((char)('0' + n / 10));
    }
    scr_putc((char)('0' + n % 10));
}

static void record(uint8_t idx, uint8_t ok, uint16_t got, uint16_t want,
                   uint8_t required) {
    hw_color_results[idx] = ok ? 1 : 0;
    hw_color_got[idx] = got;
    hw_color_want[idx] = want;
    if (required) {
        hw_color_total++;
        if (ok) hw_color_pass++;
    }
}

static uint8_t all_eq(const uint8_t *p, uint8_t n, uint8_t want) {
    uint8_t i;
    for (i = 0; i < n; i++) if (p[i] != want) return 0;
    return 1;
}

static uint8_t same_bytes(const uint8_t *a, const uint8_t *b, uint8_t n) {
    uint8_t i;
    for (i = 0; i < n; i++) if (a[i] != b[i]) return 0;
    return 1;
}

static void draw_visible_pattern(void) {
    uint8_t x;
    scr_clear();
    puts_scr("color ram edma smoke\n");
    puts_scr("top row should show varied colors\n");
    for (x = 0; x < 16; x++) {
        scr_put_at(x, 4, (char)('a' + x), -1);
    }
}

static void run_color_checks(void) {
    uint8_t flat;

    hw_edma_fill(HW_M65_COLOR_RAM, 6, HW_M65_SCREEN_CELLS);
    hw_edma_copy(HW_M65_COLOR_RAM, (uint32_t)(uintptr_t)color_back, 32);
    record(HW_COLOR_EDMA_FILL, all_eq(color_back, 32, 6), color_back[31], 6, 1);

    hw_edma_copy((uint32_t)(uintptr_t)color_pattern, HW_M65_COLOR_RAM + 4u * 80u, 16);
    hw_edma_copy(HW_M65_COLOR_RAM + 4u * 80u, (uint32_t)(uintptr_t)color_back, 16);
    record(HW_COLOR_EDMA_PATTERN, same_bytes(color_pattern, color_back, 16),
           color_back[15], color_pattern[15], 1);

    hw_flat_write8(HW_M65_COLOR_RAM + 10u, 2);
    flat = 0;
    hw_edma_copy(HW_M65_COLOR_RAM + 10u, (uint32_t)(uintptr_t)&flat, 1);
    record(HW_COLOR_FLAT_CELL_OBS, flat == 2, flat, 2, 0);
}

static void show_result(void) {
    uint8_t pass = (hw_color_pass == hw_color_total);
    hw_border(pass ? COLOR_GREEN : COLOR_RED);
    scr_put_at(0, 7, pass ? 'p' : 'f', -1);
    puts_scr("\ncolor ram ");
    puts_scr(pass ? "pass " : "fail ");
    put_u8(hw_color_pass);
    scr_putc('/');
    put_u8(hw_color_total);
    puts_scr(" flat ");
    puts_scr(hw_color_results[HW_COLOR_FLAT_CELL_OBS] ? "yes" : "no");
    scr_putc('\n');
}

int main(void) {
    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    hw_color_pass = 0;
    hw_color_total = 0;
    draw_visible_pattern();
    run_color_checks();
    show_result();
    for (;;) { }
    return 0;
}
