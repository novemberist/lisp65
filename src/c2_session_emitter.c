/* Product C2I-v2 emitter.
 *
 * The staging window is deliberately the same byte domain consumed by M65D
 * and the session append path.  No L65M record, patch table or magic is
 * emitted here.  Static product images are produced offline; all code born on
 * the device (interactive or persistent) passes through this one state
 * machine.
 */
#include "c2_session_emitter.h"

#if defined(LISP65_C2_PRODUCT_CUT) && defined(LISP65_COMPILE_STRING)
#ifdef LISP65_C2_KERNAL_UNMAP
#define C2_KERNAL_RESIDENT __attribute__((noinline, section(".lisp65_c2_kernal_window.c2_resident")))
#define C2_SESSION_WINDOW_STATE \
    __attribute__((used, section(".lisp65_c2_kernal_window.session_emitter_state")))
#else
#define C2_KERNAL_RESIDENT
#define C2_SESSION_WINDOW_STATE
#endif

#include "mem.h"
#include "eval.h"
#include "c2_product_runtime.h"
#include "c2_kernal_facade.h"
#include "c2_kernal_layout.h"
#include "c2_phase_scratch.h"
#include "c2_literal_cursor.h"
#include "c2-stream-decoder.h"
#include "symbol.h"
#include "vm.h"
#include "vm_runtime_overlay.h"

#define C2E_MAX_ENTRIES 64u
#define C2E_MAX_LITERALS 256u
#define C2E_MAX_ROOTS 48u
#define C2E_MAX_STRINGS 2048u
#define C2E_MAX_TOTAL 8192u
#define C2E_CODE_BASE 64u
#define C2E_ENTRY_STAGE 8192u
#define C2E_LITERAL_STAGE 9216u
#define C2E_STRING_STAGE 11264u
#define C2E_ANONYMOUS 0xffffu
#define C2E_SECTION(name) __attribute__((noinline, section(".lisp65_rt_c2emit_" name)))
#define C2E_INLINE static __attribute__((always_inline)) inline

enum {
    C2K_NIL = 0, C2K_TRUE = 1, C2K_FIXNUM = 2, C2K_STRING = 3,
    C2K_ENTRY = 4, C2K_EXPORT = 5, C2K_NATIVE = 6,
    C2K_PAIR = 7, C2K_SYMBOL = 8
};

typedef struct __attribute__((may_alias)) {
    uint8_t kind;
    uint16_t arg0;
    uint32_t arg1;
} c2e_descriptor;

typedef struct {
    obj cdr_value;
    uint16_t car_ordinal;
    uint8_t state;
} c2e_literal_frame;

typedef struct {
    uint16_t code_cursor;
    uint16_t entry_count;
    uint16_t literal_count;
    uint16_t string_bytes;
    uint8_t active;
    uint8_t failed;
#ifndef LISP65_C2_RESIDENCY_TRIAGE
    c2e_descriptor roots[C2E_MAX_ROOTS];
#endif
} c2e_state;

#ifdef LISP65_C2_RESIDENCY_TRIAGE
/* The 48 immutable root descriptors are emitter-session state, not CPU-hot
 * state.  They occupy the fixed Bank-5 gap immediately below C2J and never
 * overlap the maximum publication journal.  Each descriptor is written once
 * by literal_prep and read once by literal_append. */
#define C2E_ROOT_STATE_BYTES ((uint16_t)(C2E_MAX_ROOTS * sizeof(c2e_descriptor)))
#define C2E_ROOT_STATE_BASE ((uint16_t)(50752u - C2E_ROOT_STATE_BYTES))
_Static_assert(sizeof(c2e_descriptor) == 7u,
               "C2 emitter root descriptor geometry drift");
_Static_assert(C2E_ROOT_STATE_BASE >= 33840u + 2048u * 4u,
               "C2 emitter roots overlap the maximum export journal");
static uint8_t c2e_root_write(uint16_t index, const c2e_descriptor *value) {
    return index < C2E_MAX_ROOTS && value
        && c2_stream_c2d_write((uint16_t)(C2E_ROOT_STATE_BASE
                                  + index * sizeof *value),
                               value, sizeof *value);
}
static uint8_t c2e_root_read(uint16_t index, c2e_descriptor *value) {
    return index < C2E_MAX_ROOTS && value
        && c2_stream_c2d_read((uint16_t)(C2E_ROOT_STATE_BASE
                                 + index * sizeof *value),
                              value, sizeof *value);
}
#endif

