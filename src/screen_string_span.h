/* One implementation for the tree and VM screen-write-string primitives. */
#ifndef LISP65_SCREEN_STRING_SPAN_H
#define LISP65_SCREEN_STRING_SPAN_H

#include "mem.h"
#include "screen.h"

static __attribute__((always_inline)) inline void
lisp65_screen_write_string_span(uint8_t x, uint8_t y, obj string,
                                int16_t attribute) {
    char buffer[80];
    uint8_t count = 0;
#ifdef LISP65_STRING_ARENA
    count = (uint8_t)str_copy_out(string, buffer, sizeof buffer);
#else
    obj cells;
    for (cells = cell_a(string);
         IS_PTR(cells) && cell_type(cells) == T_CONS && count < sizeof buffer;
         cells = cell_b(cells))
        buffer[count++] = (char)FIXVAL(cell_a(cells));
#endif
    scr_write_span(x, y, buffer, count,
                   (attribute >= 0 && (attribute & 0x40)) ? scr_cols() : 0,
                   (attribute >= 0) ? (attribute & ~0x40) : attribute);
}

#endif /* LISP65_SCREEN_STRING_SPAN_H */
