/* Native product-path proof for Directory-only L65M v2. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "l65m-v2-product-cases.h"
#include "l65m_commit_overlay.h"
#include "l65m_overlay_abi.h"
#include "l65m_validate.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

static uint8_t bank5[65536];
static int failures;

/* Exact native-service subset reached by ide-make-state's budget string.  The
 * carrier owns the full service differential; this fixture keeps its scope on
 * sequential L65M publication while using the same observable values. */
uint8_t eval_v2_workbench_service(uint8_t id, const obj *args, obj *result) {
    (void)args;
    if (id == 42u) *result = MKFIX((int16_t)sym_count());
    else if (id == 43u) *result = MKFIX((int16_t)sym_max());
    else return 0;
    return 1;
}

typedef struct {
    const uint8_t *data;
    uint16_t length;
    uint16_t reads;
    uint16_t fail_at;
} byte_source;

static uint16_t u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint8_t read_source(void *opaque, uint16_t off, uint8_t *dst, uint16_t len) {
    byte_source *source = opaque;
    source->reads++;
    if (source->fail_at && source->reads == source->fail_at) return 0;
    if (off > source->length || len > (uint16_t)(source->length - off)) return 0;
    memcpy(dst, source->data + off, len);
    return 1;
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    if (bank != 5 || (uint32_t)off + len > sizeof bank5) memset(dst, 0, len);
    else memcpy(dst, bank5 + off, len);
}

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
    if (bank != 5 || (uint32_t)off + len > sizeof bank5) {
        failures++;
        return;
    }
    memcpy(bank5 + off, src, len);
}

void sympool_read(uint16_t off, char *dst, uint16_t len) {
    memcpy(dst, bank5 + 0xd000u + off, len);
}

void sympool_write(uint16_t off, const char *src, uint16_t len) {
    memcpy(bank5 + 0xd000u + off, src, len);
}

static void check(const char *id, const char *message, int condition) {
    if (condition) return;
    fprintf(stderr, "l65m-v2-product: FAIL %s: %s\n", id, message);
    failures++;
}

static const uint8_t *metadata(const uint8_t *image, const l65m_plan *plan,
                               uint16_t relative) {
    return image + plan->source_metadata_off + relative;
}

static l65m_status preflight(const uint8_t *data, uint16_t length,
                             byte_source *bytes, l65m_source *source,
                             l65m_plan *plan) {
    bytes->data = data; bytes->length = length; bytes->reads = 0; bytes->fail_at = 0;
    source->read = read_source; source->ctx = bytes; source->length = length;
    return vm_preflight_lib_ext(source, plan);
}

static void stage(const uint8_t *image, const l65m_plan *plan) {
    vm_ext_write(image + plan->source_blob_off, plan->blob_len, 5, plan->code_base);
}

static uint8_t symbol_exists(void *unused, const char *name) {
    obj found;
    (void)unused;
    return sym_lookup(name, &found);
}

static l65m_status commit_step(l65m_commit_work *work) {
    switch (work->expected_phase) {
    case L65M_COMMIT_PHASE_VERIFY: return (l65m_status)l65m_commit_phase_verify(work);
    case L65M_COMMIT_PHASE_PATCH_RECORD: return (l65m_status)l65m_commit_phase_patch_record(work);
    case L65M_COMMIT_PHASE_MATERIALIZE_SHAPE: return (l65m_status)l65m_commit_phase_materialize_shape(work);
    case L65M_COMMIT_PHASE_MATERIALIZE_SCALARS: return (l65m_status)l65m_commit_phase_materialize_scalars(work);
    case L65M_COMMIT_PHASE_MATERIALIZE_STRINGS: return (l65m_status)l65m_commit_phase_materialize_strings(work);
    case L65M_COMMIT_PHASE_PATCH_PUBLISH: return (l65m_status)l65m_commit_phase_patch_publish(work);
    case L65M_COMMIT_PHASE_ENTRIES: return (l65m_status)l65m_commit_phase_entries(work);
    default: return L65M_ERR_STATE;
    }
}

