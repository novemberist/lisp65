/* Dedicated Bank-3 L65E slice: table and renderer share one catalog record. */
#include "error_overlay.h"

#if defined(LISP65_ERROR_OVERLAY) && \
    (defined(LISP65_RUNTIME_OVERLAY) || \
     defined(LISP65_RUNTIME_OVERLAY_HOST_TEST))

#include "error-text-table.h"
#include "printer.h"
#include "symbol.h"
#include "vm_runtime_overlay.h"

#ifndef LISP65_ERROR_TEXT_TABLE_MAGIC_U32
#error "generated LISP65 error text table header is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_INITIALIZER
#error "generated LISP65 error text table initializer is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_BUILD_ID
#error "generated LISP65 error text table build ID is required"
#endif
#if LISP65_ERROR_TEXT_TABLE_MAGIC_U32 != 0x4535364cUL
#error "generated error text table magic is not L65E"
#endif
#if LISP65_ERROR_TEXT_TABLE_VERSION != 1u
#error "unsupported L65E table version"
#endif
#if LISP65_ERROR_TEXT_TABLE_HEADER_BYTES != 16u
#error "unsupported L65E table header size"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_FLAGS
#error "generated L65E error text table flags are required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_FLAG_OFFSET_INDEX
#error "generated L65E offset-index flag is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_FLAG_SPARSE
#error "generated L65E sparse flag is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_FLAG_SHARED_REFS
#error "generated L65E shared-reference flag is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_PROFILE_ID
#error "generated L65E profile ID is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_INDEX_ENTRIES
#error "generated L65E index entry count is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_INDEX_BYTES
#error "generated L65E index byte count is required"
#endif
#ifndef LISP65_ERROR_TEXT_TABLE_TEXT_OFFSET
#error "generated L65E text offset is required"
#endif
#if LISP65_ERROR_TEXT_TABLE_COUNT == 0u || LISP65_ERROR_TEXT_TABLE_COUNT > 255u
#error "L65E table must bind stable error codes 1..255"
#endif
#if LISP65_ERROR_TEXT_TABLE_FLAGS != \
    ((LISP65_ERROR_TEXT_TABLE_PROFILE_ID << 4) | \
     LISP65_ERROR_TEXT_TABLE_FLAG_OFFSET_INDEX | \
     LISP65_ERROR_TEXT_TABLE_FLAG_SPARSE | \
     LISP65_ERROR_TEXT_TABLE_FLAG_SHARED_REFS)
#error "L65E table flags do not describe the sparse shared-reference profile"
#endif
#if LISP65_ERROR_TEXT_TABLE_INDEX_ENTRIES != \
    LISP65_ERROR_TEXT_TABLE_COUNT
#error "L65E shared-reference index must contain one entry per code"
#endif
#if LISP65_ERROR_TEXT_TABLE_INDEX_BYTES != \
    LISP65_ERROR_TEXT_TABLE_INDEX_ENTRIES * 2u
#error "L65E offset index must use little-endian uint16 entries"
#endif
#if LISP65_ERROR_TEXT_TABLE_TEXT_OFFSET != \
    LISP65_ERROR_TEXT_TABLE_HEADER_BYTES + LISP65_ERROR_TEXT_TABLE_INDEX_BYTES
#error "L65E text payload does not follow its offset index"
#endif
#if LISP65_ERROR_TEXT_TABLE_TEXT_OFFSET > LISP65_ERROR_TEXT_TABLE_BYTES
#error "L65E text payload starts outside the table"
#endif
#if LISP65_ERROR_TEXT_TABLE_BYTES > LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICE
#error "L65E table alone exceeds the runtime overlay window"
#endif
#if defined(LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID) && \
    LISP65_ERROR_TEXT_TABLE_BUILD_ID != LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID
#error "L65E table and runtime overlay profile build IDs differ"
#endif
#ifndef LISP65_ERROR_OVERLAY_SLOT
#error "LISP65_ERROR_OVERLAY_SLOT is required"
#endif
#if LISP65_ERROR_OVERLAY_SLOT != 36u
#error "dedicated L65E renderer is pinned to catalog slot 36"
#endif

