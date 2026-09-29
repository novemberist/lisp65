/* Stable cursor contract between literal traversal and atom lowering. */
#ifndef LISP65_C2_LITERAL_CURSOR_H
#define LISP65_C2_LITERAL_CURSOR_H

#include <stdint.h>

static inline uint8_t c2_literal_atom_handoff_valid(
        uint8_t pending, uint8_t have, uint8_t done,
        uint16_t index, uint16_t count, uint8_t depth) {
    return (uint8_t)(pending == 1u && have == 0u && done == 0u
        && index < count && depth <= 48u);
}

#endif
