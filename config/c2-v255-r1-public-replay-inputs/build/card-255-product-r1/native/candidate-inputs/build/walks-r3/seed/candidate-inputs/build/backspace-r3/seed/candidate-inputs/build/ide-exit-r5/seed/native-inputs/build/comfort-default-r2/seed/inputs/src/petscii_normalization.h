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

/* Owner decision 2026-09-08: the `£` key (PETSCII $5C) is the device
 * quasiquote character.  PETSCII $5C and ASCII backslash 0x5C are the same
 * code, so the input service needs NO mapping — it only has to keep passing
 * the byte through untouched, so the reader (src/reader.c) sees 0x5C and
 * reads it as quasiquote sugar.  The three normalization rows below cover
 * $41..$5a, $c1..$da and $a0 only; $5c lies outside all three.  The typedef
 * below fails the build closed if a future row is ever widened over it. */
#define LISP65_PETSCII_QUASIQUOTE 0x5cu

#define LISP65_PETSCII_NORMALIZATION_ROWS(X) \
    X(0x41u, 0x5au,  0x20, 0u)             \
    X(0xc1u, 0xdau, -0x80, LISP65_KEYMOD_SHIFT) \
    X(0xa0u, 0xa0u, -0x80, 0u)

#define LISP65_QUASIQUOTE_OUTSIDE_ROW(first, last, delta, modifiers) \
    && (LISP65_PETSCII_QUASIQUOTE < (first) || LISP65_PETSCII_QUASIQUOTE > (last))
typedef char lisp65_petscii_quasiquote_stays_unmapped[
    (1 LISP65_PETSCII_NORMALIZATION_ROWS(LISP65_QUASIQUOTE_OUTSIDE_ROW)) ? 1 : -1];
#undef LISP65_QUASIQUOTE_OUTSIDE_ROW

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
