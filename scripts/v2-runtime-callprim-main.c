/* Focused Runtime-Core host harness for dialect-v2 CALLPRIM 23..29. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mem.h"
#include "symbol.h"
#include "vm.h"

static uint8_t code_store[32];
static int failures;

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    if ((uint16_t)(off + len) > sizeof(code_store)) {
        memset(dst, 0, len);
        return;
    }
    memcpy(dst, code_store + off, len);
}

#define CHECK(name, condition) do { \
    if (!(condition)) { fprintf(stderr, "v2-runtime-callprim: FAIL %s\n", (name)); failures++; } \
} while (0)

static void fresh(void) {
    mem_init();
    mem_oom = 0;
    vm_dir_reset();
    vm_init();
#ifndef LISP65_V2_CARRIER_CUT
    vm_treewalk_call = NULL;
    vm_treewalk_apply = NULL;
#endif
}

static obj run_prim(uint8_t pid, const obj *args, uint8_t nargs) {
    uint8_t payload = 0;
    uint8_t i;
    memset(code_store, 0, sizeof(code_store));
    code_store[CO_OFF_MAGIC] = CO_MAGIC;
    code_store[CO_OFF_NARGS] = nargs;
    code_store[CO_OFF_NLOCS] = 0;
    code_store[CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    code_store[CO_OFF_NLITS] = 0;
    for (i = 0; i < nargs; i++) {
        code_store[CO_OFF_LITTAB + payload++] =
            i == 0 ? OP_PUSHARG0 : i == 1 ? OP_PUSHARG1 : OP_PUSHARG2;
    }
    code_store[CO_OFF_LITTAB + payload++] = OP_CALLPRIM;
    code_store[CO_OFF_LITTAB + payload++] = pid;
    code_store[CO_OFF_LITTAB + payload++] = nargs;
    code_store[CO_OFF_LITTAB + payload++] = OP_RET;
    code_store[CO_OFF_CLEN] = payload;
    code_store[CO_OFF_CLEN + 1] = 0;
    vm_status = VM_OK;
    return vm_run(0, 0, (uint16_t)(CO_OFF_LITTAB + payload), args, nargs);
}

static obj make_string(const char *text) {
    return str_from_bytes((const uint8_t *)text, (uint16_t)strlen(text));
}

static int string_equal(obj value, const char *expected) {
    uint16_t i;
    uint16_t len = (uint16_t)strlen(expected);
    if (!IS_PTR(value) || cell_type(value) != T_STR || str_len(value) != len) return 0;
    for (i = 0; i < len; i++) {
        if (str_byte(value, i) != (uint8_t)expected[i]) return 0;
    }
    return 1;
}

static obj list_from(const obj *items, uint8_t count) {
    obj list = NIL;
    uint8_t i;
    GC_PUSH(list);
    for (i = count; i > 0; i--) {
        list = cons(items[i - 1], gc_rootstack[GC_TOP]);
        GC_SET(GC_TOP, list);
    }
    GC_POPN(1);
    return list;
}

static void check_hooks(const char *name) {
#ifdef LISP65_V2_CARRIER_CUT
    (void)name;
#else
    CHECK(name, vm_treewalk_call == NULL && vm_treewalk_apply == NULL);
#endif
}

static void test_lists(void) {
    obj args[3], dotted, pair, result;
    fresh();
    dotted = cons(MKFIX(2), MKFIX(9));
    dotted = cons(MKFIX(1), dotted);
    args[0] = dotted;
    result = run_prim(23, args, 1);
    CHECK("nreverse-status", vm_status == VM_OK);
    CHECK("nreverse-result", IS_PTR(result) && FIXVAL(cell_a(result)) == 2
          && IS_PTR(cell_b(result)) && FIXVAL(cell_a(cell_b(result))) == 1
          && cell_b(cell_b(result)) == NIL);

    pair = cons(MKFIX(1), NIL);
    args[0] = pair; args[1] = MKFIX(7);
    result = run_prim(24, args, 2);
    CHECK("rplaca", vm_status == VM_OK && result == pair && cell_a(pair) == MKFIX(7));
    args[1] = MKFIX(8);
    result = run_prim(25, args, 2);
    CHECK("rplacd", vm_status == VM_OK && result == pair && cell_b(pair) == MKFIX(8));

    args[0] = NIL;
    result = run_prim(23, args, 1);
    CHECK("nreverse-non-cons", vm_status == VM_OK && result == NIL);
    (void)run_prim(23, args, 0);
    CHECK("nreverse-arity", vm_status == VM_ARITY);
    (void)run_prim(24, args, 1);
    CHECK("rplaca-arity", vm_status == VM_ARITY);
    args[0] = MKFIX(1); args[1] = MKFIX(2);
    (void)run_prim(24, args, 2);
    CHECK("rplaca-type", vm_status == VM_TYPEERROR);
    (void)run_prim(25, args, 2);
    CHECK("rplacd-type", vm_status == VM_TYPEERROR);
    args[2] = MKFIX(3);
    (void)run_prim(25, args, 3);
    CHECK("rplacd-arity", vm_status == VM_ARITY);
    check_hooks("list-hooks-null");
}

static void test_strings(void) {
    obj args[3], items[3], result, source, codes, it;
    uint8_t expected = (uint8_t)'a';
    fresh();
    source = make_string("abcdef");
    args[0] = source; args[1] = MKFIX(1); args[2] = MKFIX(4);
    (void)run_prim(26, args, 3);
    CHECK("slice-tombstone", vm_status == VM_BADOPCODE);

    items[0] = make_string("ab");
    items[1] = make_string("");
    items[2] = make_string("CD");
    args[0] = list_from(items, 3);
    result = run_prim(27, args, 1);
    CHECK("concat-tombstone", result == NIL && vm_status == VM_BADOPCODE);

    args[0] = source;
    codes = run_prim(28, args, 1);
    CHECK("codes-status", vm_status == VM_OK);
    for (it = codes; expected <= (uint8_t)'f'; expected++) {
        CHECK("codes-shape", IS_PTR(it) && cell_type(it) == T_CONS);
        if (!IS_PTR(it) || cell_type(it) != T_CONS) break;
        CHECK("codes-byte", cell_a(it) == MKFIX(expected));
        it = cell_b(it);
    }
    CHECK("codes-tail", it == NIL);
    args[0] = codes;
    result = run_prim(29, args, 1);
    CHECK("from-codes-status", vm_status == VM_OK);
    CHECK("from-codes-result", string_equal(result, "abcdef"));
    args[0] = MKFIX(1);
    (void)run_prim(28, args, 1);
    CHECK("codes-type", vm_status == VM_TYPEERROR);
    (void)run_prim(29, args, 0);
    CHECK("from-codes-arity", vm_status == VM_ARITY);
    check_hooks("string-hooks-null");
}

static void test_gc_and_arena_oom(void) {
    static const uint8_t payload[24] = {
        'x','x','x','x','x','x','x','x','x','x','x','x',
        'x','x','x','x','x','x','x','x','x','x','x','x'
    };
    obj args[1], dead, resident, result, code_items[24];
    uint8_t i;
    fresh();
    dead = make_string("012345678901234567890123456789012345678901234567");
    (void)dead;
    for (i = 0; i < sizeof(payload); i++) code_items[i] = MKFIX(payload[i]);
    args[0] = list_from(code_items, sizeof(payload));
    result = run_prim(29, args, 1);
    CHECK("codec-construction-gc", vm_status == VM_OK && gc_runs != 0
          && string_equal(result, "xxxxxxxxxxxxxxxxxxxxxxxx"));

    fresh();
    resident = make_string("012345678901234567890123456789012345678901234567");
    GC_PUSH(resident);
    for (i = 0; i < sizeof(payload); i++) code_items[i] = MKFIX(payload[i]);
    args[0] = list_from(code_items, sizeof(payload));
    result = run_prim(29, args, 1);
    CHECK("codec-arena-oom", result == NIL && vm_status == VM_HEAPOOM && mem_oom == 1);
    CHECK("codec-arena-oom-no-observable-partial",
          string_equal(resident, "012345678901234567890123456789012345678901234567"));
    GC_POPN(1);
    check_hooks("gc-oom-hooks-null");
}

static void test_heap_oom(void) {
    obj args[1], codes, chain = NIL;
    fresh();
    codes = cons(MKFIX('z'), NIL);
    GC_PUSH(codes);
    GC_PUSH(chain);
    while (mem_free_cells() != 0) {
        chain = cons(MKFIX(1), chain);
        GC_SET(GC_TOP, chain);
    }
    args[0] = codes;
    (void)run_prim(29, args, 1);
    CHECK("codec-heap-oom", vm_status == VM_HEAPOOM && mem_oom == 1);
    GC_POPN(2);
}

static void test_tombstones_and_visibility(void) {
    obj args[3], apply_args[3], arglist, source, result;
    fresh();
    source = make_string("abc");
    args[0] = source;
    (void)run_prim(1, args, 1);
    CHECK("string-to-list-tombstone", vm_status == VM_BADOPCODE);
    args[0] = NIL;
    (void)run_prim(2, args, 1);
    CHECK("list-to-string-tombstone", vm_status == VM_BADOPCODE);
    args[0] = source; args[1] = MKFIX(0); args[2] = MKFIX(1);
    (void)run_prim(26, args, 3);
    CHECK("string-slice-tombstone", vm_status == VM_BADOPCODE);
    args[0] = NIL;
    (void)run_prim(27, args, 1);
    CHECK("string-concat-tombstone", vm_status == VM_BADOPCODE);
    vm_status = VM_OK;
    result = vm_native_apply(intern("string->list"), cons(source, NIL));
    CHECK("string-to-list-not-function-designator",
          result == NIL && vm_status == VM_TYPEERROR);
    vm_status = VM_OK;
    result = vm_native_apply(intern("list->string"), cons(NIL, NIL));
    CHECK("list-to-string-not-function-designator",
          result == NIL && vm_status == VM_TYPEERROR);
    (void)run_prim(30, args, 0);
    CHECK("workbench-service-profile-disabled", vm_status == VM_BADOPCODE);

    apply_args[0] = source; apply_args[1] = MKFIX(0); apply_args[2] = MKFIX(1);
    arglist = list_from(apply_args, 3);
    vm_status = VM_OK;
    result = vm_native_apply(intern("%string-slice"), arglist);
    CHECK("slice-not-function-designator", result == NIL && vm_status == VM_TYPEERROR);
    arglist = cons(NIL, NIL);
    vm_status = VM_OK;
    result = vm_native_apply(intern("%string-concat-list"), arglist);
    CHECK("concat-not-function-designator", result == NIL && vm_status == VM_TYPEERROR);
    vm_status = VM_OK;
    result = vm_native_apply(intern("%string-codes"), cons(source, NIL));
    CHECK("codes-not-function-designator",
          result == NIL && vm_status == VM_NOTDESIGNATOR &&
          vm_status_error_code(vm_status) == LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR);
    vm_status = VM_OK;
    result = vm_native_apply(intern("%string-from-codes"), arglist);
    CHECK("from-codes-not-function-designator",
          result == NIL && vm_status == VM_NOTDESIGNATOR &&
          vm_status_error_code(vm_status) == LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR);
    check_hooks("visibility-hooks-null");
}

int main(void) {
    test_lists();
    test_strings();
    test_gc_and_arena_oom();
    test_heap_oom();
    test_tombstones_and_visibility();
    if (failures) {
        fprintf(stderr, "v2-runtime-callprim: %d failure(s)\n", failures);
        return 1;
    }
    puts("v2-runtime-callprim: PASS active=23..25,28..29 tombstones=1,2,26,27");
    return 0;
}
