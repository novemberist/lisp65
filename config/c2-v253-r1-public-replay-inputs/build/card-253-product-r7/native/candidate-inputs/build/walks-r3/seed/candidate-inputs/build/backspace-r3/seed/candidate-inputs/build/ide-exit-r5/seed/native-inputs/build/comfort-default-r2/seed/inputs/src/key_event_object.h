/* Shared Lisp representation of one normalized keyboard event. */
#ifndef LISP65_KEY_EVENT_OBJECT_H
#define LISP65_KEY_EVENT_OBJECT_H

#include "c2_kernal_runtime.h"
#include "mem.h"
#include "petscii_normalization.h"

static __attribute__((always_inline)) inline obj
lisp65_key_event_object(int code, uint8_t event_modifiers,
                        obj key, obj shift, obj control, obj meta) {
    obj modifiers = NIL, event;
    code = lisp65_normalize_petscii((uint8_t)code, &event_modifiers);
    if (event_modifiers & LISP65_KEYMOD_SHIFT)
        modifiers = cons(shift, modifiers);
    if (event_modifiers & LISP65_KEYMOD_CONTROL)
        modifiers = cons(control, modifiers);
    if (event_modifiers & LISP65_KEYMOD_META)
        modifiers = cons(meta, modifiers);
    GC_PUSH(modifiers);
    event = cons(gc_rootstack[GC_TOP], NIL);
    GC_SET(GC_TOP, event);
    event = cons(MKFIX((int16_t)code), gc_rootstack[GC_TOP]);
    GC_SET(GC_TOP, event);
    event = cons(key, gc_rootstack[GC_TOP]);
    GC_POPN(1);
    return event;
}

#endif /* LISP65_KEY_EVENT_OBJECT_H */
