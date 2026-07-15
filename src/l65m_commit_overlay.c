/* On-demand L65M commit slices. Validation and blob staging precede this unit. */
#include "l65m_commit_overlay.h"

#if defined(LISP65_VM) && defined(LISP65_STDLIB_EXT_METADATA) && \
    defined(LISP65_DISK_LIBS)

#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

enum { LIT_FIX=1, LIT_NIL, LIT_T, LIT_SYMBOL, LIT_CONS, LIT_LIST, LIT_STRING,
       LIT_ENTRY_REF };

#define INLINE static __attribute__((always_inline)) inline
#ifdef LISP65_RUNTIME_OVERLAY
#define COMMIT_SLICE(n) \
    __attribute__((section(".lisp65_rt_l65c_" #n), noinline, used))
#define COMMIT_HELP(n) \
    static __attribute__((section(".lisp65_rt_l65c_" #n), noinline))
#else
#define COMMIT_SLICE(n) __attribute__((noinline))
#define COMMIT_HELP(n) static __attribute__((noinline))
#endif

#define MD_NAME_MAX 34u

/* The pointer-free slice ABI keeps one minimal synchronous resident binding. */
static const l65m_source *commit_source_ref;
static obj commit_keep_symbol;
static obj commit_keep_checkpoint;

INLINE uint16_t commit_u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

INLINE uint16_t commit_cookie(uint8_t phase) {
    return (uint16_t)(L65M_COMMIT_OVERLAY_COOKIE_BASE ^ phase);
}

static __attribute__((noinline)) uint8_t commit_enter(l65m_commit_work *work,
                                                       uint8_t phase) {
    uint8_t transport = L65M_COMMIT_TRANSPORT_OK;
    if (!work) return 0;
    if (!commit_source_ref) transport = L65M_COMMIT_TRANSPORT_CONTEXT;
    else if (work->abi_version != L65M_COMMIT_OVERLAY_ABI_VERSION
             || work->context_size != L65M_COMMIT_CONTEXT_SIZE)
        transport = L65M_COMMIT_TRANSPORT_ABI;
    else if (work->busy) transport = L65M_COMMIT_TRANSPORT_REENTRY;
    else if (work->expected_phase != phase)
        transport = L65M_COMMIT_TRANSPORT_PHASE;
    else if (work->cookie != commit_cookie(phase))
        transport = L65M_COMMIT_TRANSPORT_COOKIE;
    if (transport != L65M_COMMIT_TRANSPORT_OK) {
        work->transport_status = transport;
        return 0;
    }
    work->busy = 1;
    return 1;
}

INLINE uint8_t commit_begin(l65m_commit_work *work, uint8_t phase) {
    if (!commit_enter(work, phase)) return 0;
    work->repeat_phase = 0;
    return 1;
}

static __attribute__((noinline)) uint8_t commit_leave(l65m_commit_work *work,
                                                       uint8_t status,
                                                       uint8_t next_phase) {
    work->busy = 0;
    if (status == L65M_OK && work->repeat_phase) return L65M_OK;
    work->commit_status = status;
    work->repeat_phase = 0;
    work->cursor = 0;
    if (status != L65M_OK) next_phase = L65M_COMMIT_PHASE_COUNT;
    work->expected_phase = next_phase;
    work->cookie = commit_cookie(next_phase);
    work->finished = (uint8_t)(next_phase == L65M_COMMIT_PHASE_COUNT);
    return status;
}

INLINE uint8_t commit_more(l65m_commit_work *work, uint16_t count) {
    if (work->cursor >= count) return 0;
    work->repeat_phase = 1;
    return 1;
}

static __attribute__((noinline)) uint8_t commit_fetch(l65m_commit_work *work,
                                                       uint16_t relative,
                                                       uint8_t *dst,
                                                       uint16_t length) {
    if (!commit_source_ref->read(commit_source_ref->ctx,
                                 (uint16_t)(work->source_metadata_off + relative),
                                 dst, length)) {
        work->commit_status = L65M_ERR_SOURCE;
        return 0;
    }
    return 1;
}

INLINE obj commit_handle_load(l65m_commit_work *work, uint16_t off) {
    uint8_t bytes[2];
    vm_code_load(lisp65_stdlib_bank, (uint16_t)(work->code_base + off),
                 sizeof bytes, bytes);
    return (obj)commit_u16(bytes);
}

INLINE void commit_handle_store(l65m_commit_work *work, uint16_t off, obj value) {
    uint8_t bytes[2];
    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)((uint16_t)value >> 8);
    vm_ext_write(bytes, sizeof bytes, lisp65_stdlib_bank,
                 (uint16_t)(work->code_base + off));
}

#define commit_fetch_01 commit_fetch
#define commit_fetch_02 commit_fetch
#define commit_fetch_03 commit_fetch
#define commit_fetch_04 commit_fetch
#define commit_fetch_06 commit_fetch

/* Shared by scalar-literal and directory-publication slices. */
static __attribute__((noinline)) void commit_name(l65m_commit_work *work,
                                                   uint16_t off) {
    char *name = sym_name_scratch;
    uint8_t remaining = MD_NAME_MAX - 1u;
    uint16_t relative = (uint16_t)(work->strings_off + off);
    do {
        if (!commit_fetch(work, relative++, (uint8_t *)name, 1))
            return;
        if (!*name++) return;
    } while (--remaining);
    *name = 0;
}

l65m_status l65m_commit_work_prepare(l65m_commit_work *work,
                                     const l65m_source *source,
                                     const l65m_plan *plan) {
    uint8_t *bytes;
    uint16_t i;
    if (!work || !source || !source->read || !plan) return L65M_ERR_ARGUMENT;
    if (commit_source_ref) return L65M_ERR_STATE;
    if (source->length != plan->source_length || plan->source_blob_off != 4u
        || plan->source_metadata_off < 4u
        || plan->source_metadata_off > plan->source_length
        || plan->blob_len != (uint16_t)(plan->source_metadata_off - 4u))
        return L65M_ERR_STATE;
    bytes = (uint8_t *)work;
    for (i = 0; i < sizeof *work; i++) bytes[i] = 0;
    work->abi_version = L65M_COMMIT_OVERLAY_ABI_VERSION;
    work->context_size = L65M_COMMIT_CONTEXT_SIZE;
    work->cookie = commit_cookie(L65M_COMMIT_PHASE_VERIFY);
    work->format_version = plan->format_version;
    work->pending_off = plan->source_crc16;
    work->source_length = plan->source_length;
    work->source_metadata_off = plan->source_metadata_off;
    work->code_base = plan->code_base;
    work->entry_count = plan->entry_count;
    work->patch_count = plan->patch_count;
    work->entries_off = plan->entries_off;
    work->index_off = plan->index_off;
    work->nodes_off = plan->nodes_off;
    work->patches_off = plan->patches_off;
    work->strings_off = plan->strings_off;
    work->dir_before = plan->dir_before;
    work->symbols_before = plan->symbols_before;
    work->namepool_before = plan->namepool_before;
    work->heap_free_before = plan->heap_free_before;
    work->arena_used_before = plan->arena_used_before;
    work->roots_before = plan->roots_before;
    commit_source_ref = source;
    return L65M_OK;
}

void l65m_commit_work_release(void) {
    if (commit_keep_symbol != NIL)
        set_sym_value(commit_keep_symbol, commit_keep_checkpoint);
    commit_source_ref = 0;
    commit_keep_symbol = NIL;
}

__attribute__((noinline)) void l65m_commit_abort_cleanup(void) {
    l65m_commit_work_release();
}

COMMIT_SLICE(00) uint8_t l65m_commit_phase_verify(void *context) {
    l65m_commit_work *work = context;
    uint8_t source_bytes[16], staged_bytes[16];
    uint8_t status = L65M_OK, count, i, bits;
    uint16_t off = 0, end, lo, hi, j, crc = 0xffffu;
    if (!commit_begin(work, L65M_COMMIT_PHASE_VERIFY)) return L65M_ERR_STATE;
    if (commit_source_ref->length != work->source_length
        || vm_ext_code_watermark() != work->code_base
        || vm_dir_count() != work->dir_before
        || sym_count() != work->symbols_before
        || sym_pool_used() != work->namepool_before
        || mem_free_cells() != work->heap_free_before
        || gc_rootsp != work->roots_before
#ifdef LISP65_STRING_ARENA
        || str_arena_used() != work->arena_used_before
#endif
       ) status = L65M_ERR_STATE;
    while (status == L65M_OK && off < commit_source_ref->length) {
        count = (uint8_t)((uint16_t)(commit_source_ref->length - off)
                          > sizeof source_bytes ? sizeof source_bytes
                                                : (uint16_t)(commit_source_ref->length - off));
        if (!commit_source_ref->read(commit_source_ref->ctx, off, source_bytes, count)) {
            status = L65M_ERR_SOURCE;
            break;
        }
        for (i = 0; i < count; i++) {
            crc ^= (uint16_t)source_bytes[i] << 8;
            bits = 8;
            while (bits--)
                crc = crc & 0x8000u ? (uint16_t)((crc << 1) ^ 0x1021u)
                                    : (uint16_t)(crc << 1);
        }
        end = (uint16_t)(off + count);
        lo = off < 4u ? 4u : off;
        hi = end > work->source_metadata_off ? work->source_metadata_off : end;
        if (lo < hi) {
            vm_code_load(lisp65_stdlib_bank,
                         (uint16_t)(work->code_base + lo - 4u),
                         (uint16_t)(hi - lo), staged_bytes);
            for (j = lo; j < hi; j++)
                if (source_bytes[j - off] != staged_bytes[j - lo]) {
                    status = L65M_ERR_STATE;
                    break;
                }
        }
        off = end;
    }
    if (status == L65M_OK && crc != work->pending_off) status = L65M_ERR_STATE;
    if (status == L65M_OK) {
        commit_keep_symbol = intern("%lit-keep");
        if (commit_keep_symbol == NIL || mem_oom) status = L65M_ERR_HEAP;
        else {
            commit_keep_checkpoint = sym_value(commit_keep_symbol);
            if (vm_ext_code_alloc(
                    (uint16_t)(work->source_metadata_off - 4u), 1)
                != work->code_base)
                status = L65M_ERR_STATE;
            else
                work->dir_before = (uint16_t)MK_BCODE(
                    (uint16_t)((work->dir_before + 7u) & ~7u));
        }
    }
    return commit_leave(work, status, work->patch_count
                        ? L65M_COMMIT_PHASE_PATCH_RECORD : L65M_COMMIT_PHASE_ENTRIES);
}

COMMIT_SLICE(01) uint8_t l65m_commit_phase_patch_record(void *context) {
    l65m_commit_work *work = context;
    uint8_t patch[4], status = L65M_OK;
    if (!commit_begin(work, L65M_COMMIT_PHASE_PATCH_RECORD))
        return L65M_ERR_STATE;
    if (work->cursor >= work->patch_count) status = L65M_ERR_STATE;
    else if (!commit_fetch_01(work,
                             (uint16_t)(work->patches_off + work->cursor * 4u),
                             patch, sizeof patch))
        status = work->commit_status;
    else {
        uint16_t off = commit_u16(patch);
        if (off > (uint16_t)(work->source_metadata_off - 4u)
            || 2u > (uint16_t)(work->source_metadata_off - 4u - off))
            status = L65M_ERR_PATCH;
        else {
            commit_handle_store(work, off, NIL);
            work->cursor++;
            commit_more(work, work->patch_count);
        }
    }
    return commit_leave(work, status, work->repeat_phase
                        ? L65M_COMMIT_PHASE_PATCH_RECORD
                        : L65M_COMMIT_PHASE_MATERIALIZE_SHAPE);
}

/* Build only the aggregate topology. Leaves remain NIL until phase 03. */
COMMIT_HELP(02) uint16_t commit_index_02(l65m_commit_work *work,
                                         uint16_t index) {
    uint8_t bytes[2];
    if (!commit_fetch(work, (uint16_t)(work->index_off + index * 2u),
                      bytes, sizeof bytes))
        return 0;
    return commit_u16(bytes);
}

COMMIT_HELP(02) obj commit_shape_02(l65m_commit_work *work, uint16_t index,
                                   uint8_t depth) {
    uint8_t node[10];
    uint16_t first, count;
    obj value, child;
    if (++depth > L65M_MAX_GRAPH_DEPTH) {
        work->commit_status = L65M_ERR_GRAPH;
        return NIL;
    }
    if (!commit_fetch_02(work, (uint16_t)(work->nodes_off + index * 10u),
                         node, sizeof node))
        return NIL;
    if (node[0] != LIT_CONS && node[0] != LIT_LIST) return NIL;
    first = commit_u16(node + 4);
    count = commit_u16(node + 6);
    if (node[0] == LIT_CONS) {
        value = commit_shape_02(work,
                                commit_index_02(work, (uint16_t)(first + 1u)),
                                depth);
        count = 1;
    } else value = NIL;
    GC_PUSH(value);
    while (count && work->commit_status == L65M_OK) {
        count--;
        child = commit_shape_02(work,
                                commit_index_02(work, (uint16_t)(first + count)),
                                depth);
        if (work->commit_status == L65M_OK) {
            value = cons(child, gc_rootstack[GC_TOP]);
            GC_SET(GC_TOP, value);
        }
    }
    GC_POPN(1);
    if (mem_oom && work->commit_status == L65M_OK)
        work->commit_status = L65M_ERR_HEAP;
    return value;
}

COMMIT_SLICE(02) uint8_t l65m_commit_phase_materialize_shape(void *context) {
    l65m_commit_work *work = context;
    uint8_t patch[4], status = L65M_OK;
    uint16_t off, node;
    obj value, link;
    if (!commit_begin(work, L65M_COMMIT_PHASE_MATERIALIZE_SHAPE))
        return L65M_ERR_STATE;
    if (work->cursor >= work->patch_count) status = L65M_ERR_STATE;
    else if (!commit_fetch_02(work,
                             (uint16_t)(work->patches_off + work->cursor * 4u),
                             patch, sizeof patch)) status = work->commit_status;
    else if (mem_oom) status = L65M_ERR_HEAP;
    else {
        off = commit_u16(patch); node = commit_u16(patch + 2);
        value = commit_shape_02(work, node, 0);
        status = work->commit_status;
        if (status == L65M_OK && IS_PTR(value)) {
            GC_PUSH(value);
            link = cons(value, sym_value(commit_keep_symbol));
            value = gc_rootstack[GC_TOP];
            if (link == NIL) status = L65M_ERR_HEAP;
            else set_sym_value(commit_keep_symbol, link);
            GC_POPN(1);
        }
        if (status == L65M_OK) {
            commit_handle_store(work, off, value);
            work->cursor++;
            commit_more(work, work->patch_count);
        }
    }
    return commit_leave(work, status, work->repeat_phase
                        ? L65M_COMMIT_PHASE_MATERIALIZE_SHAPE
                        : L65M_COMMIT_PHASE_MATERIALIZE_SCALARS);
}

/* Fill non-string scalar leaves in the already-rooted aggregate topology. */
COMMIT_HELP(03) uint16_t commit_index_03(l65m_commit_work *work,
                                         uint16_t index) {
    uint8_t bytes[2];
    if (!commit_fetch(work, (uint16_t)(work->index_off + index * 2u),
                      bytes, sizeof bytes))
        return 0;
    return commit_u16(bytes);
}

COMMIT_HELP(03) obj commit_scalars_03(l65m_commit_work *work, uint16_t index,
                                     obj value, uint8_t depth) {
    uint8_t node[10];
    uint16_t first, count, i;
    obj child, head;
    if (++depth > L65M_MAX_GRAPH_DEPTH) {
        work->commit_status = L65M_ERR_GRAPH;
        return NIL;
    }
    if (!commit_fetch_03(work, (uint16_t)(work->nodes_off + index * 10u),
                         node, sizeof node))
        return NIL;
    if (node[0] == LIT_ENTRY_REF)
        return (obj)(work->dir_before + (commit_u16(node + 4) << 1));
    switch (node[0]) {
    case LIT_FIX: return MKFIX((int16_t)commit_u16(node + 2));
    case LIT_NIL: return NIL;
    case LIT_T: return intern("t");
    case LIT_SYMBOL:
        commit_name(work, commit_u16(node + 8));
        return work->commit_status == L65M_OK ? intern(sym_name_scratch) : NIL;
    case LIT_STRING: return value;
    case LIT_CONS:
        first = commit_u16(node + 4);
        child = commit_scalars_03(work, commit_index_03(work, first), cell_a(value),
                                  depth);
        if (work->commit_status == L65M_OK) cell_set_a(value, child);
        child = commit_scalars_03(work,
                                  commit_index_03(work, (uint16_t)(first + 1u)),
                                  cell_b(value), depth);
        if (work->commit_status == L65M_OK) cell_set_b(value, child);
        return value;
    case LIT_LIST:
        head = value;
        first = commit_u16(node + 4);
        count = commit_u16(node + 6);
        for (i = 0; i < count && work->commit_status == L65M_OK; i++) {
            child = commit_scalars_03(work,
                                      commit_index_03(work, (uint16_t)(first + i)),
                                      cell_a(value), depth);
            if (work->commit_status == L65M_OK) cell_set_a(value, child);
            value = cell_b(value);
        }
        return head;
    default:
        work->commit_status = L65M_ERR_NODE;
        return NIL;
    }
}

COMMIT_SLICE(03) uint8_t l65m_commit_phase_materialize_scalars(void *context) {
    l65m_commit_work *work = context;
    uint8_t patch[4], status = L65M_OK;
    uint16_t off, node;
    obj value;
    if (!commit_begin(work, L65M_COMMIT_PHASE_MATERIALIZE_SCALARS))
        return L65M_ERR_STATE;
    if (mem_oom) status = L65M_ERR_HEAP;
    else if (work->cursor >= work->patch_count) status = L65M_ERR_STATE;
    else if (!commit_fetch_03(work,
                             (uint16_t)(work->patches_off + work->cursor * 4u),
                             patch, sizeof patch)) status = work->commit_status;
    else {
        off = commit_u16(patch); node = commit_u16(patch + 2);
        value = commit_handle_load(work, off);
        GC_PUSH(value);
        value = commit_scalars_03(work, node, value, 0);
        GC_POPN(1);
        status = work->commit_status;
        if (status == L65M_OK && mem_oom) status = L65M_ERR_HEAP;
        if (status == L65M_OK) {
            commit_handle_store(work, off, value);
            work->cursor++;
            commit_more(work, work->patch_count);
        }
    }
    return commit_leave(work, status, work->repeat_phase
                        ? L65M_COMMIT_PHASE_MATERIALIZE_SCALARS
                        : L65M_COMMIT_PHASE_MATERIALIZE_STRINGS);
}

COMMIT_HELP(04) uint16_t commit_index_04(l65m_commit_work *work,
                                         uint16_t index) {
    uint8_t bytes[2];
    if (!commit_fetch(work, (uint16_t)(work->index_off + index * 2u),
                      bytes, sizeof bytes))
        return 0;
    return commit_u16(bytes);
}

COMMIT_HELP(04) obj commit_strings_04(l65m_commit_work *work, uint16_t index,
                                     obj value, uint8_t depth) {
    uint8_t node[10], ch;
    uint16_t first, count, i, off;
    obj child, head;
    if (++depth > L65M_MAX_GRAPH_DEPTH) {
        work->commit_status = L65M_ERR_GRAPH;
        return NIL;
    }
    if (!commit_fetch_04(work, (uint16_t)(work->nodes_off + index * 10u),
                         node, sizeof node))
        return NIL;
    switch (node[0]) {
    case LIT_FIX:
    case LIT_NIL:
    case LIT_T:
    case LIT_SYMBOL:
    case LIT_ENTRY_REF:
        return value;
    case LIT_STRING:
        off = commit_u16(node + 8);
#ifdef LISP65_STRING_ARENA
        value = str_open();
        if (value == NIL) {
            work->commit_status = L65M_ERR_HEAP;
            return NIL;
        }
        for (i = 0;; i++) {
            if (!commit_fetch_04(work, (uint16_t)(work->strings_off + off + i),
                                 &ch, 1) || !ch)
                break;
            if (!str_putc(value, ch)) {
                work->commit_status = L65M_ERR_ARENA;
                break;
            }
        }
        return str_close(value);
#else
        value = NIL;
        for (i = 0;; i++) {
            if (!commit_fetch_04(work, (uint16_t)(work->strings_off + off + i),
                                 &ch, 1) || !ch)
                break;
        }
        GC_PUSH(value);
        while (i && work->commit_status == L65M_OK) {
            i--;
            commit_fetch_04(work, (uint16_t)(work->strings_off + off + i), &ch, 1);
            if (work->commit_status == L65M_OK) {
                value = cons(MKFIX(ch), gc_rootstack[GC_TOP]);
                GC_SET(GC_TOP, value);
            }
        }
        value = alloc(T_STR);
        if (value != NIL) {
            cell_set_a(value, gc_rootstack[GC_TOP]);
            cell_set_b(value, NIL);
        }
        GC_POPN(1);
        return value;
#endif
    case LIT_CONS:
        first = commit_u16(node + 4);
        child = commit_strings_04(work, commit_index_04(work, first), cell_a(value),
                                  depth);
        if (work->commit_status == L65M_OK) cell_set_a(value, child);
        child = commit_strings_04(work,
                                  commit_index_04(work, (uint16_t)(first + 1u)),
                                  cell_b(value), depth);
        if (work->commit_status == L65M_OK) cell_set_b(value, child);
        return value;
    case LIT_LIST:
        head = value;
        first = commit_u16(node + 4);
        count = commit_u16(node + 6);
        for (i = 0; i < count && work->commit_status == L65M_OK; i++) {
            child = commit_strings_04(work,
                                      commit_index_04(work, (uint16_t)(first + i)),
                                      cell_a(value), depth);
            if (work->commit_status == L65M_OK) cell_set_a(value, child);
            value = cell_b(value);
        }
        return head;
    default:
        return value;
    }
}

COMMIT_SLICE(04) uint8_t l65m_commit_phase_materialize_strings(void *context) {
    l65m_commit_work *work = context;
    uint8_t patch[4], status = L65M_OK;
    uint16_t off, node;
    obj value;
    if (!commit_begin(work, L65M_COMMIT_PHASE_MATERIALIZE_STRINGS))
        return L65M_ERR_STATE;
    if (mem_oom) status = L65M_ERR_HEAP;
    else if (work->cursor >= work->patch_count) status = L65M_ERR_STATE;
    else if (!commit_fetch_04(work,
                             (uint16_t)(work->patches_off + work->cursor * 4u),
                             patch, sizeof patch)) status = work->commit_status;
    else {
        off = commit_u16(patch); node = commit_u16(patch + 2);
        value = commit_handle_load(work, off);
        if (IS_PTR(value))
            (void)commit_strings_04(work, node, value, 0);
        status = work->commit_status;
        if (status == L65M_OK) {
            work->cursor++;
            commit_more(work, work->patch_count);
        }
    }
    return commit_leave(work, status, work->repeat_phase
                        ? L65M_COMMIT_PHASE_MATERIALIZE_STRINGS
                        : L65M_COMMIT_PHASE_PATCH_PUBLISH);
}

COMMIT_HELP(05) obj commit_root_string_05(l65m_commit_work *work,
                                         uint16_t off) {
    uint8_t ch;
    uint16_t i;
#ifdef LISP65_STRING_ARENA
    obj value = str_open();
    if (value == NIL) {
        work->commit_status = L65M_ERR_HEAP;
        return NIL;
    }
    for (i = 0;; i++) {
        if (!commit_fetch(work, (uint16_t)(work->strings_off + off + i),
                          &ch, 1) || !ch)
            break;
        if (!str_putc(value, ch)) {
            work->commit_status = L65M_ERR_ARENA;
            break;
        }
    }
    return str_close(value);
#else
    obj value = NIL;
    for (i = 0;; i++) {
        if (!commit_fetch(work, (uint16_t)(work->strings_off + off + i),
                          &ch, 1) || !ch)
            break;
    }
    GC_PUSH(value);
    while (i && work->commit_status == L65M_OK) {
        i--;
        commit_fetch(work, (uint16_t)(work->strings_off + off + i), &ch, 1);
        if (work->commit_status == L65M_OK) {
            value = cons(MKFIX(ch), gc_rootstack[GC_TOP]);
            GC_SET(GC_TOP, value);
        }
    }
    value = alloc(T_STR);
    if (value != NIL) {
        cell_set_a(value, gc_rootstack[GC_TOP]);
        cell_set_b(value, NIL);
    }
    GC_POPN(1);
    return value;
#endif
}

COMMIT_SLICE(05) uint8_t l65m_commit_phase_patch_publish(void *context) {
    l65m_commit_work *work = context;
    obj value, link;
    uint8_t patch[4], node[10], status = L65M_OK;
    uint16_t off, root;
    if (!commit_begin(work, L65M_COMMIT_PHASE_PATCH_PUBLISH))
        return L65M_ERR_STATE;
    if (mem_oom) status = L65M_ERR_HEAP;
    else if (work->cursor >= work->patch_count) status = L65M_ERR_STATE;
    else if (!commit_fetch(work,
                          (uint16_t)(work->patches_off + work->cursor * 4u),
                          patch, sizeof patch)) status = work->commit_status;
    else {
        off = commit_u16(patch); root = commit_u16(patch + 2);
        if (!commit_fetch(work, (uint16_t)(work->nodes_off + root * 10u),
                          node, sizeof node)) status = work->commit_status;
        else {
            value = commit_handle_load(work, off);
            if (node[0] == LIT_STRING) {
                value = commit_root_string_05(work, commit_u16(node + 8));
                GC_PUSH(value);
                status = work->commit_status;
                if (status == L65M_OK && mem_oom) status = L65M_ERR_HEAP;
                if (status == L65M_OK) {
                    link = cons(value, sym_value(commit_keep_symbol));
                    value = gc_rootstack[GC_TOP];
                    if (link == NIL || mem_oom) status = L65M_ERR_HEAP;
                    else {
                        set_sym_value(commit_keep_symbol, link);
                        commit_handle_store(work, off, value);
                    }
                }
                GC_POPN(1);
            }
            if (status == L65M_OK) {
                if (node[0] == LIT_FIX && !IS_FIX(value)) status = L65M_ERR_STATE;
                else if (node[0] == LIT_NIL && value != NIL) status = L65M_ERR_STATE;
                else if ((node[0] == LIT_T || node[0] == LIT_SYMBOL)
                         && !IS_SYMI(value)) status = L65M_ERR_STATE;
                else if (node[0] == LIT_ENTRY_REF && !IS_BCODE(value))
                    status = L65M_ERR_STATE;
                else if ((node[0] == LIT_CONS || node[0] == LIT_LIST)
                         && (!IS_PTR(value) || cell_type(value) != T_CONS))
                    status = L65M_ERR_STATE;
                else if (node[0] == LIT_STRING
                         && (!IS_PTR(value) || cell_type(value) != T_STR))
                    status = L65M_ERR_STATE;
            }
        }
        if (status == L65M_OK) {
            work->cursor++;
            commit_more(work, work->patch_count);
        }
    }
    return commit_leave(work, status, work->repeat_phase
                        ? L65M_COMMIT_PHASE_PATCH_PUBLISH
                        : L65M_COMMIT_PHASE_ENTRIES);
}

COMMIT_SLICE(06) uint8_t l65m_commit_phase_entries(void *context) {
    l65m_commit_work *work = context;
    uint8_t entry[8], status = L65M_OK;
    uint16_t off, len, blob_len;
    obj symbol, macro = NIL;
    int directory_index;
    if (!commit_begin(work, L65M_COMMIT_PHASE_ENTRIES))
        return L65M_ERR_STATE;
    if (mem_oom) status = L65M_ERR_HEAP;
    else if (work->cursor >= work->entry_count)
        status = L65M_ERR_STATE;
    else if (!commit_fetch_06(work,
                             (uint16_t)(work->entries_off + work->cursor * 8u),
                             entry, sizeof entry))
        status = work->commit_status;
    else {
        off = commit_u16(entry + 4);
        len = commit_u16(entry + 6);
        blob_len = (uint16_t)(work->source_metadata_off - 4u);
        if ((entry[3] & (uint8_t)~1u) || off > blob_len
            || len > (uint16_t)(blob_len - off))
            status = L65M_ERR_ENTRIES;
        else {
            if (commit_u16(entry) == 0xffffu) {
                if (work->format_version != 2u || (entry[3] & 1u))
                    status = L65M_ERR_ENTRIES;
                symbol = NIL;
            } else {
                commit_name(work, commit_u16(entry));
                if (work->commit_status != L65M_OK) status = work->commit_status;
                else {
                symbol = intern(sym_name_scratch);
                if (symbol == NIL || mem_oom) status = L65M_ERR_HEAP;
                else if (entry[3] & 1u) {
                    macro = alloc(T_MACRO);
                    if (macro == NIL || mem_oom) status = L65M_ERR_HEAP;
                }
                }
            }
            if (status == L65M_OK) {
                if (!work->cursor) vm_dir_align8();
                directory_index = vm_dir_add(symbol, lisp65_stdlib_bank,
                                             (uint16_t)(work->code_base + off), len);
                if (directory_index < 0) status = L65M_ERR_DIRECTORY;
                else if (entry[3] & 1u) {
                    cell_set_a(macro, MK_BCODE(directory_index));
                    cell_set_b(macro, NIL);
                    set_sym_function(symbol, macro);
                } else if (symbol != NIL)
                    set_sym_function(symbol, MK_BCODE(directory_index));
                if (status == L65M_OK) {
                    /* From here on Directory entries can reference the staged literals.
                     * Abort cleanup must retain their root chain. */
                    commit_keep_symbol = NIL;
                    work->cursor++;
                    commit_more(work, work->entry_count);
                }
            }
        }
    }
    return commit_leave(work, status, work->repeat_phase
                        ? L65M_COMMIT_PHASE_ENTRIES : L65M_COMMIT_PHASE_COUNT);
}

#ifdef L65M_COMMIT_OVERLAY_HOST_DIRECT
l65m_status l65m_commit_run_direct(const l65m_source *source, const l65m_plan *plan) {
    l65m_commit_work work;
    l65m_status status = l65m_commit_work_prepare(&work, source, plan);
    uint8_t phase;
    uint32_t steps = 0;
    uint32_t step_limit = 1u + (uint32_t)plan->patch_count * 5u
                            + plan->entry_count;
    if (status != L65M_OK) return status;
    while (!work.finished && status == L65M_OK) {
        if (++steps > step_limit) {
            status = L65M_ERR_STATE;
            break;
        }
        phase = work.expected_phase;
        switch (phase) {
        case L65M_COMMIT_PHASE_VERIFY:
            status = (l65m_status)l65m_commit_phase_verify(&work); break;
        case L65M_COMMIT_PHASE_PATCH_RECORD:
            status = (l65m_status)l65m_commit_phase_patch_record(&work); break;
        case L65M_COMMIT_PHASE_MATERIALIZE_SHAPE:
            status = (l65m_status)l65m_commit_phase_materialize_shape(&work); break;
        case L65M_COMMIT_PHASE_MATERIALIZE_SCALARS:
            status = (l65m_status)l65m_commit_phase_materialize_scalars(&work); break;
        case L65M_COMMIT_PHASE_MATERIALIZE_STRINGS:
            status = (l65m_status)l65m_commit_phase_materialize_strings(&work); break;
        case L65M_COMMIT_PHASE_PATCH_PUBLISH:
            status = (l65m_status)l65m_commit_phase_patch_publish(&work); break;
        case L65M_COMMIT_PHASE_ENTRIES:
            status = (l65m_status)l65m_commit_phase_entries(&work); break;
        default: status = L65M_ERR_STATE; break;
        }
    }
    if (status == L65M_OK && steps != step_limit) status = L65M_ERR_STATE;
    l65m_commit_work_release();
    return status;
}
#endif

#endif /* LISP65_VM && LISP65_STDLIB_EXT_METADATA && LISP65_DISK_LIBS */
