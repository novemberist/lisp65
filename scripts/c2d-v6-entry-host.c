/* Host ABI wrapper around the target's single C2D-v6 entry-row emitter. */
#include <stdint.h>
#include "c2d_v6_entry.h"

uint8_t lisp65_c2d_v6_emit_entry_row(
        uint8_t out[LISP65_C2D_V6_ENTRY_BYTES],
        uint8_t image_slot, uint8_t literal_count,
        uint16_t code_offset, uint16_t code_length,
        uint16_t resolution_base, uint16_t generation) {
    return c2d_v6_emit_entry_row(out, image_slot, literal_count,
                                 code_offset, code_length,
                                 resolution_base, generation);
}
