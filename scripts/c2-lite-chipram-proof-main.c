/* Standalone, receipt-less C2-lite Bank-2/3 metal proof.
 *
 * This is not a product candidate.  It establishes an owned Bank-0 window by
 * CPU stores, then tests the production F018A DMA trigger shape with Chip RAM
 * as source.  The first CPU observation after every trigger is authoritative;
 * there is no convergence retry or delayed-success path. */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"
#include "c2-lite-chipram-proof-shared.h"
#include "c2-lite-chipram-window.generated.h"
#include "c2-lite-chipram-patterns.generated.h"

#define REG8(a) (*(volatile uint8_t *)(a))

#define CIA1_ICR  REG8(0xdc0d)
#define CIA2_TALO REG8(0xdd04)
#define CIA2_TAHI REG8(0xdd05)
#define CIA2_ICR  REG8(0xdd0d)
#define CIA2_CRA  REG8(0xdd0e)
#define VIC_D011  REG8(0xd011)
#define VIC_D012  REG8(0xd012)
#define VIC_D019  REG8(0xd019)
#define VIC_D01A  REG8(0xd01a)

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

#define SOURCE_SCRATCH ((volatile uint8_t *)0x8000u)
#define RESULT_SCRATCH ((volatile uint8_t *)0x9000u)
#define SOURCE_SCRATCH_OFF 0x8000u
#define RESULT_SCRATCH_OFF 0x9000u
#define MAX_TRANSFER 1781u
#define BANK_BYTES 65536ul
#define WINDOW_BASE 0xe000u
#define WINDOW_BYTES 8192u
#define OVERLAY_TARGET 0xc356u
#define ISLAND_TARGET 0x1800u
#define NATIVE_BOOT_GENERATION 1u
#define NATIVE_SESSION_GENERATION 2u
#define TEST_CASES 12u

extern void c2lt_map_window(void);
extern void c2lt_window_dispatch_call(void);
extern void c2lt_rom_write_enable(void);

/* Same 12-byte F018A list and D700 trigger sequence as the product path. */
__attribute__((used)) uint8_t dma_job[12];

typedef struct {
    uint8_t bank;
    uint16_t source;
    uint16_t target;
    uint16_t length;
    uint8_t seed;
} transfer_case;

static const transfer_case cases[TEST_CASES] = {
    {2u, 0x00ffu, RESULT_SCRATCH_OFF, 1u,   C2LT_BANK2_SEED},
    {2u, 0x01fdu, RESULT_SCRATCH_OFF, 7u,   C2LT_BANK2_SEED},
    {2u, 0x0ff8u, RESULT_SCRATCH_OFF, 16u,  C2LT_BANK2_SEED},
    {2u, 0x7fc1u, RESULT_SCRATCH_OFF, 127u, C2LT_BANK2_SEED},
    {2u, 0xff80u, RESULT_SCRATCH_OFF, 128u, C2LT_BANK2_SEED},
    {3u, 0x00ffu, RESULT_SCRATCH_OFF, 1u,   C2LT_BANK3_SESSION_SEED},
    {3u, 0x01fdu, RESULT_SCRATCH_OFF, 7u,   C2LT_BANK3_SESSION_SEED},
    {3u, 0x0ff8u, RESULT_SCRATCH_OFF, 16u,  C2LT_BANK3_SESSION_SEED},
    {3u, 0x7fc1u, RESULT_SCRATCH_OFF, 127u, C2LT_BANK3_SESSION_SEED},
    {3u, 0xff80u, RESULT_SCRATCH_OFF, 128u, C2LT_BANK3_SESSION_SEED},
    {3u, 0x2000u, OVERLAY_TARGET, 1761u, C2LT_BANK3_SESSION_SEED},
    {3u, 0x9000u, ISLAND_TARGET, 1781u, C2LT_BANK3_SESSION_SEED},
};

static void puts_scr(const char *s) {
    while (*s) scr_putc(*s++);
}

static void put_hex4(uint8_t value) {
    value &= 15u;
    scr_putc((char)(value < 10u ? '0' + value : 'a' + value - 10u));
}

static void put_hex8(uint8_t value) {
    put_hex4((uint8_t)(value >> 4));
    put_hex4(value);
}

static void put_hex16(uint16_t value) {
    put_hex8((uint8_t)(value >> 8));
    put_hex8((uint8_t)value);
}