typedef struct {
    obj cursor;
    obj helper;
    obj export_name;
    obj function;
    obj literals;
    obj literal_walk;
    obj code;
    obj literal_current;
    /* add() owns function_count; finalize() starts only after add() has
     * returned and owns final_length.  Their lifetimes are disjoint. */
    union {
        uint16_t function_count;
        uint16_t final_length;
    };
    uint16_t local;
    uint16_t literal_count;
    /* literal_index dies when literal traversal completes; code_start is
     * born and consumed wholly inside the following code phase. */
    union {
        uint16_t literal_index;
        uint16_t code_start;
    };
    uint16_t code_count;
    uint16_t first;
    uint16_t name_off;
    uint8_t export_flags;
    uint8_t nargs;
    uint8_t nlocals;
    uint8_t flags;
    uint8_t is_main;
    uint8_t literal_depth;
    uint8_t literal_have;
    uint8_t literal_done;
    uint8_t literal_atom_pending;
    c2e_descriptor literal_result;
    c2e_literal_frame literal_stack[49];
    c2_emit_status status;
    /* The persistent emitter state shares the already-owned phase scratch.
     * Its address changes; every c2e.* access and its semantics stay intact. */
    c2e_state session;
} c2e_work_state;

_Static_assert(sizeof(c2e_work_state) == LISP65_C2_INSTALL_TRACE_OFFSET,
               "C2 emitter lifetime union must exactly fill its scratch span");
_Static_assert(sizeof(c2e_state) == 10u,
               "C2 emitter session state geometry drift");
_Static_assert(sizeof(c2e_work_state) <= LISP65_C2_INSTALL_TRACE_OFFSET,
               "C2 emitter work state overlaps installer trace provenance");
#define c2ew (*(c2e_work_state *)(void *)lisp65_c2_phase_scratch)
#define c2e (c2ew.session)

