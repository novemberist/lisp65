/* Transactional L65M validation, split into independently loadable runtime slices. */
#include "l65m_validate.h"
#if defined(LISP65_VM) && defined(LISP65_DISK_LIBS)
#include "l65m_overlay_abi.h"
#include "c1_phase_probe.h"
#include "symbol.h"
#include "vm.h"
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
#include "dialect-v2/libs/lcc-contract.h"
#endif

enum { LIT_FIX=1, LIT_NIL, LIT_T, LIT_SYMBOL, LIT_CONS, LIT_LIST, LIT_STRING,
       LIT_ENTRY_REF };
enum {
    WORK_ANY_T = 1u,
    WORK_ANY_POINTER = 2u,
    WORK_ANY_HEAP_LITERAL = 4u,
    WORK_IMPLICIT_T = 8u,
    WORK_IMPLICIT_KEEP = 16u,
    WORK_NAME_OVERFLOW = 32u,
    WORK_TRUSTED_STAGE = 128u
};

#define INLINE static __attribute__((always_inline)) inline
#ifdef LISP65_RUNTIME_OVERLAY
#define SLICE(n) __attribute__((section(".lisp65_rt_l65m_" #n), noinline, used))
#define SLICE_HELP(n) static __attribute__((section(".lisp65_rt_l65m_" #n), noinline))
#define SLICE_DATA(n) static const __attribute__((section(".lisp65_rt_l65m_" #n "_data"), used))
#else
#define SLICE(n) __attribute__((noinline))
#define SLICE_HELP(n) static __attribute__((noinline))
#define SLICE_DATA(n) static const
#endif
#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define ISLAND_COORDINATOR \
    __attribute__((section(".lisp65_resident_island"), noinline, used))
#else
#define ISLAND_COORDINATOR __attribute__((noinline))
#endif
/* Keep the phase bodies compact while the ABI stores only synchronous references. */
#define source source_ref[0]
#define limits limits_ref[0]
#define plan plan_ref[0]

INLINE uint16_t v16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}
INLINE uint32_t v32(const uint8_t *p) {
    return (uint32_t)v16(p) | ((uint32_t)v16(p + 2) << 16);
}
INLINE uint8_t source_read(l65m_overlay_work *w, uint32_t off, uint8_t *dst, uint16_t len) {
    if (!w->source.read || off > w->source.length
        || (uint32_t)len > (uint32_t)w->source.length - off || off > 0xffffu) return 0;
    return w->source.read(w->source.ctx, (uint16_t)off, dst, len);
}
INLINE uint8_t md_read(l65m_overlay_work *w, uint32_t off, uint8_t *dst, uint16_t len) {
    return w->source.read(w->source.ctx, (uint16_t)(w->plan.source_metadata_off + off), dst, len);
}
INLINE uint8_t blob_read(l65m_overlay_work *w, uint32_t off, uint8_t *dst, uint16_t len) {
    return w->source.read(w->source.ctx, (uint16_t)(w->plan.source_blob_off + off), dst, len);
}
INLINE uint8_t md_rec(l65m_overlay_work *w, uint16_t base, uint16_t idx,
                      uint16_t stride, uint8_t *dst) {
    return md_read(w, (uint16_t)(base + idx * stride), dst, stride);
}
INLINE uint16_t phase_cookie(uint8_t phase) {
    return (uint16_t)(L65M_OVERLAY_COOKIE_BASE ^ phase);
}
INLINE uint8_t phase_enter(l65m_overlay_work *w, uint8_t phase) {
    return l65m_overlay_guard(w, phase, L65M_OK, 0) == L65M_OK;
}
INLINE uint8_t phase_leave(l65m_overlay_work *w, uint8_t phase, uint8_t status) {
    return l65m_overlay_guard(w, phase, status, 1);
}

__attribute__((noinline))
uint8_t l65m_overlay_guard(void *context, uint8_t phase, uint8_t status, uint8_t leaving) {
    l65m_overlay_work *w = context;
    uint8_t next;
    if (!w) return L65M_ERR_STATE;
    if (leaving) {
        w->busy = 0;
        w->validation_status = status;
        if (status == L65M_OK && w->repeat_phase) {
            if (w->repeat_count == L65M_OVERLAY_REPEAT_LIMIT) {
                w->repeat_phase = 0;
                w->validation_status = L65M_ERR_STATE;
                w->transport_status = L65M_OV_TRANSPORT_REPEAT_LIMIT;
                w->expected_phase = L65M_OVERLAY_PHASE_COUNT;
                w->cookie = phase_cookie(L65M_OVERLAY_PHASE_COUNT);
                w->finished = 1;
                return L65M_ERR_STATE;
            }
            w->repeat_count++;
            return L65M_OK;
        }
        w->repeat_count = 0;
        next = status != L65M_OK ? L65M_OVERLAY_PHASE_COUNT : (uint8_t)(phase + 1u);
        w->expected_phase = next;
        w->cookie = phase_cookie(next);
        w->finished = (uint8_t)(next == L65M_OVERLAY_PHASE_COUNT);
        if (status == L65M_OK) w->cursor_a = w->cursor_b = 0;
        return status;
    }
    if (w->abi_version != L65M_OVERLAY_ABI_VERSION
        || w->context_size != L65M_OVERLAY_CONTEXT_SIZE) {
        w->transport_status = L65M_OV_TRANSPORT_ABI; return L65M_ERR_STATE;
    }
    if (!w->source_ref || !w->limits_ref || !w->plan_ref
        || !w->source_ref->read || !w->limits_ref->symbol_exists) {
        w->transport_status = L65M_OV_TRANSPORT_CONTEXT; return L65M_ERR_STATE;
    }
    if (w->busy) { w->transport_status = L65M_OV_TRANSPORT_REENTRY; return L65M_ERR_STATE; }
    if (w->expected_phase != phase) {
        w->transport_status = L65M_OV_TRANSPORT_PHASE; return L65M_ERR_STATE;
    }
    if (w->cookie != phase_cookie(phase)) {
        w->transport_status = L65M_OV_TRANSPORT_COOKIE; return L65M_ERR_STATE;
    }
    w->busy = 1; w->repeat_phase = 0;
    return L65M_OK;
}

INLINE uint8_t read_node(l65m_overlay_work *w, uint16_t idx, uint8_t *b) {
    return l65m_overlay_record(w, 0, idx, b);
}
INLINE uint8_t read_index(l65m_overlay_work *w, uint16_t idx, uint16_t *node) {
    uint8_t b[2];
    if (!l65m_overlay_record(w, 1, idx, b)) return 0;
    *node = v16(b); return 1;
}
INLINE uint8_t read_entry(l65m_overlay_work *w, uint16_t idx, uint8_t *b) {
    return l65m_overlay_record(w, 2, idx, b);
}
INLINE uint8_t read_patch(l65m_overlay_work *w, uint16_t idx, uint8_t *b) {
    return l65m_overlay_record(w, 3, idx, b);
}

ISLAND_COORDINATOR
uint8_t l65m_overlay_record(void *context, uint8_t kind, uint16_t idx, void *dst) {
    l65m_overlay_work *w = context;
    uint16_t base, count;
    uint8_t stride;
    if (kind == 0) {
        base = w->plan.nodes_off; count = w->plan.node_count; stride = 10;
    } else if (kind == 1) {
        base = w->plan.index_off; count = w->plan.index_count; stride = 2;
    } else if (kind == 2) {
        base = w->plan.entries_off; count = w->plan.entry_count; stride = 8;
    } else {
        base = w->plan.patches_off; count = w->plan.patch_count; stride = 4;
    }
    if (idx >= count) return 0;
    return md_rec(w, base, idx, stride, dst);
}

