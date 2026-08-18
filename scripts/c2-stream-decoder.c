/* Streaming C2I-v2/C2D-v1 decoder used only by the C2.1 substitution proof. */
#include "c2-stream-decoder.h"
#include "../src/boot_progress.h"
#ifdef LISP65_C2_PRODUCT_CUT
#include "c2_product_runtime.h"
#include "c2_phase_scratch.h"
#define C2_INSTALL_DECODER_STAMP(slot) C2_INSTALL_TRACE_STAMP_SLOT(slot)
#else
#define C2_INSTALL_DECODER_STAMP(slot) ((void)0)
#define C2_FRAME_ATTRIBUTION_STAMP(index) ((void)0)
#endif
#ifdef LISP65_C2_LITE_BANK3_STAGING
#endif
#ifdef LISP65_C2_LITE_BANK2_STAGING
#include "c2_product_runtime.h"
#include "c2_kernal_facade.h"
#include "c2_kernal_runtime.h"
#include "c2_lite_static_plane.h"
#include "vm_runtime_overlay.h"
#endif

#ifndef C2_STREAM_PHASE
#error "compile c2-stream-decoder.c through one of the phase wrapper translation units"
#endif

#ifdef C2_STREAM_PRODUCT_V3
#ifndef LISP65_C2_PRODUCT_BUILD_ID
#error "C2D-v3 product decoder requires LISP65_C2_PRODUCT_BUILD_ID"
#endif
#define C2_SLICE(n) __attribute__((noinline, section(".lisp65_rt_c2d_" #n)))
#else
#define C2_SLICE(n) __attribute__((noinline, section(".lisp65_rt_l65m_" #n)))
#endif
#define C2_LOCAL static __attribute__((unused))
#define C2_STREAM_PRODUCT_HEADER_SUFFIX 0xfeu

C2_LOCAL uint16_t r16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
C2_LOCAL uint32_t r24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}
C2_LOCAL uint32_t r32(const uint8_t *p) {
    return (uint32_t)r16(p) | (uint32_t)r16(p + 2) << 16;
}
C2_LOCAL void w16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
C2_LOCAL uint8_t magic4(const uint8_t *p, const char *s) {
    return p[0] == (uint8_t)s[0] && p[1] == (uint8_t)s[1]
        && p[2] == (uint8_t)s[2] && p[3] == (uint8_t)s[3];
}
C2_LOCAL uint8_t fail(c2_stream_context *c, uint8_t status) {
    c->error = status; return status;
}
C2_LOCAL uint32_t crc32_update(uint32_t crc, const uint8_t *p, uint16_t n) {
    uint16_t i; uint8_t bit;
    for (i = 0; i < n; ++i) {
        crc ^= p[i];
        for (bit = 0; bit < 8; ++bit) {
#ifdef LISP65_C2_MAP_CPU_TRANSPORT
            if (crc & 1u) crc = (crc >> 1) ^ 0xedb88320UL;
            else crc >>= 1;
#else
            crc = (crc >> 1)
                ^ (0xedb88320UL & (uint32_t)-(int32_t)(crc & 1u));
#endif
        }
    }
    return crc;
}
C2_LOCAL uint8_t shelf_crc32(uint32_t at, uint32_t bytes, uint32_t *result) {
    uint8_t block[32]; uint32_t crc = 0xffffffffUL;
    while (bytes) {
        uint16_t n = bytes > sizeof(block) ? sizeof(block) : (uint16_t)bytes;
        if (!c2_stream_shelf_read(at, block, n)) return 0;
        crc = crc32_update(crc, block, n); at += n; bytes -= n;
    }
    *result = ~crc; return 1;
}
C2_LOCAL uint8_t shelf_crc32_pair(uint32_t first_at, uint16_t first_bytes,
                                uint32_t second_at, uint16_t second_bytes,
                                uint32_t *result) {
    uint8_t block[32]; uint32_t crc = 0xffffffffUL, at = first_at;
    uint32_t left = first_bytes; uint8_t part;
    for (part = 0; part < 2u; ++part) {
        while (left) {
            uint16_t n = left > sizeof(block) ? sizeof(block) : (uint16_t)left;
            if (!c2_stream_shelf_read(at, block, n)) return 0;
            crc = crc32_update(crc, block, n); at += n; left -= n;
        }
        at = second_at; left = second_bytes;
    }
    *result = ~crc; return 1;
}
#ifdef LISP65_C2_LITE_BANK2_STAGING
/*
 * One cold Chip-stage protocol serves the native and bytecode planes:
 * record-bound source, physical copy, readback from the actual destination,
 * content convergence before publication.  Bank 2 carries CRC-32 in its
 * existing L65S record, while the Bank-3 family manifest carries CRC-16;
 * neither path invents a second destination identity.
 */
