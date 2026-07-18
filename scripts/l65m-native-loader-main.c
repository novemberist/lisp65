/* Native host conformance harness for the transactional L65M disk-lib loader. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "l65m-contract-cases.h"
#include "l65m_commit_overlay.h"
#include "l65m_overlay_abi.h"
#include "l65m_validate.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"
#include "vm_runtime_overlay.h"

/* The loader uses the product's Bank-5 ABI, but this host test has no boot image. */
const uint8_t lisp65_stdlib_blob[] = { 0 };
const uint16_t lisp65_stdlib_blob_len = 0;
const uint8_t lisp65_stdlib_bank = 5;
const uint16_t lisp65_stdlib_off = 0;
const vm_embed_entry lisp65_embed[] = { { 0, 0, 0, 0, 0 } };
const uint16_t lisp65_embed_count = 0;

static uint8_t bank5[65536];
static uint8_t bank5_before[65536];
static Cell heap_before[HEAP_CELLS];
static obj roots_before[GC_ROOTS];
static unsigned stage_calls;
static uint16_t staged_source_off;
static uint16_t staged_destination;
static uint16_t staged_bytes;
static unsigned ext_write_calls;
static obj sentinel;
static int failed;
static int expect(const char *case_name, const char *what, int condition);
static int expect_status(const char *case_name, l65m_status actual,
                         l65m_status expected);

static void check_repeat_guard(void) {
    l65m_overlay_work work;
    uint8_t result;
    memset(&work, 0, sizeof work);
    work.abi_version = L65M_OVERLAY_ABI_VERSION;
    work.context_size = L65M_OVERLAY_CONTEXT_SIZE;
    work.expected_phase = L65M_PHASE_05_ENTRY_NAMES;
    work.cookie = (uint16_t)(L65M_OVERLAY_COOKIE_BASE ^ work.expected_phase);
    work.busy = 1;
    work.repeat_phase = 1;
    work.repeat_count = L65M_OVERLAY_REPEAT_LIMIT;
    result = l65m_overlay_guard(&work, work.expected_phase, L65M_OK, 1);
    expect("repeat-guard", "repeat limit did not fail closed",
           result == L65M_ERR_STATE && !work.busy && work.finished
           && work.transport_status == L65M_OV_TRANSPORT_REPEAT_LIMIT
           && work.expected_phase == L65M_OVERLAY_PHASE_COUNT);

    memset(&work, 0, sizeof work);
    work.abi_version = L65M_OVERLAY_ABI_VERSION;
    work.context_size = L65M_OVERLAY_CONTEXT_SIZE;
    work.expected_phase = L65M_PHASE_05_ENTRY_NAMES;
    work.cookie = (uint16_t)(L65M_OVERLAY_COOKIE_BASE ^ work.expected_phase);
    work.busy = 1;
    work.repeat_count = 7;
    result = l65m_overlay_guard(&work, work.expected_phase, L65M_OK, 1);
    expect("repeat-guard", "phase progress did not reset repeat count",
           result == L65M_OK && work.repeat_count == 0
           && work.expected_phase == L65M_PHASE_06_CODE && !work.finished);
}

