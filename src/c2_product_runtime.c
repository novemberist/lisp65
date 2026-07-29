/* C2 product runtime integration.
 *
 * This file intentionally has no dependency on the historical container,
 * validator, commit path or directory arrays.  Physical Attic addresses are
 * represented as uint32_t DMA-domain values, never as C pointers.
 */
#include "c2_product_runtime.h"
#include "c2d_v6_entry.h"
#include <stddef.h>

#ifdef LISP65_C2_PRODUCT_CUT

#ifndef C2_STREAM_PRODUCT_V3
#define C2_STREAM_PRODUCT_V3 1
#endif
#include "c2-stream-v2-decoder.h"
#include "c2_c1_freezer_fixture.h"
#include "c2_product_decoder.h"
#include "c2_kernal_facade.h"
#include "c2_kernal_layout.h"
#include "c2_kernal_runtime.h"
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
#ifdef LISP65_C2_LITE_COLD_EVICTION
#define C2_EXPORT_PLAN_RECORD_BYTES 8u
#define C2_EXPORT_SCRATCH_RECORD_BYTES C2_EXPORT_PLAN_RECORD_BYTES
#else
#define C2_EXPORT_SCRATCH_RECORD_BYTES C2_EXPORT_JOURNAL_RECORD_BYTES
#endif
#ifdef LISP65_C2_NESTED_APPEND_V5
#define C2D_IMAGE_CAP 64u
#define C2D_ENTRY_CAP 2048u
#define C2D_RESOLUTION_CAP 4096u
#define C2D_ROOT_CAP 1536u
#define C2D_HANDLE_CAP 4096u
#define C2D_MAX_TRANSIENT_DEPTH 4u
#define C2D_UNWIND_BASE 50752u
#define C2D_UNWIND_BYTES 64u
#ifdef LISP65_C2_TWO_REGION_SESSION_STORE
#define C2_EXPORT_PLAN_LIMIT 48384u
#else
#define C2_EXPORT_PLAN_LIMIT C2D_UNWIND_BASE
#endif
#define C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES 64u
#define C2J_RESULT_NONE 0u
#define C2J_RESULT_ACTIVE 1u
/* The one co-resident rollback cutpoint.  NONE selects rollback preparation,
 * PREPARED selects the immediately following journal write, and ACTIVE makes
 * a replay fail closed.  The byte already belongs to the C2J transaction. */
#define C2J_RESULT_PREPARED 2u
#define C2_APPEND_FLAG_REBUILD 1u
#define C2_APPEND_FLAG_TRANSIENT 0x80u
#define C2_APPEND_BEGIN_OK 1u
static inline void c2_header_watermark(uint8_t header[48], uint16_t value);
#endif
#define C2_APPEND_SECTION(name) __attribute__((noinline, section(".lisp65_rt_c2append_" name)))
#define C2_APPEND_INLINE static __attribute__((always_inline)) inline
#ifdef __mos__
/* The target definition is the named, sized, ABI-gated assembler leaf in
 * rtov_crc_mem.s.  C2J bookends reuse it instead of materializing another
 * CRC implementation in the append overlays. */
uint16_t rtov_crc_mem(const uint8_t *p, uint16_t length);
#else
/* Host-only parity body for source and mutation fixtures that compile the
 * product runtime without the MOS leaf. */
C2_APPEND_INLINE uint16_t rtov_crc_mem(
        const uint8_t *p, uint16_t length) {
    uint16_t crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
    uint8_t bit;
    while (length--) {
        crc ^= (uint16_t)*p++ << 8;
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc & 0x8000u)
                ? (uint16_t)((crc << 1)
                    ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                : (uint16_t)(crc << 1);
    }
    return crc;
}
#endif
#ifdef LISP65_C2_KERNAL_UNMAP
#define C2_KERNAL_RESIDENT __attribute__((noinline, section(".lisp65_c2_kernal_window.c2_resident")))
#define C2_HANDLE_NORMALIZE(context, handle) \
    c2_facade_handle_normalize((context), (handle))
#else
#define C2_KERNAL_RESIDENT
#define C2_HANDLE_NORMALIZE(context, handle) \
    c2_product_handle_normalize((context), (handle))
#endif

/* C2-lite has no hot C2I reader.  Under the cold-eviction contract these
 * helpers are compiled only into their append consumers; the legacy product
 * keeps the externally visible/window-resident seams unchanged. */
#ifdef LISP65_C2_LITE_COLD_EVICTION
#define C2_COLD_SOURCE_FN C2_APPEND_INLINE
#define C2_COLD_ENTRY_FN C2_APPEND_INLINE
#else
#define C2_COLD_SOURCE_FN static C2_KERNAL_RESIDENT
#define C2_COLD_ENTRY_FN C2_KERNAL_RESIDENT
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
    union {
        struct {
            uint8_t old_header[48];
            uint8_t new_header[48];
        };
        /* During C2J recovery these first 64 bytes are the exact validated
         * journal snapshot.  The alternate view prevents llvm-mos from
         * manufacturing a resident .noinit static stack for a local copy. */
        uint8_t journal_snapshot[96];
    };
    uint8_t record[32];
    uint8_t meta[24];
    uint8_t staged;
    uint8_t committed;
    uint8_t rollback_rebuild_header;
} c2_append_state;

_Static_assert(sizeof(c2_append_state) <= LISP65_C2_INSTALL_TRACE_OFFSET,
               "C2 append state overlaps installer trace provenance");
#ifdef LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC
_Static_assert(sizeof(c2_append_state) <= LISP65_C2_FRAME_ATTRIBUTION_OFFSET,
               "C2 append state overlaps frame attribution results");
#endif
#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
_Static_assert(offsetof(c2_append_state, main_ordinal) == 2u,
               "journal-prepare leaf main-ordinal ABI drift");
_Static_assert(offsetof(c2_append_state, record) + 31u == 213u,
               "journal-prepare leaf C2J-result ABI drift");
#endif
#define c2aw (*(c2_append_state *)(void *)lisp65_c2_phase_scratch)

#ifdef LISP65_C2_NESTED_APPEND_V5
#define C2AW_TRANSIENT(w) ((w)->rollback_rebuild_header & C2_APPEND_FLAG_TRANSIENT)
#define C2AW_REBUILD(w) ((w)->rollback_rebuild_header & C2_APPEND_FLAG_REBUILD)
#define C2AW_FRONT_DEPTH(w) ((w)->record[0])
#define C2AW_FRONT_ENTRIES(w) c2_u16((w)->record + 2)
#define C2AW_FRONT_RESOLUTIONS(w) c2_u16((w)->record + 4)
#define C2AW_FRONT_ROOTS(w) c2_u16((w)->record + 6)
#define C2AW_FRONT_ATTIC(w) c2_u32((w)->record + 8)
#define C2AW_JOURNAL_RESULT(w) ((w)->record[31])
/* Bytes 25..26 are dead after the source-record CRC phase and before phase
 * scratch is released.  They carry the producer-bound CRC16 seal over the
 * complete 64-byte C2J record, including its format CRC32. */
#define C2AW_C2J_SEAL(w) c2_u16((w)->record + 25)
#define C2AW_C2J_SEAL_BYTES(w) ((w)->record + 25)
#ifdef LISP65_C2_LITE_COLD_EVICTION
#define C2AW_CHIP_CODE_BASE(w) c2_u16((w)->record + 28)
#endif
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
/* Split cutpoints reuse bytes that are otherwise idle between the named
 * phases.  Each consumer clears its marker, so skip and replay both fail
 * closed without adding resident state or carrying a pointer across loads. */
#define C2AW_RESERVE_MARK(w) ((w)->record[20])
#define C2AW_STAGE_MARK(w) ((w)->record[21])
#define C2AW_PLAN_MARK(w) ((w)->record[22])
#define C2AW_COMPLETION_MARK(w) ((w)->record[24])
#define C2_COMPLETION_ACTIVE_MARK 0xa1u
#define C2_COMPLETION_PUBLISH_MARK 0xa2u
#define C2_COMPLETION_ROLLBACK_MARK 0xa3u
#define C2_COMPLETION_CLEAR_MARK 0xa4u
#if defined(LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT) \
    || defined(LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT)
/* The source record is dead after the fused CRC/metadata phase.  Byte 23 is
 * therefore the zero-cost request byte shared by the two lifetime-disjoint
 * co-resident phase pairs. */
#define C2AW_FUSED_PHASE_MARK(w) ((w)->record[23])
#endif
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
#define C2AW_ROOTS_FRONTS_MARK(w) C2AW_FUSED_PHASE_MARK(w)
#define C2_ROOTS_REQUEST_MARK 0x72u
#define C2_FRONTS_REQUEST_MARK 0x66u
#endif
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
#define C2AW_PUBLISH_CLEAR_MARK(w) C2AW_FUSED_PHASE_MARK(w)
#define C2_PUBLISH_REQUEST_MARK 0x70u
#define C2_CLEAR_REQUEST_MARK 0x6au
#endif
#define C2_RESERVE_TRANSIENT_MARK 0x74u
#define C2_RESERVE_PERSISTENT_MARK 0x70u
#define C2_STAGE_COPY_MARK 0x53u
#define C2_EXPORT_SCAN_MARK 0xa7u
#define C2_EXPORT_PLAN_MARK 0x50u
#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET
#define C2_EXPORT_PUBLISH_MARK 0x51u
#endif
#endif
#ifdef LISP65_C2_RESIDENCY_TRIAGE
#define C2AW_ABORT_STATE(w) ((w)->meta[0])
#define C2AW_ABORT_START(w) ((w)->meta[1])
#define C2AW_ABORT_END(w) ((w)->meta[2])
#define C2AW_ABORT_DONE(w) ((w)->meta[3])
enum {
    C2_ABORT_PLAN_VALIDATE = 0u,
    C2_ABORT_PLAN_AFTER_VALIDATE,
    C2_ABORT_PLAN_AFTER_BARRIER,
    C2_ABORT_PLAN_AFTER_UNPUBLISH,
    C2_ABORT_PLAN_AFTER_CLEAR_WRITE,
    C2_ABORT_PLAN_AFTER_ROLLBACK,
    C2_ABORT_PLAN_AFTER_FRONTS,
    C2_ABORT_PLAN_AFTER_PREPARE,
    C2_ABORT_PLAN_AFTER_WRITE,
    C2_ABORT_PLAN_AFTER_ACTIVE
};
#endif
C2_APPEND_INLINE void c2_record_u16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
C2_APPEND_INLINE void c2_record_u32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16); p[3] = (uint8_t)(value >> 24);
}
#endif

#ifdef LISP65_C2_SLICED_APPEND
static uint8_t c2_publish_exports_from(uint16_t first);
#endif

C2_KERNAL_RESIDENT void c2_product_physical_copy(
        uint32_t source, uint32_t target, uint16_t length) {
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

#define c2_dma_copy c2_product_physical_copy

static uint16_t c2_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
static uint32_t c2_u24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}
static uint32_t c2_u32(const uint8_t *p) {
    return c2_u24(p) | (uint32_t)p[3] << 24;
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

#ifdef LISP65_C2_LITE_COLD_EVICTION
/* The first Session decoder phase and this guard share one transported
 * record.  Before READY the immutable boot context may start at image zero.
 * Afterwards the only admitted source is the active, staged Append
 * transaction, whose private Session span is bounded before any source DMA.
 * Reading c2aw directly avoids a second carried representation and therefore
 * needs no handoff byte between Append entries and phase 04. */
__attribute__((noinline, used, visibility("hidden"),
               section(".lisp65_rt_c2d_04")))
uint8_t c2_append_source_domain_guard(const c2_stream_context *c) {
    uint32_t base;
    if (!c) return 0;
    if (!c2_ready) return (uint8_t)!c->image_first;
    if (!c->image_first || c != &c2aw.append || c2_decode_active != c
        || !c2aw.staged || !c2aw.length) return 0;
    base = c2aw.attic;
    return (uint8_t)(base <= LISP65_C2_SESSION_BYTES
        && c2aw.length <= LISP65_C2_SESSION_BYTES - base);
}
#endif

/* Whole-phase decoder facade.  These helpers are immutable product-format
 * operations shared by several transported phases.  Housing one copy in the
 * owned window restores phase-granularity transport without removing any
 * format check from the proven decoder. */
C2_KERNAL_RESIDENT uint8_t c2_stream_product_image_read(
        c2_stream_context *c, uint16_t image, uint8_t out[20]) {
    uint8_t raw[32];
#ifdef LISP65_C2_LITE_COLD_EVICTION
    uint8_t source[32];
#endif
    uint32_t tag, code, meta;
    if (!c || !out || image >= c->image_count
        || !c2_stream_c2d_read((uint16_t)(c->images_offset + image * 32u),
                               raw, sizeof raw)) return 0;
    if (raw[0] >
#ifdef LISP65_C2_NESTED_APPEND_V5
            2u
#else
            1u
#endif
        || raw[1]
        || (raw[0] == 0u ? raw[2] != image
#ifdef LISP65_C2_NESTED_APPEND_V5
            : raw[0] == 2u ? raw[2] != (uint8_t)(63u - image)
#endif
            : raw[2] != (uint8_t)(image - 6u))
        || raw[3] || c2_u16(raw + 4) != c->generation) return 0;
    out[0] = (uint8_t)image; out[1] = raw[0];
    out[2] = raw[6]; out[3] = raw[7];
    out[4] = raw[8]; out[5] = raw[9];
    out[6] = raw[10]; out[7] = raw[11];
    out[8] = raw[12]; out[9] = raw[13];
#ifdef LISP65_C2_LITE_COLD_EVICTION
    /* The final v6 image contains execution coordinates only; its former
     * metadata locator is deliberately zero.  Cold decoding derives source
     * coordinates from the authenticated shelf record (static) or from the
     * still-private append transaction (session).  No post-READY consumer can
     * reconstruct either locator from the published C2D image. */
    if (raw[0] == 0u) {
        if (!c2_stream_shelf_read(32u + (uint32_t)raw[2] * 32u,
                                  source, sizeof source)
            || source[30] != 1u || source[31]
            || c2_u16(source + 11) != c2_u16(raw + 21)) return 0;
        tag = 0u; code = c2_u24(source + 8); meta = c2_u24(source + 13);
        out[18] = source[16]; out[19] = source[17];
    } else {
        if (c != &c2aw.append || !c2aw.staged
            || image < c2aw.append.image_first
            || image >= c2aw.append.image_count) return 0;
        tag = C2_SESSION_SOURCE_TAG;
        code = c2aw.attic + c2aw.code_off;
        meta = c2aw.attic + c2aw.meta_off;
        out[18] = (uint8_t)c2aw.meta_len;
        out[19] = (uint8_t)(c2aw.meta_len >> 8);
    }
    code |= tag; meta |= tag;
#else
    tag = raw[0] ? C2_SESSION_SOURCE_TAG : 0u;
    code = c2_u24(raw + 18) | tag;
    meta = c2_u24(raw + 23) | tag;
    out[18] = raw[26]; out[19] = raw[27];
#endif
    out[10] = (uint8_t)code; out[11] = (uint8_t)(code >> 8);
    out[12] = (uint8_t)(code >> 16);
    out[13] = (uint8_t)meta; out[14] = (uint8_t)(meta >> 8);
    out[15] = (uint8_t)(meta >> 16);
    out[16] = raw[21]; out[17] = raw[22];
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

/* Link-29 resolver, deliberately unchanged.  Full descriptor validation is
 * owned by the stage/decode path; this reader performs the proven resolution
 * and canonical-root lookup used by both stage 11 and hot materialization. */
#ifndef LISP65_C2_LITE_COLD_EVICTION
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
        if (word >= c2_pending_roots
            || !c2_stream_c2d_read((uint16_t)(c->roots_offset + word * 2u),
                                   b, 2u)) return 0;
        word = c2_u16(b);
        if (!word || word >= 0x8000u || (word & 1u)) return 0;
    }
    *value = word;
    return 1;
}
#endif

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
    c2_pending_roots =
#ifdef LISP65_C2_NESTED_APPEND_V5
        (c2_runtime.entry_first != C2D_HANDLE_CAP
         || c2_decode_active->image_first >= 60u) ? C2D_ROOT_CAP :
#endif
        root_count;
    /* This seam publishes the canonical root plane before the next
     * allocation.  The host proof deliberately collects at every checkpoint
     * as a stress schedule; making that proof schedule product semantics
     * forced 283 full collections during cold boot.  Natural allocator GCs
     * still see every previously published value through pending_roots. */
    return (uint8_t)!mem_oom;
}