#define C2_LITE_BANK2_PHYSICAL 0x00020000UL
#define C2_LITE_STAGE_BLOCK 32u
C2_LOCAL uint8_t bank2_crc32(uint16_t at, uint16_t bytes,
                             uint32_t *result) {
    uint8_t block[C2_LITE_STAGE_BLOCK];
    uint32_t crc = 0xffffffffUL;
    while (bytes) {
        uint16_t n = bytes > sizeof(block) ? sizeof(block) : bytes;
        c2_facade_vm_code_load(2u, at, n, block);
        crc = crc32_update(crc, block, n);
        at = (uint16_t)(at + n); bytes = (uint16_t)(bytes - n);
    }
    *result = ~crc;
    return 1u;
}
#endif
#ifdef C2_STREAM_PRODUCT_V3
#define canonical_name c2_stream_product_canonical_name
#define string_record_any c2_stream_product_string_record_any
#define string_record c2_stream_product_string_record
#define c2_image_read c2_stream_product_image_read
#else
C2_LOCAL uint8_t canonical_name(uint32_t at, uint16_t length) {
    uint8_t block[16]; uint16_t done = 0, i;
    if (!length || length > 255u) return 0;
    while (done < length) {
        uint16_t n = (uint16_t)(length - done);
        if (n > sizeof(block)) n = sizeof(block);
        if (!c2_stream_shelf_read(at + done, block, n)) return 0;
        for (i = 0; i < n; ++i) if (block[i] < 0x21u || block[i] > 0x7eu) return 0;
        done = (uint16_t)(done + n);
    }
    return 1;
}
C2_LOCAL uint8_t string_record_any(uint32_t pool, uint16_t pool_bytes, uint32_t wanted,
                                 uint16_t *length, uint32_t *payload) {
    uint8_t b[2]; uint16_t cursor = 0, n;
    if (wanted > 0xffffUL) return 0;
    while (cursor < pool_bytes) {
        if ((uint16_t)(pool_bytes - cursor) < 2u
            || !c2_stream_shelf_read(pool + cursor, b, 2)) return 0;
        n = r16(b);
        if (n > (uint16_t)(pool_bytes - cursor - 2u)) return 0;
        if (cursor == (uint16_t)wanted) {
            *length = n; *payload = pool + cursor + 2u; return 1;
        }
        cursor = (uint16_t)(cursor + 2u + n);
    }
    return 0;
}
C2_LOCAL uint8_t string_record(uint32_t pool, uint16_t pool_bytes, uint32_t wanted,
                             uint16_t expected, uint32_t *payload) {
    uint16_t actual;
    return string_record_any(pool, pool_bytes, wanted, &actual, payload)
        && actual == expected;
}

/*
 * The proof plane used compact 20-byte immutable-image records.  The approved
 * product plane is C2D-v3: 32-byte capacity-separated records with an explicit
 * source kind and generation.  Normalize both into the proven 20-byte view so
 * phases 2--12 share one decoder implementation instead of forking.
 */
C2_LOCAL uint8_t c2_image_read(c2_stream_context *c, uint16_t image,
                               uint8_t out[20]) {
    return c2_stream_c2d_read(
        (uint16_t)(c->images_offset + image * 20u), out, 20u);
}
#endif

