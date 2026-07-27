/* Link-only C2D-v2 target harness. */
#include <stdint.h>
#include "c2-stream-v2-decoder.h"

static volatile uint8_t shelf[256], c2d[256];
static uint16_t token = 0x100u;

__attribute__((noinline)) uint8_t
c2_stream_shelf_read(uint32_t offset, void *dst, uint16_t length) {
    uint8_t *out = dst; uint16_t i;
    if (offset + length > sizeof(shelf)) return 0;
    for (i = 0; i < length; ++i) out[i] = shelf[(uint16_t)offset + i];
    return 1;
}
__attribute__((noinline)) uint8_t
c2_stream_c2d_read(uint16_t offset, void *dst, uint16_t length) {
    uint8_t *out = dst; uint16_t i;
    if ((uint16_t)(offset + length) > sizeof(c2d)) return 0;
    for (i = 0; i < length; ++i) out[i] = c2d[offset + i];
    return 1;
}
__attribute__((noinline)) uint8_t
c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length) {
    const uint8_t *in = src; uint16_t i;
    if ((uint16_t)(offset + length) > sizeof(c2d)) return 0;
    for (i = 0; i < length; ++i) c2d[offset + i] = in[i];
    return 1;
}
__attribute__((noinline)) uint8_t
c2_stream_name_value(uint8_t kind, uint32_t offset, uint16_t length, uint16_t *value) {
    (void)kind; (void)offset; (void)length; *value = token; token += 2u; return 1;
}
__attribute__((noinline)) uint8_t
c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value) {
    (void)car; (void)cdr; *value = token; token += 2u; return 1;
}
__attribute__((noinline)) uint8_t
c2_stream_gc_checkpoint(uint16_t roots_offset, uint16_t root_count) {
    return roots_offset != 0u && root_count != 0u;
}

volatile uint8_t c2_stream_target_sink;
int main(void) {
    c2_stream_context context; uint16_t hot[23]; uint8_t count;
    c2_stream_init(&context, sizeof(shelf), sizeof(c2d));
    c2_stream_target_sink = (uint8_t)(
        (uintptr_t)c2_stream_phase_00 ^ (uintptr_t)c2_stream_phase_01
        ^ (uintptr_t)c2_stream_phase_02 ^ (uintptr_t)c2_stream_phase_03
        ^ (uintptr_t)c2_stream_phase_04 ^ (uintptr_t)c2_stream_phase_05);
    c2_stream_target_sink ^= (uint8_t)(
        (uintptr_t)c2_stream_phase_06 ^ (uintptr_t)c2_stream_phase_07
        ^ (uintptr_t)c2_stream_phase_08 ^ (uintptr_t)c2_stream_phase_09
        ^ (uintptr_t)c2_stream_phase_10 ^ (uintptr_t)c2_stream_phase_11
        ^ (uintptr_t)c2_stream_phase_12
        ^ (uintptr_t)c2_stream_materialize_entry);
    c2_stream_target_sink ^= c2_stream_materialize_entry(&context, 0, hot, 23, &count);
    return c2_stream_target_sink == 0xffu;
}
