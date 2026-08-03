/* C2 product ownership of the MEGA65 $e000 window and typed event queue.
 *
 * The window is a separately linked, SHA-bound product artifact staged in
 * Attic RAM by the product packer.  This resident facade publishes it into
 * physical bank-0 RAM, establishes the complete raster context, maps the
 * owned $e000-$ffff product window, validates its CPU-visible bytes, and only
 * then enables owned IRQs.  The adjacent $d000 I/O block remains unmapped.
 * No physical address is represented by a C pointer before it is in the
 * 16-bit CPU map. */
#include <stdint.h>
#include "c2_kernal_runtime.h"
#include "mega65_raster_timebase.h"

#ifdef LISP65_C2_KERNAL_UNMAP
#include "c2-kernal-window.generated.h"

#define C2K_SECTION __attribute__((noinline, section(".lisp65_c2_kernal_handoff")))
#define C2K_BOOT_ONLY __attribute__((noinline, section(".text.c2_kernal_boot_only")))
#define REG8(address) (*(volatile uint8_t *)(address))

#define CIA1_ICR REG8(0xdc0d)
#define CIA2_ICR REG8(0xdd0d)
#define CIA2_CRA REG8(0xdd0e)
#define VIC_D011 REG8(0xd011)
#define VIC_D012 REG8(0xd012)
#define VIC_D019 REG8(0xd019)
#define VIC_D01A REG8(0xd01a)
#define ETHERNET_IRQ REG8(0xd6e1)
#define AUTOIEC_IRQ  REG8(0xd697)
#define AUDIODMA_IRQ REG8(0xd713)

#define C2K_FRAME_LO        REG8(LISP65_C2_FRAME_LO_ADDRESS)
#define C2K_FRAME_HI        REG8(LISP65_C2_FRAME_HI_ADDRESS)
#define C2K_MAP_GENERATION  REG8(0xff87)
#define C2K_STATE           REG8(0xff88)

#define C2K_STATE_PRODUCT 4u

extern void c2_kernal_reveal_io(void);
extern void c2_kernal_map_window(void);

/* One enhanced-DMA descriptor.  High address nibbles are explicit fields;
 * Attic addresses never pass through the platform's 16-bit uintptr_t. */
__attribute__((used, section(".lisp65_c2_kernal_state")))
static uint8_t c2k_dma_job[20];

static C2K_SECTION void c2k_copy(uint32_t source, uint32_t target,
                                 uint16_t length) {
    uint8_t *job = c2k_dma_job;
    job[0] = 0x0bu; job[1] = 0x80u; job[2] = (uint8_t)(source >> 20);
    job[3] = 0x81u; job[4] = (uint8_t)(target >> 20);
    job[5] = 0x85u; job[6] = 1u; job[7] = 0u; job[8] = 0u;
    job[9] = (uint8_t)length; job[10] = (uint8_t)(length >> 8);
    job[11] = (uint8_t)source; job[12] = (uint8_t)(source >> 8);
    job[13] = (uint8_t)((source >> 16) & 0x0fu);
    job[14] = (uint8_t)target; job[15] = (uint8_t)(target >> 8);
    job[16] = (uint8_t)((target >> 16) & 0x0fu);
    job[17] = 0u; job[18] = 0u; job[19] = 0u;
    __asm__ volatile(
        /* Z is normalized at the ownership boundary below.  Writing D702
         * clears D704 by controller contract, so the second zero-store is
         * redundant; omitting it pays for the I/O-personality boundary call
         * without growing the fixed handoff block. */
        "lda #1\n\tsta $d703\n\tstz $d702\n\t"
        "lda #mos16hi(c2k_dma_job)\n\tsta $d701\n\t"
        "lda #mos16lo(c2k_dma_job)\n\tsta $d705\n\t"
        ::: "a", "memory");
}

/* This verifier is consumed exactly once while ownership is being acquired.
 * Keep the fixed handoff for the code that must remain on its pinned facade;
 * ordinary resident text is already owned when this boot-only body runs. */
static C2K_BOOT_ONLY uint16_t c2k_crc16(
        const volatile uint8_t *source, uint16_t length) {
    uint16_t crc = 0xffffu;
    while (length--) {
        uint8_t bit;
        crc ^= (uint16_t)*source++ << 8;
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u)
                                  : (uint16_t)(crc << 1);
    }
    return crc;
}

C2K_SECTION uint8_t c2_kernal_take_ownership(void) {
    /* Firmware-owned IRQ code is outside the llvm-mos ABI and may return with
     * the 45GS02 Z register nonzero.  llvm-mos emits STZ for C zero stores and
     * therefore requires Z == 0 at every C boundary.  Close the firmware-to-C
     * handoff before the first generated store; the Link-19 hardware pre-smoke
     * caught Z == $06 turning every zero in the DMA descriptor into $06. */
    __asm__ volatile("sei\n\tldz #0" ::: "memory");

    /* $D700 is meaningful only in the MEGA65 I/O personality.  C2 boot-time
     * work may return with another personality selected; normalize it before
     * the first CIA, VIC or DMA register access.  Link-20 hardware diagnosis
     * proved that repeating this knock makes the unchanged DMA job publish
     * the pinned $E000 window byte-for-byte. */
    c2_kernal_reveal_io();

    /* The full interrupt context is established again after MAP; nothing is
     * inherited from firmware-maintained register state. */
    CIA1_ICR = 0x7fu; (void)CIA1_ICR;
    CIA2_CRA = 0u;
    CIA2_ICR = 0x7fu; (void)CIA2_ICR;
    VIC_D01A = 0u;
    VIC_D019 = 0xffu;

    /* Raster is the sole product-owned IRQ.  Firmware/hypervisor state may
     * leave these otherwise unrelated source families enabled, including
     * Audio-DMA even when this product never uses it.  Mask every internal
     * foreign source while SEI is still in force, then prove the enable
     * fields read back disabled before publishing the owned vectors. */
    ETHERNET_IRQ = 0u;
    AUTOIEC_IRQ = 0xf0u;
    AUDIODMA_IRQ = 0u;
    if ((ETHERNET_IRQ & 0xc0u) != 0u
        || (AUTOIEC_IRQ & 0x0fu) != 0u
        || (AUDIODMA_IRQ & 0x0fu) != 0u)
        return 0u;

    c2k_copy(C2_KERNAL_WINDOW_STAGE_PHYSICAL,
             C2_KERNAL_WINDOW_CPU_BASE, C2_KERNAL_WINDOW_BYTES);
    c2_kernal_map_window();

    if (c2k_crc16((volatile const uint8_t *)C2_KERNAL_WINDOW_CPU_BASE,
                  C2_KERNAL_WINDOW_BYTES) != C2_KERNAL_WINDOW_CRC16)
        return 0u;

    C2K_MAP_GENERATION = 1u;
    C2K_STATE = C2K_STATE_PRODUCT;
    lisp65_raster_timebase_arm();
    __asm__ volatile("cli" ::: "memory");
    return 1u;
}

C2K_SECTION uint16_t c2_kernal_frame_count(void) {
    return c2_kernal_frame_count_inline();
}

#endif /* LISP65_C2_KERNAL_UNMAP */
