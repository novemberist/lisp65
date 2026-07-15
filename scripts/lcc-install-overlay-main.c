/* Focused host harness for the three-phase LCC installer overlay ABI. */
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "lcc_install_overlay.h"
#include "mem.h"
#include "reader.h"
#include "symbol.h"
#include "vm.h"

static uint8_t code_store[8192];
static uint16_t code_top;
static int failures;

obj car(obj value) { return IS_PTR(value) ? cell_a(value) : NIL; }
obj cdr(obj value) { return IS_PTR(value) ? cell_b(value) : NIL; }

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    (void)bank;
    memcpy(dst, code_store + off, length);
}

int lcc_region_alloc(uint16_t length, uint8_t *bank, uint16_t *off) {
    if ((uint32_t)code_top + length > sizeof code_store) return 0;
    *bank = 0;
    *off = code_top;
    code_top = (uint16_t)(code_top + length);
    return 1;
}

void lcc_region_write(uint8_t bank, uint16_t off,
                      const uint8_t *source, uint16_t length) {
    (void)bank;
    memcpy(code_store + off, source, length);
}

static void expect(int condition, const char *name) {
    printf("%-48s %s\n", name, condition ? "OK" : "FAIL");
    if (!condition) failures++;
}

static obj parse(const char *source) {
    const char *cursor = source;
    return read_expr(&cursor);
}

static lcc_install_status install(obj functions, obj name,
                                  lcc_install_result *result) {
    uint16_t base = gc_rootsp;
    lcc_install_status status;
    GC_PUSH(functions);
    GC_PUSH(name);
    status = lcc_install_overlay(functions, name, intern("t"),
                                 intern("%lcc-lit-keep"),
                                 intern("%lcc-helper"), result);
    gc_rootsp = base;
    return status;
}

static void reset_code(void) {
    memset(code_store, 0xcc, sizeof code_store);
    code_top = 0;
    vm_dir_reset();
    vm_status = VM_OK;
    lisp_error_msg = 0;
}

static void test_persistent(void) {
    lcc_install_result result;
    obj functions = parse("((0 0 0 () (1 42 0)))");
    obj name = intern("overlay-persistent");
    obj value;
    reset_code();
    expect(install(functions, name, &result) == LCC_INSTALL_OK,
           "persistent install status");
    expect(!result.transient && result.result == name,
           "persistent result and mode");
    expect(IS_BCODE(sym_function(name)), "persistent function publication");
    value = vm_run_dir((int)BCODE_IDX(sym_function(name)), NULL, 0);
    expect(vm_status == VM_OK && IS_FIX(value) && FIXVAL(value) == 42,
           "persistent bytecode executes");
}

static void test_transient(void) {
    lcc_install_result result;
    obj functions = parse("((0 0 0 () (1 37 0)))");
    obj value;
    uint16_t before;
    reset_code();
    before = vm_dir_count();
    expect(install(functions, intern("t"), &result) == LCC_INSTALL_OK,
           "transient install status");
    expect(result.transient && vm_dir_count() == before,
           "transient remains unpublished");
    value = vm_run(result.bank, result.off, result.length, NULL, 0);
    lcc_install_transient_pop(&result);
    expect(vm_status == VM_OK && IS_FIX(value) && FIXVAL(value) == 37,
           "transient runs after dispatch");
}

static void test_helper_marker(void) {
    lcc_install_result result;
    obj functions = parse(
        "((0 0 0 () (1 7 0)) (0 0 0 ((%lcc-helper 0)) (6 0 0)))");
    uint16_t main_off;
    obj value;
    reset_code();
    expect(install(functions, NIL, &result) == LCC_INSTALL_OK,
           "helper install status");
    expect(vm_dir_count() == 2 && IS_BCODE(result.result),
           "helper and main directory entries");
    main_off = 10u; /* helper is 10 bytes: 7-byte header plus three code bytes. */
    expect(code_store[main_off + CO_OFF_LITTAB] == (uint8_t)MK_BCODE(0) &&
           code_store[main_off + CO_OFF_LITTAB + 1] ==
               (uint8_t)((uint16_t)MK_BCODE(0) >> 8),
           "helper marker resolves to directory index");
    value = vm_run_dir((int)BCODE_IDX(result.result), NULL, 0);
    expect(vm_status == VM_OK && value == MK_BCODE(0),
           "resolved helper literal executes");
}