static l65m_status validation_step(l65m_overlay_work *work, uint8_t phase) {
    static l65m_overlay_entry_fn const entries[] = {
        l65m_overlay_phase_00, l65m_overlay_phase_01, l65m_overlay_phase_02,
        l65m_overlay_phase_03, l65m_overlay_phase_04, l65m_overlay_phase_05,
        l65m_overlay_phase_06, l65m_overlay_phase_07, l65m_overlay_phase_08,
        l65m_overlay_phase_09, l65m_overlay_phase_10, l65m_overlay_phase_11,
        l65m_overlay_phase_12, l65m_overlay_phase_13, l65m_overlay_phase_14,
        l65m_overlay_phase_15, l65m_overlay_phase_16, l65m_overlay_phase_17,
        l65m_overlay_phase_18, l65m_overlay_phase_19, l65m_overlay_phase_20,
    };
    return (l65m_status)entries[phase](work);
}

static void check_validation_aborts(void) {
    byte_source bytes = { l65m_v2_ide_data, sizeof l65m_v2_ide_data, 0, 0 };
    l65m_source source = { read_source, &bytes, sizeof l65m_v2_ide_data };
    uint8_t target;
    for (target = 0; target < L65M_OVERLAY_PHASE_COUNT; target++) {
        l65m_limits limits;
        l65m_plan plan;
        l65m_overlay_work work;
        l65m_status status = L65M_OK;
        uint8_t phase;
        uint16_t dirs = vm_dir_count(), symbols = sym_count(), names = sym_pool_used();
        limits.dir_count = dirs; limits.dir_capacity = vm_dir_capacity();
        limits.symbol_count = symbols; limits.symbol_capacity = sym_max();
        limits.namepool_used = names; limits.namepool_capacity = sym_pool_capacity();
        limits.heap_free = mem_free_cells();
        limits.arena_used = str_arena_used(); limits.arena_capacity = str_arena_capacity();
        limits.roots_used = gc_rootsp; limits.roots_capacity = GC_ROOTS;
        limits.string_arena = 1; limits.symbol_exists = symbol_exists; limits.symbol_ctx = 0;
        bytes.reads = 0; bytes.fail_at = 0;
        l65m_overlay_work_init(&work, &source, vm_ext_code_watermark(), &limits, &plan);
        for (phase = 0; phase <= target && status == L65M_OK; phase++)
            do status = validation_step(&work, phase);
            while (status == L65M_OK && work.expected_phase == phase);
        check("validation-abort", "phase prefix failed", status == L65M_OK);
        check("validation-abort", "discarded phase prefix mutated product state",
              vm_dir_count() == dirs && sym_count() == symbols
              && sym_pool_used() == names && gc_rootsp == limits.roots_used);
    }
}

