#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "c2-stream-v2-decoder.h"
#include "obj.h"

#ifndef EXPECTED_IMAGES
#define EXPECTED_IMAGES 6u
#endif
#ifndef EXPECTED_ENTRIES
#define EXPECTED_ENTRIES 583u
#endif
#ifndef EXPECTED_RESOLUTIONS
#define EXPECTED_RESOLUTIONS 2249u
#endif
#ifndef EXPECTED_ROOTS
#define EXPECTED_ROOTS 284u
#endif
#ifndef EXPECTED_PAIRS
#define EXPECTED_PAIRS 168u
#endif
#ifndef EXPECTED_NAME_REQUESTS
#define EXPECTED_NAME_REQUESTS 1095u
#endif
#ifndef EXPECTED_STRINGS
#define EXPECTED_STRINGS 116u
#endif
#ifndef EXPECTED_SYMBOLS
#define EXPECTED_SYMBOLS 344u
#endif
#ifndef EXPECTED_MAX_LITERALS
#define EXPECTED_MAX_LITERALS 23u
#endif

static uint8_t *shelf_data, *c2d_data;
static uint32_t shelf_length;
static uint16_t c2d_length, next_heap = 0x0100u, next_symbol = 0x4000u;
static uint16_t name_requests, string_values, symbol_values, pair_values;
#ifdef C2_STREAM_PRODUCT_V3
#define EXPECTED_C2D_BYTES 33840u
#define ROOTS_OFFSET(data) u16((data) + 34)
#define EXPECTED_CONTEXT_BYTES 48u
#else
#define EXPECTED_C2D_BYTES 11048u
#define ROOTS_OFFSET(data) ((uint16_t)(u16((data) + 22) + u16((data) + 16) * 2u))
#define EXPECTED_CONTEXT_BYTES 44u
#endif
static uint16_t gc_checkpoints, allocated_count, allocated[1536];
static uint32_t write_calls, fail_write_call;
static struct { uint32_t offset; uint16_t length, value; } symbols[4096];

static uint16_t u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
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
    ++write_calls;
    if (fail_write_call && write_calls == fail_write_call) return 0;
    if (offset > c2d_length || length > (uint16_t)(c2d_length - offset)) return 0;
    memcpy(c2d_data + offset, src, length); return 1;
}
uint8_t c2_stream_name_value(uint8_t kind, uint32_t offset,
                             uint16_t length, uint16_t *value) {
    uint16_t i;
    if ((kind != 3u && kind != 5u && kind != 8u)
        || offset > shelf_length || length > shelf_length - offset
        || (!length && kind != 3u)) return 0;
    ++name_requests;
    if (kind == 3u) {
        if (allocated_count >= 284u) return 0;
        *value = next_heap; next_heap = (uint16_t)(next_heap + 2u);
        allocated[allocated_count++] = *value; ++string_values; return 1;
    }
    for (i = 0; i < symbol_values; ++i) {
        if (symbols[i].length == length
            && !memcmp(shelf_data + symbols[i].offset, shelf_data + offset, length)) {
            *value = symbols[i].value; return 1;
        }
    }
    if (symbol_values >= sizeof(symbols) / sizeof(symbols[0])) return 0;
    *value = next_symbol; next_symbol = (uint16_t)(next_symbol + 2u);
    symbols[symbol_values].offset = offset; symbols[symbol_values].length = length;
    symbols[symbol_values].value = *value; ++symbol_values; return 1;
}
uint8_t c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value) {
    (void)car; (void)cdr;
    if (allocated_count >= 284u) return 0;
    *value = next_heap; next_heap = (uint16_t)(next_heap + 2u);
    allocated[allocated_count++] = *value; ++pair_values; return 1;
}
uint8_t c2_stream_gc_checkpoint(uint16_t roots_offset, uint16_t root_count) {
    uint8_t before[3072]; uint16_t root, seen = 0, i, value, bytes;
    if (root_count != EXPECTED_ROOTS || roots_offset > c2d_length
        || root_count * 2u > (uint16_t)(c2d_length - roots_offset)) return 0;
    bytes = (uint16_t)(root_count * 2u);
    memcpy(before, c2d_data + roots_offset, bytes);
    for (root = 0; root < root_count; ++root) {
        value = u16(c2d_data + roots_offset + root * 2u);
        if (!value) continue;
        if (value >= 0x8000u || (value & 1u)) return 0;
        for (i = 0; i < allocated_count && allocated[i] != value; ++i) { }
        if (i == allocated_count) return 0;
        ++seen;
    }
    if (seen != allocated_count
        || memcmp(before, c2d_data + roots_offset, bytes)) return 0;
    ++gc_checkpoints; return 1;
}

