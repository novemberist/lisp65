/* C2 product platform DMA.
 *
 * This is deliberately separate from vm_embed.c: the C2 product still needs
 * code-window and cold symbol-table transfers, but must not pull the retired
 * L65M materializer, validator, directory publisher or their magic into its
 * source closure.  Banked CPU addresses remain 16-bit bank:offset values;
 * 28-bit physical Attic addresses use the Enhanced-DMA seam in
 * c2_product_runtime.c and never pass through C pointer types.
 */
#include <stdint.h>
#include "obj.h"
#include "c2_kernal_facade.h"

#if defined(LISP65_C2_PRODUCT_CUT) && defined(LISP65_EMBED_DMA)

/* Non-static: the inline assembler names this object directly and LTO cannot
 * otherwise see the reference. */
__attribute__((used)) uint8_t c2_dma_list[12];

#ifdef LISP65_DMA_PROF
uint16_t dma_code = 0, dma_wr = 0, dma_sym = 0;
#define DMA_COUNT(value) (++(value))
#else
#define DMA_COUNT(value) ((void)0)
#endif

LISP65_C2_REOPEN_TEXT_GAP2_FN
void c2_facade_target_c2_dma(uint16_t source, uint8_t source_bank,
                             uint16_t target, uint8_t target_bank,
                             uint16_t length) {
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

void vm_code_load(uint8_t bank, uint16_t offset, uint16_t length,
                  uint8_t *destination) {
    DMA_COUNT(dma_code);
    c2_facade_c2_dma(offset, bank,
                     (uint16_t)(uintptr_t)destination, 0u, length);
}

void vm_ext_write(const uint8_t *source, uint16_t length,
                  uint8_t bank, uint16_t offset) {
    DMA_COUNT(dma_wr);
    c2_facade_c2_dma((uint16_t)(uintptr_t)source, 0u, offset, bank, length);
}

#ifndef SYMPOOL_EXT_BANK
#define SYMPOOL_EXT_BANK 5u
#endif
#ifndef SYMPOOL_EXT_OFF
#define SYMPOOL_EXT_OFF 0x8000u
#endif

#ifdef LISP65_SYMPOOL_EXT
void sympool_read(uint16_t offset, char *destination, uint16_t length) {
    DMA_COUNT(dma_sym);
    c2_facade_c2_dma((uint16_t)(SYMPOOL_EXT_OFF + offset), SYMPOOL_EXT_BANK,
                     (uint16_t)(uintptr_t)destination, 0u, length);
}
void sympool_write(uint16_t offset, const char *source, uint16_t length) {
    c2_facade_c2_dma((uint16_t)(uintptr_t)source, 0u,
                     (uint16_t)(SYMPOOL_EXT_OFF + offset),
                     SYMPOOL_EXT_BANK, length);
}
#endif

#ifdef LISP65_SYMVAL_EXT
#ifndef SYMVAL_EXT_BANK
#define SYMVAL_EXT_BANK 5u
#endif
#ifndef SYMVAL_EXT_OFF
#define SYMVAL_EXT_OFF ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL))
#endif
obj symval_get(uint16_t index) {
    uint16_t value;
    c2_facade_c2_dma((uint16_t)(SYMVAL_EXT_OFF + index * 2u),
                     SYMVAL_EXT_BANK, (uint16_t)(uintptr_t)&value, 0u, 2u);
    return (obj)value;
}
void symval_set(uint16_t index, obj value) {
    uint16_t word = (uint16_t)value;
    c2_facade_c2_dma((uint16_t)(uintptr_t)&word, 0u,
                     (uint16_t)(SYMVAL_EXT_OFF + index * 2u),
                     SYMVAL_EXT_BANK, 2u);
}
#endif

#ifdef LISP65_NAMEOFF_EXT
#ifndef NAMEOFF_EXT_BANK
#define NAMEOFF_EXT_BANK 5u
#endif
#ifndef NAMEOFF_EXT_OFF
#define NAMEOFF_EXT_OFF ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 2u))
#endif
uint16_t nameoff_get(uint16_t index) {
    uint16_t value;
    c2_facade_c2_dma((uint16_t)(NAMEOFF_EXT_OFF + index * 2u),
                     NAMEOFF_EXT_BANK, (uint16_t)(uintptr_t)&value, 0u, 2u);
    return value;
}
void nameoff_set(uint16_t index, uint16_t offset) {
    c2_facade_c2_dma((uint16_t)(uintptr_t)&offset, 0u,
                     (uint16_t)(NAMEOFF_EXT_OFF + index * 2u),
                     NAMEOFF_EXT_BANK, 2u);
}
#endif

#ifdef LISP65_SYMFN_EXT
#ifndef SYMFN_EXT_BANK
#define SYMFN_EXT_BANK 5u
#endif
#ifndef SYMFN_EXT_OFF
#ifdef LISP65_NAMEOFF_EXT
#define SYMFN_EXT_OFF ((uint16_t)(NAMEOFF_EXT_OFF + MAX_SYM * 2u))
#elif defined(LISP65_SYMVAL_EXT)
#define SYMFN_EXT_OFF ((uint16_t)(SYMVAL_EXT_OFF + MAX_SYM * 2u))
#else
#define SYMFN_EXT_OFF ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL))
#endif
#endif

#if defined(LISP65_NAMEOFF_EXT)
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 6u) > 0x10000
#error "C2 EXT symbol layout exceeds Bank 5"
#endif
#elif defined(LISP65_SYMVAL_EXT)
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 4u) > 0x10000
#error "C2 EXT symbol layout exceeds Bank 5"
#endif
#else
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 2u) > 0x10000
#error "C2 EXT symbol layout exceeds Bank 5"
#endif
#endif

obj symfn_ext_get(uint16_t index) {
    uint16_t value;
    c2_facade_c2_dma((uint16_t)(SYMFN_EXT_OFF + index * 2u),
                     SYMFN_EXT_BANK, (uint16_t)(uintptr_t)&value, 0u, 2u);
    return (obj)value;
}
void symfn_ext_set(uint16_t index, obj value) {
    uint16_t word = (uint16_t)value;
    c2_facade_c2_dma((uint16_t)(uintptr_t)&word, 0u,
                     (uint16_t)(SYMFN_EXT_OFF + index * 2u),
                     SYMFN_EXT_BANK, 2u);
}
#endif

#undef DMA_COUNT
#endif /* LISP65_C2_PRODUCT_CUT && LISP65_EMBED_DMA */
