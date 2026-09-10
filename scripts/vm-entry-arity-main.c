/* Host-only strict-arity coverage of direct and tail callee entry. */
#define main status_probe_main
#include "vm-entry-status-main.c"
#undef main

unsigned arity_checks;

static void object_at(unsigned off, unsigned nargs, obj literal,
                      const uint8_t *ops, unsigned count) {
    code_store[off + CO_OFF_MAGIC] = CO_MAGIC;
    code_store[off + CO_OFF_NARGS] = nargs;
    code_store[off + CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    code_store[off + CO_OFF_CLEN] = count;
    code_store[off + CO_OFF_NLITS] = 1;
    code_store[off + CO_OFF_LITTAB] = (uint16_t)literal;
    code_store[off + CO_OFF_LITTAB + 1] = (uint16_t)literal >> 8;
    memcpy(code_store + off + HDRLEN, ops, count);
}

/* Three routes into the one shared callee entry, and each must run exactly one
 * arity check per Lisp frame it enters:
 *   mode 0  the function prologue (vm_run's own callee)
 *   mode 1  OP_TAILCALL  (frame reuse)
 *   mode 2  OP_CALL to a directory callee.  Natively that is a nested
 *           vm_run_inner activation; under LISP65_VM_SOFT_FRAMES (R2) it is a
 *           soft-frame push into the same activation.  Either way the callee is
 *           entered once and gates once, which is what this mode pins. */
enum { MODE_ENTRY = 0, MODE_TAIL = 1, MODE_CALL = 2, MODE_COUNT = 3 };

int main(void) {
    unsigned mode, actual, i;
    obj args[2] = { MKFIX(7), MKFIX(8) };
    for (mode = 0; mode < MODE_COUNT; mode++) for (actual = 0; actual < 3; actual++) {
        uint8_t ops[8]; unsigned n = 0;
        obj name; int di;
        unsigned want_checks, want_bridge;
        mem_init(); vm_init(); vm_dir_reset(); vm_treewalk_call = bridge;
        memset(code_store, 0, sizeof code_store);
        object_at(32, 1, intern("not-compiled"), payload, sizeof payload);
        name = intern("callee"); di = vm_dir_add(name, 0, 32, OBJLEN);
        if (di < 0) return 2;
        for (i = 0; i < actual; i++) { ops[n++] = OP_PUSHI8; ops[n++] = 7; }
        if (mode == MODE_CALL) { ops[n++] = OP_CALL; ops[n++] = 0; ops[n++] = actual; }
        else                   { ops[n++] = OP_TAILCALL; ops[n++] = 0; ops[n++] = actual; }
        ops[n++] = OP_RET;
        object_at(0, 0, MK_BCODE(di), ops, n);
        gc_rootsp = 0; vm_status = VM_OK; bridge_calls = arity_checks = 0;
        (void)vm_run(0, mode == MODE_ENTRY ? 32 : 0,
                     mode == MODE_ENTRY ? OBJLEN : (uint16_t)(HDRLEN + n),
                     mode == MODE_ENTRY ? args : NULL,
                     mode == MODE_ENTRY ? (uint8_t)actual : 0);
        /* mode 0 gates once (the entered callee); modes 1 and 2 gate twice
         * (the outer object's own entry, then the callee's). */
        want_checks = (mode == MODE_ENTRY) ? 1u : 2u;
        /* The callee's body tail-calls an uncompiled symbol, so the bridge runs
         * exactly when the callee was actually entered. */
        want_bridge = (actual == 1);
        printf("mode=%u actual=%u status=%u checks=%u bridge=%u roots=%u\n",
               mode, actual, vm_status, arity_checks, bridge_calls, gc_rootsp);
        if (arity_checks != want_checks || gc_rootsp != 0 ||
            vm_status != (actual == 1 ? VM_OK : VM_ARITY) ||
            bridge_calls != want_bridge) return 1;
    }
    return 0;
}
