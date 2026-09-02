/* C2 product runtime integration.
 *
 * This file intentionally has no dependency on the historical container,
 * validator, commit path or directory arrays.  Physical Attic addresses are
 * represented as uint32_t DMA-domain values, never as C pointers.
 */
#include "c2_product_runtime.h"

#ifdef LISP65_C2_PRODUCT_CUT

#ifndef C2_STREAM_PRODUCT_V3
#define C2_STREAM_PRODUCT_V3 1
#endif
#include "c2-stream-v2-decoder.h"
#include "c2_product_decoder.h"
#include "c2_kernal_facade.h"
#include "c2_kernal_layout.h"
#include "c2_phase_scratch.h"
#include "c2_platform_dma.h"
#include "c2_session_emitter.h"
#include "eval.h"
#include "interrupt.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "vm_runtime_overlay.h"

#ifndef LISP65_C2_PRODUCT_SHELF_BYTES
#error "C2 product cut requires the exact generated shelf byte count"
#endif
#ifndef LISP65_C2_PRODUCT_BUILD_ID
#error "C2 product cut requires the exact product build identity"
#endif

#define C2_MAX_HOT_LITERALS 23u
#define C2_SESSION_SOURCE_TAG 0x800000UL
#define C2_EXPORT_JOURNAL_BASE LISP65_C2D_BYTES
#define C2_EXPORT_JOURNAL_RECORD_BYTES 4u
#define C2_APPEND_SECTION(name) __attribute__((noinline, section(".lisp65_rt_c2append_" name)))
#define C2_APPEND_INLINE static __attribute__((always_inline)) inline
#ifdef LISP65_C2_KERNAL_UNMAP
#define C2_KERNAL_RESIDENT __attribute__((noinline, section(".lisp65_c2_kernal_window.c2_resident")))
#else
#define C2_KERNAL_RESIDENT
#endif

static c2_stream_context LISP65_C2_FIXED_BANK0("runtime") c2_runtime;
static uint16_t LISP65_C2_FIXED_BANK0("committed_roots") c2_committed_roots;
static uint16_t LISP65_C2_FIXED_ZP("pending_roots") c2_pending_roots;
static uint16_t c2_journal_count;
static uint8_t LISP65_C2_FIXED_ZP("ready") c2_ready;
static c2_stream_context *LISP65_C2_FIXED_BANK0("decode_active")
    c2_decode_active;

/* Hardened 20-byte Enhanced-DMA job.  The job owns all high address nibbles;
 * callers never truncate a 28-bit physical address through uintptr_t. */
static uint8_t LISP65_C2_FIXED_BANK0("edma_job") c2_edma_job[20];

typedef struct __attribute__((may_alias)) {
    c2_stream_context *before;
    uint16_t *main_ordinal;
    c2_stream_context append;
    uint16_t length;
    uint16_t code_off;
    uint16_t code_len;
    uint16_t meta_off;
    uint16_t meta_len;
    uint16_t entries;
    uint16_t literals;
    uint16_t roots;
    uint16_t old_images;
    uint16_t old_entries;
    uint16_t old_res;
    uint16_t old_roots;
    uint16_t new_images;
    uint16_t new_entries;
    uint16_t new_res;
    uint16_t new_roots;
    uint32_t attic;
    uint8_t old_header[48];
    uint8_t new_header[48];
    uint8_t record[32];
    uint8_t meta[24];
    uint8_t staged;
    uint8_t committed;
    uint8_t rollback_rebuild_header;
} c2_append_state;

_Static_assert(sizeof(c2_append_state) <= LISP65_C2_PHASE_SCRATCH_BYTES,
               "C2 append state exceeds the exclusive phase scratch");
#define c2aw (*(c2_append_state *)(void *)lisp65_c2_phase_scratch)

#ifdef LISP65_C2_SLICED_APPEND
static uint8_t c2_publish_exports_from(uint16_t first);
#endif

static C2_KERNAL_RESIDENT void c2_dma_copy(uint32_t source, uint32_t target, uint16_t length) {
    uint8_t *job = c2_edma_job;
    job[0] = 0x0bu; job[1] = 0x80u; job[2] = (uint8_t)(source >> 20);
    job[3] = 0x81u; job[4] = (uint8_t)(target >> 20);
    job[5] = 0x85u; job[6] = 1u; job[7] = 0u; job[8] = 0u;
    job[9] = (uint8_t)length; job[10] = (uint8_t)(length >> 8);
    job[11] = (uint8_t)source; job[12] = (uint8_t)(source >> 8);
    job[13] = (uint8_t)((source >> 16) & 0x0fu);
    job[14] = (uint8_t)target; job[15] = (uint8_t)(target >> 8);
    job[16] = (uint8_t)((target >> 16) & 0x0fu);
    job[17] = 0u; job[18] = 0u; job[19] = 0u;
    __asm__ volatile(
        "lda #1\n\tsta $d703\n\tlda #0\n\tsta $d702\n\tsta $d704\n\t"
        "lda #mos16hi(c2_edma_job)\n\tsta $d701\n\t"
        "lda #mos16lo(c2_edma_job)\n\tsta $d705\n\t"
        ::: "a", "memory");
}