__attribute__((noinline))
uint8_t l65m_overlay_metadata(void *context, uint16_t off, void *dst, uint16_t len) {
    return md_read((l65m_overlay_work *)context, off, dst, len);
}
INLINE void add_cap(uint16_t *value, uint16_t add, uint16_t cap) {
    if (*value > cap || add > (uint16_t)(cap - *value)) *value = (uint16_t)(cap + 1u);
    else *value = (uint16_t)(*value + add);
}
INLINE void account_symbol(l65m_overlay_work *w, uint16_t length) {
    uint16_t before = w->name_bytes_total;
    w->symbols_total++;
    w->name_bytes_total = (uint16_t)(before + length + 1u);
    if (w->name_bytes_total < before) w->flags |= WORK_NAME_OVERFLOW;
}

void l65m_overlay_work_init(l65m_overlay_work *w, const l65m_source *src,
                            uint16_t code_base, const l65m_limits *lim,
                            l65m_plan *out) {
    uint16_t i;
    uint8_t *p;
    if (!w) return;
    p = (uint8_t *)w;
    for (i = 0; i < sizeof *w; i++) p[i] = 0;
    w->abi_version = L65M_OVERLAY_ABI_VERSION;
    w->cookie = phase_cookie(0);
    w->context_size = L65M_OVERLAY_CONTEXT_SIZE;
    w->source_ref = src; w->limits_ref = lim; w->plan_ref = out;
    if (out) {
        p = (uint8_t *)out;
        for (i = 0; i < sizeof *out; i++) p[i] = 0;
        out->code_base = code_base;
    }
}

#ifndef LISP65_RUNTIME_OVERLAY
__attribute__((noinline)) l65m_status
l65m_probe(const l65m_source *src, uint16_t *blob_len, uint16_t *metadata_len) {
    uint8_t b[4]; uint16_t bl, ml; uint32_t total;
    if (!src || !blob_len || !metadata_len || !src->read) return L65M_ERR_ARGUMENT;
    if (src->length < 4) return L65M_ERR_CONTAINER;
    if (!src->read(src->ctx, 0, b, 4)) return L65M_ERR_SOURCE;
    bl = v16(b); ml = v16(b + 2); total = 4u + (uint32_t)bl + ml;
    if (!bl || total > src->length
        || (total != src->length && src->ctx != (void *)1))
        return L65M_ERR_CONTAINER;
    if (ml < L65M_HEADER_SIZE) return L65M_ERR_HEADER;
    *blob_len = bl; *metadata_len = ml;
    return L65M_OK;
}
#endif

#define LOCAL_MD_READ(tag,w,off,dst,len) \
    l65m_overlay_metadata((w), (uint16_t)(off), (dst), (len))
#define LOCAL_STRING_READ(tag,w,off,dst,len) \
    LOCAL_MD_READ(tag, (w), (uint16_t)((w)->plan.strings_off + (off)), (dst), (len))

#define LOCAL_STRING_LENGTH(tag) \
    SLICE_HELP(tag) uint8_t phase_string_length_##tag( \
            l65m_overlay_work *w, uint16_t off, uint8_t symbol, uint16_t *length) { \
        uint8_t ch; uint16_t n = 0, pos = off; \
        if (off >= w->plan.strings_bytes) return L65M_ERR_STRINGS; \
        if (off) { \
            if (!LOCAL_STRING_READ(tag, w, off - 1u, \
                               &ch, 1)) return L65M_ERR_SOURCE; \
            if (ch) return L65M_ERR_STRINGS; \
        } \
        do { \
            if (pos >= w->plan.strings_bytes \
                || !LOCAL_STRING_READ(tag, w, pos++, \
                                  &ch, 1)) return L65M_ERR_SOURCE; \
            if (ch) n++; \
        } while (ch); \
        if (symbol && (!n || n > LISP65_SYMBOL_NAME_MAX)) return L65M_ERR_STRINGS; \
        *length = n; \
        return L65M_OK; \
    }

#define LOCAL_SYMBOL_LENGTH(tag) \
    SLICE_HELP(tag) uint8_t phase_symbol_length_##tag( \
            l65m_overlay_work *w, uint16_t off, uint16_t *length) { \
        uint8_t name[LISP65_SYMBOL_NAME_BUFFER], ch; uint16_t n, available; \
        if (off >= w->plan.strings_bytes) return L65M_ERR_STRINGS; \
        if (off) { \
            if (!LOCAL_STRING_READ(tag, w, off - 1u, \
                               &ch, 1)) return L65M_ERR_SOURCE; \
            if (ch) return L65M_ERR_STRINGS; \
        } \
        available = (uint16_t)(w->plan.strings_bytes - off); \
        if (available > sizeof name) available = sizeof name; \
        if (!LOCAL_STRING_READ(tag, w, off, \
                           name, available)) return L65M_ERR_SOURCE; \
        for (n = 0; n < available && name[n]; n++) {} \
        if (!n || n > LISP65_SYMBOL_NAME_MAX || n == available) return L65M_ERR_STRINGS; \
        *length = n; \
        return L65M_OK; \
    }

#define LOCAL_SYMBOL_ACCOUNT(tag) \
    INLINE uint8_t phase_symbol_account_##tag( \
            l65m_overlay_work *w, uint16_t off) { \
        char name[LISP65_SYMBOL_NAME_BUFFER]; \
        uint16_t remaining = (uint16_t)(w->plan.strings_bytes - off); \
        uint8_t n = 0, available = remaining > sizeof name ? sizeof name : (uint8_t)remaining; \
        if (!LOCAL_STRING_READ(tag, w, off, \
                           (uint8_t *)name, available)) return L65M_ERR_SOURCE; \
        while (name[n]) n++; \
        if (!w->limits.symbol_exists(w->limits.symbol_ctx, name)) account_symbol(w, n); \
        return L65M_OK; \
    }

#define LOCAL_KNOWN_STRING_LENGTH(tag) \
    SLICE_HELP(tag) uint8_t phase_known_string_length_##tag( \
            l65m_overlay_work *w, uint16_t off, uint16_t *length) { \
        uint8_t ch; uint16_t n = 0; \
        do { \
            if (!LOCAL_STRING_READ(tag, w, (uint16_t)(off + n), &ch, 1)) \
                return L65M_ERR_SOURCE; \
            n++; \
        } while (ch); \
        *length = (uint16_t)(n - 1u); \
        return L65M_OK; \
    }

LOCAL_SYMBOL_ACCOUNT(15)
LOCAL_SYMBOL_ACCOUNT(16)

enum {
    L65M_BYTE_BLOCK = 256u,
    L65M_RECORD_BLOCK = 240u,
    L65M_NAME_ENTRY_BLOCK = 120u,
    L65M_NAME_HASH_BITS = 4096u,
    L65M_NAME_HASH_BYTES = L65M_NAME_HASH_BITS / 8u,
    L65M_NAME_SEGMENT_BITS = 1024u,
    L65M_NAME_SEGMENT_BYTES = L65M_NAME_SEGMENT_BITS / 8u
};

