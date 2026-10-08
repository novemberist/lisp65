/* Single C2D-v6 execution-entry emitter shared by host and target.
 *
 * This header is deliberately portable C: the host product builder and the
 * target append slice compile this exact routine.  No consumer may reconstruct
 * the ten-byte row independently.
 */
#ifndef LISP65_C2D_V6_ENTRY_H
#define LISP65_C2D_V6_ENTRY_H

#include <stdint.h>

#define LISP65_C2D_V6_ENTRY_BYTES 10u
#define LISP65_C2D_V6_IMAGE_CAP 64u
#define LISP65_C2D_V6_RESOLUTION_CAP 4096u

static inline uint8_t c2d_v6_emit_entry_row(
        uint8_t out[LISP65_C2D_V6_ENTRY_BYTES],
        uint8_t image_slot, uint8_t literal_count,
        uint16_t code_offset, uint16_t code_length,
        uint16_t resolution_base, uint16_t generation) {
    uint32_t code_end = (uint32_t)code_offset + code_length;
    uint32_t resolution_end = (uint32_t)resolution_base + literal_count;
    if (!out || image_slot >= LISP65_C2D_V6_IMAGE_CAP || !code_length
        || code_end > 65536UL
        || resolution_end > LISP65_C2D_V6_RESOLUTION_CAP || !generation)
        return 0u;
    out[0] = image_slot;
    out[1] = literal_count;
    out[2] = (uint8_t)code_offset;
    out[3] = (uint8_t)(code_offset >> 8);
    out[4] = (uint8_t)code_length;
    out[5] = (uint8_t)(code_length >> 8);
    out[6] = (uint8_t)resolution_base;
    out[7] = (uint8_t)(resolution_base >> 8);
    out[8] = (uint8_t)generation;
    out[9] = (uint8_t)(generation >> 8);
    return 1u;
}

#endif
