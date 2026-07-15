/* Host mutation oracle for the Runtime Core L65B preload gate. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "preload_integrity.h"

#define PAYLOAD_BYTES 9u
#define IMAGE_BYTES (PAYLOAD_BYTES + RUNTIME_PRELOAD_TRAILER_BYTES)
#define BUILD_ID 0x12345678UL

typedef struct {
    uint8_t bytes[IMAGE_BYTES];
    uint16_t available;
} fixture;

static uint8_t fixture_read(void *context, uint16_t offset, uint8_t *dst,
                            uint16_t length) {
    fixture *image = (fixture *)context;
    if ((uint32_t)offset + length > image->available) return 0;
    memcpy(dst, image->bytes + offset, length);
    return 1;
}

static void put_u16(uint8_t *dst, uint16_t value) {
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
}

static void put_u32(uint8_t *dst, uint32_t value) {
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static void fixture_init(fixture *image) {
    static const uint8_t payload[PAYLOAD_BYTES] = {
        '1', '2', '3', '4', '5', '6', '7', '8', '9'
    };
    uint8_t *trailer;
    memset(image, 0, sizeof *image);
    memcpy(image->bytes, payload, sizeof payload);
    trailer = image->bytes + PAYLOAD_BYTES;
    memcpy(trailer, "L65B", 4);
    trailer[4] = RUNTIME_PRELOAD_TRAILER_VERSION;
    trailer[5] = RUNTIME_PRELOAD_TRAILER_BYTES;
    put_u16(trailer + 6, PAYLOAD_BYTES);
    put_u32(trailer + 8, BUILD_ID);
    image->available = IMAGE_BYTES;
}

static int expect(const char *name, runtime_preload_status actual,
                  runtime_preload_status expected) {
    if (actual == expected) return 0;
    fprintf(stderr, "runtime-preload-integrity: FAIL %s got=%u expected=%u\n",
            name, (unsigned)actual, (unsigned)expected);
    return 1;
}

int main(void) {
    const runtime_preload_contract contract = {
        PAYLOAD_BYTES, 0x66a3u, BUILD_ID
    };
    runtime_preload_observation observed;
    fixture image;
    int failed = 0;

    fixture_init(&image);
    failed |= expect("valid", runtime_preload_verify(
        fixture_read, &image, &contract, &observed), RUNTIME_PRELOAD_OK);
    if (observed.observed_length != PAYLOAD_BYTES
        || observed.observed_build_id != BUILD_ID
        || observed.observed_image_crc16 != 0x66a3u) {
        fprintf(stderr, "runtime-preload-integrity: FAIL observation\n");
        failed = 1;
    }

    fixture_init(&image);
    image.available = (uint16_t)(IMAGE_BYTES - 1u);
    failed |= expect("truncated", runtime_preload_verify(
        fixture_read, &image, &contract, 0), RUNTIME_PRELOAD_ERR_LENGTH);

    fixture_init(&image);
    image.bytes[2] ^= 0x40u;
    failed |= expect("payload-bitflip", runtime_preload_verify(
        fixture_read, &image, &contract, 0), RUNTIME_PRELOAD_ERR_CRC);

    fixture_init(&image);
    image.bytes[PAYLOAD_BYTES + 8u] ^= 0x01u;
    failed |= expect("build-id", runtime_preload_verify(
        fixture_read, &image, &contract, 0),
        RUNTIME_PRELOAD_ERR_BUILD_ID);

    fixture_init(&image);
    image.bytes[PAYLOAD_BYTES + 6u]++;
    image.bytes[PAYLOAD_BYTES + 8u] ^= 0x01u;
    image.bytes[2] ^= 0x40u;
    failed |= expect("length-precedence", runtime_preload_verify(
        fixture_read, &image, &contract, 0), RUNTIME_PRELOAD_ERR_LENGTH);

    fixture_init(&image);
    image.bytes[PAYLOAD_BYTES + 8u] ^= 0x01u;
    image.bytes[2] ^= 0x40u;
    failed |= expect("build-id-precedence", runtime_preload_verify(
        fixture_read, &image, &contract, 0),
        RUNTIME_PRELOAD_ERR_BUILD_ID);

    if (failed) return 1;
    puts("runtime-preload-integrity: PASS valid=1 truncation=1 bitflip=1 build-id=1 precedence=2");
    return 0;
}