static uint16_t c2_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
static uint32_t c2_u24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_shelf_read(uint32_t offset, void *dst, uint16_t length) {
    uint32_t base = LISP65_C2_SHELF_PHYSICAL;
    uint32_t limit = (uint32_t)LISP65_C2_PRODUCT_SHELF_BYTES;
    if (offset & C2_SESSION_SOURCE_TAG) {
        offset &= ~C2_SESSION_SOURCE_TAG;
        base = LISP65_C2_SESSION_PHYSICAL;
        limit = LISP65_C2_SESSION_BYTES;
    }
    if (offset > limit || length > limit - offset) return 0;
    c2_dma_copy(base + offset,
                (uint32_t)(uint16_t)(uintptr_t)dst, length);
    return 1;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_read(uint16_t offset, void *dst, uint16_t length) {
    if (offset > LISP65_C2D_REGION_BYTES
        || length > (uint16_t)(LISP65_C2D_REGION_BYTES - offset)) return 0;
    c2_facade_vm_code_load(LISP65_C2D_BANK,
                           (uint16_t)(LISP65_C2D_BASE + offset),
                           length, (uint8_t *)dst);
    return 1;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length) {
    if (offset > LISP65_C2D_REGION_BYTES
        || length > (uint16_t)(LISP65_C2D_REGION_BYTES - offset)) return 0;
    c2_facade_c2_dma((uint16_t)(uintptr_t)src, 0u,
                     (uint16_t)(LISP65_C2D_BASE + offset),
                     LISP65_C2D_BANK, length);
    return 1;
}

/* Whole-phase decoder facade.  These helpers are immutable product-format
 * operations shared by several transported phases.  Housing one copy in the
 * owned window restores phase-granularity transport without removing any
 * format check from the proven decoder. */
C2_KERNAL_RESIDENT uint8_t c2_stream_product_image_read(
        c2_stream_context *c, uint16_t image, uint8_t out[20]) {
    uint8_t raw[32];
    uint32_t tag, code, meta;
    if (!c || !out || image >= c->image_count
        || !c2_stream_c2d_read((uint16_t)(c->images_offset + image * 32u),
                               raw, sizeof raw)) return 0;
    if (raw[0] > 1u || raw[1]
        || (raw[0] == 0u ? raw[2] != image
                         : raw[2] != (uint8_t)(image - 6u))
        || raw[3] || c2_u16(raw + 4) != c->generation) return 0;
    out[0] = (uint8_t)image; out[1] = 0;
    out[2] = raw[6]; out[3] = raw[7];
    out[4] = raw[8]; out[5] = raw[9];
    out[6] = raw[10]; out[7] = raw[11];
    out[8] = raw[12]; out[9] = raw[13];
    tag = raw[0] == 1u ? C2_SESSION_SOURCE_TAG : 0u;
    code = c2_u24(raw + 18) | tag;
    meta = c2_u24(raw + 23) | tag;
    out[10] = (uint8_t)code; out[11] = (uint8_t)(code >> 8);
    out[12] = (uint8_t)(code >> 16);
    out[13] = (uint8_t)meta; out[14] = (uint8_t)(meta >> 8);
    out[15] = (uint8_t)(meta >> 16);
    out[16] = raw[21]; out[17] = raw[22];
    out[18] = raw[26]; out[19] = raw[27];
    return 1;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_product_string_record_any(
        uint32_t pool, uint16_t pool_bytes, uint32_t wanted,
        uint16_t *length, uint32_t *payload) {
    uint8_t b[2];
    uint16_t cursor = 0, n;
    if (!length || !payload || wanted > 0xffffUL) return 0;
    while (cursor < pool_bytes) {
        if ((uint16_t)(pool_bytes - cursor) < 2u
            || !c2_stream_shelf_read(pool + cursor, b, 2u)) return 0;
        n = c2_u16(b);
        if (n > (uint16_t)(pool_bytes - cursor - 2u)) return 0;
        if (cursor == (uint16_t)wanted) {
            *length = n; *payload = pool + cursor + 2u; return 1;
        }
        cursor = (uint16_t)(cursor + 2u + n);
    }
    return 0;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_product_string_record(
        uint32_t pool, uint16_t pool_bytes, uint32_t wanted,
        uint16_t expected, uint32_t *payload) {
    uint16_t actual;
    return c2_stream_product_string_record_any(
               pool, pool_bytes, wanted, &actual, payload)
        && actual == expected;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_product_canonical_name(
        uint32_t at, uint16_t length) {
    uint8_t block[16];
    uint16_t done = 0, i;
    if (!length || length > 255u) return 0;
    while (done < length) {
        uint16_t n = (uint16_t)(length - done);
        if (n > sizeof block) n = sizeof block;
        if (!c2_stream_shelf_read(at + done, block, n)) return 0;
        for (i = 0; i < n; ++i)
            if (block[i] < 0x21u || block[i] > 0x7eu) return 0;
        done = (uint16_t)(done + n);
    }
    return 1;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_product_child_value(
        c2_stream_context *c, uint32_t meta, uint16_t literals_offset,
        uint16_t resolution_base, uint16_t local, uint16_t *value) {
    uint8_t descriptor[8], b[2];
    uint16_t word;
    if (!c || !value
        || !c2_stream_shelf_read(meta + literals_offset
                                 + (uint32_t)local * 8u,
                                 descriptor, sizeof descriptor)
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                                  + (resolution_base + local) * 2u),
                               b, 2u)) return 0;
    word = c2_u16(b);
    if (descriptor[0] == 3u || descriptor[0] == 7u) {
        if (word >= c->c2_root_count
            || !c2_stream_c2d_read((uint16_t)(c->roots_offset + word * 2u),
                                   b, 2u)) return 0;
        word = c2_u16(b);
        if (!word || word >= 0x8000u || (word & 1u)) return 0;
    }
    *value = word;
    return 1;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_name_value(uint8_t kind, uint32_t offset,
                             uint16_t length, uint16_t *value) {
    uint8_t block[16]; uint16_t done = 0, i;
    if (!value || (kind != 3u && kind != 5u && kind != 8u)) return 0;
    if (kind == 3u) {
        obj string = c2_facade_str_open();
        if (string == NIL) return 0;
        while (done < length) {
            uint16_t n = (uint16_t)(length - done);
            if (n > sizeof block) n = sizeof block;
            if (!c2_stream_shelf_read(offset + done, block, n)) {
                (void)str_close(string); return 0;
            }
            for (i = 0; i < n; ++i)
                if (!c2_facade_str_putc(string, block[i])) {
                    (void)str_close(string); return 0;
                }
            done = (uint16_t)(done + n);
        }
        string = str_close(string);
        if (string == NIL || mem_oom) return 0;
        *value = (uint16_t)string; return 1;
    }
    if (!length || length > LISP65_SYMBOL_NAME_MAX) return 0;
    while (done < length) {
        uint16_t n = (uint16_t)(length - done);
        if (n > sizeof block) n = sizeof block;
        if (!c2_stream_shelf_read(offset + done, block, n)) return 0;
        for (i = 0; i < n; ++i)
            sym_name_scratch[done + i] = (char)block[i];
        done = (uint16_t)(done + n);
    }
    sym_name_scratch[length] = 0;
    *value = (uint16_t)c2_facade_intern(sym_name_scratch);
    return (uint8_t)(*value != (uint16_t)NIL && !mem_oom);
}

uint8_t c2_stream_pair_value(uint16_t car_value, uint16_t cdr_value,
                             uint16_t *value) {
    obj pair;
    if (!value) return 0;
    pair = cons((obj)car_value, (obj)cdr_value);
    if (pair == NIL || mem_oom) return 0;
    *value = (uint16_t)pair; return 1;
}

C2_KERNAL_RESIDENT uint8_t c2_stream_gc_checkpoint(uint16_t roots_offset, uint16_t root_count) {
    if (!c2_decode_active || roots_offset != c2_decode_active->roots_offset
        || root_count != c2_decode_active->c2_root_count) return 0;
    c2_pending_roots = root_count;
    /* This seam publishes the canonical root plane before the next
     * allocation.  The host proof deliberately collects at every checkpoint
     * as a stress schedule; making that proof schedule product semantics
     * forced 283 full collections during cold boot.  Natural allocator GCs
     * still see every previously published value through pending_roots. */
    return (uint8_t)!mem_oom;
}

static C2_KERNAL_RESIDENT uint8_t c2_source_read(const uint8_t image[32], uint32_t relative,
                              void *dst, uint16_t length) {
    uint32_t base;
    if (image[0] == 0u) base = LISP65_C2_SHELF_PHYSICAL;
    else if (image[0] == 1u) base = LISP65_C2_SESSION_PHYSICAL;
    else return 0;
    if (c2_u16(image + 4) != c2_runtime.generation) return 0;
    c2_dma_copy(base + relative, (uint32_t)(uint16_t)(uintptr_t)dst, length);
    return 1;
}

__attribute__((noinline, used))
uint8_t c2_facade_target_overlay_call_family(uint8_t family,
                                              uint16_t generation,
                                              uint8_t slot, void *context) {
    uint8_t status = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    return (uint8_t)(vm_runtime_overlay_exec_family(
                         family, generation, slot, context, &status)
        == VM_RUNTIME_OVERLAY_OK && status == C2_STREAM_OK);
}

static C2_KERNAL_RESIDENT uint8_t c2_overlay_call(uint8_t slot, void *context) {
    return c2_facade_overlay_call_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
        c2_runtime.generation, slot, context);
}

/* Execute each proven logical decoder phase through one authenticated
 * transport.  Link 24's cursor split paid catalog/record/payload verification
 * more than 21,000 times during one boot; whole-phase residents preserve the
 * exact checks while amortizing transport at the intended phase boundary. */
static C2_KERNAL_RESIDENT uint8_t c2_decode_from(c2_stream_context *stream, uint8_t first) {
    if (first <= 0u && !c2_facade_overlay_call_family(
            LISP65_RUNTIME_OVERLAY_FAMILY_BOOT,
            0u, LISP65_C2_PHASE_00_SLOT, stream)) return 0;
    if (first <= 0u && !c2_facade_overlay_call_family(
            LISP65_RUNTIME_OVERLAY_FAMILY_BOOT,
            0u, LISP65_C2_PHASE_00B_SLOT, stream)) return 0;
    if (first <= 1u && !c2_facade_overlay_call_family(
            LISP65_RUNTIME_OVERLAY_FAMILY_BOOT,
            0u, LISP65_C2_PHASE_01_SLOT, stream)) return 0;
    if (first <= 2u
        && (!c2_facade_overlay_call_family(
                LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u,
                LISP65_C2_PHASE_02A_SLOT, stream)
            || !c2_facade_overlay_call_family(
                LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u,
                LISP65_C2_PHASE_02B_SLOT, stream))) return 0;
    if (first <= 3u) {
        if (!c2_facade_overlay_call_family(
                                    LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u,
                                    LISP65_C2_PHASE_03_SLOT, stream)
            || !stream->generation
            || c2_facade_select_family(
                   LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
                   stream->generation)
               != VM_RUNTIME_OVERLAY_OK) return 0;
    }
    if (first <= 4u && !c2_overlay_call(LISP65_C2_PHASE_04_SLOT, stream)) return 0;
    if (first <= 5u && !c2_overlay_call(LISP65_C2_PHASE_05_SLOT, stream)) return 0;
    if (first <= 6u
        && (!c2_overlay_call(LISP65_C2_PHASE_06A_SLOT, stream)
            || !c2_overlay_call(LISP65_C2_PHASE_06B_SLOT, stream))) return 0;
    if (first <= 7u && !c2_overlay_call(LISP65_C2_PHASE_07_SLOT, stream)) return 0;
    if (first <= 8u && !c2_overlay_call(LISP65_C2_PHASE_08_SLOT, stream)) return 0;
    if (first <= 9u && !c2_overlay_call(LISP65_C2_PHASE_09_SLOT, stream)) return 0;
    if (first <= 10u && !c2_overlay_call(LISP65_C2_PHASE_10_SLOT, stream)) return 0;
    if (first <= 11u && !c2_overlay_call(LISP65_C2_PHASE_11_SLOT, stream)) return 0;
    return (uint8_t)(first > 12u
        || c2_overlay_call(LISP65_C2_PHASE_12_SLOT, stream));
}

static C2_KERNAL_RESIDENT uint8_t c2_entry_records(uint16_t ordinal, uint8_t directory[10],
                                uint8_t image[32], uint8_t entry[16]) {
    uint8_t metadata_header[24]; uint16_t local, entries_offset;
    uint32_t metadata;
    if (!c2_ready || ordinal >= c2_runtime.entry_count
        || !c2_stream_c2d_read((uint16_t)(c2_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    if (directory[0] >= c2_runtime.image_count || directory[1]
        || c2_u16(directory + 8) != c2_runtime.generation) return 0;
    if (!c2_stream_c2d_read((uint16_t)(c2_runtime.images_offset
        + directory[0] * 32u), image, 32u)) return 0;
    local = c2_u16(directory + 2); metadata = c2_u24(image + 23);
    if (local >= c2_u16(image + 8)
        || !c2_source_read(image, metadata, metadata_header,
                           sizeof metadata_header)) return 0;
    entries_offset = c2_u16(metadata_header + 14);
    return c2_source_read(image, metadata + entries_offset
                          + (uint32_t)local * 16u, entry, 16u);
}

uint16_t c2_product_dir_count(void) {
    return c2_ready ? c2_runtime.entry_count : 0u;
}

uint8_t c2_product_static_image_named(obj name) {
    uint8_t record[32], image;
    uint16_t length, i;
    if (!c2_ready || !IS_PTR(name) || cell_type(name) != T_STR) return 0;
    length = str_len(name);
    if (!length || length > 8u) return 0;
    for (image = 0; image < 6u && image < c2_runtime.image_count; ++image) {
        if (!c2_stream_shelf_read(32u + (uint32_t)image * 32u,
                                  record, sizeof record)) return 0;
        for (i = 0; i < length && record[i] == str_byte(name, i); ++i) { }
        if (i == length && (length == 8u || record[length] == 0u)) return 1;
    }
    return 0;
}

C2_KERNAL_RESIDENT uint16_t c2_product_entry_length(uint16_t ordinal) {
    uint8_t d[10], image[32], entry[16];
    if (!c2_entry_records(ordinal, d, image, entry)) return 0;
    if (!c2_u16(d + 4) || c2_u16(d + 4) != c2_u16(entry + 3)) return 0;
    return c2_u16(d + 4);
}

uint8_t c2_product_entry_read(uint16_t ordinal, uint16_t relative,
                              uint8_t *destination, uint16_t length) {
    uint8_t d[10], image[32], entry[16];
    uint16_t code_length, i, lit_end;
    uint16_t hot[C2_MAX_HOT_LITERALS];
    c2_stream_materialize_context materialize;
    uint32_t source;
    if (!destination || !c2_entry_records(ordinal, d, image, entry)) return 0;
    code_length = c2_u16(entry + 3);
    if (relative > code_length || length > (uint16_t)(code_length - relative)) return 0;
    source = c2_u24(image + 18) + c2_u24(entry);
    if (!c2_source_read(image, source + relative, destination, length)) return 0;

    lit_end = (uint16_t)(7u + 2u * entry[7]);
    if (relative < lit_end && (uint16_t)(relative + length) > 7u && entry[7]) {
        materialize.stream = &c2_runtime;
        materialize.directory_ordinal = ordinal;
        materialize.hot_values = hot;
        materialize.hot_capacity = C2_MAX_HOT_LITERALS;
        materialize.hot_count = 0;
        if (!c2_overlay_call(LISP65_C2_PHASE_13_SLOT, &materialize)) return 0;
        if (materialize.hot_count != entry[7]) return 0;
        for (i = 0; i < length; ++i) {
            uint16_t at = (uint16_t)(relative + i);
            if (at >= 7u && at < lit_end) {
                uint16_t word = hot[(at - 7u) >> 1];
                destination[i] = (uint8_t)(((at - 7u) & 1u)
                    ? (word >> 8) : word);
            }
        }
    }
    return 1;
}

/* Root-plane ownership belongs to C2.  Keeping the walker in the owned
 * window avoids charging its block transport loop to the 26-byte ordinary
 * Bank-0 corridor.  The only return edge is the thirteenth pinned facade;
 * the window must never bind directly to moving gc_mark. */
C2_KERNAL_RESIDENT void c2_product_gc_mark_roots(void) {
    uint8_t b[32];
    uint16_t i, n, done = 0, scan = c2_committed_roots;
    if (c2_pending_roots > scan) scan = c2_pending_roots;
    while (done < scan) {
        n = (uint16_t)(scan - done);
        if (n > (uint16_t)(sizeof b / 2u))
            n = (uint16_t)(sizeof b / 2u);
        if (!c2_stream_c2d_read(
                (uint16_t)(c2_runtime.roots_offset + done * 2u),
                b, (uint16_t)(n * 2u))) break;
        for (i = 0; i < n; ++i)
            c2_facade_gc_mark((obj)((uint16_t)b[i * 2u]
                | (uint16_t)b[i * 2u + 1u] << 8));
        done = (uint16_t)(done + n);
    }
    for (i = 0; i < c2_journal_count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_JOURNAL_RECORD_BYTES), b, sizeof b)) break;
        c2_facade_gc_mark((obj)((uint16_t)b[2]
            | (uint16_t)b[3] << 8));
    }
}

C2_APPEND_INLINE uint8_t c2_export_name(
                              const uint8_t image[32], const uint8_t entry[16],
                              char *name) {
    uint8_t h[24], size[2], block[16];
    uint16_t name_offset = c2_u16(entry + 8), strings, bytes, n, done = 0, i;
    uint32_t metadata = c2_u24(image + 23), payload;
    if (name_offset == 0xffffu) return 2u;
    if (!c2_source_read(image, metadata, h, sizeof h)) return 0;
    strings = c2_u16(h + 18); bytes = c2_u16(h + 20);
    if (name_offset > bytes || (uint16_t)(bytes - name_offset) < 2u
        || !c2_source_read(image, metadata + strings + name_offset, size, 2u)) return 0;
    n = c2_u16(size);
    if (!n || n > LISP65_SYMBOL_NAME_MAX
        || n > (uint16_t)(bytes - name_offset - 2u)) return 0;
    payload = metadata + strings + name_offset + 2u;
    while (done < n) {
        uint16_t chunk = (uint16_t)(n - done);
        if (chunk > sizeof block) chunk = sizeof block;
        if (!c2_source_read(image, payload + done, block, chunk)) return 0;
        for (i = 0; i < chunk; ++i) name[done + i] = (char)block[i];
        done = (uint16_t)(done + chunk);
    }
    name[n] = 0; return 1;
}

#ifndef LISP65_C2_SLICED_APPEND
static void c2_restore_exports(void) {
    uint8_t b[4];
    while (c2_journal_count) {
        --c2_journal_count;
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + c2_journal_count * C2_EXPORT_JOURNAL_RECORD_BYTES), b, sizeof b))
            continue;
        set_sym_function((obj)c2_u16(b), (obj)c2_u16(b + 2));
    }
}
#endif

