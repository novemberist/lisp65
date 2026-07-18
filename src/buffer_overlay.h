#ifndef LISP65_BUFFER_OVERLAY_H
#define LISP65_BUFFER_OVERLAY_H

#include <stdint.h>

#include "obj.h"

#define LISP65_BUFFER_OVERLAY_ABI_VERSION 1u
#define LISP65_BUFFER_OVERLAY_READ_SLOT 40u
#define LISP65_BUFFER_OVERLAY_WRITE_SLOT 41u
#define LISP65_BUFFER_OVERLAY_ALLOC_SLOT 42u
#define LISP65_BUFFER_PRIM_READ 63u
#define LISP65_BUFFER_PRIM_WRITE 64u
#define LISP65_BUFFER_PRIM_ALLOC 65u
#define LISP65_C1_COMPILER_PRIM 66u
#define LISP65_BUFFER_PRIM_FIRST LISP65_BUFFER_PRIM_READ
#define LISP65_BUFFER_PRIM_LAST LISP65_C1_COMPILER_PRIM

typedef enum {
    LISP65_BUFFER_OVERLAY_OK = 0,
    LISP65_BUFFER_OVERLAY_ERR_CONTEXT
} lisp65_buffer_overlay_status;

/* The argument vector lives on the synchronous VM C stack for the complete
 * overlay call. Allocating operations root any individual Lisp value before
 * invoking GC; keeping the vector by pointer avoids seven copies in the
 * resident facade. */
typedef struct {
    obj *args;
    obj result;
    uint8_t argc;
} lisp65_buffer_overlay_context;

uint8_t lisp65_buffer_overlay_read_entry(void *context);
uint8_t lisp65_buffer_overlay_write_entry(void *context);
uint8_t lisp65_buffer_overlay_alloc_entry(void *context);

#endif /* LISP65_BUFFER_OVERLAY_H */
