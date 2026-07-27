#include <stdint.h>
#include "c2_phase_scratch.h"
#include "c2_literal_cursor.h"

int main(void) {
    if (!c2_phase_scratch_pointer()) return 1;
    if (c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_NONE)) return 2;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_EMITTER)) return 3;
    if (c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 4;
    if (c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_EMITTER)) return 5;
    if (c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 6;
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER)) return 7;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 8;
    if (c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_EMITTER)) return 9;
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 10;
    if (!c2_literal_atom_handoff_valid(1u, 0u, 0u, 2u, 3u, 48u)) return 11;
    if (c2_literal_atom_handoff_valid(0u, 0u, 0u, 2u, 3u, 48u)) return 12;
    if (c2_literal_atom_handoff_valid(1u, 1u, 0u, 2u, 3u, 48u)) return 13;
    if (c2_literal_atom_handoff_valid(1u, 0u, 1u, 2u, 3u, 48u)) return 14;
    if (c2_literal_atom_handoff_valid(1u, 0u, 0u, 3u, 3u, 48u)) return 15;
    if (c2_literal_atom_handoff_valid(1u, 0u, 0u, 2u, 3u, 49u)) return 16;
    return 0;
}