static uint16_t crc16_update(uint16_t crc, uint8_t value) {
    uint8_t bit;
    crc ^= (uint16_t)value << 8;
    for (bit = 0; bit < 8u; ++bit)
        crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u)
                              : (uint16_t)(crc << 1);
    return crc;
}

static uint16_t crc16_mem(volatile const uint8_t *p, uint16_t length) {
    uint16_t crc = 0xffffu;
    while (length--) crc = crc16_update(crc, *p++);
    return crc;
}

static uint8_t pattern_byte(uint8_t seed, uint16_t offset) {
    uint8_t lo = (uint8_t)offset;
    uint8_t hi = (uint8_t)(offset >> 8);
    return (uint8_t)(seed ^ lo ^ (uint8_t)(hi * 17u)
                     ^ (uint8_t)((lo << 3) | (lo >> 5)));
}

static uint16_t frame_count(void) {
    uint8_t high_a, low, high_b;
    do {
        high_a = REG8(C2LT_FRAME_HI);
        low = REG8(C2LT_FRAME_LO);
        high_b = REG8(C2LT_FRAME_HI);
    } while (high_a != high_b);
    return (uint16_t)low | ((uint16_t)high_a << 8);
}

static uint32_t raster_stamp(void) {
    uint16_t frame = frame_count();
    uint16_t line = (uint16_t)VIC_D012
                  | (uint16_t)((VIC_D011 & 0x80u) << 1);
    return ((uint32_t)frame << 9) | line;
}

static void stop_fail(uint8_t code, uint8_t which) {
    __asm__ volatile("sei" ::: "memory");
    VIC_D01A = 0u;
    REG8(C2LT_FAIL_CODE) = code;
    REG8(C2LT_FAIL_CASE) = which;
    hw_border(COLOR_RED);
    scr_clear();
    puts_scr("C2-LITE B2/B3 CHIP-RAM PROOF\n\nFAIL - FIRST RED ");
    put_hex8(code);
    puts_scr(" CASE "); put_hex8(which);
    puts_scr("\nB2 ");
    put_hex16((uint16_t)REG8(C2LT_BANK2_CRC_LO)
              | ((uint16_t)REG8(C2LT_BANK2_CRC_HI) << 8));
    puts_scr(" B3 ");
    put_hex16((uint16_t)REG8(C2LT_BANK3_SESSION_CRC_LO)
              | ((uint16_t)REG8(C2LT_BANK3_SESSION_CRC_HI) << 8));
    puts_scr("\nNON-PRODUCT / NO RETRY\nDISK REBOOT REQUIRED\n");
    for (;;) { }
}

__attribute__((noinline))
static void dma_copy(uint16_t source, uint8_t source_bank,
                     uint16_t target, uint8_t target_bank,
                     uint16_t length) {
    dma_job[0] = 0u;
    dma_job[1] = (uint8_t)length;
    dma_job[2] = (uint8_t)(length >> 8);
    dma_job[3] = (uint8_t)source;
    dma_job[4] = (uint8_t)(source >> 8);
    dma_job[5] = source_bank;
    dma_job[6] = (uint8_t)target;
    dma_job[7] = (uint8_t)(target >> 8);
    dma_job[8] = target_bank;
    dma_job[9] = 0u;
    dma_job[10] = 0u;
    dma_job[11] = 0u;
    __asm__ volatile(
        "stz $d702\n\t"
        "lda #mos16hi(dma_job)\n\tsta $d701\n\t"
        "lda #mos16lo(dma_job)\n\tsta $d700\n\t"
        ::: "a", "memory");
}

