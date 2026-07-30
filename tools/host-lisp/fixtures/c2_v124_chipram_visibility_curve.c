/* v1.2.4 non-promotable Chip-RAM append-visibility measurement.
 *
 * The only Bank-5 write is the unpublished C2D append-scratch span
 * $8430..$852f.  The hardware driver establishes C2J=CLEAR before entry.
 * This diagnostic uses the product's 12-byte F018B / $D700 descriptor shape,
 * captures four device-timed 256-byte readbacks, then executes twenty
 * immediate write/read cycles.  It never becomes product code.
 */
#include <stdint.h>

#define REG8(address) (*(volatile uint8_t *)(address))

#define DMA_MODE REG8(0xd703u)
#define DMA_LIST_BANK REG8(0xd702u)
#define DMA_LIST_HIGH REG8(0xd701u)
#define DMA_TRIGGER REG8(0xd700u)
#define VIC_D011 REG8(0xd011u)
#define VIC_D012 REG8(0xd012u)
#define VIC_BORDER REG8(0xd020u)

#define PROBE_MAILBOX ((volatile uint8_t *)0x7000u)
#define PROBE_TARGET 0x8430u
#define PROBE_BANK 5u
#define PROBE_BYTES 256u
#define PROBE_REPETITIONS 20u
#define PROBE_CURVE_SEED 0x6du
#define PROBE_STATE_RUNNING 0x31u
#define PROBE_STATE_COMPLETE 0xa5u

/* Approximate PAL raster-line offsets for 2 ms, 100 ms and 714 ms. */
#define PROBE_DELAY_2MS_LINES 31u
#define PROBE_DELAY_100MS_AFTER_2MS_LINES 1532u
#define PROBE_DELAY_714MS_AFTER_100MS_LINES 9593u

__attribute__((used)) uint8_t c2_dma_list[12];
__attribute__((used)) uint8_t probe_source[PROBE_BYTES];
__attribute__((used)) uint8_t probe_readback[PROBE_BYTES];
__attribute__((used)) uint8_t probe_curve[4][PROBE_BYTES];

static uint8_t pattern_byte(uint8_t seed, uint8_t offset) {
    return (uint8_t)(
        seed ^ offset ^ (uint8_t)((offset << 3) | (offset >> 5)));
}

static void fill_pattern(uint8_t seed) {
    uint16_t offset;
    for (offset = 0u; offset < PROBE_BYTES; ++offset)
        probe_source[offset] = pattern_byte(seed, (uint8_t)offset);
}

static void poison_readback(void) {
    uint16_t offset;
    for (offset = 0u; offset < PROBE_BYTES; ++offset)
        probe_readback[offset] = (uint8_t)~probe_source[offset];
}

/* Keep this descriptor and trigger sequence structurally identical to
 * c2_facade_target_c2_dma in src/c2_platform_dma.c. */
__attribute__((noinline))
static void product_dma_copy(
        uint16_t source, uint8_t source_bank,
        uint16_t target, uint8_t target_bank, uint16_t length) {
    c2_dma_list[0] = 0u;
    c2_dma_list[1] = (uint8_t)length;
    c2_dma_list[2] = (uint8_t)(length >> 8);
    c2_dma_list[3] = (uint8_t)source;
    c2_dma_list[4] = (uint8_t)(source >> 8);
    c2_dma_list[5] = source_bank;
    c2_dma_list[6] = (uint8_t)target;
    c2_dma_list[7] = (uint8_t)(target >> 8);
    c2_dma_list[8] = target_bank;
    c2_dma_list[9] = 0u;
    c2_dma_list[10] = 0u;
    c2_dma_list[11] = 0u;
    __asm__ volatile(
        "lda #0\n\tsta $d702\n\t"
        "lda #mos16hi(c2_dma_list)\n\tsta $d701\n\t"
        "lda #mos16lo(c2_dma_list)\n\tsta $d700\n\t"
        ::: "a", "memory");
}

static uint16_t crc16(const uint8_t *bytes) {
    uint16_t value = 0xffffu;
    uint16_t offset;
    for (offset = 0u; offset < PROBE_BYTES; ++offset) {
        uint8_t bit;
        value ^= (uint16_t)bytes[offset] << 8;
        for (bit = 0u; bit < 8u; ++bit)
            value = (value & 0x8000u)
                ? (uint16_t)((value << 1) ^ 0x1021u)
                : (uint16_t)(value << 1);
    }
    return value;
}