static void check_commit_matrix(void) {
    uint8_t target;
    for (target = 0; target < L65M_COMMIT_PHASE_COUNT; target++) {
        byte_source bytes;
        l65m_source source;
        l65m_plan plan;
        l65m_commit_work work;
        l65m_status status = preflight(l65m_v2_idex_data, sizeof l65m_v2_idex_data,
                                       &bytes, &source, &plan);
        if (status != L65M_OK)
            fprintf(stderr, "l65m-v2-product: source-read preflight status=%u watermark=%u dirs=%u symbols=%u names=%u heap=%u\n",
                    (unsigned)status, (unsigned)vm_ext_code_watermark(),
                    (unsigned)vm_dir_count(), (unsigned)sym_count(),
                    (unsigned)sym_pool_used(), (unsigned)mem_free_cells());
        check("commit-abort", "IDEX preflight failed", status == L65M_OK);
        if (status != L65M_OK) continue;
        stage(l65m_v2_idex_data, &plan);
        status = l65m_commit_work_prepare(&work, &source, &plan);
        while (status == L65M_OK && work.expected_phase < target)
            status = commit_step(&work);
        check("commit-abort", "could not reach contracted phase",
              status == L65M_OK && work.expected_phase == target);
        l65m_commit_abort_cleanup();
        gc_collect();
    }

    {
        byte_source bytes;
        l65m_source source;
        l65m_plan plan, retry;
        l65m_commit_work work, reusable;
        l65m_status status = preflight(l65m_v2_idex_data, sizeof l65m_v2_idex_data,
                                       &bytes, &source, &plan);
        if (status != L65M_OK)
        {
            uint16_t preview = 0xffffu;
            uint8_t preview_ok = vm_ext_code_preview(u16(l65m_v2_idex_data), &preview);
            fprintf(stderr, "l65m-v2-product: read-case preflight status=%u watermark=%u preview=%u/%u heap=%u arena=%u\n",
                    (unsigned)status, (unsigned)vm_ext_code_watermark(),
                    (unsigned)preview_ok, (unsigned)preview,
                    (unsigned)mem_free_cells(), (unsigned)str_arena_used());
        }
        check("commit-source-read", "preflight failed", status == L65M_OK);
        if (status == L65M_OK) {
            stage(l65m_v2_idex_data, &plan);
            status = l65m_commit_work_prepare(&work, &source, &plan);
            if (status == L65M_OK) status = commit_step(&work);
            bytes.fail_at = (uint16_t)(bytes.reads + 1u);
            if (status == L65M_OK) status = commit_step(&work);
            check("commit-source-read", "read failure did not fail closed",
                  status == L65M_ERR_SOURCE && work.finished);
            l65m_commit_work_release();
        }
        bytes.fail_at = 0;
        status = preflight(l65m_v2_idex_data, sizeof l65m_v2_idex_data,
                           &bytes, &source, &retry);
        if (status != L65M_OK)
            fprintf(stderr, "l65m-v2-product: recovery preflight status=%u\n", (unsigned)status);
        check("commit-latch-recovery", "fresh preflight after source failure failed",
              status == L65M_OK);
        if (status == L65M_OK) {
            stage(l65m_v2_idex_data, &retry);
            status = l65m_commit_work_prepare(&reusable, &source, &retry);
            check("commit-latch-recovery", "commit source latch was not reusable",
                  status == L65M_OK);
            if (status == L65M_OK) l65m_commit_work_release();
        }
    }

    {
        byte_source bytes;
        l65m_source source;
        l65m_plan plan;
        l65m_commit_work work;
        l65m_status status = preflight(l65m_v2_idex_data, sizeof l65m_v2_idex_data,
                                       &bytes, &source, &plan);
        if (status != L65M_OK)
            fprintf(stderr, "l65m-v2-product: oom preflight status=%u\n", (unsigned)status);
        check("commit-oom-after-ext", "preflight failed", status == L65M_OK);
        if (status == L65M_OK) {
            stage(l65m_v2_idex_data, &plan);
            status = l65m_commit_work_prepare(&work, &source, &plan);
            if (status == L65M_OK) status = commit_step(&work);
            mem_oom = 1;
            while (status == L65M_OK && !work.finished) status = commit_step(&work);
            check("commit-oom-after-ext", "latched OOM did not fail closed after reservation",
                  status == L65M_ERR_HEAP && work.finished);
            l65m_commit_work_release();
            mem_oom = 0;
            gc_collect();
        }
    }
}

static void check_entry_refs(const uint8_t *image, const l65m_plan *plan) {
    uint16_t patch_index, found = 0;
    uint16_t dir_base = (uint16_t)((plan->dir_before + 7u) & ~7u);
    for (patch_index = 0; patch_index < plan->patch_count; patch_index++) {
        const uint8_t *patch = metadata(
            image, plan, (uint16_t)(plan->patches_off + patch_index * 4u));
        uint16_t blob_off = u16(patch), node_index = u16(patch + 2);
        const uint8_t *node = metadata(
            image, plan, (uint16_t)(plan->nodes_off + node_index * 10u));
        if (node[0] == 8u) {
            obj value = (obj)u16(bank5 + plan->code_base + blob_off);
            found++;
            check("entry-ref", "materialized value is not the local Directory ordinal",
                  value == MK_BCODE((uint16_t)(dir_base + u16(node + 4))));
        }
    }
    check("entry-ref", "entry-ref node count drift", found == L65M_V2_IDE_ENTRY_REFS);
}

