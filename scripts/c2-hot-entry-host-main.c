#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "c2-stream-v2-decoder.h"

#define SESSION_TAG 0x800000UL

static uint8_t *shelf_data, *c2d_data;
static uint32_t shelf_bytes;
static uint16_t c2d_bytes;
static uint32_t shelf_fail_at = 0xffffffffUL;
static uint16_t c2d_fail_at = 0xffffu;

static uint16_t rd16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}

static uint32_t rd24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}

static uint8_t *read_file(const char *path, uint32_t *length) {
    FILE *file = fopen(path, "rb");
    long size;
    uint8_t *data;
    if (!file || fseek(file, 0, SEEK_END)
        || (size = ftell(file)) < 0 || fseek(file, 0, SEEK_SET)) return 0;
    data = malloc(size ? (size_t)size : 1u);
    if (!data || fread(data, 1, (size_t)size, file) != (size_t)size
        || fclose(file)) {
        free(data); return 0;
    }
    *length = (uint32_t)size;
    return data;
}

uint8_t c2_stream_shelf_read(uint32_t offset, void *dst, uint16_t length) {
    if (offset & SESSION_TAG) return 0;
    if (offset > shelf_bytes || length > shelf_bytes - offset
        || (offset <= shelf_fail_at && length > shelf_fail_at - offset))
        return 0;
    memcpy(dst, shelf_data + offset, length);
    return 1;
}

uint8_t c2_stream_c2d_read(uint16_t offset, void *dst, uint16_t length) {
    if (offset > c2d_bytes || length > (uint16_t)(c2d_bytes - offset)
        || (offset <= c2d_fail_at
            && length > (uint16_t)(c2d_fail_at - offset))) return 0;
    memcpy(dst, c2d_data + offset, length);
    return 1;
}

uint8_t c2_stream_c2d_write(uint16_t offset, const void *src,
                            uint16_t length) {
    (void)offset; (void)src; (void)length;
    return 0;
}

static c2_stream_context active_context;

