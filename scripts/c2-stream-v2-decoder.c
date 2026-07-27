/* C2D-v2 single-source roots layered over the proven C2I-v2 validator. */
#include "c2-stream-v2-decoder.h"
#include "obj.h"
#ifdef LISP65_C2_PRODUCT_CUT
#include "c2_product_runtime.h"
#include "c2_phase_scratch.h"
#define C2_INSTALL_V2_STAMP(slot) C2_INSTALL_TRACE_STAMP_SLOT(slot)
#else
#define C2_INSTALL_V2_STAMP(slot) ((void)0)
#define C2_FRAME_ATTRIBUTION_STAMP(index) ((void)0)
#endif

#ifndef C2_STREAM_V2_PHASE
#error "compile c2-stream-v2-decoder.c through a v2 phase wrapper"
#endif

#ifdef C2_STREAM_PRODUCT_V3
#define C2_V2_SLICE(n) __attribute__((noinline, section(".lisp65_rt_c2d_" #n)))
#else
#define C2_V2_SLICE(n) __attribute__((noinline, section(".lisp65_rt_l65m_" #n)))
#endif
#define C2_V2_LOCAL static __attribute__((unused))
#define C2_SESSION_SOURCE_TAG 0x800000UL

C2_V2_LOCAL uint16_t v2_r16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
C2_V2_LOCAL uint32_t v2_r24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}
C2_V2_LOCAL uint32_t v2_r32(const uint8_t *p) {
    return (uint32_t)v2_r16(p) | (uint32_t)v2_r16(p + 2) << 16;
}
C2_V2_LOCAL void v2_w16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
C2_V2_LOCAL uint8_t v2_magic4(const uint8_t *p, const char *s) {
    return p[0] == (uint8_t)s[0] && p[1] == (uint8_t)s[1]
        && p[2] == (uint8_t)s[2] && p[3] == (uint8_t)s[3];
}
C2_V2_LOCAL uint8_t v2_fail(c2_stream_context *c, uint8_t status) {
    c->error = status; return status;
}
C2_V2_LOCAL uint8_t v2_pointer(uint16_t value) {
    return value && value < 0x8000u && !(value & 1u);
}
C2_V2_LOCAL uint16_t v2_roots_offset(const c2_stream_context *c) {
#ifdef C2_STREAM_PRODUCT_V3
    return c->roots_offset;
#else
    return (uint16_t)(c->resolutions_offset + c->resolution_count * 2u);
#endif
}

#ifdef C2_STREAM_PRODUCT_V3
#define v2_image_read c2_stream_product_image_read
#define v2_string_record_any c2_stream_product_string_record_any
#define v2_string_record c2_stream_product_string_record
#define v2_canonical_name c2_stream_product_canonical_name
#ifndef LISP65_C2_LITE_COLD_EVICTION
#define v2_child_value c2_stream_product_child_value
#endif
#else
/* Normalize approved immutable-image records into the proven view. */
C2_V2_LOCAL uint8_t v2_image_read(c2_stream_context *c, uint16_t image,
                                  uint8_t out[20]) {
    return c2_stream_c2d_read(
        (uint16_t)(c->images_offset + image * 20u), out, 20u);
}
C2_V2_LOCAL uint8_t v2_string_record_any(uint32_t pool, uint16_t pool_bytes,
                                         uint32_t wanted, uint16_t *length,
                                         uint32_t *payload) {
    uint8_t b[2]; uint16_t cursor = 0, n;
    if (wanted > 0xffffUL) return 0;
    while (cursor < pool_bytes) {
        if ((uint16_t)(pool_bytes - cursor) < 2u
            || !c2_stream_shelf_read(pool + cursor, b, 2)) return 0;
        n = v2_r16(b);
        if (n > (uint16_t)(pool_bytes - cursor - 2u)) return 0;
        if (cursor == (uint16_t)wanted) {
            *length = n; *payload = pool + cursor + 2u; return 1;
        }
        cursor = (uint16_t)(cursor + 2u + n);
    }
    return 0;
}
C2_V2_LOCAL uint8_t v2_string_record(uint32_t pool, uint16_t pool_bytes,
                                     uint32_t wanted, uint16_t expected,
                                     uint32_t *payload) {
    uint16_t actual;
    return v2_string_record_any(pool, pool_bytes, wanted, &actual, payload)
        && actual == expected;
}
C2_V2_LOCAL uint8_t v2_canonical_name(uint32_t at, uint16_t length) {
    uint8_t block[16]; uint16_t done = 0, i;
    if (!length || length > 255u) return 0;
    while (done < length) {
        uint16_t n = (uint16_t)(length - done);
        if (n > sizeof(block)) n = sizeof(block);
        if (!c2_stream_shelf_read(at + done, block, n)) return 0;
        for (i = 0; i < n; ++i)
            if (block[i] < 0x21u || block[i] > 0x7eu) return 0;
        done = (uint16_t)(done + n);
    }
    return 1;
}
#endif