static obj invoke_route(const char *route, obj fn, obj argument) {
    obj flat[2], list, result;
    vm_status = VM_OK;
    if (!strcmp(route, "direct")) return vm_run_dir((int)BCODE_IDX(fn), &argument, 1);
    if (!strcmp(route, "funcall")) {
        flat[0] = fn; flat[1] = argument;
        return vm_directory_only_test_callprim(8, flat, 2);
    }
    GC_PUSH(argument);
    list = cons(argument, NIL);
    argument = gc_rootstack[GC_TOP];
    GC_SET(GC_TOP, list);
    flat[0] = fn; flat[1] = list;
    result = vm_directory_only_test_callprim(7, flat, 2);
    GC_POPN(1);
    (void)argument;
    return result;
}

static void check_designators(const uint8_t *image, const l65m_plan *plan) {
    static const char *const routes[] = { "direct", "funcall", "apply" };
    uint16_t dir_base = (uint16_t)((plan->dir_before + 7u) & ~7u), site_index;
    for (site_index = 0; site_index < L65M_V2_DESIGNATOR_SITE_COUNT; site_index++) {
        const l65m_v2_designator_site *site = &l65m_v2_designator_sites[site_index];
        const uint8_t *entry = metadata(
            image, plan, (uint16_t)(plan->entries_off + site->caller_ordinal * 8u));
        uint16_t literal_off = (uint16_t)(u16(entry + 4) + 7u + 2u * site->literal_slot);
        obj fn = (obj)u16(bank5 + plan->code_base + literal_off);
        const char *text = "x";
        obj expected = site_index == 0 ? NIL : intern("t");
        uint8_t route;
        check(site->id, "designator literal did not resolve to the contracted ordinal",
              fn == MK_BCODE((uint16_t)(dir_base + site->target_ordinal)));
        for (route = 0; route < 3; route++) {
            obj string = str_from_bytes((const uint8_t *)text, (uint16_t)strlen(text));
            obj result;
            GC_PUSH(string);
            result = invoke_route(routes[route], fn, string);
            GC_POPN(1);
            check(site->id, routes[route], vm_status == VM_OK && result == expected);
        }
        {
            char want[32];
            vm_status = VM_OK;
            (void)vm_run_dir((int)BCODE_IDX(fn), 0, 0);
            snprintf(want, sizeof want, "entry #%u", (unsigned)BCODE_IDX(fn));
            check(site->id, "global diagnostic index is not host-resolvable",
                  vm_status == VM_ARITY && strstr(vm_status_message(), want) != 0);
        }
    }
}

static int string_is(obj value, const char *expected) {
    uint16_t index, length = (uint16_t)strlen(expected);
    if (!IS_PTR(value) || cell_type(value) != T_STR || str_len(value) != length)
        return 0;
    for (index = 0; index < length; index++)
        if (str_byte(value, index) != (uint8_t)expected[index]) return 0;
    return 1;
}

static obj call_named(const char *id, const char *name, obj *args, uint8_t argc) {
    obj symbol, function;
    if (!sym_lookup(name, &symbol)) {
        check(id, "named function symbol is not published", 0);
        return NIL;
    }
    function = sym_function(symbol);
    if (!IS_BCODE(function)) {
        check(id, "named function cell is not bytecode", 0);
        return NIL;
    }
    vm_status = VM_OK;
    function = vm_run_dir((int)BCODE_IDX(function), args, argc);
    if (vm_status != VM_OK)
        fprintf(stderr, "l65m-v2-product: %s call %s failed: %s\n",
                id, name, vm_status_message());
    check(id, "named function execution failed", vm_status == VM_OK);
    return function;
}