#ifndef LISP65_C2_SLICED_APPEND
static uint8_t c2_publish_exports_from(uint16_t first) {
    uint8_t d[10], image[32], entry[16], journal[4], named;
    uint16_t ordinal; obj symbol, old, published;
    char name[LISP65_SYMBOL_NAME_BUFFER];

    /* First pass may allocate symbol records, but publishes no callable. */
    for (ordinal = first; ordinal < c2_runtime.entry_count; ++ordinal) {
        if (!c2_entry_records(ordinal, d, image, entry)) return 0;
        named = c2_export_name(image, entry, name);
        if (!named) return 0;
        if (named == 1u && (c2_facade_intern(name) == NIL || mem_oom)) return 0;
    }

    c2_journal_count = 0;
    for (ordinal = first; ordinal < c2_runtime.entry_count; ++ordinal) {
        if (!c2_entry_records(ordinal, d, image, entry)) goto rollback;
        named = c2_export_name(image, entry, name);
        if (!named) goto rollback;
        if (named == 2u) continue;
        if (!sym_lookup(name, &symbol)) goto rollback;
        old = sym_function(symbol);
        if (entry[11] & 1u) {
            published = alloc(T_MACRO);
            if (published == NIL || mem_oom) goto rollback;
            cell_set_a(published, MK_BCODE(ordinal));
            cell_set_b(published, NIL);
        } else published = MK_BCODE(ordinal);
        journal[0] = (uint8_t)symbol;
        journal[1] = (uint8_t)((uint16_t)symbol >> 8);
        journal[2] = (uint8_t)old;
        journal[3] = (uint8_t)((uint16_t)old >> 8);
        if (!c2_stream_c2d_write((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + c2_journal_count * C2_EXPORT_JOURNAL_RECORD_BYTES),
                journal, sizeof journal)) goto rollback;
        ++c2_journal_count;
        set_sym_function(symbol, published);
    }
    c2_journal_count = 0;
    return 1;

rollback:
    c2_restore_exports();
    return 0;
}
#endif