LISP65_C2_FIXED_BANK0_CODE("c2e_cons")
uint8_t c2_facade_target_c2e_cons(obj value) {
    return IS_PTR(value) && cell_type(value) == T_CONS;
}
#define c2e_cons(value) c2_facade_c2e_cons(value)
#define car(value) c2_facade_car(value)
#define cdr(value) c2_facade_cdr(value)
#define intern(name) c2_facade_intern(name)
static uint8_t c2e_symbol(obj value) {
    return IS_SYMI(value) || (IS_PTR(value) && cell_type(value) == T_SYM);
}
static void c2e_put(uint16_t at, uint8_t value) {
    ext_disk_put((uint16_t)(256u + at), value);
}
static uint8_t c2e_get(uint16_t at) {
    return ext_disk_get((uint16_t)(256u + at));
}
static void c2e_w16(uint16_t at, uint16_t value) {
    c2e_put(at, (uint8_t)value); c2e_put((uint16_t)(at + 1u), (uint8_t)(value >> 8));
}
static void c2e_w24(uint16_t at, uint32_t value) {
    c2e_put(at, (uint8_t)value); c2e_put((uint16_t)(at + 1u), (uint8_t)(value >> 8));
    c2e_put((uint16_t)(at + 2u), (uint8_t)(value >> 16));
}
C2E_SECTION("final_crc") static void c2e_w32(uint16_t at, uint32_t value) {
    c2e_w16(at, (uint16_t)value); c2e_w16((uint16_t)(at + 2u), (uint16_t)(value >> 16));
}
C2E_SECTION("final_crc") static uint32_t c2e_crc(uint16_t at, uint16_t bytes) {
    uint32_t crc = 0xffffffffUL; uint16_t i; uint8_t bit;
    for (i = 0; i < bytes; ++i) {
        crc ^= c2e_get((uint16_t)(at + i));
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc >> 1) ^ (0xedb88320UL & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}
C2E_INLINE uint8_t c2e_fix_byte(obj value, uint8_t *out) {
    int16_t n;
    if (!IS_FIX(value)) return 0;
    n = FIXVAL(value); if (n < 0 || n > 255) return 0;
    *out = (uint8_t)n; return 1;
}
C2E_INLINE obj c2e_nth(obj list, uint8_t index) {
    while (index-- && c2e_cons(list)) list = cdr(list);
    return c2e_cons(list) ? car(list) : NIL;
}
C2E_INLINE uint16_t c2e_string_bytes(const char *text) {
    uint16_t n = 0; while (text[n]) ++n; return n;
}
C2E_INLINE uint16_t c2e_add_raw_string(const uint8_t *bytes, uint16_t length) {
    uint16_t off = c2e.string_bytes, i;
    if (length > 255u || off > C2E_MAX_STRINGS
        || (uint32_t)off + 2u + length > C2E_MAX_STRINGS) return C2E_ANONYMOUS;
    c2e_w16((uint16_t)(C2E_STRING_STAGE + off), length);
    for (i = 0; i < length; ++i)
        c2e_put((uint16_t)(C2E_STRING_STAGE + off + 2u + i), bytes[i]);
    c2e.string_bytes = (uint16_t)(off + 2u + length);
    return off;
}
C2E_INLINE uint16_t c2e_add_name(obj value) {
    const char *name;
    if (!c2e_symbol(value)) return C2E_ANONYMOUS;
    name = symname(value);
    return c2e_add_raw_string((const uint8_t *)name, c2e_string_bytes(name));
}
C2E_INLINE uint16_t c2e_add_string(obj value) {
    uint8_t block[255]; uint16_t n, i;
    if (!IS_PTR(value) || cell_type(value) != T_STR) return C2E_ANONYMOUS;
    n = str_len(value); if (n > sizeof block) return C2E_ANONYMOUS;
    for (i = 0; i < n; ++i) block[i] = str_byte(value, i);
    return c2e_add_raw_string(block, n);
}
C2E_SECTION("literal_prep") static void c2e_write_desc(
        uint16_t ordinal, const c2e_descriptor *d) {
    uint16_t at = (uint16_t)(C2E_LITERAL_STAGE + ordinal * 8u);
    c2e_put(at, d->kind); c2e_put((uint16_t)(at + 1u), 0);
    c2e_w16((uint16_t)(at + 2u), d->arg0);
    c2e_w24((uint16_t)(at + 4u), d->arg1);
    c2e_put((uint16_t)(at + 7u), 0);
}
C2E_SECTION("literal_prep") static c2_emit_status c2e_append_desc(
        const c2e_descriptor *d, uint16_t *ordinal) {
    if (c2e.literal_count >= C2E_MAX_LITERALS) return C2_EMIT_LITERALS;
    *ordinal = c2e.literal_count++;
    c2e_write_desc(*ordinal, d); return C2_EMIT_OK;
}

/* Prepare one non-pair descriptor.  Ordinary pairs are lowered iteratively by
 * the overlay entry below, so no C recursion consumes the product stack. */
C2E_SECTION("literal_atom") static c2_emit_status c2e_prepare_atom(
                                          obj value, obj helper,
                                          uint16_t helper_entries,
                                          c2e_descriptor *root) {
    uint16_t off;
    root->arg0 = 0; root->arg1 = 0;
    if (value == NIL) { root->kind = C2K_NIL; return C2_EMIT_OK; }
    if (value == intern("t")) { root->kind = C2K_TRUE; return C2_EMIT_OK; }
    if (IS_FIX(value)) {
        root->kind = C2K_FIXNUM; root->arg0 = (uint16_t)FIXVAL(value);
        return C2_EMIT_OK;
    }
    if (c2e_cons(value) && car(value) == helper) {
        obj rest = cdr(value), index;
        if (!c2e_cons(rest) || cdr(rest) != NIL) return C2_EMIT_SHAPE;
        index = car(rest);
        if (!IS_FIX(index) || FIXVAL(index) < 0
            || (uint16_t)FIXVAL(index) >= helper_entries) return C2_EMIT_SHAPE;
        root->kind = C2K_ENTRY; root->arg0 = (uint16_t)FIXVAL(index);
        return C2_EMIT_OK;
    }
    if (c2e_symbol(value)) {
        off = c2e_add_name(value); if (off == C2E_ANONYMOUS) return C2_EMIT_STRINGS;
        root->kind = C2K_SYMBOL; root->arg0 = c2e_string_bytes(symname(value));
        root->arg1 = off; return C2_EMIT_OK;
    }
    if (IS_PTR(value) && cell_type(value) == T_STR) {
        off = c2e_add_string(value); if (off == C2E_ANONYMOUS) return C2_EMIT_STRINGS;
        root->kind = C2K_STRING; root->arg0 = str_len(value); root->arg1 = off;
        return C2_EMIT_OK;
    }
    return C2_EMIT_UNSUPPORTED;
}

C2_KERNAL_RESIDENT c2_emit_status c2_session_emit_reset(void) {
    (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER);
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_EMITTER))
        return C2_EMIT_STATE;
    c2e.code_cursor = C2E_CODE_BASE; c2e.entry_count = 0;
    c2e.literal_count = 0; c2e.string_bytes = 0;
    c2e.active = 1; c2e.failed = 0; return C2_EMIT_OK;
}

