/* On-demand LCC installer slices. The resident facade runs transient code later. */
#include "lcc_install_overlay.h"
#include "c1_phase_probe.h"

#ifdef LISP65_LCC_INSTALL

#include <stddef.h>

#include "mem.h"
#include "symbol.h"
#include "vm.h"

/* Resident evaluator accessors; sharing avoids a second EXT-aware copy here. */
extern obj car(obj value);
extern obj cdr(obj value);

#ifdef LISP65_RUNTIME_OVERLAY
#include "vm_runtime_overlay.h"
#ifndef LISP65_LCC_INSTALL_OVERLAY_SLOT_BASE
#error "LISP65 runtime LCC install requires LISP65_LCC_INSTALL_OVERLAY_SLOT_BASE"
#endif
#define LCC_SLICE(n) \
    __attribute__((section(".lisp65_rt_lcci_" #n), noinline, used))
#define LCC_HELP(n) \
    static __attribute__((section(".lisp65_rt_lcci_" #n), noinline))
#else
#define LCC_SLICE(n) __attribute__((noinline))
#define LCC_HELP(n) static __attribute__((noinline))
#endif

#ifdef __MEGA65__
#include "vm_embed.h"
#ifndef LISP65_LCC_REGION_BANK
#define LISP65_LCC_REGION_BANK 5u
#endif
#else
extern int lcc_region_alloc(uint16_t length, uint8_t *bank, uint16_t *off);
extern void lcc_region_write(uint8_t bank, uint16_t off,
                             const uint8_t *source, uint16_t length);
#endif

#define LCC_INLINE static __attribute__((always_inline)) inline
#ifdef LISP65_RUNTIME_OVERLAY
#define LCC_RESIDENT static LISP65_RESIDENT_ISLAND_FN
#else
#define LCC_RESIDENT static __attribute__((noinline))
#endif

#define lcc_car car
#define lcc_cdr cdr

LCC_RESIDENT uint8_t lcc_cons_p(obj value) {
    return IS_PTR(value) && cell_type(value) == T_CONS;
}

LCC_INLINE uint16_t lcc_cookie(uint8_t phase) {
    return (uint16_t)(LCC_INSTALL_OVERLAY_COOKIE_BASE ^ phase);
}

LCC_RESIDENT uint8_t lcc_enter(lcc_install_work *work, uint8_t phase) {
    if (!work) return LCC_INSTALL_ERR_ARGUMENT;
    if (work->abi_version != LCC_INSTALL_OVERLAY_ABI_VERSION) {
        work->status = LCC_INSTALL_ERR_ABI;
        return work->status;
    }
    if (work->busy) {
        work->status = LCC_INSTALL_ERR_REENTRY;
        return work->status;
    }
    if (work->expected_phase != phase) {
        work->status = LCC_INSTALL_ERR_PHASE;
        return work->status;
    }
    if (work->cookie != lcc_cookie(phase)) {
        work->status = LCC_INSTALL_ERR_COOKIE;
        return work->status;
    }
    if (work->status != LCC_INSTALL_OK || work->finished) {
        work->status = LCC_INSTALL_ERR_PHASE;
        return work->status;
    }
    work->busy = 1;
    work->repeat_phase = 0;
    return LCC_INSTALL_OK;
}

LCC_INLINE uint8_t lcc_leave(lcc_install_work *work,
                             lcc_install_status status, uint8_t next_phase,
                             uint8_t finished) {
    work->busy = 0;
    work->status = (uint8_t)status;
    work->finished = finished || status != LCC_INSTALL_OK;
    work->repeat_phase = (uint8_t)!work->finished;
    work->expected_phase = next_phase;
    work->cookie = lcc_cookie(next_phase);
    return (uint8_t)status;
}

LCC_HELP(00) uint8_t lcc_fix_byte(obj value, uint8_t *out) {
    int16_t number;
    if (!IS_FIX(value)) return 0;
    number = FIXVAL(value);
    if (number < 0 || number > 255) return 0;
    *out = (uint8_t)number;
    return 1;
}

LCC_HELP(00) obj lcc_nth(obj list, uint8_t index) {
    while (index-- && lcc_cons_p(list)) list = lcc_cdr(list);
    return lcc_cons_p(list) ? lcc_car(list) : NIL;
}

LCC_INLINE uint8_t lcc_alloc(uint8_t transient, uint16_t length,
                             uint8_t *bank, uint16_t *off) {
#ifdef __MEGA65__
    uint16_t at = transient ? vm_ext_code_alloc_transient(length)
                            : vm_ext_code_alloc(length, 1);
    if (at == 0xffffu) return 0;
    *bank = LISP65_LCC_REGION_BANK;
    *off = at;
    return 1;
#else
    (void)transient;
    return (uint8_t)lcc_region_alloc(length, bank, off);
#endif
}

LCC_INLINE void lcc_write(uint8_t bank, uint16_t off,
                          const uint8_t *source, uint16_t length) {
#ifdef __MEGA65__
    vm_ext_write(source, length, bank, off);
#else
    lcc_region_write(bank, off, source, length);
#endif
}

LCC_HELP(01) uint8_t lcc_resolve_literal(lcc_install_work *work, obj literal,
                                       obj *resolved) {
    if (lcc_cons_p(literal) && lcc_car(literal) == work->marker_symbol) {
        obj rest = lcc_cdr(literal);
        obj index;
        int16_t i;
        if (!lcc_cons_p(rest)) return 0;
        index = lcc_car(rest);
        rest = lcc_cdr(rest);
        if (rest != NIL || !IS_FIX(index)) return 0;
        i = FIXVAL(index);
        if (i < 0 || i >= (int16_t)work->fn_count) return 0;
        *resolved = MK_BCODE(work->dir_map[(uint8_t)i]);
        return 1;
    }
    *resolved = literal;
    return 1;
}

LCC_SLICE(00) uint8_t lcc_install_phase_00(void *context) {
    lcc_install_work *work = (lcc_install_work *)context;
    obj function, fields, list;
    uint16_t count;
    uint8_t byte;
    lcc_install_status status = (lcc_install_status)lcc_enter(
        work, LCC_INSTALL_PHASE_SHAPE);
    if (status != LCC_INSTALL_OK) return (uint8_t)status;
    if (!work->fn_count)
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_INSTALL,
                                 LISP65_C1_PROBE_EDGE_BEGIN);

    if (!lcc_cons_p(work->current_fn))
        return lcc_leave(work, work->fn_count ? LCC_INSTALL_ERR_SHAPE
                                             : LCC_INSTALL_ERR_EMPTY,
                         LCC_INSTALL_PHASE_COUNT, 1);
    if (work->fn_count >= LCC_INSTALL_MAX_FNS)
        return lcc_leave(work, LCC_INSTALL_ERR_FNS,
                         LCC_INSTALL_PHASE_COUNT, 1);

    function = lcc_car(work->current_fn);
    fields = function;
    count = 0;
    while (lcc_cons_p(fields) && count < 6u) {
        count++;
        fields = lcc_cdr(fields);
    }
    if (count != 5u || fields != NIL)
        return lcc_leave(work, LCC_INSTALL_ERR_SHAPE,
                         LCC_INSTALL_PHASE_COUNT, 1);
    if (!lcc_fix_byte(lcc_nth(function, 0), &work->nargs) ||
        !lcc_fix_byte(lcc_nth(function, 1), &work->nlocals) ||
        !lcc_fix_byte(lcc_nth(function, 2), &work->flags))
        return lcc_leave(work, LCC_INSTALL_ERR_SHAPE,
                         LCC_INSTALL_PHASE_COUNT, 1);
    byte = CO_OPTIONAL_COUNT(work->flags);
#ifdef LISP65_DIALECT_V2
    if (!(work->flags & CO_FLAG_STRICT_ARITY) || byte > work->nargs ||
        ((work->flags & CO_FLAG_REST) && !work->nlocals))
#else
    if ((work->flags & (uint8_t)~CO_FLAG_REST) ||
        ((work->flags & CO_FLAG_REST) && !work->nlocals))
#endif
        return lcc_leave(work, LCC_INSTALL_ERR_SHAPE,
                         LCC_INSTALL_PHASE_COUNT, 1);

    work->literals = lcc_nth(function, 3);
    list = work->literals;
    count = 0;
    while (lcc_cons_p(list) && count <= LCC_INSTALL_MAX_LITS) {
        count++;
        list = lcc_cdr(list);
    }
    if (list != NIL)
        return lcc_leave(work, LCC_INSTALL_ERR_SHAPE,
                         LCC_INSTALL_PHASE_COUNT, 1);
    if (count > LCC_INSTALL_MAX_LITS)
        return lcc_leave(work, LCC_INSTALL_ERR_LITS,
                         LCC_INSTALL_PHASE_COUNT, 1);
    work->literal_count = (uint8_t)count;

    work->code = lcc_nth(function, 4);
    list = work->code;
    count = 0;
    while (lcc_cons_p(list) && count <= LCC_INSTALL_MAX_CODE) {
        if (!lcc_fix_byte(lcc_car(list), &byte))
            return lcc_leave(work, LCC_INSTALL_ERR_CODE,
                             LCC_INSTALL_PHASE_COUNT, 1);
        count++;
        list = lcc_cdr(list);
    }
    if (list != NIL)
        return lcc_leave(work, LCC_INSTALL_ERR_SHAPE,
                         LCC_INSTALL_PHASE_COUNT, 1);
    if (count > LCC_INSTALL_MAX_CODE)
        return lcc_leave(work, LCC_INSTALL_ERR_CODE,
                         LCC_INSTALL_PHASE_COUNT, 1);
    work->code_length = count;
    work->blob_length = (uint16_t)(CO_OFF_LITTAB + 2u *
                                   work->literal_count + count);
    if (work->blob_length > 255u)
        return lcc_leave(work, LCC_INSTALL_ERR_BLOB,
                         LCC_INSTALL_PHASE_COUNT, 1);

    work->is_main = (uint8_t)(lcc_cdr(work->current_fn) == NIL);
    work->transient = (uint8_t)(work->is_main &&
                                work->defname == work->true_symbol);
    return lcc_leave(work, LCC_INSTALL_OK, LCC_INSTALL_PHASE_LITERALS, 0);
}

LCC_SLICE(01) uint8_t lcc_install_phase_01(void *context) {
    lcc_install_work *work = (lcc_install_work *)context;
    uint8_t header[CO_OFF_LITTAB];
    uint8_t pair[2];
    uint8_t index = 0;
    obj list, literal, source_literal, keep;
    lcc_install_status status = (lcc_install_status)lcc_enter(
        work, LCC_INSTALL_PHASE_LITERALS);
    if (status != LCC_INSTALL_OK) return (uint8_t)status;
    if (mem_oom)
        return lcc_leave(work, LCC_INSTALL_ERR_OOM,
                         LCC_INSTALL_PHASE_COUNT, 1);

    if (!lcc_alloc(work->transient, work->blob_length,
                   &work->bank, &work->blob_off))
        return lcc_leave(work, LCC_INSTALL_ERR_REGION,
                         LCC_INSTALL_PHASE_COUNT, 1);

    header[0] = CO_MAGIC;
    header[1] = work->nargs;
    header[2] = work->nlocals;
    header[3] = work->flags;
    header[4] = (uint8_t)work->code_length;
    header[5] = (uint8_t)(work->code_length >> 8);
    header[6] = work->literal_count;
    lcc_write(work->bank, work->blob_off, header, sizeof header);

    list = work->literals;
    while (lcc_cons_p(list)) {
        source_literal = lcc_car(list);
        literal = source_literal;
        if (!lcc_resolve_literal(work, literal, &literal))
            return lcc_leave(work, LCC_INSTALL_ERR_MARKER,
                             LCC_INSTALL_PHASE_COUNT, 1);
        if (!work->transient && !(lcc_cons_p(source_literal) &&
                                  lcc_car(source_literal) == work->marker_symbol)) {
            keep = cons(literal, sym_value(work->keep_symbol));
            if (keep == NIL || mem_oom)
                return lcc_leave(work, LCC_INSTALL_ERR_OOM,
                                 LCC_INSTALL_PHASE_COUNT, 1);
            set_sym_value(work->keep_symbol, keep);
        }
        pair[0] = (uint8_t)literal;
        pair[1] = (uint8_t)((uint16_t)literal >> 8);
        lcc_write(work->bank,
                  (uint16_t)(work->blob_off + CO_OFF_LITTAB + 2u * index),
                  pair, sizeof pair);
        index++;
        list = lcc_cdr(list);
    }
    return lcc_leave(work, LCC_INSTALL_OK, LCC_INSTALL_PHASE_CODE, 0);
}

LCC_SLICE(02) uint8_t lcc_install_phase_02(void *context) {
    lcc_install_work *work = (lcc_install_work *)context;
    uint8_t chunk[32];
    uint8_t used = 0;
    uint16_t position = 0;
    int directory_index;
    obj list = work ? work->code : NIL;
    lcc_install_status status = (lcc_install_status)lcc_enter(
        work, LCC_INSTALL_PHASE_CODE);
    if (status != LCC_INSTALL_OK) return (uint8_t)status;

    while (lcc_cons_p(list)) {
        chunk[used++] = (uint8_t)FIXVAL(lcc_car(list));
        if (used == sizeof chunk) {
            lcc_write(work->bank,
                      (uint16_t)(work->blob_off + CO_OFF_LITTAB +
                                 2u * work->literal_count + position),
                      chunk, used);
            position = (uint16_t)(position + used);
            used = 0;
        }
        list = lcc_cdr(list);
    }
    if (used)
        lcc_write(work->bank,
                  (uint16_t)(work->blob_off + CO_OFF_LITTAB +
                             2u * work->literal_count + position),
                  chunk, used);

    if (work->transient) {
        work->result = NIL;
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_INSTALL,
                                 LISP65_C1_PROBE_EDGE_END);
        return lcc_leave(work, LCC_INSTALL_OK, LCC_INSTALL_PHASE_COUNT, 1);
    }

    directory_index = vm_dir_add(work->is_main ? work->defname : NIL,
                                 work->bank, work->blob_off,
                                 work->blob_length);
    if (directory_index < 0)
        return lcc_leave(work, LCC_INSTALL_ERR_DIR,
                         LCC_INSTALL_PHASE_COUNT, 1);
    work->dir_map[work->fn_count++] = (uint16_t)directory_index;
    if (work->is_main) {
        work->result = work->defname != NIL
                         ? work->defname : MK_BCODE(directory_index);
        if (work->defname != NIL)
            set_sym_function(work->defname, MK_BCODE(directory_index));
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_INSTALL,
                                 LISP65_C1_PROBE_EDGE_END);
        return lcc_leave(work, LCC_INSTALL_OK, LCC_INSTALL_PHASE_COUNT, 1);
    }

    work->current_fn = lcc_cdr(work->current_fn);
    return lcc_leave(work, LCC_INSTALL_OK, LCC_INSTALL_PHASE_SHAPE, 0);
}

#ifdef LISP65_RUNTIME_OVERLAY
static LISP65_RESIDENT_ISLAND_FN
uint8_t lcc_install_batch_repeat(void *context, uint8_t slot,
                                 uint8_t entry_result) {
    lcc_install_work *work = (lcc_install_work *)context;
    if (!work || work->abi_version != LCC_INSTALL_OVERLAY_ABI_VERSION) return 0;
    return (uint8_t)(entry_result == LCC_INSTALL_OK
                     && work->repeat_phase
                     && slot == (uint8_t)(LISP65_LCC_INSTALL_OVERLAY_SLOT_BASE
                                          + work->expected_phase));
}
#endif

static lcc_install_status lcc_dispatch_phase(lcc_install_work *work) {
#ifdef LISP65_RUNTIME_OVERLAY
    uint8_t result, slot;
    vm_runtime_overlay_status transport;
    slot = (uint8_t)(LISP65_LCC_INSTALL_OVERLAY_SLOT_BASE
                     + work->expected_phase);
    transport = vm_runtime_overlay_exec_batch(
        slot, work, &result, VM_RUNTIME_OVERLAY_BATCH_LCC,
        lcc_install_batch_repeat);
    if (transport != VM_RUNTIME_OVERLAY_OK)
        return LCC_INSTALL_ERR_TRANSPORT;
    if (work->abi_version != LCC_INSTALL_OVERLAY_ABI_VERSION
        || work->status != result)
        return LCC_INSTALL_ERR_TRANSPORT;
    return (lcc_install_status)result;
#else
    switch (work->expected_phase) {
    case LCC_INSTALL_PHASE_SHAPE: return (lcc_install_status)lcc_install_phase_00(work);
    case LCC_INSTALL_PHASE_LITERALS: return (lcc_install_status)lcc_install_phase_01(work);
    case LCC_INSTALL_PHASE_CODE: return (lcc_install_status)lcc_install_phase_02(work);
    default: return LCC_INSTALL_ERR_PHASE;
    }
#endif
}

#ifdef __MEGA65__
/* The installer is synchronous and the transport rejects nested execution.
 * Keeping its pointer-free ABI block in BSS avoids costly software-stack
 * addressing in the resident coordinator. */
static lcc_install_work lcc_resident_work;
#endif

lcc_install_status lcc_install_overlay(obj fnlist, obj defname,
                                       obj true_symbol, obj keep_symbol,
                                       obj marker_symbol,
                                       lcc_install_result *result) {
#ifdef __MEGA65__
    lcc_install_work *work = &lcc_resident_work;
#else
    lcc_install_work local_work = {0};
    lcc_install_work *work = &local_work;
#endif
    lcc_install_status status = LCC_INSTALL_OK;
    uint8_t iterations = 0;
    if (!result) return LCC_INSTALL_ERR_ARGUMENT;
    result->result = NIL;
    result->transient = 0;
    result->bank = 0;
    result->off = 0;
    result->length = 0;
    work->abi_version = LCC_INSTALL_OVERLAY_ABI_VERSION;
    work->cookie = lcc_cookie(LCC_INSTALL_PHASE_SHAPE);
    work->expected_phase = LCC_INSTALL_PHASE_SHAPE;
#ifdef __MEGA65__
    work->busy = 0;
    work->status = LCC_INSTALL_OK;
    work->finished = 0;
    work->repeat_phase = 0;
    work->fn_count = 0;
    work->result = NIL;
#endif
    work->defname = defname;
    work->true_symbol = true_symbol;
    work->keep_symbol = keep_symbol;
    work->marker_symbol = marker_symbol;
    work->current_fn = fnlist;

    while (work->expected_phase != LCC_INSTALL_PHASE_COUNT) {
        if (iterations++ >= LCC_INSTALL_OVERLAY_MAX_STEPS) {
            status = LCC_INSTALL_ERR_REPEAT;
            break;
        }
        status = lcc_dispatch_phase(work);
        if (status != LCC_INSTALL_OK) break;
    }
    if (status != LCC_INSTALL_OK) return status;

    result->result = work->result;
    result->transient = work->transient;
    result->bank = work->bank;
    result->off = work->blob_off;
    result->length = work->blob_length;
    return LCC_INSTALL_OK;
}

void lcc_install_transient_pop(const lcc_install_result *result) {
    if (!result || !result->transient) return;
#ifdef __MEGA65__
    vm_ext_code_pop_transient(result->off, result->length);
#else
    (void)result;
#endif
}

const char *lcc_install_status_message(lcc_install_status status) {
#ifdef __MEGA65__
    (void)status;
    return "lcc-install failed";
#else
    switch (status) {
    case LCC_INSTALL_ERR_ARGUMENT: return "lcc-install: argument";
    case LCC_INSTALL_ERR_ABI: return "lcc-install: abi";
    case LCC_INSTALL_ERR_COOKIE: return "lcc-install: cookie";
    case LCC_INSTALL_ERR_REENTRY: return "lcc-install: busy";
    case LCC_INSTALL_ERR_PHASE: return "lcc-install: phase";
    case LCC_INSTALL_ERR_ROOTS: return "lcc-install: roots";
    case LCC_INSTALL_ERR_EMPTY: return "lcc-install: empty fn list";
    case LCC_INSTALL_ERR_SHAPE: return "lcc-install: malformed output";
    case LCC_INSTALL_ERR_FNS: return "lcc-install: too many fns";
    case LCC_INSTALL_ERR_LITS: return "lcc-install: littab full";
    case LCC_INSTALL_ERR_CODE: return "lcc-install: invalid code";
    case LCC_INSTALL_ERR_BLOB: return "lcc-install: blob too large";
    case LCC_INSTALL_ERR_MARKER: return "lcc-install: marker";
    case LCC_INSTALL_ERR_REGION: return "lcc-install: region full";
    case LCC_INSTALL_ERR_DIR: return "lcc-install: directory full";
    case LCC_INSTALL_ERR_OOM: return "lcc-install: out of memory";
    case LCC_INSTALL_ERR_TRANSPORT: return "lcc-install: overlay transport";
    case LCC_INSTALL_ERR_REPEAT: return "lcc-install: repeat limit";
    default: return "lcc-install: error";
    }
#endif
}

#endif /* LISP65_LCC_INSTALL */