uint8_t c2_product_boot(void) {
    if (vm_runtime_overlay_family() != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT)
        return 0;
    c2_ready = 0; c2_committed_roots = 0; c2_pending_roots = 0;
    c2_journal_count = 0;
    c2_stream_init(&c2_runtime, (uint32_t)LISP65_C2_PRODUCT_SHELF_BYTES,
                   LISP65_C2D_BYTES);
    c2_decode_active = &c2_runtime;
    if (!c2_decode_from(&c2_runtime, 0u)) return 0;
    c2_pending_roots = c2_runtime.c2_root_count;
    c2_committed_roots = c2_runtime.c2_root_count;
    c2_ready = 1;
    c2_decode_active = &c2_runtime;
    if (!c2_publish_exports_from(0)) {
        c2_ready = 0; return 0;
    }
    return 1;
}

uint8_t c2_product_prepare_boot(void) {
    /* Invalidation and boot-family entry are one product operation.  The
     * runtime transport accepts BOOT only with the zero generation written
     * here; SESSION then latches the nonzero generation decoded by phase 0. */
    c2_ready = 0;
    c2_runtime.generation = 0;
    c2_committed_roots = 0;
    c2_pending_roots = 0;
    c2_journal_count = 0;
    c2_decode_active = &c2_runtime;
    return c2_facade_select_family(
               LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u)
           == VM_RUNTIME_OVERLAY_OK;
}