__attribute__((noinline, used))
uint8_t c2_facade_target_c2e_overlay(uint8_t slot) {
    uint8_t transport = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    return (uint8_t)(vm_runtime_overlay_exec(slot, &c2ew, &transport)
        == VM_RUNTIME_OVERLAY_OK && transport == C2_STREAM_OK
        && c2ew.status == C2_EMIT_OK);
}
#define c2e_overlay(slot) c2_facade_c2e_overlay(slot)

C2E_SECTION("prepare") uint8_t c2_session_emit_prepare_phase(void *opaque) {
    c2e_work_state *w = opaque; obj fields, walk; uint16_t field_count = 0;
    uint8_t byte;
    C2_INSTALL_TRACE_RESET_INNER();
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_PREPARE_SLOT);
    if (!w || !c2e_cons(w->cursor)) return C2_STREAM_ERR_STATE;
    w->function = car(w->cursor); fields = w->function;
    while (c2e_cons(fields) && field_count < 6u) {
        ++field_count; fields = cdr(fields);
    }
    if (field_count != 5u || fields != NIL
        || !c2e_fix_byte(c2e_nth(w->function, 0), &w->nargs)
        || !c2e_fix_byte(c2e_nth(w->function, 1), &w->nlocals)
        || !c2e_fix_byte(c2e_nth(w->function, 2), &w->flags)) {
        c2e.failed = 1; w->status = C2_EMIT_SHAPE; return C2_STREAM_OK;
    }
    w->literals = c2e_nth(w->function, 3); walk = w->literals;
    w->literal_count = 0;
    while (c2e_cons(walk) && w->literal_count <= C2E_MAX_ROOTS) {
        ++w->literal_count; walk = cdr(walk);
    }
    if (walk != NIL || w->literal_count > C2E_MAX_ROOTS) {
        c2e.failed = 1; w->status = C2_EMIT_LITERALS; return C2_STREAM_OK;
    }
    w->code = c2e_nth(w->function, 4); walk = w->code; w->code_count = 0;
    while (c2e_cons(walk)) {
        if (!c2e_fix_byte(car(walk), &byte) || w->code_count == 0xffffu) {
            c2e.failed = 1; w->status = C2_EMIT_SHAPE; return C2_STREAM_OK;
        }
        ++w->code_count; walk = cdr(walk);
    }
    if (walk != NIL) { c2e.failed = 1; w->status = C2_EMIT_SHAPE; return C2_STREAM_OK; }
    return C2_STREAM_OK;
}

C2E_SECTION("name") uint8_t c2_session_emit_name_phase(void *opaque) {
    c2e_work_state *w = opaque;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_NAME_SLOT);
    if (!w || w->status != C2_EMIT_OK) return C2_STREAM_OK;
    w->is_main = (uint8_t)(w->local + 1u == w->function_count);
    w->name_off = C2E_ANONYMOUS;
    if (w->is_main && w->export_name != NIL && w->export_name != intern("t")) {
        w->name_off = c2e_add_name(w->export_name);
        if (w->name_off == C2E_ANONYMOUS) {
            c2e.failed = 1; w->status = C2_EMIT_STRINGS;
        }
    }
    return C2_STREAM_OK;
}