static void check_commit_batch_predicate(void) {
    l65m_commit_work work;
    const uint8_t phase = L65M_COMMIT_PHASE_MATERIALIZE_SCALARS;
    const uint8_t slot_base = (uint8_t)(
        LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE + L65M_OVERLAY_PHASE_COUNT);
    memset(&work, 0, sizeof work);
    work.abi_version = L65M_COMMIT_OVERLAY_ABI_VERSION;
    work.context_size = L65M_COMMIT_CONTEXT_SIZE;
    work.expected_phase = phase;
    work.cookie = (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE ^ phase);
    work.repeat_phase = 1;
    expect("commit-predicate", "valid repeat was rejected",
           vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase), L65M_OK));

    work.abi_version++;
    expect("commit-predicate", "ABI drift repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase), L65M_OK));
    work.abi_version = L65M_COMMIT_OVERLAY_ABI_VERSION;
    work.expected_phase++;
    expect("commit-predicate", "phase drift repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase), L65M_OK));
    work.expected_phase = phase;
    work.transport_status = L65M_COMMIT_TRANSPORT_OK;
    expect("commit-predicate", "slot drift repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase + 1u), L65M_OK));
    work.transport_status = L65M_COMMIT_TRANSPORT_OK;
    work.repeat_phase = 0;
    expect("commit-predicate", "cleared repeat flag repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase), L65M_OK));
    work.repeat_phase = 1;
    work.transport_status = L65M_COMMIT_TRANSPORT_OK;
    work.busy = 1;
    expect("commit-predicate", "busy context repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase), L65M_OK));
    work.busy = 0;
    expect("commit-predicate", "failed entry result repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + phase), L65M_ERR_STATE));
    work.expected_phase = L65M_COMMIT_PHASE_COUNT;
    work.cookie = (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE
                             ^ L65M_COMMIT_PHASE_COUNT);
    expect("commit-predicate", "finished state repeated",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + L65M_COMMIT_PHASE_COUNT), L65M_OK));

    memset(&work, 0, sizeof work);
    work.abi_version = L65M_COMMIT_OVERLAY_ABI_VERSION;
    work.context_size = L65M_COMMIT_CONTEXT_SIZE;
    work.expected_phase = L65M_COMMIT_PHASE_ENTRIES;
    work.cookie = (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE
                             ^ L65M_COMMIT_PHASE_ENTRIES);
    expect("commit-predicate", "zero-patch VERIFY-to-ENTRIES skip was rejected",
           !vm_l65m_commit_batch_repeat_test(
               &work, slot_base, L65M_OK)
           && work.transport_status == L65M_COMMIT_TRANSPORT_OK);

    work.expected_phase = L65M_COMMIT_PHASE_COUNT;
    work.cookie = (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE
                             ^ L65M_COMMIT_PHASE_COUNT);
    work.finished = 1;
    expect("commit-predicate", "valid final state was rejected",
           !vm_l65m_commit_batch_repeat_test(
               &work, (uint8_t)(slot_base + L65M_COMMIT_PHASE_ENTRIES), L65M_OK)
           && work.transport_status == L65M_COMMIT_TRANSPORT_OK);
}

typedef struct {
    const uint8_t *data;
    uint16_t length;
    uint16_t read_calls;
    uint16_t fail_call;
} bytes_source;

typedef struct {
    uint16_t dir_count;
    uint16_t symbol_count;
    uint16_t namepool_used;
    uint16_t heap_free;
    uint16_t roots_used;
    uint16_t arena_used;
    uint16_t watermark;
    uint16_t gc_count;
    uint8_t oom;
    obj sentinel_value;
    obj sentinel_function;
    unsigned stages;
    uint16_t stage_source_off;
    uint16_t stage_destination;
    uint16_t stage_bytes;
    unsigned writes;
} protected_state;

static uint16_t u16le(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static int16_t i16le(const uint8_t *p) {
    return (int16_t)u16le(p);
}

static uint8_t read_bytes(void *opaque, uint16_t off, uint8_t *dst, uint16_t len) {
    bytes_source *source = (bytes_source *)opaque;
    source->read_calls++;
    if (source->fail_call && source->read_calls == source->fail_call) return 0;
    if (off > source->length || len > (uint16_t)(source->length - off)) return 0;
    if (len) memcpy(dst, source->data + off, len);
    return 1;
}

static bytes_source *disk_carrier_bytes;
/* Product-equivalent reader: the real disk callback ignores its private ctx. */
uint8_t lisp65_disk_carrier_read(void *opaque, uint16_t off,
                                 uint8_t *dst, uint16_t len) {
    (void)opaque;
    return read_bytes(disk_carrier_bytes, off, dst, len);
}

static void check_disk_carrier_framing(const l65m_contract_case *test) {
    uint8_t padded[test->len + 16u];
    bytes_source bytes;
    l65m_source source;
    l65m_plan plan;
    l65m_status status;
    memcpy(padded, test->data, test->len);
    memset(padded + test->len, 0x20, 16u);
    bytes.data = padded; bytes.length = (uint16_t)sizeof padded;
    bytes.read_calls = 0; bytes.fail_call = 0;
    source.read = read_bytes; source.ctx = &bytes; source.length = bytes.length;
    status = vm_preflight_lib_ext(&source, &plan);
    expect("disk-carrier-framing", "arbitrary padded source was accepted",
           status == L65M_ERR_CONTAINER);
    bytes.read_calls = 0;
    disk_carrier_bytes = &bytes;
    source.read = lisp65_disk_carrier_read;
    source.ctx = (void *)1;
    status = vm_preflight_lib_ext(&source, &plan);
    expect_status("disk-carrier-framing", status, L65M_OK);
    expect("disk-carrier-framing", "plan retained allocation-chain length",
           status == L65M_OK && plan.source_length == test->len);
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    if (bank != lisp65_stdlib_bank || (uint32_t)off + len > sizeof bank5) {
        memset(dst, 0, len);
        return;
    }
    memcpy(dst, bank5 + off, len);
}

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    ext_write_calls++;
    if (bank != lisp65_stdlib_bank || (uint32_t)off + len > sizeof bank5) {
        fprintf(stderr, "l65m-native-loader: FAIL invalid EXT write bank=%u off=%u len=%u\n",
                bank, off, len);
        failed++;
        return;
    }
    memcpy(bank5 + off, src, len);
}

static int expect(const char *case_name, const char *what, int condition) {
    if (condition) return 1;
    fprintf(stderr, "l65m-native-loader: FAIL %s: %s\n", case_name, what);
    failed++;
    return 0;
}

static int expect_status(const char *case_name, l65m_status actual,
                         l65m_status expected) {
    if (actual == expected) return 1;
    fprintf(stderr,
            "l65m-native-loader: FAIL %s: preflight status got=%u expected=%u\n",
            case_name, (unsigned)actual, (unsigned)expected);
    failed++;
    return 0;
}

static uint16_t free_cells(void) {
    return mem_free_cells();
}

static uint16_t arena_used(void) {
#ifdef LISP65_STRING_ARENA
    return str_arena_used();
#else
    return 0;
#endif
}

static void capture_state(protected_state *state) {
    state->dir_count = vm_dir_count();
    state->symbol_count = sym_count();
    state->namepool_used = sym_pool_used();
    state->heap_free = free_cells();
    state->roots_used = gc_rootsp;
    state->arena_used = arena_used();
    state->watermark = vm_ext_code_watermark();
    state->gc_count = gc_runs;
    state->oom = mem_oom;
    state->sentinel_value = sym_value(sentinel);
    state->sentinel_function = sym_function(sentinel);
    state->stages = stage_calls;
    state->stage_source_off = staged_source_off;
    state->stage_destination = staged_destination;
    state->stage_bytes = staged_bytes;
    state->writes = ext_write_calls;
    memcpy(heap_before, heap, sizeof heap_before);
    memcpy(roots_before, gc_rootstack, sizeof roots_before);
    memcpy(bank5_before, bank5, sizeof bank5_before);
}

static void expect_unchanged(const char *name, const protected_state *before) {
    protected_state after;
    after.dir_count = vm_dir_count();
    after.symbol_count = sym_count();
    after.namepool_used = sym_pool_used();
    after.heap_free = free_cells();
    after.roots_used = gc_rootsp;
    after.arena_used = arena_used();
    after.watermark = vm_ext_code_watermark();
    after.gc_count = gc_runs;
    after.oom = mem_oom;
    after.sentinel_value = sym_value(sentinel);
    after.sentinel_function = sym_function(sentinel);
    after.stages = stage_calls;
    after.stage_source_off = staged_source_off;
    after.stage_destination = staged_destination;
    after.stage_bytes = staged_bytes;
    after.writes = ext_write_calls;

    expect(name, "directory changed during preflight", after.dir_count == before->dir_count);
    expect(name, "symbol table changed during preflight",
           after.symbol_count == before->symbol_count);
    expect(name, "namepool changed during preflight",
           after.namepool_used == before->namepool_used);
    expect(name, "heap freelist changed during preflight", after.heap_free == before->heap_free);
    expect(name, "heap bytes changed during preflight",
           memcmp(heap_before, heap, sizeof heap_before) == 0);
    expect(name, "root depth changed during preflight", after.roots_used == before->roots_used);
    expect(name, "root storage changed during preflight",
           memcmp(roots_before, gc_rootstack, sizeof roots_before) == 0);
    expect(name, "string arena changed during preflight", after.arena_used == before->arena_used);
    expect(name, "EXT watermark changed during preflight", after.watermark == before->watermark);
    expect(name, "GC/OOM state changed during preflight",
           after.gc_count == before->gc_count && after.oom == before->oom);
    expect(name, "sentinel cells changed during preflight",
           after.sentinel_value == before->sentinel_value &&
           after.sentinel_function == before->sentinel_function);
    expect(name, "stage state changed during preflight",
           after.stages == before->stages &&
           after.stage_source_off == before->stage_source_off &&
           after.stage_destination == before->stage_destination &&
           after.stage_bytes == before->stage_bytes);
    expect(name, "vm_ext_write ran during preflight", after.writes == before->writes);
    expect(name, "Bank 5 changed during preflight",
           memcmp(bank5_before, bank5, sizeof bank5_before) == 0);
}

static void expect_reserved_failure(const char *name, const protected_state *before,
                                    const l65m_plan *plan) {
    expect(name, "directory published after a pre-publication failure",
           vm_dir_count() == before->dir_count);
    expect(name, "symbols changed after a pre-publication failure",
           sym_count() == before->symbol_count && sym_pool_used() == before->namepool_used);
    expect(name, "heap changed after a patch-record read failure",
           free_cells() == before->heap_free &&
           memcmp(heap_before, heap, sizeof heap_before) == 0);
    expect(name, "roots changed after a patch-record read failure",
           gc_rootsp == before->roots_used &&
           memcmp(roots_before, gc_rootstack, sizeof roots_before) == 0);
    expect(name, "string arena changed after a patch-record read failure",
           arena_used() == before->arena_used);
    expect(name, "verified blob reservation was not retained",
           vm_ext_code_watermark() == (uint16_t)(before->watermark + plan->blob_len));
    expect(name, "patch write ran after a patch-record read failure",
           ext_write_calls == before->writes);
    expect(name, "staged blob changed after a patch-record read failure",
           memcmp(bank5_before, bank5, sizeof bank5_before) == 0);
}

static const uint8_t *metadata_at(const l65m_contract_case *test, const l65m_plan *plan,
                                  uint16_t relative) {
    return test->data + plan->source_metadata_off + relative;
}

static const char *metadata_string(const l65m_contract_case *test, const l65m_plan *plan,
                                   uint16_t name_off) {
    return (const char *)metadata_at(test, plan, (uint16_t)(plan->strings_off + name_off));
}

enum {
    TEST_LIT_FIX = 1,
    TEST_LIT_NIL = 2,
    TEST_LIT_T = 3,
    TEST_LIT_SYMBOL = 4,
    TEST_LIT_CONS = 5,
    TEST_LIT_LIST = 6,
    TEST_LIT_STRING = 7
};

static int literal_matches(const l65m_contract_case *test, const l65m_plan *plan,
                           uint16_t node_index, obj value, uint8_t depth) {
    const uint8_t *node;
    uint8_t kind;
    uint16_t first, count, name_off, i;

    if (depth > L65M_MAX_GRAPH_DEPTH || node_index >= plan->node_count) return 0;
    node = metadata_at(test, plan, (uint16_t)(plan->nodes_off + node_index * 10u));
    kind = node[0];
    first = u16le(node + 4);
    count = u16le(node + 6);
    name_off = u16le(node + 8);
    switch (kind) {
    case TEST_LIT_FIX:
        return value == MKFIX(i16le(node + 2));
    case TEST_LIT_NIL:
        return value == NIL;
    case TEST_LIT_T:
        return value == intern("t");
    case TEST_LIT_SYMBOL:
        return (IS_SYMI(value) || (IS_PTR(value) && cell_type(value) == T_SYM)) &&
               strcmp(symname(value), metadata_string(test, plan, name_off)) == 0;
    case TEST_LIT_STRING: {
        const char *want = metadata_string(test, plan, name_off);
        uint16_t len = 0;
        if (!IS_PTR(value) || cell_type(value) != T_STR) return 0;
        while (want[len]) len++;
#ifdef LISP65_STRING_ARENA
        if (str_len(value) != len) return 0;
        for (i = 0; i < len; i++) if (str_byte(value, i) != (uint8_t)want[i]) return 0;
#else
        value = cell_a(value);
        for (i = 0; i < len; i++) {
            if (!IS_PTR(value) || cell_type(value) != T_CONS ||
                cell_a(value) != MKFIX((uint8_t)want[i])) return 0;
            value = cell_b(value);
        }
        if (value != NIL) return 0;
#endif
        return 1;
    }
    case TEST_LIT_CONS: {
        uint16_t a_node, b_node;
        if (!IS_PTR(value) || cell_type(value) != T_CONS || count != 2) return 0;
        a_node = u16le(metadata_at(test, plan, (uint16_t)(plan->index_off + first * 2u)));
        b_node = u16le(metadata_at(test, plan,
                                  (uint16_t)(plan->index_off + (first + 1u) * 2u)));
        return literal_matches(test, plan, a_node, cell_a(value), (uint8_t)(depth + 1)) &&
               literal_matches(test, plan, b_node, cell_b(value), (uint8_t)(depth + 1));
    }
    case TEST_LIT_LIST:
        for (i = 0; i < count; i++) {
            uint16_t child;
            if (!IS_PTR(value) || cell_type(value) != T_CONS) return 0;
            child = u16le(metadata_at(
                test, plan, (uint16_t)(plan->index_off + (first + i) * 2u)));
            if (!literal_matches(test, plan, child, cell_a(value), (uint8_t)(depth + 1)))
                return 0;
            value = cell_b(value);
        }
        return value == NIL;
    default:
        return 0;
    }
}

static unsigned macro_count(const l65m_contract_case *test, const l65m_plan *plan) {
    unsigned count = 0;
    uint16_t i;
    for (i = 0; i < plan->entry_count; i++) {
        const uint8_t *entry = metadata_at(
            test, plan, (uint16_t)(plan->entries_off + i * 8u));
        if (entry[3] & 1u) count++;
    }
    return count;
}

static void stage_blob(const l65m_contract_case *test, const l65m_plan *plan) {
    stage_calls++;
    staged_source_off = plan->source_blob_off;
    staged_destination = plan->code_base;
    staged_bytes = plan->blob_len;
    vm_ext_write(test->data + plan->source_blob_off, plan->blob_len,
                 lisp65_stdlib_bank, plan->code_base);
}

static void check_patches(const l65m_contract_case *test, const l65m_plan *plan) {
    uint16_t i;
    for (i = 0; i < plan->patch_count; i++) {
        const uint8_t *patch = metadata_at(
            test, plan, (uint16_t)(plan->patches_off + i * 4u));
        uint16_t blob_off = u16le(patch);
        uint16_t node = u16le(patch + 2);
        obj value = (obj)u16le(bank5 + plan->code_base + blob_off);
        char label[80];
        snprintf(label, sizeof label, "literal patch %u was not materialized", (unsigned)i);
        expect(test->name, label, literal_matches(test, plan, node, value, 0));
    }
}

static void check_entries_and_run(const l65m_contract_case *test, const l65m_plan *plan) {
    uint16_t i;
    int ran = 0;
    for (i = 0; i < plan->entry_count; i++) {
        const uint8_t *entry = metadata_at(
            test, plan, (uint16_t)(plan->entries_off + i * 8u));
        const char *name = metadata_string(test, plan, u16le(entry));
        uint8_t flags = entry[3];
        uint16_t blob_off = u16le(entry + 4);
        const uint8_t *code = test->data + plan->source_blob_off + blob_off;
        obj fn = sym_function(intern(name));
        obj bytecode = NIL;

        if (flags & 1u) {
            expect(test->name, "macro entry was not published as T_MACRO",
                   IS_PTR(fn) && cell_type(fn) == T_MACRO && IS_BCODE(cell_a(fn)));
            if (IS_PTR(fn) && cell_type(fn) == T_MACRO && IS_BCODE(cell_a(fn)))
                bytecode = cell_a(fn);
        } else {
            expect(test->name, "function entry was not published as BCODE", IS_BCODE(fn));
            if (IS_BCODE(fn)) bytecode = fn;
        }
        if (!ran && IS_BCODE(bytecode) && code[1] == 0) {
            uint16_t payload_off = (uint16_t)(7u + 2u * code[6]);
            uint16_t payload_len = u16le(code + 4);
            if (payload_len == 2 && code[payload_off] == OP_PUSHNIL &&
                code[payload_off + 1] == OP_RET) {
                obj result;
                vm_status = VM_OK;
                result = vm_run_dir((int)BCODE_IDX(bytecode), 0, 0);
                expect(test->name, "loaded PUSHNIL/RET bytecode failed",
                       vm_status == VM_OK && result == NIL);
                ran = 1;
            }
        }
    }
    expect(test->name, "no executable PUSHNIL/RET golden entry", ran);
}

static void run_commit_case(const l65m_contract_case *test) {
    uint8_t source_data[test->len];
    bytes_source bytes = { source_data, test->len, 0, 0 };
    l65m_source source = { read_bytes, &bytes, test->len };
    l65m_plan plan;
    protected_state before;
    l65m_status status;
    uint16_t before_watermark;
    obj keep = intern("%lit-keep"), keep_before;

    memcpy(source_data, test->data, test->len);
    status = vm_preflight_lib_ext(&source, &plan);
    if (!expect(test->name, "golden preflight failed", status == L65M_OK)) return;
    before_watermark = vm_ext_code_watermark();
    expect(test->name, "preflight selected the wrong code base",
           plan.code_base == before_watermark);
    expect(test->name, "fixture entry count mismatch",
           plan.entry_count == test->expected_entry_count);
    expect(test->name, "fixture patch count mismatch",
           plan.patch_count == test->expected_patch_count);
    expect(test->name, "fixture macro count mismatch",
           macro_count(test, &plan) == test->expected_macro_count);

    /* A source changed after preflight must fail before reservation or publication. */
    stage_blob(test, &plan);
    source_data[plan.source_metadata_off] ^= 1u;
    capture_state(&before);
    bytes.read_calls = 0;
    status = vm_load_lib_ext(&source, &plan);
    expect(test->name, "source TOCTOU was accepted", status == L65M_ERR_STATE);
    expect_unchanged(test->name, &before);
    source_data[plan.source_metadata_off] ^= 1u;

    /* A staged blob different from the verified source has identical pre-mutation semantics. */
    stage_blob(test, &plan);
    bank5[plan.code_base] ^= 1u;
    capture_state(&before);
    bytes.read_calls = 0;
    status = vm_load_lib_ext(&source, &plan);
    expect(test->name, "staged blob mutation was accepted", status == L65M_ERR_STATE);
    expect_unchanged(test->name, &before);
    bank5[plan.code_base] ^= 1u;

    /* A phase-00 source failure also precedes the persistent reservation. */
    stage_blob(test, &plan);
    capture_state(&before);
    bytes.read_calls = 0;
    bytes.fail_call = 1;
    status = vm_load_lib_ext(&source, &plan);
    expect(test->name, "phase-00 read failure had the wrong status",
           status == L65M_ERR_SOURCE);
    expect_unchanged(test->name, &before);
    bytes.fail_call = 0;

    /* Once phase 00 succeeds, the blob remains reserved even if metadata later disappears. */
    stage_blob(test, &plan);
    capture_state(&before);
    bytes.read_calls = 0;
    bytes.fail_call = (uint16_t)(((uint32_t)test->len + 15u) / 16u + 1u);
    status = vm_load_lib_ext(&source, &plan);
    expect(test->name, "post-verification read failure had the wrong status",
           status == L65M_ERR_SOURCE);
    expect_reserved_failure(test->name, &before, &plan);
    bytes.fail_call = 0;

    /* The failed reservation is append-only; preflight the successful retry at the new base. */
    bytes.read_calls = 0;
    status = vm_preflight_lib_ext(&source, &plan);
    if (!expect(test->name, "retry preflight failed", status == L65M_OK)) return;
    before_watermark = vm_ext_code_watermark();
    expect(test->name, "retry preflight selected the wrong code base",
           plan.code_base == before_watermark);

    capture_state(&before);
    keep_before = sym_value(keep);
    stage_blob(test, &plan);
    expect(test->name, "stage count/length mismatch",
           stage_calls == before.stages + 1u && staged_bytes == plan.blob_len &&
           staged_source_off == plan.source_blob_off &&
           staged_destination == plan.code_base);
    expect(test->name, "stage did not copy the golden blob",
           memcmp(bank5 + plan.code_base, test->data + plan.source_blob_off,
                  plan.blob_len) == 0);
    expect(test->name, "stage copied metadata before commit",
           bank5[plan.code_base + plan.blob_len] ==
           bank5_before[plan.code_base + plan.blob_len]);

    status = vm_load_lib_ext(&source, &plan);
    if (!expect(test->name, "golden commit failed", status == L65M_OK)) return;
    expect(test->name, "directory commit count mismatch", vm_dir_count() == plan.dir_after);
    expect(test->name, "loader did not retain exactly the verified blob",
           vm_ext_code_watermark() == (uint16_t)(before_watermark + plan.blob_len));
    expect(test->name, "commit leaked temporary roots", gc_rootsp == plan.roots_before);
    expect(test->name, "commit reported OOM", mem_oom == 0);
    expect(test->name, "published literals did not retain their keep chain",
           !plan.patch_count || sym_value(keep) != keep_before);
    gc_collect();
    expect(test->name, "published literal keep chain did not survive GC", mem_oom == 0);
    expect(test->name, "Bank 5 prefix changed outside the staged blob",
           memcmp(bank5_before, bank5, plan.code_base) == 0);
    expect(test->name, "Bank 5 suffix changed outside the staged blob",
           memcmp(bank5_before + plan.code_base + plan.blob_len,
                  bank5 + plan.code_base + plan.blob_len,
                  sizeof bank5 - plan.code_base - plan.blob_len) == 0);
    check_patches(test, &plan);
    check_entries_and_run(test, &plan);
}

static void run_depth_commit_case(const l65m_contract_case *test) {
    uint8_t source_data[test->len];
    bytes_source bytes = { source_data, test->len, 0, 0 };
    l65m_source source = { read_bytes, &bytes, test->len };
    l65m_plan plan;
    uint16_t before_watermark;
    l65m_status status;

    memcpy(source_data, test->data, test->len);
    status = vm_preflight_lib_ext(&source, &plan);
    if (!expect(test->name, "depth contract preflight failed", status == L65M_OK))
        return;
    expect(test->name, "depth contract was not pinned to nine",
           plan.max_graph_depth == L65M_MAX_GRAPH_DEPTH);
    before_watermark = vm_ext_code_watermark();
    stage_blob(test, &plan);
    status = vm_load_lib_ext(&source, &plan);
    if (!expect(test->name, "depth contract commit failed", status == L65M_OK))
        return;
    expect(test->name, "depth contract reservation mismatch",
           vm_ext_code_watermark() == (uint16_t)(before_watermark + plan.blob_len));
    expect(test->name, "depth contract commit leaked temporary roots",
           gc_rootsp == plan.roots_before);
    expect(test->name, "depth contract commit reported OOM", mem_oom == 0);
    check_patches(test, &plan);
}

static void check_commit_enter_mutations(const l65m_source *source,
                                         const l65m_plan *plan) {
    l65m_commit_work work;
    l65m_status status;

    status = l65m_commit_work_prepare(&work, source, plan);
    expect("commit-enter", "ABI mutation prepare failed", status == L65M_OK);
    if (status == L65M_OK) {
        work.abi_version++;
        status = (l65m_status)l65m_commit_phase_verify(&work);
        expect("commit-enter", "ABI mutation entered",
               status == L65M_ERR_STATE && !work.busy && !work.finished
               && work.transport_status == L65M_COMMIT_TRANSPORT_ABI);
        l65m_commit_work_release();
    }

    status = l65m_commit_work_prepare(&work, source, plan);
    expect("commit-enter", "context-size mutation prepare failed",
           status == L65M_OK);
    if (status == L65M_OK) {
        work.context_size++;
        status = (l65m_status)l65m_commit_phase_verify(&work);
        expect("commit-enter", "context-size mutation entered",
               status == L65M_ERR_STATE && !work.busy && !work.finished
               && work.transport_status == L65M_COMMIT_TRANSPORT_ABI);
        l65m_commit_work_release();
    }

    status = l65m_commit_work_prepare(&work, source, plan);
    expect("commit-enter", "cookie mutation prepare failed", status == L65M_OK);
    if (status == L65M_OK) {
        work.cookie ^= 1u;
        status = (l65m_status)l65m_commit_phase_verify(&work);
        expect("commit-enter", "cookie mutation entered",
               status == L65M_ERR_STATE && !work.busy && !work.finished
               && work.transport_status == L65M_COMMIT_TRANSPORT_COOKIE);
        l65m_commit_work_release();
    }

    status = l65m_commit_work_prepare(&work, source, plan);
    expect("commit-enter", "phase mutation prepare failed", status == L65M_OK);
    if (status == L65M_OK) {
        status = (l65m_status)l65m_commit_phase_entries(&work);
        expect("commit-enter", "phase mutation entered",
               status == L65M_ERR_STATE && !work.busy && !work.finished
               && work.transport_status == L65M_COMMIT_TRANSPORT_PHASE);
        l65m_commit_work_release();
    }

    status = l65m_commit_work_prepare(&work, source, plan);
    expect("commit-enter", "final-state prepare failed", status == L65M_OK);
    if (status == L65M_OK) {
        work.expected_phase = L65M_COMMIT_PHASE_ENTRIES;
        work.cookie = (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE
                                 ^ L65M_COMMIT_PHASE_ENTRIES);
        work.entry_count = 0;
        status = (l65m_status)l65m_commit_phase_entries(&work);
        expect("commit-enter", "valid enter did not finish fail-closed",
               status == L65M_ERR_STATE && !work.busy && work.finished
               && work.transport_status == L65M_COMMIT_TRANSPORT_OK
               && work.expected_phase == L65M_COMMIT_PHASE_COUNT
               && work.cookie == (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE
                                             ^ L65M_COMMIT_PHASE_COUNT));
        l65m_commit_work_release();
    }
}

static l65m_status commit_step(l65m_commit_work *work) {
    switch (work->expected_phase) {
    case L65M_COMMIT_PHASE_VERIFY:
        return (l65m_status)l65m_commit_phase_verify(work);
    case L65M_COMMIT_PHASE_PATCH_RECORD:
        return (l65m_status)l65m_commit_phase_patch_record(work);
    case L65M_COMMIT_PHASE_MATERIALIZE_SHAPE:
        return (l65m_status)l65m_commit_phase_materialize_shape(work);
    case L65M_COMMIT_PHASE_MATERIALIZE_SCALARS:
        return (l65m_status)l65m_commit_phase_materialize_scalars(work);
    case L65M_COMMIT_PHASE_MATERIALIZE_STRINGS:
        return (l65m_status)l65m_commit_phase_materialize_strings(work);
    case L65M_COMMIT_PHASE_PATCH_PUBLISH:
        return (l65m_status)l65m_commit_phase_patch_publish(work);
    case L65M_COMMIT_PHASE_ENTRIES:
        return (l65m_status)l65m_commit_phase_entries(work);
    default:
        return L65M_ERR_STATE;
    }
}

static l65m_status prepare_commit_phase(const l65m_contract_case *test,
                                        l65m_source *source, l65m_plan *plan,
                                        l65m_commit_work *work,
                                        uint8_t target_phase) {
    l65m_status status = vm_preflight_lib_ext(source, plan);
    if (status != L65M_OK) return status;
    stage_blob(test, plan);
    status = l65m_commit_work_prepare(work, source, plan);
    while (status == L65M_OK && work->expected_phase < target_phase)
        status = commit_step(work);
    return status;
}

/* The caller owns one GC root at GC_TOP. Fill the remaining heap with a live
 * chain so the next product allocation must take the real alloc()->GC->OOM path. */
static void exhaust_heap_at_root(const char *name) {
    obj next;
    do {
        next = cons(NIL, gc_rootstack[GC_TOP]);
        if (next != NIL) GC_SET(GC_TOP, next);
    } while (next != NIL);
    expect(name, "heap exhaustion left free cells", mem_free_cells() == 0);
    mem_oom = 0;
}

static void check_commit_allocation_site_oom(const l65m_contract_case *test,
                                             l65m_source *source) {
    l65m_commit_work work, reusable;
    l65m_plan plan;
    l65m_status status;
    obj keep = intern("%lit-keep"), keep_before;
    uint16_t directory_before, i, macro_index = 0xffffu, watermark;

    /* Scalar materialization only installs immediates and preallocated shape
     * cells. In the SYMI design intern() does not allocate a heap cell. Prove
     * that contract by running the complete phase with no free heap cells. */
    keep_before = sym_value(keep);
    status = prepare_commit_phase(test, source, &plan, &work,
                                  L65M_COMMIT_PHASE_MATERIALIZE_SCALARS);
    expect("commit-scalar-no-allocation", "could not reach scalar phase",
           status == L65M_OK
           && work.expected_phase == L65M_COMMIT_PHASE_MATERIALIZE_SCALARS);
    if (status == L65M_OK) {
        watermark = vm_ext_code_watermark();
        GC_PUSH(NIL);
        exhaust_heap_at_root("commit-scalar-no-allocation");
        while (status == L65M_OK
               && work.expected_phase == L65M_COMMIT_PHASE_MATERIALIZE_SCALARS)
            status = commit_step(&work);
        expect("commit-scalar-no-allocation",
               "scalar phase allocated from an exhausted heap",
               status == L65M_OK && mem_oom == 0
               && work.expected_phase == L65M_COMMIT_PHASE_MATERIALIZE_STRINGS);
        l65m_commit_work_release();
        GC_POPN(1);
        expect("commit-scalar-no-allocation",
               "scalar release did not restore the keep checkpoint",
               sym_value(keep) == keep_before);
        expect("commit-scalar-no-allocation",
               "scalar release rolled back the append-only reservation",
               vm_ext_code_watermark() == watermark);
        gc_collect();
    } else {
        l65m_commit_work_release();
    }
    mem_oom = 0;

    /* Nested-string materialization has no allocation site in this fixture;
     * root strings are created during patch publication. Leave every heap cell
     * live so str_open() takes the real alloc()->GC->OOM path there. */
    keep_before = sym_value(keep);
    status = prepare_commit_phase(test, source, &plan, &work,
                                  L65M_COMMIT_PHASE_PATCH_PUBLISH);
    expect("commit-string-allocation-oom", "could not reach patch-publish phase",
           status == L65M_OK
           && work.expected_phase == L65M_COMMIT_PHASE_PATCH_PUBLISH);
    if (status == L65M_OK) {
        watermark = vm_ext_code_watermark();
        GC_PUSH(NIL);
        exhaust_heap_at_root("commit-string-allocation-oom");
        while (status == L65M_OK
               && work.expected_phase == L65M_COMMIT_PHASE_PATCH_PUBLISH)
            status = commit_step(&work);
        expect("commit-string-allocation-oom",
               "str_open allocation did not report heap OOM",
               status == L65M_ERR_HEAP && mem_oom
               && work.commit_status == L65M_ERR_HEAP
               && work.finished && !work.busy);
        l65m_commit_work_release();
        GC_POPN(1);
        expect("commit-string-allocation-oom",
               "string OOM did not restore the keep checkpoint",
               sym_value(keep) == keep_before);
        expect("commit-string-allocation-oom",
               "string OOM rolled back the append-only reservation",
               vm_ext_code_watermark() == watermark);
        mem_oom = 0;
        gc_collect();
    } else {
        l65m_commit_work_release();
    }
    mem_oom = 0;

    /* Entry publication allocates only T_MACRO wrappers. Advance to the macro
     * entry, then exhaust the heap immediately before that alloc(T_MACRO). */
    keep_before = sym_value(keep);
    status = prepare_commit_phase(test, source, &plan, &work,
                                  L65M_COMMIT_PHASE_ENTRIES);
    expect("commit-entry-allocation-oom", "could not reach entry phase",
           status == L65M_OK && work.expected_phase == L65M_COMMIT_PHASE_ENTRIES);
    if (status == L65M_OK) {
        for (i = 0; i < plan.entry_count; i++) {
            const uint8_t *entry = metadata_at(
                test, &plan, (uint16_t)(plan.entries_off + i * 8u));
            if (entry[3] & 1u) {
                macro_index = i;
                break;
            }
        }
        expect("commit-entry-allocation-oom", "fixture has no macro entry",
               macro_index != 0xffffu);
        if (macro_index == 0xffffu) {
            l65m_commit_work_release();
            mem_oom = 0;
            return;
        }
        while (status == L65M_OK && work.cursor < macro_index)
            status = commit_step(&work);
        expect("commit-entry-allocation-oom",
               "could not stop immediately before macro publication",
               status == L65M_OK && work.cursor == macro_index
               && work.expected_phase == L65M_COMMIT_PHASE_ENTRIES);
        directory_before = vm_dir_count();
        GC_PUSH(NIL);
        exhaust_heap_at_root("commit-entry-allocation-oom");
        status = commit_step(&work);
        expect("commit-entry-allocation-oom",
               "alloc(T_MACRO) did not report heap OOM",
               status == L65M_ERR_HEAP && mem_oom
               && work.commit_status == L65M_ERR_HEAP
               && work.finished && !work.busy);
        expect("commit-entry-allocation-oom",
               "failed macro entry was published",
               vm_dir_count() == directory_before);
        l65m_commit_work_release();
        GC_POPN(1);
        if (macro_index) {
            expect("commit-entry-allocation-oom",
                   "post-publication OOM rolled back visible literal roots",
                   sym_value(keep) != keep_before);
        }
        mem_oom = 0;
        gc_collect();
        status = l65m_commit_work_prepare(&reusable, source, &plan);
        expect("commit-entry-allocation-oom",
               "source binding was not reusable after OOM cleanup",
               status == L65M_OK);
        if (status == L65M_OK) l65m_commit_work_release();
    } else {
        l65m_commit_work_release();
    }
    mem_oom = 0;
}

static void check_commit_late_phase_recovery(const l65m_contract_case *test,
                                             l65m_source *source) {
    static const uint8_t phases[] = {
        L65M_COMMIT_PHASE_MATERIALIZE_SCALARS,
        L65M_COMMIT_PHASE_MATERIALIZE_STRINGS,
        L65M_COMMIT_PHASE_ENTRIES
    };
    static const char *const names[] = {
        "commit-scalar-latched-oom", "commit-string-latched-oom",
        "commit-entry-latched-oom"
    };
    static const char *const abort_names[] = {
        "commit-scalar-abort", "commit-string-abort", "commit-entry-abort"
    };
    l65m_commit_work work, reusable;
    l65m_plan plan;
    l65m_status status;
    obj keep = intern("%lit-keep"), keep_before;
    uint16_t i, watermark, directory_before;

    /* Bank-5 reservations are append-only. Before the first Directory entry,
     * `%lit-keep` is transactional and release/abort restores its checkpoint. */
    for (i = 0; i < sizeof phases / sizeof phases[0]; i++) {
        keep_before = sym_value(keep);
        status = prepare_commit_phase(test, source, &plan, &work, phases[i]);
        expect(names[i], "could not reach target phase",
               status == L65M_OK && work.expected_phase == phases[i]);
        if (status != L65M_OK) {
            l65m_commit_work_release();
            continue;
        }
        watermark = vm_ext_code_watermark();
        expect(names[i], "target phase has no temporary literal roots",
               sym_value(keep) != keep_before);
        mem_oom = 1;
        status = commit_step(&work);
        expect(names[i], "latched OOM did not fail closed",
               status == L65M_ERR_HEAP && work.finished && !work.busy);
        l65m_commit_work_release();
        expect(names[i], "OOM did not restore the keep checkpoint",
               sym_value(keep) == keep_before);
        expect(names[i], "append-only reservation was rolled back",
               vm_ext_code_watermark() == watermark);
        mem_oom = 0;
        gc_collect();
    }

    for (i = 0; i < sizeof phases / sizeof phases[0]; i++) {
        keep_before = sym_value(keep);
        status = prepare_commit_phase(test, source, &plan, &work, phases[i]);
        expect(abort_names[i], "could not reach target phase",
               status == L65M_OK && work.expected_phase == phases[i]);
        if (status != L65M_OK) {
            l65m_commit_work_release();
            continue;
        }
        watermark = vm_ext_code_watermark();
        expect(abort_names[i], "target phase has no temporary literal roots",
               sym_value(keep) != keep_before);
        l65m_commit_abort_cleanup();
        expect(abort_names[i], "abort did not restore the keep checkpoint",
               sym_value(keep) == keep_before);
        expect(abort_names[i], "append-only reservation was rolled back",
               vm_ext_code_watermark() == watermark);
        gc_collect();
    }

    /* The first successful Directory publication is the commit sentinel.
     * Later abort is fail-stop: visible entries keep their literal roots. */
    keep_before = sym_value(keep);
    status = prepare_commit_phase(test, source, &plan, &work,
                                  L65M_COMMIT_PHASE_ENTRIES);
    expect("commit-entry-fail-stop", "could not reach entry publication",
           status == L65M_OK
           && work.expected_phase == L65M_COMMIT_PHASE_ENTRIES);
    if (status == L65M_OK) {
        directory_before = vm_dir_count();
        status = commit_step(&work);
        expect("commit-entry-fail-stop", "first entry was not published",
               status == L65M_OK && work.cursor == 1u
               && vm_dir_count() >= directory_before);
        l65m_commit_abort_cleanup();
        expect("commit-entry-fail-stop", "published roots were rolled back",
               sym_value(keep) != keep_before);
        status = l65m_commit_work_prepare(&reusable, source, &plan);
        expect("commit-entry-fail-stop", "fail-stop retained source binding",
               status == L65M_OK);
        if (status == L65M_OK) l65m_commit_work_release();
    }
    mem_oom = 0;
}

static void check_commit_oom_recovery(const l65m_contract_case *test) {
    uint8_t source_data[test->len];
    bytes_source bytes = { source_data, test->len, 0, 0 };
    l65m_source source = { read_bytes, &bytes, test->len };
    l65m_commit_work work, recovered;
    l65m_plan plan;
    l65m_status status;
    uint16_t patch_index, aggregate_patch = 0xffffu;
    obj exhaustion = NIL, next, keep, keep_before;

    memcpy(source_data, test->data, test->len);
    status = vm_preflight_lib_ext(&source, &plan);
    if (!expect("commit-oom", "preflight failed", status == L65M_OK)) return;
    check_commit_enter_mutations(&source, &plan);
    for (patch_index = 0; patch_index < plan.patch_count; patch_index++) {
        const uint8_t *patch = metadata_at(
            test, &plan, (uint16_t)(plan.patches_off + patch_index * 4u));
        uint16_t node_index = u16le(patch + 2);
        const uint8_t *node = metadata_at(
            test, &plan, (uint16_t)(plan.nodes_off + node_index * 10u));
        if (node[0] == TEST_LIT_CONS || node[0] == TEST_LIT_LIST) {
            aggregate_patch = patch_index;
            break;
        }
    }
    if (!expect("commit-oom", "fixture has no allocating aggregate patch",
                aggregate_patch != 0xffffu)) return;

    stage_blob(test, &plan);
    keep = intern("%lit-keep");
    keep_before = sym_value(keep);
    status = l65m_commit_work_prepare(&work, &source, &plan);
    if (!expect("commit-oom", "prepare failed", status == L65M_OK)) return;
    status = (l65m_status)l65m_commit_phase_verify(&work);
    expect("commit-oom", "phase-0 verification failed", status == L65M_OK);
    expect("commit-oom", "phase-0 reservation failed",
           vm_ext_code_watermark()
           == (uint16_t)(plan.code_base + plan.blob_len));
    do {
        status = (l65m_status)l65m_commit_phase_patch_record(&work);
    } while (status == L65M_OK
             && work.expected_phase == L65M_COMMIT_PHASE_PATCH_RECORD);
    expect("commit-oom", "patch-record pass failed", status == L65M_OK
           && work.expected_phase == L65M_COMMIT_PHASE_MATERIALIZE_SHAPE);
    while (status == L65M_OK && work.cursor < aggregate_patch)
        status = (l65m_status)l65m_commit_phase_materialize_shape(&work);
    expect("commit-oom", "shape pass did not reach aggregate fixture",
           status == L65M_OK && work.cursor == aggregate_patch);

    GC_PUSH(exhaustion);
    do {
        next = cons(NIL, gc_rootstack[GC_TOP]);
        if (next != NIL) GC_SET(GC_TOP, next);
    } while (next != NIL);
    mem_oom = 0;
    lisp_error_msg = NULL;
    status = (l65m_status)l65m_commit_phase_materialize_shape(&work);
    expect("commit-oom", "allocating phase did not report heap OOM",
           status == L65M_ERR_HEAP && work.commit_status == L65M_ERR_HEAP);
    expect("commit-oom", "OOM left commit busy or unfinished",
           !work.busy && work.finished
           && work.expected_phase == L65M_COMMIT_PHASE_COUNT);
    expect("commit-oom", "OOM escaped through lisp_abort", lisp_error_msg == NULL);
    expect("commit-oom", "OOM latched commit transport",
           work.transport_status == L65M_COMMIT_TRANSPORT_OK);
    GC_POPN(1);
    l65m_commit_work_release();
    expect("commit-oom", "OOM rollback changed the literal keep checkpoint",
           sym_value(keep) == keep_before);
    gc_collect();
    mem_oom = 0;

    status = l65m_commit_work_prepare(&recovered, &source, &plan);
    expect("commit-oom", "binding was not reusable after cleanup", status == L65M_OK);
    if (status == L65M_OK) {
        recovered.expected_phase = L65M_COMMIT_PHASE_ENTRIES;
        recovered.cookie = (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE
                                      ^ L65M_COMMIT_PHASE_ENTRIES);
        recovered.entry_count = 1;
        recovered.cursor = 1;
        status = (l65m_status)l65m_commit_phase_entries(&recovered);
        expect("commit-cursor", "exhausted entry budget did not fail closed",
               status == L65M_ERR_STATE && recovered.finished && !recovered.busy);
        l65m_commit_work_release();
    }

    mem_oom = 0;
    status = vm_preflight_lib_ext(&source, &plan);
    expect("commit-abort", "rollback preflight failed", status == L65M_OK);
    stage_blob(test, &plan);
    keep_before = sym_value(keep);
    status = l65m_commit_work_prepare(&recovered, &source, &plan);
    expect("commit-abort", "prepare before abort cleanup failed", status == L65M_OK);
    if (status == L65M_OK)
        status = (l65m_status)l65m_commit_phase_verify(&recovered);
    if (status == L65M_OK)
        expect("commit-abort", "phase-0 rollback reservation failed",
               vm_ext_code_watermark()
               == (uint16_t)(plan.code_base + plan.blob_len));
    while (status == L65M_OK
           && recovered.expected_phase == L65M_COMMIT_PHASE_PATCH_RECORD)
        status = (l65m_status)l65m_commit_phase_patch_record(&recovered);
    while (status == L65M_OK
           && recovered.expected_phase == L65M_COMMIT_PHASE_MATERIALIZE_SHAPE
           && recovered.cursor <= aggregate_patch)
        status = (l65m_status)l65m_commit_phase_materialize_shape(&recovered);
    expect("commit-abort", "shape pass did not stage a temporary keep root",
           status == L65M_OK && sym_value(keep) != keep_before);
    if (status == L65M_OK) l65m_commit_abort_cleanup();
    expect("commit-abort", "abort cleanup did not restore literal keep checkpoint",
           sym_value(keep) == keep_before);
    status = l65m_commit_work_prepare(&work, &source, &plan);
    expect("commit-abort", "abort cleanup retained the source binding", status == L65M_OK);
    if (status == L65M_OK) l65m_commit_work_release();
    mem_oom = 0;
    check_commit_late_phase_recovery(test, &source);
    check_commit_allocation_site_oom(test, &source);
}

int main(void) {
    uint16_t i;
    const l65m_contract_case *commit_case = 0;
    const l65m_contract_case *depth_case = 0;

    memset(bank5, 0xa5, sizeof bank5);
    mem_init();
    vm_dir_reset();
    vm_init();
    sentinel = intern("l65m-test-sentinel");
    (void)intern("%lit-keep");
    set_sym_value(sentinel, MKFIX(17));
    expect("setup", "could not reserve baseline code", vm_ext_code_alloc(16, 1) == 0);
    expect("setup", "could not register sentinel", vm_dir_add(sentinel, 5, 0, 1) == 0);
    set_sym_function(sentinel, MK_BCODE(0));
    check_repeat_guard();
    check_commit_batch_predicate();

    for (i = 0; i < l65m_contract_case_count; i++) {
        const l65m_contract_case *test = &l65m_contract_cases[i];
        bytes_source bytes = { test->data, test->len, 0, 0 };
        l65m_source source = { read_bytes, &bytes, test->len };
        l65m_plan plan;
        protected_state before;
        l65m_status status;

        capture_state(&before);
        memset(&plan, 0xa5, sizeof plan);
        status = vm_preflight_lib_ext(&source, &plan);
        expect_status(test->name, status, test->expected_status);
        expect_unchanged(test->name, &before);
        if (test->valid && status == L65M_OK) {
            expect(test->name, "valid entry count differs from fixture",
                   plan.entry_count == test->expected_entry_count);
            expect(test->name, "valid patch count differs from fixture",
                   plan.patch_count == test->expected_patch_count);
            expect(test->name, "valid macro count differs from fixture",
                   macro_count(test, &plan) == test->expected_macro_count);
            if (commit_case == 0 || test->expected_patch_count > commit_case->expected_patch_count)
                commit_case = test;
            if (strcmp(test->name, "valid-literal-depth-9") == 0)
                depth_case = test;
        }
    }

    if (expect("depth-contract", "no valid depth-9 generated case", depth_case != 0))
        run_depth_commit_case(depth_case);
    if (expect("golden", "no valid generated case", commit_case != 0))
        run_commit_case(commit_case);
    if (commit_case != 0) check_disk_carrier_framing(commit_case);
    if (commit_case != 0) check_commit_oom_recovery(commit_case);

    if (failed) {
        fprintf(stderr, "l65m-native-loader: FAIL cases=%u failures=%d\n",
                (unsigned)l65m_contract_case_count, failed);
        return 1;
    }
    printf("l65m-native-loader: PASS cases=%u commit=%s depth=%s\n",
           (unsigned)l65m_contract_case_count, commit_case->name,
           depth_case->name);
    return 0;
}
