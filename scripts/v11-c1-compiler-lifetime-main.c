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
static uint16_t symbol_count_now;
static uint16_t namepool_now;
static uint16_t directory_now;
static unsigned failures;

#define TEST_TIER_NEW_SYMBOLS 7u
#define TEST_TIER_NEW_NAME_BYTES 83u

#define CHECK(condition, label) do { \
    if (!(condition)) { \
        fprintf(stderr, "c1-lifetime: FAIL %s\n", label); \
        failures++; \
    } \
} while (0)

obj sym_function(obj symbol) {
    return symbol == export_symbol ? export_function : NIL;
}

void set_sym_function(obj symbol, obj value) {
    if (symbol == export_symbol) export_function = value;
}

uint16_t sym_count(void) { return symbol_count_now; }
uint16_t sym_pool_used(void) { return namepool_now; }
uint16_t vm_dir_count(void) { return directory_now; }

uint8_t vm_dir_truncate(uint16_t count) {
    if (count > directory_now) return 0;
    directory_now = count;
    return 1;
}

static uint8_t invoke(int16_t action, obj argument, obj *result) {
    obj args[2];
    lisp65_buffer_overlay_context context;
    args[0] = MKFIX(action);
    args[1] = argument;
    context.args = args;
    context.argc = 2;
    context.result = NIL;
    {
        uint8_t status = lisp65_c1_compiler_overlay_entry(&context);
        if (result) *result = context.result;
        return status;
    }
}

static void reset_model(void) {
    memset(&lisp65_disk_lib_plan, 0, sizeof lisp65_disk_lib_plan);
    memset(&lisp65_disk_lib_source, 0, sizeof lisp65_disk_lib_source);
    export_symbol = MK_SYMI(17);
    export_function = NIL;
    symbol_count_now = 500;
    namepool_now = 7000;
    directory_now = 205;
    vm_ext_code_test_state(0x2200, 0);
}

static void exact_plan(void) {
    l65m_plan *plan = &lisp65_disk_lib_plan;
    uint16_t aligned = (uint16_t)((directory_now + 7u) & ~7u);
    plan->source_length = LISP65_C1_COMPILER_CONTAINER_BYTES;
    plan->source_crc16 = LISP65_C1_COMPILER_CONTAINER_CRC16;
    plan->source_blob_off = 4;
    plan->source_metadata_off =
        (uint16_t)(4u + LISP65_C1_COMPILER_BLOB_BYTES);
    plan->code_base = vm_ext_code_watermark();
    plan->blob_len = LISP65_C1_COMPILER_BLOB_BYTES;
    plan->entry_count = LISP65_C1_COMPILER_ENTRY_COUNT;
    plan->dir_before = directory_now;
    plan->dir_after =
        (uint16_t)(aligned + LISP65_C1_COMPILER_ENTRY_COUNT);
    plan->symbols_before = symbol_count_now;
    plan->namepool_before = namepool_now;
    plan->new_symbols = TEST_TIER_NEW_SYMBOLS;
    plan->new_name_bytes = TEST_TIER_NEW_NAME_BYTES;
    plan->format_version = LISP65_C1_COMPILER_FORMAT_VERSION;
}

static void installed(void) {
    vm_ext_code_test_state(
        (uint16_t)(lisp65_disk_lib_plan.code_base +
                   lisp65_disk_lib_plan.blob_len), 0);
    directory_now = lisp65_disk_lib_plan.dir_after;
    symbol_count_now = (uint16_t)(lisp65_disk_lib_plan.symbols_before +
                                  lisp65_disk_lib_plan.new_symbols);
    namepool_now = (uint16_t)(lisp65_disk_lib_plan.namepool_before +
                              lisp65_disk_lib_plan.new_name_bytes);
    export_function = MK_BCODE(121);
}