C2_COLD_SOURCE_FN uint8_t c2_source_read(const uint8_t image[32], uint32_t relative,
                                         void *dst, uint16_t length) {
    uint32_t base;
    if (image[0] == 0u) base = LISP65_C2_SHELF_PHYSICAL;
    else if (image[0] == 1u
#ifdef LISP65_C2_NESTED_APPEND_V5
             || image[0] == 2u
#endif
             ) base = LISP65_C2_SESSION_PHYSICAL;
    else return 0;
    if (c2_u16(image + 4) != c2_runtime.generation) return 0;
    c2_dma_copy(base + relative, (uint32_t)(uint16_t)(uintptr_t)dst, length);
    return 1;
}

#ifdef LISP65_C2_NESTED_APPEND_V5
/* These are the complete non-contiguous transaction plans.  They stay as
 * named data so source and linked gates can compare and mutate the plan
 * itself rather than reverse-engineering a compiler's branch sequence. */
__attribute__((used, visibility("hidden")))
const uint8_t lisp65_c2_append_stage_plan[] = {
    LISP65_C2_APPEND_JOURNAL_WRITE_SLOT,
    LISP65_C2_APPEND_HEADER_SLOT,
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
    LISP65_C2_APPEND_STAGE_COPY_SLOT,
    LISP65_C2_APPEND_STAGE_PLANE_SLOT,
#else
    LISP65_C2_APPEND_STAGE_SLOT,
#endif
    LISP65_C2_APPEND_IMAGE_SLOT,
    LISP65_C2_APPEND_ENTRIES_SLOT,
    0u
};
/* The persistent post-decode path is non-contiguous too: the named header
 * commit is a mandatory station between resolution and publication.
 * Keeping the whole order as data makes omission (not merely bad ordering)
 * visible to the phase-plan gate. */
__attribute__((used, visibility("hidden")))
const uint8_t lisp65_c2_append_persistent_publish_plan[] = {
#ifdef LISP65_C2_LITE_COLD_EVICTION
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
    LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT,
    LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT,
    LISP65_C2_APPEND_HEADER_SLOT,
    LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT,
#else
    LISP65_C2_APPEND_PUBLISH_PLAN_SLOT,
    LISP65_C2_APPEND_HEADER_SLOT,
    LISP65_C2_APPEND_PUBLISH_NAMES_SLOT,
    LISP65_C2_APPEND_PUBLISH_CELLS_SLOT,
#endif
#else
    LISP65_C2_APPEND_HEADER_SLOT,
    LISP65_C2_APPEND_PUBLISH_NAMES_SLOT,
    LISP65_C2_APPEND_PUBLISH_CELLS_SLOT,
#endif
    0u
};
__attribute__((used, visibility("hidden")))
const uint8_t lisp65_c2_append_rollback_plan[] = {
    LISP65_C2_APPEND_HEADER_SLOT,
    LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT,
#ifdef LISP65_C2_TWO_REGION_SESSION_STORE
    LISP65_C2_APPEND_ROLLBACK_WIPE_PLANE_SLOT,
    LISP65_C2_APPEND_ROLLBACK_WIPE_CHIP_SLOT,
    LISP65_C2_APPEND_ROLLBACK_WIPE_ATTIC_SLOT,
#endif
    LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT,
    LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT,
    LISP65_C2_APPEND_HEADER_SLOT,
    0u
};
#endif

__attribute__((noinline, used))
uint8_t c2_facade_target_overlay_call_family(uint8_t family,
                                              uint16_t generation,
                                              uint8_t slot, void *context) {
    uint8_t status = LISP65_RUNTIME_OVERLAY_ENTRY_NOT_RUN;
    return (uint8_t)(vm_runtime_overlay_exec_family(
                         family, generation, slot, context, &status)
        == VM_RUNTIME_OVERLAY_OK && status == C2_STREAM_OK);
}

/* Hidden but non-static: the non-LTO plan walker is an ordinary linked caller
 * of this one generic Session seam. */
__attribute__((noinline, used, visibility("hidden")))
C2_KERNAL_RESIDENT uint8_t c2_overlay_call(
        uint8_t slot, void *context) {
    return c2_facade_overlay_call_family(
        LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
        c2_runtime.generation, slot, context);
}

#ifdef LISP65_C2_NESTED_APPEND_V5
/* Serial overlay phases are laid out in execution order.  One resident range
 * loop replaces duplicated call-site machinery without permitting an overlay
 * phase to load or call another overlay. */
static C2_KERNAL_RESIDENT uint8_t c2_overlay_call_range(
        uint8_t first, uint8_t last, void *context) {
    if (first > last) return 0;
    while (first <= last) {
        if (!c2_overlay_call(first, context)) return 0;
        ++first;
    }
    return 1;
}

/* Slot numbers are storage identities, not semantic order.  The non-LTO leaf
 * walks either zero-terminated named plan through the one generic Session
 * seam above.  No transported overlay calls another transported overlay. */
uint8_t c2_append_plan_walk(const uint8_t *plan, void *context);
#ifdef LISP65_C2_APPEND_PLAN_FACADE
uint8_t c2_facade_append_plan_walk(const uint8_t *plan, void *context);
#define C2_APPEND_PLAN_WALK c2_facade_append_plan_walk
#else
#define C2_APPEND_PLAN_WALK c2_append_plan_walk
#endif
#define c2_append_run_stage_plan(context) \
    C2_APPEND_PLAN_WALK(lisp65_c2_append_stage_plan, (context))
#define c2_append_run_persistent_publish_plan(context) \
    (C2AW_COMPLETION_MARK((context)) = C2_COMPLETION_PUBLISH_MARK, \
     C2AW_PUBLISH_CLEAR_MARK((context)) = C2_PUBLISH_REQUEST_MARK, \
     C2_APPEND_PLAN_WALK(lisp65_c2_append_persistent_publish_plan, (context)))

/* Rollback is requested from three resident sites.  Keep the one canonical
 * plan pointer and, for the co-resident terminal slice, its request marker in
 * one seam so LTO cannot reproduce that setup at every caller. */
static C2_KERNAL_RESIDENT uint8_t c2_append_run_rollback_plan(void *context) {
    c2_append_state *w = context;
    if (!w) return 0;
    C2AW_COMPLETION_MARK(w) = C2_COMPLETION_ROLLBACK_MARK;
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
    C2AW_PUBLISH_CLEAR_MARK(w) = C2_CLEAR_REQUEST_MARK;
#endif
    return C2_APPEND_PLAN_WALK(lisp65_c2_append_rollback_plan, context);
}

#endif

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
#ifdef LISP65_C2_LITE_BANK2_STAGING
            || !c2_facade_overlay_call_family(
                   LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u,
                   LISP65_C2_PHASE_03B_SLOT, stream)
#endif
#ifdef LISP65_C2_LITE_BANK3_STAGING
            || !c2_facade_overlay_call_family(
                   LISP65_RUNTIME_OVERLAY_FAMILY_BOOT, 0u,
                   LISP65_C2_BANK3_STAGE_SESSION_SLOT, stream)
#endif
            || !stream->generation
            || c2_facade_select_family(
                   LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
                   stream->generation)
               != VM_RUNTIME_OVERLAY_OK) return 0;
    }
    if (first <= 4u && !c2_overlay_call(LISP65_C2_PHASE_04_SLOT, stream)) return 0;
    if (first <= 5u
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
        && (!c2_overlay_call(LISP65_C2_PHASE_05A_SLOT, stream)
            || !c2_overlay_call(LISP65_C2_PHASE_05B_SLOT, stream))
#else
        && !c2_overlay_call(LISP65_C2_PHASE_05_SLOT, stream)
#endif
       ) return 0;
    if (first <= 6u
        && (!c2_overlay_call(LISP65_C2_PHASE_06A_SLOT, stream)
            || !c2_overlay_call(LISP65_C2_PHASE_06B_SLOT, stream))) return 0;
    if (first <= 7u && !c2_overlay_call(LISP65_C2_PHASE_07_SLOT, stream)) return 0;
    if (first <= 8u && !c2_overlay_call(LISP65_C2_PHASE_08_SLOT, stream)) return 0;
    if (first <= 9u && !c2_overlay_call(LISP65_C2_PHASE_09_SLOT, stream)) return 0;
    if (first <= 10u && !c2_overlay_call(LISP65_C2_PHASE_10_SLOT, stream)) return 0;
    if (first <= 11u
#ifdef LISP65_C2_PHASE11_SPLIT
        && (!c2_overlay_call(LISP65_C2_PHASE_11A_SLOT, stream)
            || !c2_overlay_call(LISP65_C2_PHASE_11B_SLOT, stream))
#else
        && !c2_overlay_call(LISP65_C2_PHASE_11_SLOT, stream)
#endif
       ) return 0;
    return (uint8_t)(first > 12u
        || c2_overlay_call(LISP65_C2_PHASE_12_SLOT, stream));
}

/* Link-29 record seam, deliberately unchanged apart from external linkage so
 * the Island materializer can reuse it. */
C2_COLD_ENTRY_FN uint8_t c2_entry_records(
        uint16_t ordinal, uint8_t directory[10],
        uint8_t image[32], uint8_t entry[16]) {
    uint8_t metadata_header[24]; uint16_t local, entries_offset;
    uint32_t metadata;
    if (!c2_ready
#ifdef LISP65_C2_NESTED_APPEND_V5
        || (ordinal = C2_HANDLE_NORMALIZE(&c2_runtime, ordinal)) == 0xffffu
#else
        || ordinal >= c2_runtime.entry_count
#endif
        || !c2_stream_c2d_read((uint16_t)(c2_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    if (
#ifndef LISP65_C2_NESTED_APPEND_V5
        directory[0] >= c2_runtime.image_count ||
#endif
        directory[1]
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
    if (!c2_ready || !IS_PTR(name) || cell_type(name) != T_STR) return 0u;
    length = str_len(name);
    if (!length || length > 8u) return 0u;
    for (image = 0; image < 6u && image < c2_runtime.image_count; ++image) {
        if (!c2_stream_shelf_read(32u + (uint32_t)image * 32u,
                                  record, sizeof record)) return 0u;
        for (i = 0; i < length && record[i] == str_byte(name, i); ++i) { }
        if (i == length && (length == 8u || record[length] == 0u))
            return 1u;
    }
    return 0u;
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
#ifndef LISP65_C2_DIRECT_HOT_REFILL
    c2_stream_materialize_context materialize;
#else
    uint8_t hot_count = 0;
#endif
    uint32_t source;
    if (!destination || !c2_entry_records(ordinal, d, image, entry)) return 0;
    code_length = c2_u16(entry + 3);
    if (relative > code_length || length > (uint16_t)(code_length - relative)) return 0;
    source = c2_u24(image + 18) + c2_u24(entry);
    if (!c2_source_read(image, source + relative, destination, length)) return 0;

    lit_end = (uint16_t)(7u + 2u * entry[7]);
    if (relative < lit_end && (uint16_t)(relative + length) > 7u
        && entry[7]) {
#ifndef LISP65_C2_DIRECT_HOT_REFILL
        materialize.stream = &c2_runtime;
        materialize.directory_ordinal = ordinal;
        materialize.hot_values = hot;
        materialize.hot_capacity = C2_MAX_HOT_LITERALS;
        materialize.hot_count = 0;
        if (!c2_overlay_call(LISP65_C2_PHASE_13_SLOT, &materialize)) return 0;
        if (materialize.hot_count != entry[7]) return 0;
#else
        if (c2_stream_product_materialize_entry(
                &c2_runtime, ordinal, hot, C2_MAX_HOT_LITERALS, &hot_count)
                != C2_STREAM_OK || hot_count != entry[7]) return 0;
#endif
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
    c2_decode_active = &c2_runtime;
    if (!c2_publish_exports_from(0)) {
        c2_ready = 0; return 0;
    }
    /* READY is the product commit marker.  The cold plan, header identity and
     * every export cell are complete before this single publication. */
    c2_ready = 1;
    return 1;
}

uint8_t c2_product_prepare_boot(void) {
    /* Invalidation and boot-family entry are one product operation.  The
     * runtime transport accepts BOOT only with the zero generation written
     * here; SESSION then latches the nonzero generation decoded by phase 0. */
    c2_ready = 0;
#ifdef LISP65_C2_NESTED_APPEND_V5
    {
        uint8_t header[48];
        /* Restage kills every high handle before the generation changes.
         * Stale physical records may survive a failed wipe, but are already
         * unreachable at this publish-last boundary. */
        if (c2_stream_c2d_read(0u, header, sizeof header)
            && header[0] == 'C' && header[1] == '2' && header[2] == 'D'
            && header[3] == 0u && header[4] ==
#ifdef LISP65_C2_LITE_COLD_EVICTION
                6u
#else
                5u
#endif
                ) {
            c2_header_watermark(header, C2D_HANDLE_CAP);
            if (!c2_stream_c2d_write(0u, header, sizeof header)) return 0;
        }
    }
#endif
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
#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET
C2_APPEND_SECTION("crc_metadata")
#else
C2_APPEND_SECTION("crc")
#endif
static uint32_t c2_stage_crc(uint16_t at, uint16_t bytes) {
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
#ifdef LISP65_C2_LITE_COLD_EVICTION
    /* C2-lite keeps no published session-source locator.  The closed staging
     * transaction owns this cold scratch from byte zero and releases it before
     * any generated code is callable. */
    return 0u;
#else
    uint16_t image; uint8_t row[32]; uint32_t high = 0, end;
    for (image = 6u; image < c2_runtime.image_count; ++image) {
        if (!c2_stream_c2d_read((uint16_t)(c2_runtime.images_offset
                + image * 32u), row, sizeof row) || row[0] != 1u) return 0xffffffffUL;
        end = c2_u24(row + 23) + c2_u16(row + 26);
        if (end > high) high = end;
    }
    return (high + 1u) & ~1UL;
#endif
}

#ifdef LISP65_C2_NESTED_APPEND_V5
/* Derive every high edge from the sole published header watermark and the
 * contiguous source-kind-2 image records.  No depth, Tail locator or Attic
 * watermark is maintained beside these records. */
C2_APPEND_INLINE uint8_t c2_transient_fronts(
        uint8_t *depth_out, uint16_t *entries_out,
        uint16_t *resolutions_out, uint16_t *roots_out,
        uint32_t *attic_out) {
    uint8_t header[48], row[32], depth = 0, slot;
    uint16_t entries = C2D_ENTRY_CAP, resolutions = C2D_RESOLUTION_CAP;
    uint16_t roots = C2D_ROOT_CAP, watermark;
    uint32_t attic = LISP65_C2_SESSION_BYTES;
    if (!c2_stream_c2d_read(0u, header, sizeof header)
        || header[4] !=
#ifdef LISP65_C2_LITE_COLD_EVICTION
            6u
#else
            5u
#endif
        || c2_u16(header + 10) != c2_runtime.generation)
        return 0;
    watermark = c2_u16(header + 8);
    if (watermark < C2D_ENTRY_CAP || watermark > C2D_HANDLE_CAP) return 0;
    for (depth = 0; depth < C2D_MAX_TRANSIENT_DEPTH; ++depth) {
        slot = (uint8_t)(C2D_IMAGE_CAP - 1u - depth);
        if (!c2_stream_c2d_read((uint16_t)(c2_runtime.images_offset
                + (uint16_t)slot * 32u), row, sizeof row)) return 0;
        if (row[0] != 2u) break;
        if (row[1] || row[2] != depth || row[3]
            || c2_u16(row + 4) != c2_runtime.generation
            || (uint16_t)(c2_u16(row + 6) + c2_u16(row + 8)) != entries
            || (uint16_t)(c2_u16(row + 10) + c2_u16(row + 12)) != resolutions
            || (uint16_t)(c2_u16(row + 14) + c2_u16(row + 16)) != roots
#ifndef LISP65_C2_LITE_COLD_EVICTION
            || c2_u24(row + 18) + c2_u16(row + 21) != c2_u24(row + 23)
            || c2_u24(row + 23) + c2_u16(row + 26) != attic)
#else
            || c2_u24(row + 23) || c2_u16(row + 26))
#endif
            return 0;
        entries = c2_u16(row + 6);
        resolutions = c2_u16(row + 10);
        roots = c2_u16(row + 14);
#ifndef LISP65_C2_LITE_COLD_EVICTION
        attic = c2_u24(row + 18);
#endif
    }
    if (watermark != (uint16_t)(entries + C2D_ENTRY_CAP)) return 0;
    *depth_out = depth; *entries_out = entries;
    *resolutions_out = resolutions; *roots_out = roots; *attic_out = attic;
    return 1;
}

#ifdef LISP65_C2_LITE_COLD_EVICTION
/* Derive both Bank-2 fronts from the one published entry directory.  The
 * returned interval is the only place a new image may be installed; no
 * separately maintained watermark can drift from the rows that make code
 * callable. */
C2_APPEND_INLINE uint8_t c2_lite_bank2_fronts(
        uint16_t transient_first, uint32_t *low_out, uint32_t *high_out) {
    uint8_t row[10]; uint16_t i; uint32_t low = 0u, high = 65536UL, end;
    if (!low_out || !high_out || transient_first > C2D_ENTRY_CAP) return 0u;
    for (i = 0; i < c2_runtime.entry_count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(c2_runtime.entries_offset
                + i * LISP65_C2D_V6_ENTRY_BYTES), row, sizeof row)
            || !c2_u16(row + 4)
            || c2_u16(row + 8) != c2_runtime.generation
            || (uint32_t)c2_u16(row + 2) + c2_u16(row + 4) > 65536UL)
            return 0u;
        end = (uint32_t)c2_u16(row + 2) + c2_u16(row + 4);
        if (end > low) low = end;
    }
    if (transient_first < C2D_ENTRY_CAP) {
        for (i = transient_first; i < C2D_ENTRY_CAP; ++i) {
            if (!c2_stream_c2d_read((uint16_t)(c2_runtime.entries_offset
                    + i * LISP65_C2D_V6_ENTRY_BYTES), row, sizeof row)
                || !c2_u16(row + 4)
                || c2_u16(row + 8) != c2_runtime.generation)
                return 0u;
            if ((uint32_t)c2_u16(row + 2) < high) high = c2_u16(row + 2);
        }
    }
    if (low > high) return 0u;
    *low_out = low; *high_out = high; return 1u;
}
#endif

C2_APPEND_INLINE void c2_header_watermark(uint8_t header[48], uint16_t value) {
    header[8] = (uint8_t)value; header[9] = (uint8_t)(value >> 8);
}
#endif
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
static C2_KERNAL_RESIDENT uint8_t c2_append_begin(uint16_t length,
                               c2_stream_context *before,
                               uint16_t *main_ordinal
#ifdef LISP65_C2_NESTED_APPEND_V5
                               , uint8_t transient
#endif
                               ) {
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
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_ENVELOPE_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_APPEND_ENVELOPE);
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

#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET
/* CRC and metadata are one strictly ordered cold transaction step.  Keeping
 * both halves in one transported section removes one catalog record and one
 * payload quantum; the resident serial driver still owns the only call. */
C2_APPEND_SECTION("crc_metadata")
uint8_t c2_append_crc_metadata_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_CRC_METADATA_SLOT);
    c2_append_state *w = opaque;
    uint16_t i;
    if (!w) return C2_STREAM_ERR_STATE;
    if (c2_stage_crc(32u, 32u) != c2_stage_u32(18u)
        || c2_stage_crc(w->code_off, w->code_len) != c2_stage_u32(50u)
        || c2_stage_crc(w->meta_off, w->meta_len) != c2_stage_u32(54u)
        || c2_stage_crc(w->code_off, (uint16_t)(w->code_len + w->meta_len))
            != c2_stage_u32(58u)) return C2_STREAM_ERR_C2I;
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
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
    /* Open the roots/fronts cutpoint only after both predecessor halves have
     * completed.  The envelope's byte 23 must never select an entry. */
    C2AW_ROOTS_FRONTS_MARK(w) = 0u;
#endif
    return C2_STREAM_OK;
}
#else
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
#endif

#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
#define C2_ROOTS_FRONTS_SECTION C2_APPEND_SECTION("roots_fronts")
#define C2_ROOTS_ENTRY static C2_ROOTS_FRONTS_SECTION
#define C2_FRONTS_ENTRY static C2_ROOTS_FRONTS_SECTION
#else
#define C2_ROOTS_ENTRY C2_APPEND_SECTION("roots")
#define C2_FRONTS_ENTRY C2_APPEND_SECTION("fronts")
#endif

C2_ROOTS_ENTRY uint8_t c2_append_roots_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w) return C2_STREAM_ERR_STATE;
    w->roots = 0;
    for (i = 0; i < w->literals; ++i) {
        uint8_t kind = ext_disk_get((uint16_t)(256u + w->meta_off
            + c2_u16(w->meta + 16) + i * 8u));
        if (kind == 3u || kind == 7u) ++w->roots;
    }
    return C2_STREAM_OK;
}

