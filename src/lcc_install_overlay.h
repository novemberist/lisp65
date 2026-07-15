/* Pointer-free synchronous work ABI for the three LCC installer slices. */
#ifndef LISP65_LCC_INSTALL_OVERLAY_H
#define LISP65_LCC_INSTALL_OVERLAY_H

#include <stdint.h>

#include "obj.h"

#define LCC_INSTALL_OVERLAY_ABI_VERSION 1u
#define LCC_INSTALL_OVERLAY_COOKIE_BASE 0x1cc0u

#define LCC_INSTALL_MAX_LITS 48u
#define LCC_INSTALL_MAX_FNS  16u
#define LCC_INSTALL_MAX_CODE 512u

enum {
    LCC_INSTALL_PHASE_SHAPE = 0,
    LCC_INSTALL_PHASE_LITERALS,
    LCC_INSTALL_PHASE_CODE,
    LCC_INSTALL_PHASE_COUNT
};

/* Exactly three transport calls per emitted function; this also bounds repeats. */
#define LCC_INSTALL_OVERLAY_MAX_STEPS \
    (LCC_INSTALL_MAX_FNS * LCC_INSTALL_PHASE_COUNT)

typedef enum {
    LCC_INSTALL_OK = 0,
    LCC_INSTALL_ERR_ARGUMENT,
    LCC_INSTALL_ERR_ABI,
    LCC_INSTALL_ERR_COOKIE,
    LCC_INSTALL_ERR_REENTRY,
    LCC_INSTALL_ERR_PHASE,
    LCC_INSTALL_ERR_ROOTS,
    LCC_INSTALL_ERR_EMPTY,
    LCC_INSTALL_ERR_SHAPE,
    LCC_INSTALL_ERR_FNS,
    LCC_INSTALL_ERR_LITS,
    LCC_INSTALL_ERR_CODE,
    LCC_INSTALL_ERR_BLOB,
    LCC_INSTALL_ERR_MARKER,
    LCC_INSTALL_ERR_REGION,
    LCC_INSTALL_ERR_DIR,
    LCC_INSTALL_ERR_OOM,
    LCC_INSTALL_ERR_TRANSPORT,
    LCC_INSTALL_ERR_REPEAT
} lcc_install_status;

typedef struct {
    uint16_t abi_version;
    uint16_t cookie;
    uint8_t expected_phase;
    uint8_t busy;
    uint8_t status;
    uint8_t finished;
    uint8_t repeat_phase;

    obj defname;
    obj true_symbol;
    obj keep_symbol;
    obj marker_symbol;
    obj current_fn;

    uint16_t dir_map[LCC_INSTALL_MAX_FNS];
    uint8_t fn_count;
    uint8_t is_main;
    uint8_t transient;
    uint8_t bank;
    uint8_t nargs;
    uint8_t nlocals;
    uint8_t flags;
    uint8_t literal_count;
    uint16_t code_length;
    uint16_t blob_length;
    uint16_t blob_off;
    obj literals;
    obj code;
    obj result;
} lcc_install_work;

typedef struct {
    obj result;
    uint8_t transient;
    uint8_t bank;
    uint16_t off;
    uint16_t length;
} lcc_install_result;

#ifdef __mos__
_Static_assert(sizeof(lcc_install_work) <= 80u,
               "LCC install overlay work ABI exceeds 80 bytes");
#endif

/* Synchronous call. The caller must root fnlist and defname until a returned
 * transient has run; obj values in the work block are IDs, never C pointers. */
lcc_install_status lcc_install_overlay(obj fnlist, obj defname,
                                       obj true_symbol, obj keep_symbol,
                                       obj marker_symbol,
                                       lcc_install_result *result);
void lcc_install_transient_pop(const lcc_install_result *result);
const char *lcc_install_status_message(lcc_install_status status);

uint8_t lcc_install_phase_00(void *context);
uint8_t lcc_install_phase_01(void *context);
uint8_t lcc_install_phase_02(void *context);

#endif /* LISP65_LCC_INSTALL_OVERLAY_H */
