/* Runtime Core preload verification. The L65M-v1 payload remains unchanged. */
#include "preload_integrity.h"

#define CRC16_CCITT_FALSE_INIT 0xffffu

static uint16_t read_u16(const uint8_t *bytes) {
    return (uint16_t)(bytes[0] | ((uint16_t)bytes[1] << 8));
}

static uint32_t read_u32(const uint8_t *bytes) {
    return (uint32_t)bytes[0]
        | ((uint32_t)bytes[1] << 8)
        | ((uint32_t)bytes[2] << 16)
        | ((uint32_t)bytes[3] << 24);
}

static uint16_t crc16_update(uint16_t crc, const uint8_t *bytes,
                             uint8_t length) {
    uint8_t i, value;
    for (i = 0; i < length; i++) {
        value = (uint8_t)(bytes[i] ^ (uint8_t)(crc >> 8));
        value ^= (uint8_t)(value >> 4);
        crc = (uint16_t)((crc << 8) ^ ((uint16_t)value << 12)
                         ^ ((uint16_t)value << 5) ^ value);
    }
    return crc;
}

runtime_preload_status runtime_preload_verify(
    runtime_preload_read_fn read, void *context,
    const runtime_preload_contract *expected,
    runtime_preload_observation *observation) {
    uint8_t trailer[RUNTIME_PRELOAD_TRAILER_BYTES];
    uint8_t block[32];
    uint16_t offset, crc;
    uint8_t count;

    if (observation) {
        observation->observed_length = 0;
        observation->observed_image_crc16 = 0;
        observation->observed_build_id = 0;
    }
    if (!read || !expected ||
        expected->payload_length >
            (uint16_t)(0xffffu - RUNTIME_PRELOAD_TRAILER_BYTES))
        return RUNTIME_PRELOAD_ERR_ARGUMENT;

    /* A cleared or incomplete stage cannot inherit a valid descriptor. */
    if (!read(context, expected->payload_length, trailer,
              RUNTIME_PRELOAD_TRAILER_BYTES)
        || trailer[0] != 'L' || trailer[1] != '6'
        || trailer[2] != '5' || trailer[3] != 'B'
        || trailer[4] != RUNTIME_PRELOAD_TRAILER_VERSION
        || trailer[5] != RUNTIME_PRELOAD_TRAILER_BYTES)
        return RUNTIME_PRELOAD_ERR_LENGTH;

    if (observation) {
        observation->observed_length = read_u16(trailer + 6);
        observation->observed_build_id = read_u32(trailer + 8);
    }
    if (read_u16(trailer + 6) != expected->payload_length)
        return RUNTIME_PRELOAD_ERR_LENGTH;
    if (read_u32(trailer + 8) != expected->build_id)
        return RUNTIME_PRELOAD_ERR_BUILD_ID;

    crc = CRC16_CCITT_FALSE_INIT;
    offset = 0;
    while (offset < expected->payload_length) {
        uint16_t remaining = (uint16_t)(expected->payload_length - offset);
        count = (uint8_t)(remaining > sizeof block ? sizeof block : remaining);
        if (!read(context, offset, block, count))
            return RUNTIME_PRELOAD_ERR_LENGTH;
        crc = crc16_update(crc, block, count);
        offset = (uint16_t)(offset + count);
    }
    crc = crc16_update(crc, trailer, RUNTIME_PRELOAD_TRAILER_BYTES);
    if (observation) observation->observed_image_crc16 = crc;
    if (crc != expected->image_crc16) return RUNTIME_PRELOAD_ERR_CRC;
    return RUNTIME_PRELOAD_OK;
}