C2_FRONTS_ENTRY uint8_t c2_append_fronts_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint8_t depth; uint16_t high_entries, high_res, high_roots;
    uint32_t high_attic;
    if (!w) return C2_STREAM_ERR_STATE;
    if (!c2_transient_fronts(&depth, &high_entries, &high_res,
                             &high_roots, &high_attic)) return C2_STREAM_ERR_C2D;
    if (C2AW_TRANSIENT(w) && depth >= C2D_MAX_TRANSIENT_DEPTH) {
        LISP65_ERROR_EMISSION_MARK(LISP65_ERR_C2_NESTING_DEPTH);
        lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));
#ifdef __mos__
        /* The product evaluator owns an active REPL abort landing.  The host
         * fixture deliberately returns so it can inspect the postcondition. */
        __builtin_unreachable();
#else
        return C2_STREAM_ERR_C2D;
#endif
    }
    C2AW_FRONT_DEPTH(w) = depth;
    c2_record_u16(w->record + 2, high_entries);
    c2_record_u16(w->record + 4, high_res);
    c2_record_u16(w->record + 6, high_roots);
    c2_record_u32(w->record + 8, high_attic);
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
    /* The input record occupied these bytes during envelope validation.  No
     * later phase consumes those source fields, so fronts explicitly opens
     * the three marker lifetimes rather than assuming zeroed scratch. */
    C2AW_RESERVE_MARK(w) = 0u;
    C2AW_STAGE_MARK(w) = 0u;
    C2AW_PLAN_MARK(w) = 0u;
#endif
    return C2_STREAM_OK;
}

#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
/* One catalog record owns both entry bodies.  The resident serial driver
 * selects exactly one body per call through the dead source-record byte; a
 * skipped, replayed or unknown half fails before either body changes state. */
C2_ROOTS_FRONTS_SECTION
uint8_t c2_append_roots_fronts_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_ROOTS_FRONTS_SLOT);
    c2_append_state *w = opaque;
    uint8_t requested;
    uint8_t result;
    if (!w) return C2_STREAM_ERR_STATE;
    requested = C2AW_ROOTS_FRONTS_MARK(w);
    C2AW_ROOTS_FRONTS_MARK(w) = 0u;
    if (requested == C2_ROOTS_REQUEST_MARK)
        result = c2_append_roots_phase(opaque);
    else if (requested == C2_FRONTS_REQUEST_MARK)
        result = c2_append_fronts_phase(opaque);
    else
        return C2_STREAM_ERR_STATE;
    return result;
}
#undef C2_ROOTS_FRONTS_SECTION
#endif
#undef C2_ROOTS_ENTRY
#undef C2_FRONTS_ENTRY

#ifndef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
C2_APPEND_SECTION("reserve_transient")
uint8_t c2_append_reserve_transient_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint8_t depth; uint16_t high_entries, high_res, high_roots;
    uint32_t high_attic, low_attic;
#ifdef LISP65_C2_LITE_COLD_EVICTION
    uint32_t code_low, code_high;
#endif
    if (!w || !C2AW_TRANSIENT(w)) return C2_STREAM_ERR_STATE;
    depth = C2AW_FRONT_DEPTH(w);
    high_entries = C2AW_FRONT_ENTRIES(w);
    high_res = C2AW_FRONT_RESOLUTIONS(w);
    high_roots = C2AW_FRONT_ROOTS(w);
    high_attic = C2AW_FRONT_ATTIC(w);
    low_attic = c2_attic_watermark();
    if (w->entries > high_entries
        || w->literals > high_res || w->roots > high_roots
        || c2_runtime.entry_count + (C2D_ENTRY_CAP - high_entries)
            + w->entries > C2D_ENTRY_CAP
        || c2_runtime.resolution_count
            + (C2D_RESOLUTION_CAP - high_res) + w->literals
            > C2D_RESOLUTION_CAP
        || c2_runtime.c2_root_count + (C2D_ROOT_CAP - high_roots)
            + w->roots > C2D_ROOT_CAP
        || high_attic < w->length || low_attic == 0xffffffffUL
        || high_attic - w->length < low_attic)
        return C2_STREAM_ERR_C2D;
    w->old_images = depth;
    w->old_entries = high_entries;
    w->old_res = high_res; w->old_roots = high_roots;
    w->new_images = (uint16_t)(C2D_IMAGE_CAP - 1u - depth);
    w->new_entries = (uint16_t)(high_entries - w->entries);
    w->new_res = (uint16_t)(high_res - w->literals);
    w->new_roots = (uint16_t)(high_roots - w->roots);
    w->attic = high_attic - w->length;
#ifdef LISP65_C2_LITE_COLD_EVICTION
    if (!c2_lite_bank2_fronts(high_entries, &code_low, &code_high)
        || w->code_len > code_high || code_high - w->code_len < code_low)
        return C2_STREAM_ERR_C2D;
    c2_record_u16(w->record + 28, (uint16_t)(code_high - w->code_len));
#endif
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("reserve_persistent")
uint8_t c2_append_reserve_persistent_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint16_t high_entries, high_res, high_roots;
    uint32_t high_attic;
#ifdef LISP65_C2_LITE_COLD_EVICTION
    uint32_t code_low, code_high;
#endif
    if (!w || C2AW_TRANSIENT(w)) return C2_STREAM_ERR_STATE;
    high_entries = C2AW_FRONT_ENTRIES(w);
    high_res = C2AW_FRONT_RESOLUTIONS(w);
    high_roots = C2AW_FRONT_ROOTS(w);
    high_attic = C2AW_FRONT_ATTIC(w);
    w->old_images = c2_runtime.image_count;
    w->old_entries = c2_runtime.entry_count;
    w->old_res = c2_runtime.resolution_count;
    w->old_roots = c2_runtime.c2_root_count;
    w->new_images = (uint16_t)(w->old_images + 1u);
    w->new_entries = (uint16_t)(w->old_entries + w->entries);
    w->new_res = (uint16_t)(w->old_res + w->literals);
    w->new_roots = (uint16_t)(w->old_roots + w->roots);
    if (w->new_images > 64u || w->new_entries > high_entries
        || w->new_res > high_res || w->new_roots > high_roots)
        return C2_STREAM_ERR_C2D;
    w->attic = c2_attic_watermark();
    if (w->attic == 0xffffffffUL || w->attic + w->length > high_attic)
        return C2_STREAM_ERR_STATE;
#ifdef LISP65_C2_LITE_COLD_EVICTION
    if (!c2_lite_bank2_fronts(high_entries, &code_low, &code_high)
        || code_low + w->code_len > code_high)
        return C2_STREAM_ERR_C2D;
    c2_record_u16(w->record + 28, (uint16_t)code_low);
#endif
    return C2_STREAM_OK;
}
#else
/* Transient reservation first proves both disjoint directory fronts and the
 * cold-source range.  The following phase owns only the Bank-2 code edge.
 * The marker is the complete handoff: no added bytes and no live pointer. */
C2_APPEND_SECTION("reserve_transient_bounds")
uint8_t c2_append_reserve_transient_bounds_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_RESERVE_TRANSIENT_BOUNDS_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(
        LISP65_C2_FRAME_ATTR_RESERVE_TRANSIENT_BOUNDS);
    c2_append_state *w = opaque;
    uint8_t depth; uint16_t high_entries, high_res, high_roots;
    uint32_t high_attic, low_attic;
    if (!w || !C2AW_TRANSIENT(w) || C2AW_RESERVE_MARK(w))
        return C2_STREAM_ERR_STATE;
    depth = C2AW_FRONT_DEPTH(w);
    high_entries = C2AW_FRONT_ENTRIES(w);
    high_res = C2AW_FRONT_RESOLUTIONS(w);
    high_roots = C2AW_FRONT_ROOTS(w);
    high_attic = C2AW_FRONT_ATTIC(w);
    low_attic = c2_attic_watermark();
    if (w->entries > high_entries
        || w->literals > high_res || w->roots > high_roots
        || c2_runtime.entry_count + (C2D_ENTRY_CAP - high_entries)
            + w->entries > C2D_ENTRY_CAP
        || c2_runtime.resolution_count
            + (C2D_RESOLUTION_CAP - high_res) + w->literals
            > C2D_RESOLUTION_CAP
        || c2_runtime.c2_root_count + (C2D_ROOT_CAP - high_roots)
            + w->roots > C2D_ROOT_CAP
        || high_attic < w->length || low_attic == 0xffffffffUL
        || high_attic - w->length < low_attic)
        return C2_STREAM_ERR_C2D;
    w->old_images = depth;
    w->old_entries = high_entries;
    w->old_res = high_res; w->old_roots = high_roots;
    w->new_images = (uint16_t)(C2D_IMAGE_CAP - 1u - depth);
    w->new_entries = (uint16_t)(high_entries - w->entries);
    w->new_res = (uint16_t)(high_res - w->literals);
    w->new_roots = (uint16_t)(high_roots - w->roots);
    w->attic = high_attic - w->length;
    C2AW_RESERVE_MARK(w) = C2_RESERVE_TRANSIENT_MARK;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("reserve_transient_code")
uint8_t c2_append_reserve_transient_code_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_RESERVE_TRANSIENT_CODE_SLOT);
    c2_append_state *w = opaque; uint32_t code_low, code_high;
    if (!w || !C2AW_TRANSIENT(w)
        || C2AW_RESERVE_MARK(w) != C2_RESERVE_TRANSIENT_MARK)
        return C2_STREAM_ERR_STATE;
    if (!c2_lite_bank2_fronts(C2AW_FRONT_ENTRIES(w), &code_low, &code_high)
        || w->code_len > code_high || code_high - w->code_len < code_low)
        return C2_STREAM_ERR_C2D;
    c2_record_u16(w->record + 28, (uint16_t)(code_high - w->code_len));
    C2AW_RESERVE_MARK(w) = 0u;
    return C2_STREAM_OK;
}

/* Persistent counts and cold-source placement are independent of the Bank-2
 * execution edge.  Preserve that semantic boundary as a second marker-only
 * handoff rather than retaining temporary addresses across overlay loads. */
C2_APPEND_SECTION("reserve_persistent_bounds")
uint8_t c2_append_reserve_persistent_bounds_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_RESERVE_PERSISTENT_BOUNDS_SLOT);
    c2_append_state *w = opaque;
    uint16_t high_entries, high_res, high_roots; uint32_t high_attic;
    if (!w || C2AW_TRANSIENT(w) || C2AW_RESERVE_MARK(w))
        return C2_STREAM_ERR_STATE;
    high_entries = C2AW_FRONT_ENTRIES(w);
    high_res = C2AW_FRONT_RESOLUTIONS(w);
    high_roots = C2AW_FRONT_ROOTS(w);
    high_attic = C2AW_FRONT_ATTIC(w);
    w->old_images = c2_runtime.image_count;
    w->old_entries = c2_runtime.entry_count;
    w->old_res = c2_runtime.resolution_count;
    w->old_roots = c2_runtime.c2_root_count;
    w->new_images = (uint16_t)(w->old_images + 1u);
    w->new_entries = (uint16_t)(w->old_entries + w->entries);
    w->new_res = (uint16_t)(w->old_res + w->literals);
    w->new_roots = (uint16_t)(w->old_roots + w->roots);
    if (w->new_images > 64u || w->new_entries > high_entries
        || w->new_res > high_res || w->new_roots > high_roots)
        return C2_STREAM_ERR_C2D;
    w->attic = c2_attic_watermark();
    if (w->attic == 0xffffffffUL || w->attic + w->length > high_attic)
        return C2_STREAM_ERR_STATE;
    C2AW_RESERVE_MARK(w) = C2_RESERVE_PERSISTENT_MARK;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("reserve_persistent_code")
uint8_t c2_append_reserve_persistent_code_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT);
    c2_append_state *w = opaque; uint32_t code_low, code_high;
    if (!w || C2AW_TRANSIENT(w)
        || C2AW_RESERVE_MARK(w) != C2_RESERVE_PERSISTENT_MARK)
        return C2_STREAM_ERR_STATE;
    if (!c2_lite_bank2_fronts(C2AW_FRONT_ENTRIES(w), &code_low, &code_high)
        || code_low + w->code_len > code_high)
        return C2_STREAM_ERR_C2D;
    c2_record_u16(w->record + 28, (uint16_t)code_low);
    C2AW_RESERVE_MARK(w) = 0u;
    return C2_STREAM_OK;
}
#endif

