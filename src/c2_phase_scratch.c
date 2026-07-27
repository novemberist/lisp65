#include "c2_phase_scratch.h"
#include "c2_kernal_layout.h"

#ifdef LISP65_C2_PRODUCT_CUT

uint8_t LISP65_C2_FIXED_BANK0("phase_scratch")
    lisp65_c2_phase_scratch[LISP65_C2_PHASE_SCRATCH_BYTES];
static uint8_t LISP65_C2_FIXED_ZP("phase_owner") c2_phase_owner;

uint8_t c2_phase_scratch_acquire(uint8_t owner) {
    if ((owner != LISP65_C2_PHASE_OWNER_EMITTER
            && owner != LISP65_C2_PHASE_OWNER_APPEND)
        || c2_phase_owner != LISP65_C2_PHASE_OWNER_NONE) return 0;
    c2_phase_owner = owner;
    return 1;
}

uint8_t c2_phase_scratch_release(uint8_t owner) {
    if (owner == LISP65_C2_PHASE_OWNER_NONE || c2_phase_owner != owner) return 0;
    c2_phase_owner = LISP65_C2_PHASE_OWNER_NONE;
    return 1;
}

#endif
