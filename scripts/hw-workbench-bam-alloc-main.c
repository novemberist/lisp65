/* lisp65 -- M2 throwaway-D81 BAM allocation smoke.
 *
 * Writes exactly one 1581 BAM allocation bit in the mounted D81:
 * T45/S8, represented in BAM sector T40/S2 by free-count byte 40 and
 * bitmap byte 42. The shell harness verifies the downloaded D81 byte-for-byte.
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"
#include "f011_context.h"

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

enum {
    CASE_READ_BAM = 0,
    CASE_BEFORE_COUNT,
    CASE_WRITE_VERIFY,
    CASE_AFTER_COUNT,
    CASES
};

__attribute__((used)) volatile uint8_t hw_bam_alloc_pass;
__attribute__((used)) volatile uint8_t hw_bam_alloc_total;
__attribute__((used)) volatile uint8_t hw_bam_alloc_results[CASES];
__attribute__((used)) volatile uint8_t hw_bam_alloc_got[CASES];
__attribute__((used)) volatile uint8_t hw_bam_alloc_want[CASES];

static uint8_t scratch[256];

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

static void record(uint8_t idx, uint8_t ok, uint8_t got, uint8_t want) {
    hw_bam_alloc_results[idx] = ok ? 1 : 0;
    hw_bam_alloc_got[idx] = got;
    hw_bam_alloc_want[idx] = want;
    hw_bam_alloc_total++;
    if (ok) hw_bam_alloc_pass++;
}

static void m65_io_enable(void) {
    __asm__ volatile("lda #$47\n\t sta $d02f\n\t lda #$53\n\t sta $d02f\n\t" ::: "a");
}

static unsigned int f011_read_at(uint8_t T, uint8_t S) {
    uint8_t b = (uint8_t)(S >> 1);
    uint8_t half = (uint8_t)(S & 1);
    uint8_t side = (uint8_t)(b >= 10 ? 1 : 0);
    uint8_t fsec = (uint8_t)((b >= 10 ? b - 10 : b) + 1);
    unsigned int g;
    m65_io_enable();
    lisp65_f011_take_context();
    *((volatile uint8_t *)0xD081) = 0x20;
    for (g = 0; g < 20000; g++) {}
    *((volatile uint8_t *)0xD084) = (uint8_t)(T - 1);
    *((volatile uint8_t *)0xD085) = fsec;
    *((volatile uint8_t *)0xD086) = side;
    *((volatile uint8_t *)0xD081) = 0x40;
    for (g = 0; g < 60000 && (*((volatile uint8_t *)0xD082) & 0x80); g++) {}
    lisp65_f011_map_buffer();
    return (unsigned int)half << 8;
}

static void read_sector(uint8_t track, uint8_t sector) {
    unsigned int off = f011_read_at(track, sector);
    unsigned int i;
    for (i = 0; i < 256; i++)
        scratch[i] = ((volatile uint8_t *)0xDE00)[off + i];
    lisp65_f011_unmap_buffer();
}

static uint8_t write_sector(uint8_t track, uint8_t sector) {
    uint8_t b = (uint8_t)(sector >> 1);
    uint8_t side = (uint8_t)(b >= 10 ? 1 : 0);
    uint8_t fsec = (uint8_t)((b >= 10 ? b - 10 : b) + 1);
    unsigned int off, i, g;
    off = f011_read_at(track, sector);
    for (i = 0; i < 256; i++)
        ((volatile uint8_t *)0xDE00)[off + i] = scratch[i];
    lisp65_f011_unmap_buffer();
    m65_io_enable();
    lisp65_f011_take_context();
    *((volatile uint8_t *)0xD084) = (uint8_t)(track - 1);
    *((volatile uint8_t *)0xD085) = fsec;
    *((volatile uint8_t *)0xD086) = side;
    *((volatile uint8_t *)0xD081) = 0x84;
    for (g = 0; g < 60000 && (*((volatile uint8_t *)0xD082) & 0x80); g++) {}
    off = f011_read_at(track, sector);
    for (i = 0; i < 256; i++) {
        if (((volatile uint8_t *)0xDE00)[off + i] != scratch[i]) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
    }
    lisp65_f011_unmap_buffer();
    return 1;
}

static void run_m2(void) {
    uint8_t ok, before_count, after_count;
    m65_io_enable();
    read_sector(40, 2);
    record(CASE_READ_BAM, scratch[0] == 0 && scratch[1] == 255, scratch[0], 0);
    before_count = scratch[40];
    after_count = (uint8_t)(before_count - 1u);
    ok = before_count > 0 && scratch[42] == 255;
    record(CASE_BEFORE_COUNT, ok, before_count, before_count);
    if (!ok) return;
    scratch[40] = after_count;
    scratch[42] = 254;
    ok = write_sector(40, 2);
    record(CASE_WRITE_VERIFY, ok, ok, 1);
    read_sector(40, 2);
    ok = scratch[40] == after_count && scratch[42] == 254;
    record(CASE_AFTER_COUNT, ok, scratch[40], after_count);
}

static void show_result(void) {
    uint8_t pass = (hw_bam_alloc_pass == hw_bam_alloc_total);
    hw_border(pass ? COLOR_GREEN : COLOR_RED);
    puts_scr("bam alloc ");
    puts_scr(pass ? "pass " : "fail ");
    put_u8(hw_bam_alloc_pass);
    scr_putc('/');
    put_u8(hw_bam_alloc_total);
    scr_putc('\n');
    puts_scr("target T45/S8 via BAM T40/S2 bytes 40/42\n");
    puts_scr("count ");
    put_u8(hw_bam_alloc_got[CASE_BEFORE_COUNT]);
    puts_scr(" -> ");
    put_u8(hw_bam_alloc_got[CASE_AFTER_COUNT]);
    puts_scr(" bits ff -> fe\n");
}

int main(void) {
    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    hw_bam_alloc_pass = 0;
    hw_bam_alloc_total = 0;
    run_m2();
    show_result();
    for (;;) { }
    return 0;
}