#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
SLICE_DATA(03) l65m_plan c1_trusted_template = {
    .source_length = LISP65_C1_COMPILER_CONTAINER_BYTES,
    .source_crc16 = LISP65_C1_COMPILER_CONTAINER_CRC16,
    .source_blob_off = 4u,
    .source_metadata_off = 4u + LISP65_C1_COMPILER_BLOB_BYTES,
    .blob_len = LISP65_C1_COMPILER_BLOB_BYTES,
    .metadata_len = LISP65_C1_PLAN_METADATA_BYTES,
    .entry_count = LISP65_C1_COMPILER_ENTRY_COUNT,
    .index_count = LISP65_C1_PLAN_INDEX_COUNT,
    .node_count = LISP65_C1_PLAN_NODE_COUNT,
    .patch_count = LISP65_C1_PLAN_PATCH_COUNT,
    .entries_off = LISP65_C1_PLAN_ENTRIES_OFF,
    .index_off = LISP65_C1_PLAN_INDEX_OFF,
    .nodes_off = LISP65_C1_PLAN_NODES_OFF,
    .patches_off = LISP65_C1_PLAN_PATCHES_OFF,
    .strings_off = LISP65_C1_PLAN_STRINGS_OFF,
    .strings_bytes = LISP65_C1_PLAN_STRINGS_BYTES,
    .new_symbols = LISP65_C1_PLAN_SYMBOL_CEILING,
    .new_name_bytes = LISP65_C1_PLAN_NAME_BYTES_CEILING,
    .heap_cells = LISP65_C1_PLAN_HEAP_CELLS,
    .arena_bytes = LISP65_C1_PLAN_ARENA_BYTES,
    .root_slots = LISP65_C1_PLAN_ROOT_SLOTS,
    .max_graph_depth = 0x80u | LISP65_C1_PLAN_MAX_GRAPH_DEPTH,
    .format_version = LISP65_C1_COMPILER_FORMAT_VERSION
};

SLICE_HELP(00) uint8_t c1_trusted_stage_capacity(l65m_overlay_work *w) {
    uint16_t directory;
    const l65m_limits *l = w->limits_ref;
    directory = (uint16_t)((l->dir_count + 7u) & ~7u);
    if (directory > l->dir_capacity || LISP65_C1_COMPILER_ENTRY_COUNT >
            (uint16_t)(l->dir_capacity - directory)) return L65M_ERR_DIRECTORY;
    if (l->symbol_count > l->symbol_capacity || LISP65_C1_PLAN_SYMBOL_CEILING >
            (uint16_t)(l->symbol_capacity - l->symbol_count)) return L65M_ERR_SYMBOLS;
    if (l->namepool_used > l->namepool_capacity ||
        LISP65_C1_PLAN_NAME_BYTES_CEILING >
            (uint16_t)(l->namepool_capacity - l->namepool_used))
        return L65M_ERR_NAMEPOOL;
    if (l->heap_free < LISP65_C1_PLAN_HEAP_CELLS) return L65M_ERR_HEAP;
    if (l->roots_used > l->roots_capacity || LISP65_C1_PLAN_ROOT_SLOTS >
            (uint16_t)(l->roots_capacity - l->roots_used)) return L65M_ERR_ROOTS;
    if (l->string_arena && (l->arena_used > l->arena_capacity ||
        LISP65_C1_PLAN_ARENA_BYTES >
            (uint16_t)(l->arena_capacity - l->arena_used))) return L65M_ERR_ARENA;
    return L65M_OK;
}

SLICE_HELP(03) void c1_trusted_stage_plan(l65m_overlay_work *w) {
    uint16_t directory, code_base;
    l65m_plan *p = w->plan_ref;
    const l65m_limits *l = w->limits_ref;
    directory = (uint16_t)((l->dir_count + 7u) & ~7u);
    code_base = p->code_base;
    *p = c1_trusted_template;
    p->code_base = code_base;
    p->dir_before = l->dir_count;
    p->dir_after = (uint16_t)(directory + LISP65_C1_COMPILER_ENTRY_COUNT);
    p->symbols_before = l->symbol_count;
    p->namepool_before = l->namepool_used;
    p->heap_free_before = l->heap_free;
    p->arena_used_before = l->arena_used;
    p->roots_before = l->roots_used;
    /* The commit's final slice replaces the template's conservative symbol
     * ceilings with observed deltas and clears its private depth marker. */
}
#endif

SLICE(00) uint8_t l65m_overlay_phase_00(void *context) {
    l65m_overlay_work *w = context; uint8_t b[4]; uint16_t bl, ml; uint32_t end;
    uint8_t st = L65M_OK;
    if (!phase_enter(w, 0)) return L65M_ERR_STATE;
    lisp65_c1_phase_mark_for(LISP65_C1_PROBE_COMMIT,
                             LISP65_C1_PROBE_EDGE_BEGIN);
    lisp65_c1_phase_mark_for(LISP65_C1_PROBE_PREFLIGHT,
                             LISP65_C1_PROBE_EDGE_BEGIN);
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    if (((uintptr_t)w->source.ctx & 1u) &&
        IS_SYMI((obj)((uint16_t)(uintptr_t)w->source.ctx & 0xfffeu))) {
        /* Remove the private shelf tag before commit and C1 lifetime code see
         * the export symbol. The disk reader never consumes ctx itself. */
        ((l65m_source *)w->source_ref)->ctx =
            (void *)((uintptr_t)w->source.ctx & ~(uintptr_t)1u);
        if (w->source.length == LISP65_C1_COMPILER_CONTAINER_BYTES) {
            st = c1_trusted_stage_capacity(w);
            if (st == L65M_OK) {
                w->flags |= WORK_TRUSTED_STAGE;
            }
            return phase_leave(w, 0, st);
        }
    }
#endif
    if (!w->source.read || w->source.length < 4) st = L65M_ERR_CONTAINER;
    else if (!source_read(w, 0, b, 4)) st = L65M_ERR_SOURCE;
    else {
        bl = v16(b); ml = v16(b + 2); end = 4u + (uint32_t)bl + ml;
        /* Exact sources remain strict.  ctx==1 is the private synchronous
         * grant used only by the disk carrier to frame one L65M payload inside
         * a larger reusable 1581 allocation chain; artifact bytes cannot set
         * it, and truncation remains an unconditional rejection. */
        if (!bl || end > w->source.length
            || (end != w->source.length && w->source.ctx != (void *)1))
            st = L65M_ERR_CONTAINER;
        else if (ml < L65M_HEADER_SIZE) st = L65M_ERR_HEADER;
        else if (ml & 1u) st = L65M_ERR_SECTIONS;
        else if (4u + (uint32_t)bl > 0xffffu
                 || (uint32_t)w->plan.code_base + bl > 0x10000u) st = L65M_ERR_REGION;
        else {
            w->plan.source_length = (uint16_t)end;
            w->plan.source_blob_off = 4; w->plan.source_metadata_off = (uint16_t)(4u + bl);
            w->plan.blob_len = bl; w->plan.metadata_len = ml;
        }
    }
    return phase_leave(w, 0, st);
}

SLICE(01) uint8_t l65m_overlay_phase_01(void *context) {
    l65m_overlay_work *w = context; uint8_t h[38]; uint8_t st = L65M_OK;
    if (!phase_enter(w, 1)) return L65M_ERR_STATE;
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    if (w->flags & WORK_TRUSTED_STAGE) goto phase_01_done;
#endif
    if (!md_read(w, 0, h, 38)) st = L65M_ERR_SOURCE;
    else if (h[0]!='L'||h[1]!='6'||h[2]!='5'||h[3]!='M'||h[5]!=38
#ifdef LISP65_DIALECT_V2
             ||(h[4]!=1&&h[4]!=2)
#else
             ||h[4]!=1
#endif
             ||v16(h+6)||v32(h+8)||v16(h+12)!=w->plan.blob_len
             ||v16(h+14)!=w->plan.metadata_len||v16(h+36)) st = L65M_ERR_HEADER;
    else {
        w->plan.format_version=h[4];
        w->plan.entry_count=v16(h+16); w->plan.index_count=v16(h+18);
        w->plan.node_count=v16(h+20); w->plan.patch_count=v16(h+22);
        w->plan.entries_off=v16(h+24); w->plan.index_off=v16(h+26);
        w->plan.nodes_off=v16(h+28); w->plan.patches_off=v16(h+30);
        w->plan.strings_off=v16(h+32); w->plan.strings_bytes=v16(h+34);
        if (!w->plan.entry_count) st=L65M_ERR_ENTRIES;
    }
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
phase_01_done:
#endif
    return phase_leave(w, 1, st);
}

