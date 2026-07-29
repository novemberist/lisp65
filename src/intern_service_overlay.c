/* Cold Session service: canonical string -> interned symbol conversion. */
#include "intern_service_overlay.h"

#ifdef LISP65_INTERN_SESSION_SERVICE

#include "mem.h"
#include "symbol.h"
#include "vm.h"

#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define INTERN_SERVICE_ENTRY \
    __attribute__((section(".lisp65_rt_intern_service"), noinline, used))
#else
#define INTERN_SERVICE_ENTRY
#endif

INTERN_SERVICE_ENTRY uint8_t lisp65_intern_service_entry(void *opaque) {
    lisp65_buffer_overlay_context *context =
        (lisp65_buffer_overlay_context *)opaque;
    uint16_t length;

    if (!context || !context->args) return VM_BADOPCODE;
    length = str_len(context->args[0]);
    if (length > LISP65_SYMBOL_NAME_MAX) return VM_TYPEERROR;
    str_copy_out(context->args[0], sym_name_scratch, length);
    sym_name_scratch[length] = '\0';
    context->result = intern(sym_name_scratch);
    return context->result == NIL || mem_oom ? VM_HEAPOOM : VM_OK;
}

#endif /* LISP65_INTERN_SESSION_SERVICE */
