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
#include "c2_platform_dma.h"
#include "c2_kernal_facade.h"
#include "mega65_dma_descriptor.h"
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
#include "c2_kernal_runtime.h"
#include "c2_kernal_layout.h"
#include "c2_mapped_far_service.h"
#include "interrupt.h"
#include "vm.h"
#endif

#if defined(LISP65_C2_PRODUCT_CUT) && defined(LISP65_EMBED_DMA)

/* Non-static: the inline assembler names this object directly and LTO cannot
 * otherwise see the reference. */
__attribute__((used)) uint8_t c2_dma_list[12];
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
uint8_t c2_dma_verify_list[24]
    LISP65_C2_CONVERGENCE_STATE("d700_jobs");
volatile uint8_t c2_dma_verify
    LISP65_C2_CONVERGENCE_STATE("d700_value");
volatile uint8_t LISP65_C2_ZP c2_dma_verify_done
    LISP65_C2_CONVERGENCE_ZP("d700_done");
const uint8_t c2_dma_verify_marker = 0xa5u;
#endif

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
    lisp65_f018_descriptor(c2_dma_list, 0u, source, source_bank,
                           target, target_bank, length);
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
#if defined(LISP65_CODE_WINDOW_CONVERGENCE) \
    && (!defined(__mos__) || !defined(LISP65_C2_ASM_CONVERGENCE))
static LISP65_C2_MAPPED_FAR_FN
void c2_dma_verify_submit(uint16_t source, uint8_t source_bank) {
    uint8_t *next = c2_dma_verify_list + 12u;
    lisp65_f018_descriptor(c2_dma_verify_list, 4u, source, source_bank,
                           (uint16_t)(uintptr_t)&c2_dma_verify, 0u, 1u);
    lisp65_f018_descriptor(next, 0u,
                           (uint16_t)(uintptr_t)&c2_dma_verify_marker, 0u,
                           (uint16_t)(uintptr_t)&c2_dma_verify_done, 0u, 1u);
    __asm__ volatile(
        "lda #0\n\tsta $d702\n\t"
        "lda #mos16hi(c2_dma_verify_list)\n\tsta $d701\n\t"
        "lda #mos16lo(c2_dma_verify_list)\n\tsta $d700\n\t"
        ::: "a", "memory");
}
#endif

#ifdef LISP65_CODE_WINDOW_CONVERGENCE

#if !defined(__mos__) || !defined(LISP65_C2_ASM_CONVERGENCE)
static LISP65_C2_MAPPED_FAR_FN
uint8_t c2_dma_source_byte(uint8_t bank, uint16_t offset, uint8_t *value) {
    uint16_t start = c2_kernal_frame_count_inline();
    c2_dma_verify_done = (uint8_t)~c2_dma_verify_marker;
    c2_dma_verify_submit(offset, bank);
    while (c2_dma_verify_done != c2_dma_verify_marker) {
        if ((uint16_t)(c2_kernal_frame_count_inline() - start)
            >= C2_DMA_CONTENT_TIMEOUT_FRAMES)
            return 0u;
    }
    *value = c2_dma_verify;
    return 1u;
}
#endif

#ifdef __mos__
#define C2_VM_CODE_LOAD_CONVERGED_IMPL \
    c2_mapped_far_vm_code_load_converged
#else
#define C2_VM_CODE_LOAD_CONVERGED_IMPL vm_code_load_converged
#endif
#if !defined(__mos__) || !defined(LISP65_C2_ASM_CONVERGENCE)
LISP65_C2_MAPPED_FAR_FN
uint8_t C2_VM_CODE_LOAD_CONVERGED_IMPL(
        uint8_t bank, uint16_t offset, uint16_t length,
        uint8_t *destination) {
    volatile uint8_t *observed = (volatile uint8_t *)destination;
    uint8_t expected;
    uint16_t i;
    uint16_t start;
    if (!destination || !length) return 0u;

    /* The chained marker makes the one-byte source probe content-defined;
     * submission return is never treated as source visibility. */
    for (i = 0u; i < length; ++i) {
        if (!c2_dma_source_byte(bank, (uint16_t)(offset + i), &expected))
            return 0u;
        if (observed[i] != expected) break;
    }
    if (i == length) return 1u;

    start = c2_kernal_frame_count_inline();
    vm_code_load(bank, offset, length, destination);
    while (observed[i] != expected) {
        if ((uint16_t)(c2_kernal_frame_count_inline() - start)
            >= C2_DMA_CONTENT_TIMEOUT_FRAMES)
            return 0u;
    }
    return 1u;
}
#endif

