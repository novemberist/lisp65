/* Focused ASAN/UBSAN harness for v2 Workbench CALLPRIM services 30..56. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "eval.h"
#include "interrupt.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"

static uint8_t code_store[64];
static int failures;

/* Device-owned seams are deterministic stubs in this focused host harness. */
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
    (void)track; (void)sector; return 0;
}
unsigned char io_disk_byte(unsigned char index) { return ext_disk_get(index); }
unsigned char io_disk_load_chain(unsigned char track, unsigned char sector) {
    (void)track; (void)sector; return 0;
}
void io_disk_scratch_poke(unsigned char index, unsigned char value) {
    ext_disk_put(index, value);
}
unsigned char io_disk_write_sector(unsigned char track, unsigned char sector) {
    (void)track; (void)sector; return 0;
}
void io_disk_transaction_capture_mount_token(void) {}
unsigned char io_disk_transaction_classify_status(unsigned char status) {
    return status;
}
unsigned char io_disk_write_sector_guarded(unsigned char track, unsigned char sector) {
    return io_disk_write_sector(track, sector);
}
unsigned char io_disk_stage_put(unsigned int index, unsigned char value) {
    ext_disk_put((uint16_t)index, value); return 1;
}
unsigned char io_disk_save_named(const char *name, unsigned int length) {
    (void)name; (void)length; return 0;
}
const char *io_load_file(const char *name) { (void)name; return NULL; }
int lcc_region_alloc(uint16_t length, uint8_t *bank, uint16_t *off) {
    (void)length; (void)bank; (void)off; return 0;
}
void lcc_region_write(uint8_t bank, uint16_t off,
                      const uint8_t *source, uint16_t length) {
    (void)bank; (void)off; (void)source; (void)length;
}
uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    (void)code; (void)symbol; return 0;
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    if ((uint16_t)(off + len) > sizeof(code_store)) {
        memset(dst, 0, len); return;
    }
    memcpy(dst, code_store + off, len);
}

#define CHECK(name, condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "v2-workbench-services: FAIL %s\n", (name)); failures++; \
    } \
} while (0)