C2_APPEND_INLINE uint16_t c2_stage_u16(uint16_t at) {
    return (uint16_t)ext_disk_get((uint16_t)(256u + at))
        | (uint16_t)ext_disk_get((uint16_t)(257u + at)) << 8;
}
C2_APPEND_INLINE uint32_t c2_stage_u24(uint16_t at) {
    return (uint32_t)ext_disk_get((uint16_t)(256u + at))
        | (uint32_t)ext_disk_get((uint16_t)(257u + at)) << 8
        | (uint32_t)ext_disk_get((uint16_t)(258u + at)) << 16;
}
C2_APPEND_INLINE uint32_t c2_stage_u32(uint16_t at) {
    return c2_stage_u24(at)
        | (uint32_t)ext_disk_get((uint16_t)(259u + at)) << 24;
}
#ifdef LISP65_C2_SLICED_APPEND
C2_APPEND_SECTION("crc") static uint32_t c2_stage_crc(uint16_t at, uint16_t bytes) {
#else
static uint32_t c2_stage_crc(uint16_t at, uint16_t bytes) {
#endif
    uint32_t crc = 0xffffffffUL; uint16_t i; uint8_t bit;
    for (i = 0; i < bytes; ++i) {
        crc ^= ext_disk_get((uint16_t)(256u + at + i));
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc >> 1) ^ (0xedb88320UL & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}
C2_APPEND_INLINE uint32_t c2_attic_watermark(void) {
    uint16_t image; uint8_t row[32]; uint32_t high = 0, end;
    for (image = 6u; image < c2_runtime.image_count; ++image) {
        if (!c2_stream_c2d_read((uint16_t)(c2_runtime.images_offset
                + image * 32u), row, sizeof row) || row[0] != 1u) return 0xffffffffUL;
        end = c2_u24(row + 23) + c2_u16(row + 26);
        if (end > high) high = end;
    }
    return (high + 1u) & ~1UL;
}
#ifndef LISP65_C2_SLICED_APPEND
static void c2_zero_plane(uint16_t at, uint16_t bytes) {
    static const uint8_t zeros[16] = {0};
    while (bytes) {
        uint16_t n = bytes > sizeof zeros ? sizeof zeros : bytes;
        (void)c2_stream_c2d_write(at, zeros, n);
        at = (uint16_t)(at + n); bytes = (uint16_t)(bytes - n);
    }
}
#endif
static C2_KERNAL_RESIDENT void c2_header_counts(uint8_t header[48], uint16_t images,
                             uint16_t entries, uint16_t resolutions,
                             uint16_t roots) {
    header[12] = (uint8_t)images; header[13] = (uint8_t)(images >> 8);
    header[16] = (uint8_t)entries; header[17] = (uint8_t)(entries >> 8);
    header[20] = (uint8_t)resolutions; header[21] = (uint8_t)(resolutions >> 8);
    header[24] = (uint8_t)roots; header[25] = (uint8_t)(roots >> 8);
}

#ifndef LISP65_C2_SLICED_APPEND
/* Validate/stage/resolve/publish one canonical staged extension.  `transient`
 * leaves the committed suffix live until the caller executes its main, then
 * c2_product_install restores the old counts and zeroes the mutable suffix. */
static C2_KERNAL_RESIDENT uint8_t c2_append_begin(uint16_t length, c2_stream_context *before,
                               uint16_t *main_ordinal) {
    uint8_t old_header[48], new_header[48], record[32], image_row[32];
    uint8_t meta[24], entry[16], readback[16];
    uint16_t code_off, code_len, meta_off, meta_len, entries, literals;
    uint16_t roots = 0, i, old_images, old_entries, old_res, old_roots;
    uint16_t new_images, new_entries, new_res, new_roots;
    uint32_t attic, combined;
    c2_stream_context append;

    if (!c2_ready || !before || !main_ordinal || length < 88u || length > 8192u)
        return 0;
    if (ext_disk_get(256u) != 'L' || ext_disk_get(257u) != '6'
        || ext_disk_get(258u) != '5' || ext_disk_get(259u) != 'S'
        || ext_disk_get(260u) != 4u || ext_disk_get(261u) != 32u
        || ext_disk_get(262u) != 32u || ext_disk_get(263u) != 1u
        || c2_stage_u16(8u) != 32u || c2_stage_u24(10u) != 64u
        || c2_stage_u24(13u) != length || c2_stage_u16(16u) != 32u
        || c2_stage_u32(22u) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID
        || c2_stage_u16(26u) != 1u
        || ext_disk_get(284u) || ext_disk_get(285u)
        || ext_disk_get(286u) || ext_disk_get(287u)
        || c2_stage_crc(32u, 32u) != c2_stage_u32(18u)) return 0;
    for (i = 0; i < sizeof record; ++i)
        record[i] = ext_disk_get((uint16_t)(288u + i));
    if (record[30] != 1u || record[31]
        || (record[0] != 'S' || record[1] != 'E' || record[2] != 'S' || record[3] != 'S'))
        return 0;
    code_off = (uint16_t)c2_stage_u24(40u); code_len = c2_stage_u16(43u);
    meta_off = (uint16_t)c2_stage_u24(45u); meta_len = c2_stage_u16(48u);
    if (code_off != 64u || !code_len || meta_off != (uint16_t)(code_off + code_len)
        || meta_len < 24u || (uint32_t)meta_off + meta_len != length
        || c2_stage_crc(code_off, code_len) != c2_stage_u32(50u)
        || c2_stage_crc(meta_off, meta_len) != c2_stage_u32(54u)
        || c2_stage_crc(code_off, (uint16_t)(code_len + meta_len))
            != c2_stage_u32(58u)) return 0;
    for (i = 0; i < sizeof meta; ++i)
        meta[i] = ext_disk_get((uint16_t)(256u + meta_off + i));
    if (meta[0] != 'C' || meta[1] != '2' || meta[2] != 'I' || meta[3]
        || meta[4] != 2u || meta[5] != 24u || meta[6] != 16u || meta[7] != 8u
        || c2_u16(meta + 8) || c2_u16(meta + 22)) return 0;
    entries = c2_u16(meta + 10); literals = c2_u16(meta + 12);
    if (!entries || c2_u16(meta + 14) != 24u
        || c2_u16(meta + 16) != (uint16_t)(24u + entries * 16u)
        || c2_u16(meta + 18) != (uint16_t)(24u + entries * 16u + literals * 8u)
        || (uint16_t)((c2_u16(meta + 18) + c2_u16(meta + 20) + 1u) & ~1u)
            != meta_len) return 0;
    for (i = 0; i < literals; ++i) {
        uint8_t kind = ext_disk_get((uint16_t)(256u + meta_off
            + c2_u16(meta + 16) + i * 8u));
        if (kind == 3u || kind == 7u) ++roots;
    }
    old_images = c2_runtime.image_count; old_entries = c2_runtime.entry_count;
    old_res = c2_runtime.resolution_count; old_roots = c2_runtime.c2_root_count;
    new_images = (uint16_t)(old_images + 1u);
    new_entries = (uint16_t)(old_entries + entries);
    new_res = (uint16_t)(old_res + literals);
    new_roots = (uint16_t)(old_roots + roots);
    if (new_images > 64u || new_entries > 2048u || new_res > 4096u
        || new_roots > 1536u) return 0;
    attic = c2_attic_watermark();
    if (attic == 0xffffffffUL || attic + length > LISP65_C2_SESSION_BYTES) return 0;
    c2_dma_copy(LISP65_EXT_DISK_FILE_PHYSICAL,
                LISP65_C2_SESSION_PHYSICAL + attic, length);
    for (i = 0; i < length; i = (uint16_t)(i + sizeof readback)) {
        uint16_t n = (uint16_t)(length - i), j;
        if (n > sizeof readback) n = sizeof readback;
        c2_dma_copy(LISP65_C2_SESSION_PHYSICAL + attic + i,
                    (uint32_t)(uint16_t)(uintptr_t)readback, n);
        for (j = 0; j < n; ++j)
            if (readback[j] != ext_disk_get((uint16_t)(256u + i + j))) return 0;
    }
    if (!c2_stream_c2d_read(0, old_header, sizeof old_header)) return 0;
    *before = c2_runtime;
    c2_zero_plane((uint16_t)(c2_runtime.images_offset + old_images * 32u), 32u);
    c2_zero_plane((uint16_t)(c2_runtime.entries_offset + old_entries * 10u),
                  (uint16_t)(entries * 10u));
    c2_zero_plane((uint16_t)(c2_runtime.resolutions_offset + old_res * 2u),
                  (uint16_t)(literals * 2u));
    c2_zero_plane((uint16_t)(c2_runtime.roots_offset + old_roots * 2u),
                  (uint16_t)(roots * 2u));

    for (i = 0; i < sizeof image_row; ++i) image_row[i] = 0;
    image_row[0] = 1u; image_row[2] = (uint8_t)(old_images - 6u);
    image_row[4] = (uint8_t)c2_runtime.generation;
    image_row[5] = (uint8_t)(c2_runtime.generation >> 8);
    image_row[6] = (uint8_t)old_entries; image_row[7] = (uint8_t)(old_entries >> 8);
    image_row[8] = (uint8_t)entries; image_row[9] = (uint8_t)(entries >> 8);
    image_row[10] = (uint8_t)old_res; image_row[11] = (uint8_t)(old_res >> 8);
    image_row[12] = (uint8_t)literals; image_row[13] = (uint8_t)(literals >> 8);
    image_row[14] = (uint8_t)old_roots; image_row[15] = (uint8_t)(old_roots >> 8);
    image_row[16] = (uint8_t)roots; image_row[17] = (uint8_t)(roots >> 8);
    combined = c2_stage_u32(58u);
    image_row[18] = (uint8_t)(attic + code_off);
    image_row[19] = (uint8_t)((attic + code_off) >> 8);
    image_row[20] = (uint8_t)((attic + code_off) >> 16);
    image_row[21] = (uint8_t)code_len; image_row[22] = (uint8_t)(code_len >> 8);
    image_row[23] = (uint8_t)(attic + meta_off);
    image_row[24] = (uint8_t)((attic + meta_off) >> 8);
    image_row[25] = (uint8_t)((attic + meta_off) >> 16);
    image_row[26] = (uint8_t)meta_len; image_row[27] = (uint8_t)(meta_len >> 8);
    image_row[28] = (uint8_t)combined; image_row[29] = (uint8_t)(combined >> 8);
    image_row[30] = (uint8_t)(combined >> 16); image_row[31] = (uint8_t)(combined >> 24);
    if (!c2_stream_c2d_write((uint16_t)(c2_runtime.images_offset
            + old_images * 32u), image_row, sizeof image_row)) goto rollback;
    for (i = 0; i < entries; ++i) {
        uint16_t at = (uint16_t)(meta_off + 24u + i * 16u);
        uint16_t first;
        uint8_t row[10]; uint8_t j;
        for (j = 0; j < sizeof entry; ++j)
            entry[j] = ext_disk_get((uint16_t)(256u + at + j));
        first = c2_u16(entry + 5);
        row[0] = (uint8_t)old_images; row[1] = 0;
        row[2] = (uint8_t)i; row[3] = (uint8_t)(i >> 8);
        row[4] = entry[3]; row[5] = entry[4];
        row[6] = (uint8_t)(old_res + first);
        row[7] = (uint8_t)((old_res + first) >> 8);
        row[8] = (uint8_t)c2_runtime.generation;
        row[9] = (uint8_t)(c2_runtime.generation >> 8);
        if (!c2_stream_c2d_write((uint16_t)(c2_runtime.entries_offset
                + (old_entries + i) * 10u), row, sizeof row)) goto rollback;
    }

    append = c2_runtime;
    append.image_count = new_images; append.entry_count = new_entries;
    append.resolution_count = new_res; append.c2_root_count = new_roots;
    append.image_first = old_images; append.entry_first = old_entries;
    append.resolution_first = old_res; append.root_first = old_roots;
    append.resolution_cursor = old_res; append.phase = 4u;
    append.finished = 0; append.error = 0;
    c2_pending_roots = new_roots; c2_decode_active = &append;
    if (!c2_decode_from(&append, 4u)) goto rollback;
    for (i = 0; i < sizeof new_header; ++i) new_header[i] = old_header[i];
    c2_header_counts(new_header, new_images, new_entries, new_res, new_roots);
    if (!c2_stream_c2d_write(0, new_header, sizeof new_header)) goto rollback;
    c2_runtime = append; c2_decode_active = &c2_runtime;
    c2_committed_roots = new_roots; c2_pending_roots = new_roots;
    if (!c2_publish_exports_from(old_entries)) goto rollback_committed;
    *main_ordinal = (uint16_t)(new_entries - 1u); return 1;

rollback_committed:
    c2_runtime = *before; c2_decode_active = &c2_runtime;
    c2_committed_roots = old_roots;
rollback:
    (void)c2_stream_c2d_write(0, old_header, sizeof old_header);
    c2_zero_plane((uint16_t)(before->images_offset + old_images * 32u), 32u);
    c2_zero_plane((uint16_t)(before->entries_offset + old_entries * 10u),
                  (uint16_t)(entries * 10u));
    c2_zero_plane((uint16_t)(before->resolutions_offset + old_res * 2u),
                  (uint16_t)(literals * 2u));
    c2_zero_plane((uint16_t)(before->roots_offset + old_roots * 2u),
                  (uint16_t)(roots * 2u));
    c2_pending_roots = old_roots; c2_decode_active = &c2_runtime;
    return 0;
}
#else

C2_APPEND_SECTION("envelope") uint8_t c2_append_envelope_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w || w->length < 88u || w->length > 8192u) return C2_STREAM_ERR_STATE;
    if (ext_disk_get(256u) != 'L' || ext_disk_get(257u) != '6'
        || ext_disk_get(258u) != '5' || ext_disk_get(259u) != 'S'
        || ext_disk_get(260u) != 4u || ext_disk_get(261u) != 32u
        || ext_disk_get(262u) != 32u || ext_disk_get(263u) != 1u
        || c2_stage_u16(8u) != 32u || c2_stage_u24(10u) != 64u
        || c2_stage_u24(13u) != w->length || c2_stage_u16(16u) != 32u
        || c2_stage_u32(22u) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID
        || c2_stage_u16(26u) != 1u || ext_disk_get(284u) || ext_disk_get(285u)
        || ext_disk_get(286u) || ext_disk_get(287u)) return C2_STREAM_ERR_C2I;
    for (i = 0; i < sizeof w->record; ++i)
        w->record[i] = ext_disk_get((uint16_t)(288u + i));
    if (w->record[30] != 1u || w->record[31] || w->record[0] != 'S'
        || w->record[1] != 'E' || w->record[2] != 'S' || w->record[3] != 'S')
        return C2_STREAM_ERR_C2I;
    w->code_off = (uint16_t)c2_stage_u24(40u); w->code_len = c2_stage_u16(43u);
    w->meta_off = (uint16_t)c2_stage_u24(45u); w->meta_len = c2_stage_u16(48u);
    if (w->code_off != 64u || !w->code_len
        || w->meta_off != (uint16_t)(w->code_off + w->code_len)
        || w->meta_len < 24u || (uint32_t)w->meta_off + w->meta_len != w->length)
        return C2_STREAM_ERR_C2I;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("crc") uint8_t c2_append_crc_phase(void *opaque) {
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    if (c2_stage_crc(32u, 32u) != c2_stage_u32(18u)
        || c2_stage_crc(w->code_off, w->code_len) != c2_stage_u32(50u)
        || c2_stage_crc(w->meta_off, w->meta_len) != c2_stage_u32(54u)
        || c2_stage_crc(w->code_off, (uint16_t)(w->code_len + w->meta_len))
            != c2_stage_u32(58u)) return C2_STREAM_ERR_C2I;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("metadata") uint8_t c2_append_metadata_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w) return C2_STREAM_ERR_STATE;
    for (i = 0; i < sizeof w->meta; ++i)
        w->meta[i] = ext_disk_get((uint16_t)(256u + w->meta_off + i));
    if (w->meta[0] != 'C' || w->meta[1] != '2' || w->meta[2] != 'I' || w->meta[3]
        || w->meta[4] != 2u || w->meta[5] != 24u || w->meta[6] != 16u
        || w->meta[7] != 8u || c2_u16(w->meta + 8) || c2_u16(w->meta + 22))
        return C2_STREAM_ERR_C2I;
    w->entries = c2_u16(w->meta + 10); w->literals = c2_u16(w->meta + 12);
    if (!w->entries || c2_u16(w->meta + 14) != 24u
        || c2_u16(w->meta + 16) != (uint16_t)(24u + w->entries * 16u)
        || c2_u16(w->meta + 18) != (uint16_t)(24u + w->entries * 16u
            + w->literals * 8u)
        || (uint16_t)((c2_u16(w->meta + 18) + c2_u16(w->meta + 20) + 1u) & ~1u)
            != w->meta_len) return C2_STREAM_ERR_C2I;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("capacity") uint8_t c2_append_capacity_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w) return C2_STREAM_ERR_STATE;
    w->roots = 0;
    for (i = 0; i < w->literals; ++i) {
        uint8_t kind = ext_disk_get((uint16_t)(256u + w->meta_off
            + c2_u16(w->meta + 16) + i * 8u));
        if (kind == 3u || kind == 7u) ++w->roots;
    }
    w->old_images = c2_runtime.image_count; w->old_entries = c2_runtime.entry_count;
    w->old_res = c2_runtime.resolution_count; w->old_roots = c2_runtime.c2_root_count;
    w->new_images = (uint16_t)(w->old_images + 1u);
    w->new_entries = (uint16_t)(w->old_entries + w->entries);
    w->new_res = (uint16_t)(w->old_res + w->literals);
    w->new_roots = (uint16_t)(w->old_roots + w->roots);
    if (w->new_images > 64u || w->new_entries > 2048u
        || w->new_res > 4096u || w->new_roots > 1536u) return C2_STREAM_ERR_C2D;
    w->attic = c2_attic_watermark();
    if (w->attic == 0xffffffffUL
        || w->attic + w->length > LISP65_C2_SESSION_BYTES) return C2_STREAM_ERR_STATE;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("stage") static void c2_append_stage_zero_plane(
                                             uint16_t at, uint16_t bytes) {
    static const uint8_t zeros[16] = {0};
    while (bytes) {
        uint16_t n = bytes > sizeof zeros ? sizeof zeros : bytes;
        (void)c2_stream_c2d_write(at, zeros, n);
        at = (uint16_t)(at + n); bytes = (uint16_t)(bytes - n);
    }
}