uint8_t c2_entry_records(uint16_t ordinal, uint8_t directory[10],
                         uint8_t image[32], uint8_t entry[16]) {
    uint8_t metadata_header[24];
    uint16_t local, entries_offset;
    uint32_t metadata;
    if (ordinal >= active_context.entry_count
        || !c2_stream_c2d_read((uint16_t)(active_context.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    if (directory[0] >= active_context.image_count || directory[1]
        || rd16(directory + 8) != active_context.generation
        || !c2_stream_c2d_read((uint16_t)(active_context.images_offset
            + directory[0] * 32u), image, 32u)) return 0;
    local = rd16(directory + 2); metadata = rd24(image + 23);
    if (image[0] || local >= rd16(image + 8)
        || !c2_stream_shelf_read(metadata, metadata_header,
                                 sizeof metadata_header)) return 0;
    entries_offset = rd16(metadata_header + 14);
    return c2_stream_shelf_read(metadata + entries_offset
                                + (uint32_t)local * 16u,
                                entry, 16u);
}

uint8_t c2_stream_product_child_value(
        c2_stream_context *context, uint32_t metadata,
        uint16_t literals_offset, uint16_t resolution_base,
        uint16_t local, uint16_t *value) {
    uint8_t descriptor[8], b[2];
    uint16_t word;
    if (!context || !value
        || !c2_stream_shelf_read(metadata + literals_offset
                                 + (uint32_t)local * 8u,
                                 descriptor, sizeof descriptor)
        || !c2_stream_c2d_read((uint16_t)(context->resolutions_offset
                                  + (resolution_base + local) * 2u),
                               b, 2u)) return 0;
    word = rd16(b);
    if (descriptor[0] == 3u || descriptor[0] == 7u) {
        if (word >= context->c2_root_count
            || !c2_stream_c2d_read((uint16_t)(context->roots_offset
                                      + word * 2u), b, 2u)) return 0;
        word = rd16(b);
        if (!word || word >= 0x8000u || (word & 1u)) return 0;
    }
    *value = word;
    return 1;
}

int main(int argc, char **argv) {
    uint8_t *cases, *cursor, *end;
    uint32_t raw_c2d, case_bytes;
    uint16_t case_count, ordinal, hot[23], expected, i, completed = 0;
    uint8_t count, hot_count, status, negatives = 0;
    uint16_t first_ordinal = 0xffffu, first_values[23];
    uint8_t first_count = 0, nested = 0;
    if (argc != 4) return 90;
    shelf_data = read_file(argv[1], &shelf_bytes);
    c2d_data = read_file(argv[2], &raw_c2d);
    cases = read_file(argv[3], &case_bytes);
    if (!shelf_data || !c2d_data || !cases || raw_c2d > 0xffffu
        || case_bytes < 6u || memcmp(cases, "HREF", 4)) return 91;
    c2d_bytes = (uint16_t)raw_c2d;
    memset(&active_context, 0, sizeof active_context);
    if (c2d_bytes < 48u || memcmp(c2d_data, "C2D\0", 4)
        || c2d_data[4] != 3u) return 92;
    active_context.generation = rd16(c2d_data + 10);
    active_context.image_count = rd16(c2d_data + 12);
    active_context.entry_count = rd16(c2d_data + 16);
    active_context.resolution_count = rd16(c2d_data + 20);
    active_context.c2_root_count = rd16(c2d_data + 24);
    active_context.images_offset = rd16(c2d_data + 28);
    active_context.entries_offset = rd16(c2d_data + 30);
    active_context.resolutions_offset = rd16(c2d_data + 32);
    active_context.roots_offset = rd16(c2d_data + 34);
    active_context.finished = 1u; active_context.phase = 13u;
    case_count = rd16(cases + 4); cursor = cases + 6; end = cases + case_bytes;
    if (case_count != active_context.entry_count) return 93;
    while (completed < case_count) {
        if ((size_t)(end - cursor) < 19u) return 94;
        ordinal = rd16(cursor); count = cursor[18]; cursor += 19;
        if (ordinal != completed || count > 23u
            || (size_t)(end - cursor) < (size_t)count * 2u) return 95;
        status = c2_stream_product_materialize_entry(
            &active_context, ordinal, hot, 23u, &hot_count);
        if (status != C2_STREAM_OK || hot_count != count) return 96;
        for (i = 0; i < count; ++i) {
            expected = rd16(cursor + i * 2u);
            if (hot[i] != expected) return 97;
        }
        if (count && first_ordinal == 0xffffu) {
            first_ordinal = ordinal; first_count = count;
            for (i = 0; i < count; ++i) first_values[i] = hot[i];
        } else if (count && !nested) {
            status = c2_stream_product_materialize_entry(
                &active_context, first_ordinal, hot, 23u, &hot_count);
            if (status != C2_STREAM_OK || hot_count != first_count) return 98;
            for (i = 0; i < first_count; ++i)
                if (hot[i] != first_values[i]) return 99;
            nested = 1;
        }
        if (count && !negatives) {
            uint8_t phase = active_context.phase;
            status = c2_stream_product_materialize_entry(
                &active_context, ordinal, hot, (uint8_t)(count - 1u), &hot_count);
            if (status != C2_STREAM_ERR_ENTRY) return 100;
            status = c2_stream_product_materialize_entry(
                &active_context, active_context.entry_count, hot, 23u, &hot_count);
            if (status != C2_STREAM_ERR_ENTRY) return 101;
            active_context.phase = 12u;
            status = c2_stream_product_materialize_entry(
                &active_context, ordinal, hot, 23u, &hot_count);
            active_context.phase = phase;
            if (status != C2_STREAM_ERR_STATE) return 102;
            shelf_fail_at = rd24(c2d_data + active_context.images_offset
                                 + c2d_data[active_context.entries_offset
                                     + ordinal * 10u] * 32u + 23)
                + rd16(shelf_data + rd24(c2d_data + active_context.images_offset
                    + c2d_data[active_context.entries_offset + ordinal * 10u]
                    * 32u + 23) + 16)
                + (uint32_t)rd16(cursor - 3) * 8u;
            status = c2_stream_product_materialize_entry(
                &active_context, ordinal, hot, 23u, &hot_count);
            shelf_fail_at = 0xffffffffUL;
            if (status != C2_STREAM_ERR_IO) return 103;
            c2d_fail_at = (uint16_t)(active_context.resolutions_offset
                + (rd16(c2d_data + active_context.images_offset
                    + c2d_data[active_context.entries_offset + ordinal * 10u]
                    * 32u + 10) + rd16(cursor - 3)) * 2u);
            status = c2_stream_product_materialize_entry(
                &active_context, ordinal, hot, 23u, &hot_count);
            c2d_fail_at = 0xffffu;
            if (status != C2_STREAM_ERR_IO) return 104;
            negatives = 5;
        }
        cursor += (uint16_t)count * 2u; ++completed;
    }
    if (cursor != end || negatives != 5u || nested != 1u) return 105;
    printf("c2-hot-entry: PASS entries=%u literals=1931 negatives=%u nested=%u\n",
           completed, negatives, nested);
    free(shelf_data); free(c2d_data); free(cases);
    return 0;
}