static uint16_t emit_prim_call(uint16_t offset, uint8_t pid, uint8_t nargs) {
    uint8_t payload = 0, index;
    code_store[offset + CO_OFF_MAGIC] = CO_MAGIC;
    code_store[offset + CO_OFF_NARGS] = nargs;
    code_store[offset + CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    for (index = 0; index < nargs; index++) {
        code_store[offset + CO_OFF_LITTAB + payload++] =
            index == 0 ? OP_PUSHARG0 : index == 1 ? OP_PUSHARG1 : OP_PUSHARG2;
    }
    code_store[offset + CO_OFF_LITTAB + payload++] = OP_CALLPRIM;
    code_store[offset + CO_OFF_LITTAB + payload++] = pid;
    code_store[offset + CO_OFF_LITTAB + payload++] = nargs;
    code_store[offset + CO_OFF_LITTAB + payload++] = OP_RET;
    code_store[offset + CO_OFF_CLEN] = payload;
    return (uint16_t)(CO_OFF_LITTAB + payload);
}

static obj run_prim(uint8_t pid, const obj *args, uint8_t nargs) {
    uint16_t length;
    memset(code_store, 0, sizeof(code_store));
    length = emit_prim_call(0, pid, nargs);
    vm_status = VM_OK;
    return vm_run(0, 0, length, args, nargs);
}

static int string_equal(obj value, const char *expected) {
    uint16_t index, length = (uint16_t)strlen(expected);
    if (!IS_PTR(value) || cell_type(value) != T_STR || str_len(value) != length)
        return 0;
    for (index = 0; index < length; index++)
        if (str_byte(value, index) != (uint8_t)expected[index]) return 0;
    return 1;
}

static void test_internal_symbol_name_cap(void) {
    static const char name32[] = "12345678901234567890123456789012";
    static const char name33[] = "123456789012345678901234567890123";
    static const char name34[] = "1234567890123456789012345678901234";
    uint16_t before;
    obj symbol;

    symbol = intern(name32);
    CHECK("internal symbol name length 32", symbol != NIL &&
          strcmp(symname(symbol), name32) == 0);
    symbol = intern(name33);
    CHECK("internal symbol name length 33", symbol != NIL &&
          strcmp(symname(symbol), name33) == 0);
    before = sym_count();
    lisp65_error_clear();
    symbol = intern(name34);
    CHECK("internal symbol name length 34 rejected", symbol == NIL &&
          lisp65_error_pending_code() == LISP65_ERR_TOO_MANY_SYMBOLS &&
          sym_count() == before);
    lisp65_error_clear();
}

static void test_arities(void) {
    static const uint8_t arity[16] = {
        1, 0, 2, 1, 2, 2, 1, 0, 2, 1, 1, 1, 0, 0, 1, 1
    };
    obj args[3] = {NIL, NIL, NIL};
    uint8_t id;
    for (id = 30; id <= 45; id++) {
        if (id == 40) continue;
        uint8_t wrong = arity[id - 30] == 0 ? 1 : 0;
        (void)run_prim(id, args, wrong);
        CHECK("native-service exact arity", vm_status == VM_ARITY);
    }
    for (id = 46; id <= 56; id++) {
        (void)run_prim(id, args, 1);
        CHECK("error-service exact arity", vm_status == VM_ARITY);
    }
}

static void test_native_services(void) {
    obj args[2], result, source, name;

    source = str_from_bytes((const uint8_t *)"42", 2);
    GC_PUSH(source);
    args[0] = source;
    result = run_prim(30, args, 1);
    CHECK("cs-read-open", vm_status == VM_OK && result != NIL);
    result = run_prim(31, args, 0);
    CHECK("fasl-read-form", vm_status == VM_OK && result == MKFIX(42));
    GC_POPN(1);

    args[0] = MKFIX(0); args[1] = MKFIX(65);
    result = run_prim(32, args, 2);
    CHECK("fasl-stage", vm_status == VM_OK && result != NIL);
    result = run_prim(33, args, 1);
    CHECK("fasl-stage-get", vm_status == VM_OK && result == MKFIX(65));

    source = str_from_bytes((const uint8_t *)"test", 4);
    args[0] = source; args[1] = MKFIX(0);
    result = run_prim(34, args, 2);
    CHECK("save-staged tombstone", vm_status == VM_BADOPCODE && result == NIL);

    name = intern("service-macro");
    args[0] = name; args[1] = MK_BCODE(0);
    result = run_prim(35, args, 2);
    CHECK("set-macro", vm_status == VM_OK && result == name);
    args[0] = name;
    result = run_prim(36, args, 1);
    CHECK("function-kind", vm_status == VM_OK && result == intern("macro"));

    result = run_prim(37, args, 0);
    CHECK("gensym", vm_status == VM_OK && IS_PTR(result) && cell_type(result) == T_SYM);

    args[0] = MKFIX(7);
    result = run_prim(39, args, 1);
    CHECK("macroexpand atom", vm_status == VM_OK && result == MKFIX(7));
    args[0] = MKFIX(-123);
    result = run_prim(40, args, 1);
    CHECK("number-to-string tombstone", vm_status == VM_BADOPCODE && result == NIL);
    args[0] = MKFIX(7);
    result = run_prim(41, args, 1);
    CHECK("prin1", vm_status == VM_OK && result == MKFIX(7));
    result = run_prim(42, args, 0);
    CHECK("symbol-count", vm_status == VM_OK && IS_FIX(result));
    result = run_prim(43, args, 0);
    CHECK("symbol-max", vm_status == VM_OK && IS_FIX(result));
    args[0] = name;
    result = run_prim(44, args, 1);
    CHECK("symbol-name", vm_status == VM_OK && string_equal(result, "service-macro"));
    args[0] = MKFIX('!');
    result = run_prim(45, args, 1);
    CHECK("write-char", vm_status == VM_OK && result == MKFIX('!'));

    /* lcc-install requires a valid emitted function-list artifact for success;
     * exact arity is covered above and its full semantics remain in the existing
     * lcc-install overlay smoke rather than being faked here. */
}

static void test_macroexpand_bcode_cut(void) {
    const uint16_t expansion_offset = 32;
    obj macro_name, macro, argument, tail, form, args[1], result;
    uint16_t caller_length, expansion_length;
    int directory_index;

    memset(code_store, 0, sizeof(code_store));
    code_store[expansion_offset + CO_OFF_MAGIC] = CO_MAGIC;
    code_store[expansion_offset + CO_OFF_NARGS] = 1;
    code_store[expansion_offset + CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    code_store[expansion_offset + CO_OFF_CLEN] = 2;
    code_store[expansion_offset + CO_OFF_LITTAB] = OP_PUSHARG0;
    code_store[expansion_offset + CO_OFF_LITTAB + 1] = OP_RET;
    expansion_length = (uint16_t)(CO_OFF_LITTAB + 2);

    macro_name = intern("service39-bcode-macro");
    directory_index = vm_dir_add(intern("service39-expansion"), 0,
                                 expansion_offset, expansion_length);
    CHECK("macroexpand BCODE directory", directory_index >= 0);
    macro = alloc(T_MACRO);
    CHECK("macroexpand BCODE macro allocation", macro != NIL);
    if (directory_index < 0 || macro == NIL) return;
    cell_set_a(macro, MK_BCODE(directory_index));
    cell_set_b(macro, NIL);
    set_sym_function(macro_name, macro);

    argument = MKFIX(73);
    tail = cons(argument, NIL);
    form = cons(macro_name, tail);
    args[0] = form;
    caller_length = emit_prim_call(0, 39, 1);
    vm_status = VM_OK;
    result = vm_run(0, 0, caller_length, args, 1);
    CHECK("macroexpand BCODE service39 carrier cut",
          vm_status == VM_OK && result == argument);

    lisp65_error_clear();
    code_store[expansion_offset + CO_OFF_NARGS] = 2;
    vm_status = VM_OK;
    result = vm_run(0, 0, caller_length, args, 1);
    CHECK("macroexpand BCODE status cleanup",
          result == NIL && vm_status == VM_OK &&
          lisp65_error_pending_code() == LISP65_ERR_WRONG_ARGUMENT_COUNT);
    lisp65_error_clear();
}

static void test_eval_lcc_run_bcode_cut(void) {
    /* The compact VM directory requires contiguous objects within an 8-entry
     * block. Service39's identity expansion occupies bytes 32..40. */
    const uint16_t lcc_run_offset = 41;
    obj lcc_run_name, form, result;
    uint16_t length;
    int directory_index;

    memset(code_store, 0, sizeof(code_store));
    code_store[lcc_run_offset + CO_OFF_MAGIC] = CO_MAGIC;
    code_store[lcc_run_offset + CO_OFF_NARGS] = 1;
    code_store[lcc_run_offset + CO_OFF_FLAGS] = CO_FLAG_STRICT_ARITY;
    code_store[lcc_run_offset + CO_OFF_CLEN] = 2;
    code_store[lcc_run_offset + CO_OFF_LITTAB] = OP_PUSHARG0;
    code_store[lcc_run_offset + CO_OFF_LITTAB + 1] = OP_RET;
    length = (uint16_t)(CO_OFF_LITTAB + 2);

    lcc_run_name = intern("lcc-run");
    directory_index = vm_dir_add(lcc_run_name, 0, lcc_run_offset, length);
    CHECK("eval lcc-run BCODE directory", directory_index >= 0);
    if (directory_index < 0) return;
    set_sym_function(lcc_run_name, MK_BCODE(directory_index));
    form = cons(intern("carrier-cut-form"), cons(MKFIX(11), NIL));
    result = eval(form);
    CHECK("eval lcc-run BCODE carrier cut",
          vm_status == VM_OK && result == form);
}

static void test_error_services(void) {
    static const lisp65_error_code codes[11] = {
        LISP65_ERR_FASL_ENTRIES_OVERFLOW, LISP65_ERR_FASL_NODES_OVERFLOW,
        LISP65_ERR_FASL_NOT_A_DEFUN, LISP65_ERR_FASL_OUTPUT_OVERFLOW,
        LISP65_ERR_FASL_PATCHES_OVERFLOW, LISP65_ERR_FASL_STRINGS_OVERFLOW,
        LISP65_ERR_FASL_TOO_MANY_HELPERS, LISP65_ERR_FASL_UNSUPPORTED_LITERAL,
        LISP65_ERR_FASL_WINDOW_OVERFLOW, LISP65_ERR_LCC_DO_BODY_TOO_BIG,
        LISP65_ERR_LCC_INVALID_PARAMETER_LIST,
    };
    static const char *const names[11] = {
        "%fasl-error-entries-overflow", "%fasl-error-nodes-overflow",
        "%fasl-error-not-a-defun", "%fasl-error-output-overflow",
        "%fasl-error-patches-overflow", "%fasl-error-strings-overflow",
        "%fasl-error-too-many-helpers", "%fasl-error-unsupported-literal",
        "%fasl-error-window-overflow", "%lcc-error-do-body-too-big",
        "%lcc-error-invalid-parameter-list",
    };
    uint8_t index;
    for (index = 0; index < 11; index++) {
        uint16_t free_before = mem_free_cells();
        uint16_t roots_before = gc_rootsp;
        uint16_t symbols_before = sym_count();
        lisp65_error_clear();
        (void)run_prim((uint8_t)(46 + index), NULL, 0);
        CHECK("error-service VM status", vm_status == VM_OK);
        CHECK("error-service stable code", lisp65_error_pending_code() == codes[index]);
        CHECK("error-service symbol", lisp65_error_pending_symbol() != NIL &&
              strcmp(symname(lisp65_error_pending_symbol()), names[index]) == 0);
        CHECK("error-service allocation-free", mem_free_cells() == free_before &&
              gc_rootsp == roots_before && sym_count() == symbols_before);
    }
    CHECK("invalid-parameter-list code 59",
          codes[10] == LISP65_ERR_LCC_INVALID_PARAMETER_LIST &&
          lisp65_error_pending_code() == LISP65_ERR_LCC_INVALID_PARAMETER_LIST);
    CHECK("invalid-parameter-list sentinel",
          lisp65_error_pending_symbol() != NIL &&
          strcmp(symname(lisp65_error_pending_symbol()),
                 "%lcc-error-invalid-parameter-list") == 0);
}

int main(void) {
    eval_init();
    test_internal_symbol_name_cap();
    test_arities();
    test_native_services();
    test_macroexpand_bcode_cut();
    test_eval_lcc_run_bcode_cut();
    test_error_services();
    (void)run_prim(255, NULL, 0);
    CHECK("unknown service", vm_status == VM_BADOPCODE);
    if (failures) {
        fprintf(stderr, "v2-workbench-services: %d failure(s)\n", failures);
        return 1;
    }
    puts("v2-workbench-services: PASS native=15 dependency=lcc-install-covered-elsewhere errors=11");
    return 0;
}
