#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "attic_library_shelf.h"

static uint16_t u16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint8_t *read_file(const char *path, size_t *length) {
    FILE *stream = fopen(path, "rb");
    uint8_t *data;
    long size;
    if (!stream || fseek(stream, 0, SEEK_END) || (size = ftell(stream)) < 0 ||
        fseek(stream, 0, SEEK_SET)) {
        if (stream) fclose(stream);
        return NULL;
    }
    data = malloc((size_t)size ? (size_t)size : 1u);
    if (!data || fread(data, 1, (size_t)size, stream) != (size_t)size) {
        free(data);
        fclose(stream);
        return NULL;
    }
    fclose(stream);
    *length = (size_t)size;
    return data;
}

static void reset_context(l65s_stage_context *context) {
    memset(context, 0, sizeof *context);
    context->abi_version = L65S_STAGE_ABI_VERSION;
    context->context_size = sizeof *context;
    context->library_id = 0xffu;
}

static int expect(uint8_t actual, uint8_t wanted, const char *label) {
    if (actual == wanted) return 1;
    fprintf(stderr, "attic-library-shelf-smoke: %s: got %u, expected %u\n",
            label, actual, wanted);
    return 0;
}

static int check_library(const uint8_t *shelf, uint16_t shelf_length,
                         uint8_t *scratch, uint16_t scratch_capacity,
                         const char *name, uint8_t id) {
    l65s_stage_context context;
    const uint8_t *record = shelf + L65S_HEADER_BYTES + id * L65S_RECORD_BYTES;
    uint16_t offset = u16(record + 8);
    uint16_t length = u16(record + 10);
    reset_context(&context);
    memset(scratch, 0xa5, scratch_capacity);
    l65s_host_bind(shelf, shelf_length, scratch, scratch_capacity, name);
    if (!expect(l65s_name_entry(&context), L65S_STAGE_OK, "name") ||
        context.library_id != id ||
        !expect(l65s_stage_entry(&context), L65S_STAGE_OK, "stage") ||
        context.status != L65S_STAGE_OK || context.length != length ||
        memcmp(scratch, shelf + offset, length)) {
        fprintf(stderr, "attic-library-shelf-smoke: exact copy failed for %s\n", name);
        return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    l65s_stage_context context;
    uint8_t *shelf, *damaged, *scratch;
    size_t shelf_size;
    uint16_t shelf_length;
    int ok = 1;
    if (argc != 2) {
        fprintf(stderr, "usage: %s SHELF\n", argv[0]);
        return 2;
    }
    shelf = read_file(argv[1], &shelf_size);
    if (!shelf || shelf_size > 0xffffu || shelf_size < L65S_PAYLOAD_OFF) {
        fprintf(stderr, "attic-library-shelf-smoke: cannot read valid shelf\n");
        free(shelf);
        return 2;
    }
    shelf_length = (uint16_t)shelf_size;
    scratch = malloc(0x9600u);
    damaged = malloc(shelf_size);
    if (!scratch || !damaged) {
        free(damaged); free(scratch); free(shelf);
        return 2;
    }

    ok &= check_library(shelf, shelf_length, scratch, 0x9600u, "ide", 0);
    ok &= check_library(shelf, shelf_length, scratch, 0x9600u, "idex", 1);
    ok &= check_library(shelf, shelf_length, scratch, 0x9600u, "m65d", 2);
    ok &= check_library(shelf, shelf_length, scratch, 0x9600u, "buffer", 3);
    ok &= check_library(shelf, shelf_length, scratch, 0x9600u, "lcc", 4);

    reset_context(&context);
    l65s_host_bind(shelf, shelf_length, scratch, 0x9600u, "unknown");
    ok &= expect(l65s_name_entry(&context), L65S_STAGE_ERR_NAME, "unknown name");

    reset_context(&context);
    context.library_id = L65S_RECORDS;
    l65s_host_bind(shelf, shelf_length, scratch, 0x9600u, "ide");
    ok &= expect(l65s_stage_entry(&context), L65S_STAGE_ERR_HEADER, "invalid id");

    memcpy(damaged, shelf, shelf_size);
    damaged[0] ^= 1;
    reset_context(&context); context.library_id = 0;
    l65s_host_bind(damaged, shelf_length, scratch, 0x9600u, "ide");
    ok &= expect(l65s_stage_entry(&context), L65S_STAGE_ERR_HEADER, "header mutation");

    memcpy(damaged, shelf, shelf_size);
    damaged[7] ^= 1;
    reset_context(&context); context.library_id = 0;
    l65s_host_bind(damaged, shelf_length, scratch, 0x9600u, "ide");
    ok &= expect(l65s_stage_entry(&context), L65S_STAGE_ERR_HEADER, "record-count mutation");

    memcpy(damaged, shelf, shelf_size);
    damaged[L65S_HEADER_BYTES] ^= 1;
    reset_context(&context); context.library_id = 0;
    l65s_host_bind(damaged, shelf_length, scratch, 0x9600u, "ide");
    ok &= expect(l65s_stage_entry(&context), L65S_STAGE_ERR_CATALOG, "catalog mutation");

    reset_context(&context); context.library_id = 4;
    l65s_host_bind(shelf, (uint16_t)(shelf_length - 1u), scratch, 0x9600u, "lcc");
    ok &= expect(l65s_stage_entry(&context), L65S_STAGE_ERR_COPY, "truncated payload");

    reset_context(&context); context.library_id = 0;
    l65s_host_bind(shelf, shelf_length, scratch, 1u, "ide");
    ok &= expect(l65s_stage_entry(&context), L65S_STAGE_ERR_COPY, "short scratch");

    free(damaged); free(scratch); free(shelf);
    if (!ok) return 1;
    puts("attic-library-shelf-smoke: PASS libraries=5 negative_cases=7 exact_copy=yes");
    return 0;
}
