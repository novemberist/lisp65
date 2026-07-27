/* Receipt-less controller for the bounded C2 KERNAL-unmap hardware proof.
 *
 * The $e000 window is a separately linked and preloaded artifact.  This PRG
 * remains below $c000, performs the firmware-to-product handoff once, then
 * exercises owned vectors, the typed queue and Freezer restoration without a
 * KERNAL service edge.  It is not a product candidate and emits no receipt.
 */
#include <stdint.h>
#include "screen.h"
#include "hw-mega65-hwops.h"
#include "c2-kernal-unmap-proof-shared.h"
#include "c2-kernal-unmap-generated.h"
#include "l-full-keymap.generated.h"

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
#define KEY_MODS  REG8(0xd60a)

#define COLOR_RED 2u
#define COLOR_GREEN 5u
#define COLOR_YELLOW 7u
#define C2KU_STAGE_ROW (0x0800u + 6u * 80u)
#define C2KU_WINDOW_STAGE_PHYSICAL 0x087fe000ul

extern void c2ku_capture_firmware_map(void);
extern void c2ku_map_window(void);
extern void c2ku_window_dispatch_call(void);
extern void c2ku_prehandoff_irq(void);

static void mark_stage(uint8_t slot, uint8_t marker) {
    /* Cursor-independent hardware diagnosis.  These cells are deliberately
     * outside the controller mailbox and survive a broken screen cursor. */
    REG8((uint16_t)(C2KU_STAGE_ROW + slot)) = marker;
}

static void puts_scr(const char *s) {
    while (*s) scr_putc(*s++);
}

static void put_hex4(uint8_t value) {
    value &= 0x0fu;
    scr_putc((char)(value < 10u ? '0' + value : 'a' + value - 10u));
}

static void put_hex8(uint8_t value) {
    put_hex4((uint8_t)(value >> 4));
    put_hex4(value);
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

static uint16_t crc16_update(uint16_t crc, uint8_t value) {
    uint8_t bit;
    crc ^= (uint16_t)value << 8;
    for (bit = 0; bit < 8u; ++bit)
        crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u)
                              : (uint16_t)(crc << 1);
    return crc;
}

static uint8_t mapped_window_matches(void) {
    uint16_t offset;
    uint16_t crc = 0xffffu;
    volatile const uint8_t *window = (volatile const uint8_t *)C2KU_WINDOW_BASE;
    /* Firmware mapping deliberately hides the underlying bank-0 bytes before
     * the handoff.  Validate through the actual CPU view after MAP, while SEI
     * and the handoff-closed state still make publication impossible. */
    for (offset = 0; offset < C2KU_WINDOW_BYTES; ++offset)
        crc = crc16_update(crc, window[offset]);
    REG8(C2KU_WINDOW_CRC_LO) = (uint8_t)crc;
    REG8(C2KU_WINDOW_CRC_HI) = (uint8_t)(crc >> 8);
    return crc == C2KU_WINDOW_CRC16;
}

static void stage_window_for_handoff(void) {
    /* Host tools use $f700 as transport scratch.  Keep the host-verified
     * source in Attic and publish the physical Bank-0 window only after the
     * handoff is closed, when no host operation remains before validation. */
    hw_edma_copy(C2KU_WINDOW_STAGE_PHYSICAL, C2KU_WINDOW_BASE,
                 C2KU_WINDOW_BYTES);
}

static uint16_t frame_count(void) {
    uint8_t high_a, low, high_b;
    do {
        high_a = REG8(C2KU_FRAME_HI);
        low = REG8(C2KU_FRAME_LO);
        high_b = REG8(C2KU_FRAME_HI);
    } while (high_a != high_b);
    return (uint16_t)low | ((uint16_t)high_a << 8);
}

