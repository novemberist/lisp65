#ifndef LISP65_C2_KERNAL_RUNTIME_H
#define LISP65_C2_KERNAL_RUNTIME_H

#include <stdint.h>

/* Product-owned event tuple.  The implementation samples code and modifiers
 * from one MEGA65 queue head and advances that head exactly once. */
typedef struct {
    uint8_t code;
    uint8_t modifiers;
} lisp65_key_event;

uint8_t c2_kernal_event_poll(lisp65_key_event *event);
uint8_t c2_kernal_take_ownership(void);
uint16_t c2_kernal_frame_count(void);

/* The frame counter is product-owned state in the mapped $e000 window, not a
 * second clock.  Cold overlay slices may sample the same cells inline so
 * their convergence loops remain in those slices instead of pulling the
 * handoff helper into resident Bank 0. */
#define LISP65_C2_FRAME_LO_ADDRESS 0xff83u
#define LISP65_C2_FRAME_HI_ADDRESS 0xff84u

#ifdef __mos__
static __attribute__((always_inline)) inline
uint16_t c2_kernal_frame_count_inline(void) {
    volatile const uint8_t *low_cell =
        (volatile const uint8_t *)LISP65_C2_FRAME_LO_ADDRESS;
    volatile const uint8_t *high_cell =
        (volatile const uint8_t *)LISP65_C2_FRAME_HI_ADDRESS;
    uint8_t high_a, low, high_b;
    do {
        high_a = *high_cell;
        low = *low_cell;
        high_b = *high_cell;
    } while (high_a != high_b);
    return (uint16_t)low | ((uint16_t)high_a << 8);
}
#endif

#define LISP65_KEYMOD_SHIFT   0x03u
#define LISP65_KEYMOD_CONTROL 0x04u
#define LISP65_KEYMOD_META    0x10u
#define LISP65_KEY_RUN_STOP   0x03u
/* The physical RUN/STOP source is matrix ordinal 63: segment 7, active-low
 * bit 7.  The typed queue remains the sole ordinary-key transport, but it is
 * not an abort authority.  This constant is source-bound to the pinned core
 * by the D3 gate; it is not a second keymap. */
#define LISP65_RUN_STOP_MATRIX_SEGMENT 7u

#endif /* LISP65_C2_KERNAL_RUNTIME_H */