static void test_marker_recovery(void) {
    lcc_install_result result;
    obj invalid = parse("((0 0 0 ((%lcc-helper 0)) (0)))");
    obj valid = parse("((0 0 0 () (1 9 0)))");
    reset_code();
    expect(install(invalid, NIL, &result) == LCC_INSTALL_ERR_MARKER,
           "forward marker rejected");
    expect(lisp_error_msg == NULL, "slice error does not lisp_abort");
    expect(install(valid, NIL, &result) == LCC_INSTALL_OK,
           "marker error leaves installer reusable");
}

static void test_limits(void) {
    lcc_install_result result;
    char source[4096];
    char *p;
    unsigned i;

    p = source;
    p += sprintf(p, "((0 0 0 (");
    for (i = 0; i < LCC_INSTALL_MAX_LITS + 1u; i++) p += sprintf(p, "0 ");
    strcpy(p, ") (0)))");
    expect(install(parse(source), NIL, &result) == LCC_INSTALL_ERR_LITS,
           "literal count limit");

    p = source;
    p += sprintf(p, "((0 0 0 () (");
    for (i = 0; i < 249u; i++) p += sprintf(p, "0 ");
    strcpy(p, ")))");
    expect(install(parse(source), NIL, &result) == LCC_INSTALL_ERR_BLOB,
           "255-byte directory blob limit");

    p = source;
    p += sprintf(p, "((0 0 0 () (");
    for (i = 0; i < LCC_INSTALL_MAX_CODE + 1u; i++) p += sprintf(p, "0 ");
    strcpy(p, ")))");
    expect(install(parse(source), NIL, &result) == LCC_INSTALL_ERR_CODE,
           "code count limit");
}

static void test_cookie_and_reentry(void) {
    lcc_install_work work;
    memset(&work, 0, sizeof work);
    work.abi_version = LCC_INSTALL_OVERLAY_ABI_VERSION;
    work.cookie = 1;
    expect(lcc_install_phase_00(&work) == LCC_INSTALL_ERR_COOKIE,
           "bad cookie rejected");
    expect(!work.busy, "bad cookie does not leave busy state");
    memset(&work, 0, sizeof work);
    work.abi_version = LCC_INSTALL_OVERLAY_ABI_VERSION;
    work.cookie = LCC_INSTALL_OVERLAY_COOKIE_BASE;
    work.busy = 1;
    expect(lcc_install_phase_00(&work) == LCC_INSTALL_ERR_REENTRY,
           "work reentry rejected");
}

static void test_oom_recovery(void) {
    lcc_install_result result;
    obj functions = parse("((0 0 0 (17) (1 5 0)))");
    obj name = intern("overlay-oom");
    lcc_install_status status;
    uint16_t base = gc_rootsp;
    obj cell;
    reset_code();
    GC_PUSH(functions);
    GC_PUSH(name);
    gc_collect();
    while (GC_CAN_RESERVE(1) && mem_free_cells()) {
        cell = alloc(T_CONS);
        if (cell == NIL) break;
        GC_PUSH(cell);
    }
    expect(!mem_oom && mem_free_cells() == 0,
           "allocator is full before slice entry");
    status = lcc_install_overlay(functions, name, intern("t"),
                                 intern("%lcc-lit-keep"),
                                 intern("%lcc-helper"), &result);
    if (status != LCC_INSTALL_ERR_OOM)
        printf("    unexpected status=%u (%s), free=%u roots=%u gc=%u\n",
               (unsigned)status, lcc_install_status_message(status),
               (unsigned)mem_free_cells(), (unsigned)gc_rootsp,
               (unsigned)gc_runs);
    expect(status == LCC_INSTALL_ERR_OOM,
           "allocator OOM returns from slice");
    expect(mem_oom, "OOM was raised inside literal phase");
    expect(lisp_error_msg == NULL, "OOM slice does not lisp_abort");
    gc_rootsp = base;
    mem_oom = 0;
    gc_collect();
    functions = parse("((0 0 0 () (1 11 0)))");
    expect(install(functions, NIL, &result) == LCC_INSTALL_OK,
           "OOM leaves installer reusable");
}

int main(void) {
    mem_init();
    vm_init();
    (void)intern("%lcc-lit-keep");
    (void)intern("%lcc-helper");
    test_persistent();
    test_transient();
    test_helper_marker();
    test_marker_recovery();
    test_limits();
    test_cookie_and_reentry();
    test_oom_recovery();
    printf(failures ? "\nFAILED (%d)\n" : "\nALL PASS\n", failures);
    return failures ? 1 : 0;
}