static void stop_fail(uint8_t code) {
    __asm__ volatile("sei" ::: "memory");
    VIC_D01A = 0;
    hw_border(COLOR_RED);
    scr_clear();
    mark_stage(0u, '!');
    mark_stage(1u, (uint8_t)(code >> 4) < 10u
                     ? (uint8_t)('0' + (code >> 4))
                     : (uint8_t)('a' + (code >> 4) - 10u));
    mark_stage(2u, (uint8_t)(code & 0x0fu) < 10u
                     ? (uint8_t)('0' + (code & 0x0fu))
                     : (uint8_t)('a' + (code & 0x0fu) - 10u));
    puts_scr("C2 KERNAL-UNMAP PROBE\n\nFAIL - FIRST RED ");
    put_hex8(code);
    /* Keep the compact post-MAP diagnostics free of tiny ZP string literals:
     * some llvm-mos layouts place those in startup-only ZP data.  Raw fields
     * are: frame-hi/lo, unexpected-IRQ, state, map-generation, dequeues. */
    scr_putc('\n'); put_hex8(REG8(C2KU_FRAME_HI));
    put_hex8(REG8(C2KU_FRAME_LO)); scr_putc(' ');
    put_hex8(REG8(C2KU_UNEXPECTED_IRQ)); scr_putc(' ');
    put_hex8(REG8(C2KU_STATE)); scr_putc(' ');
    put_hex8(REG8(C2KU_MAP_GENERATION)); scr_putc(' ');
    put_hex8(REG8(C2KU_DEQUEUE_COUNT));
    puts_scr("\nNO PRODUCT LINK\nDISK REBOOT REQUIRED\n");
    for (;;) { }
}

static void wait_frames(uint16_t count, uint8_t fail_code) {
    uint16_t start = frame_count();
    uint32_t fuel = 0x01fffffful;
    while ((uint16_t)(frame_count() - start) < count && fuel) --fuel;
    if (!fuel) stop_fail(fail_code);
}

static uint8_t poll_window_event(void) {
    REG8(C2KU_COMMAND) = C2KU_CMD_POLL_EVENT;
    REG8(C2KU_RESPONSE) = 0;
    c2ku_window_dispatch_call();
    return REG8(C2KU_RESPONSE);
}

static void flush_queue(void) {
    /* D60A is the pending/modifier snapshot; D619 is dequeued by writing the
     * byte just read.  Merely zeroing D60A leaves a queued event alive and can
     * let a stale RUN/STOP cross the handoff without an operator action. */
    while (KEY_MODS & 0x80u) {
        uint8_t code = REG8(0xd619);
        REG8(0xd619) = code;
    }
}

static void wait_firmware_event(uint8_t wanted, uint8_t fail_code) {
    uint32_t fuel = 0x0ffffffful;
    while (fuel) {
        if (KEY_MODS & 0x80u) {
            uint8_t code = REG8(0xd619);
            if (code == wanted) {
                /* Firmware-side observations cross the handoff only through
                 * explicit semantic state.  Never leave their hardware queue
                 * records behind for the product-owned consumer: a stale
                 * head blocks every later typed event even while the physical
                 * scanner and the queue producer remain healthy. */
                REG8(0xd619) = code;
                return;
            }
            /* Launch residue and unrelated keys are discarded explicitly. */
            REG8(0xd619) = code;
        }
        --fuel;
    }
    stop_fail(fail_code);
}

static void wait_event(uint8_t code, uint8_t required_mods, uint8_t fail_code) {
    uint32_t fuel = 0x0ffffffful;
    while (fuel) {
        if (poll_window_event()) {
            uint8_t got_code = REG8(C2KU_EVENT_CODE);
            uint8_t got_mods = REG8(C2KU_EVENT_MODIFIERS);
            if (got_code != code || (got_mods & required_mods) != required_mods) {
                scr_putc('\n');
                puts_scr("GOT CODE $"); put_hex8(got_code);
                puts_scr(" MOD $"); put_hex8(got_mods);
                stop_fail(fail_code);
            }
            return;
        }
        --fuel;
    }
    stop_fail((uint8_t)(fail_code + 1u));
}

static void arm_prehandoff_frame_source(void) {
    __asm__ volatile("sei" ::: "memory");
    REG8(C2KU_OLD_IRQ_LO) = REG8(0x0314);
    REG8(C2KU_OLD_IRQ_HI) = REG8(0x0315);
    REG8(0x0314) = (uint8_t)(uintptr_t)c2ku_prehandoff_irq;
    REG8(0x0315) = (uint8_t)((uintptr_t)c2ku_prehandoff_irq >> 8);
    CIA1_ICR = 0x7fu;
    (void)CIA1_ICR;
    /* The exact same VIC raster source feeds the KERNAL-dispatched shim now
     * and the owned hardware vector after MAP.  Only vector ownership changes;
     * the authoritative monotonic counter and source do not. */
    VIC_D012 = 0xffu;
    VIC_D011 &= 0x7fu;
    VIC_D019 = 0xffu;
    VIC_D01A = 0x01u;
    __asm__ volatile("cli" ::: "memory");
}

