/* lisp65 -- M4 throwaway-D81 directory-entry write smoke.
 *
 * Writes a source chain to the shared R5 fixture sectors, allocates both in the BAM,
 * then writes directory entry #2 in T40/S4 for "M4SRC". The shell harness
 * verifies the downloaded D81 byte-for-byte and boots the Workbench to call
 * normal (load "m4src").
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"
#include "m4-dir-source.h"
#include "f011_context.h"

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

#ifndef R5_FIXED_TRACK
#error R5_FIXED_TRACK must come from the R5 persistence-fixture contract
#endif
#ifndef R5_FIXED_FIRST
#error R5_FIXED_FIRST must come from the R5 persistence-fixture contract
#endif
#ifndef R5_FIXED_SECOND
#error R5_FIXED_SECOND must come from the R5 persistence-fixture contract
#endif

#define DATA_TRACK ((uint8_t)R5_FIXED_TRACK)
#define DATA_FIRST ((uint8_t)R5_FIXED_FIRST)
#define DATA_SECOND ((uint8_t)R5_FIXED_SECOND)
#define BAM_ENTRY ((uint8_t)(16u + 6u * (DATA_TRACK - 41u)))
#define BAM_COUNT BAM_ENTRY
#define BAM_BITMAP ((uint8_t)(BAM_ENTRY + 1u + DATA_FIRST / 8u))
#define BAM_FIRST_MASK ((uint8_t)(1u << (DATA_FIRST & 7u)))
#define BAM_SECOND_MASK ((uint8_t)(1u << (DATA_SECOND & 7u)))
#define BAM_MASK ((uint8_t)(BAM_FIRST_MASK | BAM_SECOND_MASK))
#define DIR_TRACK 40u
#define DIR_SECTOR 4u
#define DIR_ENTRY_BASE 64u

enum {
    CASE_READ_BAM = 0,
    CASE_BEFORE_BAM,
    CASE_PAYLOAD_LEN,
    CASE_WRITE_FIRST,
    CASE_WRITE_SECOND,
    CASE_WRITE_BAM,
    CASE_AFTER_BAM,
    CASE_READ_DIR,
    CASE_BEFORE_DIR,
    CASE_WRITE_DIR,
    CASE_AFTER_DIR,
    CASES
};

__attribute__((used)) volatile uint8_t hw_dir_write_pass;
__attribute__((used)) volatile uint8_t hw_dir_write_total;
__attribute__((used)) volatile uint8_t hw_dir_write_results[CASES];
__attribute__((used)) volatile uint16_t hw_dir_write_got[CASES];
__attribute__((used)) volatile uint16_t hw_dir_write_want[CASES];

static uint8_t scratch[256];

static void puts_scr(const char *s) {
    while (*s) scr_putc(*s++);
}

static void put_u16(uint16_t n) {
    uint16_t div = 10000;
    uint8_t started = 0;
    while (div > 1) {
        uint8_t d = (uint8_t)(n / div);
        if (d || started) {
            scr_putc((char)('0' + d));
            started = 1;
        }
        n = (uint16_t)(n % div);
        div = (uint16_t)(div / 10);
    }
    scr_putc((char)('0' + n));
}

static void record(uint8_t idx, uint8_t ok, uint16_t got, uint16_t want) {
    hw_dir_write_results[idx] = ok ? 1 : 0;
    hw_dir_write_got[idx] = got;
    hw_dir_write_want[idx] = want;
    hw_dir_write_total++;
    if (ok) hw_dir_write_pass++;
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

static uint16_t payload_len(void) {
    uint16_t n = 0;
    while (m4_dir_src[n]) n++;
    return n;
}

static void clear_scratch(void) {
    unsigned int i;
    for (i = 0; i < 256; i++) scratch[i] = 0;
}

static void fill_first_sector(void) {
    unsigned int i;
    clear_scratch();
    scratch[0] = DATA_TRACK;
    scratch[1] = DATA_SECOND;
    for (i = 0; i < 254; i++)
        scratch[2 + i] = (uint8_t)m4_dir_src[i];
}

static void fill_second_sector(uint16_t len) {
    unsigned int i;
    uint16_t tail = (uint16_t)(len - 254u);
    clear_scratch();
    scratch[0] = 0;
    scratch[1] = (uint8_t)(tail + 1u);
    for (i = 0; i < tail; i++)
        scratch[2 + i] = (uint8_t)m4_dir_src[254u + i];
}

static void fill_dir_entry(void) {
    uint8_t i;
    static const uint8_t name[16] = {
        'M','4','S','R','C',0xA0,0xA0,0xA0,
        0xA0,0xA0,0xA0,0xA0,0xA0,0xA0,0xA0,0xA0
    };
    for (i = 0; i < 32; i++) scratch[DIR_ENTRY_BASE + i] = 0;
    scratch[DIR_ENTRY_BASE + 2] = 0x81;
    scratch[DIR_ENTRY_BASE + 3] = DATA_TRACK;
    scratch[DIR_ENTRY_BASE + 4] = DATA_FIRST;
    for (i = 0; i < 16; i++) scratch[DIR_ENTRY_BASE + 5u + i] = name[i];
    scratch[DIR_ENTRY_BASE + 30] = 2;
    scratch[DIR_ENTRY_BASE + 31] = 0;
}

static uint8_t dir_entry_matches(void) {
    return scratch[DIR_ENTRY_BASE + 2] == 0x81 &&
           scratch[DIR_ENTRY_BASE + 3] == DATA_TRACK &&
           scratch[DIR_ENTRY_BASE + 4] == DATA_FIRST &&
           scratch[DIR_ENTRY_BASE + 5] == 'M' &&
           scratch[DIR_ENTRY_BASE + 6] == '4' &&
           scratch[DIR_ENTRY_BASE + 7] == 'S' &&
           scratch[DIR_ENTRY_BASE + 8] == 'R' &&
           scratch[DIR_ENTRY_BASE + 9] == 'C' &&
           scratch[DIR_ENTRY_BASE + 30] == 2 &&
           scratch[DIR_ENTRY_BASE + 31] == 0;
}

static void run_m4(void) {
    uint16_t len;
    uint8_t ok, before_count, after_count, before_bitmap, after_bitmap;
    m65_io_enable();

    len = payload_len();
    read_sector(40, 2);
    record(CASE_READ_BAM, scratch[0] == 0 && scratch[1] == 255, scratch[0], 0);
    before_count = scratch[BAM_COUNT];
    before_bitmap = scratch[BAM_BITMAP];
    after_count = (uint8_t)(before_count - 2u);
    after_bitmap = (uint8_t)(before_bitmap & (uint8_t)~BAM_MASK);
    ok = before_count >= 2 && (before_bitmap & BAM_MASK) == BAM_MASK;
    record(CASE_BEFORE_BAM, ok, ((uint16_t)before_count << 8) | before_bitmap,
           ((uint16_t)before_count << 8) | before_bitmap);
    if (!ok) return;
    ok = len > 254 && len <= 508;
    record(CASE_PAYLOAD_LEN, ok, len, 255);
    if (!ok) return;

    fill_first_sector();
    ok = write_sector(DATA_TRACK, DATA_FIRST);
    record(CASE_WRITE_FIRST, ok, ok, 1);

    fill_second_sector(len);
    ok = write_sector(DATA_TRACK, DATA_SECOND);
    record(CASE_WRITE_SECOND, ok, ok, 1);

    read_sector(40, 2);
    scratch[BAM_COUNT] = after_count;
    scratch[BAM_BITMAP] = after_bitmap;
    ok = write_sector(40, 2);
    record(CASE_WRITE_BAM, ok, ok, 1);

    read_sector(40, 2);
    ok = scratch[BAM_COUNT] == after_count && scratch[BAM_BITMAP] == after_bitmap;
    record(CASE_AFTER_BAM, ok, ((uint16_t)scratch[BAM_COUNT] << 8) | scratch[BAM_BITMAP],
           ((uint16_t)after_count << 8) | after_bitmap);

    read_sector(DIR_TRACK, DIR_SECTOR);
    record(CASE_READ_DIR, scratch[0] == 0 && scratch[1] == 255, scratch[0], 0);
    ok = scratch[DIR_ENTRY_BASE + 2] == 0;
    record(CASE_BEFORE_DIR, ok, scratch[DIR_ENTRY_BASE + 2], 0);

    fill_dir_entry();
    ok = write_sector(DIR_TRACK, DIR_SECTOR);
    record(CASE_WRITE_DIR, ok, ok, 1);

    read_sector(DIR_TRACK, DIR_SECTOR);
    ok = dir_entry_matches();
    record(CASE_AFTER_DIR, ok, scratch[DIR_ENTRY_BASE + 2], 0x81);
}

static void show_result(void) {
    uint8_t pass = (hw_dir_write_pass == hw_dir_write_total);
    hw_border(pass ? COLOR_GREEN : COLOR_RED);
    puts_scr("dir write ");
    puts_scr(pass ? "pass " : "fail ");
    put_u16(hw_dir_write_pass);
    scr_putc('/');
    put_u16(hw_dir_write_total);
    scr_putc('\n');
    puts_scr("name M4SRC T");
    put_u16(DATA_TRACK);
    puts_scr("/S");
    put_u16(DATA_FIRST);
    puts_scr(" -> S");
    put_u16(DATA_SECOND);
    scr_putc('\n');
    puts_scr("payload bytes ");
    put_u16(payload_len());
    scr_putc('\n');
    puts_scr("dir T40/S4 entry 2 last\n");
}

int main(void) {
    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    hw_dir_write_pass = 0;
    hw_dir_write_total = 0;
    run_m4();
    show_result();
    for (;;) { }
    return 0;
}
