#ifndef LISP65_ATTIC_LIBRARY_SHELF_H
#define LISP65_ATTIC_LIBRARY_SHELF_H

#include <stdint.h>
#include "obj.h"

#define L65S_MAGIC_0 'L'
#define L65S_MAGIC_1 '6'
#define L65S_MAGIC_2 '5'
#define L65S_MAGIC_3 'S'
#define L65S_VERSION 3u
#define L65S_HEADER_BYTES 32u
#define L65S_RECORD_BYTES 32u
#define L65S_RECORDS 5u
#define L65S_PAYLOAD_OFF 192u
#define L65S_ATTIC_BASE 0x08100000ul
#define L65S_STAGE_SLOT 38u
#define L65S_NAME_SLOT 39u
#define L65S_STAGE_ABI_VERSION 1u

typedef enum {
    L65S_STAGE_OK = 0,
    L65S_STAGE_ERR_CONTEXT,
    L65S_STAGE_ERR_HEADER,
    L65S_STAGE_ERR_CATALOG,
    L65S_STAGE_ERR_NAME,
    L65S_STAGE_ERR_RANGE,
    L65S_STAGE_ERR_CRC,
    L65S_STAGE_ERR_COPY
} l65s_stage_status;

typedef struct {
    uint16_t abi_version;
    uint16_t context_size;
    obj name;
    uint8_t library_id;
    uint8_t reserved_name;
    uint16_t length;
    uint8_t status;
    uint8_t reserved;
    uint8_t buffer[32];
} l65s_stage_context;

uint8_t l65s_stage_entry(void *context);
uint8_t l65s_name_entry(void *context);

#ifdef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
void l65s_host_bind(const uint8_t *shelf, uint16_t shelf_length,
                    uint8_t *scratch, uint16_t scratch_capacity,
                    const char *name);
#endif

#endif
