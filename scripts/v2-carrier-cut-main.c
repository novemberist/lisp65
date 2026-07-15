/* Focused CP4 host harness: no evaluator or Treewalk carrier is linked. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "eval.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"

static uint8_t code_store[256];
static int failures;

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    if ((uint16_t)(off + len) > sizeof(code_store)) {
        memset(dst, 0, len);
        return;
    }
    memcpy(dst, code_store + off, len);
}

/* This focused Workbench-shaped harness never invokes resident services. The
 * generic cut prerequisite is proven separately by each product inventory. */
uint8_t eval_v2_workbench_service(uint8_t id, const obj *args, obj *result) {
    (void)id; (void)args; (void)result;
    return 0;
}

#define CHECK(name, condition) do { \
    if (!(condition)) { fprintf(stderr, "v2-carrier-cut: FAIL %s status=%u\n", \
                                (name), (unsigned)vm_status); failures++; } \
} while (0)

static void put_obj(uint8_t *dst, obj value) {
    dst[0] = (uint8_t)((uint16_t)value & 0xffu);
    dst[1] = (uint8_t)((uint16_t)value >> 8);
}

static uint16_t emit_identity(uint16_t off) {
    uint8_t *p = code_store + off;
    memset(p, 0, 16);
    p[CO_OFF_MAGIC] = CO_MAGIC;
    p[CO_OFF_NARGS] = 1;
    p[CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    p[CO_OFF_CLEN] = 2;
    p[CO_OFF_NLITS] = 0;
    p[CO_OFF_LITTAB] = OP_PUSHARG0;
    p[CO_OFF_LITTAB + 1] = OP_RET;
    return (uint16_t)(CO_OFF_LITTAB + 2);
}

static uint16_t emit_call(uint16_t off, obj callee, uint8_t op, uint8_t nargs) {
    uint8_t *p = code_store + off;
    uint8_t i, pc = 0;
    memset(p, 0, 32);
    p[CO_OFF_MAGIC] = CO_MAGIC;
    p[CO_OFF_NARGS] = nargs;
    p[CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    p[CO_OFF_NLITS] = 1;
    put_obj(p + CO_OFF_LITTAB, callee);
    for (i = 0; i < nargs; i++)
        p[CO_OFF_LITTAB + 2 + pc++] = i == 0 ? OP_PUSHARG0 : OP_PUSHARG1;
    p[CO_OFF_LITTAB + 2 + pc++] = op;
    p[CO_OFF_LITTAB + 2 + pc++] = 0;
    p[CO_OFF_LITTAB + 2 + pc++] = nargs;
    p[CO_OFF_LITTAB + 2 + pc++] = OP_RET;
    p[CO_OFF_CLEN] = pc;
    return (uint16_t)(CO_OFF_LITTAB + 2 + pc);
}

static obj run_prim(uint8_t pid, const obj *args, uint8_t nargs) {
    uint16_t off = 128;
    uint8_t *p = code_store + off;
    uint8_t i, pc = 0;
    memset(p, 0, 32);
    p[CO_OFF_MAGIC] = CO_MAGIC;
    p[CO_OFF_NARGS] = nargs;
    p[CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    for (i = 0; i < nargs; i++)
        p[CO_OFF_LITTAB + pc++] = i == 0 ? OP_PUSHARG0 : i == 1 ? OP_PUSHARG1 : OP_PUSHARG2;
    p[CO_OFF_LITTAB + pc++] = OP_CALLPRIM;
    p[CO_OFF_LITTAB + pc++] = pid;
    p[CO_OFF_LITTAB + pc++] = nargs;
    p[CO_OFF_LITTAB + pc++] = OP_RET;
    p[CO_OFF_CLEN] = pc;
    vm_status = VM_OK;
    return vm_run(0, off, (uint16_t)(CO_OFF_LITTAB + pc), args, nargs);
}

static obj one(obj value) {
    return cons(value, NIL);
}

int main(void) {
    obj id = intern("cut-id"), missing = intern("cut-missing");
    obj bound = intern("cut-bound"), boundp = intern("boundp");
    obj direct_args[1] = {MKFIX(41)}, args[3], list_items[2], result, arglist;
    uint16_t id_len, call_off, call_len, missing_off, missing_len;

    mem_init(); vm_dir_reset(); vm_init();
    id_len = emit_identity(0);
    CHECK("directory add", vm_dir_add(id, 0, 0, id_len) == 0);
    set_sym_function(id, MK_BCODE(0));

    call_off = id_len;
    call_len = emit_call(call_off, id, OP_CALL, 1);
    vm_status = VM_OK;
    result = vm_run(0, call_off, call_len, direct_args, 1);
    CHECK("direct OP_CALL", vm_status == VM_OK && result == MKFIX(41));

    args[0] = id; args[1] = MKFIX(42);
    result = run_prim(8, args, 2);
    CHECK("CALLPRIM funcall", vm_status == VM_OK && result == MKFIX(42));

    args[0] = id;
    result = run_prim(8, args, 1);
    CHECK("CALLPRIM funcall strict arity", result == NIL && vm_status == VM_ARITY);

    arglist = one(MKFIX(43));
    args[0] = id; args[1] = arglist;
    result = run_prim(7, args, 2);
    CHECK("CALLPRIM apply", vm_status == VM_OK && result == MKFIX(43));

    args[0] = id; args[1] = NIL;
    result = run_prim(7, args, 2);
    CHECK("CALLPRIM apply strict arity", result == NIL && vm_status == VM_ARITY);

    list_items[0] = MKFIX(20); list_items[1] = MKFIX(12);
    arglist = cons(list_items[0], one(list_items[1]));
    args[0] = intern("+"); args[1] = MKFIX(10); args[2] = arglist;
    result = run_prim(7, args, 3);
    CHECK("CALLPRIM apply prefix", vm_status == VM_OK && result == MKFIX(42));

    args[0] = id; args[1] = MKFIX(46);
    result = run_prim(7, args, 2);
    CHECK("CALLPRIM apply dotted", result == NIL && vm_status == VM_TYPEERROR);

    arglist = one(MKFIX(44));
    args[0] = intern("apply"); args[1] = id; args[2] = arglist;
    result = run_prim(8, args, 3);
    CHECK("indirect apply designator", vm_status == VM_OK && result == MKFIX(44));

    arglist = cons(id, one(MKFIX(45)));
    args[0] = intern("funcall"); args[1] = arglist;
    result = run_prim(7, args, 2);
    CHECK("indirect funcall designator", vm_status == VM_OK && result == MKFIX(45));

    missing_off = 160;
    set_sym_value(bound, MKFIX(42));
    direct_args[0] = bound;
    result = run_prim(57, direct_args, 1);
    CHECK("boundp direct CALLPRIM route", vm_status == VM_OK && result == intern("t"));
    args[0] = boundp; args[1] = bound;
    result = run_prim(8, args, 2);
    CHECK("boundp funcall registry route", vm_status == VM_OK && result == intern("t"));
    arglist = one(bound);
    args[0] = boundp; args[1] = arglist;
    result = run_prim(7, args, 2);
    CHECK("boundp apply registry route", vm_status == VM_OK && result == intern("t"));

    args[0] = intern("%string-codes"); args[1] = NIL;
    result = run_prim(8, args, 2);
    CHECK("excluded primitive diagnostic",
          result == NIL && vm_status == VM_NOTDESIGNATOR &&
          vm_status_error_code(vm_status) == LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR);

    missing_len = emit_call(missing_off, missing, OP_CALL, 0);
    vm_status = VM_OK;
    result = vm_run(0, missing_off, missing_len, NULL, 0);
    CHECK("undefined directory miss", result == NIL && vm_status == VM_DIRMISS);

    missing_len = emit_call(missing_off, missing, OP_TAILCALL, 0);
    vm_status = VM_OK;
    result = vm_run(0, missing_off, missing_len, NULL, 0);
    CHECK("undefined tail directory miss", result == NIL && vm_status == VM_DIRMISS);

    if (failures) return 1;
    puts("v2-carrier-cut: PASS direct=2 funcall=2 apply=4 strict-arity=2 indirect=2 exclusion=1 dirmiss=2");
    return 0;
}
