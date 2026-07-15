/* Build-bound Runtime Core Bank-5 preload integrity contract. */
#ifndef LISP65_RUNTIME_PRELOAD_INTEGRITY_H
#define LISP65_RUNTIME_PRELOAD_INTEGRITY_H

#include <stdint.h>

/* Appended after the unchanged L65M-v1 payload:
 * "L65B", u8 version, u8 trailer_bytes, u16 payload_bytes, u32 build_id. */
#define RUNTIME_PRELOAD_TRAILER_BYTES 12u
#define RUNTIME_PRELOAD_TRAILER_VERSION 1u
#define RUNTIME_PRELOAD_BINDING_RECORD_BYTES 14u
#define RUNTIME_PRELOAD_BINDING_RECORD_VERSION 1u

typedef enum {
    RUNTIME_PRELOAD_OK = 0,
    RUNTIME_PRELOAD_ERR_LENGTH = 1,
    RUNTIME_PRELOAD_ERR_BUILD_ID = 2,
    RUNTIME_PRELOAD_ERR_CRC = 3,
    RUNTIME_PRELOAD_ERR_ARGUMENT = 4
} runtime_preload_status;

typedef struct {
    uint16_t payload_length;
    uint16_t image_crc16;
    uint32_t build_id;
} runtime_preload_contract;

typedef struct {
    uint16_t observed_length;
    uint16_t observed_image_crc16;
    uint32_t observed_build_id;
} runtime_preload_observation;

/* Return nonzero only when the complete requested span was read. */
typedef uint8_t (*runtime_preload_read_fn)(void *context, uint16_t offset,
                                           uint8_t *dst, uint16_t length);

runtime_preload_status runtime_preload_verify(
    runtime_preload_read_fn read, void *context,
    const runtime_preload_contract *expected,
    runtime_preload_observation *observation);

#endif /* LISP65_RUNTIME_PRELOAD_INTEGRITY_H */