C2_APPEND_SECTION("stage") uint8_t c2_append_stage_phase(void *opaque) {
    c2_append_state *w = opaque; uint8_t readback[16]; uint16_t i;
    if (!w || !w->before) return C2_STREAM_ERR_STATE;
    c2_dma_copy(LISP65_EXT_DISK_FILE_PHYSICAL,
                LISP65_C2_SESSION_PHYSICAL + w->attic, w->length);
    for (i = 0; i < w->length; i = (uint16_t)(i + sizeof readback)) {
        uint16_t n = (uint16_t)(w->length - i), j;
        if (n > sizeof readback) n = sizeof readback;
        c2_dma_copy(LISP65_C2_SESSION_PHYSICAL + w->attic + i,
                    (uint32_t)(uint16_t)(uintptr_t)readback, n);
        for (j = 0; j < n; ++j)
            if (readback[j] != ext_disk_get((uint16_t)(256u + i + j)))
                return C2_STREAM_ERR_IO;
    }
    if (!c2_stream_c2d_read(0, w->old_header, sizeof w->old_header))
        return C2_STREAM_ERR_IO;
    *w->before = c2_runtime; w->staged = 1;
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.images_offset + w->old_images * 32u), 32u);
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.entries_offset + w->old_entries * 10u),
                  (uint16_t)(w->entries * 10u));
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.resolutions_offset + w->old_res * 2u),
                  (uint16_t)(w->literals * 2u));
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.roots_offset + w->old_roots * 2u),
                  (uint16_t)(w->roots * 2u));
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("image") uint8_t c2_append_image_phase(void *opaque) {
    c2_append_state *w = opaque; uint8_t row[32]; uint16_t i; uint32_t combined;
    if (!w || !w->staged) return C2_STREAM_ERR_STATE;
    for (i = 0; i < sizeof row; ++i) row[i] = 0;
    row[0] = 1u; row[2] = (uint8_t)(w->old_images - 6u);
    row[4] = (uint8_t)c2_runtime.generation; row[5] = (uint8_t)(c2_runtime.generation >> 8);
    row[6] = (uint8_t)w->old_entries; row[7] = (uint8_t)(w->old_entries >> 8);
    row[8] = (uint8_t)w->entries; row[9] = (uint8_t)(w->entries >> 8);
    row[10] = (uint8_t)w->old_res; row[11] = (uint8_t)(w->old_res >> 8);
    row[12] = (uint8_t)w->literals; row[13] = (uint8_t)(w->literals >> 8);
    row[14] = (uint8_t)w->old_roots; row[15] = (uint8_t)(w->old_roots >> 8);
    row[16] = (uint8_t)w->roots; row[17] = (uint8_t)(w->roots >> 8);
    combined = c2_stage_u32(58u);
    row[18] = (uint8_t)(w->attic + w->code_off);
    row[19] = (uint8_t)((w->attic + w->code_off) >> 8);
    row[20] = (uint8_t)((w->attic + w->code_off) >> 16);
    row[21] = (uint8_t)w->code_len; row[22] = (uint8_t)(w->code_len >> 8);
    row[23] = (uint8_t)(w->attic + w->meta_off);
    row[24] = (uint8_t)((w->attic + w->meta_off) >> 8);
    row[25] = (uint8_t)((w->attic + w->meta_off) >> 16);
    row[26] = (uint8_t)w->meta_len; row[27] = (uint8_t)(w->meta_len >> 8);
    row[28] = (uint8_t)combined; row[29] = (uint8_t)(combined >> 8);
    row[30] = (uint8_t)(combined >> 16); row[31] = (uint8_t)(combined >> 24);
    return c2_stream_c2d_write((uint16_t)(c2_runtime.images_offset
        + w->old_images * 32u), row, sizeof row) ? C2_STREAM_OK : C2_STREAM_ERR_IO;
}