static void check_override_sequence(void) {
    static const char id[] = "ide-idex-late-bound-hook";
    byte_source bytes;
    l65m_source source;
    l65m_plan plan;
    l65m_commit_work work;
    l65m_status status;
    obj hook_symbol, core_hook, idex_hook;
    obj scratch, empty, lines, buffer, state, marker;
    obj args[4];

    if (!sym_lookup("%ide-x", &hook_symbol)) {
        check(id, "provider hook symbol is not published", 0);
        return;
    }
    core_hook = sym_function(hook_symbol);
    check(id, "provider hook function cell is not bytecode", IS_BCODE(core_hook));

    status = preflight(l65m_v2_idex_data, sizeof l65m_v2_idex_data,
                       &bytes, &source, &plan);
    if (status != L65M_OK)
        fprintf(stderr,
                "l65m-v2-product: %s IDEX preflight status=%u dirs=%u symbols=%u names=%u heap=%u arena=%u\n",
                id, (unsigned)status, (unsigned)vm_dir_count(),
                (unsigned)sym_count(), (unsigned)sym_pool_used(),
                (unsigned)mem_free_cells(), (unsigned)str_arena_used());
    check(id, "IDEX preflight failed", status == L65M_OK);
    if (status != L65M_OK) return;
    stage(l65m_v2_idex_data, &plan);
    status = l65m_commit_work_prepare(&work, &source, &plan);
    while (status == L65M_OK && !work.finished) status = commit_step(&work);
    l65m_commit_work_release();
    check(id, "IDEX commit failed", status == L65M_OK);
    if (status != L65M_OK) return;

    idex_hook = sym_function(hook_symbol);
    check(id, "override did not replace the provider function cell",
          IS_BCODE(idex_hook) && idex_hook != core_hook);
    if (!IS_BCODE(idex_hook) || idex_hook == core_hook) return;

    scratch = str_from_bytes((const uint8_t *)"scratch", 7);
    GC_PUSH(scratch);
    empty = str_from_bytes((const uint8_t *)"", 0);
    GC_PUSH(empty);
    lines = cons(empty, NIL);
    GC_PUSH(lines);
    args[0] = scratch; args[1] = lines;
    buffer = call_named(id, "ide-make-buffer", args, 2);
    GC_PUSH(buffer);
    args[0] = buffer;
    state = call_named(id, "ide-make-state", args, 1);
    GC_PUSH(state);
    args[0] = intern("motion"); args[1] = state; args[2] = MKFIX(1013); args[3] = NIL;
    vm_status = VM_OK;
    state = vm_run_dir((int)BCODE_IDX(idex_hook), args, 4);
    if (vm_status != VM_OK)
        fprintf(stderr, "l65m-v2-product: %s override call failed: %s\n",
                id, vm_status_message());
    check(id, "overriding hook execution failed", vm_status == VM_OK);
    GC_SET(GC_TOP, state);
    args[0] = state; args[1] = MKFIX(80);
    marker = call_named(id, "ide-status-line", args, 2);
    check(id, "M-x marker drift after real sequential commits",
          string_is(marker, "M-x [find-file]"));
    GC_POPN(5);
}

static void check_native_negatives(void) {
    uint8_t image[sizeof l65m_v2_ide_data];
    byte_source bytes;
    l65m_source source;
    l65m_plan plan;
    uint16_t blob_len = u16(l65m_v2_ide_data), md, entries, nodes, entry_count, node_count, i;
    struct mutation { const char *id; l65m_status expected; } cases[] = {
        { "unknown-version", L65M_ERR_HEADER },
        { "v1-sentinel", L65M_ERR_ENTRIES },
        { "anonymous-macro", L65M_ERR_ENTRIES },
        { "entry-ref-range", L65M_ERR_NODE },
    };
    md = (uint16_t)(4u + blob_len);
    entries = u16(l65m_v2_ide_data + md + 24u);
    nodes = u16(l65m_v2_ide_data + md + 28u);
    entry_count = u16(l65m_v2_ide_data + md + 16u);
    node_count = u16(l65m_v2_ide_data + md + 20u);
    for (i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        uint16_t node;
        memcpy(image, l65m_v2_ide_data, sizeof image);
        if (i == 0) image[md + 4u] = 3u;
        else if (i == 1) image[md + 4u] = 1u;
        else if (i == 2) image[md + entries + 3u] |= 1u;
        else {
            for (node = 0; node < node_count; node++)
                if (image[md + nodes + node * 10u] == 8u) break;
            image[md + nodes + node * 10u + 4u] = (uint8_t)entry_count;
            image[md + nodes + node * 10u + 5u] = (uint8_t)(entry_count >> 8);
        }
        check(cases[i].id, "native validator accepted/reclassified mutation",
              preflight(image, sizeof image, &bytes, &source, &plan) == cases[i].expected);
    }
}