C2_APPEND_INLINE uint32_t c2j_crc32(
                                             const uint8_t *bytes) {
    uint32_t crc = 0xffffffffUL; uint8_t i, bit;
    for (i = 0; i < 60u; ++i) {
        crc ^= bytes[i];
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc >> 1)
                ^ (0xedb88320UL & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}

/* One transported cold body owns every poison/readback/timeout loop.  The
 * producer phases submit ordered writes only.  Reading the independently
 * content-proven C2J after those jobs is the transaction-data fence; ACTIVE
 * and CLEAR use the same machinery as independent journal bookends. */
C2_APPEND_INLINE uint8_t c2_completion_bytes_equal(
        const uint8_t *expected, const uint8_t *observed, uint16_t length) {
    uint16_t i;
    for (i = 0; i < length; ++i)
        if (observed[i] != expected[i]) return 0u;
    return 1u;
}

C2_APPEND_INLINE uint8_t c2_completion_c2j_matches(
        const c2_append_state *w, const uint8_t b[64]) {
#ifdef LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE
    uint16_t observed_crc;
    if (!w) return 0u;
    observed_crc = rtov_crc_mem(b, C2D_UNWIND_BYTES);
    C2_C1_COMPLETION_WITNESS16(
        LISP65_C2_C1_COMPLETION_OBSERVED_CRC_ADDRESS, observed_crc);
    C2_C1_COMPLETION_WITNESS16(
        LISP65_C2_C1_COMPLETION_EXPECTED_CRC_ADDRESS,
        C2AW_C2J_SEAL(w));
    return (uint8_t)(observed_crc == C2AW_C2J_SEAL(w));
#else
    return (uint8_t)(w
        && rtov_crc_mem(b, C2D_UNWIND_BYTES) == C2AW_C2J_SEAL(w));
#endif
}

/* Completion has exactly two content domains.  The target implementation is
 * the named, sized, non-LTO leaf in c2_completion_mode_length.s: each call
 * rematerializes one of two constants from A, so no optimizer may turn the
 * source-level derivation back into live length state across the reader. */
#ifdef __mos__
uint8_t c2_completion_mode_length(uint8_t mode);
#else
/* Host-only parity body for the completion contract and mutation fixtures. */
C2_APPEND_INLINE uint8_t c2_completion_mode_length(uint8_t mode) {
    if (mode == C2_COMPLETION_PUBLISH_MARK)
        return (uint8_t)sizeof c2aw.new_header;
    if (mode == C2_COMPLETION_ACTIVE_MARK
        || mode == C2_COMPLETION_ROLLBACK_MARK
        || mode == C2_COMPLETION_CLEAR_MARK)
        return C2D_UNWIND_BYTES;
    return 0u;
}
#endif

C2_APPEND_SECTION("header")
static uint8_t c2_completion_poll(c2_append_state *w, uint8_t mode,
                                  const uint8_t *expected) {
    uint8_t observed[64], attempt_length, i, reader_ok;
#ifdef __mos__
    uint16_t start = c2_kernal_frame_count_inline();
#else
    uint16_t attempts = 0u;
#endif
    C2_C1_COMPLETION_WITNESS8(
        LISP65_C2_C1_COMPLETION_STAGE_ADDRESS, 5u);
    if (!w || !c2_completion_mode_length(mode)) return 0u;
    attempt_length = c2_completion_mode_length(mode);
    for (i = 0; i < attempt_length; ++i)
        observed[i] = expected ? (uint8_t)(expected[i] ^ 0xffu) : 0xa5u;
    attempt_length = c2_completion_mode_length(mode);
    reader_ok = c2_stream_c2d_read(
        mode == C2_COMPLETION_PUBLISH_MARK ? 0u : C2D_UNWIND_BASE,
        observed, attempt_length);
    C2_C1_COMPLETION_WITNESS8(
        LISP65_C2_C1_COMPLETION_STAGE_ADDRESS,
        reader_ok ? 6u : 0xe6u);
    if (!reader_ok) return 0u;
    do {
        attempt_length = c2_completion_mode_length(mode);
        if (mode == C2_COMPLETION_CLEAR_MARK) {
            for (i = 0; i < attempt_length && !observed[i]; ++i) { }
            if (i == attempt_length) return 1u;
        } else if (mode == C2_COMPLETION_PUBLISH_MARK && expected) {
            if (c2_completion_bytes_equal(
                    expected, observed, attempt_length))
                return 1u;
        } else if (c2_completion_c2j_matches(w, observed)) {
            return 1u;
        }
#ifdef __mos__
    } while ((uint16_t)(c2_kernal_frame_count_inline() - start)
             < C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES);
#else
    } while (++attempts < C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES);
#endif
    C2_C1_COMPLETION_WITNESS8(
        LISP65_C2_C1_COMPLETION_STAGE_ADDRESS, 8u);
    return 0u;
}

#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
#define C2_PUBLISH_CLEAR_SECTION C2_APPEND_SECTION("publish_clear")
#define C2_JOURNAL_CLEAR_ENTRY static C2_PUBLISH_CLEAR_SECTION
#else
#define C2_JOURNAL_CLEAR_ENTRY C2_APPEND_SECTION("journal_clear")
#endif
C2_JOURNAL_CLEAR_ENTRY
uint8_t c2_append_journal_clear_phase(void *opaque) {
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_JOURNAL_CLEAR);
    c2_append_state *w = opaque;
    uint8_t *b;
    uint16_t i, count;
    if (!w) return C2_STREAM_ERR_STATE;
    b = w->journal_snapshot;
    count = c2_u16(w->meta + 22);
    if (count > C2D_ENTRY_CAP
        || (uint32_t)C2_EXPORT_JOURNAL_BASE
            + (uint32_t)count * C2_EXPORT_SCRATCH_RECORD_BYTES
            > C2D_UNWIND_BASE)
        return C2_STREAM_ERR_STATE;
    for (i = 0; i < C2D_UNWIND_BYTES; ++i) b[i] = 0;
    /* Submit every cleanup write in order and C2J CLEAR last.  The common
     * cold boundary phase proves the final zero bookend before bookkeeping
     * or phase scratch can be reused. */
    for (i = 0; i < count; ++i)
        if (!c2_stream_c2d_write(
                (uint16_t)(C2_EXPORT_JOURNAL_BASE
                    + i * C2_EXPORT_SCRATCH_RECORD_BYTES),
                b, C2_EXPORT_SCRATCH_RECORD_BYTES))
            return C2_STREAM_ERR_IO;
    if (!c2_stream_c2d_write(C2D_UNWIND_BASE, b, C2D_UNWIND_BYTES))
        return C2_STREAM_ERR_IO;
    C2AW_COMPLETION_MARK(w) = C2_COMPLETION_CLEAR_MARK;
    return C2_STREAM_OK;
}
#undef C2_JOURNAL_CLEAR_ENTRY

#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
#define C2_JOURNAL_PREPARE_SECTION C2_APPEND_SECTION("journal_prepare")
#define C2_JOURNAL_WRITE_ENTRY C2_JOURNAL_PREPARE_SECTION
#else
#define C2_JOURNAL_WRITE_ENTRY C2_APPEND_SECTION("journal_write")
#endif
C2_JOURNAL_WRITE_ENTRY
uint8_t c2_append_journal_write_phase(void *opaque) {
#ifndef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_JOURNAL_WRITE_SLOT);
#endif
    c2_append_state *w = opaque; uint8_t *b, i; uint32_t crc;
#ifndef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
    if (!w) return C2_STREAM_ERR_STATE;
#endif
    b = w->journal_snapshot;
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_NONE;
    for (i = 0; i < C2D_UNWIND_BYTES; ++i) b[i] = 0;
    b[0] = 'C'; b[1] = '2'; b[2] = 'J'; b[3] = 0u;
    b[4] = 1u; b[5] = 1u;
    b[6] = C2AW_TRANSIENT(w) ? C2_APPEND_FLAG_TRANSIENT : 0u;
    b[7] = c2_journal_count;
    c2_record_u16(b + 8, c2_runtime.generation);
    c2_record_u16(b + 10, w->old_images);
    c2_record_u16(b + 12, w->old_entries);
    c2_record_u16(b + 14, w->old_res);
    c2_record_u16(b + 16, w->old_roots);
    c2_record_u16(b + 18, w->new_images);
    c2_record_u16(b + 20, w->new_entries);
    c2_record_u16(b + 22, w->new_res);
    c2_record_u16(b + 24, w->new_roots);
    c2_record_u16(b + 26, w->entries);
    c2_record_u16(b + 28, w->literals);
    c2_record_u16(b + 30, w->roots);
    c2_record_u32(b + 32, w->attic);
    c2_record_u16(b + 36, w->length);
    c2_record_u16(b + 38, (uint16_t)(C2AW_TRANSIENT(w)
        ? w->old_entries + C2D_ENTRY_CAP : C2D_HANDLE_CAP));
    crc = c2j_crc32(b); c2_record_u32(b + 60, crc);
    c2_record_u16(C2AW_C2J_SEAL_BYTES(w),
                  rtov_crc_mem(b, C2D_UNWIND_BYTES));
    if (!c2_stream_c2d_write(C2D_UNWIND_BASE, b, C2D_UNWIND_BYTES))
        return C2_STREAM_ERR_IO;
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_PREPARED;
    C2AW_COMPLETION_MARK(w) = C2_COMPLETION_ACTIVE_MARK;
    return C2_STREAM_OK;
}
#undef C2_JOURNAL_WRITE_ENTRY

C2_APPEND_SECTION("journal_validate")
uint8_t c2_append_journal_validate_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT);
    c2_append_state *w = opaque; uint8_t *b; uint8_t i; uint32_t crc;
    if (!w) return C2_STREAM_ERR_STATE;
    b = w->journal_snapshot;
    if (!c2_stream_c2d_read(C2D_UNWIND_BASE, b, C2D_UNWIND_BYTES))
        return C2_STREAM_ERR_IO;
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_NONE;
    for (i = 0; i < C2D_UNWIND_BYTES && !b[i]; ++i) { }
    if (i == C2D_UNWIND_BYTES) return C2_STREAM_OK;
    crc = c2j_crc32(b);
    if (b[0] != 'C' || b[1] != '2' || b[2] != 'J' || b[3]
        || b[4] != 1u || b[5] != 1u
        || (b[6] & ~C2_APPEND_FLAG_TRANSIENT) || b[7] > 63u
        || c2_u16(b + 8) != c2_runtime.generation
        || c2_u32(b + 60) != crc
        || c2_u16(b + 10) > C2D_IMAGE_CAP
        || c2_u16(b + 12) > C2D_ENTRY_CAP
        || c2_u16(b + 14) > C2D_RESOLUTION_CAP
        || c2_u16(b + 16) > C2D_ROOT_CAP
        || c2_u16(b + 18) > C2D_IMAGE_CAP
        || c2_u16(b + 20) > C2D_ENTRY_CAP
        || c2_u16(b + 22) > C2D_RESOLUTION_CAP
        || c2_u16(b + 24) > C2D_ROOT_CAP
        || !c2_u16(b + 26) || !c2_u16(b + 36)
        || c2_u32(b + 32) + c2_u16(b + 36) > LISP65_C2_SESSION_BYTES
        || c2_u16(b + 38) < C2D_ENTRY_CAP
        || c2_u16(b + 38) > C2D_HANDLE_CAP) {
        c2_ready = 0; return C2_STREAM_ERR_C2D;
    }
    c2_record_u16(C2AW_C2J_SEAL_BYTES(w),
                  rtov_crc_mem(b, C2D_UNWIND_BYTES));
    /* `b` already is the exact snapshot in exclusive phase scratch.
     * Reconstruction must neither copy it to resident state nor reread a
     * mutable Bank-5 journal. */
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("journal_reconstruct")
uint8_t c2_append_journal_reconstruct_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT);
    c2_append_state *w = &c2aw; uint8_t transient;
    if (!opaque) return C2_STREAM_ERR_STATE;
    if (C2AW_JOURNAL_RESULT(w) == C2J_RESULT_NONE) return C2_STREAM_OK;
    if (C2AW_JOURNAL_RESULT(w) != C2J_RESULT_ACTIVE)
        return C2_STREAM_ERR_C2D;
    transient = (uint8_t)(w->journal_snapshot[6]
                          & C2_APPEND_FLAG_TRANSIENT);
    if (transient
        ? (c2_u16(w->journal_snapshot + 10) >= C2D_MAX_TRANSIENT_DEPTH
           || c2_u16(w->journal_snapshot + 18)
                != (uint16_t)(C2D_IMAGE_CAP - 1u
                    - c2_u16(w->journal_snapshot + 10))
           || (uint16_t)(c2_u16(w->journal_snapshot + 20)
                         + c2_u16(w->journal_snapshot + 26))
                != c2_u16(w->journal_snapshot + 12)
           || (uint16_t)(c2_u16(w->journal_snapshot + 22)
                         + c2_u16(w->journal_snapshot + 28))
                != c2_u16(w->journal_snapshot + 14)
           || (uint16_t)(c2_u16(w->journal_snapshot + 24)
                         + c2_u16(w->journal_snapshot + 30))
                != c2_u16(w->journal_snapshot + 16)
           || c2_u16(w->journal_snapshot + 38)
                != (uint16_t)(c2_u16(w->journal_snapshot + 12)
                              + C2D_ENTRY_CAP))
        : (c2_u16(w->journal_snapshot + 10) < 6u
           || c2_u16(w->journal_snapshot + 18)
                != (uint16_t)(c2_u16(w->journal_snapshot + 10) + 1u)
           || c2_u16(w->journal_snapshot + 20)
                != (uint16_t)(c2_u16(w->journal_snapshot + 12)
                              + c2_u16(w->journal_snapshot + 26))
           || c2_u16(w->journal_snapshot + 22)
                != (uint16_t)(c2_u16(w->journal_snapshot + 14)
                              + c2_u16(w->journal_snapshot + 28))
           || c2_u16(w->journal_snapshot + 24)
                != (uint16_t)(c2_u16(w->journal_snapshot + 16)
                              + c2_u16(w->journal_snapshot + 30))
           || c2_u16(w->journal_snapshot + 38) != C2D_HANDLE_CAP)) {
        c2_ready = 0; return C2_STREAM_ERR_C2D;
    }
    w->old_images = c2_u16(w->journal_snapshot + 10);
    w->old_entries = c2_u16(w->journal_snapshot + 12);
    w->old_res = c2_u16(w->journal_snapshot + 14);
    w->old_roots = c2_u16(w->journal_snapshot + 16);
    w->new_images = c2_u16(w->journal_snapshot + 18);
    w->new_entries = c2_u16(w->journal_snapshot + 20);
    w->new_res = c2_u16(w->journal_snapshot + 22);
    w->new_roots = c2_u16(w->journal_snapshot + 24);
    w->entries = c2_u16(w->journal_snapshot + 26);
    w->literals = c2_u16(w->journal_snapshot + 28);
    w->roots = c2_u16(w->journal_snapshot + 30);
    w->attic = c2_u32(w->journal_snapshot + 32);
    w->length = c2_u16(w->journal_snapshot + 36);
    c2_journal_count = w->journal_snapshot[7];
    w->rollback_rebuild_header = w->journal_snapshot[6];
    if (!C2AW_TRANSIENT(w)) w->rollback_rebuild_header |= C2_APPEND_FLAG_REBUILD;
    /* A non-local abort cannot retain the dead caller's `before` pointer.
     * Reconstruct the persistent predecessor context inside phase scratch. */
    if (!C2AW_TRANSIENT(w)) {
        w->append.shelf_bytes = c2_runtime.shelf_bytes;
        w->append.catalog_crc32 = c2_runtime.catalog_crc32;
        w->append.c2d_bytes = c2_runtime.c2d_bytes;
        w->append.generation = c2_runtime.generation;
        w->append.image_count = w->old_images;
        w->append.entry_count = w->old_entries;
        w->append.resolution_count = w->old_res;
        w->append.images_offset = c2_runtime.images_offset;
        w->append.entries_offset = c2_runtime.entries_offset;
        w->append.resolutions_offset = c2_runtime.resolutions_offset;
        w->append.roots_offset = c2_runtime.roots_offset;
        w->append.image_cursor = w->old_roots;
        w->append.entry_cursor = c2_runtime.entry_cursor;
        w->append.resolution_cursor = c2_runtime.resolution_cursor;
        w->append.pair_depth_max = c2_runtime.pair_depth_max;
        w->append.image_first = c2_runtime.image_first;
        w->append.entry_first = c2_runtime.entry_first;
        w->append.resolution_first = c2_runtime.resolution_first;
        w->append.root_first = c2_runtime.root_first;
        w->append.phase = c2_runtime.phase;
        w->append.finished = c2_runtime.finished;
        w->append.error = c2_runtime.error;
        w->append.reserved = c2_runtime.reserved;
        w->before = &w->append;
    } else w->before = 0;
    w->staged = 1u; w->committed = 1u;
    return C2_STREAM_OK;
}