/* Validate the self-describing C2D header and pin all mutable-plane ranges. */
#if C2_STREAM_PHASE == 0
C2_SLICE(00) uint8_t c2_stream_phase_00(void *opaque) {
#ifdef C2_STREAM_PRODUCT_V3
    c2_stream_context *c = opaque; uint8_t h[48];
    /* Phase 00 is a transported boot-family slice.  The message is part of
     * that disposable slice, never the resident decoder facade. */
    LISP65_BOOT_PROGRESS_LIBRARIES();
    if (!c || c->phase || c->error || c->c2d_bytes != 33840u)
        return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read(0, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
    if (!magic4(h, "C2D") || h[3]
#ifdef LISP65_C2_NESTED_APPEND_V5
        || h[4] != 5u
#else
        || h[4] != 3u
#endif
        || h[5] != 48u
        || h[6] != 32u || h[7] != 10u
#ifdef LISP65_C2_NESTED_APPEND_V5
        || r16(h + 8) != 4096u
#else
        || r16(h + 8)
#endif
        || !r16(h + 10)
        || r16(h + 14) != 64u || r16(h + 18) != 2048u
        || r16(h + 22) != 4096u || r16(h + 26) != 1536u
        || r32(h + 44) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID)
        return fail(c, C2_STREAM_ERR_C2D);
    c->generation = r16(h + 10); c->image_count = r16(h + 12);
    c->entry_count = r16(h + 16); c->resolution_count = r16(h + 20);
    c->c2_root_count = r16(h + 24); c->images_offset = r16(h + 28);
    c->entries_offset = r16(h + 30); c->resolutions_offset = r16(h + 32);
    c->roots_offset = r16(h + 34); c->catalog_crc32 = r32(h + 40);
    c->phase = C2_STREAM_PRODUCT_HEADER_SUFFIX;
    return C2_STREAM_OK;
#else
    c2_stream_context *c = opaque; uint8_t h[32]; uint32_t expected;
    if (!c || c->phase || c->error || c->c2d_bytes < sizeof(h)) return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read(0, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
    if (!magic4(h, "C2D") || h[3] || h[4] != 1u
        || h[5] != 32u || h[6] != 20u || h[7] != 10u
        || r16(h + 8) || !r16(h + 10) || r16(h + 26))
        return fail(c, C2_STREAM_ERR_C2D);
    c->generation = r16(h + 10); c->image_count = r16(h + 12);
    c->entry_count = r16(h + 14); c->resolution_count = r16(h + 16);
    c->images_offset = r16(h + 18); c->entries_offset = r16(h + 20);
    c->resolutions_offset = r16(h + 22); c->catalog_crc32 = r32(h + 28);
    expected = (uint32_t)c->resolutions_offset + (uint32_t)c->resolution_count * 2u;
    if (!c->image_count || c->images_offset != 32u
        || c->entries_offset != (uint16_t)(32u + c->image_count * 20u)
        || c->resolutions_offset != (uint16_t)(c->entries_offset + c->entry_count * 10u)
        || expected != r16(h + 24) || expected != c->c2d_bytes)
        return fail(c, C2_STREAM_ERR_C2D);
    c->phase = 1; return C2_STREAM_OK;
#endif
}
#endif

/* Product C2D-v3 has a 48-byte mutable-plane header.  Keep its immutable
 * shape/identity check and its offset/count binding in separate transport
 * residents.  The context values written by phase 00 are compared to the
 * second read, so a changed header cannot splice two accepted halves. */
#if C2_STREAM_PHASE == 14
C2_SLICE(00b) uint8_t c2_stream_phase_00b(void *opaque) {
#ifdef C2_STREAM_PRODUCT_V3
    c2_stream_context *c = opaque; uint8_t h[48];
    if (!c || c->phase != C2_STREAM_PRODUCT_HEADER_SUFFIX || c->error)
        return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read(0, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
    if (r16(h + 10) != c->generation || r16(h + 12) != c->image_count
        || r16(h + 16) != c->entry_count
        || r16(h + 20) != c->resolution_count
        || r16(h + 24) != c->c2_root_count
        || r16(h + 28) != 48u || r16(h + 30) != 2096u
        || r16(h + 32) != 22576u || r16(h + 34) != 30768u
        || r16(h + 36) != 33840u || r16(h + 38) != 6u
        || r32(h + 40) != c->catalog_crc32
        || r32(h + 44) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID
        || !c->image_count || c->image_count > 64u
        || c->entry_count > 2048u || c->resolution_count > 4096u
        || c->c2_root_count > 1536u
#ifdef LISP65_C2_NESTED_APPEND_V5
        || r16(h + 8) < 2048u || r16(h + 8) > 4096u
#endif
        )
        return fail(c, C2_STREAM_ERR_C2D);
#ifdef LISP65_C2_NESTED_APPEND_V5
    /* Once the boot decode is complete, entry_first is no longer a decoder
     * cursor.  It becomes the authenticated in-core mirror of the v5 header
     * watermark; the header remains the mutable-plane authority. */
    c->entry_first = r16(h + 8);
#endif
    c->phase = 1; return C2_STREAM_OK;
#else
    (void)opaque;
    return C2_STREAM_ERR_STATE;
#endif
}
#endif

/* Validate the u24-sized shelf and its complete catalog identity. */
#if C2_STREAM_PHASE == 1
C2_SLICE(01) uint8_t c2_stream_phase_01(void *opaque) {
    c2_stream_context *c = opaque; uint8_t h[32]; uint16_t catalog;
    uint32_t payload, total, crc;
    if (!c || c->phase != 1u || c->error) return C2_STREAM_ERR_STATE;
    if (!c2_stream_shelf_read(0, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
    payload = r24(h + 10); total = r24(h + 13); catalog = r16(h + 16);
    if (!magic4(h, "L65S") || h[4] != 4u || h[5] != 32u || h[6] != 32u
        || h[7] != c->image_count || r16(h + 8) != 32u
        || payload != 32u + (uint32_t)c->image_count * 32u
        || total != c->shelf_bytes || catalog != c->image_count * 32u
        || r16(h + 26) != 1u || h[28] || h[29] || h[30] || h[31]
#ifdef C2_STREAM_PRODUCT_V3
        || r32(h + 22) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID
#endif
        || r32(h + 18) != c->catalog_crc32)
        return fail(c, C2_STREAM_ERR_SHELF);
    if (!shelf_crc32(32u, catalog, &crc)) return fail(c, C2_STREAM_ERR_IO);
    if (crc != c->catalog_crc32) return fail(c, C2_STREAM_ERR_SHELF);
    c->phase = 2; return C2_STREAM_OK;
}
#endif

/* Cross-bind every shelf record to its C2D image record. */
#if C2_STREAM_PHASE == 2
C2_SLICE(02) uint8_t c2_stream_phase_02(void *opaque) {
    c2_stream_context *c = opaque; uint8_t s[32], d[20]; uint16_t i;
    uint32_t co, mo;
    if (!c || c->phase != 2u || c->error) return C2_STREAM_ERR_STATE;
    for (i = 0; i < c->image_count; ++i) {
        if (!c2_stream_shelf_read(32u + (uint32_t)i * 32u, s, sizeof(s))
            || !c2_image_read(c, i, d))
            return fail(c, C2_STREAM_ERR_IO);
        co = r24(s + 8); mo = r24(s + 13);
        if (d[0] != i || d[1] || r16(d + 2) != c->entry_cursor
            || r16(d + 6) != c->resolution_cursor
            || r24(d + 10) != co || r24(d + 13) != mo
            || r16(d + 16) != r16(s + 11) || r16(d + 18) != r16(s + 16)
            || !r16(s + 11) || !r16(s + 16) || s[30] != 1u || s[31]
            || co + r16(s + 11) > c->shelf_bytes || mo + r16(s + 16) > c->shelf_bytes)
            return fail(c, C2_STREAM_ERR_SHELF);
        c->entry_cursor = (uint16_t)(c->entry_cursor + r16(d + 4));
        c->resolution_cursor = (uint16_t)(c->resolution_cursor + r16(d + 8));
    }
    if (c->entry_cursor != c->entry_count || c->resolution_cursor != c->resolution_count)
        return fail(c, C2_STREAM_ERR_C2D);
    c->entry_cursor = 0; c->resolution_cursor = 0;
    c->phase = 3; return C2_STREAM_OK;
}
#endif

/* Product-only coarse cut: perform all phase-02 record cross-bindings, but
 * leave the totals close and phase transition to 02b.  `reserved` is the
 * transport cutpoint marker; skipping or replaying either half fails closed. */
#if C2_STREAM_PHASE == 15
#ifdef C2_PHASE02A_DELIVERY_ORACLE
extern const uint16_t c2_phase02a_shelf_crc16[];
extern const uint16_t c2_phase02a_c2d_crc16[];
extern uint16_t rtov_crc_mem(const uint8_t *, uint16_t);

/* Phase 02a consumes immutable, delivery-bound records.  Its expected CRCs
 * are generated from the exact Shelf and C2D bytes packed with this product;
 * a sample obtained through either guarded DMA channel is never an oracle. */
static C2_SLICE(02a) uint8_t c2_phase02a_record_read(
        uint8_t shelf, uint32_t source, uint8_t target[32],
        uint16_t expected) {
    uint16_t start = c2_kernal_frame_count_inline();
    uint8_t i;
    /* A target which already happens to carry the expected CRC is not a
     * convergence witness.  Start from a host-proved nonmatching image so
     * acceptance necessarily follows this submission. */
    for (i = 0u; i != 32u; ++i) target[i] = 0u;
    if (shelf) {
        c2_product_physical_copy(
            (uint32_t)LISP65_C2_SHELF_PHYSICAL + source,
            (uint32_t)(uint16_t)(uintptr_t)target, 32u);
    } else {
        c2_facade_vm_code_load(LISP65_C2D_BANK, (uint16_t)source,
                               32u, target);
    }
    do {
        if (rtov_crc_mem(target, 32u) == expected) return 1u;
    } while ((uint16_t)(c2_kernal_frame_count_inline() - start)
             < C2_PHASE02A_TIMEOUT_FRAMES);
    return 0u;
}
#endif

C2_SLICE(02a) uint8_t c2_stream_phase_02a(void *opaque) {
#ifdef C2_PHASE02A_DELIVERY_ORACLE
    c2_stream_context *c = opaque;
    uint8_t s[32], source[32], raw[32]; uint16_t i;
    if (!c || c->phase != 2u || c->error || c->reserved
        || c->image_count != C2_PHASE02A_ORACLE_RECORDS)
        return C2_STREAM_ERR_STATE;
    for (i = 0; i < c->image_count; ++i) {
        if (!c2_phase02a_record_read(
                1u, 32u + (uint32_t)i * 32u, s,
                c2_phase02a_shelf_crc16[i])
            || !c2_phase02a_record_read(
                0u, (uint16_t)(c->images_offset + i * 32u), raw,
                c2_phase02a_c2d_crc16[i]))
            return fail(c, C2_STREAM_ERR_IO);
        /* Bind the inner image-reader Shelf view independently.  This is the
         * third historical verifier site, not an alias of the outer buffer. */
        if (!c2_phase02a_record_read(
                1u, 32u + (uint32_t)raw[2] * 32u, source,
                c2_phase02a_shelf_crc16[i]))
            return fail(c, C2_STREAM_ERR_IO);
        /* The exact delivery CRCs make all three records the host-validated
         * immutable row.  These live checks bind that row to decoder state;
         * all static field relationships remain independently host-gated. */
        if (raw[2] != i || r16(raw + 4) != c->generation
            || r16(raw + 6) != c->entry_cursor
            || r16(raw + 10) != c->resolution_cursor
            || r16(raw + 21) != r16(s + 11)
            || r16(source + 16) != r16(s + 16))
            return fail(c, C2_STREAM_ERR_SHELF);
        c->entry_cursor = (uint16_t)(c->entry_cursor + r16(raw + 8));
        c->resolution_cursor =
            (uint16_t)(c->resolution_cursor + r16(raw + 12));
    }
    c->reserved = 0x2au;
    return C2_STREAM_OK;
#else
    c2_stream_context *c = opaque; uint8_t s[32], d[20]; uint16_t i;
    uint32_t co, mo;
    if (!c || c->phase != 2u || c->error || c->reserved)
        return C2_STREAM_ERR_STATE;
    for (i = 0; i < c->image_count; ++i) {
        if (!c2_stream_shelf_read(32u + (uint32_t)i * 32u, s, sizeof(s))
            || !c2_image_read(c, i, d))
            return fail(c, C2_STREAM_ERR_IO);
        co = r24(s + 8); mo = r24(s + 13);
        if (d[0] != i || d[1] || r16(d + 2) != c->entry_cursor
            || r16(d + 6) != c->resolution_cursor
            || r24(d + 10) != co || r24(d + 13) != mo
            || r16(d + 16) != r16(s + 11) || r16(d + 18) != r16(s + 16)
            || !r16(s + 11) || !r16(s + 16) || s[30] != 1u || s[31]
            || co + r16(s + 11) > c->shelf_bytes || mo + r16(s + 16) > c->shelf_bytes)
            return fail(c, C2_STREAM_ERR_SHELF);
        c->entry_cursor = (uint16_t)(c->entry_cursor + r16(d + 4));
        c->resolution_cursor = (uint16_t)(c->resolution_cursor + r16(d + 8));
    }
    c->reserved = 0x2au;
    return C2_STREAM_OK;
#endif
}
#endif

/* Product-only coarse cut: close phase-02 totals and publish phase 3. */
#if C2_STREAM_PHASE == 16
C2_SLICE(02b) uint8_t c2_stream_phase_02b(void *opaque) {
    c2_stream_context *c = opaque;
#ifdef LISP65_C2_LITE_BANK2_STAGING
    uint8_t target[5]; uint16_t i, length; uint32_t code_target = 0u;
#endif
    if (!c || c->phase != 2u || c->error || c->reserved != 0x2au)
        return C2_STREAM_ERR_STATE;
    if (c->entry_cursor != c->entry_count || c->resolution_cursor != c->resolution_count)
        return fail(c, C2_STREAM_ERR_C2D);
#ifdef LISP65_C2_LITE_BANK2_STAGING
    /* Phase 02a already cross-bound each raw record length to its immutable
     * Shelf record.  Close the remaining execution-coordinate invariant here,
     * in the record phase, before phase 3 can authenticate payload content. */
    for (i = 0; i < c->image_count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(c->images_offset
                                           + i * 32u + 18u),
                                target, sizeof target))
            return fail(c, C2_STREAM_ERR_IO);
        length = r16(target + 3);
        if (!length || r24(target) != code_target
            || code_target + length > 0x10000UL)
            return fail(c, C2_STREAM_ERR_C2D);
        code_target += length;
    }
    if (code_target != LISP65_C2_LITE_STATIC_CODE_BYTES)
        return fail(c, C2_STREAM_ERR_C2D);
#endif
    c->entry_cursor = 0; c->resolution_cursor = 0; c->reserved = 0;
    c->phase = 3; return C2_STREAM_OK;
}
#endif

/* Validate per-region and combined image CRCs without retaining Attic pointers. */
#if C2_STREAM_PHASE == 3
C2_SLICE(03) uint8_t c2_stream_phase_03(void *opaque) {
    c2_stream_context *c = opaque; uint8_t s[32]; uint16_t image;
    uint32_t co, mo, crc;
    if (!c || c->phase != 3u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_stream_shelf_read(32u + (uint32_t)image * 32u, s, sizeof(s)))
            return fail(c, C2_STREAM_ERR_IO);
        co = r24(s + 8); mo = r24(s + 13);
        if (!shelf_crc32(co, r16(s + 11), &crc)) return fail(c, C2_STREAM_ERR_IO);
        if (crc != r32(s + 18)) return fail(c, C2_STREAM_ERR_SHELF);
        if (!shelf_crc32(mo, r16(s + 16), &crc)) return fail(c, C2_STREAM_ERR_IO);
        if (crc != r32(s + 22)) return fail(c, C2_STREAM_ERR_SHELF);
        if (!shelf_crc32_pair(co, r16(s + 11), mo, r16(s + 16), &crc))
            return fail(c, C2_STREAM_ERR_IO);
        if (crc != r32(s + 26)) return fail(c, C2_STREAM_ERR_SHELF);
    }
#ifdef LISP65_C2_LITE_BANK2_STAGING
    /* Source truth is complete.  Phase 03b alone may now manufacture and
     * prove the target plane; skip/replay cannot reach phase 04. */
    c->reserved = 0x3bu;
#else
    c->phase = 4;
#endif
    return C2_STREAM_OK;
}
#endif

/* Stage every authenticated immutable code record into its C2D-v6 Bank-2
 * coordinate and prove the bytes by reading Bank 2 itself.  READY remains
 * unreachable until all six target CRCs have converged. */
#if C2_STREAM_PHASE == 21
C2_SLICE(03b) uint8_t c2_stream_phase_03b(void *opaque) {
#ifdef LISP65_C2_LITE_BANK2_STAGING
    c2_stream_context *c = opaque;
    uint8_t shelf[32];
    uint16_t image, length, base, start;
    uint32_t source, expected, actual, next = 0u;
    if (!c || c->phase != 3u || c->error || c->reserved != 0x3bu)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_stream_shelf_read(32u + (uint32_t)image * 32u,
                                  shelf, sizeof shelf))
            return fail(c, C2_STREAM_ERR_IO);
        source = r24(shelf + 8); length = r16(shelf + 11);
        expected = r32(shelf + 18);
        if (!length || !expected || next + length > 0x10000UL)
            return fail(c, C2_STREAM_ERR_C2D);
        base = (uint16_t)next;
        c2_product_physical_copy(
            (uint32_t)LISP65_C2_SHELF_PHYSICAL + source,
            C2_LITE_BANK2_PHYSICAL + next, length);
        start = c2_kernal_frame_count_inline();
        do {
            if (!bank2_crc32(base, length, &actual))
                return fail(c, C2_STREAM_ERR_IO);
            if (actual == expected) break;
        } while ((uint16_t)(c2_kernal_frame_count_inline() - start)
                 < LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES);
        if (actual != expected)
            return fail(c, C2_STREAM_ERR_CODE_STAGE);
        next += length;
    }
    if (next != LISP65_C2_LITE_STATIC_CODE_BYTES)
        return fail(c, C2_STREAM_ERR_CODE_STAGE);
    c->reserved = 0u; c->phase = 4u;
    return C2_STREAM_OK;
#else
    (void)opaque;
    return C2_STREAM_ERR_STATE;
#endif
}
#endif