int main(int argc, char **argv) {
    c2_stream_context context; uint32_t raw_c2d, at; uint8_t status, count;
    uint16_t hot[23], entry, materialized = 0, maximum = 0;
    unsigned inject_ordinal = 0, inject_value = 0;
    uint8_t inject_resolution = 0, inject_post_resolution = 0, inject_root = 0;
    uint8_t (*const phases[])(void *) = {
        c2_stream_phase_00, c2_stream_phase_01, c2_stream_phase_02,
        c2_stream_phase_03, c2_stream_phase_04, c2_stream_phase_05,
        c2_stream_phase_06, c2_stream_phase_07, c2_stream_phase_08,
        c2_stream_phase_09, c2_stream_phase_10,
#ifdef C2_STREAM_PHASE11_SPLIT_TEST
        c2_stream_phase_11a, c2_stream_phase_11b,
#else
        c2_stream_phase_11,
#endif
        c2_stream_phase_12
    };
    if (argc != 3 && argc != 4) return 90;
    if (argc == 4) {
        unsigned long fail_at;
        if (sscanf(argv[3], "resolution:%u:%u", &inject_ordinal, &inject_value) == 2)
            inject_resolution = 1;
        else if (sscanf(argv[3], "post-resolution:%u:%u", &inject_ordinal,
                        &inject_value) == 2)
            inject_post_resolution = 1;
        else if (sscanf(argv[3], "root:%u:%u", &inject_ordinal, &inject_value) == 2)
            inject_root = 1;
        else if (sscanf(argv[3], "fail-write:%lu", &fail_at) == 1)
            fail_write_call = fail_at;
        else return 94;
    }
    shelf_data = read_file(argv[1], &shelf_length);
    c2d_data = read_file(argv[2], &raw_c2d);
    if (!shelf_data || !c2d_data || raw_c2d > 0xffffu) return 91;
    c2d_length = (uint16_t)raw_c2d;
    at =
#ifdef C2_STREAM_PRODUCT_V3
        u16(c2d_data + 32);
#else
        u16(c2d_data + 22);
#endif
    if (at > c2d_length) return 92;
    memset(c2d_data + at, 0, c2d_length - (uint16_t)at);
    c2_stream_init(&context, shelf_length, c2d_length);
    for (at = 0; at < sizeof(phases) / sizeof(phases[0]); ++at) {
        status = phases[at](&context);
        if (status != C2_STREAM_OK) {
            fprintf(stderr, "c2-stream-v2: FAIL phase=%lu status=%u finished=%u writes=%lu\n",
                    (unsigned long)at, status, context.finished,
                    (unsigned long)write_calls);
            return status;
        }
        if (at == 7u && inject_resolution) {
            if (inject_ordinal >= context.resolution_count) return 95;
            c2d_data[context.resolutions_offset + inject_ordinal * 2u] = (uint8_t)inject_value;
            c2d_data[context.resolutions_offset + inject_ordinal * 2u + 1u]
                = (uint8_t)(inject_value >> 8);
        }
        if (at == 8u && inject_post_resolution) {
            if (inject_ordinal >= context.resolution_count) return 97;
            c2d_data[context.resolutions_offset + inject_ordinal * 2u]
                = (uint8_t)inject_value;
            c2d_data[context.resolutions_offset + inject_ordinal * 2u + 1u]
                = (uint8_t)(inject_value >> 8);
        }
        if (at == 11u && inject_root) {
            uint16_t roots = ROOTS_OFFSET(c2d_data);
            if (inject_ordinal >= context.c2_root_count) return 96;
            c2d_data[roots + inject_ordinal * 2u] = (uint8_t)inject_value;
            c2d_data[roots + inject_ordinal * 2u + 1u] = (uint8_t)(inject_value >> 8);
        }
    }
    for (entry = 0; entry < context.entry_count; ++entry) {
        status = c2_stream_materialize_entry(&context, entry, hot, 23u, &count);
        if (status != C2_STREAM_OK) return status;
        if (count > maximum) maximum = count;
        ++materialized;
    }
    if (!context.finished || context.phase != 13u
        || context.image_count != EXPECTED_IMAGES || context.entry_count != EXPECTED_ENTRIES
        || context.resolution_count != EXPECTED_RESOLUTIONS
        || context.resolution_cursor != EXPECTED_RESOLUTIONS
        || context.c2_root_count != EXPECTED_ROOTS
        || context.c2_root_cursor != EXPECTED_ROOTS
        || allocated_count != EXPECTED_ROOTS || gc_checkpoints != EXPECTED_ROOTS
        || pair_values != EXPECTED_PAIRS || name_requests != EXPECTED_NAME_REQUESTS
        || string_values != EXPECTED_STRINGS || symbol_values != EXPECTED_SYMBOLS
        || materialized != EXPECTED_ENTRIES || maximum != EXPECTED_MAX_LITERALS
        || c2d_length != EXPECTED_C2D_BYTES
        || sizeof(context) != EXPECTED_CONTEXT_BYTES) return 93;
    printf("c2-stream-v2: PASS shelf=%lu c2d=%u images=%u entries=%u "
           "descriptors=%u roots=%u gc=%u materialized=%u max-literals=%u context=%lu\n",
           (unsigned long)shelf_length, c2d_length, context.image_count,
           context.entry_count, context.resolution_count, context.c2_root_count,
           gc_checkpoints, materialized, maximum, (unsigned long)sizeof(context));
    free(shelf_data); free(c2d_data); return 0;
}
