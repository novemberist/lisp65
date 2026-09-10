#include <stdint.h>
#include "c2-stream-decoder.h"

void c2_stream_init(c2_stream_context *c, uint32_t shelf_bytes,
                    uint16_t c2d_bytes) {
    uint8_t *p = (uint8_t *)c; uint16_t i;
    for (i = 0; i < sizeof(*c); ++i) p[i] = 0;
    c->shelf_bytes = shelf_bytes; c->c2d_bytes = c2d_bytes;
}