C2_APPEND_SECTION("entries") uint8_t c2_append_entries_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w || !w->staged) return C2_STREAM_ERR_STATE;
    for (i = 0; i < w->entries; ++i) {
        uint16_t at = (uint16_t)(w->meta_off + 24u + i * 16u), first;
        uint8_t entry[16], row[10], j;
        for (j = 0; j < sizeof entry; ++j)
            entry[j] = ext_disk_get((uint16_t)(256u + at + j));
        first = c2_u16(entry + 5);
        row[0] = (uint8_t)w->old_images; row[1] = 0;
        row[2] = (uint8_t)i; row[3] = (uint8_t)(i >> 8);
        row[4] = entry[3]; row[5] = entry[4];
        row[6] = (uint8_t)(w->old_res + first);
        row[7] = (uint8_t)((w->old_res + first) >> 8);
        row[8] = (uint8_t)c2_runtime.generation;
        row[9] = (uint8_t)(c2_runtime.generation >> 8);
        if (!c2_stream_c2d_write((uint16_t)(c2_runtime.entries_offset
                + (w->old_entries + i) * 10u), row, sizeof row)) return C2_STREAM_ERR_IO;
    }
    w->append = c2_runtime;
    w->append.image_count = w->new_images; w->append.entry_count = w->new_entries;
    w->append.resolution_count = w->new_res; w->append.c2_root_count = w->new_roots;
    w->append.image_first = w->old_images; w->append.entry_first = w->old_entries;
    w->append.resolution_first = w->old_res; w->append.root_first = w->old_roots;
    w->append.resolution_cursor = w->old_res; w->append.phase = 4u;
    w->append.finished = 0; w->append.error = 0;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("header") uint8_t c2_append_header_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w || !w->append.finished) return C2_STREAM_ERR_STATE;
    for (i = 0; i < sizeof w->new_header; ++i) w->new_header[i] = w->old_header[i];
    c2_header_counts(w->new_header, w->new_images, w->new_entries,
                     w->new_res, w->new_roots);
    if (!c2_stream_c2d_write(0, w->new_header, sizeof w->new_header))
        return C2_STREAM_ERR_IO;
    c2_runtime = w->append; c2_decode_active = &c2_runtime;
    c2_committed_roots = w->new_roots; c2_pending_roots = w->new_roots;
    w->committed = 1; return C2_STREAM_OK;
}