/* Validate every local self-describing C2I-v2 envelope. */
#if C2_STREAM_PHASE == 4
C2_SLICE(04) uint8_t c2_stream_phase_04(void *opaque) {
    C2_INSTALL_DECODER_STAMP(LISP65_C2_PHASE_04_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_DECODE_04);
    c2_stream_context *c = opaque; uint8_t im[20], h[24];
    uint16_t image, ec, lc, eo, lo, so, sb, expected;
    uint32_t meta;
    if (!c || c->phase != 4u || c->error
#ifdef LISP65_C2_LITE_COLD_EVICTION
        || !c2_append_source_domain_guard(c)
#endif
       ) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        meta = r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14); lo = r16(h + 16);
        so = r16(h + 18); sb = r16(h + 20);
        expected = (uint16_t)((so + sb + 1u) & (uint16_t)~1u);
        if (!magic4(h, "C2I") || h[3] || h[4] != 2u
            || h[5] != 24u || h[6] != 16u || h[7] != 8u || r16(h + 8) || r16(h + 22)
            || eo != 24u || lo != (uint16_t)(eo + ec * 16u)
            || so != (uint16_t)(lo + lc * 8u) || expected != r16(im + 18)
            || ec != r16(im + 4) || lc != r16(im + 8))
            return fail(c, C2_STREAM_ERR_C2I);
    }
    c->phase = 5; return C2_STREAM_OK;
}
#endif