/* Validate the self-describing C2D-v2 header and its canonical root region. */
#if C2_STREAM_V2_PHASE == 0
C2_V2_SLICE(00) uint8_t c2_stream_phase_00(void *opaque) {
    c2_stream_context *c = opaque; uint8_t h[32]; uint32_t roots, expected;
    if (!c || c->phase || c->error || c->c2d_bytes < sizeof(h))
        return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read(0, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
    if (!v2_magic4(h, "C2D") || h[3] || h[4] != 2u
        || h[5] != 32u || h[6] != 20u || h[7] != 10u
        || v2_r16(h + 8) || !v2_r16(h + 10))
        return v2_fail(c, C2_STREAM_ERR_C2D);
    c->generation = v2_r16(h + 10); c->image_count = v2_r16(h + 12);
    c->entry_count = v2_r16(h + 14); c->resolution_count = v2_r16(h + 16);
    c->images_offset = v2_r16(h + 18); c->entries_offset = v2_r16(h + 20);
    c->resolutions_offset = v2_r16(h + 22); c->c2_root_count = v2_r16(h + 26);
    c->catalog_crc32 = v2_r32(h + 28);
    roots = (uint32_t)c->resolutions_offset + (uint32_t)c->resolution_count * 2u;
    expected = roots + (uint32_t)c->c2_root_count * 2u;
    if (!c->image_count || !c->c2_root_count || c->images_offset != 32u
        || c->entries_offset != (uint16_t)(32u + c->image_count * 20u)
        || c->resolutions_offset != (uint16_t)(c->entries_offset + c->entry_count * 10u)
        || roots > 0xffffUL || expected > 0xffffUL
        || expected != v2_r16(h + 24) || expected != c->c2d_bytes)
        return v2_fail(c, C2_STREAM_ERR_C2D);
    c->phase = 1; return C2_STREAM_OK;
}
#endif

/* Assign every heap descriptor its immutable canonical root ordinal. */
#if C2_STREAM_V2_PHASE == 7
C2_V2_SLICE(07) uint8_t c2_stream_phase_07(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_07_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, base, root = c->root_first;
    uint32_t meta;
    if (!c || c->phase != 7u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        for (i = 0; i < lc; ++i) {
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            if (r[0] > 8u || r[1] || r[7]) return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
            if (r[0] == 3u || r[0] == 7u) {
                if (root >= c->c2_root_count) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
                v2_w16(b, root++);
                if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset
                    + (base + i) * 2u), b, 2)) return v2_fail(c, C2_STREAM_ERR_IO);
            }
        }
    }
    if (root != c->c2_root_count) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
    c->c2_root_cursor = root; c->phase = 8; return C2_STREAM_OK;
}
#endif

/* Resolve immediate, entry and native values without allocation. */
#if C2_STREAM_V2_PHASE == 8
C2_V2_SLICE(08) uint8_t c2_stream_phase_08(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_08_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, base, value, a, directory_ordinal;
    uint32_t meta, arg1;
    if (!c || c->phase != 8u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        for (i = 0; i < lc; ++i) {
            uint8_t kind;
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            kind = r[0]; a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (kind > 8u || r[1] || r[7]) return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
            if (kind == 3u || kind == 5u || kind == 7u || kind == 8u) continue;
            switch (kind) {
            case 0: if (a || arg1) return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR); value = 0; break;
            case 1: if (a || arg1) return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR); value = 2; break;
            case 2: {
                int16_t n = (int16_t)a;
                if (n < -16384 || n > 16383 || arg1)
                    return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
                value = (uint16_t)((uint16_t)n << 1 | 1u); break;
            }
            case 4:
                if (a >= v2_r16(im + 4) || arg1) return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
                directory_ordinal = (uint16_t)(v2_r16(im + 2) + a);
                if (directory_ordinal >= c->entry_count)
                    return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
#ifdef LISP65_C2_NESTED_APPEND_V5
                if (im[1] == 2u)
                    directory_ordinal = (uint16_t)(directory_ordinal + 2048u);
#endif
                value = (uint16_t)MK_BCODE(directory_ordinal);
                if (!IS_BCODE((obj)value) || BCODE_IDX((obj)value) != directory_ordinal)
                    return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
                break;
            case 6:
                if (arg1 || a > 255u) return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
                value = (uint16_t)(0x8000u | a); break;
            default: return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
            }
            v2_w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset + (base + i) * 2u), b, 2))
                return v2_fail(c, C2_STREAM_ERR_IO);
            ++c->resolution_cursor;
        }
    }
    c->phase = 9; return C2_STREAM_OK;
}
#endif

