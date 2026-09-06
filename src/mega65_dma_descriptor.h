/* Canonical MEGA65 DMA descriptor builders.
 *
 * Submission stays at each resource owner's call site: the inline assembly
 * names owner-specific storage and carries the required "memory" clobber.
 * Only the byte contract is shared here, so F018/EDMA layouts cannot drift.
 */
#ifndef LISP65_MEGA65_DMA_DESCRIPTOR_H
#define LISP65_MEGA65_DMA_DESCRIPTOR_H

#include <stdint.h>

static __attribute__((always_inline)) inline void
lisp65_f018_descriptor(uint8_t job[12], uint8_t command,
                       uint16_t source, uint8_t source_bank,
                       uint16_t target, uint8_t target_bank,
                       uint16_t length) {
    job[0] = command;
    job[1] = (uint8_t)length;
    job[2] = (uint8_t)(length >> 8);
    job[3] = (uint8_t)source;
    job[4] = (uint8_t)(source >> 8);
    job[5] = source_bank;
    job[6] = (uint8_t)target;
    job[7] = (uint8_t)(target >> 8);
    job[8] = target_bank;
    job[9] = 0u;
    job[10] = 0u;
    job[11] = 0u;
}

static __attribute__((always_inline)) inline void
lisp65_edma_tuple_descriptor(uint8_t job[20], uint8_t command,
                             uint16_t source_low,
                             uint16_t source_megabyte_bank,
                             uint32_t target, uint16_t length) {
    job[0] = 0x0bu;
    job[1] = 0x80u;
    job[2] = (uint8_t)(source_megabyte_bank >> 8);
    job[3] = 0x81u;
    job[4] = (uint8_t)(target >> 20);
    job[5] = 0x85u;
    job[6] = 1u;
    job[7] = 0u;
    job[8] = command;
    job[9] = (uint8_t)length;
    job[10] = (uint8_t)(length >> 8);
    job[11] = (uint8_t)source_low;
    job[12] = (uint8_t)(source_low >> 8);
    job[13] = (uint8_t)source_megabyte_bank;
    job[14] = (uint8_t)target;
    job[15] = (uint8_t)(target >> 8);
    job[16] = (uint8_t)((target >> 16) & 0x0fu);
    job[17] = 0u;
    job[18] = 0u;
    job[19] = 0u;
}

static __attribute__((always_inline)) inline void
lisp65_edma_descriptor(uint8_t job[20], uint8_t command,
                       uint32_t source, uint32_t target,
                       uint16_t length) {
    uint16_t source_megabyte_bank =
        (uint16_t)(((source >> 16) & 0x0fu) | ((source >> 12) & 0xff00u));
    lisp65_edma_tuple_descriptor(job, command, (uint16_t)source,
                                 source_megabyte_bank, target, length);
}

static __attribute__((always_inline)) inline void
lisp65_edma_fill_descriptor(uint8_t job[20], uint8_t command,
                            uint8_t value, uint32_t target,
                            uint16_t length) {
    lisp65_edma_descriptor(job, command, (uint32_t)value, target, length);
    job[2] = 0u;
    job[11] = value;
    job[12] = 0u;
    job[13] = 0u;
}

#endif /* LISP65_MEGA65_DMA_DESCRIPTOR_H */
