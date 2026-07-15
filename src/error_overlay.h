/* Build-bound, allocation-free error text renderer overlay. */
#ifndef LISP65_ERROR_OVERLAY_H
#define LISP65_ERROR_OVERLAY_H

#include <stdint.h>

#include "error_codes.h"
#include "obj.h"

#ifndef LISP65_ERROR_OVERLAY_SLOT
#define LISP65_ERROR_OVERLAY_SLOT             36u
#endif
#define LISP65_ERROR_OVERLAY_ABI_VERSION      1u
#define LISP65_ERROR_OVERLAY_CONTEXT_TAG      0x4535364cUL /* "L65E" */
#define LISP65_ERROR_OVERLAY_CONTEXT_COOKIE   0x65e0u
#define LISP65_ERROR_OVERLAY_CONTEXT_CONTRACT \
    (LISP65_ERROR_OVERLAY_CONTEXT_COOKIE | LISP65_ERROR_OVERLAY_ABI_VERSION)

typedef enum {
    LISP65_ERROR_OVERLAY_OK = 0,
    LISP65_ERROR_OVERLAY_ERR_CONTEXT,
    LISP65_ERROR_OVERLAY_ERR_ABI,
    LISP65_ERROR_OVERLAY_ERR_SIZE,
    LISP65_ERROR_OVERLAY_ERR_COOKIE,
    LISP65_ERROR_OVERLAY_ERR_CODE,
    LISP65_ERROR_OVERLAY_ERR_TABLE,
    LISP65_ERROR_OVERLAY_ERR_SYMBOL
} lisp65_error_overlay_status;

/* context_tag is deliberately first: the entry rejects a context type mismatch
 * before inspecting any field shared with another overlay ABI. */
typedef struct {
    uint32_t context_tag;
    uint16_t context_contract;
    uint8_t code;
    obj symbol;
} lisp65_error_overlay_context;

#define LISP65_ERROR_OVERLAY_CONTEXT_SIZE \
    ((uint8_t)sizeof(lisp65_error_overlay_context))

#ifdef __mos__
_Static_assert(sizeof(lisp65_error_overlay_context) == 9u,
               "L65E overlay context ABI changed");
#endif

uint8_t lisp65_error_overlay_entry(void *context);

/* Returns one only after the complete text was rendered. Sparse codes without
 * profile text return zero; the caller owns the resident Ehh fallback for that
 * case and for transport, latch, context, and table failures. */
uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol);

#endif /* LISP65_ERROR_OVERLAY_H */
