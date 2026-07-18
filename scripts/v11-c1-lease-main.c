#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "buffer_overlay.h"
#include "c1_compiler_overlay.h"
#include "dialect-v2/libs/lcc-contract.h"
#include "io.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

l65m_plan lisp65_disk_lib_plan;
l65m_source lisp65_disk_lib_source;

static obj export_symbol;
static obj export_function;
static uint16_t symbols_now, names_now, directory_now;
static unsigned failures;

#define CHECK(c, label) do { if (!(c)) { \
    fprintf(stderr, "c1-lease: FAIL %s\n", label); failures++; \
} } while (0)

obj sym_function(obj symbol) {
    return symbol == export_symbol ? export_function : NIL;
}
void set_sym_function(obj symbol, obj value) {
    if (symbol == export_symbol) export_function = value;
}
uint16_t sym_count(void) { return symbols_now; }
uint16_t sym_pool_used(void) { return names_now; }
uint16_t vm_dir_count(void) { return directory_now; }
uint8_t vm_dir_truncate(uint16_t count) {
    if (count > directory_now) return 0;
    directory_now = count;
    return 1;
}

static uint8_t invoke(int16_t action, obj argument, obj *result) {
    obj args[2];
    lisp65_buffer_overlay_context context;
    args[0] = MKFIX(action); args[1] = argument;
    context.args = args; context.argc = 2; context.result = NIL;
    {
        uint8_t status = lisp65_c1_compiler_overlay_entry(&context);
        if (result) *result = context.result;
        return status;
    }
}

static void reset_model(void) {
    memset(&lisp65_disk_lib_plan, 0, sizeof lisp65_disk_lib_plan);
    memset(&lisp65_disk_lib_source, 0, sizeof lisp65_disk_lib_source);
    export_symbol = MK_SYMI(19); export_function = NIL;
    symbols_now = 480; names_now = 6500; directory_now = 197;
    vm_ext_code_test_state(0x2400, 0);
}

static void install_exact(void) {
    l65m_plan *plan = &lisp65_disk_lib_plan;
    uint16_t aligned = (uint16_t)((directory_now + 7u) & ~7u);
    plan->source_length = LISP65_C1_COMPILER_CONTAINER_BYTES;
    plan->source_crc16 = LISP65_C1_COMPILER_CONTAINER_CRC16;
    plan->code_base = vm_ext_code_watermark();
    plan->blob_len = LISP65_C1_COMPILER_BLOB_BYTES;
    plan->entry_count = LISP65_C1_COMPILER_ENTRY_COUNT;
    plan->dir_before = directory_now;
    plan->dir_after = (uint16_t)(aligned + plan->entry_count);
    plan->symbols_before = symbols_now; plan->new_symbols = 5;
    plan->namepool_before = names_now; plan->new_name_bytes = 55;
    plan->format_version = LISP65_C1_COMPILER_FORMAT_VERSION;
    vm_ext_code_test_state((uint16_t)(plan->code_base + plan->blob_len), 0);
    directory_now = plan->dir_after;
    symbols_now = (uint16_t)(plan->symbols_before + plan->new_symbols);
    names_now = (uint16_t)(plan->namepool_before + plan->new_name_bytes);
    export_function = MK_BCODE(77);
}

int main(void) {
    obj result = NIL;
    uint16_t transient;

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "checkpoint");
    install_exact();
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
          "validate installs lease tag");
    CHECK(vm_ext_code_test_lease(), "single lease tag");
    result = MKFIX(42); /* generated Lisp returns this without action 2 */
    CHECK(export_function != NIL && vm_ext_code_watermark() != 0x2400,
          "retained tier remains installed");
    CHECK(IS_BCODE(export_function),
          "warm route is admitted only by published compiler function cell");

    transient = vm_ext_code_alloc_transient(48);
    CHECK(transient != 0xffffu, "transient expression allowed under lease");
    CHECK(vm_ext_code_alloc(1, 1) == 0xffffu,
          "foreign persistent append rejected before retirement");
    vm_ext_code_pop_transient(transient, 48);
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_OK,
          "explicit foreign-allocation retirement");
    CHECK(export_function == NIL && vm_ext_code_watermark() == 0x2400 &&
          directory_now == 197, "force restores exact watermarks");
    CHECK(vm_ext_code_alloc(1, 1) == 0x2400,
          "persistent append succeeds only after retirement");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "failure checkpoint");
    install_exact();
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
          "failure validate");
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_OK,
          "nil compile result retires instead of leasing");
    CHECK(export_function == NIL && vm_ext_code_watermark() == 0x2400,
          "failed compile leaves no lease");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "corrupt checkpoint");
    install_exact();
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
          "corrupt validate");
    export_function = NIL;
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, &result) == VM_BADOPCODE,
          "missing published compiler cannot enter warm or cold route");
    lisp65_disk_lib_plan.source_crc16 ^= 1u;
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_BADOPCODE,
          "mutated identity is not destructively retired");
    CHECK(vm_ext_code_watermark() != 0x2400 && directory_now != 197,
          "corrupt-state rejection preserves installed allocation watermarks");

    if (failures) return 1;
    puts("v11-c1-lease: PASS reuse=yes transient=yes "
         "retire-before-persistent=yes nil-retires=yes mutation-fail-closed=yes");
    return 0;
}