/* Validate every 16-byte entry against its C2D session record. */
#if C2_STREAM_PHASE == 5
C2_SLICE(05) uint8_t c2_stream_phase_05(void *opaque) {
    c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16], de[10];
    uint16_t image, local, ec, lc, eo, directory_base;
    uint32_t meta;
    if (!c || c->phase != 5u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        directory_base = r16(im + 2); meta = r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14);
        for (local = 0; local < ec; ++local) {
            uint32_t at; uint16_t length, first, name;
            if (!c2_stream_shelf_read(meta + eo + (uint32_t)local * 16u, e, sizeof(e))
                || !c2_stream_c2d_read((uint16_t)(c->entries_offset
                    + (directory_base + local) * 10u), de, sizeof(de)))
                return fail(c, C2_STREAM_ERR_IO);
            at = r24(e); length = r16(e + 3); first = r16(e + 5); name = r16(e + 8);
            if (!length || at + length > r16(im + 16) || first + e[7] > lc
                || (e[11] & (uint8_t)~3u) || r16(e + 14)
                || (name == 0xffffu && e[11]) || de[0] != image || de[1]
                || r16(de + 2) != local || r16(de + 4) != length
                || r16(de + 6) != (uint16_t)(r16(im + 6) + first)
                || r16(de + 8) != c->generation)
                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->phase = 6; return C2_STREAM_OK;
}
#endif