#if defined(__GNUC__) || defined(__clang__)
#define L65E_SLICE \
    __attribute__((section(".lisp65_rt_l65e"), noinline, used))
#define L65E_SLICE_DATA \
    __attribute__((section(".lisp65_rt_l65e_data"), used))
#else
#define L65E_SLICE
#define L65E_SLICE_DATA
#endif

static const uint8_t l65e_table[] L65E_SLICE_DATA =
    LISP65_ERROR_TEXT_TABLE_INITIALIZER;

_Static_assert(sizeof l65e_table == LISP65_ERROR_TEXT_TABLE_BYTES,
               "generated L65E byte count differs from initializer");
_Static_assert(LISP65_ERROR_TEXT_TABLE_COUNT + 1u == LISP65_ERROR_CODE_LIMIT,
               "L65E table does not cover the stable error-code enum");
#define L65E_ASSERT_CODE(name, value) \
    _Static_assert((name) == (value), "L65E error-code binding changed");
LISP65_ERROR_TEXT_CODE_BINDINGS(L65E_ASSERT_CODE)
#undef L65E_ASSERT_CODE

static uint16_t L65E_SLICE l65e_u16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

/* The build gate proves every generated shared span is inside the table; the
 * transport verifies the whole slice CRC. Runtime checks cover dynamic input. */
L65E_SLICE uint8_t lisp65_error_overlay_entry(void *opaque) {
    lisp65_error_overlay_context *context;
    uint16_t descriptor, index, offset;
    uint8_t length;

    if (!opaque) return LISP65_ERROR_OVERLAY_ERR_CONTEXT;
    context = (lisp65_error_overlay_context *)opaque;
    if (context->context_tag != LISP65_ERROR_OVERLAY_CONTEXT_TAG)
        return LISP65_ERROR_OVERLAY_ERR_CONTEXT;
    if (context->context_contract != LISP65_ERROR_OVERLAY_CONTEXT_CONTRACT)
        return LISP65_ERROR_OVERLAY_ERR_ABI;
    if (!context->code || context->code > LISP65_ERROR_TEXT_TABLE_COUNT)
        return LISP65_ERROR_OVERLAY_ERR_CODE;
    if (context->symbol != NIL &&
        context->code != LISP65_ERR_UNDEFINED_FUNCTION &&
        (context->code < LISP65_ERR_FASL_ENTRIES_OVERFLOW ||
         context->code > LISP65_ERR_LCC_INVALID_PARAMETER_LIST))
        return LISP65_ERROR_OVERLAY_ERR_SYMBOL;
    index = (uint16_t)(LISP65_ERROR_TEXT_TABLE_HEADER_BYTES +
                       ((uint16_t)(context->code - 1u) << 1));
    descriptor = l65e_u16(l65e_table + index);
    length = (uint8_t)(descriptor >> LISP65_ERROR_TEXT_TABLE_REF_LENGTH_SHIFT);
    if (!length) return LISP65_ERROR_OVERLAY_ERR_CODE;
    offset = (uint16_t)(LISP65_ERROR_TEXT_TABLE_TEXT_OFFSET +
                        (descriptor & LISP65_ERROR_TEXT_TABLE_REF_OFFSET_MASK));

    while (length--) emit((char)l65e_table[offset++]);
    if (context->symbol != NIL) {
        const char *symbol_name = symname(context->symbol);
        while (*symbol_name) emit(*symbol_name++);
    }
    return LISP65_ERROR_OVERLAY_OK;
}

uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    lisp65_error_overlay_context context;
    vm_runtime_overlay_status transport;
    uint8_t result;

    context.context_tag = LISP65_ERROR_OVERLAY_CONTEXT_TAG;
    context.context_contract = LISP65_ERROR_OVERLAY_CONTEXT_CONTRACT;
    context.code = code;
    context.symbol = symbol;
    transport = vm_runtime_overlay_exec((uint8_t)LISP65_ERROR_OVERLAY_SLOT,
                                        &context, &result);
    return transport == VM_RUNTIME_OVERLAY_OK &&
           result == LISP65_ERROR_OVERLAY_OK;
}

#endif /* LISP65_ERROR_OVERLAY && runtime-overlay transport */