#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
#define C2_ROLLBACK_PREPARE_ENTRY C2_JOURNAL_PREPARE_SECTION
#else
#define C2_ROLLBACK_PREPARE_ENTRY C2_APPEND_SECTION("rollback_prepare")
#endif
C2_ROLLBACK_PREPARE_ENTRY
uint8_t c2_append_rollback_prepare_phase(void *opaque) {
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_ROLLBACK_PREPARE);
#ifndef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT);
#endif
    c2_append_state *w = opaque; uint8_t depth, row[32];
#ifndef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
    if (!w) return C2_STREAM_ERR_STATE;
#endif
    depth = C2AW_FRONT_DEPTH(w);
    if (depth > C2D_MAX_TRANSIENT_DEPTH) return C2_STREAM_ERR_C2D;
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_NONE;
    if (!depth) return C2_STREAM_OK;
    if (!c2_stream_c2d_read((uint16_t)(c2_runtime.images_offset
            + (C2D_IMAGE_CAP - depth) * 32u), row, sizeof row))
        return C2_STREAM_ERR_IO;
    w->before = &c2_runtime;
    w->old_images = (uint16_t)(depth - 1u);
    w->new_images = (uint16_t)(C2D_IMAGE_CAP - depth);
    w->new_entries = c2_u16(row + 6); w->entries = c2_u16(row + 8);
    w->old_entries = (uint16_t)(w->new_entries + w->entries);
    w->new_res = c2_u16(row + 10); w->literals = c2_u16(row + 12);
    w->old_res = (uint16_t)(w->new_res + w->literals);
    w->new_roots = c2_u16(row + 14); w->roots = c2_u16(row + 16);
    w->old_roots = (uint16_t)(w->new_roots + w->roots);
#ifdef LISP65_C2_LITE_COLD_EVICTION
    /* Published v6 images retain no source locator.  Rollback restores the
     * handle/code fronts; unreachable cold scratch and Bank-2 bytes need no
     * post-READY source reconstruction or wipe. */
    w->attic = 0u; w->length = 0u;
#else
    w->attic = c2_u24(row + 18);
    w->length = (uint16_t)(c2_u24(row + 23) + c2_u16(row + 26)
                           - w->attic);
#endif
    w->staged = 1; w->committed = 1;
    w->rollback_rebuild_header = C2_APPEND_FLAG_TRANSIENT;
#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_PREPARED;
#else
    C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE;
#endif
    return C2_STREAM_OK;
}
#undef C2_ROLLBACK_PREPARE_ENTRY

#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
/* The named, sized assembler leaf c2_journal_prepare_select.s owns the sole
 * physical entry.  It consumes the same target-ABI fields asserted above and
 * tail-jumps to one of these two C semantic bodies. */
#undef C2_JOURNAL_PREPARE_SECTION
#endif
#else
C2_APPEND_SECTION("capacity") uint8_t c2_append_capacity_phase(void *opaque) {
    c2_append_state *w = opaque; uint16_t i;
    if (!w) return C2_STREAM_ERR_STATE;
    w->roots = 0;
    for (i = 0; i < w->literals; ++i) {
        uint8_t kind = ext_disk_get((uint16_t)(256u + w->meta_off
            + c2_u16(w->meta + 16) + i * 8u));
        if (kind == 3u || kind == 7u) ++w->roots;
    }
    w->old_images = c2_runtime.image_count;
    w->old_entries = c2_runtime.entry_count;
    w->old_res = c2_runtime.resolution_count;
    w->old_roots = c2_runtime.c2_root_count;
    w->new_images = (uint16_t)(w->old_images + 1u);
    w->new_entries = (uint16_t)(w->old_entries + w->entries);
    w->new_res = (uint16_t)(w->old_res + w->literals);
    w->new_roots = (uint16_t)(w->old_roots + w->roots);
    if (w->new_images > 64u || w->new_entries > 2048u
        || w->new_res > 4096u || w->new_roots > 1536u)
        return C2_STREAM_ERR_C2D;
    w->attic = c2_attic_watermark();
    if (w->attic == 0xffffffffUL
        || w->attic + w->length > LISP65_C2_SESSION_BYTES)
        return C2_STREAM_ERR_STATE;
    return C2_STREAM_OK;
}
#endif

#ifndef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
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
    c2_append_state *w = opaque;
    uint8_t expected[16], readback[16];
    uint16_t i;
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
#ifdef LISP65_C2_LITE_COLD_EVICTION
    /* The verified C2I code body becomes the one Bank-2 execution image.  The
     * source is ordinary staging RAM here, so the chip-to-chip DMA premise is
     * the already hardware-proved immediate-completion case. */
    for (i = 0; i < w->code_len; i = (uint16_t)(i + sizeof readback)) {
        uint16_t n = (uint16_t)(w->code_len - i), j;
        if (n > sizeof readback) n = sizeof readback;
        for (j = 0; j < n; ++j)
            expected[j] =
                ext_disk_get((uint16_t)(256u + w->code_off + i + j));
        vm_ext_write(expected, n, 2u,
                     (uint16_t)(C2AW_CHIP_CODE_BASE(w) + i));
    }
#endif
    if (!c2_stream_c2d_read(0, w->old_header, sizeof w->old_header))
        return C2_STREAM_ERR_IO;
    *w->before = c2_runtime; w->staged = 1;
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.images_offset
#ifdef LISP65_C2_NESTED_APPEND_V5
                    + (C2AW_TRANSIENT(w) ? w->new_images : w->old_images) * 32u
#else
                    + w->old_images * 32u
#endif
                    ), 32u);
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.entries_offset
#ifdef LISP65_C2_NESTED_APPEND_V5
                    + (C2AW_TRANSIENT(w) ? w->new_entries : w->old_entries) * 10u
#else
                    + w->old_entries * 10u
#endif
                    ),
                  (uint16_t)(w->entries * 10u));
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.resolutions_offset
#ifdef LISP65_C2_NESTED_APPEND_V5
                    + (C2AW_TRANSIENT(w) ? w->new_res : w->old_res) * 2u
#else
                    + w->old_res * 2u
#endif
                    ),
                  (uint16_t)(w->literals * 2u));
    c2_append_stage_zero_plane(
                  (uint16_t)(c2_runtime.roots_offset
#ifdef LISP65_C2_NESTED_APPEND_V5
                    + (C2AW_TRANSIENT(w) ? w->new_roots : w->old_roots) * 2u
#else
                    + w->old_roots * 2u
#endif
                    ),
                  (uint16_t)(w->roots * 2u));
    return C2_STREAM_OK;
}
#else
/* Transport/verify and plane preparation are separate observable operations.
 * The first phase proves every copied byte and publishes only a marker.  The
 * second snapshots the predecessor and clears the mutable suffix. */
C2_APPEND_SECTION("stage_copy")
uint8_t c2_append_stage_copy_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_STAGE_COPY_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_STAGE_COPY);
    c2_append_state *w = opaque;
    uint8_t expected[16], readback[16];
    uint16_t i;
    if (!w || !w->before || C2AW_STAGE_MARK(w))
        return C2_STREAM_ERR_STATE;
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
    for (i = 0; i < w->code_len; i = (uint16_t)(i + sizeof readback)) {
        uint16_t n = (uint16_t)(w->code_len - i), j;
        if (n > sizeof readback) n = sizeof readback;
        for (j = 0; j < n; ++j)
            expected[j] =
                ext_disk_get((uint16_t)(256u + w->code_off + i + j));
        vm_ext_write(expected, n, 2u,
                     (uint16_t)(C2AW_CHIP_CODE_BASE(w) + i));
    }
    C2AW_STAGE_MARK(w) = C2_STAGE_COPY_MARK;
    return C2_STREAM_OK;
}

C2_APPEND_INLINE void c2_append_stage_plane_zero(uint16_t at,
                                                  uint16_t bytes) {
    static const uint8_t zeros[16] = {0};
    while (bytes) {
        uint16_t n = bytes > sizeof zeros ? sizeof zeros : bytes;
        (void)c2_stream_c2d_write(at, zeros, n);
        at = (uint16_t)(at + n); bytes = (uint16_t)(bytes - n);
    }
}

C2_APPEND_SECTION("stage_plane")
uint8_t c2_append_stage_plane_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_STAGE_PLANE_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_STAGE_PLANE);
    c2_append_state *w = opaque;
    if (!w || !w->before || C2AW_STAGE_MARK(w) != C2_STAGE_COPY_MARK)
        return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read(0, w->old_header, sizeof w->old_header))
        return C2_STREAM_ERR_IO;
    *w->before = c2_runtime; w->staged = 1;
    c2_append_stage_plane_zero(
                  (uint16_t)(c2_runtime.images_offset
                    + (C2AW_TRANSIENT(w) ? w->new_images : w->old_images) * 32u),
                  32u);
    c2_append_stage_plane_zero(
                  (uint16_t)(c2_runtime.entries_offset
                    + (C2AW_TRANSIENT(w) ? w->new_entries : w->old_entries) * 10u),
                  (uint16_t)(w->entries * 10u));
    c2_append_stage_plane_zero(
                  (uint16_t)(c2_runtime.resolutions_offset
                    + (C2AW_TRANSIENT(w) ? w->new_res : w->old_res) * 2u),
                  (uint16_t)(w->literals * 2u));
    c2_append_stage_plane_zero(
                  (uint16_t)(c2_runtime.roots_offset
                    + (C2AW_TRANSIENT(w) ? w->new_roots : w->old_roots) * 2u),
                  (uint16_t)(w->roots * 2u));
    C2AW_STAGE_MARK(w) = 0u;
    return C2_STREAM_OK;
}
#endif

C2_APPEND_SECTION("image") uint8_t c2_append_image_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_IMAGE_SLOT);
    c2_append_state *w = opaque; uint8_t row[32]; uint16_t i; uint32_t combined;
    if (!w || !w->staged) return C2_STREAM_ERR_STATE;
    for (i = 0; i < sizeof row; ++i) row[i] = 0;
    row[0] =
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? 2u :
#endif
        1u;
    row[2] =
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? (uint8_t)w->old_images :
#endif
        (uint8_t)(w->old_images - 6u);
    row[4] = (uint8_t)c2_runtime.generation; row[5] = (uint8_t)(c2_runtime.generation >> 8);
    row[6] = (uint8_t)(
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? w->new_entries :
#endif
        w->old_entries);
    row[7] = (uint8_t)((
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? w->new_entries :
#endif
        w->old_entries) >> 8);
    row[8] = (uint8_t)w->entries; row[9] = (uint8_t)(w->entries >> 8);
    row[10] = (uint8_t)(
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? w->new_res :
#endif
        w->old_res);
    row[11] = (uint8_t)((
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? w->new_res :
#endif
        w->old_res) >> 8);
    row[12] = (uint8_t)w->literals; row[13] = (uint8_t)(w->literals >> 8);
    row[14] = (uint8_t)(
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? w->new_roots :
#endif
        w->old_roots);
    row[15] = (uint8_t)((
#ifdef LISP65_C2_NESTED_APPEND_V5
        C2AW_TRANSIENT(w) ? w->new_roots :
#endif
        w->old_roots) >> 8);
    row[16] = (uint8_t)w->roots; row[17] = (uint8_t)(w->roots >> 8);
    combined = c2_stage_u32(58u);
    row[18] = (uint8_t)(
#ifdef LISP65_C2_LITE_COLD_EVICTION
        C2AW_CHIP_CODE_BASE(w)
#else
        w->attic + w->code_off
#endif
        );
    row[19] = (uint8_t)((
#ifdef LISP65_C2_LITE_COLD_EVICTION
        (uint32_t)C2AW_CHIP_CODE_BASE(w)
#else
        w->attic + w->code_off
#endif
        ) >> 8);
    row[20] =
#ifdef LISP65_C2_LITE_COLD_EVICTION
        0u;
#else
        (uint8_t)((w->attic + w->code_off) >> 16);
#endif
    row[21] = (uint8_t)w->code_len; row[22] = (uint8_t)(w->code_len >> 8);
#ifdef LISP65_C2_LITE_COLD_EVICTION
    /* Source coordinates are transaction-private and never published. */
    row[23] = 0u; row[24] = 0u; row[25] = 0u;
    row[26] = 0u; row[27] = 0u;
#else
    row[23] = (uint8_t)(w->attic + w->meta_off);
    row[24] = (uint8_t)((w->attic + w->meta_off) >> 8);
    row[25] = (uint8_t)((w->attic + w->meta_off) >> 16);
    row[26] = (uint8_t)w->meta_len; row[27] = (uint8_t)(w->meta_len >> 8);
#endif
    row[28] = (uint8_t)combined; row[29] = (uint8_t)(combined >> 8);
    row[30] = (uint8_t)(combined >> 16); row[31] = (uint8_t)(combined >> 24);
    return c2_stream_c2d_write((uint16_t)(c2_runtime.images_offset
        + (
#ifdef LISP65_C2_NESTED_APPEND_V5
           C2AW_TRANSIENT(w) ? w->new_images :
#endif
           w->old_images) * 32u), row, sizeof row)
        ? C2_STREAM_OK : C2_STREAM_ERR_IO;
}

C2_APPEND_SECTION("entries") uint8_t c2_append_entries_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_ENTRIES_SLOT);
    c2_append_state *w = opaque; uint16_t i;
    if (!w || !w->staged) return C2_STREAM_ERR_STATE;
    for (i = 0; i < w->entries; ++i) {
        uint16_t at = (uint16_t)(w->meta_off + 24u + i * 16u), first;
        uint8_t entry[16], row[10], j;
        for (j = 0; j < sizeof entry; ++j)
            entry[j] = ext_disk_get((uint16_t)(256u + at + j));
        first = c2_u16(entry + 5);
#ifdef LISP65_C2_LITE_COLD_EVICTION
        if (c2_u24(entry) > 0xffffUL
            || (uint32_t)C2AW_CHIP_CODE_BASE(w) + c2_u24(entry) > 0xffffUL
            || !c2d_v6_emit_entry_row(
                row,
                (uint8_t)(
#ifdef LISP65_C2_NESTED_APPEND_V5
                    C2AW_TRANSIENT(w) ? w->new_images :
#endif
                    w->old_images),
                entry[7],
                (uint16_t)(C2AW_CHIP_CODE_BASE(w) + (uint16_t)c2_u24(entry)),
                c2_u16(entry + 3),
                (uint16_t)((
#ifdef LISP65_C2_NESTED_APPEND_V5
                    C2AW_TRANSIENT(w) ? w->new_res :
#endif
                    w->old_res) + first),
                c2_runtime.generation))
            return C2_STREAM_ERR_ENTRY;
#else
        row[0] = (uint8_t)(
#ifdef LISP65_C2_NESTED_APPEND_V5
            C2AW_TRANSIENT(w) ? w->new_images :
#endif
            w->old_images); row[1] = 0;
        row[2] = (uint8_t)i; row[3] = (uint8_t)(i >> 8);
        row[4] = entry[3]; row[5] = entry[4];
        row[6] = (uint8_t)((
#ifdef LISP65_C2_NESTED_APPEND_V5
            C2AW_TRANSIENT(w) ? w->new_res :
#endif
            w->old_res) + first);
        row[7] = (uint8_t)(((
#ifdef LISP65_C2_NESTED_APPEND_V5
            C2AW_TRANSIENT(w) ? w->new_res :
#endif
            w->old_res) + first) >> 8);
        row[8] = (uint8_t)c2_runtime.generation;
        row[9] = (uint8_t)(c2_runtime.generation >> 8);
#endif
        if (!c2_stream_c2d_write((uint16_t)(c2_runtime.entries_offset
                + ((
#ifdef LISP65_C2_NESTED_APPEND_V5
                    C2AW_TRANSIENT(w) ? w->new_entries :
#endif
                    w->old_entries) + i) * 10u), row, sizeof row))
            return C2_STREAM_ERR_IO;
    }
    w->append = c2_runtime;