/* C2-lite v6 cutpoint: validate the immutable entry records themselves before
 * binding them to the execution rows.  `reserved` is the complete handoff;
 * no entry pointer or temporary record survives the overlay replacement. */
#if C2_STREAM_PHASE == 19
C2_SLICE(05a) uint8_t c2_stream_phase_05a(void *opaque) {
    C2_INSTALL_DECODER_STAMP(LISP65_C2_PHASE_05A_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16];
    uint16_t image, local, ec, lc, eo; uint32_t meta;
    if (!c || c->phase != 5u || c->error || c->reserved)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        meta = r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h)))
            return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14);
        for (local = 0; local < ec; ++local) {
            uint32_t at; uint16_t length, first, name;
            if (!c2_stream_shelf_read(meta + eo + (uint32_t)local * 16u,
                                      e, sizeof(e)))
                return fail(c, C2_STREAM_ERR_IO);
            at = r24(e); length = r16(e + 3);
            first = r16(e + 5); name = r16(e + 8);
            if (!length || at + length > r16(im + 16)
                || first + e[7] > lc || (e[11] & (uint8_t)~3u)
                || r16(e + 14) || (name == 0xffffu && e[11]))
                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->reserved = 0x5au;
    return C2_STREAM_OK;
}
#endif

/* C2-lite v6 cutpoint: cross-bind every previously validated entry to its
 * Bank-2 execution coordinate and source-free final image. */
#if C2_STREAM_PHASE == 20
C2_SLICE(05b) uint8_t c2_stream_phase_05b(void *opaque) {
    C2_INSTALL_DECODER_STAMP(LISP65_C2_PHASE_05B_SLOT);
    c2_stream_context *c = opaque;
    uint8_t im[20], h[24], e[16], de[10], raw[32];
    uint16_t image, local, ec, eo, directory_base; uint32_t meta;
    if (!c || c->phase != 5u || c->error || c->reserved != 0x5au)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im)
            || !c2_stream_c2d_read((uint16_t)(c->images_offset
                + image * 32u), raw, sizeof(raw)))
            return fail(c, C2_STREAM_ERR_IO);
        directory_base = r16(im + 2); meta = r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h)))
            return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); eo = r16(h + 14);
        for (local = 0; local < ec; ++local) {
            uint32_t at; uint16_t length, first;
            if (!c2_stream_shelf_read(meta + eo + (uint32_t)local * 16u,
                                      e, sizeof(e))
                || !c2_stream_c2d_read((uint16_t)(c->entries_offset
                    + (directory_base + local) * 10u), de, sizeof(de)))
                return fail(c, C2_STREAM_ERR_IO);
            at = r24(e); length = r16(e + 3); first = r16(e + 5);
            if (de[0] != image || de[1] != e[7]
                || r24(raw + 23) || r16(raw + 26)
                || r24(raw + 18) > 0xffffUL
                || at > 0xffffUL - r24(raw + 18)
                || r16(de + 2) != (uint16_t)(r24(raw + 18) + at)
                || r16(de + 4) != length
                || r16(de + 6) != (uint16_t)(r16(im + 6) + first)
                || r16(de + 8) != c->generation)
                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->reserved = 0u; c->phase = 6u;
    return C2_STREAM_OK;
}
#endif