/* Resolve strings and publish them through the sole canonical root region. */
#if C2_STREAM_V2_PHASE == 9
C2_V2_SLICE(09) uint8_t c2_stream_phase_09(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_09_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_DECODE_09);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, so, sb, base, value, a, root;
    uint32_t meta, payload, arg1;
    if (!c || c->phase != 9u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        so = v2_r16(h + 18); sb = v2_r16(h + 20);
        for (i = 0; i < lc; ++i) {
            uint8_t kind;
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            kind = r[0];
            if (kind != 3u) continue;
            a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (r[1] || r[7] || !v2_string_record(meta + so, sb, arg1, a, &payload)
                || !c2_stream_name_value(kind, payload, a, &value))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            if (!v2_pointer(value)
                || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                    + (base + i) * 2u), b, 2))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            root = v2_r16(b);
            if (root >= c->c2_root_count) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            v2_w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(v2_roots_offset(c) + root * 2u), b, 2)
                || !c2_stream_gc_checkpoint(v2_roots_offset(c), c->c2_root_count))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            ++c->resolution_cursor;
        }
    }
    c->phase = 10; return C2_STREAM_OK;
}
#endif

/* Resolve exported-call and general-symbol spellings through one interner. */
#if C2_STREAM_V2_PHASE == 10
C2_V2_SLICE(10) uint8_t c2_stream_phase_10(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_10_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, so, sb, base, value, a;
    uint32_t meta, payload, arg1;
    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        so = v2_r16(h + 18); sb = v2_r16(h + 20);
        for (i = 0; i < lc; ++i) {
            uint8_t kind;
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            kind = r[0];
            if (kind != 5u && kind != 8u) continue;
            a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (r[1] || r[7] || !v2_string_record(meta + so, sb, arg1, a, &payload)
                || !v2_canonical_name(payload, a)
                || !c2_stream_name_value(kind, payload, a, &value))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            v2_w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset
                + (base + i) * 2u), b, 2)) return v2_fail(c, C2_STREAM_ERR_IO);
            ++c->resolution_cursor;
        }
    }
    c->phase = 11; return C2_STREAM_OK;
}
#endif

#if !defined(C2_STREAM_PRODUCT_V3) || defined(LISP65_C2_LITE_COLD_EVICTION)
C2_V2_LOCAL uint8_t v2_child_value(c2_stream_context *c, uint32_t meta,
                                   uint16_t lo, uint16_t base, uint16_t local,
                                   uint16_t *value) {
#ifdef LISP65_C2_LITE_COLD_EVICTION
    uint8_t b[2]; uint16_t word, root;
    (void)meta; (void)lo;
    if (!c || !value
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
            + (base + local) * 2u), b, 2u)) return 0;
    word = v2_r16(b);
    if (word && word < 0x8000u && !(word & 1u)) {
        root = (uint16_t)((word >> 1) - 1u);
        if (root >= c->c2_root_count
            || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c)
                + root * 2u), b, 2u)) return 0;
        word = v2_r16(b);
        if (!v2_pointer(word)) return 0;
    }
    *value = word; return 1;
#else
    uint8_t descriptor[8], b[2]; uint16_t word;
    if (!c2_stream_shelf_read(meta + lo + (uint32_t)local * 8u,
                              descriptor, sizeof(descriptor))
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
            + (base + local) * 2u), b, 2)) return 0;
    word = v2_r16(b);
    if (descriptor[0] == 3u || descriptor[0] == 7u) {
        if (word >= c->c2_root_count
            || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c) + word * 2u), b, 2))
            return 0;
        word = v2_r16(b);
        if (!v2_pointer(word)) return 0;
    }
    *value = word; return 1;
#endif
}
#endif

