/* lisp65 -- MEGA65 HW-access smoke/probe.
 *
 * Required checks go red on failure. Exploratory flat 28-bit probes are recorded
 * but do not fail the smoke, because their stability is exactly what this gate
 * is meant to measure on real hardware.
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

enum {
    HW_ACCESS_LEGACY_DMA = 0,
    HW_ACCESS_EDMA_COPY,
    HW_ACCESS_EDMA_FILL,
    HW_ACCESS_EDMA_ATTIC,
    HW_ACCESS_FLAT_BANK0,
    HW_ACCESS_Q_REG,
    HW_ACCESS_MATH_MUL,
    HW_ACCESS_MATH_DIV,
    HW_ACCESS_FLAT_BANK4_OBS,
    HW_ACCESS_CASES
};

__attribute__((used)) volatile uint8_t hw_access_pass;
__attribute__((used)) volatile uint8_t hw_access_total;
__attribute__((used)) volatile uint8_t hw_access_results[HW_ACCESS_CASES];
__attribute__((used)) volatile uint16_t hw_access_got[HW_ACCESS_CASES];
__attribute__((used)) volatile uint16_t hw_access_want[HW_ACCESS_CASES];

static uint8_t src_buf[32];
static uint8_t dst_buf[32];
static uint8_t attic_back[8];
static uint8_t flat_bank4_back;

__attribute__((section(".zp.bss"), used)) static volatile uint8_t hw_q_store[4];
__attribute__((section(".zp.bss"), used)) static volatile uint8_t hw_q_add[4];
__attribute__((section(".zp.bss"), used)) static volatile uint8_t hw_q_sum[4];

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

static void clear_buf(uint8_t *p, uint8_t n) {
    uint8_t i;
    for (i = 0; i < n; i++) p[i] = 0;
}

static uint8_t eq_buf(const uint8_t *a, const uint8_t *b, uint8_t n) {
    uint8_t i;
    for (i = 0; i < n; i++) if (a[i] != b[i]) return 0;
    return 1;
}

static void record(uint8_t idx, uint8_t ok, uint16_t got, uint16_t want,
                   uint8_t required) {
    hw_access_results[idx] = ok ? 1 : 0;
    hw_access_got[idx] = got;
    hw_access_want[idx] = want;
    if (required) {
        hw_access_total++;
        if (ok) hw_access_pass++;
    }
}

static void q_probe(void) {
    hw_q_add[0] = 1;
    hw_q_add[1] = 0;
    hw_q_add[2] = 0;
    hw_q_add[3] = 0;
    __asm__ volatile(
        "lda #$78\n\t"
        "ldx #$56\n\t"
        "ldy #$34\n\t"
        "ldz #$12\n\t"
        "stq hw_q_store\n\t"
        "ldq hw_q_store\n\t"
        "clc\n\t"
        "adcq hw_q_add\n\t"
        "stq hw_q_sum\n\t"
        /* llvm-mos assumes Z is zero for later generated stores. */
        "ldz #0\n\t"
        ::: "a", "x", "y", "memory");
}

static void math_set32(uint16_t addr, uint32_t value) {
    volatile uint8_t *p = (volatile uint8_t *)(uintptr_t)addr;
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
    p[3] = (uint8_t)(value >> 24);
}

