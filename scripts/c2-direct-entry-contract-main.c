#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "c2-stream-v2-decoder.h"
#include "obj.h"

#ifndef EXPECTED_IMAGES
#error "EXPECTED_IMAGES is required"
#endif
#ifndef EXPECTED_ENTRIES
#error "EXPECTED_ENTRIES is required"
#endif
#ifndef EXPECTED_RESOLUTIONS
#error "EXPECTED_RESOLUTIONS is required"
#endif
#ifndef EXPECTED_ROOTS
#error "EXPECTED_ROOTS is required"
#endif
#ifndef EXPECTED_DIRECT_REFS
#error "EXPECTED_DIRECT_REFS is required"
#endif

static uint8_t *shelf_data, *c2d_data;
static uint32_t shelf_length;
static uint16_t c2d_length;

static uint16_t r16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
static uint32_t r24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}
static void w16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
static uint8_t *read_file(const char *path, uint32_t *length) {
    FILE *file = fopen(path, "rb"); long size; uint8_t *data;
    if (!file || fseek(file, 0, SEEK_END)
        || (size = ftell(file)) < 0 || fseek(file, 0, SEEK_SET)) return 0;
    data = malloc((size_t)size ? (size_t)size : 1u);
    if (!data || fread(data, 1, (size_t)size, file) != (size_t)size
        || fclose(file)) { free(data); return 0; }
    *length = (uint32_t)size; return data;
}
static uint8_t write_file(const char *path, const uint8_t *data, uint16_t length) {
    FILE *file = fopen(path, "wb");
    if (!file) return 0;
    if (fwrite(data, 1, length, file) != length || fclose(file)) return 0;
    return 1;
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
uint8_t c2_stream_name_value(uint8_t kind, uint32_t shelf_offset,
                             uint16_t length, uint16_t *value) {
    (void)kind; (void)shelf_offset; (void)length; (void)value; return 0;
}
uint8_t c2_stream_pair_value(uint16_t car, uint16_t cdr, uint16_t *value) {
    (void)car; (void)cdr; (void)value; return 0;
}
uint8_t c2_stream_gc_checkpoint(uint16_t roots_offset, uint16_t root_count) {
    (void)roots_offset; (void)root_count; return 0;
}

static uint8_t phase12_rejects(c2_stream_context *context, uint16_t at,
                               uint16_t mutation) {
    uint16_t original = r16(c2d_data + at);
    uint8_t status;
    w16(c2d_data + at, mutation);
    context->phase = 12u; context->finished = 0u; context->error = 0u;
    status = c2_stream_phase_12(context);
    w16(c2d_data + at, original);
    return status == C2_STREAM_ERR_RESOLUTION && !context->finished;
}

int main(int argc, char **argv) {
    c2_stream_context context;
    uint32_t raw_c2d, meta;
    uint16_t image, i, literal_count, literal_offset, resolution_base;
    uint16_t directory_base, local, global, value, root = 0;
    uint16_t first_at = 0, first_expected = 0, first_local = 0;
    uint16_t direct_entries = 0, direct_min = 0xffffu, direct_max = 0;
    uint16_t direct_fixnums = 0;
    uint8_t *im, *header, *descriptor;
    if (argc != 4) return 90;
    shelf_data = read_file(argv[1], &shelf_length);
    c2d_data = read_file(argv[2], &raw_c2d);
    if (!shelf_data || !c2d_data || raw_c2d > 0xffffu) return 91;
    c2d_length = (uint16_t)raw_c2d;
    memset(&context, 0, sizeof(context));
    context.c2d_bytes = c2d_length;
    context.image_count = EXPECTED_IMAGES;
    context.entry_count = EXPECTED_ENTRIES;
    context.resolution_count = EXPECTED_RESOLUTIONS;
    context.images_offset = 32u;
    context.resolutions_offset = (uint16_t)(32u + EXPECTED_IMAGES * 20u);
    context.c2_root_count = EXPECTED_ROOTS;
    context.phase = 8u;
    if (c2_stream_phase_08(&context) != C2_STREAM_OK || context.phase != 9u)
        return 92;

    for (image = 0; image < EXPECTED_IMAGES; ++image) {
        im = c2d_data + context.images_offset + image * 20u;
        directory_base = r16(im + 2); resolution_base = r16(im + 6);
        meta = r24(im + 13);
        if (meta + 24u > shelf_length) return 93;
        header = shelf_data + meta;
        literal_count = r16(header + 12); literal_offset = r16(header + 16);
        if (meta + literal_offset + (uint32_t)literal_count * 8u > shelf_length)
            return 94;
        for (i = 0; i < literal_count; ++i) {
            descriptor = shelf_data + meta + literal_offset + (uint32_t)i * 8u;
            if (descriptor[0] == 3u || descriptor[0] == 7u) {
                uint16_t pointer = (uint16_t)(2u * (1000u + root));
#ifdef C2D_V6_ROOT_SURROGATE
                w16(c2d_data + context.resolutions_offset
                    + (resolution_base + i) * 2u,
                    (uint16_t)((root + 1u) << 1));
#else
                w16(c2d_data + context.resolutions_offset
                    + (resolution_base + i) * 2u, root);
#endif
                w16(c2d_data + context.resolutions_offset
                    + EXPECTED_RESOLUTIONS * 2u + root * 2u, pointer);
                ++root;
            } else if (descriptor[0] == 4u) {
                local = r16(descriptor + 2);
                global = (uint16_t)(directory_base + local);
                value = r16(c2d_data + context.resolutions_offset
                            + (resolution_base + i) * 2u);
                if (local >= r16(im + 4) || global >= EXPECTED_ENTRIES
                    || value != (uint16_t)MK_BCODE(global)
                    || !IS_BCODE((obj)value) || BCODE_IDX((obj)value) != global)
                    return 95;
                if (value & 1u) ++direct_fixnums;
                if (value < direct_min) direct_min = value;
                if (value > direct_max) direct_max = value;
                if (!direct_entries && directory_base) {
                    first_at = (uint16_t)(context.resolutions_offset
                        + (resolution_base + i) * 2u);
                    first_expected = value; first_local = local;
                }
                ++direct_entries;
            }
        }
    }
    if (root != EXPECTED_ROOTS
        || direct_entries != EXPECTED_DIRECT_REFS || direct_fixnums
        || !first_at || !write_file(argv[3], c2d_data, c2d_length)) return 96;

    context.resolution_cursor = EXPECTED_RESOLUTIONS;
    context.c2_root_cursor = EXPECTED_ROOTS;
    context.phase = 12u; context.error = 0u;
    if (c2_stream_phase_12(&context) != C2_STREAM_OK || !context.finished)
        return 97;
    if (!phase12_rejects(&context, first_at, (uint16_t)(first_expected | 1u))
        || !phase12_rejects(&context, first_at, (uint16_t)MK_BCODE(first_local))
        || !phase12_rejects(&context, first_at,
                            (uint16_t)(0xc000u + BCODE_IDX((obj)first_expected)))
        || !phase12_rejects(&context, first_at, 0xe000u)) return 98;

    printf("c2-direct-entry-target: PASS refs=%u range=%04x..%04x "
           "fixnums=0 negatives=4\n",
           direct_entries, direct_min, direct_max);
    free(shelf_data); free(c2d_data); return 0;
}