static uint16_t raster_line(void) {
    return (uint16_t)VIC_D012
        | (uint16_t)((uint16_t)(VIC_D011 & 0x80u) << 1);
}

static void wait_raster_lines(uint16_t count) {
    uint16_t previous = raster_line();
    while (count) {
        uint16_t current = raster_line();
        if (current != previous) {
            previous = current;
            --count;
        }
    }
}

static void snapshot(uint8_t index) {
    product_dma_copy(
        PROBE_TARGET, PROBE_BANK,
        (uint16_t)(uintptr_t)probe_curve[index], 0u, PROBE_BYTES);
}

static void put_u16(uint8_t offset, uint16_t value) {
    PROBE_MAILBOX[offset] = (uint8_t)value;
    PROBE_MAILBOX[(uint8_t)(offset + 1u)] = (uint8_t)(value >> 8);
}

int main(void) {
    uint8_t iteration;
    uint16_t expected;
    uint16_t repeat_hash = 0x65c2u;
    uint16_t repeat_mismatches = 0u;

    __asm__ volatile("sei" ::: "memory");
    DMA_MODE = 1u;
    PROBE_MAILBOX[0] = 'C';
    PROBE_MAILBOX[1] = 'V';
    PROBE_MAILBOX[2] = 'C';
    PROBE_MAILBOX[3] = '1';
    PROBE_MAILBOX[4] = 1u;
    PROBE_MAILBOX[5] = PROBE_STATE_RUNNING;
    PROBE_MAILBOX[6] = 0u;
    PROBE_MAILBOX[7] = 0u;
    put_u16(8u, 0u);
    PROBE_MAILBOX[22] = 0xffu;
    PROBE_MAILBOX[23] = 0xffu;
    put_u16(24u, PROBE_TARGET);

    fill_pattern(PROBE_CURVE_SEED);
    expected = crc16(probe_source);
    put_u16(18u, expected);
    product_dma_copy(
        (uint16_t)(uintptr_t)probe_source, 0u,
        PROBE_TARGET, PROBE_BANK, PROBE_BYTES);
    snapshot(0u);
    wait_raster_lines(PROBE_DELAY_2MS_LINES);
    snapshot(1u);
    wait_raster_lines(PROBE_DELAY_100MS_AFTER_2MS_LINES);
    snapshot(2u);
    wait_raster_lines(PROBE_DELAY_714MS_AFTER_100MS_LINES);
    snapshot(3u);
    for (iteration = 0u; iteration < 4u; ++iteration) {
        uint16_t observed = crc16(probe_curve[iteration]);
        put_u16((uint8_t)(10u + 2u * iteration), observed);
        if (observed != expected)
            ++PROBE_MAILBOX[7];
    }

    for (iteration = 0u; iteration < PROBE_REPETITIONS; ++iteration) {
        uint16_t offset;
        uint8_t seed = (uint8_t)(0x80u + iteration);
        uint8_t mismatch = 0u;
        fill_pattern(seed);
        product_dma_copy(
            (uint16_t)(uintptr_t)probe_source, 0u,
            PROBE_TARGET, PROBE_BANK, PROBE_BYTES);
        poison_readback();
        product_dma_copy(
            PROBE_TARGET, PROBE_BANK,
            (uint16_t)(uintptr_t)probe_readback, 0u, PROBE_BYTES);
        for (offset = 0u; offset < PROBE_BYTES; ++offset) {
            if (probe_readback[offset] != probe_source[offset]) {
                if (!mismatch && PROBE_MAILBOX[22] == 0xffu) {
                    PROBE_MAILBOX[22] = iteration;
                    PROBE_MAILBOX[23] = (uint8_t)offset;
                }
                mismatch = 1u;
            }
        }
        if (mismatch)
            ++repeat_mismatches;
        repeat_hash = (uint16_t)(
            (repeat_hash << 1) | (repeat_hash >> 15));
        repeat_hash ^= crc16(probe_readback);
        PROBE_MAILBOX[6] = (uint8_t)(iteration + 1u);
    }
    put_u16(8u, repeat_mismatches);
    put_u16(20u, repeat_hash);
    PROBE_MAILBOX[5] = PROBE_STATE_COMPLETE;
    VIC_BORDER = repeat_mismatches || PROBE_MAILBOX[7] ? 2u : 5u;
    for (;;) { }
}
