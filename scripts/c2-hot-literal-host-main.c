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

static uint32_t rd32(const uint8_t *p) {
    return (uint32_t)rd16(p) | (uint32_t)rd16(p + 2) << 16;
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
        || (offset <= shelf_fail_at
            && length > shelf_fail_at - offset)) return 0;
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

static int parse_fail_mode(const char *mode, uint8_t *expected) {
    unsigned value; unsigned long shelf_at;
    if (sscanf(mode, "expect:%u", &value) == 1 && value <= 255u) {
        *expected = (uint8_t)value; return 1;
    }
    if (sscanf(mode, "shelf-fail:%lu:expect:%u", &shelf_at,
               &value) == 2 && shelf_at <= 0xffffffffUL && value <= 255u) {
        shelf_fail_at = (uint32_t)shelf_at;
        *expected = (uint8_t)value; return 1;
    }
    {
        unsigned at;
        if (sscanf(mode, "c2d-fail:%u:expect:%u", &at, &value) == 2
            && at <= 65535u && value <= 255u) {
            c2d_fail_at = (uint16_t)at; *expected = (uint8_t)value; return 1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    c2_stream_context context;
    uint8_t *cases, *cursor, *end;
    uint32_t raw_c2d, case_bytes;
    uint16_t case_count, ordinal, literal_offset, literal_count;
    uint16_t resolution_base, directory_base, image_entry_count, first;
    uint16_t hot[23], expected_word, index, completed = 0;
    uint8_t count, hot_count, status, expected_status = C2_STREAM_OK;
    uint32_t caller_metadata = 0;
    uint16_t caller_literal_offset = 0, caller_literal_count = 0;
    uint16_t caller_resolution_base = 0, caller_directory_base = 0;
    uint16_t caller_image_entry_count = 0, caller_first = 0;
    uint16_t caller_expected[23];
    uint8_t caller_count = 0, nested_restorations = 0;
    int negative_mode = 0, internal_negatives = 0;
    if (argc != 4 && argc != 5) return 90;
    shelf_data = read_file(argv[1], &shelf_bytes);
    c2d_data = read_file(argv[2], &raw_c2d);
    cases = read_file(argv[3], &case_bytes);
    if (!shelf_data || !c2d_data || !cases || raw_c2d > 0xffffu
        || case_bytes < 6u || memcmp(cases, "HREF", 4)) return 91;
    c2d_bytes = (uint16_t)raw_c2d;
    if (argc == 5) {
        negative_mode = parse_fail_mode(argv[4], &expected_status);
        if (!negative_mode || expected_status == C2_STREAM_OK) return 92;
    }
    memset(&context, 0, sizeof context);
    if (c2d_bytes < 48u || memcmp(c2d_data, "C2D\0", 4)
        || c2d_data[4] != 3u) return 93;
    context.generation = rd16(c2d_data + 10);
    context.image_count = rd16(c2d_data + 12);
    context.entry_count = rd16(c2d_data + 16);
    context.resolution_count = rd16(c2d_data + 20);
    context.c2_root_count = rd16(c2d_data + 24);
    context.images_offset = rd16(c2d_data + 28);
    context.entries_offset = rd16(c2d_data + 30);
    context.resolutions_offset = rd16(c2d_data + 32);
    context.roots_offset = rd16(c2d_data + 34);
    context.finished = 1u; context.phase = 13u;
    case_count = rd16(cases + 4); cursor = cases + 6; end = cases + case_bytes;
    if (case_count != context.entry_count) return 94;
    while (completed < case_count) {
        uint32_t metadata;
        if ((size_t)(end - cursor) < 19u) return 95;
        ordinal = rd16(cursor); metadata = rd32(cursor + 2);
        literal_offset = rd16(cursor + 6); literal_count = rd16(cursor + 8);
        resolution_base = rd16(cursor + 10); directory_base = rd16(cursor + 12);
        image_entry_count = rd16(cursor + 14); first = rd16(cursor + 16);
        count = cursor[18]; cursor += 19;
        if (ordinal != completed || count > 23u
            || (size_t)(end - cursor) < (size_t)count * 2u) return 96;
        status = c2_stream_product_materialize_literals(
            &context, metadata, literal_offset, literal_count,
            resolution_base, directory_base, image_entry_count, first, count,
            hot, 23u, &hot_count);
        if (status != C2_STREAM_OK) {
            if (negative_mode && status == expected_status) {
                printf("c2-hot-literal: REJECT status=%u ordinal=%u\n",
                       status, ordinal);
                return 0;
            }
            fprintf(stderr, "c2-hot-literal: unexpected status=%u ordinal=%u\n",
                    status, ordinal);
            return status;
        }
        if (negative_mode) {
            cursor += (uint16_t)count * 2u; ++completed; continue;
        }
        if (hot_count != count) return 97;
        for (index = 0; index < count; ++index) {
            expected_word = rd16(cursor + index * 2u);
            if (hot[index] != expected_word) {
                fprintf(stderr,
                        "c2-hot-literal: value mismatch ordinal=%u local=%u "
                        "got=%04x expected=%04x\n", ordinal, index,
                        hot[index], expected_word);
                return 98;
            }
        }
        if (count && !caller_count) {
            caller_metadata = metadata;
            caller_literal_offset = literal_offset;
            caller_literal_count = literal_count;
            caller_resolution_base = resolution_base;
            caller_directory_base = directory_base;
            caller_image_entry_count = image_entry_count;
            caller_first = first; caller_count = count;
            for (index = 0; index < count; ++index)
                caller_expected[index] = rd16(cursor + index * 2u);
        } else if (count && caller_count && !nested_restorations) {
            status = c2_stream_product_materialize_literals(
                &context, caller_metadata, caller_literal_offset,
                caller_literal_count, caller_resolution_base,
                caller_directory_base, caller_image_entry_count,
                caller_first, caller_count, hot, 23u, &hot_count);
            if (status != C2_STREAM_OK || hot_count != caller_count) return 103;
            for (index = 0; index < caller_count; ++index)
                if (hot[index] != caller_expected[index]) return 104;
            nested_restorations = 1;
        }
        if (!internal_negatives && count) {
            uint8_t saved_phase = context.phase;
            status = c2_stream_product_materialize_literals(
                &context, metadata, literal_offset, literal_count,
                resolution_base, directory_base, image_entry_count, first, count,
                hot, (uint8_t)(count - 1u), &hot_count);
            if (status != C2_STREAM_ERR_ENTRY) return 99;
            status = c2_stream_product_materialize_literals(
                &context, metadata, literal_offset, literal_count,
                resolution_base, directory_base, image_entry_count,
                literal_count, 1u, hot, 23u, &hot_count);
            if (status != C2_STREAM_ERR_ENTRY) return 100;
            context.phase = 12u;
            status = c2_stream_product_materialize_literals(
                &context, metadata, literal_offset, literal_count,
                resolution_base, directory_base, image_entry_count, first, count,
                hot, 23u, &hot_count);
            context.phase = saved_phase;
            if (status != C2_STREAM_ERR_STATE) return 101;
            internal_negatives = 3;
        }
        cursor += (uint16_t)count * 2u; ++completed;
    }
    if (cursor != end || negative_mode || internal_negatives != 3
        || nested_restorations != 1) return 102;
    printf("c2-hot-literal: PASS entries=%u negatives=%d nested=%u\n",
           completed, internal_negatives, nested_restorations);
    free(shelf_data); free(c2d_data); free(cases);
    return 0;
}