static void install_owned_window(void) {
    uint16_t i;
    volatile uint8_t *window = (volatile uint8_t *)WINDOW_BASE;

    __asm__ volatile("sei\n\tldz #0" ::: "memory");
    REG8(C2LT_STATE) = C2LT_STATE_INSTALLING;
    c2lt_map_window();

    /* Vectors publish last.  Until then interrupts stay masked and the old
     * vectors are not claimed as valid product-owned state. */
    for (i = 0; i < 0x1ffau; ++i) window[i] = 0u;
    for (i = 0; i < C2LT_WINDOW_PREFIX_BYTES; ++i)
        window[i] = c2lt_window_prefix[i];
    for (i = 0; i < 6u; ++i)
        window[0x1ffau + i] = c2lt_window_vectors[i];
    if (crc16_mem(window, WINDOW_BYTES) != C2LT_WINDOW_CRC16)
        stop_fail(0x10u, 0xffu);
    REG8(C2LT_WINDOW_CRC_LO) = (uint8_t)C2LT_WINDOW_CRC16;
    REG8(C2LT_WINDOW_CRC_HI) = (uint8_t)(C2LT_WINDOW_CRC16 >> 8);

    CIA1_ICR = 0x7fu; (void)CIA1_ICR;
    CIA2_CRA = 0u;
    CIA2_ICR = 0x7fu; (void)CIA2_ICR;
    VIC_D01A = 0u;
    VIC_D019 = 0xffu;
    REG8(C2LT_FRAME_LO) = 0u;
    REG8(C2LT_FRAME_HI) = 0u;
    REG8(C2LT_NMI_COUNT) = 0u;
    REG8(C2LT_UNEXPECTED_IRQ) = 0u;
    REG8(C2LT_UNOWNED_VIC_FLAGS) = 0u;
    REG8(C2LT_DEQUEUE_COUNT) = 0u;
    REG8(C2LT_STATE) = C2LT_STATE_OWNED;
    VIC_D012 = 0xffu;
    VIC_D011 &= 0x7fu;
    VIC_D019 = 0xffu;
    VIC_D01A = 0x01u;
    __asm__ volatile("cli" ::: "memory");
}

static void wait_frames(uint16_t count, uint8_t fail_code) {
    uint16_t start = frame_count();
    uint32_t fuel = 0x01fffffful;
    while ((uint16_t)(frame_count() - start) < count && fuel) --fuel;
    if (!fuel) stop_fail(fail_code, 0xffu);
}

static void prove_owned_nmi(void) {
    uint8_t before = REG8(C2LT_NMI_COUNT);
    CIA2_CRA = 0u;
    CIA2_ICR = 0x7fu; (void)CIA2_ICR;
    CIA2_TALO = 0x00u;
    CIA2_TAHI = 0x08u;
    CIA2_ICR = 0x81u;
    CIA2_CRA = 0x19u;
    while (REG8(C2LT_NMI_COUNT) == before) { }
    CIA2_CRA = 0u;
    CIA2_ICR = 0x7fu; (void)CIA2_ICR;
}

static uint8_t poll_event(void) {
    REG8(C2LT_COMMAND) = C2LT_CMD_POLL_EVENT;
    REG8(C2LT_RESPONSE) = 0u;
    c2lt_window_dispatch_call();
    return REG8(C2LT_RESPONSE);
}

static void wait_f(void) {
    uint32_t fuel = 0x1ffffffful;
    while (fuel) {
        if (poll_event()) {
            if (REG8(C2LT_EVENT_CODE) == 0x46u) return;
        }
        --fuel;
    }
    stop_fail(0x61u, 0xffu);
}

static void fill_source(uint8_t seed, uint16_t offset, uint16_t length) {
    uint16_t i;
    for (i = 0; i < length; ++i)
        SOURCE_SCRATCH[i] = pattern_byte(seed, (uint16_t)(offset + i));
}

static void poison(volatile uint8_t *target, uint16_t length) {
    while (length--) *target++ = 0xa5u;
}

static uint8_t matches(volatile const uint8_t *target, uint8_t seed,
                       uint16_t offset, uint16_t length) {
    uint16_t i;
    for (i = 0; i < length; ++i)
        if (target[i] != pattern_byte(seed, (uint16_t)(offset + i))) return 0u;
    return 1u;
}

static uint16_t stage_full_bank(uint8_t bank, uint8_t seed, uint8_t fail_code) {
    uint32_t offset = 0u;
    uint16_t crc = 0xffffu;
    while (offset < BANK_BYTES) {
        uint16_t i;
        uint16_t length = (uint16_t)((BANK_BYTES - offset) > MAX_TRANSFER
                                    ? MAX_TRANSFER : (BANK_BYTES - offset));
        fill_source(seed, (uint16_t)offset, length);
        dma_copy(SOURCE_SCRATCH_OFF, 0u, (uint16_t)offset, bank, length);
        poison(RESULT_SCRATCH, length);
        dma_copy((uint16_t)offset, bank, RESULT_SCRATCH_OFF, 0u, length);
        if (!matches(RESULT_SCRATCH, seed, (uint16_t)offset, length))
            stop_fail(fail_code, (uint8_t)(offset >> 11));
        for (i = 0; i < length; ++i) crc = crc16_update(crc, RESULT_SCRATCH[i]);
        offset += length;
    }
    return crc;
}

