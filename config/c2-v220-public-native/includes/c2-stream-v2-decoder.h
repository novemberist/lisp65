#ifndef LISP65_C2_STREAM_V2_DECODER_H
#define LISP65_C2_STREAM_V2_DECODER_H

#include "c2-stream-decoder.h"

/*
 * C2D-v2 preserves the proven 36-byte transport context.  The two v1 fields
 * below were never consumed by phases 1--6; v2 gives them one precise meaning
 * without moving any field used by those unchanged validation phases.
 */
#ifndef C2_STREAM_PRODUCT_V3
#define c2_root_count image_cursor
#define c2_root_cursor pair_depth_max
#endif

/*
 * Called after a newly allocated heap object has been published in its sole
 * canonical root slot and before any later allocation.  Product integration
 * binds this seam to a non-moving collection; the proof harness collects at
 * every call and rejects writeback or loss of an earlier root.
 */
uint8_t c2_stream_gc_checkpoint(uint16_t roots_offset, uint16_t root_count);

/* Build the ordinary Bank-0 hot literal table for one directory entry. */
uint8_t c2_stream_materialize_entry(c2_stream_context *context,
                                    uint16_t directory_ordinal,
                                    uint16_t *hot_values,
                                    uint8_t hot_capacity,
                                    uint8_t *hot_count);

#ifdef C2_STREAM_PRODUCT_V3
/* Runtime-overlay ABI wrapper for the proven materializer.  Product code may
 * not call an LMA symbol directly: slot transport copies this phase to the
 * runtime VMA, then invokes the one-argument entry below. */
typedef struct {
    c2_stream_context *stream;
    uint16_t directory_ordinal;
    uint16_t *hot_values;
    uint8_t hot_capacity;
    uint8_t hot_count;
} c2_stream_materialize_context;
uint8_t c2_stream_phase_13(void *context);
#endif

uint8_t c2_stream_phase_10(void *context);
uint8_t c2_stream_phase_11(void *context);
uint8_t c2_stream_phase_11a(void *context);
uint8_t c2_stream_phase_11b(void *context);
uint8_t c2_stream_phase_12(void *context);

#endif