#ifdef LISP65_C2_MUTABLE_CPU_READS
static LISP65_C2_MAPPED_FACADE_FN
void c2_dma_read_or_abort(uint8_t bank, uint16_t offset,
                          uint16_t length, uint8_t *destination) {
    uint32_t physical = (uint32_t)offset | ((uint32_t)bank << 16);
    if (c2_map_cpu_read(physical, destination, length)) return;
    lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                      "CPU content read failed; reboot");
}
#else
static LISP65_C2_MAPPED_FACADE_FN
void c2_dma_read_or_abort(uint8_t bank, uint16_t offset,
                          uint16_t length, uint8_t *destination) {
    if (vm_code_load_converged(bank, offset, length, destination)) return;
    lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                      "DMA content did not converge; reboot");
}
#endif
#endif

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
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    c2_dma_read_or_abort(SYMPOOL_EXT_BANK,
                         (uint16_t)(SYMPOOL_EXT_OFF + offset), length,
                         (uint8_t *)destination);
#else
    c2_facade_c2_dma((uint16_t)(SYMPOOL_EXT_OFF + offset), SYMPOOL_EXT_BANK,
                     (uint16_t)(uintptr_t)destination, 0u, length);
#endif
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
#define SYMVAL_EXT_OFF (SYMPOOL_EXT_OFF + NAMEPOOL + 0UL)
#endif
obj symval_get(uint16_t index) {
    uint16_t value;
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    c2_dma_read_or_abort(SYMVAL_EXT_BANK,
                         (uint16_t)(SYMVAL_EXT_OFF + index * 2u), 2u,
                         (uint8_t *)&value);
#else
    c2_facade_c2_dma((uint16_t)(SYMVAL_EXT_OFF + index * 2u),
                     SYMVAL_EXT_BANK, (uint16_t)(uintptr_t)&value, 0u, 2u);
#endif
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
#define NAMEOFF_EXT_OFF (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 2UL)
#endif
uint16_t nameoff_get(uint16_t index) {
    uint16_t value;
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    c2_dma_read_or_abort(NAMEOFF_EXT_BANK,
                         (uint16_t)(NAMEOFF_EXT_OFF + index * 2u), 2u,
                         (uint8_t *)&value);
#else
    c2_facade_c2_dma((uint16_t)(NAMEOFF_EXT_OFF + index * 2u),
                     NAMEOFF_EXT_BANK, (uint16_t)(uintptr_t)&value, 0u, 2u);
#endif
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
#define SYMFN_EXT_OFF (NAMEOFF_EXT_OFF + MAX_SYM * 2UL)
#elif defined(LISP65_SYMVAL_EXT)
#define SYMFN_EXT_OFF (SYMVAL_EXT_OFF + MAX_SYM * 2UL)
#else
#define SYMFN_EXT_OFF (SYMPOOL_EXT_OFF + NAMEPOOL + 0UL)
#endif
#endif

/* Every owner is checked in its actual bank. Moving a whole table through
 * the existing DMA seam must neither wrap an offset nor overlap another
 * table; the composed linker map additionally protects non-symbol owners. */
#define C2_SYM_FITS(bank, off, bytes) \
    _Static_assert((bank) <= 15u && (off) <= 65536UL \
        && (bytes) <= 65536UL - (off), "C2 symbol owner exceeds bank")
#define C2_SYM_DISJOINT(ab, ao, an, bb, bo, bn) \
    _Static_assert((ab) != (bb) || (ao) + (an) <= (bo) \
        || (bo) + (bn) <= (ao), "C2 symbol owners overlap")
C2_SYM_FITS(SYMPOOL_EXT_BANK, SYMPOOL_EXT_OFF, NAMEPOOL);
C2_SYM_FITS(SYMFN_EXT_BANK, SYMFN_EXT_OFF, MAX_SYM * 2UL);
C2_SYM_DISJOINT(SYMPOOL_EXT_BANK, SYMPOOL_EXT_OFF, NAMEPOOL,
                SYMFN_EXT_BANK, SYMFN_EXT_OFF, MAX_SYM * 2UL);
#ifdef LISP65_SYMVAL_EXT
C2_SYM_FITS(SYMVAL_EXT_BANK, SYMVAL_EXT_OFF, MAX_SYM * 2UL);
C2_SYM_DISJOINT(SYMPOOL_EXT_BANK, SYMPOOL_EXT_OFF, NAMEPOOL,
                SYMVAL_EXT_BANK, SYMVAL_EXT_OFF, MAX_SYM * 2UL);
C2_SYM_DISJOINT(SYMVAL_EXT_BANK, SYMVAL_EXT_OFF, MAX_SYM * 2UL,
                SYMFN_EXT_BANK, SYMFN_EXT_OFF, MAX_SYM * 2UL);
#endif
#ifdef LISP65_NAMEOFF_EXT
C2_SYM_FITS(NAMEOFF_EXT_BANK, NAMEOFF_EXT_OFF, MAX_SYM * 2UL);
C2_SYM_DISJOINT(SYMPOOL_EXT_BANK, SYMPOOL_EXT_OFF, NAMEPOOL,
                NAMEOFF_EXT_BANK, NAMEOFF_EXT_OFF, MAX_SYM * 2UL);
C2_SYM_DISJOINT(NAMEOFF_EXT_BANK, NAMEOFF_EXT_OFF, MAX_SYM * 2UL,
                SYMFN_EXT_BANK, SYMFN_EXT_OFF, MAX_SYM * 2UL);
#ifdef LISP65_SYMVAL_EXT
C2_SYM_DISJOINT(SYMVAL_EXT_BANK, SYMVAL_EXT_OFF, MAX_SYM * 2UL,
                NAMEOFF_EXT_BANK, NAMEOFF_EXT_OFF, MAX_SYM * 2UL);
#endif
#endif
#undef C2_SYM_DISJOINT
#undef C2_SYM_FITS

#if defined(LISP65_CODE_WINDOW_CONVERGENCE) && defined(LISP65_C2_MUTABLE_CPU_READS)
/* Keep the function-cell bank out of the shared mutable-read ABI.  All
 * other symbol pools share Bank 5; making their bank an argument solely
 * for this table prevents constant specialization on every GC value read.
 * The same CPU-read/error contract still applies to both banks. */
static LISP65_C2_MAPPED_FACADE_FN
void c2_symfn_read_or_abort(uint16_t offset, uint8_t *destination) {
    uint32_t physical = (uint32_t)offset | ((uint32_t)SYMFN_EXT_BANK << 16);
    if (c2_map_cpu_read(physical, destination, 2u)) return;
    lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                      "CPU content read failed; reboot");
}
#endif

obj symfn_ext_get(uint16_t index) {
    uint16_t value;
#if defined(LISP65_CODE_WINDOW_CONVERGENCE) && defined(LISP65_C2_MUTABLE_CPU_READS)
    c2_symfn_read_or_abort((uint16_t)(SYMFN_EXT_OFF + index * 2u),
                           (uint8_t *)&value);
#elif defined(LISP65_CODE_WINDOW_CONVERGENCE)
    c2_dma_read_or_abort(SYMFN_EXT_BANK,
                         (uint16_t)(SYMFN_EXT_OFF + index * 2u), 2u,
                         (uint8_t *)&value);
#else
    c2_facade_c2_dma((uint16_t)(SYMFN_EXT_OFF + index * 2u),
                     SYMFN_EXT_BANK, (uint16_t)(uintptr_t)&value, 0u, 2u);
#endif
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