static uint32_t math_get32(uint16_t addr) {
    volatile uint8_t *p = (volatile uint8_t *)(uintptr_t)addr;
    return (uint32_t)p[0] |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void math_wait_div(void) {
    __asm__ volatile(
        "1:\n\t"
        "bit $d70f\n\t"
        "bmi 1b\n\t"
        ::: "memory");
}

static void math_settle(void) {
    uint8_t i;
    for (i = 0; i < 32; i++) {
        __asm__ volatile("nop" ::: "memory");
    }
}

static void run_required(void) {
    uint8_t i, ok;
    uint16_t got;

    for (i = 0; i < sizeof(src_buf); i++) src_buf[i] = (uint8_t)(0x30u + i);

    clear_buf(dst_buf, sizeof(dst_buf));
    hw_dma_legacy_copy((uint32_t)(uintptr_t)src_buf, 0x00042000ul, 16);
    hw_dma_legacy_copy(0x00042000ul, (uint32_t)(uintptr_t)dst_buf, 16);
    record(HW_ACCESS_LEGACY_DMA, eq_buf(src_buf, dst_buf, 16), dst_buf[15], src_buf[15], 1);

    clear_buf(dst_buf, sizeof(dst_buf));
    hw_edma_copy((uint32_t)(uintptr_t)src_buf, 0x00042100ul, 16);
    hw_dma_legacy_copy(0x00042100ul, (uint32_t)(uintptr_t)dst_buf, 16);
    record(HW_ACCESS_EDMA_COPY, eq_buf(src_buf, dst_buf, 16), dst_buf[15], src_buf[15], 1);

    clear_buf(dst_buf, sizeof(dst_buf));
    hw_edma_fill(0x00042200ul, 0x5a, 16);
    hw_dma_legacy_copy(0x00042200ul, (uint32_t)(uintptr_t)dst_buf, 16);
    ok = 1;
    for (i = 0; i < 16; i++) if (dst_buf[i] != 0x5a) ok = 0;
    record(HW_ACCESS_EDMA_FILL, ok, dst_buf[15], 0x5a, 1);

    clear_buf(attic_back, sizeof(attic_back));
    hw_edma_fill(HW_M65_ATTIC_RAM + 0x1200ul, 0xa6, 8);
    hw_edma_copy(HW_M65_ATTIC_RAM + 0x1200ul, (uint32_t)(uintptr_t)attic_back, 8);
    ok = 1;
    for (i = 0; i < 8; i++) if (attic_back[i] != 0xa6) ok = 0;
    record(HW_ACCESS_EDMA_ATTIC, ok, attic_back[7], 0xa6, 1);

    hw_flat_write8(0x0000fffau, 0x6a);
    got = hw_flat_read8(0x0000fffau);
    record(HW_ACCESS_FLAT_BANK0, got == 0x6a, got, 0x6a, 1);

    q_probe();
    got = (uint16_t)hw_q_sum[0] | ((uint16_t)hw_q_sum[1] << 8);
    record(HW_ACCESS_Q_REG,
           hw_q_store[0] == 0x78 && hw_q_store[1] == 0x56 &&
           hw_q_store[2] == 0x34 && hw_q_store[3] == 0x12 &&
           hw_q_sum[0] == 0x79 && hw_q_sum[1] == 0x56 &&
           hw_q_sum[2] == 0x34 && hw_q_sum[3] == 0x12,
           got, 0x5679, 1);

    math_set32(0xd770u, 1234ul);
    math_set32(0xd774u, 37ul);
    math_settle();
    got = (uint16_t)math_get32(0xd778u);
    record(HW_ACCESS_MATH_MUL, math_get32(0xd778u) == 45658ul, got, 45658u, 1);

    math_set32(0xd770u, 144ul);
    math_set32(0xd774u, 12ul);
    math_wait_div();
    got = (uint16_t)math_get32(0xd76cu);
    record(HW_ACCESS_MATH_DIV, math_get32(0xd76cu) == 12ul, got, 12u, 1);
}

static void run_observed(void) {
    hw_flat_write8(0x0004c800ul, 0x7b);
    flat_bank4_back = 0;
    hw_dma_legacy_copy(0x0004c800ul, (uint32_t)(uintptr_t)&flat_bank4_back, 1);
    record(HW_ACCESS_FLAT_BANK4_OBS, flat_bank4_back == 0x7b, flat_bank4_back, 0x7b, 0);
}

static void show_result(void) {
    uint8_t pass = (hw_access_pass == hw_access_total);
    hw_border(pass ? COLOR_GREEN : COLOR_RED);
    puts_scr("hw access ");
    puts_scr(pass ? "pass " : "fail ");
    put_u8(hw_access_pass);
    scr_putc('/');
    put_u8(hw_access_total);
    puts_scr(" flat4 ");
    puts_scr(hw_access_results[HW_ACCESS_FLAT_BANK4_OBS] ? "yes" : "no");
    scr_putc('\n');
    puts_scr("legacy edma copy fill attic flat0 q math\n");
}

int main(void) {
    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    hw_access_pass = 0;
    hw_access_total = 0;
    run_required();
    run_observed();
    show_result();
    for (;;) { }
    return 0;
}
