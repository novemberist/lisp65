/* 1.1-C1 temporary compiler lifetime.
 *
 * C1 deliberately owns no second resident checkpoint.  It consumes the exact
 * l65m_plan already produced by the shelf loader; the otherwise-unused source
 * context carries the one pre-existing export symbol.  Both records live in
 * reset-cleared BSS before C1 and therefore add zero resident state bytes.
 */
#include "c1_compiler_overlay.h"

#ifdef LISP65_C1_COMPILER_TIER

#include "buffer_overlay.h"
#include "c1_phase_probe.h"
#include "dialect-v2/libs/lcc-contract.h"
#include "io.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define C1_FN __attribute__((section(".lisp65_rt_c1_compiler"), noinline, used))
#else
#define C1_FN
#endif

static C1_FN uint8_t c1_plan_exact(const l65m_plan *plan) {
    /* The one-argument loader can only select the CRC32-bound shelf record.
     * These generated preflight fields bind that record to the exact compiler
     * container without adding a second resident identity checkpoint. */
    return (uint8_t)(plan &&
        plan->source_length == LISP65_C1_COMPILER_CONTAINER_BYTES &&
        plan->source_crc16 == LISP65_C1_COMPILER_CONTAINER_CRC16 &&
        plan->blob_len == LISP65_C1_COMPILER_BLOB_BYTES &&
        plan->entry_count == LISP65_C1_COMPILER_ENTRY_COUNT &&
        plan->format_version == LISP65_C1_COMPILER_FORMAT_VERSION);
}

static C1_FN obj c1_export_symbol(void) {
    return (obj)(uint16_t)(uintptr_t)lisp65_disk_lib_source.ctx;
}

static C1_FN uint8_t c1_restore(void) {
    uint16_t directory = lisp65_disk_lib_plan.dir_before;
    uint16_t watermark = lisp65_disk_lib_plan.code_base;
    /* Directory rollback cannot fail after this preflight in the synchronous
     * VM.  EXT truncation still runs first because it owns the only overlap
     * rejection; a rejection therefore leaves export and directory intact. */
    if (vm_dir_count() < directory || !vm_ext_code_truncate(watermark)) return 0;
    set_sym_function(c1_export_symbol(), NIL);
    (void)vm_dir_truncate(directory);
    lisp65_disk_lib_source.ctx = 0;
    return 1;
}

static C1_FN uint8_t c1_retire(void) {
    l65m_plan *plan = &lisp65_disk_lib_plan;
    obj export_symbol = c1_export_symbol();
    uint16_t code_now, directory_now;
    if (export_symbol == NIL) return 1; /* no transaction, or already retired */
    if (plan->source_length == 0u) {
        /* Shelf/catalog/preflight failed before any publish-capable step. */
        lisp65_disk_lib_source.ctx = 0;
        return 1;
    }
    if (!c1_plan_exact(plan)) {
        return 0;
    }
    code_now = vm_ext_code_watermark();
    directory_now = vm_dir_count();
    if (code_now == plan->code_base && directory_now == plan->dir_before) {
        /* Verified preflight, but commit stopped before reserving the blob. */
        lisp65_disk_lib_source.ctx = 0;
        return 1;
    }
    if (code_now != (uint16_t)(plan->code_base + plan->blob_len) ||
        directory_now < plan->dir_before || directory_now > plan->dir_after)
        return 0;
    return c1_restore();
}

/* Longjmp bypasses the normal Lisp retirement call.  The abort landing path
 * reloads this slice with a null context after the generic transport cleanup;
 * the checkpoint captured before loading is therefore the only state needed
 * to restore the exact pre-transaction watermarks. */
static C1_FN uint8_t c1_abort(void) {
    if (c1_export_symbol() == NIL) return VM_OK;
    return c1_restore() ? VM_OK : VM_BADOPCODE;
}

C1_FN uint8_t lisp65_c1_compiler_overlay_entry(void *opaque) {
    lisp65_buffer_overlay_context *context =
        (lisp65_buffer_overlay_context *)opaque;
    int16_t action;
    obj export_symbol;
    if (!context) return c1_abort();
    if (!context->args) return VM_BADOPCODE;
    context->result = NIL;
    if (context->argc != 2 || !IS_FIX(context->args[0])) return VM_ARITY;
    action = FIXVAL(context->args[0]);
    if (action == LISP65_C1_COMPILER_CHECKPOINT) {
        export_symbol = context->args[1];
        if (lisp65_disk_lib_source.ctx || !IS_SYMI(export_symbol) ||
            sym_function(export_symbol) != NIL)
            return VM_BADOPCODE;
        /* Invalidating the exact-plan discriminator makes every failure before
         * preflight a proven no-mutation retirement. */
        lisp65_disk_lib_plan.source_length = 0;
        lisp65_disk_lib_plan.code_base = vm_ext_code_watermark();
        lisp65_disk_lib_plan.dir_before = vm_dir_count();
        lisp65_disk_lib_source.ctx =
            (void *)(uintptr_t)(uint16_t)export_symbol;
        context->result = context->args[0];
        return VM_OK;
    }
    if (action == LISP65_C1_COMPILER_RETIRE && c1_export_symbol() == NIL) {
        context->result = context->args[1];
        return VM_OK;
    }
    if (c1_export_symbol() == NIL) return VM_BADOPCODE;
    if (action == LISP65_C1_COMPILER_VALIDATE) {
        l65m_plan *plan = &lisp65_disk_lib_plan;
        export_symbol = c1_export_symbol();
        if (!c1_plan_exact(plan) ||
            vm_ext_code_watermark() !=
                (uint16_t)(plan->code_base + plan->blob_len) ||
            vm_dir_count() != plan->dir_after ||
            sym_count() !=
                (uint16_t)(plan->symbols_before + plan->new_symbols) ||
            sym_pool_used() !=
                (uint16_t)(plan->namepool_before + plan->new_name_bytes) ||
            !IS_BCODE(sym_function(export_symbol)))
            return VM_BADOPCODE;
#ifdef LISP65_C1_LEASE_ALLOC_GUARD
        /* Ownership reuses the high bit of the allocator's existing init
         * byte. Retirement clears it in the same truncate operation that
         * restores the persistent watermark. */
        vm_ext_code_lease_begin();
#endif
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_COMPILE,
                                 LISP65_C1_PROBE_EDGE_BEGIN);
        context->result = context->args[0];
        return VM_OK;
    }
    if (action == LISP65_C1_COMPILER_RETIRE) {
        obj result = context->args[1];
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_COMPILE,
                                 LISP65_C1_PROBE_EDGE_END);
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_RETIRE,
                                 LISP65_C1_PROBE_EDGE_BEGIN);
        if (!c1_retire()) return VM_BADOPCODE;
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_RETIRE,
                                 LISP65_C1_PROBE_EDGE_END);
        context->result = result;
        return VM_OK;
    }
    return VM_TYPEERROR;
}

#endif /* LISP65_C1_COMPILER_TIER */