SLICE(02) uint8_t l65m_overlay_phase_02(void *context) {
    l65m_overlay_work *w=context; uint32_t n=38,end; uint8_t pad,st=L65M_OK;
    if (!phase_enter(w,2)) return L65M_ERR_STATE;
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    if (w->flags & WORK_TRUSTED_STAGE) goto phase_02_done;
#endif
#define SEC(field,count,bytes) do { \
    if ((field)!=n || ((field)&1u)) { st=L65M_ERR_SECTIONS; break; } \
    end=(uint32_t)(field)+(bytes); if(end>w->plan.metadata_len){st=L65M_ERR_SECTIONS;break;} \
    n=(end+1u)&~1u; \
} while(0)
    SEC(w->plan.entries_off,w->plan.entry_count,(uint32_t)w->plan.entry_count<<3);
    if(st==L65M_OK) SEC(w->plan.index_off,w->plan.index_count,(uint32_t)w->plan.index_count<<1);
    if(st==L65M_OK) SEC(w->plan.nodes_off,w->plan.node_count,
                       ((uint32_t)w->plan.node_count<<3)+((uint32_t)w->plan.node_count<<1));
    if(st==L65M_OK) SEC(w->plan.patches_off,w->plan.patch_count,(uint32_t)w->plan.patch_count<<2);
#undef SEC
    if(st==L65M_OK){
        end=(uint32_t)w->plan.strings_off+w->plan.strings_bytes;
        if(w->plan.strings_off!=n||(w->plan.strings_off&1u)
           ||((end+1u)&~1u)!=w->plan.metadata_len) st=L65M_ERR_SECTIONS;
        else if((end&1u)&&(!md_read(w,end,&pad,1)||pad)) st=L65M_ERR_SECTIONS;
    }
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
phase_02_done:
#endif
    return phase_leave(w,2,st);
}

SLICE(03) uint8_t l65m_overlay_phase_03(void *context) {
    l65m_overlay_work*w=context;uint8_t block[L65M_BYTE_BLOCK],ch,need=0,lo=0x80,hi=0xbf;
    uint8_t st=L65M_OK;uint16_t pos=0,n,i;
    if(!phase_enter(w,3)) return L65M_ERR_STATE;
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    if (w->flags & WORK_TRUSTED_STAGE) {
        c1_trusted_stage_plan(w);
        st = phase_leave(w, 3, L65M_OK);
        w->expected_phase = L65M_OVERLAY_PHASE_COUNT;
        w->cookie = phase_cookie(L65M_OVERLAY_PHASE_COUNT);
        w->finished = 1;
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_PREFLIGHT,
                                 LISP65_C1_PROBE_EDGE_END);
        return st;
    }
#endif
    while(pos<w->plan.strings_bytes&&st==L65M_OK){
        n=(uint16_t)(w->plan.strings_bytes-pos);
        if(n>L65M_BYTE_BLOCK)n=L65M_BYTE_BLOCK;
        if(!l65m_overlay_metadata(w,(uint16_t)(w->plan.strings_off+pos),block,n)){
            st=L65M_ERR_SOURCE;break;
        }
        for(i=0;i<n&&st==L65M_OK;i++){
            ch=block[i];pos++;
            if(pos==w->plan.strings_bytes&&ch){st=L65M_ERR_STRINGS;break;}
            if(ch){
                if(need){if(ch<lo||ch>hi){st=L65M_ERR_STRINGS;break;}need--;lo=0x80;hi=0xbf;}
                else if(ch>=0x80){
                    if(ch>=0xc2&&ch<=0xdf)need=1;
                    else if(ch==0xe0){need=2;lo=0xa0;}
                    else if(ch>=0xe1&&ch<=0xec)need=2;
                    else if(ch==0xed){need=2;hi=0x9f;}
                    else if(ch>=0xee&&ch<=0xef)need=2;
                    else if(ch==0xf0){need=3;lo=0x90;}
                    else if(ch>=0xf1&&ch<=0xf3)need=3;
                    else if(ch==0xf4){need=3;hi=0x8f;}
                    else st=L65M_ERR_STRINGS;
                }
            }else if(need)st=L65M_ERR_STRINGS;
            else{lo=0x80;hi=0xbf;}
        }
    }
    return phase_leave(w,3,st);
}

SLICE(04) uint8_t l65m_overlay_phase_04(void *context) {
    l65m_overlay_work*w=context;uint8_t b[8],chunk[8],ch,k,n,j,st=L65M_OK;
    uint16_t i,name,off,len,available;
    if(!phase_enter(w,4))return L65M_ERR_STATE;
    i=w->cursor_a;
    if(i<w->plan.entry_count)do{
        if(!w->byte_cursor){
            if(!read_entry(w,i,b)){st=L65M_ERR_SOURCE;break;}
            off=v16(b+4);len=v16(b+6);
            if(b[2]||(b[3]&~1u)||off!=w->entry_end)st=L65M_ERR_ENTRIES;
            else if(len<7u||off>w->plan.blob_len
                    ||len>(uint16_t)(w->plan.blob_len-off))st=L65M_ERR_ENTRIES;
            else if(len>255u)st=L65M_ERR_CODE;
            else{
                w->entry_end=(uint16_t)(off+len);if(b[3]&1u)w->macro_cells++;
                name=v16(b);
                if(name==0xffffu){
                    if(w->plan.format_version!=2u||(b[3]&1u))st=L65M_ERR_ENTRIES;
                    else{w->cursor_a++;w->byte_cursor=0;}
                }
                else if(name>=w->plan.strings_bytes)st=L65M_ERR_STRINGS;
                else if(name&&!LOCAL_STRING_READ(04,w,(uint16_t)(name-1u),&ch,1))
                    st=L65M_ERR_SOURCE;
                else if(name&&ch)st=L65M_ERR_STRINGS;
                else{w->cursor_b=name;w->byte_cursor=1;}
            }
        }else{
            k=(uint8_t)(w->byte_cursor-1u);off=w->cursor_b;
            if(k>LISP65_SYMBOL_NAME_MAX)st=L65M_ERR_STRINGS;
            else{
                available=(uint16_t)(w->plan.strings_bytes-off-k);
                n=(uint8_t)(LISP65_SYMBOL_NAME_BUFFER-k);if(n>sizeof chunk)n=sizeof chunk;
                if(available<n)n=(uint8_t)available;
                if(!n||!LOCAL_STRING_READ(04,w,(uint16_t)(off+k),chunk,n))st=L65M_ERR_SOURCE;
                else{for(j=0;j<n&&chunk[j];j++){}
                    if(j<n){if(!k&&!j)st=L65M_ERR_STRINGS;
                        else{w->cursor_a++;w->byte_cursor=0;}}
                    else w->byte_cursor=(uint8_t)(w->byte_cursor+n);}
            }
        }
        if(st==L65M_OK&&w->cursor_a<w->plan.entry_count)w->repeat_phase=1;
    }while(0);
    return phase_leave(w,4,st);
}

