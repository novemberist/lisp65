/* lisp65 -- MEGA65 hardware-probe helpers.
 *
 * Test-only code for small, isolated PRGs. Nothing here is linked into the
 * product profiles unless a smoke main includes this header explicitly.
 */
#ifndef LISP65_HW_MEGA65_HWOPS_H
#define LISP65_HW_MEGA65_HWOPS_H

#include <stdint.h>
#include <mega65.h>

#define HW_M65_SCREEN_CELLS 2000u
#define HW_M65_COLOR_RAM    0x0ff80000ul
#define HW_M65_ATTIC_RAM    0x08000000ul

static void __attribute__((unused)) hw_m65_fast(void) {
#ifdef __MEGA65__
    *(volatile uint8_t *)0xd02f = 0x47;  /* VIC-IV / extended IO unlock */
    *(volatile uint8_t *)0xd02f = 0x53;
    *(volatile uint8_t *)0xd054 |= 0x40; /* VFAST: 40 MHz */
#endif
}

static void __attribute__((unused)) hw_border(uint8_t color) {
    *(volatile uint8_t *)0xd020 = color;
    *(volatile uint8_t *)0xd021 = 0;
}

__attribute__((used)) static uint8_t hw_dma_list[12];

static void __attribute__((unused)) hw_dma_legacy_copy(uint32_t src, uint32_t dst, uint16_t count) {
    hw_dma_list[0] = 0x00;
    hw_dma_list[1] = (uint8_t)count;
    hw_dma_list[2] = (uint8_t)(count >> 8);
    hw_dma_list[3] = (uint8_t)src;
    hw_dma_list[4] = (uint8_t)(src >> 8);
    hw_dma_list[5] = (uint8_t)((src >> 16) & 0x0f);
    hw_dma_list[6] = (uint8_t)dst;
    hw_dma_list[7] = (uint8_t)(dst >> 8);
    hw_dma_list[8] = (uint8_t)((dst >> 16) & 0x0f);
    hw_dma_list[9] = 0;
    hw_dma_list[10] = 0;
    hw_dma_list[11] = 0;
    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "lda #mos16hi(hw_dma_list)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(hw_dma_list)\n\t"
        "sta $d700\n\t"
        ::: "a", "memory");
}

struct hw_edma_job {
    uint8_t options[7];
    uint8_t end_option;
    uint8_t dmalist[12];
};

__attribute__((used)) static struct hw_edma_job hw_edma;

static void __attribute__((unused)) hw_edma_common(uint8_t cmd, uint32_t src, uint32_t dst,
                                                   uint16_t count, uint8_t fill_value) {
    hw_edma.options[0] = ENABLE_F018B_OPT;
    hw_edma.options[1] = SRC_ADDR_BITS_OPT;
    hw_edma.options[2] = (uint8_t)(src >> 20);
    hw_edma.options[3] = DST_ADDR_BITS_OPT;
    hw_edma.options[4] = (uint8_t)(dst >> 20);
    hw_edma.options[5] = DST_SKIP_RATE_OPT;
    hw_edma.options[6] = 1;
    hw_edma.end_option = 0;

    hw_edma.dmalist[0] = cmd;
    hw_edma.dmalist[1] = (uint8_t)count;
    hw_edma.dmalist[2] = (uint8_t)(count >> 8);
    if (cmd == DMA_FILL_CMD) {
        hw_edma.dmalist[3] = fill_value;
        hw_edma.dmalist[4] = 0;
        hw_edma.dmalist[5] = 0;
    } else {
        hw_edma.dmalist[3] = (uint8_t)src;
        hw_edma.dmalist[4] = (uint8_t)(src >> 8);
        hw_edma.dmalist[5] = (uint8_t)((src >> 16) & 0x0f);
    }
    hw_edma.dmalist[6] = (uint8_t)dst;
    hw_edma.dmalist[7] = (uint8_t)(dst >> 8);
    hw_edma.dmalist[8] = (uint8_t)((dst >> 16) & 0x0f);
    hw_edma.dmalist[9] = 0;
    hw_edma.dmalist[10] = 0;
    hw_edma.dmalist[11] = 0;

    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(hw_edma)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(hw_edma)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
}

static void __attribute__((unused)) hw_edma_copy(uint32_t src, uint32_t dst, uint16_t count) {
    hw_edma_common(DMA_COPY_CMD, src, dst, count, 0);
}

static void __attribute__((unused)) hw_edma_fill(uint32_t dst, uint8_t value, uint16_t count) {
    hw_edma_common(DMA_FILL_CMD, 0, dst, count, value);
}

__attribute__((section(".zp.bss"), used)) static uint8_t hw_flat_ptr[4];

static void __attribute__((unused)) hw_flat_set(uint32_t addr) {
    hw_flat_ptr[0] = (uint8_t)addr;
    hw_flat_ptr[1] = (uint8_t)(addr >> 8);
    hw_flat_ptr[2] = (uint8_t)(addr >> 16);
    hw_flat_ptr[3] = (uint8_t)(addr >> 24);
}

static uint8_t __attribute__((unused)) hw_flat_read8(uint32_t addr) {
    uint8_t out;
    hw_flat_set(addr);
    __asm__ volatile(
        "ldz #0\n\t"
        ".byte $ea,$b2,mos16lo(hw_flat_ptr)\n\t"
        "sta %0\n\t"
        : "=m"(out)
        :
        : "a", "memory");
    return out;
}

static void __attribute__((unused)) hw_flat_write8(uint32_t addr, uint8_t value) {
    hw_flat_set(addr);
    __asm__ volatile(
        "lda %0\n\t"
        "ldz #0\n\t"
        ".byte $ea,$92,mos16lo(hw_flat_ptr)\n\t"
        :
        : "m"(value)
        : "a", "memory");
}

#endif /* LISP65_HW_MEGA65_HWOPS_H */