/* Validate normalized code headers, zero literal slots and export names. */
#if C2_STREAM_PHASE == 6
C2_SLICE(06) uint8_t c2_stream_phase_06(void *opaque) {
    c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16], co[7];
    uint16_t image, local, ec, eo, so, sb;
    uint32_t meta, code;
    if (!c || c->phase != 6u || c->error) return C2_STREAM_ERR_STATE;
    for (image = 0; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        code = r24(im + 10); meta = r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); eo = r16(h + 14); so = r16(h + 18); sb = r16(h + 20);
        for (local = 0; local < ec; ++local) {
            uint32_t at, payload; uint16_t length, name, name_length;
            if (!c2_stream_shelf_read(meta + eo + (uint32_t)local * 16u, e, sizeof(e)))
                return fail(c, C2_STREAM_ERR_IO);
            at = r24(e); length = r16(e + 3); name = r16(e + 8);
            if (!c2_stream_shelf_read(code + at, co, sizeof(co))) return fail(c, C2_STREAM_ERR_IO);
            if (co[0] != 0xb5u || co[1] != e[10] || co[6] != e[7]
                || (uint32_t)7u + (uint32_t)2u * co[6] + r16(co + 4) != length)
                return fail(c, C2_STREAM_ERR_ENTRY);
            {
                uint8_t zeros[16]; uint16_t done = 0, bytes = (uint16_t)(2u * co[6]), z;
                while (done < bytes) {
                    uint16_t n = (uint16_t)(bytes - done);
                    if (n > sizeof(zeros)) n = sizeof(zeros);
                    if (!c2_stream_shelf_read(code + at + 7u + done, zeros, n))
                        return fail(c, C2_STREAM_ERR_IO);
                    for (z = 0; z < n; ++z) if (zeros[z]) return fail(c, C2_STREAM_ERR_ENTRY);
                    done = (uint16_t)(done + n);
                }
            }
            if (name != 0xffffu
                && (!string_record_any(meta + so, sb, name, &name_length, &payload)
                    || !canonical_name(payload, name_length)))
                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->phase = 7; return C2_STREAM_OK;
}
#endif

/* Product-only coarse cut: validate normalized code structure and every zero
 * literal slot.  Export spelling belongs to 06b; no check is removed. */
#if C2_STREAM_PHASE == 17
C2_SLICE(06a) uint8_t c2_stream_phase_06a(void *opaque) {
    C2_INSTALL_DECODER_STAMP(LISP65_C2_PHASE_06A_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_DECODE_06A);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16], co[7];
    uint16_t image, local, ec, eo;
    uint32_t meta, code;
    if (!c || c->phase != 6u || c->error || c->reserved)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        c->reserved = LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD;
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        code = r24(im + 10); meta = r24(im + 13);
        c->reserved = LISP65_C2_PHASE_06A_CUT_METADATA_HEADER;
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); eo = r16(h + 14);
        for (local = 0; local < ec; ++local) {
            uint32_t at; uint16_t length;
            c->reserved = LISP65_C2_PHASE_06A_CUT_ENTRY_RECORD;
            if (!c2_stream_shelf_read(meta + eo + (uint32_t)local * 16u, e, sizeof(e)))
                return fail(c, C2_STREAM_ERR_IO);
            at = r24(e); length = r16(e + 3);
            c->reserved = LISP65_C2_PHASE_06A_CUT_CODE_HEADER;
            if (!c2_stream_shelf_read(code + at, co, sizeof(co))) return fail(c, C2_STREAM_ERR_IO);
            if (co[0] != 0xb5u || co[1] != e[10] || co[6] != e[7]
                || (uint32_t)7u + (uint32_t)2u * co[6] + r16(co + 4) != length)
                return fail(c, C2_STREAM_ERR_ENTRY);
            {
                uint8_t zeros[16]; uint16_t done = 0, bytes = (uint16_t)(2u * co[6]), z;
                while (done < bytes) {
                    uint16_t n = (uint16_t)(bytes - done);
                    if (n > sizeof(zeros)) n = sizeof(zeros);
                    c->reserved = LISP65_C2_PHASE_06A_CUT_LITERAL_BLOCK;
                    if (!c2_stream_shelf_read(code + at + 7u + done, zeros, n))
                        return fail(c, C2_STREAM_ERR_IO);
                    for (z = 0; z < n; ++z) if (zeros[z]) return fail(c, C2_STREAM_ERR_ENTRY);
                    done = (uint16_t)(done + n);
                }
            }
        }
    }
    c->reserved = LISP65_C2_PHASE_06A_COMPLETE;
    return C2_STREAM_OK;
}
#endif