#ifdef LISP65_C2_NESTED_APPEND_V5
    if (C2AW_TRANSIENT(w)) {
        w->append.image_count = (uint16_t)(w->new_images + 1u);
        w->append.entry_count = (uint16_t)(w->new_entries + w->entries);
        w->append.resolution_count = (uint16_t)(w->new_res + w->literals);
        w->append.c2_root_count = (uint16_t)(w->new_roots + w->roots);
        w->append.image_first = w->new_images;
        w->append.entry_first = w->new_entries;
        w->append.resolution_first = w->new_res;
        w->append.root_first = w->new_roots;
        w->append.resolution_cursor = w->new_res;
    } else
#endif
    {
        w->append.image_count = w->new_images;
        w->append.entry_count = w->new_entries;
        w->append.resolution_count = w->new_res;
        w->append.c2_root_count = w->new_roots;
        w->append.image_first = w->old_images;
        w->append.entry_first = w->old_entries;
        w->append.resolution_first = w->old_res;
        w->append.root_first = w->old_roots;
        w->append.resolution_cursor = w->old_res;
    }
    w->append.phase = 4u;
    w->append.finished = 0; w->append.error = 0;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("header") uint8_t c2_append_header_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_HEADER_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_APPEND_HEADER);
    c2_append_state *w = opaque; uint8_t mode; uint16_t i;
    if (!w) return C2_STREAM_ERR_STATE;
    mode = C2AW_COMPLETION_MARK(w);
    if (mode == C2_COMPLETION_ACTIVE_MARK) {
        if (C2AW_JOURNAL_RESULT(w) != C2J_RESULT_PREPARED
            || !c2_completion_poll(w, mode, 0))
            return C2_STREAM_ERR_IO;
        C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE;
        C2AW_COMPLETION_MARK(w) = 0u;
        C2_C1_FREEZER_HOLD(1);
        return C2_STREAM_OK;
    }
    if (mode == C2_COMPLETION_ROLLBACK_MARK) {
        if ((C2AW_JOURNAL_RESULT(w) != C2J_RESULT_ACTIVE
             && C2AW_JOURNAL_RESULT(w) != C2J_RESULT_PREPARED)
            || !c2_completion_poll(w, mode, 0))
            return C2_STREAM_ERR_IO;
        C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE;
        C2AW_COMPLETION_MARK(w) = 0u;
        return C2_STREAM_OK;
    }
    if (mode == C2_COMPLETION_CLEAR_MARK) {
        if (!c2_completion_poll(w, mode, 0))
            return C2_STREAM_ERR_IO;
        C2AW_JOURNAL_RESULT(w) = C2J_RESULT_NONE;
        c2_record_u16(C2AW_C2J_SEAL_BYTES(w), 0u);
        c2_journal_count = 0u;
        c2_record_u16(w->meta + 22, 0u);
        C2AW_COMPLETION_MARK(w) = 0u;
        return C2_STREAM_OK;
    }
    if (mode != C2_COMPLETION_PUBLISH_MARK
        || C2AW_JOURNAL_RESULT(w) != C2J_RESULT_ACTIVE
        || !w->append.finished)
        return C2_STREAM_ERR_STATE;
    if (!c2_completion_poll(w, C2_COMPLETION_ROLLBACK_MARK, 0))
        return C2_STREAM_ERR_IO;
    C2_C1_FREEZER_HOLD(2);
    for (i = 0; i < sizeof w->new_header; ++i) w->new_header[i] = w->old_header[i];
#ifdef LISP65_C2_NESTED_APPEND_V5
    if (C2AW_TRANSIENT(w)) {
        c2_header_watermark(w->new_header,
                            (uint16_t)(w->new_entries + C2D_ENTRY_CAP));
    } else
#endif
    {
    c2_header_counts(w->new_header, w->new_images, w->new_entries,
                     w->new_res, w->new_roots);
    }
    /* This is the final ordered Bank-5 write before publication.  Its
     * independent target proof is therefore also the completion fence for
     * every image/entry/resolution/root write submitted by earlier phases. */
    if (!c2_stream_c2d_write(0u, w->new_header, sizeof w->new_header)
        || !c2_completion_poll(
            w, C2_COMPLETION_PUBLISH_MARK,
            w->new_header))
        return C2_STREAM_ERR_IO;
#ifdef LISP65_C2_NESTED_APPEND_V5
    if (C2AW_TRANSIENT(w)) {
        c2_runtime.entry_first = (uint16_t)(w->new_entries + C2D_ENTRY_CAP);
        c2_decode_active = &c2_runtime; c2_pending_roots = C2D_ROOT_CAP;
    } else {
        uint16_t watermark = c2_u16(w->new_header + 8);
        c2_runtime = w->append; c2_runtime.entry_first = watermark;
        c2_decode_active = &c2_runtime;
        c2_committed_roots = w->new_roots;
        c2_pending_roots = watermark == C2D_HANDLE_CAP
            ? w->new_roots : C2D_ROOT_CAP;
    }
#else
    c2_runtime = w->append; c2_decode_active = &c2_runtime;
    c2_committed_roots = w->new_roots; c2_pending_roots = w->new_roots;
#endif
    w->committed = 1;
    C2AW_COMPLETION_MARK(w) = 0u;
    return C2_STREAM_OK;
}

#ifdef LISP65_C2_LITE_COLD_EVICTION
/* C2-lite publication captures every cold C2I fact once, before exports are
 * touched.  The temporary eight-byte rows occupy the otherwise idle journal
 * tail and are compacted in place to the established four-byte rollback rows
 * by publish_cells.  Forward compaction cannot overwrite an unread plan row. */
#ifndef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
C2_APPEND_SECTION("publish_plan")
uint8_t c2_append_publish_plan_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint8_t d[10], image[20], h[24], entry[16], row[8], size[2];
    uint16_t ordinal, base, local, strings, bytes, name, length, symbol;
    uint16_t count = 0; uint32_t metadata, at;
    if (!w || !w->append.finished || (w->staged && w->committed))
        return C2_STREAM_ERR_STATE;
    for (ordinal = w->old_entries; ordinal < w->append.entry_count; ++ordinal) {
        if (!c2_stream_c2d_read((uint16_t)(w->append.entries_offset
                + ordinal * LISP65_C2D_V6_ENTRY_BYTES), d, sizeof d)
            || d[0] >= w->append.image_count || d[1] > C2_MAX_HOT_LITERALS
            || c2_u16(d + 8) != w->append.generation
            || !c2_stream_product_image_read(&w->append, d[0], image))
            return C2_STREAM_ERR_STATE;
        base = c2_u16(image + 2);
        if (ordinal < base
            || (local = (uint16_t)(ordinal - base)) >= c2_u16(image + 4))
            return C2_STREAM_ERR_STATE;
        metadata = c2_u24(image + 13);
        if (!c2_stream_shelf_read(metadata, h, sizeof h)
            || !c2_stream_shelf_read(metadata + c2_u16(h + 14)
                + (uint32_t)local * 16u, entry, sizeof entry))
            return C2_STREAM_ERR_STATE;
        name = c2_u16(entry + 8);
        if (name == 0xffffu) continue;
        strings = c2_u16(h + 18); bytes = c2_u16(h + 20);
        if (name > bytes || (uint16_t)(bytes - name) < 2u
            || count >= C2D_ENTRY_CAP) return C2_STREAM_ERR_STATE;
        at = metadata + strings + name;
        if (!c2_stream_shelf_read(at, size, sizeof size)
            || !(length = c2_u16(size)) || length > LISP65_SYMBOL_NAME_MAX
            || length > (uint16_t)(bytes - name - 2u)
            || !c2_stream_name_value(8u, at + 2u, length, &symbol))
            return C2_STREAM_ERR_STATE;
        c2_record_u16(row, symbol);
        c2_record_u16(row + 2, (uint16_t)sym_function((obj)symbol));
        c2_record_u16(row + 4, (uint16_t)(ordinal
            | ((entry[11] & 1u) ? 0x8000u : 0u)));
        row[6] = 0u; row[7] = 0u;
        if ((uint32_t)C2_EXPORT_JOURNAL_BASE
                + (uint32_t)(count + 1u) * C2_EXPORT_PLAN_RECORD_BYTES
                > C2_EXPORT_PLAN_LIMIT
            || !c2_stream_c2d_write((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + count * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
        ++count;
    }
    c2_record_u16(w->meta + 22, count);
    return C2_STREAM_OK;
}
#else
/* The scan phase records only cold, source-derived coordinates.  The resolve
 * phase consumes those rows, interns names and overwrites each row with its
 * source-free publication form.  Header publication cannot occur between the
 * two slots, and the marker rejects skip or replay. */
C2_APPEND_SECTION("publish_plan_scan")
uint8_t c2_append_publish_plan_scan_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT);
    c2_append_state *w = opaque;
    uint8_t d[10], image[20], h[24], entry[16], row[8];
    uint16_t ordinal, base, local, strings, bytes, name, count = 0;
    uint32_t metadata, at;
    if (!w || !w->append.finished || (w->staged && w->committed)
        || C2AW_PLAN_MARK(w)) return C2_STREAM_ERR_STATE;
    for (ordinal = w->old_entries; ordinal < w->append.entry_count; ++ordinal) {
        if (!c2_stream_c2d_read((uint16_t)(w->append.entries_offset
                + ordinal * LISP65_C2D_V6_ENTRY_BYTES), d, sizeof d)
            || d[0] >= w->append.image_count || d[1] > C2_MAX_HOT_LITERALS
            || c2_u16(d + 8) != w->append.generation
            || !c2_stream_product_image_read(&w->append, d[0], image))
            return C2_STREAM_ERR_STATE;
        base = c2_u16(image + 2);
        if (ordinal < base
            || (local = (uint16_t)(ordinal - base)) >= c2_u16(image + 4))
            return C2_STREAM_ERR_STATE;
        metadata = c2_u24(image + 13);
        if (!c2_stream_shelf_read(metadata, h, sizeof h)
            || !c2_stream_shelf_read(metadata + c2_u16(h + 14)
                + (uint32_t)local * 16u, entry, sizeof entry))
            return C2_STREAM_ERR_STATE;
        name = c2_u16(entry + 8);
        if (name == 0xffffu) continue;
        strings = c2_u16(h + 18); bytes = c2_u16(h + 20);
        if (name > bytes || (uint16_t)(bytes - name) < 2u
            || count >= C2D_ENTRY_CAP) return C2_STREAM_ERR_STATE;
        at = metadata + strings + name;
        if (at > 0xffffffUL) return C2_STREAM_ERR_STATE;
        row[0] = (uint8_t)at; row[1] = (uint8_t)(at >> 8);
        row[2] = (uint8_t)(at >> 16);
        c2_record_u16(row + 3, (uint16_t)(bytes - name));
        c2_record_u16(row + 5, (uint16_t)(ordinal
            | ((entry[11] & 1u) ? 0x8000u : 0u)));
        row[7] = C2_EXPORT_SCAN_MARK;
        if ((uint32_t)C2_EXPORT_JOURNAL_BASE
                + (uint32_t)(count + 1u) * C2_EXPORT_PLAN_RECORD_BYTES
                > C2_EXPORT_PLAN_LIMIT
            || !c2_stream_c2d_write((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + count * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
        ++count;
    }
    c2_record_u16(w->meta + 22, count);
    C2AW_PLAN_MARK(w) = C2_EXPORT_PLAN_MARK;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("publish_plan_resolve")
uint8_t c2_append_publish_plan_resolve_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT);
    c2_append_state *w = opaque; uint8_t row[8], size[2];
    uint16_t i, count, available, length, symbol, target; uint32_t at;
    if (!w || C2AW_PLAN_MARK(w) != C2_EXPORT_PLAN_MARK)
        return C2_STREAM_ERR_STATE;
    count = c2_u16(w->meta + 22);
    if (count > C2D_ENTRY_CAP) return C2_STREAM_ERR_STATE;
    for (i = 0; i < count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row)
            || row[7] != C2_EXPORT_SCAN_MARK)
            return C2_STREAM_ERR_STATE;
        at = c2_u24(row); available = c2_u16(row + 3);
        target = c2_u16(row + 5);
        if (available < 2u || !c2_stream_shelf_read(at, size, sizeof size)
            || !(length = c2_u16(size)) || length > LISP65_SYMBOL_NAME_MAX
            || length > (uint16_t)(available - 2u)
            || !c2_stream_name_value(8u, at + 2u, length, &symbol))
            return C2_STREAM_ERR_STATE;
        c2_record_u16(row, symbol);
        c2_record_u16(row + 2, (uint16_t)sym_function((obj)symbol));
        c2_record_u16(row + 4, target); row[6] = 0u; row[7] = 0u;
        if (!c2_stream_c2d_write((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
    }
    C2AW_PLAN_MARK(w) = 0u;
    return C2_STREAM_OK;
}
#endif
#endif

#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET
/* The first loop proves the complete immutable export plan before the first
 * cell changes.  The second consumes that same proven plan without repeating
 * tag/range checks; no writer or overlay transition exists between the two.
 * One existing cutpoint byte rejects a skipped or replayed publication half. */
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
#define C2_PUBLISH_EXPORTS_ENTRY static C2_PUBLISH_CLEAR_SECTION
#else
#define C2_PUBLISH_EXPORTS_ENTRY C2_APPEND_SECTION("publish_exports")
#endif
C2_PUBLISH_EXPORTS_ENTRY
uint8_t c2_append_publish_exports_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint8_t row[8], journal[4];
    uint16_t i, count, tagged, ordinal; obj symbol, published;
    if (!w || !w->committed || C2AW_PLAN_MARK(w))
        return C2_STREAM_ERR_STATE;
    C2_C1_FREEZER_HOLD(3);
    count = c2_u16(w->meta + 22);
    for (i = 0; i < count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
        tagged = c2_u16(row + 4);
        if (!IS_SYMI((obj)c2_u16(row)) || (tagged & 0x7000u)
            || (tagged & 0x0fffu) >= C2D_ENTRY_CAP || row[6] || row[7])
            return C2_STREAM_ERR_STATE;
    }
    C2AW_PLAN_MARK(w) = C2_EXPORT_PUBLISH_MARK;
    c2_journal_count = 0;
    for (i = 0; i < count; ++i) {
        if (C2AW_PLAN_MARK(w) != C2_EXPORT_PUBLISH_MARK
            || !c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
        symbol = (obj)c2_u16(row); tagged = c2_u16(row + 4);
        ordinal = (uint16_t)(tagged & 0x0fffu);
        journal[0] = row[0]; journal[1] = row[1];
        journal[2] = row[2]; journal[3] = row[3];
        if (!c2_stream_c2d_write(
                (uint16_t)(C2_EXPORT_JOURNAL_BASE
                    + i * C2_EXPORT_JOURNAL_RECORD_BYTES),
                journal, sizeof journal))
            return C2_STREAM_ERR_STATE;
        ++c2_journal_count;
        if (tagged & 0x8000u) {
            published = alloc(T_MACRO);
            if (published == NIL || mem_oom) return C2_STREAM_ERR_STATE;
            cell_set_a(published, MK_BCODE(ordinal));
            cell_set_b(published, NIL);
        } else published = MK_BCODE(ordinal);
        set_sym_function(symbol, published);
    }
    C2AW_PLAN_MARK(w) = 0u;
    if (w->main_ordinal) *w->main_ordinal = (uint16_t)(w->new_entries - 1u);
    if (C2_C1_FREEZER_ABORT_REQUESTED()) return C2_STREAM_ERR_STATE;
    return C2_STREAM_OK;
}
#undef C2_PUBLISH_EXPORTS_ENTRY
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
/* One physical record has two logical entries.  The resident serial driver
 * selects one operation through the dead source-record byte; the dispatcher
 * clears it before either body mutates state, so skip/replay/foreign markers
 * all fail closed.  Neither body loads or calls another overlay. */
C2_PUBLISH_CLEAR_SECTION
uint8_t c2_append_publish_clear_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_PUBLISH_CLEAR_SLOT);
    c2_append_state *w = opaque;
    uint8_t requested;
    if (!w) return C2_STREAM_ERR_STATE;
    requested = C2AW_PUBLISH_CLEAR_MARK(w);
    C2AW_PUBLISH_CLEAR_MARK(w) = 0u;
    if (requested == C2_PUBLISH_REQUEST_MARK)
        return c2_append_publish_exports_phase(opaque);
    if (requested == C2_CLEAR_REQUEST_MARK)
        return c2_append_journal_clear_phase(opaque);
    return C2_STREAM_ERR_STATE;
}
#undef C2_PUBLISH_CLEAR_SECTION
#endif
#else
C2_APPEND_SECTION("publish_names") uint8_t c2_append_publish_names_phase(void *opaque) {
#ifdef LISP65_C2_LITE_COLD_EVICTION
    c2_append_state *w = opaque; uint8_t row[8];
    uint16_t i, count, tagged;
    if (!w || !w->committed) return C2_STREAM_ERR_STATE;
    count = c2_u16(w->meta + 22);
    for (i = 0; i < count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
        tagged = c2_u16(row + 4);
        if (!IS_SYMI((obj)c2_u16(row)) || (tagged & 0x7000u)
            || (tagged & 0x0fffu) >= C2D_ENTRY_CAP || row[6] || row[7])
            return C2_STREAM_ERR_STATE;
    }
    return C2_STREAM_OK;
#else
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
#endif
}

C2_APPEND_SECTION("publish_cells") uint8_t c2_append_publish_cells_phase(void *opaque) {
#ifdef LISP65_C2_LITE_COLD_EVICTION
    c2_append_state *w = opaque; uint8_t row[8], journal[4];
    uint16_t i, count, tagged, ordinal; obj symbol, published;
    if (!w || !w->committed) return C2_STREAM_ERR_STATE;
    count = c2_u16(w->meta + 22); c2_journal_count = 0;
    for (i = 0; i < count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_PLAN_RECORD_BYTES), row, sizeof row))
            return C2_STREAM_ERR_STATE;
        symbol = (obj)c2_u16(row); tagged = c2_u16(row + 4);
        ordinal = (uint16_t)(tagged & 0x0fffu);
        if (!IS_SYMI(symbol) || (tagged & 0x7000u)
            || ordinal >= C2D_ENTRY_CAP) return C2_STREAM_ERR_STATE;
        journal[0] = row[0]; journal[1] = row[1];
        journal[2] = row[2]; journal[3] = row[3];
        if (!c2_stream_c2d_write((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + i * C2_EXPORT_JOURNAL_RECORD_BYTES), journal, sizeof journal))
            return C2_STREAM_ERR_STATE;
        ++c2_journal_count;
        if (tagged & 0x8000u) {
            published = alloc(T_MACRO);
            if (published == NIL || mem_oom) return C2_STREAM_ERR_STATE;
            cell_set_a(published, MK_BCODE(ordinal));
            cell_set_b(published, NIL);
        } else published = MK_BCODE(ordinal);
        set_sym_function(symbol, published);
    }
    c2_journal_count = 0; c2_record_u16(w->meta + 22, 0u);
    if (w->main_ordinal) *w->main_ordinal = (uint16_t)(w->new_entries - 1u);
    return C2_STREAM_OK;