C2_APPEND_SECTION("publish_names") uint8_t c2_append_publish_names_phase(void *opaque) {
    c2_append_state *w = opaque; uint8_t d[10], image[32], entry[16], named;
    uint16_t ordinal; char name[LISP65_SYMBOL_NAME_BUFFER];
    if (!w || !w->committed) return C2_STREAM_ERR_STATE;
    for (ordinal = w->old_entries; ordinal < c2_runtime.entry_count; ++ordinal) {
        if (!c2_entry_records(ordinal, d, image, entry)) return C2_STREAM_ERR_STATE;
        named = c2_export_name(image, entry, name);
        if (!named) return C2_STREAM_ERR_STATE;
        if (named == 1u && (c2_facade_intern(name) == NIL || mem_oom))
            return C2_STREAM_ERR_STATE;
    }
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("publish_cells") uint8_t c2_append_publish_cells_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint8_t d[10], image[32], entry[16], journal[4], named;
    uint16_t ordinal; obj symbol, old, published;
    char name[LISP65_SYMBOL_NAME_BUFFER];
    if (!w || !w->committed) return C2_STREAM_ERR_STATE;
    c2_journal_count = 0;
    for (ordinal = w->old_entries; ordinal < c2_runtime.entry_count; ++ordinal) {
        if (!c2_entry_records(ordinal, d, image, entry)) goto rollback;
        named = c2_export_name(image, entry, name);
        if (!named) goto rollback;
        if (named == 2u) continue;
        if (!sym_lookup(name, &symbol)) goto rollback;
        old = sym_function(symbol);
        if (entry[11] & 1u) {
            published = alloc(T_MACRO);
            if (published == NIL || mem_oom) goto rollback;
            cell_set_a(published, MK_BCODE(ordinal));
            cell_set_b(published, NIL);
        } else published = MK_BCODE(ordinal);
        journal[0] = (uint8_t)symbol;
        journal[1] = (uint8_t)((uint16_t)symbol >> 8);
        journal[2] = (uint8_t)old;
        journal[3] = (uint8_t)((uint16_t)old >> 8);
        if (!c2_stream_c2d_write((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + c2_journal_count * C2_EXPORT_JOURNAL_RECORD_BYTES),
                journal, sizeof journal)) goto rollback;
        ++c2_journal_count;
        set_sym_function(symbol, published);
    }
    c2_journal_count = 0;
    if (w->main_ordinal) *w->main_ordinal = (uint16_t)(w->new_entries - 1u);
    return C2_STREAM_OK;

rollback:
    return C2_STREAM_ERR_STATE;
}

static uint8_t c2_publish_exports_from(uint16_t first) {
    uint8_t ok;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.old_entries = first; c2aw.committed = 1; c2aw.staged = 0;
    c2aw.main_ordinal = 0; c2aw.rollback_rebuild_header = 0;
    ok = (uint8_t)(c2_overlay_call(LISP65_C2_APPEND_PUBLISH_NAMES_SLOT, &c2aw)
        && c2_overlay_call(LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw));
    if (!ok)
        (void)c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    return ok;
}

C2_APPEND_SECTION("rollback") static void c2_append_restore_exports(void) {
    uint8_t b[4];
    while (c2_journal_count) {
        --c2_journal_count;
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + c2_journal_count * C2_EXPORT_JOURNAL_RECORD_BYTES), b, sizeof b))
            continue;
        set_sym_function((obj)c2_u16(b), (obj)c2_u16(b + 2));
    }
}

C2_APPEND_SECTION("rollback") static void c2_append_rollback_zero_plane(
                                             uint16_t at, uint16_t bytes) {
    static const uint8_t zeros[16] = {0};
    while (bytes) {
        uint16_t n = bytes > sizeof zeros ? sizeof zeros : bytes;
        (void)c2_stream_c2d_write(at, zeros, n);
        at = (uint16_t)(at + n); bytes = (uint16_t)(bytes - n);
    }
}

C2_APPEND_SECTION("rollback") uint8_t c2_append_rollback_phase(void *opaque) {
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    c2_append_restore_exports();
    if (!w->staged) return C2_STREAM_OK;
    if (!w->before) return C2_STREAM_ERR_STATE;
    if (w->committed) {
        c2_runtime = *w->before; c2_decode_active = &c2_runtime;
        c2_committed_roots = w->old_roots;
    }
    if (w->rollback_rebuild_header) {
        if (!c2_stream_c2d_read(0, w->old_header, sizeof w->old_header))
            return C2_STREAM_ERR_IO;
        c2_header_counts(w->old_header, w->old_images, w->old_entries,
                         w->old_res, w->old_roots);
    }
    (void)c2_stream_c2d_write(0, w->old_header, sizeof w->old_header);
    c2_append_rollback_zero_plane(
                  (uint16_t)(w->before->images_offset + w->old_images * 32u), 32u);
    c2_append_rollback_zero_plane(
                  (uint16_t)(w->before->entries_offset + w->old_entries * 10u),
                  (uint16_t)(w->entries * 10u));
    c2_append_rollback_zero_plane(
                  (uint16_t)(w->before->resolutions_offset + w->old_res * 2u),
                  (uint16_t)(w->literals * 2u));
    c2_append_rollback_zero_plane(
                  (uint16_t)(w->before->roots_offset + w->old_roots * 2u),
                  (uint16_t)(w->roots * 2u));
    c2_pending_roots = w->old_roots; c2_decode_active = &c2_runtime;
    return C2_STREAM_OK;
}

static C2_KERNAL_RESIDENT uint8_t c2_append_begin(uint16_t length, c2_stream_context *before,
                               uint16_t *main_ordinal) {
    if (!c2_ready || !before || !main_ordinal) return 0;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.before = before; c2aw.main_ordinal = main_ordinal; c2aw.length = length;
    c2aw.staged = 0; c2aw.committed = 0; c2aw.rollback_rebuild_header = 0;
    if (!c2_overlay_call(LISP65_C2_APPEND_ENVELOPE_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_CRC_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_METADATA_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_CAPACITY_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_STAGE_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_IMAGE_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_ENTRIES_SLOT, &c2aw)) {
        (void)c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
        return 0;
    }
    c2_pending_roots = c2aw.new_roots; c2_decode_active = &c2aw.append;
    if (!c2_decode_from(&c2aw.append, 4u)
        || !c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_PUBLISH_NAMES_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw)) {
        (void)c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
        return 0;
    }
    return c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
}

#endif

static uint8_t c2_append_rollback(const c2_stream_context *before) {
    uint8_t ok;
    if (!before || !c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.before = (c2_stream_context *)before;
    c2aw.old_images = before->image_count; c2aw.old_entries = before->entry_count;
    c2aw.old_res = before->resolution_count; c2aw.old_roots = before->c2_root_count;
    c2aw.entries = (uint16_t)(c2_runtime.entry_count - before->entry_count);
    c2aw.literals = (uint16_t)(c2_runtime.resolution_count - before->resolution_count);
    c2aw.roots = (uint16_t)(c2_runtime.c2_root_count - before->c2_root_count);
    c2aw.staged = 1; c2aw.committed = 1; c2aw.rollback_rebuild_header = 1;
    ok = c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    return ok;
}

uint8_t c2_product_append_staged(uint16_t length) {
    c2_stream_context before; uint16_t main;
    return c2_append_begin(length, &before, &main);
}

obj c2_product_install(obj fnlist, obj definition_name) {
    c2_stream_context before; c2_emit_status emit; uint16_t length, main;
    uint8_t transient = (uint8_t)(definition_name == c2_facade_intern("t"));
    obj result;
    emit = c2_session_emit_reset();
    if (emit == C2_EMIT_OK)
        emit = c2_session_emit_add(fnlist,
            transient ? NIL : definition_name, 0u);
    if (emit == C2_EMIT_OK) emit = c2_session_emit_finalize(&length);
    if (emit != C2_EMIT_OK || !c2_append_begin(length, &before, &main)) {
        vm_status = VM_BADOPCODE; return NIL;
    }
    if (!transient)
        return definition_name != NIL ? definition_name : MK_BCODE(main);
    result = vm_run_dir((int)main, 0, 0);
    if (!c2_append_rollback(&before)) {
        vm_status = VM_BADOPCODE; return NIL;
    }
    return result;
}

#endif /* LISP65_C2_PRODUCT_CUT */