static void enter_product_owned(void) {
    uint16_t before;

    REG8(C2KU_STATE) = C2KU_STATE_ARMED;
    arm_prehandoff_frame_source();
    wait_frames(2u, 0x21u);

    puts_scr("PRESS RUN/STOP TO CROSS HANDOFF\n");
    wait_firmware_event(LFULL_RUN_STOP_PETSCII, 0x20u);
    REG8(C2KU_ABORT_LATCHED) = 1u;

    __asm__ volatile("sei" ::: "memory");
    REG8(C2KU_STATE) = C2KU_STATE_CLOSED;
    before = frame_count();
    REG8(C2KU_HANDOFF_FRAME_LO) = (uint8_t)before;
    REG8(C2KU_HANDOFF_FRAME_HI) = (uint8_t)(before >> 8);

    CIA1_ICR = 0x7fu;
    (void)CIA1_ICR;
    CIA2_CRA = 0;
    CIA2_ICR = 0x7fu;
    (void)CIA2_ICR;
    VIC_D019 = 0xffu;

    stage_window_for_handoff();
    /* The handoff owns the complete raster source context.  Firmware may
     * rewrite D01A/D011/D012 while it owns IRQ dispatch, so no setting from
     * arm_prehandoff_frame_source is inherited across the publication seam. */
    VIC_D012 = 0xffu;
    VIC_D011 &= 0x7fu;
    VIC_D019 = 0xffu;
    VIC_D01A = 0x01u;
    REG8(C2KU_VIC_D01A_PRE_MAP) = VIC_D01A;
    mark_stage(0u, 'A');
    c2ku_map_window();
    REG8(C2KU_VIC_D01A_POST_MAP) = VIC_D01A;
    /* MAP/EOM owns the address handoff; establish the interrupt source in the
     * resulting mapping as well.  Publication remains closed and SEI remains
     * in force throughout. */
    VIC_D012 = 0xffu;
    VIC_D011 &= 0x7fu;
    VIC_D019 = 0xffu;
    VIC_D01A = 0x01u;
    REG8(C2KU_VIC_D01A_REARMED) = VIC_D01A;
    mark_stage(1u, 'B');
    if (!mapped_window_matches()) stop_fail(0x11u);
    mark_stage(2u, 'C');
    REG8(C2KU_COMMAND) = C2KU_CMD_VALIDATE;
    REG8(C2KU_RESPONSE) = 0;
    c2ku_window_dispatch_call();
    if (REG8(C2KU_RESPONSE) != C2KU_RESPONSE_MAGIC) stop_fail(0x22u);
    mark_stage(3u, 'D');

    /* The window and the vector table became visible in the same MAP commit.
     * Interrupts remain masked until the owned raster source is armed. */
    if ((REG8(C2KU_VIC_D01A_REARMED) & 0x01u) == 0u) stop_fail(0x23u);
    mark_stage(4u, 'E');
    REG8(C2KU_MAP_GENERATION) = 1u;
    REG8(C2KU_STATE) = C2KU_STATE_PRODUCT;
    mark_stage(5u, 'F');
    __asm__ volatile("cli" ::: "memory");

    /* RUN/STOP crossed the handoff as a semantic latch.  Its firmware-owned
     * queue record was consumed before closure; the latch is the sole
     * continuity object and is consumed exactly once here. */
    if (!REG8(C2KU_ABORT_LATCHED)) stop_fail(0x25u);
    REG8(C2KU_ABORT_LATCHED) = 0;
    wait_frames(2u, 0x26u);
}

static void prove_owned_nmi(void) {
    uint8_t before = REG8(C2KU_NMI_COUNT);
    CIA2_CRA = 0;
    CIA2_ICR = 0x7fu;
    (void)CIA2_ICR;
    CIA2_TALO = 0x00u;
    CIA2_TAHI = 0x08u;
    CIA2_ICR = 0x81u;
    CIA2_CRA = 0x19u;
    while (REG8(C2KU_NMI_COUNT) == before) { }
    CIA2_CRA = 0;
    CIA2_ICR = 0x7fu;
    (void)CIA2_ICR;
}

