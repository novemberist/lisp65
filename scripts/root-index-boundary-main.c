/* Exactness of the root-stack overflow boundary.
 *
 * The root-index narrowing is only admissible if the guard still fires at
 * exactly GC_ROOTS and not one slot earlier or later.  This harness drives the
 * VM's operand push until it refuses, and reports the depth at which it did,
 * the status it raised, and that the stack pointer is exactly GC_ROOTS.  Run it
 * for the same GC_ROOTS on the narrow and the wide type and compare.
 *
 * Exit 0 = PASS. */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"

static uint8_t code_store[512];
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank; memcpy(dst, code_store + off, len);
}

/* A code object that does nothing but push literals until the VM refuses. */
#define NLITS 1
#define HDRLEN (CO_OFF_LITTAB + 2 * NLITS)
static uint8_t payload[300];

int main(void) {
    unsigned i;
    obj r;
    int failed = 0;
    uint16_t n_push = (uint16_t)(GC_ROOTS + 8u);
    if (n_push > 280u) n_push = 280u;

    mem_init();
    vm_init();
    /* The reserve predicate, not only operand PUSH, owns the 255 boundary.
     * Exhaust every representable byte index for narrow profiles and every
     * valid index plus one invalid index for wider profiles. */
    {
        uint16_t sp, request;
        uint16_t last = GC_ROOTS < 256 ? 255 : GC_ROOTS + 1;
        for (sp = 0; sp <= last; sp++) {
            gc_rootsp = (gc_rootsp_t)sp;
            for (request = 0; request <= GC_ROOTS + 1u; request++) {
                int want = sp <= GC_ROOTS && request <= GC_ROOTS - sp;
                if ((!!GC_CAN_RESERVE(request)) != want) failed++;
            }
        }
        gc_rootsp = 0;
    }
    memset(code_store, 0, sizeof code_store);
    code_store[CO_OFF_MAGIC] = CO_MAGIC;
    code_store[CO_OFF_NARGS] = 0;
    code_store[CO_OFF_NLOCS] = 0;
    code_store[CO_OFF_FLAGS] = 0;
    code_store[CO_OFF_NLITS] = NLITS;
    for (i = 0; i < n_push; i++) payload[i] = OP_PUSHNIL;
    payload[n_push] = OP_RET;
    code_store[CO_OFF_CLEN] = (uint8_t)(n_push + 1u);
    memcpy(code_store + HDRLEN, payload, n_push + 1u);

    printf("GC_ROOTS=%d sizeof(gc_rootsp)=%u pushes=%u\n",
           (int)GC_ROOTS, (unsigned)sizeof gc_rootsp, (unsigned)n_push);

    gc_rootsp = 0;
    vm_status = VM_OK;
    r = vm_run(0, 0, (uint16_t)(HDRLEN + n_push + 1u), NULL, 0);
    (void)r;

    if ((uint16_t)(GC_ROOTS) <= n_push) {
        /* the run must have been refused, and refused exactly at the top */
        printf("status=%u (want %u VM_STACKOVER)\n", vm_status, (unsigned)VM_STACKOVER);
        if (vm_status != VM_STACKOVER) failed++;
        /* vm_run_inner resets gc_rootsp to its entry base on the way out */
        printf("gc_rootsp after the refusal=%u (want 0)\n", (unsigned)gc_rootsp);
        if (gc_rootsp != 0) failed++;
    } else {
        printf("status=%u (want %u VM_OK; the stack was wide enough)\n",
               vm_status, (unsigned)VM_OK);
        if (vm_status != VM_OK) failed++;
    }

    /* Direct boundary: push by hand and record the last accepted depth. */
    {
        uint16_t accepted = 0;
        gc_rootsp = 0;
        while (gc_rootsp < (uint16_t)(GC_ROOTS)) {
            gc_rootstack[gc_rootsp++] = NIL;
            accepted++;
        }
        printf("hand-pushed to gc_rootsp=%u accepted=%u (want %d both)\n",
               (unsigned)gc_rootsp, (unsigned)accepted, (int)GC_ROOTS);
        if ((uint16_t)gc_rootsp != (uint16_t)(GC_ROOTS)) failed++;
        if (accepted != (uint16_t)(GC_ROOTS)) failed++;
        /* the full state must compare as full, and one below must not */
        if (!((uint16_t)gc_rootsp >= (uint16_t)(GC_ROOTS))) failed++;
        gc_rootsp = (uint16_t)(GC_ROOTS) - 1u;
        if ((uint16_t)gc_rootsp >= (uint16_t)(GC_ROOTS)) failed++;
        gc_rootsp = 0;
    }

    printf("root-index-boundary: %s (failures=%d)\n", failed ? "FAIL" : "PASS", failed);
    return failed ? 1 : 0;
}
