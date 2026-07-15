/* Native host smoke for evaluator-free Runtime Core boot and entry dispatch. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

static uint8_t ext_code[65536];

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    if (bank != 5 || (uint32_t)off + len > sizeof(ext_code)) return;
    memcpy(ext_code + off, src, len);
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    if (bank != 5 || (uint32_t)off + len > sizeof(ext_code)) {
        memset(dst, 0, len);
        return;
    }
    memcpy(dst, ext_code + off, len);
}

static int expect(const char *name, int condition) {
    if (condition) return 0;
    fprintf(stderr, "runtime-core-smoke: FAIL %s\n", name);
    return 1;
}

int main(void) {
    obj t, entry, fn, result, invalid_closure;
    int failed = 0;

    mem_init();
    vm_dir_reset();
    vm_init();
    t = intern("t");
    set_sym_value(t, t);
    vm_load_embedded_stdlib();
#ifdef LISP65_EXT_HEAP
    gc_freeze_boot();
#endif

#ifndef LISP65_V2_CARRIER_CUT
    failed |= expect("treewalk call hook remains null", vm_treewalk_call == 0);
    failed |= expect("treewalk apply hook remains null", vm_treewalk_apply == 0);
#endif
    failed |= expect("missing entry is not published", sym_function(intern("missing-entry")) == NIL);

    entry = intern("runtime-main");
    fn = sym_function(entry);
    failed |= expect("runtime-main is bytecode", IS_BCODE(fn));
    vm_status = VM_OK;
    result = vm_run_dir((int)BCODE_IDX(fn), 0, 0);
    failed |= expect("runtime-main status", vm_status == VM_OK);
    failed |= expect("runtime-main result", IS_FIX(result) && FIXVAL(result) == 42);

    vm_status = VM_OK;
    result = vm_native_apply(intern("runtime-inc"), MKFIX(7));
    failed |= expect("improper apply list result", result == NIL);
    failed |= expect("improper apply list status", vm_status == VM_TYPEERROR);

    invalid_closure = alloc(T_CLOSURE);
    cell_set_a(invalid_closure, MKFIX(1));
    cell_set_b(invalid_closure, NIL);
    vm_status = VM_OK;
    result = vm_native_apply(invalid_closure, NIL);
    failed |= expect("invalid closure result", result == NIL);
    failed |= expect("invalid closure status", vm_status == VM_TYPEERROR);

    if (failed) return 1;
#ifdef LISP65_V2_CARRIER_CUT
    printf("runtime-core-smoke: PASS result=42 carrier=cut errors=typeerror\n");
#else
    printf("runtime-core-smoke: PASS result=42 hooks=null errors=typeerror\n");
#endif
    return 0;
}
