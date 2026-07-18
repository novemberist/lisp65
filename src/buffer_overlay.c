/* 1.1-E first-class buffer operations. The VM keeps one compact native
 * transport facade resident; checked operations execute from three reusable,
 * profile-bound runtime-overlay slices. Entry results are VM status codes. */
#include "buffer_overlay.h"

#if defined(LISP65_FIRST_CLASS_BUFFER) && !defined(LISP65_BUFFER_NO_PRIMS)

#include "mem.h"
#include "vm.h"

#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define BUFFER_READ_ENTRY \
    __attribute__((section(".lisp65_rt_buffer_read"), noinline, used))
#define BUFFER_WRITE_ENTRY \
    __attribute__((section(".lisp65_rt_buffer_write"), noinline, used))
#define BUFFER_ALLOC_ENTRY \
    __attribute__((section(".lisp65_rt_buffer_alloc"), noinline, used))
#else
#define BUFFER_READ_ENTRY
#define BUFFER_WRITE_ENTRY
#define BUFFER_ALLOC_ENTRY
#endif

static __attribute__((always_inline)) inline uint8_t buffer_context_valid(
        lisp65_buffer_overlay_context *context) {
    return context && context->args;
}

BUFFER_READ_ENTRY uint8_t lisp65_buffer_overlay_read_entry(void *opaque) {
    lisp65_buffer_overlay_context *context =
        (lisp65_buffer_overlay_context *)opaque;
    int16_t index, operation;

    if (!buffer_context_valid(context)) return VM_BADOPCODE;
    context->result = NIL;
    if (!context->argc || !IS_FIX(context->args[0])) return VM_TYPEERROR;
    operation = FIXVAL(context->args[0]);
    switch (operation) {
    case 0: /* (bufferp value) */
        if (context->argc != 2) return VM_ARITY;
        if (IS_PTR(context->args[1]) && cell_type(context->args[1]) == T_BUF)
            /* The private carrier returns a truthy witness. The shelf-level
             * public predicate normalizes it to canonical t. */
            context->result = context->args[1];
        return VM_OK;
    case 1: /* (buffer-length buffer) */
        if (context->argc != 2) return VM_ARITY;
        if (!IS_PTR(context->args[1]) ||
            cell_type(context->args[1]) != T_BUF) return VM_TYPEERROR;
        context->result = MKFIX((int16_t)buf_len(context->args[1]));
        return VM_OK;
    case 2: /* (buffer-ref buffer index) */
        if (context->argc != 3) return VM_ARITY;
        if (!IS_PTR(context->args[1]) ||
            cell_type(context->args[1]) != T_BUF ||
            !IS_FIX(context->args[2])) return VM_TYPEERROR;
        index = FIXVAL(context->args[2]);
        if (index < 0 || (uint16_t)index >= buf_len(context->args[1]))
            return VM_TYPEERROR;
        context->result = MKFIX((int16_t)buf_byte(
            context->args[1], (uint16_t)index));
        return VM_OK;
    case 3: /* (buffer-freeze buffer) */
        if (context->argc != 2) return VM_ARITY;
        if (!IS_PTR(context->args[1]) ||
            cell_type(context->args[1]) != T_BUF) return VM_TYPEERROR;
        context->result = buf_freeze(context->args[1]);
        return VM_OK;
    default:
        return VM_TYPEERROR;
    }
}

BUFFER_WRITE_ENTRY uint8_t lisp65_buffer_overlay_write_entry(void *opaque) {
    lisp65_buffer_overlay_context *context =
        (lisp65_buffer_overlay_context *)opaque;
    int16_t index, value;

    if (!buffer_context_valid(context)) return VM_BADOPCODE;
    context->result = NIL;
    if (context->argc != 3) return VM_ARITY;
    if (!IS_PTR(context->args[0]) ||
        cell_type(context->args[0]) != T_BUF ||
        !IS_FIX(context->args[1]) || !IS_FIX(context->args[2]))
        return VM_TYPEERROR;
    index = FIXVAL(context->args[1]);
    value = FIXVAL(context->args[2]);
    if (index < 0 || (uint16_t)index >=
            (uint16_t)FIXVAL(cell_a(context->args[0])) ||
        value < 0 || value > 255) return VM_TYPEERROR;
    buf_set(context->args[0], (uint16_t)index, (uint8_t)value);
    context->result = context->args[2];
    return VM_OK;
}

BUFFER_ALLOC_ENTRY uint8_t lisp65_buffer_overlay_alloc_entry(void *opaque) {
    lisp65_buffer_overlay_context *context =
        (lisp65_buffer_overlay_context *)opaque;
    obj buffer;
    int16_t operation;

    if (!buffer_context_valid(context)) return VM_BADOPCODE;
    context->result = NIL;
    if (!context->argc || !IS_FIX(context->args[0])) return VM_TYPEERROR;
    operation = FIXVAL(context->args[0]);
    if (context->argc != 2) return VM_ARITY;
#ifdef LISP65_C1_COMPILER_TIER
    if (operation == 0 || operation == 2) {
        /* make-buffer, or compiler staging window -> detached buffer */
        if (!IS_FIX(context->args[1]) || FIXVAL(context->args[1]) < 0)
            return VM_TYPEERROR;
        mem_oom = 0;
        buffer = operation == 0
            ? buf_make((uint16_t)FIXVAL(context->args[1]))
            : buf_from_stage((uint16_t)FIXVAL(context->args[1]));
    } else {
        if (operation != 1 && operation != 3) return VM_TYPEERROR;
        if (!IS_PTR(context->args[1]) ||
            cell_type(context->args[1]) !=
                (operation == 1 ? T_STR : T_BUF)) return VM_TYPEERROR;
        if (operation == 3) {
            context->result = MKFIX((int16_t)buf_to_stage(context->args[1]));
            return VM_OK;
        }
        mem_oom = 0;
        buffer = buf_from_string(context->args[1]);
    }
#else
    if (operation == 0) {
        if (!IS_FIX(context->args[1]) || FIXVAL(context->args[1]) < 0)
            return VM_TYPEERROR;
        mem_oom = 0;
        buffer = buf_make((uint16_t)FIXVAL(context->args[1]));
    } else {
        if (operation != 1) return VM_TYPEERROR;
        if (!IS_PTR(context->args[1]) ||
            cell_type(context->args[1]) != T_STR) return VM_TYPEERROR;
        mem_oom = 0;
        buffer = buf_from_string(context->args[1]);
    }
#endif
    if (buffer == NIL || mem_oom) return VM_HEAPOOM;
    context->result = buffer;
    return VM_OK;
}

#endif /* LISP65_FIRST_CLASS_BUFFER && !LISP65_BUFFER_NO_PRIMS */
