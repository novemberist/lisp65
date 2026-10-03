/* One product emitter for interactive and persistent C2I-v2 images. */
#ifndef LISP65_C2_SESSION_EMITTER_H
#define LISP65_C2_SESSION_EMITTER_H

#include <stdint.h>
#include "obj.h"

typedef enum {
    C2_EMIT_OK = 0,
    C2_EMIT_ARGUMENT,
    C2_EMIT_STATE,
    C2_EMIT_SHAPE,
    C2_EMIT_ENTRIES,
    C2_EMIT_LITERALS,
    C2_EMIT_STRINGS,
    C2_EMIT_OUTPUT,
    C2_EMIT_UNSUPPORTED
} c2_emit_status;

/* Reset/add/finalize is the one state machine used by both call sites.
 * finalize leaves the exact one-record L65S-v4/C2I-v2 artifact at the
 * compiler staging-window origin and returns its byte length. */
c2_emit_status c2_session_emit_reset(void);
c2_emit_status c2_session_emit_add(obj fnlist, obj export_name,
                                    uint8_t export_flags);
c2_emit_status c2_session_emit_finalize(uint16_t *length);

/* Lisp private service (operation, payload): 0 reset; 1 add the payload
 * (fnlist name flags); 2 finalize and return a detached Buffer. */
obj c2_session_emit_control(obj operation, obj payload);

#endif