SLICE_HELP(05) uint8_t phase_name_05(l65m_overlay_work*w,uint16_t off,
                                     uint8_t*name,uint16_t*hash){
    uint16_t available,n,h=0x9e37u;
    available=(uint16_t)(w->plan.strings_bytes-off);
    if(available>LISP65_SYMBOL_NAME_BUFFER)available=LISP65_SYMBOL_NAME_BUFFER;
    if(!LOCAL_STRING_READ(05,w,off,name,available))return L65M_ERR_SOURCE;
    for(n=0;n<available&&name[n];n++){
        h=(uint16_t)((h<<2)|(h>>14));h^=name[n];
    }
    *hash=h;return L65M_OK;
}

SLICE(05) uint8_t l65m_overlay_phase_05(void *context) {
    l65m_overlay_work*w=context;
    uint8_t bits[L65M_NAME_HASH_BYTES],name[LISP65_SYMBOL_NAME_BUFFER],
        other[LISP65_SYMBOL_NAME_BUFFER];
    uint8_t entries[L65M_NAME_ENTRY_BLOCK],p[8],n,r,mask,st=L65M_OK;
    uint16_t base,i,j,m,off,poff,hash,bucket;
    if(!phase_enter(w,5))return L65M_ERR_STATE;
    __builtin_memset(bits,0,sizeof bits);
    for(base=0;base<w->plan.entry_count&&st==L65M_OK;base=(uint16_t)(base+n)){
        i=(uint16_t)(w->plan.entry_count-base);
        if(i>L65M_NAME_ENTRY_BLOCK/8u)i=L65M_NAME_ENTRY_BLOCK/8u;
        n=(uint8_t)i;
        if(!l65m_overlay_metadata(w,(uint16_t)(w->plan.entries_off+base*8u),
                                  entries,(uint16_t)n*8u)){st=L65M_ERR_SOURCE;break;}
        for(r=0;r<n&&st==L65M_OK;r++){
            i=(uint16_t)(base+r);off=v16(entries+(uint16_t)r*8u);
            if(off==0xffffu)continue;
            st=phase_name_05(w,off,name,&hash);if(st!=L65M_OK)break;
            bucket=(uint16_t)((hash&(L65M_NAME_HASH_BITS-1u))>>3);
            mask=(uint8_t)(1u<<(hash&7u));
            if(bits[bucket]&mask)for(j=0;j<i&&st==L65M_OK;j++){
                if(!read_entry(w,j,p)){st=L65M_ERR_SOURCE;break;}poff=v16(p);
                if(poff==0xffffu)continue;
                st=phase_name_05(w,poff,other,&poff);
                if(st==L65M_OK){
                    for(m=0;m<LISP65_SYMBOL_NAME_BUFFER&&name[m]==other[m]&&name[m];m++){}
                    if(m==LISP65_SYMBOL_NAME_BUFFER)st=L65M_ERR_STRINGS;
                    else if(name[m]==other[m])st=L65M_ERR_ENTRIES;
                }
            }
            bits[bucket]|=mask;
        }
    }
    return phase_leave(w,5,st);
}

SLICE(06) uint8_t l65m_overlay_phase_06(void *context) {
    l65m_overlay_work*w=context;uint8_t e[8],h[7],st=L65M_OK,cf;uint16_t i,off,len,nl,cl,total=0;
#ifdef LISP65_DIALECT_V2
    uint8_t oc;
#endif
    if(!phase_enter(w,6))return L65M_ERR_STATE;
    for(i=0;i<w->plan.entry_count&&st==L65M_OK;i++){
        if(!read_entry(w,i,e)){st=L65M_ERR_SOURCE;break;}
        off=v16(e+4);len=v16(e+6);
        if(!blob_read(w,off,h,7)){st=L65M_ERR_SOURCE;break;}
        cf=h[3];
#ifdef LISP65_DIALECT_V2
        oc=CO_OPTIONAL_COUNT(cf);
        if(h[0]!=CO_MAGIC||!(cf&CO_FLAG_STRICT_ARITY)||oc>h[1]||
           ((cf&CO_FLAG_REST)&&!h[2]))st=L65M_ERR_CODE;
#else
        if(h[0]!=CO_MAGIC||(cf&~CO_FLAG_REST)||((cf&CO_FLAG_REST)&&!h[2]))st=L65M_ERR_CODE;
#endif
        else{cl=v16(h+4);nl=h[6];if(7u+2u*(uint16_t)nl+cl!=len)st=L65M_ERR_CODE;
             else total=(uint16_t)(total+nl);}
    }
    if(st==L65M_OK&&w->entry_end!=w->plan.blob_len)st=L65M_ERR_ENTRIES;
    if(st==L65M_OK&&w->plan.patch_count!=total)st=L65M_ERR_PATCH;
    if(st==L65M_OK)w->entry_end=0; /* reused as patch cursor after entry coverage is sealed */
    return phase_leave(w,6,st);
}

SLICE(07) uint8_t l65m_overlay_phase_07(void *context) {
    l65m_overlay_work*w=context;uint8_t block[L65M_BYTE_BLOCK],*p,*end,st=L65M_OK;
    uint16_t pos=w->plan.index_off,limit=w->plan.nodes_off,n;
    if(!phase_enter(w,7))return L65M_ERR_STATE;
    while(pos<limit&&st==L65M_OK){
        n=(uint16_t)(limit-pos);if(n>L65M_BYTE_BLOCK)n=L65M_BYTE_BLOCK;
        if(!l65m_overlay_metadata(w,pos,block,n)){st=L65M_ERR_SOURCE;break;}
        p=block;end=block+n;
        while(p<end){
            if(v16(p)>=w->plan.node_count){st=L65M_ERR_INDEX;break;}
            p+=2;
        }
        pos=(uint16_t)(pos+n);
    }
    return phase_leave(w,7,st);
}

SLICE(08) uint8_t l65m_overlay_phase_08(void *context) {
    l65m_overlay_work*w=context;uint8_t records[L65M_RECORD_BLOCK],*b,*end,k,st=L65M_OK;
    uint8_t target[8];
    uint16_t pos=w->plan.nodes_off,limit=w->plan.patches_off,n,val,first,count,no;
    if(!phase_enter(w,8))return L65M_ERR_STATE;
    while(pos<limit&&st==L65M_OK){
        n=(uint16_t)(limit-pos);if(n>L65M_RECORD_BLOCK)n=L65M_RECORD_BLOCK;
        if(!l65m_overlay_metadata(w,pos,records,n)){st=L65M_ERR_SOURCE;break;}
        b=records;end=records+n;
        while(b<end&&st==L65M_OK){
            k=b[0];val=v16(b+2);first=v16(b+4);count=v16(b+6);no=v16(b+8);
            if(k<1||k>LIT_ENTRY_REF||b[1])st=L65M_ERR_NODE;
            else if(k==LIT_FIX){if((int16_t)val< -16384||(int16_t)val>16383||first||count||no!=0xffffu)st=L65M_ERR_NODE;}
            else if(k==LIT_NIL||k==LIT_T){if(val||first||count||no!=0xffffu)st=L65M_ERR_NODE;else if(k==LIT_T)w->flags|=WORK_ANY_T;}
            else if(k==LIT_SYMBOL||k==LIT_STRING){
                if(val||first||count)st=L65M_ERR_NODE;
                else if(no>=w->plan.strings_bytes)st=L65M_ERR_STRINGS;
            }else if(k==LIT_CONS){if(val||count!=2u||no!=0xffffu||(uint32_t)first+2u>w->plan.index_count)st=L65M_ERR_NODE;}
            else if(k==LIT_LIST){if(val||no!=0xffffu||(uint32_t)first+count>w->plan.index_count)st=L65M_ERR_NODE;}
            else if(w->plan.format_version!=2u||val||count||no!=0xffffu
                    ||first>=w->plan.entry_count)st=L65M_ERR_NODE;
            else if(!read_entry(w,first,target))st=L65M_ERR_SOURCE;
            else if(target[3]&1u)st=L65M_ERR_NODE;
            b+=10;
        }
        pos=(uint16_t)(pos+n);
    }
    return phase_leave(w,8,st);
}

