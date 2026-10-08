/* Non-promotable C1 Freezer cutpoint carrier.
 *
 * The product profile never defines LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE.
 * A dedicated hardware-fixture build uses two bytes in the profile-bound
 * $17a0..$17ff gap between the 80x50 screen and the resident Island:
 *
 *   $17e0  requested cutpoint (host writes, host clears after thaw)
 *   $17e1  reached cutpoint (fixture writes, host reads)
 *
 * Every hold is paid by the cold overlay that owns the state transition.  It
 * adds no resident cell, no GC root and no product byte.  The tight loop
 * reloads the command byte from memory on every iteration.  No CPU register
 * is assumed to survive an IRQ or Freezer roundtrip.
 */
#ifndef LISP65_C2_C1_FREEZER_FIXTURE_H
#define LISP65_C2_C1_FREEZER_FIXTURE_H

#include <stdint.h>

#define LISP65_C2_C1_FREEZER_COMMAND_ADDRESS 0x17e0u
#define LISP65_C2_C1_FREEZER_REACHED_ADDRESS 0x17e1u
#define LISP65_C2_C1_COMPLETION_STAGE_ADDRESS 0x17e2u
#define LISP65_C2_C1_COMPLETION_MODE_ADDRESS 0x17e3u
#define LISP65_C2_C1_COMPLETION_READER_ADDRESS 0x17e4u
#define LISP65_C2_C1_COMPLETION_ATTEMPTS_ADDRESS 0x17e5u
#define LISP65_C2_C1_COMPLETION_OBSERVED_CRC_ADDRESS 0x17e6u
#define LISP65_C2_C1_COMPLETION_EXPECTED_CRC_ADDRESS 0x17e8u
#define LISP65_C2_C1_COMPLETION_FRAME_START_ADDRESS 0x17eau
#define LISP65_C2_C1_COMPLETION_FRAME_END_ADDRESS 0x17ecu

#define LISP65_C2_C1_FREEZER_JOURNAL_WRITTEN 1u
#define LISP65_C2_C1_FREEZER_STAGED_BEFORE_HEADER 2u
#define LISP65_C2_C1_FREEZER_HEADER_BEFORE_EXPORTS 3u
#define LISP65_C2_C1_FREEZER_ABORT_UNPUBLISH 4u

#ifdef LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE
/*
 * Numeric local labels are scoped by the assembler and allow the same exact
 * sequence in different overlay sections.  A is listed as clobbered so the C
 * continuation never inherits fixture state.
 */
#define C2_C1_FREEZER_HOLD(id) do { \
    __asm__ volatile( \
        "lda $17e0\n\t" \
        "cmp #" #id "\n\t" \
        "bne 2f\n\t" \
        "sta $17e1\n\t" \
        "1:\n\t" \
        "lda $17e0\n\t" \
        "cmp #" #id "\n\t" \
        "beq 1b\n\t" \
        "2:\n\t" \
        : : : "a", "memory"); \
} while (0)
/*
 * The rollback/unpublish slice has only fifteen bytes below its existing pack
 * quantum.  Its exact hold state is already externally distinguishable:
 * command 4 remains armed while the old header and exports are restored and
 * C2J remains ACTIVE.  It therefore needs no duplicate reached-byte store.
 * Like the ordinary form, it reloads the command byte on every iteration.
 */
#define C2_C1_FREEZER_HOLD_STATE_PROVEN(id) do { \
    __asm__ volatile( \
        "1:\n\t" \
        "lda $17e0\n\t" \
        "cmp #" #id "\n\t" \
        "beq 1b\n\t" \
        : : : "a", "memory"); \
} while (0)
#define C2_C1_FREEZER_ABORT_REQUESTED() \
    (*(volatile const uint8_t *)(uintptr_t) \
        LISP65_C2_C1_FREEZER_COMMAND_ADDRESS \
     == LISP65_C2_C1_FREEZER_ABORT_UNPUBLISH)
#define C2_C1_COMPLETION_WITNESS8(address, value) do { \
    *(volatile uint8_t *)(uintptr_t)(address) = (uint8_t)(value); \
} while (0)
#define C2_C1_COMPLETION_WITNESS16(address, value) do { \
    uint16_t c2_c1_witness_value = (uint16_t)(value); \
    C2_C1_COMPLETION_WITNESS8((address), c2_c1_witness_value); \
    C2_C1_COMPLETION_WITNESS8( \
        (uint16_t)((address) + 1u), c2_c1_witness_value >> 8); \
} while (0)
#define C2_C1_COMPLETION_WITNESS_INC(address) do { \
    ++*(volatile uint8_t *)(uintptr_t)(address); \
} while (0)
#else
#define C2_C1_FREEZER_HOLD(id) ((void)0)
#define C2_C1_FREEZER_HOLD_STATE_PROVEN(id) ((void)0)
#define C2_C1_FREEZER_ABORT_REQUESTED() 0
#define C2_C1_COMPLETION_WITNESS8(address, value) ((void)0)
#define C2_C1_COMPLETION_WITNESS16(address, value) ((void)0)
#define C2_C1_COMPLETION_WITNESS_INC(address) ((void)0)
#endif

#endif
