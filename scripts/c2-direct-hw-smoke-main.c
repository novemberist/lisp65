/* Receipt-less, non-authoritative C2.1 hardware pre-smoke.
 *
 * The proof shelf is staged separately at $08100000.  The canonical C2 direct
 * target still decodes the byte-identical generated vector, but every hot-code
 * refill is served by Enhanced DMA from that Attic shelf.  Repeated complete
 * proof executions are run until a live KERNAL jiffy advances, so at least one
 * bounded execution interval is exposed to normal device interrupts.  The
 * deploy script stages the shelf afresh on every invocation; two invocations
 * are required before the product substitution link may start.
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"
#include "c2-direct-vectors.h"

#define C2_HW_SHELF_BASE 0x08100000UL
#define C2_HW_EXPECTED_REFILLS 22u
#define C2_HW_MIN_PASSES 2u
#define C2_HW_MAX_PASSES 64u

#define CIA1_TALO (*(volatile uint8_t *)0xdc04)
#define CIA1_TAHI (*(volatile uint8_t *)0xdc05)
#define CIA1_ICR  (*(volatile uint8_t *)0xdc0d)
#define CIA1_CRA  (*(volatile uint8_t *)0xdc0e)

#define COLOR_RED    2u
#define COLOR_GREEN  5u
#define COLOR_YELLOW 7u

extern int c2_target_proof_main(void);
extern volatile uint8_t c2_target_sink;

__attribute__((used)) volatile uint8_t c2_hw_pass;
__attribute__((used)) volatile uint8_t c2_hw_error;
__attribute__((used)) volatile uint8_t c2_hw_passes;
__attribute__((used)) volatile uint16_t c2_hw_refills;
__attribute__((used)) volatile uint8_t c2_hw_irq_seen;
__attribute__((used)) volatile uint8_t c2_hw_restaged_match;
__attribute__((used)) volatile uint8_t c2_hw_irq_count;
__attribute__((used)) uint8_t c2_hw_old_irq[2];

extern void c2_hw_irq_handler(void);

static uint8_t attic_back[32];

static void puts_scr(const char *s) {
    while (*s) scr_putc(*s++);
}

static void put_u16(uint16_t value) {
    uint16_t divisor = 10000u;
    uint8_t emitted = 0;
    while (divisor) {
        uint8_t digit = (uint8_t)(value / divisor);
        if (digit || emitted || divisor == 1u) {
            scr_putc((char)('0' + digit));
            emitted = 1;
        }
        value = (uint16_t)(value % divisor);
        divisor = (uint16_t)(divisor / 10u);
    }
}

static uint8_t staged_shelf_matches(void) {
    uint16_t at = 0;
    while (at < C2_DIRECT_SHELF_BYTES) {
        uint8_t i;
        uint16_t left = (uint16_t)(C2_DIRECT_SHELF_BYTES - at);
        uint8_t n = left > sizeof(attic_back) ? sizeof(attic_back) : (uint8_t)left;
        hw_edma_copy(C2_HW_SHELF_BASE + at,
                     (uint32_t)(uintptr_t)attic_back, n);
        for (i = 0; i < n; ++i)
            if (attic_back[i] != c2_direct_shelf[at + i]) return 0;
        at = (uint16_t)(at + n);
    }
    return 1;
}

uint8_t c2_hw_refill(uint16_t shelf_offset, uint8_t *dst, uint8_t length) {
    if (!length || shelf_offset > C2_DIRECT_SHELF_BYTES
        || length > (uint16_t)(C2_DIRECT_SHELF_BYTES - shelf_offset)) return 0;
    hw_edma_copy(C2_HW_SHELF_BASE + shelf_offset,
                 (uint32_t)(uintptr_t)dst, length);
    ++c2_hw_refills;
    return 1;
}

static void arm_bounded_irq_probe(void) {
    /* Etherload does not promise a live periodic KERNAL source.  Establish a
     * short, test-owned CIA1 Timer-A source and let the existing KERNAL IRQ
     * vector service it.  A 1000-cycle latch is frequent enough to overlap a
     * bounded proof batch without becoming persistent test state. */
    __asm__ volatile("sei" ::: "memory");
    c2_hw_irq_count = 0;
    c2_hw_old_irq[0] = *(volatile uint8_t *)0x0314;
    c2_hw_old_irq[1] = *(volatile uint8_t *)0x0315;
    *(volatile uint8_t *)0x0314 = (uint8_t)(uintptr_t)c2_hw_irq_handler;
    *(volatile uint8_t *)0x0315 = (uint8_t)((uintptr_t)c2_hw_irq_handler >> 8);
    CIA1_CRA = 0;
    CIA1_ICR = 0x7fu;
    (void)CIA1_ICR;
    CIA1_TALO = 0xe8u;
    CIA1_TAHI = 0x03u;
    CIA1_ICR = 0x81u;
    CIA1_CRA = 0x11u;
    __asm__ volatile("cli" ::: "memory");
}