#else
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
#endif
}
#endif

static uint8_t c2_publish_exports_from(uint16_t first) {
    uint8_t ok;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.old_entries = first; c2aw.committed = 1; c2aw.staged = 0;
    c2aw.append = c2_runtime;
    c2aw.main_ordinal = 0; c2aw.rollback_rebuild_header = 0;
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
    C2AW_PLAN_MARK(&c2aw) = 0u;
#endif
    c2_journal_count = 0;
    ok = (uint8_t)(
#ifdef LISP65_C2_LITE_COLD_EVICTION
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
        c2_overlay_call_range(LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT,
                              LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT,
                              &c2aw)
#else
        c2_overlay_call(LISP65_C2_APPEND_PUBLISH_PLAN_SLOT, &c2aw)
#endif
        &&
#endif
#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
        (C2AW_PUBLISH_CLEAR_MARK(&c2aw) = C2_PUBLISH_REQUEST_MARK,
#endif
        c2_overlay_call(LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT, &c2aw)
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
        )
#endif
        );
#else
        c2_overlay_call(LISP65_C2_APPEND_PUBLISH_NAMES_SLOT, &c2aw)
        && c2_overlay_call(LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw));
#endif
    if (!ok) {
#ifdef LISP65_C2_NESTED_APPEND_V5
        /* The rollback plan is the one ordering authority.  In particular,
         * its three abort-only wipes are data bytes consumed by the shared
         * walker, never separately materialized control flow in main. */
        (void)c2_append_run_rollback_plan(&c2aw);
#else
        (void)c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
#endif
    }
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    return ok;
}

#ifdef LISP65_C2_NESTED_APPEND_V5
C2_APPEND_SECTION("rollback_unpublish")
#else
C2_APPEND_SECTION("rollback")
#endif
static void c2_append_restore_exports(void) {
    uint8_t b[4];
    while (c2_journal_count) {
        --c2_journal_count;
        if (!c2_stream_c2d_read((uint16_t)(C2_EXPORT_JOURNAL_BASE
                + c2_journal_count * C2_EXPORT_JOURNAL_RECORD_BYTES), b, sizeof b))
            continue;
        set_sym_function((obj)c2_u16(b), (obj)c2_u16(b + 2));
    }
}

#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_TWO_REGION_SESSION_STORE
C2_APPEND_SECTION("rollback_wipe_plane")
#else
C2_APPEND_SECTION("rollback_finalize")
#endif
#else
C2_APPEND_SECTION("rollback")
#endif
static uint8_t c2_append_rollback_zero_plane(
                                             uint16_t at, uint16_t bytes) {
    static const uint8_t zeros[16] = {0};
    while (bytes) {
        uint16_t n = bytes > sizeof zeros ? sizeof zeros : bytes;
        if (!c2_stream_c2d_write(at, zeros, n)) return 0u;
        at = (uint16_t)(at + n); bytes = (uint16_t)(bytes - n);
    }
    return 1u;
}

#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_TWO_REGION_SESSION_STORE
#define C2_ROLLBACK_ATTIC_SECTION C2_APPEND_SECTION("rollback_wipe_attic")
#define C2_ROLLBACK_CHIP_SECTION C2_APPEND_SECTION("rollback_wipe_chip")
#else
#define C2_ROLLBACK_ATTIC_SECTION C2_APPEND_SECTION("rollback_finalize")
#define C2_ROLLBACK_CHIP_SECTION C2_APPEND_SECTION("rollback_finalize")
#endif
C2_ROLLBACK_ATTIC_SECTION static void c2_append_rollback_zero_attic(
                                             uint32_t at, uint16_t bytes) {
    static const uint8_t zeros[16] = {0};
    while (bytes) {
        uint16_t n = bytes > sizeof zeros ? sizeof zeros : bytes;
        c2_dma_copy((uint32_t)(uint16_t)(uintptr_t)zeros,
                    LISP65_C2_SESSION_PHYSICAL + at, n);
        at += n; bytes = (uint16_t)(bytes - n);
    }
}

C2_ROLLBACK_CHIP_SECTION static uint8_t
c2_append_rollback_zero_chip_code(c2_append_state *w) {
#ifdef LISP65_C2_LITE_COLD_EVICTION
    static const uint8_t zeros[16] = {0}; uint16_t i;
    if (!w || !w->code_len
        || (uint32_t)C2AW_CHIP_CODE_BASE(w) + w->code_len > 65536UL)
        return 0u;
    for (i = 0; i < w->code_len; i = (uint16_t)(i + sizeof zeros)) {
        uint16_t n = (uint16_t)(w->code_len - i);
        if (n > sizeof zeros) n = sizeof zeros;
        c2_facade_c2_dma((uint16_t)(uintptr_t)zeros, 0u,
                         (uint16_t)(C2AW_CHIP_CODE_BASE(w) + i), 2u, n);
    }
    return 1u;
#else
    (void)w;
    return 1u;
#endif
}
#undef C2_ROLLBACK_ATTIC_SECTION
#undef C2_ROLLBACK_CHIP_SECTION
#endif

#ifdef LISP65_C2_NESTED_APPEND_V5
C2_APPEND_SECTION("rollback_unpublish")
uint8_t c2_append_rollback_unpublish_phase(void *opaque) {
    C2_INSTALL_TRACE_LOCK_PRIMARY();
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_ROLLBACK_UNPUBLISH);
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    c2_append_restore_exports();
    if (!w->staged) return C2_STREAM_OK;
    if (C2AW_TRANSIENT(w)) {
        if (!c2_stream_c2d_read(0, w->old_header, sizeof w->old_header))
            return C2_STREAM_ERR_IO;
        /* Unpublish first.  Once the watermark rises, every removed handle is
         * dead even if a later wipe itself fails. */
        c2_header_watermark(w->old_header,
                            (uint16_t)(w->old_entries + C2D_ENTRY_CAP));
        if (!c2_stream_c2d_write(
                0u, w->old_header, sizeof w->old_header))
            return C2_STREAM_ERR_IO;
        c2_runtime.entry_first = (uint16_t)(w->old_entries + C2D_ENTRY_CAP);
        c2_decode_active = &c2_runtime;
        return C2_STREAM_OK;
    }
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
    /* The preceding common boundary phase has already proved that all
     * forward jobs landed.  Restoration now submits plain ordered writes;
     * the final CLEAR bookend proves the complete rollback tail. */
    if (!c2_stream_c2d_write(
            0u, w->old_header, sizeof w->old_header))
        return C2_STREAM_ERR_IO;
    C2_C1_FREEZER_HOLD_STATE_PROVEN(4);
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("rollback_finalize")
uint8_t c2_append_rollback_finalize_phase(void *opaque) {
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_ROLLBACK_FINALIZE);
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    if (!w->staged) return C2_STREAM_OK;
#ifndef LISP65_C2_TWO_REGION_SESSION_STORE
    if (C2AW_TRANSIENT(w)) {
        if (!c2_append_rollback_zero_plane(
                (uint16_t)(c2_runtime.images_offset
                    + w->new_images * 32u), 32u)
            || !c2_append_rollback_zero_plane(
                (uint16_t)(c2_runtime.entries_offset
                    + w->new_entries * 10u), (uint16_t)(w->entries * 10u))
            || !c2_append_rollback_zero_plane(
                (uint16_t)(c2_runtime.resolutions_offset
                    + w->new_res * 2u), (uint16_t)(w->literals * 2u))
            || !c2_append_rollback_zero_plane(
                (uint16_t)(c2_runtime.roots_offset
                    + w->new_roots * 2u), (uint16_t)(w->roots * 2u))
            || !c2_append_rollback_zero_chip_code(w))
            return C2_STREAM_ERR_IO;
        c2_append_rollback_zero_attic(w->attic, w->length);
        if (!c2_stream_c2d_write(
                0u, w->old_header, sizeof w->old_header))
            return C2_STREAM_ERR_IO;
        c2_pending_roots = w->old_images ? C2D_ROOT_CAP : c2_committed_roots;
        c2_decode_active = &c2_runtime;
        return C2_STREAM_OK;
    }
    if (!w->before) return C2_STREAM_ERR_STATE;
    if (!c2_append_rollback_zero_plane(
            (uint16_t)(w->before->images_offset + w->old_images * 32u), 32u)
        || !c2_append_rollback_zero_plane(
            (uint16_t)(w->before->entries_offset + w->old_entries * 10u),
            (uint16_t)(w->entries * 10u))
        || !c2_append_rollback_zero_plane(
            (uint16_t)(w->before->resolutions_offset + w->old_res * 2u),
            (uint16_t)(w->literals * 2u))
        || !c2_append_rollback_zero_plane(
            (uint16_t)(w->before->roots_offset + w->old_roots * 2u),
            (uint16_t)(w->roots * 2u))
        || !c2_append_rollback_zero_chip_code(w)
        || !c2_stream_c2d_write(
            0u, w->old_header, sizeof w->old_header))
        return C2_STREAM_ERR_IO;
    c2_pending_roots = w->old_roots; c2_decode_active = &c2_runtime;
    return C2_STREAM_OK;
#else
    if (C2AW_TRANSIENT(w)) {
        if (!c2_stream_c2d_write(
                0u, w->old_header, sizeof w->old_header))
            return C2_STREAM_ERR_IO;
        c2_pending_roots = w->old_images
            ? C2D_ROOT_CAP : c2_committed_roots;
    } else {
        if (!w->before
            || !c2_stream_c2d_write(
                0u, w->old_header, sizeof w->old_header))
            return C2_STREAM_ERR_IO;
        c2_pending_roots = w->old_roots;
    }
    c2_decode_active = &c2_runtime;
    return C2_STREAM_OK;
#endif
}

#ifdef LISP65_C2_TWO_REGION_SESSION_STORE
C2_APPEND_SECTION("rollback_wipe_plane")
uint8_t c2_append_rollback_wipe_plane_phase(void *opaque) {
    c2_append_state *w = opaque;
    uint16_t images, entries, resolutions, roots;
    const c2_stream_context *base;
    if (!w) return C2_STREAM_ERR_STATE;
    if (!w->staged) return C2_STREAM_OK;
    base = C2AW_TRANSIENT(w) ? &c2_runtime : w->before;
    if (!base) return C2_STREAM_ERR_STATE;
    images = C2AW_TRANSIENT(w) ? w->new_images : w->old_images;
    entries = C2AW_TRANSIENT(w) ? w->new_entries : w->old_entries;
    resolutions = C2AW_TRANSIENT(w) ? w->new_res : w->old_res;
    roots = C2AW_TRANSIENT(w) ? w->new_roots : w->old_roots;
    if (!c2_append_rollback_zero_plane(
            (uint16_t)(base->images_offset + images * 32u), 32u)
        || !c2_append_rollback_zero_plane(
            (uint16_t)(base->entries_offset + entries * 10u),
            (uint16_t)(w->entries * 10u))
        || !c2_append_rollback_zero_plane(
            (uint16_t)(base->resolutions_offset + resolutions * 2u),
            (uint16_t)(w->literals * 2u))
        || !c2_append_rollback_zero_plane(
            (uint16_t)(base->roots_offset + roots * 2u),
            (uint16_t)(w->roots * 2u)))
        return C2_STREAM_ERR_IO;
    return C2_STREAM_OK;
}

C2_APPEND_SECTION("rollback_wipe_chip")
uint8_t c2_append_rollback_wipe_chip_phase(void *opaque) {
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    if (!w->staged) return C2_STREAM_OK;
    return c2_append_rollback_zero_chip_code(w)
        ? C2_STREAM_OK : C2_STREAM_ERR_IO;
}

C2_APPEND_SECTION("rollback_wipe_attic")
uint8_t c2_append_rollback_wipe_attic_phase(void *opaque) {
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    if (!w->staged || !C2AW_TRANSIENT(w)) return C2_STREAM_OK;
    c2_append_rollback_zero_attic(w->attic, w->length);
    return C2_STREAM_OK;
}
#endif
#else
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
#endif

static C2_KERNAL_RESIDENT uint8_t c2_append_begin(uint16_t length,
                               c2_stream_context *before,
                               uint16_t *main_ordinal
#ifdef LISP65_C2_NESTED_APPEND_V5
                               , uint8_t transient
#endif
                               ) {
    if (!c2_ready || !before || !main_ordinal) return 0;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.before = before; c2aw.main_ordinal = main_ordinal; c2aw.length = length;
    c2aw.staged = 0; c2aw.committed = 0;
    c2aw.append.error = 0u;
#ifdef LISP65_C2_NESTED_APPEND_V5
    C2AW_JOURNAL_RESULT(&c2aw) = C2J_RESULT_NONE;
    C2AW_COMPLETION_MARK(&c2aw) = 0u;
    c2_journal_count = 0;
#endif
    c2aw.rollback_rebuild_header =
#ifdef LISP65_C2_NESTED_APPEND_V5
        transient ? C2_APPEND_FLAG_TRANSIENT :
#endif
        0u;
#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
    if (!c2_overlay_call_range(LISP65_C2_APPEND_ENVELOPE_SLOT,
                               LISP65_C2_APPEND_CRC_METADATA_SLOT, &c2aw))
        goto v5_fail;
    C2AW_ROOTS_FRONTS_MARK(&c2aw) = C2_ROOTS_REQUEST_MARK;
    if (!c2_overlay_call(LISP65_C2_APPEND_ROOTS_FRONTS_SLOT, &c2aw))
        goto v5_fail;
    C2AW_ROOTS_FRONTS_MARK(&c2aw) = C2_FRONTS_REQUEST_MARK;
    if (!c2_overlay_call(LISP65_C2_APPEND_ROOTS_FRONTS_SLOT, &c2aw)
#else
    if (!c2_overlay_call_range(LISP65_C2_APPEND_ENVELOPE_SLOT,
                               LISP65_C2_APPEND_FRONTS_SLOT, &c2aw)
#endif
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
        || !(transient
             ? c2_overlay_call_range(
                    LISP65_C2_APPEND_RESERVE_TRANSIENT_BOUNDS_SLOT,
                    LISP65_C2_APPEND_RESERVE_TRANSIENT_CODE_SLOT, &c2aw)
             : c2_overlay_call_range(
                    LISP65_C2_APPEND_RESERVE_PERSISTENT_BOUNDS_SLOT,
                    LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT, &c2aw))
#else
        || !c2_overlay_call(transient
                ? LISP65_C2_APPEND_RESERVE_TRANSIENT_SLOT
                : LISP65_C2_APPEND_RESERVE_PERSISTENT_SLOT, &c2aw)
#endif
        || !c2_append_run_stage_plan(&c2aw)) {
#else
    if (!c2_overlay_call(LISP65_C2_APPEND_ENVELOPE_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_CRC_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_METADATA_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_CAPACITY_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_STAGE_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_IMAGE_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_ENTRIES_SLOT, &c2aw)) {
#endif
#ifdef LISP65_C2_NESTED_APPEND_V5
        goto v5_fail;
#else
        (void)c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
#endif
        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
        return 0;
    }
    c2_pending_roots =
#ifdef LISP65_C2_NESTED_APPEND_V5
        (transient || c2_runtime.entry_first != C2D_HANDLE_CAP)
            ? C2D_ROOT_CAP :
#endif
        c2aw.new_roots;
    c2_decode_active = &c2aw.append;
    if (!c2_decode_from(&c2aw.append, 4u)
#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_LITE_COLD_EVICTION
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
        || (transient
             ? (C2AW_COMPLETION_MARK(&c2aw) = C2_COMPLETION_PUBLISH_MARK,
                !c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw))
             : !c2_append_run_persistent_publish_plan(&c2aw))
#else
        || !(transient
             ? c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw)
#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS
             : c2_overlay_call_range(LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT,
                    LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw))
#else
             : c2_overlay_call_range(LISP65_C2_APPEND_PUBLISH_PLAN_SLOT,
                    LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw))
#endif
#endif
#else
        || !c2_overlay_call_range(LISP65_C2_APPEND_HEADER_SLOT,
                transient ? LISP65_C2_APPEND_HEADER_SLOT
                          : LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw)
#endif
#else
        || !c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_PUBLISH_NAMES_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_PUBLISH_CELLS_SLOT, &c2aw)