SLICE(09) uint8_t l65m_overlay_phase_09(void *context) {
    l65m_overlay_work*w=context;uint8_t b[10],block[L65M_BYTE_BLOCK],k,skip,st=L65M_OK;
    uint16_t i,len,off,pos,n;
    if(!phase_enter(w,9))return L65M_ERR_STATE;
    i=w->cursor_a;
    if(i<w->plan.node_count)do{
        if(!read_node(w,i,b)){st=L65M_ERR_SOURCE;break;}k=b[0];
        if(k==LIT_SYMBOL||k==LIT_STRING){
            off=v16(b+8);
            skip=(uint8_t)(!w->byte_cursor&&off);
            pos=w->byte_cursor?w->cursor_b:(skip?(uint16_t)(off-1u):off);
            n=(uint16_t)(w->plan.strings_bytes-pos);
            if(n>L65M_BYTE_BLOCK)n=L65M_BYTE_BLOCK;
            if(!n){st=L65M_ERR_STRINGS;break;}
            if(!LOCAL_STRING_READ(09,w,pos,block,n)){st=L65M_ERR_SOURCE;break;}
            if(skip&&block[0]){st=L65M_ERR_STRINGS;break;}
            for(len=skip;len<n&&block[len];len++){}
            if(len==n){w->cursor_b=(uint16_t)(pos+n);w->byte_cursor=1;
                w->repeat_phase=1;break;}
            if(pos<off)len--;else len=(uint16_t)(pos-off+len);
            w->byte_cursor=0;
            if(k==LIT_SYMBOL&&(!len||len>LISP65_SYMBOL_NAME_MAX))st=L65M_ERR_STRINGS;
            if(k==LIT_STRING&&w->limits.string_arena&&len>0x3fffu)st=L65M_ERR_NODE;
        }
        if(st==L65M_OK){w->cursor_a++;if(w->cursor_a<w->plan.node_count)w->repeat_phase=1;}
    }while(0);
    return phase_leave(w,9,st);
}

SLICE(10) uint8_t l65m_overlay_phase_10(void *context) {
    l65m_overlay_work*w=context;uint8_t b[10],sp,st=L65M_OK;uint16_t root,child,i,count,first;
    uint16_t frame_node[L65M_MAX_GRAPH_DEPTH],frame_next[L65M_MAX_GRAPH_DEPTH];
    if(!phase_enter(w,10))return L65M_ERR_STATE;
    root=w->cursor_a;
    if(root<w->plan.node_count){
        sp=1;frame_node[0]=root;frame_next[0]=0xffffu;
        if(!w->plan.max_graph_depth)w->plan.max_graph_depth=1;
        while(sp&&st==L65M_OK){
            i=(uint16_t)(sp-1u);
            if(!read_node(w,frame_node[i],b)){
                st=L65M_ERR_SOURCE;break;
            }
            if(b[0]!=LIT_CONS&&b[0]!=LIT_LIST){sp--;continue;}
            first=v16(b+4);count=v16(b+6);
            if(frame_next[i]==0xffffu)frame_next[i]=0;
            if(frame_next[i]>=count){sp--;continue;}
            if(!read_index(w,(uint16_t)(first+frame_next[i]++),&child)){
                st=L65M_ERR_SOURCE;break;
            }
            for(i=0;i<sp;i++)if(frame_node[i]==child){st=L65M_ERR_GRAPH;break;}
            if(st!=L65M_OK)break;
            if(sp>=L65M_MAX_GRAPH_DEPTH){st=L65M_ERR_GRAPH;break;}
            frame_node[sp]=child;frame_next[sp]=0xffffu;sp++;
            if(sp>w->plan.max_graph_depth)w->plan.max_graph_depth=sp;
        }
        w->cursor_a++;if(st==L65M_OK&&w->cursor_a<w->plan.node_count)w->repeat_phase=1;
    }
    return phase_leave(w,10,st);
}

SLICE(11) uint8_t l65m_overlay_phase_11(void *context) {
    l65m_overlay_work*w=context;uint8_t e[8],patches[L65M_RECORD_BLOCK],*p;
    uint8_t nl,patch_pos=0,patch_records=0,st=L65M_OK;uint16_t i,k,off,n;
    if(!phase_enter(w,11))return L65M_ERR_STATE;
    for(i=0;i<w->plan.entry_count&&st==L65M_OK;i++){
        if(!read_entry(w,i,e)){st=L65M_ERR_SOURCE;break;}off=v16(e+4);
        if(!blob_read(w,(uint16_t)(off+6u),&nl,1)){st=L65M_ERR_SOURCE;break;}
        for(k=0;k<nl;k++){
            if(patch_pos==patch_records){
                if(w->entry_end>=w->plan.patch_count){st=L65M_ERR_SOURCE;break;}
                n=(uint16_t)(w->plan.patch_count-w->entry_end);
                if(n>L65M_RECORD_BLOCK/4u)n=L65M_RECORD_BLOCK/4u;
                if(!l65m_overlay_metadata(w,
                        (uint16_t)(w->plan.patches_off+w->entry_end*4u),patches,
                        (uint16_t)(n*4u))){st=L65M_ERR_SOURCE;break;}
                patch_pos=0;patch_records=(uint8_t)n;
            }
            p=patches+(uint16_t)patch_pos*4u;patch_pos++;
            if(v16(p)!=(uint16_t)(off+7u+2u*k)
                ||v16(p+2)>=w->plan.node_count){st=L65M_ERR_PATCH;break;}
            w->entry_end++;
        }
    }
    return phase_leave(w,11,st);
}

SLICE(12) uint8_t l65m_overlay_phase_12(void *context) {
    l65m_overlay_work*w=context;uint8_t p[4],b[10],st=L65M_OK;uint16_t q;
    uint16_t hcap=w->limits.heap_free;
    if(!phase_enter(w,12))return L65M_ERR_STATE;
    if(!w->cursor_a){
        w->heap_total=0;w->arena_total=0;
        w->arena_available=w->limits.arena_capacity>=w->limits.arena_used
                           ?(uint16_t)(w->limits.arena_capacity-w->limits.arena_used):0;
        if(w->limits.string_arena){
            w->cost_total_ref=&w->arena_total;w->cost_cap=w->arena_available;w->cost_extra=0;
        }else{
            w->cost_total_ref=&w->heap_total;w->cost_cap=w->limits.heap_free;w->cost_extra=1;
        }
        add_cap(&w->heap_total,w->macro_cells,hcap);
    }
    q=w->cursor_a;
    if(q<w->plan.patch_count)do{
        if(!read_patch(w,q,p)){st=L65M_ERR_SOURCE;break;}
        if(!read_node(w,v16(p+2),b)){st=L65M_ERR_SOURCE;break;}
        if(b[0]==LIT_CONS||b[0]==LIT_LIST||b[0]==LIT_STRING){
            add_cap(&w->heap_total,1,hcap);w->flags|=WORK_ANY_HEAP_LITERAL|WORK_ANY_POINTER;
        }
        w->cursor_a++;if(st==L65M_OK&&w->cursor_a<w->plan.patch_count)w->repeat_phase=1;
    }while(0);
    return phase_leave(w,12,st);
}

