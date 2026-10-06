/* Mutually exclusive resident work area for the C2 emitter/append pipeline.
 *
 * The emitter owns the area until the final C2I commit marker is written.
 * Append may acquire it only after that cutpoint.  Acquisition is deliberately
 * non-reentrant: an accidental overlap fails closed instead of aliasing two
 * live state machines onto the same bytes.
 */
#ifndef LISP65_C2_PHASE_SCRATCH_H
#define LISP65_C2_PHASE_SCRATCH_H

#include <stdint.h>

#define LISP65_C2_PHASE_SCRATCH_BYTES 304u

/* Non-promotable top-level frame attribution.  The 15 result bytes occupy the
 * append-lifetime-dead tail immediately before the permanent two-byte
 * installer trace.  The first stamp is deliberately written only after the
 * emitter's final state read; it may overlap the then-dead emitter object but
 * survives because the following append object ends below this span.  Each
 * phase samples only the low byte of the product-owned frame clock.  A
 * diagnostic receipt is admissible only when the complete measured expression
 * is shorter than 256 frames, so consecutive deltas are exact modulo 256
 * without a resident high-byte read.
 */
#ifdef LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC
#include "c2_kernal_runtime.h"
#define LISP65_C2_FRAME_ATTRIBUTION_OFFSET 287u
#define LISP65_C2_FRAME_ATTRIBUTION_BYTES 15u
enum {
    LISP65_C2_FRAME_ATTR_EMIT_FINAL_CRC = 0u,
    LISP65_C2_FRAME_ATTR_APPEND_ENVELOPE = 1u,
    LISP65_C2_FRAME_ATTR_RESERVE_TRANSIENT_BOUNDS = 2u,
    LISP65_C2_FRAME_ATTR_STAGE_COPY = 3u,
    LISP65_C2_FRAME_ATTR_STAGE_PLANE = 4u,
    LISP65_C2_FRAME_ATTR_DECODE_04 = 5u,
    LISP65_C2_FRAME_ATTR_DECODE_06A = 6u,
    LISP65_C2_FRAME_ATTR_DECODE_09 = 7u,
    LISP65_C2_FRAME_ATTR_DECODE_12 = 8u,
    LISP65_C2_FRAME_ATTR_APPEND_HEADER = 9u,
    LISP65_C2_FRAME_ATTR_INNER_VM = 10u,
    LISP65_C2_FRAME_ATTR_ROLLBACK_PREPARE = 11u,
    LISP65_C2_FRAME_ATTR_ROLLBACK_UNPUBLISH = 12u,
    LISP65_C2_FRAME_ATTR_ROLLBACK_FINALIZE = 13u,
    LISP65_C2_FRAME_ATTR_JOURNAL_CLEAR = 14u
};
#define C2_FRAME_ATTRIBUTION_STAMP(index) do { \
    ((volatile uint8_t *)lisp65_c2_phase_scratch) \
        [LISP65_C2_FRAME_ATTRIBUTION_OFFSET + (uint8_t)(index)] = \
            *(volatile const uint8_t *)(uintptr_t)LISP65_C2_FRAME_LO_ADDRESS; \
} while (0)
#else
#define C2_FRAME_ATTRIBUTION_STAMP(index) ((void)0)
#endif

/* The last two bytes are lifetime-exclusive diagnostic provenance.  Every
 * cold overlay entry writes its own Session-family slot to LAST_SLOT until a
 * cleanup boundary freezes that primary witness.  The second byte holds two
 * orthogonal flags: INNER_ENTERED records the sole resident transition into
 * vm_run_dir; PRIMARY_LOCKED makes all dual-use cleanup-phase stamps no-ops.
 * Thus the first failing phase survives a completed unwind while C2J remains
 * the authority for what cleanup subsequently did. */
#define LISP65_C2_INSTALL_TRACE_BYTES 2u
#define LISP65_C2_INSTALL_TRACE_OFFSET \
    (LISP65_C2_PHASE_SCRATCH_BYTES - LISP65_C2_INSTALL_TRACE_BYTES)
#ifdef LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC
_Static_assert(LISP65_C2_FRAME_ATTRIBUTION_OFFSET
                   + LISP65_C2_FRAME_ATTRIBUTION_BYTES
               == LISP65_C2_INSTALL_TRACE_OFFSET,
               "frame attribution must end exactly before installer trace");
#endif
#define LISP65_C2_INSTALL_LAST_SLOT_OFFSET LISP65_C2_INSTALL_TRACE_OFFSET
#define LISP65_C2_INSTALL_INNER_ENTERED_OFFSET \
    (LISP65_C2_INSTALL_TRACE_OFFSET + 1u)
#define LISP65_C2_INSTALL_INNER_NOT_ENTERED 0u
#define LISP65_C2_INSTALL_INNER_ENTERED 1u
#define LISP65_C2_INSTALL_PRIMARY_UNLOCKED 0u
#define LISP65_C2_INSTALL_PRIMARY_LOCKED 128u

enum {
    LISP65_C2_PHASE_OWNER_NONE = 0u,
    LISP65_C2_PHASE_OWNER_EMITTER = 1u,
    LISP65_C2_PHASE_OWNER_APPEND = 2u
};

extern uint8_t lisp65_c2_phase_scratch[LISP65_C2_PHASE_SCRATCH_BYTES];

uint8_t c2_phase_scratch_acquire(uint8_t owner);
uint8_t c2_phase_scratch_release(uint8_t owner);

/* Volatile is intentional: the trace has no product reader.  It is an
 * externally captured witness and must survive whole-program dead-store
 * elimination.  These expand at the caller, so a cold phase pays its own
 * immediate store and creates no resident helper or call edge. */
#define C2_INSTALL_TRACE_STAMP_SLOT(slot) do { \
    ((volatile uint8_t *)lisp65_c2_phase_scratch) \
        [LISP65_C2_INSTALL_LAST_SLOT_OFFSET] = (uint8_t)(slot); \
} while (0)
#define C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(slot) do { \
    volatile uint8_t *c2_trace__ = \
        (volatile uint8_t *)lisp65_c2_phase_scratch; \
    if (!(c2_trace__[LISP65_C2_INSTALL_INNER_ENTERED_OFFSET] \
            & LISP65_C2_INSTALL_PRIMARY_LOCKED)) \
        c2_trace__[LISP65_C2_INSTALL_LAST_SLOT_OFFSET] = (uint8_t)(slot); \
} while (0)
#define C2_INSTALL_TRACE_RESET_INNER() do { \
    ((volatile uint8_t *)lisp65_c2_phase_scratch) \
        [LISP65_C2_INSTALL_INNER_ENTERED_OFFSET] = \
            LISP65_C2_INSTALL_INNER_NOT_ENTERED; \
} while (0)
#define C2_INSTALL_TRACE_LOCK_PRIMARY() do { \
    ((volatile uint8_t *)lisp65_c2_phase_scratch) \
        [LISP65_C2_INSTALL_INNER_ENTERED_OFFSET] |= \
            LISP65_C2_INSTALL_PRIMARY_LOCKED; \
} while (0)
#define C2_INSTALL_TRACE_ENTER_INNER() do { \
    ((volatile uint8_t *)lisp65_c2_phase_scratch) \
        [LISP65_C2_INSTALL_INNER_ENTERED_OFFSET] = \
            (LISP65_C2_INSTALL_PRIMARY_LOCKED \
             | LISP65_C2_INSTALL_INNER_ENTERED); \
} while (0)
static inline void *c2_phase_scratch_pointer(void) {
    return lisp65_c2_phase_scratch;
}

#endif