#endif
        ) {
#ifdef LISP65_C2_NESTED_APPEND_V5
        goto v5_fail;
#else
        (void)c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
#endif
        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
        return 0;
    }
#ifdef LISP65_C2_NESTED_APPEND_V5
    if (transient)
        *main_ordinal = (uint16_t)(c2aw.new_entries + c2aw.entries
                                   - 1u + C2D_ENTRY_CAP);
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
    C2AW_PUBLISH_CLEAR_MARK(&c2aw) = C2_CLEAR_REQUEST_MARK;
#endif
    if (!c2_overlay_call(LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw))
        goto v5_fail;
#endif
    return c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);

#ifdef LISP65_C2_NESTED_APPEND_V5
v5_fail:
    if (!c2_append_run_rollback_plan(&c2aw)) {
        c2_ready = 0;
        c2aw.append.error = 0u;
    }
    (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
    return 0u;
#endif
}

#endif

static uint8_t c2_append_rollback(const c2_stream_context *before) {
    uint8_t ok;
    if (!before || !c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
#ifdef LISP65_C2_NESTED_APPEND_V5
    c2aw.main_ordinal = 0;
    C2AW_JOURNAL_RESULT(&c2aw) = C2J_RESULT_NONE;
    C2AW_COMPLETION_MARK(&c2aw) = 0u;
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
    C2AW_ROOTS_FRONTS_MARK(&c2aw) = C2_FRONTS_REQUEST_MARK;
#endif
    if (!c2_overlay_call(LISP65_C2_APPEND_FRONTS_SLOT, &c2aw)
        || !c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT, &c2aw)
        || C2AW_JOURNAL_RESULT(&c2aw) !=
#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
            C2J_RESULT_PREPARED
#else
            C2J_RESULT_ACTIVE
#endif
            ) {
        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
        return 0;
    }
#else
    c2aw.before = (c2_stream_context *)before;
    c2aw.old_images = before->image_count; c2aw.old_entries = before->entry_count;
    c2aw.old_res = before->resolution_count; c2aw.old_roots = before->c2_root_count;
    c2aw.entries = (uint16_t)(c2_runtime.entry_count - before->entry_count);
    c2aw.literals = (uint16_t)(c2_runtime.resolution_count - before->resolution_count);
    c2aw.roots = (uint16_t)(c2_runtime.c2_root_count - before->c2_root_count);
    c2aw.staged = 1; c2aw.committed = 1; c2aw.rollback_rebuild_header = 1;
#endif
#ifdef LISP65_C2_NESTED_APPEND_V5
#ifndef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT
    C2AW_JOURNAL_RESULT(&c2aw) = C2J_RESULT_NONE;
#endif
    c2_journal_count = 0;
    ok = (uint8_t)(c2_overlay_call(LISP65_C2_APPEND_JOURNAL_WRITE_SLOT, &c2aw)
        && c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw)
        && c2_append_run_rollback_plan(&c2aw));
    if (!ok) c2_ready = 0;
#else
    ok = c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_SLOT, &c2aw);
#endif
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    return ok;
}

#ifdef LISP65_C2_NESTED_APPEND_V5
/* Non-local aborts first discard the transport's abandoned transaction, then
 * run this serial driver.  It restores one in-flight C2J mutation and removes
 * every dynamically scoped transient record.  Only this resident calls the
 * transported phases; an overlay never loads or calls another overlay. */
#ifdef LISP65_C2_RESIDENCY_TRIAGE
C2_APPEND_SECTION("abort_control")
uint8_t c2_append_abort_control_phase(void *opaque) {
    C2_INSTALL_TRACE_LOCK_PRIMARY();
    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(
        LISP65_C2_APPEND_ABORT_CONTROL_SLOT);
    c2_append_state *w = opaque;
    if (!w) return C2_STREAM_ERR_STATE;
    C2AW_ABORT_DONE(w) = 0u;
    switch (C2AW_ABORT_STATE(w)) {
    case C2_ABORT_PLAN_VALIDATE:
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_VALIDATE;
        break;
    case C2_ABORT_PLAN_AFTER_VALIDATE:
        if (C2AW_JOURNAL_RESULT(w) == C2J_RESULT_ACTIVE) {
            C2AW_COMPLETION_MARK(w) = C2_COMPLETION_ROLLBACK_MARK;
            C2AW_ABORT_START(w) = LISP65_C2_APPEND_HEADER_SLOT;
            C2AW_ABORT_END(w) = LISP65_C2_APPEND_HEADER_SLOT;
            C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_BARRIER;
        } else {
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
            C2AW_ROOTS_FRONTS_MARK(w) = C2_FRONTS_REQUEST_MARK;
#endif
            C2AW_ABORT_START(w) = LISP65_C2_APPEND_FRONTS_SLOT;
            C2AW_ABORT_END(w) = LISP65_C2_APPEND_FRONTS_SLOT;
            C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_FRONTS;
        }
        break;
    case C2_ABORT_PLAN_AFTER_BARRIER:
        if (C2AW_JOURNAL_RESULT(w) == C2J_RESULT_ACTIVE) {
            C2AW_ABORT_START(w) = LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT;
            C2AW_ABORT_END(w) = LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT;
            C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_UNPUBLISH;
        } else {
            return C2_STREAM_ERR_STATE;
        }
        break;
    case C2_ABORT_PLAN_AFTER_UNPUBLISH:
#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT
        C2AW_PUBLISH_CLEAR_MARK(w) = C2_CLEAR_REQUEST_MARK;
#endif
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_CLEAR_WRITE;
        break;
    case C2_ABORT_PLAN_AFTER_CLEAR_WRITE:
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_HEADER_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_HEADER_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_ROLLBACK;
        break;
    case C2_ABORT_PLAN_AFTER_ROLLBACK:
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
        C2AW_ROOTS_FRONTS_MARK(w) = C2_FRONTS_REQUEST_MARK;
#endif
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_FRONTS_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_FRONTS_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_FRONTS;
        break;
    case C2_ABORT_PLAN_AFTER_FRONTS:
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_PREPARE;
        break;
    case C2_ABORT_PLAN_AFTER_PREPARE:
        if (C2AW_JOURNAL_RESULT(w) == C2J_RESULT_NONE) {
            C2AW_ABORT_DONE(w) = 1u;
        } else {
            C2AW_ABORT_START(w) = LISP65_C2_APPEND_JOURNAL_WRITE_SLOT;
            C2AW_ABORT_END(w) = LISP65_C2_APPEND_JOURNAL_WRITE_SLOT;
            C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_WRITE;
        }
        break;
    case C2_ABORT_PLAN_AFTER_WRITE:
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_HEADER_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_HEADER_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_ACTIVE;
        break;
    case C2_ABORT_PLAN_AFTER_ACTIVE:
        C2AW_COMPLETION_MARK(w) = C2_COMPLETION_ROLLBACK_MARK;
        C2AW_ABORT_START(w) = LISP65_C2_APPEND_HEADER_SLOT;
        C2AW_ABORT_END(w) = LISP65_C2_APPEND_HEADER_SLOT;
        C2AW_ABORT_STATE(w) = C2_ABORT_PLAN_AFTER_BARRIER;
        break;
    default:
        return C2_STREAM_ERR_STATE;
    }
    return C2_STREAM_OK;
}

static LISP65_C2_REOPEN_TEXT_GAP1_FN uint8_t c2_abort_driver(void) {
    uint8_t fuel = (uint8_t)(C2D_MAX_TRANSIENT_DEPTH * 9u + 9u), ok = 0;
    (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
    (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER);
#ifndef LISP65_C2_E000_REOPEN
    if (!c2_ready) return 1;
#endif
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.main_ordinal = 0;
    C2AW_JOURNAL_RESULT(&c2aw) = C2J_RESULT_NONE;
    C2AW_COMPLETION_MARK(&c2aw) = 0u;
    C2AW_ABORT_STATE(&c2aw) = C2_ABORT_PLAN_VALIDATE;
    C2AW_ABORT_DONE(&c2aw) = 0u;
    while (fuel--) {
        if (!c2_overlay_call(LISP65_C2_APPEND_ABORT_CONTROL_SLOT, &c2aw))
            goto done;
        if (C2AW_ABORT_DONE(&c2aw)) { ok = 1; break; }
        if (C2AW_ABORT_START(&c2aw) > C2AW_ABORT_END(&c2aw)
            || !c2_overlay_call_range(C2AW_ABORT_START(&c2aw),
                                      C2AW_ABORT_END(&c2aw), &c2aw))
            goto done;
    }
done:
    if (!ok) c2_ready = 0;
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    return ok;
}
#else
static __attribute__((noinline)) uint8_t c2_abort_driver(void) {
    uint8_t ok = 0;
    (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
    (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER);
    if (!c2_ready) return 1;
    if (!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    c2aw.main_ordinal = 0;
    C2AW_JOURNAL_RESULT(&c2aw) = C2J_RESULT_NONE;
    C2AW_COMPLETION_MARK(&c2aw) = 0u;
    if (!c2_overlay_call_range(LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT,
                               LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT,
                               &c2aw)) goto done;
    if (C2AW_JOURNAL_RESULT(&c2aw) == C2J_RESULT_ACTIVE
        && !c2_append_run_rollback_plan(&c2aw)) goto done;
    for (;;) {
#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT
        C2AW_ROOTS_FRONTS_MARK(&c2aw) = C2_FRONTS_REQUEST_MARK;
#endif
        if (!c2_overlay_call(LISP65_C2_APPEND_FRONTS_SLOT, &c2aw)
            || !c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT, &c2aw))
            goto done;
        if (C2AW_JOURNAL_RESULT(&c2aw) == C2J_RESULT_NONE) break;
        if (!c2_overlay_call(LISP65_C2_APPEND_JOURNAL_WRITE_SLOT, &c2aw)
            || !c2_append_run_rollback_plan(&c2aw)) goto done;
    }
    ok = 1;
done:
    if (!ok) c2_ready = 0;
    if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND)) return 0;
    return ok;
}
#endif

uint8_t c2_product_abort_cleanup(void) {
    if (vm_runtime_overlay_abort_cleanup() != VM_RUNTIME_OVERLAY_OK) {
        c2_ready = 0; return 0;
    }
    /* E000 is not callable before ownership.  The formal reopening keeps the
     * harmless pre-READY landing in the low seam; ordinary profiles retain
     * their byte-pinned guard in c2_abort_driver itself. */
#ifdef LISP65_C2_E000_REOPEN
    return !c2_ready || c2_abort_driver();
#else
    return c2_abort_driver();
#endif
}
#endif

#ifdef LISP65_C2_TRANSACTION_AUTH_NOINLINE
__attribute__((noinline, used))
#endif
uint8_t c2_product_append_staged(uint16_t length) {
    c2_stream_context before; uint16_t main;
#ifdef LISP65_C2_TRANSACTION_AUTH
    uint8_t ok;
    if (vm_runtime_overlay_transaction_begin(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
            c2_runtime.generation) != VM_RUNTIME_OVERLAY_OK) return 0;
    ok = c2_append_begin(length, &before, &main
#ifdef LISP65_C2_NESTED_APPEND_V5
                         , 0u
#endif
                         );
    if (vm_runtime_overlay_transaction_end() != VM_RUNTIME_OVERLAY_OK) return 0;
    return ok;
#else
    return c2_append_begin(length, &before, &main
#ifdef LISP65_C2_NESTED_APPEND_V5
                           , 0u
#endif
                           );
#endif
}

#ifdef LISP65_C2_TRANSACTION_AUTH_NOINLINE
__attribute__((noinline, used))
#endif
obj c2_product_install(obj fnlist, obj definition_name) {
    c2_stream_context before; c2_emit_status emit;
    uint16_t length, main = (uint16_t)NIL;
    uint8_t transient = (uint8_t)(definition_name == lisp_t);
    uint8_t append_ok = 0u;
    obj result;
#ifdef LISP65_C2_TRANSACTION_AUTH
    if (vm_runtime_overlay_transaction_begin(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
            c2_runtime.generation) != VM_RUNTIME_OVERLAY_OK) {
        vm_status = VM_BADOPCODE; return NIL;
    }
#endif
    emit = c2_session_emit_reset();
    if (emit == C2_EMIT_OK)
        emit = c2_session_emit_add(fnlist,
            transient ? NIL : definition_name, 0u);
    if (emit == C2_EMIT_OK) emit = c2_session_emit_finalize(&length);
    if (emit == C2_EMIT_OK)
        append_ok = c2_append_begin(length, &before, &main
#ifdef LISP65_C2_NESTED_APPEND_V5
                                                , transient
#endif
                                                );
    if (emit != C2_EMIT_OK || !append_ok) {
#ifdef LISP65_C2_TRANSACTION_AUTH
        (void)vm_runtime_overlay_transaction_end();
#endif
        vm_status = VM_BADOPCODE; return NIL;
    }
    if (!transient) {
#ifdef LISP65_C2_TRANSACTION_AUTH
        if (vm_runtime_overlay_transaction_end() != VM_RUNTIME_OVERLAY_OK) {
            vm_status = VM_BADOPCODE; return NIL;
        }
#endif
        return definition_name != NIL ? definition_name : MK_BCODE(main);
    }
#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_TRANSACTION_AUTH
    if (vm_runtime_overlay_transaction_end() != VM_RUNTIME_OVERLAY_OK) {
        vm_status = VM_BADOPCODE; return NIL;
    }
#endif
#endif
    C2_INSTALL_TRACE_ENTER_INNER();
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_INNER_VM);
    result = vm_run_dir((int)main, 0, 0);
#ifdef LISP65_C2_NESTED_APPEND_V5
#ifdef LISP65_C2_TRANSACTION_AUTH
    if (vm_runtime_overlay_transaction_begin(
            LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,
            c2_runtime.generation) != VM_RUNTIME_OVERLAY_OK) {
        if (vm_status != VM_OK) return NIL;
        vm_status = VM_BADOPCODE; return NIL;
    }
#endif
#endif
    if (!c2_append_rollback(&before)) {
#ifdef LISP65_C2_TRANSACTION_AUTH
        (void)vm_runtime_overlay_transaction_end();
#endif
        /* A non-OK status is the sole error authority at this boundary.
         * lcc_install_obj() immediately consumes it through vm_check_status();
         * preserving the otherwise unobservable VM result only kept two
         * result bytes live across the cold rollback epilogue. */
        if (vm_status != VM_OK) return NIL;
        vm_status = VM_BADOPCODE; return NIL;
    }
#ifdef LISP65_C2_TRANSACTION_AUTH
    if (vm_runtime_overlay_transaction_end() != VM_RUNTIME_OVERLAY_OK) {
        if (vm_status != VM_OK) return NIL;
        vm_status = VM_BADOPCODE; return NIL;
    }
#endif
    return result;
}

#endif /* LISP65_C2_PRODUCT_CUT */