C2E_SECTION("literal_prep") uint8_t c2_session_emit_literal_prep_phase(void *opaque) {
    c2e_work_state *w = opaque; c2e_literal_frame *frame; uint16_t ordinal;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_LITERAL_PREP_SLOT);
    if (!w || w->status != C2_EMIT_OK) return C2_STREAM_OK;
    if (w->literal_index >= w->literal_count || w->literal_done)
        return C2_STREAM_ERR_STATE;
    if (w->literal_atom_pending) return C2_STREAM_ERR_STATE;
    if (!w->literal_have) {
        if (c2e_cons(w->literal_current) && car(w->literal_current) != w->helper) {
            if (w->literal_depth >= 48u) {
                c2e.failed = 1; w->status = C2_EMIT_LITERALS; return C2_STREAM_OK;
            }
            frame = &w->literal_stack[w->literal_depth++];
            frame->cdr_value = cdr(w->literal_current); frame->state = 0;
            w->literal_current = car(w->literal_current); return C2_STREAM_OK;
        }
        w->literal_atom_pending = 1; return C2_STREAM_OK;
    }
    if (!w->literal_depth) {
#ifdef LISP65_C2_RESIDENCY_TRIAGE
        if (!c2e_root_write(w->literal_index, &w->literal_result)) {
            c2e.failed = 1; w->status = C2_EMIT_STATE; return C2_STREAM_OK;
        }
#else
        c2e.roots[w->literal_index] = w->literal_result;
#endif
        w->literal_done = 1; return C2_STREAM_OK;
    }
    frame = &w->literal_stack[w->literal_depth - 1u];
    w->status = c2e_append_desc(&w->literal_result, &ordinal);
    if (w->status != C2_EMIT_OK) { c2e.failed = 1; return C2_STREAM_OK; }
    if (!frame->state) {
        frame->car_ordinal = ordinal; frame->state = 1;
        w->literal_current = frame->cdr_value; w->literal_have = 0;
        return C2_STREAM_OK;
    }
    w->literal_result.kind = C2K_PAIR;
    w->literal_result.arg0 = frame->car_ordinal;
    w->literal_result.arg1 = ordinal;
    --w->literal_depth; w->literal_have = 1;
    return C2_STREAM_OK;
}

/* The traversal resident hands off exactly one stable atom cursor.  It may
 * neither advance the literal stack nor re-enter until this resident has
 * consumed that request and published the descriptor result. */
C2E_SECTION("literal_atom") uint8_t c2_session_emit_literal_atom_phase(void *opaque) {
    c2e_work_state *w = opaque;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_LITERAL_ATOM_SLOT);
    if (!w || w->status != C2_EMIT_OK
        || !c2_literal_atom_handoff_valid(w->literal_atom_pending,
            w->literal_have, w->literal_done, w->literal_index,
            w->literal_count, w->literal_depth))
        return C2_STREAM_ERR_STATE;
    w->status = c2e_prepare_atom(w->literal_current, w->helper,
        (uint16_t)(w->function_count - 1u), &w->literal_result);
    if (w->status != C2_EMIT_OK) c2e.failed = 1;
    w->literal_atom_pending = 0;
    w->literal_have = (uint8_t)(w->status == C2_EMIT_OK);
    return C2_STREAM_OK;
}

C2E_SECTION("literal_append") uint8_t c2_session_emit_literal_append_phase(void *opaque) {
    c2e_work_state *w = opaque; uint16_t i, ordinal, at;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_LITERAL_APPEND_SLOT);
#ifdef LISP65_C2_RESIDENCY_TRIAGE
    c2e_descriptor root;
#else
    c2e_descriptor *d;
#endif
    if (!w || w->status != C2_EMIT_OK) return C2_STREAM_OK;
    w->first = c2e.literal_count;
    for (i = 0; i < w->literal_count; ++i) {
        if (c2e.literal_count >= C2E_MAX_LITERALS) {
            c2e.failed = 1; w->status = C2_EMIT_LITERALS; return C2_STREAM_OK;
        }
        ordinal = c2e.literal_count++;
#ifdef LISP65_C2_RESIDENCY_TRIAGE
        if (!c2e_root_read(i, &root)) {
            c2e.failed = 1; w->status = C2_EMIT_STATE; return C2_STREAM_OK;
        }
#define C2E_ROOT_FIELD(field) root.field
#else
        d = &c2e.roots[i];
#define C2E_ROOT_FIELD(field) d->field
#endif
        at = (uint16_t)(C2E_LITERAL_STAGE + ordinal * 8u);
        c2e_put(at, C2E_ROOT_FIELD(kind)); c2e_put((uint16_t)(at + 1u), 0);
        c2e_w16((uint16_t)(at + 2u), C2E_ROOT_FIELD(arg0));
        c2e_w24((uint16_t)(at + 4u), C2E_ROOT_FIELD(arg1));
        c2e_put((uint16_t)(at + 7u), 0);
#undef C2E_ROOT_FIELD
    }
    return C2_STREAM_OK;
}