static void check_product_commit(void) {
    byte_source bytes;
    l65m_source source;
    l65m_plan plan;
    l65m_status status = preflight(
        l65m_v2_ide_data, sizeof l65m_v2_ide_data, &bytes, &source, &plan);
    uint16_t symbols_before = sym_count(), names_before = sym_pool_used();
    check("preflight", "IDE v2 did not validate", status == L65M_OK);
    check("preflight", "format/count contract drift",
          plan.format_version == 2u && plan.entry_count == L65M_V2_IDE_ENTRIES
          && plan.patch_count == L65M_V2_IDE_PATCHES);
    if (status != L65M_OK) return;
    stage(l65m_v2_ide_data, &plan);
    {
        l65m_commit_work work;
        status = l65m_commit_work_prepare(&work, &source, &plan);
        if (status == L65M_OK) status = commit_step(&work);
        while (status == L65M_OK && !work.finished) {
            gc_collect();
            status = commit_step(&work);
        }
        if (status != L65M_OK)
            fprintf(stderr, "l65m-v2-product: commit status=%u phase=%u cursor=%u transport=%u\n",
                    (unsigned)status, (unsigned)work.expected_phase,
                    (unsigned)work.cursor, (unsigned)work.transport_status);
        l65m_commit_work_release();
    }
    check("commit", "IDE v2 commit failed", status == L65M_OK);
    check("commit", "Directory ordinal publication drift", vm_dir_count() == plan.dir_after);
    check("commit", "symbol accounting drift", sym_count() == symbols_before + plan.new_symbols);
    check("commit", "namepool accounting drift", sym_pool_used() == names_before + plan.new_name_bytes);
    if (status == L65M_OK) {
        gc_collect();
        check_entry_refs(l65m_v2_ide_data, &plan);
        check_designators(l65m_v2_ide_data, &plan);
    }
}

int main(int argc, char **argv) {
    uint8_t transaction_mode = (uint8_t)(argc == 2
        && !strcmp(argv[1], "--transaction-matrix"));
    memset(bank5, 0xa5, sizeof bank5);
    mem_init();
    vm_dir_reset();
    vm_init();
    vm_ext_write(l65m_v2_resident_data, sizeof l65m_v2_resident_data,
                 lisp65_stdlib_bank, lisp65_stdlib_off);
    vm_load_embedded_stdlib();
    vm_directory_only_test_reclaim_boot_metadata();
    check("setup", "resident v2 closure did not publish string-equal",
          IS_BCODE(sym_function(intern("string-equal"))));
    check_product_commit();
    if (transaction_mode) {
        check_validation_aborts();
        check_commit_matrix();
    } else {
        check_native_negatives();
        check_override_sequence();
    }
    if (failures) {
        fprintf(stderr, "l65m-v2-product: FAIL failures=%d\n", failures);
        return 1;
    }
    printf("l65m-v2-product: PASS mode=%s entries=%u anonymous=%u entry_refs=%u designator_routes=12 hook_sequence=%u\n",
           transaction_mode ? "transaction-matrix" : "late-bound-sequence",
           (unsigned)L65M_V2_IDE_ENTRIES, (unsigned)L65M_V2_IDE_ANONYMOUS,
           (unsigned)L65M_V2_IDE_ENTRY_REFS, transaction_mode ? 0u : 1u);
    return 0;
}
