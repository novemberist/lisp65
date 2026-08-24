#ifndef LISP65_PETSCII_NORMALIZATION_H
#define LISP65_PETSCII_NORMALIZATION_H

#include <stdint.h>

/* Defined by config/c2-v160-input-service-hybrid-contract.json.  Keep this
 * tiny range table as the sole C authority; the target assembler consumer
 * is checked against the same contract by the v1.6 hybrid gate. */
typedef struct {
    uint8_t first, last;
    int8_t delta;
    uint8_t modifiers;
} lisp65_petscii_normalization_rule;

#define LISP65_PETSCII_NORMALIZATION_ROWS(X) \
    X(0x41u, 0x5au,  0x20, 0u)             \
    X(0xc1u, 0xdau, -0x80, LISP65_KEYMOD_SHIFT) \
    X(0xa0u, 0xa0u, -0x80, 0u)

static inline uint8_t lisp65_normalize_petscii(
        uint8_t code, uint8_t *modifiers) {
    if (code >= 0x41u && code <= 0x5au) return (uint8_t)(code + 0x20u);
    if (code >= 0xc1u && code <= 0xdau) {
        *modifiers |= LISP65_KEYMOD_SHIFT;
        return (uint8_t)(code - 0x80u);
    }
    if (code == 0xa0u) return 0x20u;
    return code;
}

#endif