C2E_SECTION("code") uint8_t c2_session_emit_code_phase(void *opaque) {
    c2e_work_state *w = opaque; obj walk; uint16_t at, i; uint8_t byte;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_CODE_SLOT);
    if (!w || w->status != C2_EMIT_OK) return C2_STREAM_OK;
    if ((uint32_t)c2e.code_cursor + 7u + w->literal_count * 2u + w->code_count
            > C2E_MAX_TOTAL) {
        c2e.failed = 1; w->status = C2_EMIT_OUTPUT; return C2_STREAM_OK;
    }
    w->code_start = c2e.code_cursor;
    c2e_put(c2e.code_cursor++, 0xb5u); c2e_put(c2e.code_cursor++, w->nargs);
    c2e_put(c2e.code_cursor++, w->nlocals); c2e_put(c2e.code_cursor++, w->flags);
    c2e_w16(c2e.code_cursor, w->code_count); c2e.code_cursor += 2u;
    c2e_put(c2e.code_cursor++, (uint8_t)w->literal_count);
    for (i = 0; i < w->literal_count * 2u; ++i) c2e_put(c2e.code_cursor++, 0);
    walk = w->code;
    while (c2e_cons(walk)) {
        (void)c2e_fix_byte(car(walk), &byte); c2e_put(c2e.code_cursor++, byte);
        walk = cdr(walk);
    }
    at = (uint16_t)(C2E_ENTRY_STAGE + c2e.entry_count * 16u);
    c2e_w24(at, (uint32_t)(w->code_start - C2E_CODE_BASE));
    c2e_w16((uint16_t)(at + 3u), (uint16_t)(c2e.code_cursor - w->code_start));
    c2e_w16((uint16_t)(at + 5u), w->first);
    c2e_put((uint16_t)(at + 7u), (uint8_t)w->literal_count);
    c2e_w16((uint16_t)(at + 8u), w->name_off); c2e_put((uint16_t)(at + 10u), w->nargs);
    c2e_put((uint16_t)(at + 11u),
        (uint8_t)(w->is_main && w->name_off != C2E_ANONYMOUS ? w->export_flags : 0));
    c2e_w16((uint16_t)(at + 12u), c2e.entry_count); c2e_w16((uint16_t)(at + 14u), 0);
    ++c2e.entry_count; ++w->local; w->cursor = cdr(w->cursor); return C2_STREAM_OK;
}

C2_KERNAL_RESIDENT c2_emit_status c2_session_emit_add(obj fnlist, obj export_name, uint8_t export_flags) {
    obj cursor = fnlist;
    if (!c2e.active || c2e.failed) return C2_EMIT_STATE;
    c2ew.function_count = 0;
    while (c2e_cons(cursor)) { ++c2ew.function_count; cursor = cdr(cursor); }
    if (cursor != NIL || !c2ew.function_count
        || c2ew.function_count > C2E_MAX_ENTRIES - c2e.entry_count)
        return C2_EMIT_ENTRIES;
    c2ew.cursor = fnlist; c2ew.helper = intern("%lcc-helper");
    c2ew.export_name = export_name; c2ew.export_flags = export_flags; c2ew.local = 0;
    while (c2e_cons(c2ew.cursor)) {
        c2ew.status = C2_EMIT_OK;
        if (!c2e_overlay(LISP65_C2_EMIT_PREPARE_SLOT)
            || !c2e_overlay(LISP65_C2_EMIT_NAME_SLOT)
            )
            return c2ew.status != C2_EMIT_OK ? c2ew.status : C2_EMIT_STATE;
        c2ew.literal_walk = c2ew.literals; c2ew.literal_index = 0;
        while (c2ew.literal_index < c2ew.literal_count) {
            c2ew.literal_current = car(c2ew.literal_walk);
            c2ew.literal_depth = 0; c2ew.literal_have = 0;
            c2ew.literal_done = 0; c2ew.literal_atom_pending = 0;
            while (!c2ew.literal_done) {
                if (!c2e_overlay(LISP65_C2_EMIT_LITERAL_PREP_SLOT)
                    || (c2ew.literal_atom_pending
                        && !c2e_overlay(LISP65_C2_EMIT_LITERAL_ATOM_SLOT)))
                    return c2ew.status != C2_EMIT_OK ? c2ew.status : C2_EMIT_STATE;
            }
            c2ew.literal_walk = cdr(c2ew.literal_walk); ++c2ew.literal_index;
        }
        if (!c2e_overlay(LISP65_C2_EMIT_LITERAL_APPEND_SLOT)
            || !c2e_overlay(LISP65_C2_EMIT_CODE_SLOT))
            return c2ew.status != C2_EMIT_OK ? c2ew.status : C2_EMIT_STATE;
    }
    return C2_EMIT_OK;
}