SLICE_HELP(13) uint8_t topology_cost(l65m_overlay_work*w,uint16_t idx,uint16_t cap){
    uint8_t b[10],st;uint16_t i,child,count,first;
    if(!read_node(w,idx,b))return L65M_ERR_SOURCE;
    if(b[0]==LIT_STRING){
        if(w->limits.string_arena)add_cap(&w->heap_total,1,cap);
        return L65M_OK;
    }
    if(b[0]!=LIT_CONS&&b[0]!=LIT_LIST)return L65M_OK;
    first=v16(b+4);count=v16(b+6);add_cap(&w->heap_total,b[0]==LIT_CONS?1u:count,cap);w->flags|=WORK_ANY_HEAP_LITERAL;
    for(i=0;i<count;i++){
        if(!read_index(w,(uint16_t)(first+i),&child))return L65M_ERR_SOURCE;
        st=topology_cost(w,child,cap);if(st!=L65M_OK)return st;
    }
    return L65M_OK;
}

SLICE(13) uint8_t l65m_overlay_phase_13(void *context) {
    l65m_overlay_work*w=context;uint8_t patches[120],*p,st=L65M_OK;
    uint16_t q=w->cursor_a,n,i;
    if(!phase_enter(w,13))return L65M_ERR_STATE;
    if(q<w->plan.patch_count)do{
        n=(uint16_t)(w->plan.patch_count-q);
        if(n>sizeof patches/4u)n=sizeof patches/4u;
        if(!l65m_overlay_metadata(w,(uint16_t)(w->plan.patches_off+q*4u),
                                  patches,(uint16_t)(n*4u))){
            st=L65M_ERR_SOURCE;break;
        }
        for(i=0;i<n&&st==L65M_OK;i++){
            p=patches+i*4u;
            st=topology_cost(w,v16(p+2),w->limits.heap_free);
            w->cursor_a++;
        }
        if(st==L65M_OK&&w->cursor_a<w->plan.patch_count)w->repeat_phase=1;
    }while(0);
    return phase_leave(w,13,st);
}

SLICE_HELP(14) uint8_t string_cost(l65m_overlay_work*w,uint16_t idx){
    uint8_t b[10],ch,st;uint16_t i,child,len,count,first,off;
    if(!read_node(w,idx,b))return L65M_ERR_SOURCE;
    if(b[0]==LIT_STRING){
        off=v16(b+8);len=0;
        do{
            if(!l65m_overlay_metadata(w,(uint16_t)(w->plan.strings_off+off+len),&ch,1))
                return L65M_ERR_SOURCE;
            if(ch)len++;
        }while(ch);
        add_cap(w->cost_total_ref,(uint16_t)(len+w->cost_extra),w->cost_cap);
        return L65M_OK;
    }
    if(b[0]!=LIT_CONS&&b[0]!=LIT_LIST)return L65M_OK;
    first=v16(b+4);count=v16(b+6);
    for(i=0;i<count;i++){
        if(!read_index(w,(uint16_t)(first+i),&child))return L65M_ERR_SOURCE;
        st=string_cost(w,child);if(st!=L65M_OK)return st;
    }
    return L65M_OK;
}

SLICE(14) uint8_t l65m_overlay_phase_14(void *context) {
    l65m_overlay_work*w=context;uint8_t p[4],st=L65M_OK;uint16_t q=w->cursor_a;
    if(!phase_enter(w,14))return L65M_ERR_STATE;
    if(q<w->plan.patch_count)do{
        if(!read_patch(w,q,p)){st=L65M_ERR_SOURCE;break;}
        st=string_cost(w,v16(p+2));
        w->cursor_a++;if(st==L65M_OK&&w->cursor_a<w->plan.patch_count)w->repeat_phase=1;
    }while(0);
    return phase_leave(w,14,st);
}

SLICE(15) uint8_t l65m_overlay_phase_15(void *context) {
    l65m_overlay_work*w=context;uint8_t e[8],st=L65M_OK;uint16_t i;
    if(!phase_enter(w,15))return L65M_ERR_STATE;
    for(i=0;i<w->plan.entry_count&&st==L65M_OK;i++)
        if(!read_entry(w,i,e))st=L65M_ERR_SOURCE;
        else if(v16(e)!=0xffffu)st=phase_symbol_account_15(w,v16(e));
    return phase_leave(w,15,st);
}

SLICE_HELP(16) uint8_t phase_seen_16(uint8_t*bits,uint16_t off,uint8_t seg){
    uint8_t index,mask;
    if((uint8_t)(off>>10)!=seg)return 1;
    index=(uint8_t)((off>>3)&0x7fu);mask=(uint8_t)(1u<<(off&7u));
    if(bits[index]&mask)return 1;
    bits[index]|=mask;return 0;
}

SLICE_HELP(16) uint8_t phase_records_16(l65m_overlay_work*w,uint8_t*bits,
                                        uint8_t seg,uint8_t nodes){
    uint8_t records[120],*p,*end,stride=nodes?10u:8u,st=L65M_OK;
    uint16_t pos=nodes?w->plan.nodes_off:w->plan.entries_off;
    uint16_t limit=nodes?w->plan.patches_off:w->plan.index_off,n,off;
    while(pos<limit&&st==L65M_OK){
        n=(uint16_t)(limit-pos);if(n>sizeof records)n=sizeof records;
        if(!l65m_overlay_metadata(w,pos,records,n))return L65M_ERR_SOURCE;
        p=records;end=records+n;
        while(p<end&&st==L65M_OK){
            if(!nodes||p[0]==LIT_SYMBOL){off=v16(p+(nodes?8u:0u));
                if(off==0xffffu){p+=stride;continue;}
                if(!phase_seen_16(bits,off,seg)&&nodes)st=phase_symbol_account_16(w,off);}
            p+=stride;
        }
        pos=(uint16_t)(pos+n);
    }
    return st;
}

SLICE(16) uint8_t l65m_overlay_phase_16(void *context) {
    l65m_overlay_work*w=context;uint8_t bits[L65M_NAME_SEGMENT_BYTES];
    uint8_t st=L65M_OK,seg;
    if(!phase_enter(w,16))return L65M_ERR_STATE;
    seg=(uint8_t)w->cursor_a;
    do{
        __builtin_memset(bits,0,sizeof bits);
        st=phase_records_16(w,bits,seg,0);
        if(st==L65M_OK)st=phase_records_16(w,bits,seg,1);
        if(st==L65M_OK&&seg<(uint8_t)((w->plan.strings_bytes-1u)>>10)){
            w->cursor_a=(uint16_t)(seg+1u);w->repeat_phase=1;}
    }while(0);
    return phase_leave(w,16,st);
}

SLICE_HELP(17) uint8_t implicit_name(l65m_overlay_work*w,uint16_t off);

SLICE_HELP(17) uint8_t phase_records_17(l65m_overlay_work*w,uint8_t nodes){
    uint8_t records[L65M_RECORD_BLOCK],*p,*end,stride=nodes?10u:8u;
    uint8_t st=L65M_OK;uint16_t pos=nodes?w->plan.nodes_off:w->plan.entries_off;
    uint16_t limit=nodes?w->plan.patches_off:w->plan.index_off,n;
    while(pos<limit&&st==L65M_OK){
        n=(uint16_t)(limit-pos);if(n>sizeof records)n=sizeof records;
        if(!l65m_overlay_metadata(w,pos,records,n))return L65M_ERR_SOURCE;
        p=records;end=records+n;
        while(p<end&&st==L65M_OK){
            if((!nodes||p[0]==LIT_SYMBOL)&&v16(p+(nodes?8u:0u))!=0xffffu)
                st=implicit_name(w,v16(p+(nodes?8u:0u)));
            p+=stride;
        }
        pos=(uint16_t)(pos+n);
    }
    return st;
}

