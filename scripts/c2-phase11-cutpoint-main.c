#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "c2-stream-v2-decoder.h"

uint8_t c2_stream_shelf_read(uint32_t offset, void *dst, uint16_t length) {
    (void)offset; (void)dst; (void)length; return 0;
}
uint8_t c2_stream_c2d_read(uint16_t offset, void *dst, uint16_t length) {
    (void)offset; (void)dst; (void)length; return 0;
}
uint8_t c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length) {
    (void)offset; (void)src; (void)length; return 0;
}
uint8_t c2_stream_name_value(uint8_t kind, uint32_t offset,
                             uint16_t length, uint16_t *value) {
    (void)kind; (void)offset; (void)length; (void)value; return 0;
}
uint8_t c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value) {
    (void)car; (void)cdr; (void)value; return 0;
}
uint8_t c2_stream_gc_checkpoint(uint16_t roots_offset, uint16_t root_count) {
    (void)roots_offset; (void)root_count; return 0;
}

static void phase11(c2_stream_context *context) {
    memset(context, 0, sizeof(*context));
    context->phase = 11u;
}

int main(void) {
    c2_stream_context context;
    phase11(&context);
    if (c2_stream_phase_11b(&context) != C2_STREAM_ERR_STATE) return 1;
    if (c2_stream_phase_11a(&context) != C2_STREAM_OK
        || context.reserved != 0x11u || context.phase != 11u) return 2;
    if (c2_stream_phase_11a(&context) != C2_STREAM_ERR_STATE) return 3;
    context.reserved = 0x10u;
    if (c2_stream_phase_11b(&context) != C2_STREAM_ERR_STATE) return 4;
    context.reserved = 0x11u;
    if (c2_stream_phase_11b(&context) != C2_STREAM_OK
        || context.reserved || context.phase != 12u) return 5;
    phase11(&context); context.error = C2_STREAM_ERR_IO;
    if (c2_stream_phase_11a(&context) != C2_STREAM_ERR_STATE) return 6;
    puts("c2-phase11-cutpoint: PASS negatives=4 added-handoff-bytes=0");
    return 0;
}