static uint16_t verify_full_bank(uint8_t bank, uint8_t seed, uint8_t fail_code) {
    uint32_t offset = 0u;
    uint16_t crc = 0xffffu;
    while (offset < BANK_BYTES) {
        uint16_t i;
        uint16_t length = (uint16_t)((BANK_BYTES - offset) > MAX_TRANSFER
                                    ? MAX_TRANSFER : (BANK_BYTES - offset));
        poison(RESULT_SCRATCH, length);
        dma_copy((uint16_t)offset, bank, RESULT_SCRATCH_OFF, 0u, length);
        if (!matches(RESULT_SCRATCH, seed, (uint16_t)offset, length))
            stop_fail(fail_code, (uint8_t)(offset >> 11));
        for (i = 0; i < length; ++i) crc = crc16_update(crc, RESULT_SCRATCH[i]);
        offset += length;
    }
    return crc;
}

static uint8_t native_handle_valid(uint8_t generation, uint8_t family) {
    return REG8(C2LT_NATIVE_GENERATION) == generation
        && REG8(C2LT_NATIVE_FAMILY) == family;
}

static void run_case(uint8_t index) {
    const transfer_case *row = &cases[index];
    volatile uint8_t *target = (volatile uint8_t *)row->target;
    uint32_t before, after, delta;
    poison(target, row->length);
    before = raster_stamp();
    dma_copy(row->source, row->bank, row->target, 0u, row->length);
    after = raster_stamp();
    /* This is the one authoritative observation.  There is deliberately no
     * retry, second DMA or delayed comparison after this branch. */
    if (!matches(target, row->seed, row->source, row->length))
        stop_fail(0x50u, index);
    delta = after - before;
    REG8((uint16_t)(C2LT_LATENCY_BASE + index)) =
        (uint8_t)(delta > 255u ? 255u : delta);
    REG8(C2LT_CASE_COUNT_DONE) = (uint8_t)(index + 1u);
}

static void prove_post_freezer_write(uint8_t bank, uint8_t seed, uint8_t code) {
    uint8_t replacement = (uint8_t)(pattern_byte(seed, 0xff00u) ^ 0xffu);
    SOURCE_SCRATCH[0] = replacement;
    dma_copy(SOURCE_SCRATCH_OFF, 0u, 0xff00u, bank, 1u);
    RESULT_SCRATCH[0] = 0xa5u;
    dma_copy(0xff00u, bank, RESULT_SCRATCH_OFF, 0u, 1u);
    if (RESULT_SCRATCH[0] != replacement) stop_fail(code, bank);
    SOURCE_SCRATCH[0] = pattern_byte(seed, 0xff00u);
    dma_copy(SOURCE_SCRATCH_OFF, 0u, 0xff00u, bank, 1u);
    RESULT_SCRATCH[0] = 0xa5u;
    dma_copy(0xff00u, bank, RESULT_SCRATCH_OFF, 0u, 1u);
    if (RESULT_SCRATCH[0] != SOURCE_SCRATCH[0]) stop_fail(code, bank);
}