SLICE(17) uint8_t l65m_overlay_phase_17(void *context) {
    l65m_overlay_work*w=context;uint8_t st=L65M_OK;
    if(!phase_enter(w,17))return L65M_ERR_STATE;
    st=phase_records_17(w,0);
    if(st==L65M_OK)st=phase_records_17(w,1);
    return phase_leave(w,17,st);
}

SLICE_HELP(17) uint8_t implicit_name(l65m_overlay_work*w,uint16_t off){
    char name[10];uint16_t n=(uint16_t)(w->plan.strings_bytes-off);
    if(n>sizeof name)n=sizeof name;
    if(!l65m_overlay_metadata(w,(uint16_t)(w->plan.strings_off+off),name,n))
        return L65M_ERR_SOURCE;
    if(n>=2u&&name[0]=='t'&&!name[1])w->flags|=WORK_IMPLICIT_T;
    if(n>=10u&&name[0]=='%'&&name[1]=='l'&&name[2]=='i'&&name[3]=='t'
       &&name[4]=='-'&&name[5]=='k'&&name[6]=='e'&&name[7]=='e'
       &&name[8]=='p'&&!name[9])w->flags|=WORK_IMPLICIT_KEEP;
    return L65M_OK;
}

SLICE(18) uint8_t l65m_overlay_phase_18(void *context) {
    l65m_overlay_work*w=context;char name[10];uint16_t len;uint8_t st=L65M_OK;
    if(!phase_enter(w,18))return L65M_ERR_STATE;
#define IMPLICIT_T() do{name[0]='t';name[1]=0;len=1;}while(0)
#define IMPLICIT_KEEP() do{name[0]='%';name[1]='l';name[2]='i';name[3]='t';name[4]='-';name[5]='k';name[6]='e';name[7]='e';name[8]='p';name[9]=0;len=9;}while(0)
    if(st==L65M_OK&&(w->flags&WORK_ANY_T)&&!(w->flags&WORK_IMPLICIT_T)){IMPLICIT_T();if(!w->limits.symbol_exists(w->limits.symbol_ctx,name))account_symbol(w,len);}
    if(st==L65M_OK&&(w->flags&WORK_ANY_POINTER)&&!(w->flags&WORK_IMPLICIT_KEEP)){IMPLICIT_KEEP();if(!w->limits.symbol_exists(w->limits.symbol_ctx,name))account_symbol(w,len);}
#undef IMPLICIT_T
#undef IMPLICIT_KEEP
    return phase_leave(w,18,st);
}

SLICE(19) uint8_t l65m_overlay_phase_19(void *context) {
    l65m_overlay_work*w=context;uint32_t d;uint8_t st=L65M_OK;
    if(!phase_enter(w,19))return L65M_ERR_STATE;
    d=((uint32_t)w->limits.dir_count+7u)&~7u;d+=w->plan.entry_count;
    if(d>w->limits.dir_capacity||d>=0x1000u)st=L65M_ERR_DIRECTORY;
    else if(w->limits.symbol_count>w->limits.symbol_capacity
            ||w->symbols_total>(uint32_t)w->limits.symbol_capacity-w->limits.symbol_count)st=L65M_ERR_SYMBOLS;
    else if((w->flags&WORK_NAME_OVERFLOW)
            ||w->limits.namepool_used>w->limits.namepool_capacity
            ||w->name_bytes_total>(uint32_t)w->limits.namepool_capacity-w->limits.namepool_used)st=L65M_ERR_NAMEPOOL;
    if(st==L65M_OK){
        w->plan.dir_before=w->limits.dir_count;w->plan.dir_after=(uint16_t)d;
        w->plan.symbols_before=w->limits.symbol_count;w->plan.namepool_before=w->limits.namepool_used;
        w->plan.new_symbols=(uint16_t)w->symbols_total;w->plan.new_name_bytes=(uint16_t)w->name_bytes_total;
    }
    return phase_leave(w,19,st);
}

SLICE_HELP(20) uint8_t source_crc16(l65m_overlay_work*w,uint16_t*out){
    uint8_t block[L65M_BYTE_BLOCK],bits;uint16_t crc=0xffffu,off=0,n,i;
    while(off<w->plan.source_length){
        n=(uint16_t)(w->plan.source_length-off);if(n>L65M_BYTE_BLOCK)n=L65M_BYTE_BLOCK;
        if(!w->source.read(w->source.ctx,off,block,n))return L65M_ERR_SOURCE;
        for(i=0;i<n;i++){
            crc^=(uint16_t)block[i]<<8;bits=8;
            while(bits--)crc=crc&0x8000u?(uint16_t)((crc<<1)^0x1021u):(uint16_t)(crc<<1);
        }
        off=(uint16_t)(off+n);
    }
    *out=crc;return L65M_OK;
}

SLICE(20) uint8_t l65m_overlay_phase_20(void *context) {
    l65m_overlay_work*w=context;uint8_t st=L65M_OK;uint16_t crc;
    if(!phase_enter(w,20))return L65M_ERR_STATE;
    if(w->flags&WORK_ANY_HEAP_LITERAL)w->plan.root_slots=(uint8_t)(w->plan.max_graph_depth+3u);
    if(w->heap_total>w->limits.heap_free)st=L65M_ERR_HEAP;
    else if(w->limits.string_arena&&(w->limits.arena_used>w->limits.arena_capacity
            ||w->arena_total>w->limits.arena_capacity-w->limits.arena_used))st=L65M_ERR_ARENA;
    else if(w->limits.roots_used>w->limits.roots_capacity
            ||w->plan.root_slots>w->limits.roots_capacity-w->limits.roots_used)st=L65M_ERR_ROOTS;
    if(st==L65M_OK)st=source_crc16(w,&crc);
    if(st==L65M_OK){
        w->plan.source_crc16=crc;
        w->plan.heap_free_before=w->limits.heap_free;w->plan.arena_used_before=w->limits.arena_used;
        w->plan.roots_before=w->limits.roots_used;w->plan.heap_cells=w->heap_total;
        w->plan.arena_bytes=w->arena_total;
    }
    if(st==L65M_OK)
        lisp65_c1_phase_mark_for(LISP65_C1_PROBE_PREFLIGHT,
                                 LISP65_C1_PROBE_EDGE_END);
    return phase_leave(w,20,st);
}

#ifndef LISP65_RUNTIME_OVERLAY
__attribute__((noinline)) l65m_status
l65m_validate(const l65m_source *src, uint16_t code_base,
              const l65m_limits *lim, l65m_plan *out) {
    l65m_overlay_work work,*w=&work;uint8_t st;
    if(!src||!lim||!out||!src->read||!lim->symbol_exists)return L65M_ERR_ARGUMENT;
    l65m_overlay_work_init(w,src,code_base,lim,out);
#define RUN(n,id) do{do{st=l65m_overlay_phase_##n(w);if(st!=L65M_OK)return (l65m_status)st;}while(w->expected_phase==(id));}while(0)
    RUN(00,0);RUN(01,1);RUN(02,2);RUN(03,3);RUN(04,4);RUN(05,5);RUN(06,6);RUN(07,7);
    RUN(08,8);RUN(09,9);RUN(10,10);RUN(11,11);RUN(12,12);RUN(13,13);RUN(14,14);
    RUN(15,15);RUN(16,16);RUN(17,17);RUN(18,18);RUN(19,19);RUN(20,20);
#undef RUN
    return L65M_OK;
}
#endif

#endif /* LISP65_VM && LISP65_DISK_LIBS */