/* Resolve pairs in ordinal order; backward-only references make this iterative. */
#if C2_STREAM_V2_PHASE == 11
C2_V2_SLICE(11) uint8_t c2_stream_phase_11(void *opaque) {
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, base, value, car, cdr, a, root;
    uint32_t meta, arg1;
    if (!c || c->phase != 11u || c->error) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        for (i = 0; i < lc; ++i) {
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            if (r[0] != 7u) continue;
            a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (r[1] || r[7] || a >= i || arg1 >= i || arg1 > 0xffffUL
                || !v2_child_value(c, meta, lo, base, a, &car)
                || !v2_child_value(c, meta, lo, base, (uint16_t)arg1, &cdr)
                || !c2_stream_pair_value(car, cdr, &value) || !v2_pointer(value)
                || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                    + (base + i) * 2u), b, 2))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            root = v2_r16(b);
            if (root >= c->c2_root_count) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            v2_w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(v2_roots_offset(c) + root * 2u), b, 2)
                || !c2_stream_gc_checkpoint(v2_roots_offset(c), c->c2_root_count))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            ++c->resolution_cursor;
        }
    }
    if (c->resolution_cursor != c->resolution_count)
        return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
    c->phase = 12; return C2_STREAM_OK;
}
#endif

/* Product-only semantic cut for phase 11.  The first half proves every pair
 * descriptor structurally while the source image is immutable, then publishes
 * only the cutpoint marker.  No source pointer or partially allocated value
 * crosses the transported-overlay boundary. */
#if C2_STREAM_V2_PHASE == 14
C2_V2_SLICE(11a) uint8_t c2_stream_phase_11a(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_11A_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8];
    uint16_t image, i, lc, lo, a; uint32_t meta, arg1;
    if (!c || c->phase != 11u || c->error || c->reserved)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13);
        if (!c2_stream_shelf_read(meta, h, sizeof(h)))
            return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        for (i = 0; i < lc; ++i) {
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u,
                                      r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            if (r[0] != 7u) continue;
            a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (r[1] || r[7] || a >= i || arg1 >= i || arg1 > 0xffffUL)
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
        }
    }
    c->reserved = 0x11u; return C2_STREAM_OK;
}
#endif

/* Product-only second half: consume only the structurally authenticated,
 * immutable pair domain, allocate in backward-reference order, and publish
 * each value through its sole root before the next allocation. */
#if C2_STREAM_V2_PHASE == 15
C2_V2_SLICE(11b) uint8_t c2_stream_phase_11b(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_11B_SLOT);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, base, value, car, cdr, a, root;
    uint32_t meta, arg1;
    if (!c || c->phase != 11u || c->error || c->reserved != 0x11u)
        return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h)))
            return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        for (i = 0; i < lc; ++i) {
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u,
                                      r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            if (r[0] != 7u) continue;
            a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (!v2_child_value(c, meta, lo, base, a, &car)
                || !v2_child_value(c, meta, lo, base, (uint16_t)arg1, &cdr)
                || !c2_stream_pair_value(car, cdr, &value) || !v2_pointer(value)
                || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                    + (base + i) * 2u), b, 2))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            root = v2_r16(b);
            if (root >= c->c2_root_count)
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            v2_w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(v2_roots_offset(c)
                    + root * 2u), b, 2)
                || !c2_stream_gc_checkpoint(v2_roots_offset(c), c->c2_root_count))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            ++c->resolution_cursor;
        }
    }
    if (c->resolution_cursor != c->resolution_count)
        return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
    c->reserved = 0; c->phase = 12; return C2_STREAM_OK;
}
#endif

/* Recheck canonical membership and every published heap value before commit. */
#if C2_STREAM_V2_PHASE == 12
C2_V2_SLICE(12) uint8_t c2_stream_phase_12(void *opaque) {
    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_12_SLOT);
    C2_FRAME_ATTRIBUTION_STAMP(LISP65_C2_FRAME_ATTR_DECODE_12);
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8], b[2];
    uint16_t image, i, lc, lo, base, directory_base;
    uint16_t root = c->root_first, word, expected, local;
    uint32_t meta;
    if (!c || c->phase != 12u || c->error
        || c->resolution_cursor != c->resolution_count) return C2_STREAM_ERR_STATE;
    for (image = c->image_first; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im))
            return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        directory_base = v2_r16(im + 2);
        if (!c2_stream_shelf_read(meta, h, sizeof(h))) return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        for (i = 0; i < lc; ++i) {
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            if (!c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                + (base + i) * 2u), b, 2)) return v2_fail(c, C2_STREAM_ERR_IO);
            word = v2_r16(b);
            if (r[0] == 4u) {
                local = v2_r16(r + 2);
                if (local >= v2_r16(im + 4)
                    || (uint16_t)(directory_base + local) >= c->entry_count)
                    return v2_fail(c, C2_STREAM_ERR_DESCRIPTOR);
                expected = (uint16_t)MK_BCODE((uint16_t)(directory_base + local
#ifdef LISP65_C2_NESTED_APPEND_V5
                    + (im[1] == 2u ? 2048u : 0u)
#endif
                    ));
                if (word != expected || !IS_BCODE((obj)word)
                    || BCODE_IDX((obj)word) != (uint16_t)(directory_base + local))
                    return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
                continue;
            }
            if (r[0] != 3u && r[0] != 7u) continue;
            if (word != root || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c)
                + word * 2u), b, 2) || !v2_pointer(v2_r16(b)))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            ++root;
        }
    }
    if (root != c->c2_root_count || root != c->c2_root_cursor)
        return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
    c->finished = 1; c->phase = 13; return C2_STREAM_OK;
}
#endif