int main(void) {
    uint8_t i;
    uint16_t crc;
    uint16_t freezer_frame;

    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    puts_scr("C2-LITE B2/B3 CHIP-RAM PROOF\nNON-PRODUCT / FIRST-RED\n\n");

    install_owned_window();
    wait_frames(2u, 0x11u);
    prove_owned_nmi();
    puts_scr("OWNED IRQ/NMI + WINDOW OK\n");

    /* Re-establish the MEGA65 I/O personality before the idempotent HYPPO
     * memory trap, then remove write protection from both ROM backing banks. */
    REG8(0xd02f) = 0x47u;
    REG8(0xd02f) = 0x53u;
    c2lt_rom_write_enable();

    crc = stage_full_bank(2u, C2LT_BANK2_SEED, 0x20u);
    REG8(C2LT_BANK2_CRC_LO) = (uint8_t)crc;
    REG8(C2LT_BANK2_CRC_HI) = (uint8_t)(crc >> 8);
    if (crc != C2LT_BANK2_CRC16) stop_fail(0x21u, 2u);
    puts_scr("BANK 2 FULL IMAGE OK\n");

    crc = stage_full_bank(3u, C2LT_BANK3_BOOT_SEED, 0x30u);
    REG8(C2LT_BANK3_BOOT_CRC_LO) = (uint8_t)crc;
    REG8(C2LT_BANK3_BOOT_CRC_HI) = (uint8_t)(crc >> 8);
    if (crc != C2LT_BANK3_BOOT_CRC16) stop_fail(0x31u, 3u);
    REG8(C2LT_NATIVE_GENERATION) = NATIVE_BOOT_GENERATION;
    REG8(C2LT_NATIVE_FAMILY) = C2LT_FAMILY_BOOT;
    if (!native_handle_valid(NATIVE_BOOT_GENERATION, C2LT_FAMILY_BOOT))
        stop_fail(0x32u, 3u);

    /* Invalidate before replacement, then publish Session last. */
    REG8(C2LT_NATIVE_FAMILY) = C2LT_FAMILY_INVALID;
    REG8(C2LT_NATIVE_GENERATION) = NATIVE_SESSION_GENERATION;
    if (native_handle_valid(NATIVE_BOOT_GENERATION, C2LT_FAMILY_BOOT))
        stop_fail(0x33u, 3u);
    crc = stage_full_bank(3u, C2LT_BANK3_SESSION_SEED, 0x40u);
    REG8(C2LT_BANK3_SESSION_CRC_LO) = (uint8_t)crc;
    REG8(C2LT_BANK3_SESSION_CRC_HI) = (uint8_t)(crc >> 8);
    if (crc != C2LT_BANK3_SESSION_CRC16) stop_fail(0x41u, 3u);
    REG8(C2LT_NATIVE_FAMILY) = C2LT_FAMILY_SESSION;
    if (native_handle_valid(NATIVE_BOOT_GENERATION, C2LT_FAMILY_BOOT)
        || !native_handle_valid(NATIVE_SESSION_GENERATION, C2LT_FAMILY_SESSION))
        stop_fail(0x42u, 3u);
    puts_scr("BANK 3 BOOT->SESSION OK\n");

    for (i = 0; i < TEST_CASES; ++i) run_case(i);
    puts_scr("IMMEDIATE DMA 12/12 OK\n");

    freezer_frame = frame_count();
    puts_scr("\nOPEN FREEZER, THEN EXIT\nAFTER RETURN PRESS F\n");
    wait_f();
    REG8(C2LT_FREEZER_RETURNED) = 1u;
    if (REG8(C2LT_STATE) != C2LT_STATE_OWNED
        || REG8(C2LT_NATIVE_GENERATION) != NATIVE_SESSION_GENERATION
        || REG8(C2LT_NATIVE_FAMILY) != C2LT_FAMILY_SESSION)
        stop_fail(0x62u, 0xffu);
    if (crc16_mem((volatile const uint8_t *)WINDOW_BASE, WINDOW_BYTES)
        != C2LT_WINDOW_CRC16) stop_fail(0x63u, 0xffu);
    if (verify_full_bank(2u, C2LT_BANK2_SEED, 0x64u) != C2LT_BANK2_CRC16)
        stop_fail(0x65u, 2u);
    if (verify_full_bank(3u, C2LT_BANK3_SESSION_SEED, 0x66u)
        != C2LT_BANK3_SESSION_CRC16) stop_fail(0x67u, 3u);
    REG8(C2LT_FREEZER_BANKS_OK) = 2u;

    REG8(0xd02f) = 0x47u;
    REG8(0xd02f) = 0x53u;
    c2lt_rom_write_enable();
    prove_post_freezer_write(2u, C2LT_BANK2_SEED, 0x68u);
    prove_post_freezer_write(3u, C2LT_BANK3_SESSION_SEED, 0x69u);
    REG8(C2LT_WRITEBACK_OK) = 2u;
    wait_frames(2u, 0x6au);
    if (frame_count() == freezer_frame || REG8(C2LT_UNEXPECTED_IRQ) > 1u)
        stop_fail(0x6bu, 0xffu);

    REG8(C2LT_STATE) = C2LT_STATE_PASS;
    hw_border(COLOR_GREEN);
    scr_clear();
    puts_scr("C2-LITE B2/B3 CHIP-RAM PROOF\n\nPASS - RECEIPT-LESS PREFILTER\n");
    puts_scr("BANK2 + BANK3 FULL CRC YES\n");
    puts_scr("IMMEDIATE DMA 12/12 YES\n");
    puts_scr("BOOT->SESSION + STALE REJECT YES\n");
    puts_scr("OWNED IRQ/NMI + FREEZER YES\n");
    puts_scr("POST-FREEZER WRITE 2/2 YES\n");
    puts_scr("CORE ID CAPTURED HOST-SIDE\n\nNO PRODUCT CLAIM\n");
    for (;;) { }
    return 0;
}