int main(void) {
    uint16_t freezer_frame;
    uint8_t dequeue_before;

    hw_m65_fast();
    hw_border(COLOR_YELLOW);
    scr_init();
    puts_scr("C2 KERNAL-UNMAP PROBE\nRECEIPT-LESS / NON-PRODUCT\n\n");

    REG8(C2KU_STATE) = C2KU_STATE_FIRMWARE;
    REG8(C2KU_FRAME_LO) = 0;
    REG8(C2KU_FRAME_HI) = 0;
    REG8(C2KU_NMI_COUNT) = 0;
    REG8(C2KU_DEQUEUE_COUNT) = 0;
    REG8(C2KU_UNEXPECTED_IRQ) = 0;
    REG8(C2KU_MAP_GENERATION) = 0;
    REG8(C2KU_ABORT_LATCHED) = 0;
    REG8(C2KU_UNOWNED_VIC_FLAGS) = 0;
    flush_queue();
    c2ku_capture_firmware_map();

    puts_scr("PHYSICAL WINDOW HOST-GATE BOUND\n");

    /* m65 -r can leave a launch event in the hardware queue.  A distinct
     * operator arming key makes the following RUN/STOP continuity sample
     * provably fresh rather than inherited from deployment. */
    puts_scr("PRESS F TO ARM FRESH INPUT\n");
    wait_firmware_event(0x46u, 0x12u);
    flush_queue();

    enter_product_owned();
    puts_scr("RUN/STOP + FRAME CONTINUITY OK\n");

    dequeue_before = REG8(C2KU_DEQUEUE_COUNT);
    puts_scr("PRESS CONTROL-SPACE\n");
    wait_event(LFULL_CONTROL_SPACE_PETSCII, LFULL_MOD_CONTROL, 0x30u);
    puts_scr("C-SPACE ATOMIC EVENT OK\n");

    puts_scr("PRESS ALT-X (META-X)\n");
    wait_event(LFULL_META_X_PETSCII, LFULL_MOD_META, 0x32u);
    puts_scr("M-X ATOMIC EVENT OK\n");
    if ((uint8_t)(REG8(C2KU_DEQUEUE_COUNT) - dequeue_before) != 2u)
        stop_fail(0x34u);

    prove_owned_nmi();
    if (REG8(C2KU_UNEXPECTED_IRQ)) stop_fail(0x46u);
    puts_scr("OWNED IRQ + NMI OK\n\n");

    freezer_frame = frame_count();
    puts_scr("OPEN FREEZER, THEN EXIT\n");
    puts_scr("AFTER RETURN PRESS F\n");
    wait_event(0x46u, 0u, 0x40u);

    if (REG8(C2KU_STATE) != C2KU_STATE_PRODUCT
        || REG8(C2KU_MAP_GENERATION) != 1u) stop_fail(0x42u);
    REG8(C2KU_COMMAND) = C2KU_CMD_VALIDATE;
    REG8(C2KU_RESPONSE) = 0;
    c2ku_window_dispatch_call();
    if (REG8(C2KU_RESPONSE) != C2KU_RESPONSE_MAGIC) stop_fail(0x43u);
    if (REG8(C2KU_UNEXPECTED_IRQ) > 1u
        || REG8(C2KU_UNOWNED_VIC_FLAGS) != 0u) stop_fail(0x46u);
    wait_frames(2u, 0x44u);
    if (frame_count() == freezer_frame) stop_fail(0x45u);
    if (REG8(C2KU_UNEXPECTED_IRQ) > 1u) stop_fail(0x46u);

    hw_border(COLOR_GREEN);
    scr_clear();
    puts_scr("C2 KERNAL-UNMAP PROBE\n\nPASS - RECEIPT-LESS PREFILTER\n");
    puts_scr("RUN/STOP CONTINUITY YES\nFRAME CONTINUITY YES\n");
    puts_scr("C-SPACE + M-X QUEUE YES\nOWNED IRQ/NMI YES\n");
    puts_scr("FREEZER MAP/VECTOR RETURN YES\n\nFRAMES ");
    put_u16(frame_count());
    puts_scr("  DEQUEUES ");
    put_u16(REG8(C2KU_DEQUEUE_COUNT));
    puts_scr("\nNO PRODUCT LINK CLAIM\n");
    for (;;) { }
    return 0;
}