/* Materialize one entry's ordinary literal table from tagged resolutions. */
#if C2_STREAM_V2_PHASE == 13
#if defined(C2_STREAM_PRODUCT_V3) && defined(LISP65_C2_DIRECT_HOT_REFILL)
C2_V2_SLICE(13) uint8_t c2_stream_phase_13(void *opaque) {
    c2_stream_materialize_context *work = opaque;
    if (!work) return C2_STREAM_ERR_STATE;
    return c2_stream_product_materialize_entry(
        work->stream, work->directory_ordinal, work->hot_values,
        work->hot_capacity, &work->hot_count);
}

uint8_t c2_stream_materialize_entry(c2_stream_context *c, uint16_t ordinal,
        uint16_t *hot, uint8_t capacity, uint8_t *count) {
    return c2_stream_product_materialize_entry(
        c, ordinal, hot, capacity, count);
}
#else
#ifdef C2_STREAM_PRODUCT_V3
static uint8_t c2_stream_materialize_entry_impl(c2_stream_context *c,
#else
C2_V2_SLICE(13) uint8_t c2_stream_materialize_entry(c2_stream_context *c,
#endif
        uint16_t ordinal, uint16_t *hot, uint8_t capacity, uint8_t *count) {
    uint8_t de[10], im[20], h[24], e[16];
    uint16_t image, local, meta_entries, meta_literals, first, base;
    uint32_t meta;
    if (!c || !hot || !count || !c->finished || c->phase != 13u
        || ordinal >= c->entry_count) return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read((uint16_t)(c->entries_offset + ordinal * 10u), de, sizeof(de)))
        return C2_STREAM_ERR_IO;
    image = de[0]; local = v2_r16(de + 2);
    if (image >= c->image_count
        || !v2_image_read(c, image, im))
        return C2_STREAM_ERR_ENTRY;
    meta = v2_r24(im + 13); base = v2_r16(im + 6);
    if (!c2_stream_shelf_read(meta, h, sizeof(h))) return C2_STREAM_ERR_IO;
    meta_entries = v2_r16(h + 14); meta_literals = v2_r16(h + 16);
    if (local >= v2_r16(h + 10)
        || !c2_stream_shelf_read(meta + meta_entries + (uint32_t)local * 16u,
                                 e, sizeof(e))) return C2_STREAM_ERR_ENTRY;
    first = v2_r16(e + 5); *count = e[7];
    if (*count > capacity || (uint16_t)(first + *count) > v2_r16(h + 12))
        return C2_STREAM_ERR_ENTRY;
    {
        uint8_t descriptor[8], b[2];
        uint16_t i, word;
    for (i = 0; i < *count; ++i) {
        if (!c2_stream_shelf_read(meta + meta_literals + (uint32_t)(first + i) * 8u,
                                  descriptor, sizeof(descriptor))
            || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                + (base + first + i) * 2u), b, 2)) return C2_STREAM_ERR_IO;
        word = v2_r16(b);
        if (descriptor[0] == 3u || descriptor[0] == 7u) {
            if (word >= c->c2_root_count
                || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c) + word * 2u), b, 2)
                || !v2_pointer(v2_r16(b))) return C2_STREAM_ERR_RESOLUTION;
            word = v2_r16(b);
        }
        hot[i] = word;
    }
    return C2_STREAM_OK;
    }
}
#ifdef C2_STREAM_PRODUCT_V3
C2_V2_SLICE(13) uint8_t c2_stream_phase_13(void *opaque) {
    c2_stream_materialize_context *work = opaque;
    uint8_t status;
    if (!work) return C2_STREAM_ERR_STATE;
    status = c2_stream_materialize_entry_impl(
        work->stream, work->directory_ordinal, work->hot_values,
        work->hot_capacity, &work->hot_count);
    return status;
}

/* Keep the direct entry available for product-shaped host fixtures.  The
 * device product reaches the implementation exclusively through phase 13. */
uint8_t c2_stream_materialize_entry(c2_stream_context *c, uint16_t ordinal,
        uint16_t *hot, uint8_t capacity, uint8_t *count) {
    return c2_stream_materialize_entry_impl(c, ordinal, hot, capacity, count);
}
#endif
#endif
#endif