C2E_SECTION("final_meta") uint8_t c2_session_emit_final_meta_phase(void *opaque) {
    c2e_work_state *w = opaque; uint16_t metadata, literals, strings, bytes, i;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_FINAL_META_SLOT);
    if (!w || !c2e.active || c2e.failed || !c2e.entry_count) {
        if (w) w->status = C2_EMIT_STATE; return C2_STREAM_OK;
    }
    metadata = c2e.code_cursor; literals = (uint16_t)(24u + c2e.entry_count * 16u);
    strings = (uint16_t)(literals + c2e.literal_count * 8u);
    bytes = (uint16_t)(strings + c2e.string_bytes); if (bytes & 1u) ++bytes;
    w->final_length = (uint16_t)(metadata + bytes);
    if (w->final_length > C2E_MAX_TOTAL) {
        c2e.failed = 1; w->status = C2_EMIT_OUTPUT; return C2_STREAM_OK;
    }
    c2e_put(metadata, 'C'); c2e_put(metadata + 1u, '2'); c2e_put(metadata + 2u, 'I');
    c2e_put(metadata + 3u, 0); c2e_put(metadata + 4u, 2); c2e_put(metadata + 5u, 24);
    c2e_put(metadata + 6u, 16); c2e_put(metadata + 7u, 8);
    c2e_w16((uint16_t)(metadata + 8u), 0); c2e_w16((uint16_t)(metadata + 10u), c2e.entry_count);
    c2e_w16((uint16_t)(metadata + 12u), c2e.literal_count);
    c2e_w16((uint16_t)(metadata + 14u), 24u); c2e_w16((uint16_t)(metadata + 16u), literals);
    c2e_w16((uint16_t)(metadata + 18u), strings); c2e_w16((uint16_t)(metadata + 20u), c2e.string_bytes);
    c2e_w16((uint16_t)(metadata + 22u), 0);
    for (i = 0; i < c2e.entry_count * 16u; ++i)
        c2e_put((uint16_t)(metadata + 24u + i), c2e_get((uint16_t)(C2E_ENTRY_STAGE + i)));
    for (i = 0; i < c2e.literal_count * 8u; ++i)
        c2e_put((uint16_t)(metadata + literals + i), c2e_get((uint16_t)(C2E_LITERAL_STAGE + i)));
    for (i = 0; i < c2e.string_bytes; ++i)
        c2e_put((uint16_t)(metadata + strings + i), c2e_get((uint16_t)(C2E_STRING_STAGE + i)));
    if ((uint16_t)(strings + c2e.string_bytes) < bytes)
        c2e_put((uint16_t)(metadata + bytes - 1u), 0);
    return C2_STREAM_OK;
}

