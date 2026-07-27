#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "c2-stream-decoder.h"

static uint8_t *shelf_data, *c2d_data;
static uint32_t shelf_length;
static uint16_t c2d_length, next_name = 0x0100u, next_pair = 0x4000u;
static uint16_t name_requests, string_values, symbol_values, pair_values;
static struct {
    uint32_t offset;
    uint16_t length;
    uint16_t value;
} symbols[979];

static uint8_t *read_file(const char *path, uint32_t *length) {
    FILE *f = fopen(path, "rb"); long n; uint8_t *p;
    if (!f || fseek(f, 0, SEEK_END) || (n = ftell(f)) < 0 || fseek(f, 0, SEEK_SET)) return 0;
    p = (uint8_t *)malloc((size_t)n ? (size_t)n : 1u);
    if (!p || fread(p, 1, (size_t)n, f) != (size_t)n || fclose(f)) { free(p); return 0; }
    *length = (uint32_t)n; return p;
}

uint8_t c2_stream_shelf_read(uint32_t offset, void *dst, uint16_t length) {
    if (offset > shelf_length || length > shelf_length - offset) return 0;
    memcpy(dst, shelf_data + offset, length); return 1;
}
uint8_t c2_stream_c2d_read(uint16_t offset, void *dst, uint16_t length) {
    if (offset > c2d_length || length > (uint16_t)(c2d_length - offset)) return 0;
    memcpy(dst, c2d_data + offset, length); return 1;
}
uint8_t c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length) {
    if (offset > c2d_length || length > (uint16_t)(c2d_length - offset)) return 0;
    memcpy(c2d_data + offset, src, length); return 1;
}
uint8_t c2_stream_name_value(uint8_t kind, uint32_t offset,
                             uint16_t length, uint16_t *value) {
    uint16_t i;
    if (kind != 3u && kind != 5u && kind != 8u) return 0;
    if (offset > shelf_length || length > shelf_length - offset) return 0;
    if (!length && kind != 3u) return 0;
    ++name_requests;
    if (kind == 3u) {
        *value = next_name++; ++string_values; return *value != 0;
    }
    for (i = 0; i < symbol_values; ++i) {
        if (symbols[i].length == length
            && !memcmp(shelf_data + symbols[i].offset, shelf_data + offset, length)) {
            *value = symbols[i].value; return 1;
        }
    }
    if (symbol_values >= sizeof(symbols) / sizeof(symbols[0])) return 0;
    *value = next_name++;
    symbols[symbol_values].offset = offset;
    symbols[symbol_values].length = length;
    symbols[symbol_values].value = *value;
    ++symbol_values;
    return *value != 0;
}
uint8_t c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value) {
    (void)car; (void)cdr; *value = next_pair++; ++pair_values; return *value != 0;
}

int main(int argc, char **argv) {
    c2_stream_context context; uint32_t raw_c2d, at; uint8_t status;
    uint8_t (*const phases[])(void *) = {
        c2_stream_phase_00, c2_stream_phase_01, c2_stream_phase_02,
        c2_stream_phase_03, c2_stream_phase_04, c2_stream_phase_05,
        c2_stream_phase_06, c2_stream_phase_07, c2_stream_phase_08,
        c2_stream_phase_09
    };
    if (argc != 3) return 90;
    shelf_data = read_file(argv[1], &shelf_length);
    c2d_data = read_file(argv[2], &raw_c2d);
    if (!shelf_data || !c2d_data || raw_c2d > 0xffffu) return 91;
    c2d_length = (uint16_t)raw_c2d;
    /* Resolution objects are session state, never immutable emitter tokens. */
    at = (uint32_t)c2d_data[22] | (uint32_t)c2d_data[23] << 8;
    if (at > c2d_length) return 92;
    memset(c2d_data + at, 0, c2d_length - (uint16_t)at);
    c2_stream_init(&context, shelf_length, c2d_length);
    for (at = 0; at < sizeof(phases) / sizeof(phases[0]); ++at) {
        status = phases[at](&context);
        if (status != C2_STREAM_OK) {
            fprintf(stderr, "c2-stream: FAIL phase=%lu status=%u\n",
                    (unsigned long)at, status);
            return status;
        }
    }
    if (!context.finished || context.phase != 10u
        || context.image_count != 6u || context.entry_count != 583u
        || context.resolution_count != 2249u || context.resolution_cursor != 2249u
        || pair_values != 168u || name_requests != 1095u
        || string_values != 116u || symbol_values != 344u)
        return 93;
    printf("c2-stream: PASS shelf=%lu images=%u entries=%u descriptors=%u "
           "names=%u strings=%u unique-symbols=%u pairs=%u context=%lu\n",
           (unsigned long)shelf_length, context.image_count, context.entry_count,
           context.resolution_count, name_requests, string_values, symbol_values, pair_values,
           (unsigned long)sizeof(context));
    free(shelf_data); free(c2d_data); return 0;
}
