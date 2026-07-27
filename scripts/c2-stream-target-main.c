/* Link-only target harness. Full-composition execution is performed by the host harness. */
#include <stdint.h>
#include "c2-stream-decoder.h"

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
c2_stream_name_value(uint8_t kind, uint32_t offset,
                             uint16_t length, uint16_t *value) {
    (void)kind; (void)offset; (void)length; *value = token++; return 1;
}
__attribute__((noinline)) uint8_t
c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value) {
    (void)car; (void)cdr; *value = token++; return 1;
}

volatile uint8_t c2_stream_target_sink;
int main(void) {
    c2_stream_context context;
    c2_stream_init(&context, sizeof(shelf), sizeof(c2d));
    /* Retain every independently packed phase in the target link. */
    c2_stream_target_sink = (uint8_t)(
        (uintptr_t)c2_stream_phase_00 ^ (uintptr_t)c2_stream_phase_01
        ^ (uintptr_t)c2_stream_phase_02 ^ (uintptr_t)c2_stream_phase_03
        ^ (uintptr_t)c2_stream_phase_04 ^ (uintptr_t)c2_stream_phase_05);
    c2_stream_target_sink ^= (uint8_t)(
        (uintptr_t)c2_stream_phase_06 ^ (uintptr_t)c2_stream_phase_07
        ^ (uintptr_t)c2_stream_phase_08 ^ (uintptr_t)c2_stream_phase_09);
    return c2_stream_target_sink == 0xffu;
}
