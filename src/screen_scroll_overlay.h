#ifndef LISP65_SCREEN_SCROLL_OVERLAY_H
#define LISP65_SCREEN_SCROLL_OVERLAY_H

#include <stdint.h>

#define LISP65_SCREEN_SCROLL_OVERLAY_SLOT 44u

typedef struct {
    uint16_t screen_base;
    uint16_t copy_bytes;
    uint8_t columns;
} lisp65_screen_scroll_context;

uint8_t lisp65_screen_scroll_overlay_entry(void *context);

#endif /* LISP65_SCREEN_SCROLL_OVERLAY_H */
