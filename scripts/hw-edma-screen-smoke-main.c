/* lisp65 -- MEGA65 EDMA screen+Color-RAM scroll smoke.
 *
 * Required result: one visible 80x25 text page can be scrolled up by one row
 * with EDMA for both Screen RAM and the 28-bit Color-RAM range at $FF80000.
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

#define HW_SCREEN_COLS 80u
#define HW_SCREEN_ROWS 25u
#define HW_SCREEN_SCROLL_BYTES ((HW_SCREEN_ROWS - 1u) * HW_SCREEN_COLS)

enum {
    HW_SCREEN_GEOMETRY = 0,
    HW_SCREEN_COPY_TOP,
    HW_SCREEN_COPY_LAST_VISIBLE,
    HW_SCREEN_TAIL_FILL,
    HW_SCREEN_COLOR_COPY_TOP,
    HW_SCREEN_COLOR_COPY_LAST_VISIBLE,
    HW_SCREEN_COLOR_TAIL_FILL,
    HW_SCREEN_CASES
};

__attribute__((used)) volatile uint8_t hw_screen_pass;
__attribute__((used)) volatile uint8_t hw_screen_total;
__attribute__((used)) volatile uint8_t hw_screen_results[HW_SCREEN_CASES];
__attribute__((used)) volatile uint16_t hw_screen_got[HW_SCREEN_CASES];
__attribute__((used)) volatile uint16_t hw_screen_want[HW_SCREEN_CASES];

static uint8_t color_back[3];

static uint16_t screen_base_addr(void) {
    uint16_t lo = *(volatile uint8_t *)0xd060;
    uint16_t hi = *(volatile uint8_t *)0xd061;
    uint16_t addr = (uint16_t)(lo | (hi << 8));
    return addr ? addr : 0x0800u;
}

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

static void record(uint8_t idx, uint8_t ok, uint16_t got, uint16_t want) {
    hw_screen_results[idx] = ok ? 1 : 0;
    hw_screen_got[idx] = got;
    hw_screen_want[idx] = want;
    hw_screen_total++;
    if (ok) hw_screen_pass++;
}

static uint8_t row_code(uint8_t row) {
    return (uint8_t)(row + 1u);
}

static uint8_t row_color(uint8_t row) {
    return (uint8_t)((row % 15u) + 1u);
}

static void seed_screen(uint16_t base) {
    volatile uint8_t *screen = (volatile uint8_t *)(uintptr_t)base;
    uint8_t row, col;
    for (row = 0; row < HW_SCREEN_ROWS; row++) {
        uint8_t code = row_code(row);
        for (col = 0; col < HW_SCREEN_COLS; col++) {
            screen[(uint16_t)row * HW_SCREEN_COLS + col] = code;
        }
        hw_edma_fill(HW_M65_COLOR_RAM + (uint32_t)row * HW_SCREEN_COLS,
                     row_color(row), HW_SCREEN_COLS);
    }
}

static void run_scroll_checks(void) {
    uint16_t base = screen_base_addr();
    volatile uint8_t *screen = (volatile uint8_t *)(uintptr_t)base;

    record(HW_SCREEN_GEOMETRY,
           scr_cols() == HW_SCREEN_COLS && scr_rows() == HW_SCREEN_ROWS,
           (uint16_t)(((uint16_t)scr_rows() << 8) | scr_cols()),
           (uint16_t)((HW_SCREEN_ROWS << 8) | HW_SCREEN_COLS));

    seed_screen(base);
    /* Drive the product scroll path, not a duplicate DMA recipe in the smoke. */
    {
        uint8_t row;
        for (row = 0; row < HW_SCREEN_ROWS; row++) scr_putc('\n');
    }

    record(HW_SCREEN_COPY_TOP,
           screen[0] == row_code(1),
           screen[0], row_code(1));
    record(HW_SCREEN_COPY_LAST_VISIBLE,
           screen[(uint16_t)(HW_SCREEN_ROWS - 2u) * HW_SCREEN_COLS] ==
               row_code(HW_SCREEN_ROWS - 1u),
           screen[(uint16_t)(HW_SCREEN_ROWS - 2u) * HW_SCREEN_COLS],
           row_code(HW_SCREEN_ROWS - 1u));
    record(HW_SCREEN_TAIL_FILL,
           screen[(uint16_t)(HW_SCREEN_ROWS - 1u) * HW_SCREEN_COLS] == 0x20,
           screen[(uint16_t)(HW_SCREEN_ROWS - 1u) * HW_SCREEN_COLS], 0x20);

    hw_edma_copy(HW_M65_COLOR_RAM, (uint32_t)(uintptr_t)&color_back[0], 1);
    hw_edma_copy(HW_M65_COLOR_RAM + (uint32_t)(HW_SCREEN_ROWS - 2u) * HW_SCREEN_COLS,
                 (uint32_t)(uintptr_t)&color_back[1], 1);
    hw_edma_copy(HW_M65_COLOR_RAM + (uint32_t)(HW_SCREEN_ROWS - 1u) * HW_SCREEN_COLS,
                 (uint32_t)(uintptr_t)&color_back[2], 1);

    record(HW_SCREEN_COLOR_COPY_TOP,
           color_back[0] == row_color(1),
           color_back[0], row_color(1));
    record(HW_SCREEN_COLOR_COPY_LAST_VISIBLE,
           color_back[1] == row_color(HW_SCREEN_ROWS - 1u),
           color_back[1], row_color(HW_SCREEN_ROWS - 1u));
    record(HW_SCREEN_COLOR_TAIL_FILL,
           color_back[2] == 1,
           color_back[2], 1);
}

static void show_result(void) {
    uint8_t pass = (hw_screen_pass == hw_screen_total);
    hw_border(pass ? COLOR_GREEN : COLOR_RED);
    scr_put_at(0, 24, pass ? 'p' : 'f', 1);
    scr_put_at(1, 24, pass ? 'a' : 'a', 1);
    scr_put_at(2, 24, pass ? 's' : 'i', 1);
    scr_put_at(3, 24, pass ? 's' : 'l', 1);
    puts_scr("\nedma screen ");
    puts_scr(pass ? "pass " : "fail ");
    put_u8(hw_screen_pass);
    scr_putc('/');
    put_u8(hw_screen_total);
    scr_putc('\n');
}

int main(void) {
    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    hw_screen_pass = 0;
    hw_screen_total = 0;
    run_scroll_checks();
    show_result();
    for (;;) { }
    return 0;
}