C2E_SECTION("final_crc") uint8_t c2_session_emit_final_crc_phase(void *opaque) {
    c2e_work_state *w = opaque; uint16_t code_bytes, metadata, metadata_bytes, i;
    uint32_t code_crc, metadata_crc, combined_crc, catalog_crc;
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_FINAL_CRC_SLOT);
    if (!w || w->status != C2_EMIT_OK) return C2_STREAM_OK;
    code_bytes = (uint16_t)(c2e.code_cursor - C2E_CODE_BASE); metadata = c2e.code_cursor;
    metadata_bytes = (uint16_t)(w->final_length - metadata);
    code_crc = c2e_crc(C2E_CODE_BASE, code_bytes); metadata_crc = c2e_crc(metadata, metadata_bytes);
    combined_crc = c2e_crc(C2E_CODE_BASE, (uint16_t)(code_bytes + metadata_bytes));
    for (i = 0; i < 32u; ++i) c2e_put((uint16_t)(32u + i), 0);
    c2e_put(32u, 'S'); c2e_put(33u, 'E'); c2e_put(34u, 'S'); c2e_put(35u, 'S');
    c2e_w24(40u, C2E_CODE_BASE); c2e_w16(43u, code_bytes);
    c2e_w24(45u, metadata); c2e_w16(48u, metadata_bytes);
    c2e_w32(50u, code_crc); c2e_w32(54u, metadata_crc); c2e_w32(58u, combined_crc);
    c2e_put(62u, 1u); catalog_crc = c2e_crc(32u, 32u);
    for (i = 0; i < 32u; ++i) c2e_put(i, 0);
    c2e_put(0u, 'L'); c2e_put(1u, '6'); c2e_put(2u, '5'); c2e_put(3u, 'S');
    c2e_put(4u, 4u); c2e_put(5u, 32u); c2e_put(6u, 32u); c2e_put(7u, 1u);
    c2e_w16(8u, 32u); c2e_w24(10u, 64u); c2e_w24(13u, w->final_length);
    c2e_w16(16u, 32u); c2e_w32(18u, catalog_crc);
    c2e_w32(22u, (uint32_t)LISP65_C2_PRODUCT_BUILD_ID); c2e_w16(26u, 1u);
    c2e.active = 0;
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_EMIT_FINAL_CRC);
    return C2_STREAM_OK;
}

C2_KERNAL_RESIDENT c2_emit_status c2_session_emit_finalize(uint16_t *length) {
    c2_emit_status status;
    uint16_t final_length;
    if (!length) return C2_EMIT_ARGUMENT;
    c2ew.status = C2_EMIT_OK;
    if (!c2e_overlay(LISP65_C2_EMIT_FINAL_META_SLOT)
        || !c2e_overlay(LISP65_C2_EMIT_FINAL_CRC_SLOT)) {
        status = c2ew.status != C2_EMIT_OK ? c2ew.status : C2_EMIT_STATE;
        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER);
        return status;
    }
    final_length = c2ew.final_length;
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER))
        return C2_EMIT_STATE;
    *length = final_length; return C2_EMIT_OK;
}

obj c2_session_emit_control(obj operation, obj payload) {
    int16_t op; c2_emit_status status; uint16_t length;
    if (!IS_FIX(operation)) { vm_status = VM_TYPEERROR; return NIL; }
    op = FIXVAL(operation);
    if (op == 0) {
        if (payload != NIL) { vm_status = VM_TYPEERROR; return NIL; }
        return c2_session_emit_reset() == C2_EMIT_OK ? intern("t") : NIL;
    }
    if (op == 1) {
        obj fnlist, name, flags;
        if (!c2e_cons(payload) || !c2e_cons(cdr(payload))
            || !c2e_cons(cdr(cdr(payload))) || cdr(cdr(cdr(payload))) != NIL) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        fnlist = car(payload); name = car(cdr(payload)); flags = car(cdr(cdr(payload)));
        if (!IS_FIX(flags) || FIXVAL(flags) < 0 || FIXVAL(flags) > 3) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        status = c2_session_emit_add(fnlist, name, (uint8_t)FIXVAL(flags));
        if (status != C2_EMIT_OK) { vm_status = VM_BADOPCODE; return NIL; }
        return intern("t");
    }
    if (op == 2) {
        obj buffer;
        if (payload != NIL) { vm_status = VM_TYPEERROR; return NIL; }
        status = c2_session_emit_finalize(&length);
        if (status != C2_EMIT_OK) { vm_status = VM_BADOPCODE; return NIL; }
        mem_oom = 0; buffer = buf_from_stage(length);
        if (buffer == NIL || mem_oom) { vm_status = VM_HEAPOOM; return NIL; }
        return buffer;
    }
    vm_status = VM_TYPEERROR; return NIL;
}

#endif