int main(void) {
    obj result = NIL;

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "checkpoint");
    exact_plan();
    installed();
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
          "validate exact tier");
    symbol_count_now++;
    namepool_now += 4;
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, MKFIX(42), &result) == VM_OK,
          "retire");
    CHECK(result == MKFIX(42), "retire returns detached result");
    CHECK(export_function == NIL, "export restored");
    CHECK(directory_now == 205 && vm_ext_code_watermark() == 0x2200,
          "code and directory restored");
    CHECK(symbol_count_now == 500 + TEST_TIER_NEW_SYMBOLS + 1 &&
          namepool_now == 7000 + TEST_TIER_NEW_NAME_BYTES + 4,
          "user internings preserved");
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, MKFIX(7), &result) == VM_OK &&
          result == MKFIX(7), "unconditional abort cleanup is idempotent");

    /* GC may run while the compiler tier is active.  The checkpoint contains
     * only reset-cleared scalar watermarks plus an immediate symbol object;
     * the detached result remains a rooted argument of the synchronous retire
     * call.  Replaying the exact state after that boundary must neither depend
     * on object addresses nor change the returned object. */
    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "gc checkpoint");
    exact_plan();
    installed();
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
          "gc validate");
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, MKFIX(314), &result) == VM_OK &&
          result == MKFIX(314), "gc-transparent detached result");
    CHECK(export_function == NIL && directory_now == 205 &&
          vm_ext_code_watermark() == 0x2200,
          "gc-transparent rollback exact");

    /* A failed detached-buffer allocation returns NIL.  NIL is still a
     * completed compiler invocation, so retirement is mandatory and exact. */
    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "oom checkpoint");
    exact_plan();
    installed();
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
          "oom validate");
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, &result) == VM_OK &&
          result == NIL, "oom returns nil after retirement");
    CHECK(export_function == NIL && directory_now == 205 &&
          vm_ext_code_watermark() == 0x2200,
          "oom rollback exact");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "early-failure checkpoint");
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_OK,
          "catalog failure has no mutation to restore");
    CHECK(directory_now == 205 && vm_ext_code_watermark() == 0x2200,
          "catalog failure leaves watermarks");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "precommit checkpoint");
    exact_plan();
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_OK,
          "precommit failure retires");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "partial checkpoint");
    exact_plan();
    installed();
    directory_now -= 11;
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_OK,
          "partial directory publish rolls back");
    CHECK(export_function == NIL && directory_now == 205 &&
          vm_ext_code_watermark() == 0x2200,
          "partial rollback exact");

    reset_model();
    export_function = MK_BCODE(9);
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_BADOPCODE,
          "pre-existing export rejected");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "identity checkpoint");
    exact_plan();
    installed();
    lisp65_disk_lib_plan.source_crc16 ^= 1u;
    CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_BADOPCODE,
          "wrong compiler identity rejected");
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_BADOPCODE,
          "unknown loaded identity is not destructively guessed");
    CHECK(lisp65_c1_compiler_overlay_entry(0) == VM_OK,
          "longjmp abort uses the captured checkpoint, not mutated identity");
    CHECK(export_function == NIL && directory_now == 205 &&
          vm_ext_code_watermark() == 0x2200,
          "longjmp abort rollback exact");

    /* Public entry seams call C1 while their own transient expression main is
     * still on the downward stack.  Retirement is safe when the complete
     * persistent compiler tier remains below that stack. */
    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "nested checkpoint");
    exact_plan();
    installed();
    {
        uint16_t transient = vm_ext_code_alloc_transient(48);
        CHECK(transient != 0xffffu, "nested transient allocated");
        CHECK(invoke(LISP65_C1_COMPILER_VALIDATE, NIL, 0) == VM_OK,
              "nested validate");
        CHECK(invoke(LISP65_C1_COMPILER_RETIRE, MKFIX(2718), &result) == VM_OK &&
              result == MKFIX(2718), "nested retirement");
        CHECK(vm_ext_code_watermark() == 0x2200,
              "nested retirement restores persistent watermark");
        CHECK(vm_ext_code_test_transient() == transient,
              "nested retirement preserves transient stack");
        vm_ext_code_pop_transient(transient, 48);
    }

    /* Normal allocators cannot make the two ranges overlap.  Inject that
     * corrupt state and prove C1 refuses a destructive rollback. */
    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_CHECKPOINT, export_symbol, 0) == VM_OK,
          "overlap checkpoint");
    exact_plan();
    installed();
    vm_ext_code_test_state(vm_ext_code_watermark(),
                           (uint16_t)(vm_ext_code_watermark() - 1u));
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_BADOPCODE,
          "overlap retirement rejected");
    CHECK(export_function != NIL && directory_now == lisp65_disk_lib_plan.dir_after,
          "overlap rejection is non-destructive");
    vm_ext_code_test_state(
        (uint16_t)(lisp65_disk_lib_plan.code_base +
                   lisp65_disk_lib_plan.blob_len), 0);
    CHECK(lisp65_c1_compiler_overlay_entry(0) == VM_OK,
          "overlap fixture cleanup");

    reset_model();
    CHECK(invoke(LISP65_C1_COMPILER_RETIRE, NIL, 0) == VM_OK,
          "reset-cleared transaction is inert");

    if (failures) return 1;
    puts("v11-c1-compiler-lifetime: PASS cases=12 gc=yes oom=yes malformed=yes reset=yes partial=yes user-symbols=yes planned-internings=yes abort=yes nested-transient=yes overlap-reject=yes");
    return 0;
}
