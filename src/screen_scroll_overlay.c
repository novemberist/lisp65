/* Color-safe Workbench scroll job. The isolated hardware smoke exercises this
 * entry directly. Product integration is deferred to C2 after the bounded
 * Wave-3 link attempts; keeping the recipe here avoids creating a second,
 * smoke-only DMA implementation. */
#include "screen_scroll_overlay.h"

#if defined(__mos__) && defined(LISP65_SCREEN_EDMA_SCROLL)
#include <mega65.h>

#define M65_COLOR_RAM_28 0x0ff80000ul

#if defined(LISP65_RUNTIME_OVERLAY)
#define SCREEN_SCROLL_ENTRY \
    __attribute__((section(".lisp65_rt_screen_scroll"), noinline, used))
#define SCREEN_SCROLL_DATA \
    __attribute__((section(".lisp65_rt_screen_scroll_data"), used))
#else
#define SCREEN_SCROLL_ENTRY
#define SCREEN_SCROLL_DATA __attribute__((used))
#endif

struct screen_edma_job {
    uint8_t options[7];
    uint8_t end_option;
    uint8_t dmalist[12];
};

/* The inline assembly names this object directly. Keep the symbol global so
 * llvm-mos LTO cannot give the C object and the assembler reference different
 * internal names. */
SCREEN_SCROLL_DATA struct screen_edma_job lisp65_screen_edma_job = {{0}, 0, {0}};

static __attribute__((always_inline)) inline void screen_edma_common(
        uint8_t cmd, uint32_t src, uint32_t dst, uint16_t count,
        uint8_t fill_value) {
    lisp65_screen_edma_job.options[0] = ENABLE_F018B_OPT;
    lisp65_screen_edma_job.options[1] = SRC_ADDR_BITS_OPT;
    lisp65_screen_edma_job.options[2] = (uint8_t)(src >> 20);
    lisp65_screen_edma_job.options[3] = DST_ADDR_BITS_OPT;
    lisp65_screen_edma_job.options[4] = (uint8_t)(dst >> 20);
    lisp65_screen_edma_job.options[5] = DST_SKIP_RATE_OPT;
    lisp65_screen_edma_job.options[6] = 1;
    lisp65_screen_edma_job.end_option = 0;

    lisp65_screen_edma_job.dmalist[0] = cmd;
    lisp65_screen_edma_job.dmalist[1] = (uint8_t)count;
    lisp65_screen_edma_job.dmalist[2] = (uint8_t)(count >> 8);
    if (cmd == DMA_FILL_CMD) {
        lisp65_screen_edma_job.dmalist[3] = fill_value;
        lisp65_screen_edma_job.dmalist[4] = 0;
        lisp65_screen_edma_job.dmalist[5] = 0;
    } else {
        lisp65_screen_edma_job.dmalist[3] = (uint8_t)src;
        lisp65_screen_edma_job.dmalist[4] = (uint8_t)(src >> 8);
        lisp65_screen_edma_job.dmalist[5] = (uint8_t)((src >> 16) & 0x0f);
    }
    lisp65_screen_edma_job.dmalist[6] = (uint8_t)dst;
    lisp65_screen_edma_job.dmalist[7] = (uint8_t)(dst >> 8);
    lisp65_screen_edma_job.dmalist[8] = (uint8_t)((dst >> 16) & 0x0f);
    lisp65_screen_edma_job.dmalist[9] = 0;
    lisp65_screen_edma_job.dmalist[10] = 0;
    lisp65_screen_edma_job.dmalist[11] = 0;

    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(lisp65_screen_edma_job)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(lisp65_screen_edma_job)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
}

static __attribute__((always_inline)) inline void screen_edma_copy(
        uint32_t src, uint32_t dst, uint16_t count) {
    screen_edma_common(DMA_COPY_CMD, src, dst, count, 0);
}

static __attribute__((always_inline)) inline void screen_edma_fill(
        uint32_t dst, uint8_t value, uint16_t count) {
    screen_edma_common(DMA_FILL_CMD, 0, dst, count, value);
}

SCREEN_SCROLL_ENTRY uint8_t lisp65_screen_scroll_overlay_entry(void *opaque) {
    lisp65_screen_scroll_context *context =
        (lisp65_screen_scroll_context *)opaque;
    uint32_t base;
    if (!context || !context->columns || !context->copy_bytes) return 1;
    base = context->screen_base;
    screen_edma_copy(base + context->columns, base, context->copy_bytes);
    screen_edma_fill(base + context->copy_bytes, 0x20, context->columns);
    screen_edma_copy(M65_COLOR_RAM_28 + context->columns,
                     M65_COLOR_RAM_28, context->copy_bytes);
    screen_edma_fill(M65_COLOR_RAM_28 + context->copy_bytes,
                     1, context->columns);
    return 0;
}

#else
uint8_t lisp65_screen_scroll_overlay_entry(void *opaque) {
    (void)opaque;
    return 1;
}
#endif