static void disarm_bounded_irq_probe(void) {
    __asm__ volatile("sei" ::: "memory");
    CIA1_CRA = 0;
    CIA1_ICR = 0x7fu;
    (void)CIA1_ICR;
    *(volatile uint8_t *)0x0314 = c2_hw_old_irq[0];
    *(volatile uint8_t *)0x0315 = c2_hw_old_irq[1];
    __asm__ volatile("cli" ::: "memory");
}

static void show_result(void) {
    scr_clear();
    puts_scr("c2.1 direct attic hardware smoke\n\n");
    if (c2_hw_pass) {
        puts_scr("PASS - RECEIPT-LESS PREFILTER\n");
        puts_scr("routes 5/5, dma refills ");
        put_u16(c2_hw_refills);
        puts_scr("\npasses ");
        put_u16(c2_hw_passes);
        puts_scr(", irq yes, staged shelf yes\n");
        puts_scr("run once more for fresh restage\n");
    } else {
        puts_scr("FAIL - STOP BEFORE PRODUCT LINK\n");
        puts_scr("error ");
        put_u16(c2_hw_error);
        puts_scr(", passes ");
        put_u16(c2_hw_passes);
        puts_scr(", refills ");
        put_u16(c2_hw_refills);
        scr_putc('\n');
    }
}

int main(void) {
    uint8_t first_irq;
    uint16_t before;

    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    c2_hw_pass = 0;
    c2_hw_error = 0;
    c2_hw_passes = 0;
    c2_hw_refills = 0;
    c2_hw_irq_seen = 0;
    c2_hw_restaged_match = staged_shelf_matches();
    if (!c2_hw_restaged_match) {
        c2_hw_error = 80;
        goto done;
    }

    /* Require the KERNAL jiffy to advance while whole proof executions
     * (including all DMA refills) are running. */
    arm_bounded_irq_probe();
    first_irq = c2_hw_irq_count;
    do {
        int result;
        before = c2_hw_refills;
        result = c2_target_proof_main();
        if (result != 0) {
            c2_hw_error = (uint8_t)result;
            goto done;
        }
        ++c2_hw_passes;
        if ((uint16_t)(c2_hw_refills - before) != C2_HW_EXPECTED_REFILLS
            || c2_target_sink != 49u) {
            c2_hw_error = 81;
            goto done;
        }
        if (c2_hw_irq_count != first_irq) c2_hw_irq_seen = 1;
    } while ((!c2_hw_irq_seen || c2_hw_passes < C2_HW_MIN_PASSES)
             && c2_hw_passes < C2_HW_MAX_PASSES);

    if (!c2_hw_irq_seen) {
        c2_hw_error = 82;
        goto done;
    }
    c2_hw_pass = 1;

done:
    disarm_bounded_irq_probe();
    hw_border(c2_hw_pass ? COLOR_GREEN : COLOR_RED);
    show_result();
    for (;;) { }
    return 0;
}
