#ifndef LISP65_C1_COMPILER_OVERLAY_H
#define LISP65_C1_COMPILER_OVERLAY_H

#include <stdint.h>

#define LISP65_C1_COMPILER_OVERLAY_SLOT 43u

typedef enum {
    LISP65_C1_COMPILER_CHECKPOINT = 0,
    LISP65_C1_COMPILER_VALIDATE = 1,
    LISP65_C1_COMPILER_RETIRE = 2
} lisp65_c1_compiler_action;

uint8_t lisp65_c1_compiler_overlay_entry(void *context);

#endif /* LISP65_C1_COMPILER_OVERLAY_H */
