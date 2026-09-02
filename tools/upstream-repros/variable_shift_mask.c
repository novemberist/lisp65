/*
 * Negative re-verification for historical lisp65 finding L1.
 *
 * This reproduces both the reduced expression and the original bitmap update
 * shape.  Exit 0 means every mask and cumulative bitmap byte was correct.
 */
#include <stdint.h>
#include <stdlib.h>

static volatile uint16_t input;
static volatile uint8_t observed[8];
static volatile uint8_t marks[8];

__attribute__((noinline))
static uint8_t variable_mask(uint16_t value) {
    return (uint8_t)(1u << (value & 7u));
}

__attribute__((noinline))
static void mark_bit(uint16_t value) {
    marks[value >> 3] |= 1u << (value & 7u);
}

int main(void) {
    static const uint8_t expected[8] = {
        1u, 2u, 4u, 8u, 16u, 32u, 64u, 128u
    };

    for (uint8_t i = 0; i != 8; ++i) {
        input = i;
        observed[i] = variable_mask(input);
        if (observed[i] != expected[i])
            exit((int)i + 1);
        mark_bit(input);
        if (marks[0] != (uint8_t)((1u << (i + 1u)) - 1u))
            exit((int)i + 9);
    }
    return 0;
}