/* Product-only coarse cut: validate exported spellings and publish phase 7. */
#if C2_STREAM_PHASE == 18
C2_SLICE(06b) uint8_t c2_stream_phase_06b(void *opaque) {
    C2_INSTALL_DECODER_STAMP(LISP65_C2_PHASE_06B_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16];
    uint16_t image, local, ec, eo, so, sb;
    uint32_t meta;
    if (!c || c->phase != 6u || c->error
        || c->reserved != LISP65_C2_PHASE_06A_COMPLETE)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        meta = r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        ec = r16(h + 10); eo = r16(h + 14); so = r16(h + 18); sb = r16(h + 20);
        for (local = 0; local < ec; ++local) {
            uint32_t payload; uint16_t name, name_length;
            if (!c2_stream_shelf_read(meta + eo + (uint32_t)local * 16u, e, sizeof(e)))
                return fail(c, C2_STREAM_ERR_IO);
            name = r16(e + 8);
            if (name != 0xffffu
                && (!string_record_any(meta + so, sb, name, &name_length, &payload)
                    || !canonical_name(payload, name_length)))
                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->reserved = 0; c->phase = 7; return C2_STREAM_OK;
}
#endif

/* Resolve every non-pair descriptor; pairs remain unpublished zero slots. */
#if C2_STREAM_PHASE == 7
C2_SLICE(07) uint8_t c2_stream_phase_07(void *opaque) {
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, so, sb, base, value, a;
    uint32_t meta, payload, arg1;
    if (!c || c->phase != 7u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        meta = r24(im + 13); base = r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        lc = r16(h + 12); lo = r16(h + 16); so = r16(h + 18); sb = r16(h + 20);
        for (i = 0; i < lc; ++i) {
            uint8_t kind;
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return fail(c, C2_STREAM_ERR_IO);
            kind = r[0]; a = r16(r + 2); arg1 = r24(r + 4);
            if (kind > 8u || r[1] || r[7]) return fail(c, C2_STREAM_ERR_DESCRIPTOR);
            if (kind == 7u) continue;
            switch (kind) {
            case 0: if (a || arg1) return fail(c, C2_STREAM_ERR_DESCRIPTOR); value = 0; break;
            case 1: if (a || arg1) return fail(c, C2_STREAM_ERR_DESCRIPTOR); value = 2; break;
            case 2: {
                int16_t n = (int16_t)a;
                if (n < -16384 || n > 16383 || arg1) return fail(c, C2_STREAM_ERR_DESCRIPTOR);
                value = (uint16_t)((uint16_t)n << 1 | 1u); break;
            }
            case 3:
                if (!string_record(meta + so, sb, arg1, a, &payload)
                    || !c2_stream_name_value(kind, payload, a, &value))
                    return fail(c, C2_STREAM_ERR_RESOLUTION);
                break;
            case 5: case 8:
                if (!string_record(meta + so, sb, arg1, a, &payload)
                    || !canonical_name(payload, a)
                    || !c2_stream_name_value(kind, payload, a, &value))
                    return fail(c, C2_STREAM_ERR_RESOLUTION);
                break;
            case 4:
                if (a >= r16(im + 4) || arg1) return fail(c, C2_STREAM_ERR_DESCRIPTOR);
                value = (uint16_t)(0xc000u + r16(im + 2) + a); break;
            case 6:
                if (arg1 || a > 255u) return fail(c, C2_STREAM_ERR_DESCRIPTOR);
                value = (uint16_t)(0x8000u | a); break;
            default: return fail(c, C2_STREAM_ERR_DESCRIPTOR);
            }
            w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset + (base + i) * 2u), b, 2))
                return fail(c, C2_STREAM_ERR_IO);
            ++c->resolution_cursor;
        }
    }
    c->phase = 8; return C2_STREAM_OK;
}
#endif

/* Resolve pair descriptors in ordinal order; backward-only references forbid cycles. */
#if C2_STREAM_PHASE == 8
C2_SLICE(08) uint8_t c2_stream_phase_08(void *opaque) {
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[4];
    uint16_t image, i, lc, lo, base, value, a;
    uint32_t meta, arg1;
    if (!c || c->phase != 8u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!c2_image_read(c, image, im))
            return fail(c, C2_STREAM_ERR_IO);
        meta = r24(im + 13); base = r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return fail(c, C2_STREAM_ERR_IO);
        lc = r16(h + 12); lo = r16(h + 16);
        for (i = 0; i < lc; ++i) {
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return fail(c, C2_STREAM_ERR_IO);
            if (r[0] != 7u) continue;
            a = r16(r + 2); arg1 = r24(r + 4);
            if (r[1] || r[7] || a >= i || arg1 >= i || arg1 > 0xffffUL)
                return fail(c, C2_STREAM_ERR_DESCRIPTOR);
            if (!c2_stream_c2d_read((uint16_t)(c->resolutions_offset + (base + a) * 2u), b, 2)
                || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                    + (base + (uint16_t)arg1) * 2u), b + 2, 2)
                || !c2_stream_pair_value(r16(b), r16(b + 2), &value))
                return fail(c, C2_STREAM_ERR_RESOLUTION);
            w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset + (base + i) * 2u), b, 2))
                return fail(c, C2_STREAM_ERR_IO);
            ++c->resolution_cursor;
        }
    }
    if (c->resolution_cursor != c->resolution_count)
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    c->phase = 9; return C2_STREAM_OK;
}
#endif

/* Publication marker: no callable is visible before all resolutions exist. */
#if C2_STREAM_PHASE == 9
C2_SLICE(09) uint8_t c2_stream_phase_09(void *opaque) {
    c2_stream_context *c = opaque; uint8_t h[4];
    if (!c || c->phase != 9u || c->error || c->resolution_cursor != c->resolution_count)
        return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read(0, h, sizeof(h)) || !magic4(h, "C2D"))
        return fail(c, C2_STREAM_ERR_IO);
    c->finished = 1; c->phase = 10; return C2_STREAM_OK;
}
#endif
