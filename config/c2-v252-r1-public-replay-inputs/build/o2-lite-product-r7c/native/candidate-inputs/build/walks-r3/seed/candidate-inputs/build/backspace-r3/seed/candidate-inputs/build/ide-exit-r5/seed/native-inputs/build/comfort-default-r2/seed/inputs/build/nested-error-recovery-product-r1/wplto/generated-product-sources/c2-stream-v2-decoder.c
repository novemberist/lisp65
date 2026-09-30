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
                v2_w16(b, (uint16_t)((root++ + 1u) << 1));
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
            if (!root || (root & 1u) || root > 0x0c00u) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            root = (uint16_t)((root >> 1) - 1u);
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
        if (!word || (word & 1u) || word > 0x0c00u
            || (word = (uint16_t)((word >> 1) - 1u)) >= c->c2_root_count
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
            if (!root || (root & 1u) || root > 0x0c00u) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            root = (uint16_t)((root >> 1) - 1u);
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
            if (!root || (root & 1u) || root > 0x0c00u) return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            root = (uint16_t)((root >> 1) - 1u);
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
            if (word != (uint16_t)((root + 1u) << 1)
                || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c)
                + root * 2u), b, 2) || !v2_pointer(v2_r16(b)))
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

/* Boot-time name index, shape C.  Two new boot-only decoder phases share one
 * transient owner in the Bank-5 free tail.  Decoder phase 10 above is NOT
 * touched: it keeps resolving every session append, every `require` and every
 * interactive interning on the historical linear path, so `image_first != 0`
 * always takes the unchanged code.  Phase 10a walks the same records and only
 * records name coordinates; phase 10b builds the index once and resolves the
 * queue IN QUEUE ORDER, which is the record walk order, so new symbols are
 * created at exactly the indices the unsplit walk produces and the three
 * Bank-5 symbol tables, the length-class table and the Bank-1 name pool come
 * out identical.
 *
 * The owner holds no truth.  A tag match is never taken as equality: the full
 * canonical name decides, compared against the stored spelling and never
 * through `sym_name_scratch`, which the confirmation itself overwrites.
 * Absence is provable only because the symbol count is caught up first.  Every
 * read of the owner leaves the bank through the convergence seam, reached by
 * the one exported, owner-confined entry `c2_boot_name_index_read` (the mapped
 * facade itself is static, beside the symbol-table readers); every write uses
 * the ordinary DMA facade.  The
 * resident driver invalidates the whole owner on return and on abort. */
#if C2_STREAM_V2_PHASE == 16 || C2_STREAM_V2_PHASE == 17

#include "c2_kernal_facade.h"
/* The mapped facade that reaches the convergence seam is static in
 * src/c2_platform_dma.c, beside every historical Bank-5 table reader.  This
 * owner gets its own narrow exported seam there instead; it confines the offset
 * to the owner and aborts on anything outside it, so no read here needs an
 * error return. */
uint8_t c2_boot_name_index_read(uint16_t offset, uint8_t *destination,
                                uint8_t length);

#define C2_BNX_BANK 5u
#define C2_BNX_INDEX 0xde80u
#define C2_BNX_SLOTS 1024u
#define C2_BNX_QUEUE (uint16_t)(C2_BNX_INDEX + C2_BNX_SLOTS * 2u)
#define C2_BNX_ENTRY 6u
#define C2_BNX_BATCH 1024u
#define C2_BNX_HEAD (uint16_t)(C2_BNX_QUEUE + C2_BNX_BATCH * C2_BNX_ENTRY)
#define C2_BNX_HEAD_BYTES 10u
#define C2_BNX_DONE 0xffffu

/* Slice placement without `noinline`: these helpers are paid for in the slice
 * that uses them, and stay inlinable there. */
#ifdef C2_STREAM_PRODUCT_V3
#define C2_BNX_SECTION(n) __attribute__((section(".lisp65_rt_c2d_" n)))
#else
#define C2_BNX_SECTION(n) __attribute__((section(".lisp65_rt_l65m_" n)))
#endif
#if C2_STREAM_V2_PHASE == 17
#define C2_BNX_HERE C2_BNX_SECTION("10a")
#else
#define C2_BNX_HERE C2_BNX_SECTION("10b")
#endif

/* Resumption state lives in the transient owner, NOT in c2_stream_context:
 * that context is pinned at 46 bytes by a host gate, is a fixed Bank-0 BSS
 * owner, is nested in the Append work area, and two functions hold one on the
 * soft-frame stack where the stack-cliff known issue lives.  Header layout:
 *   [0..1] next image for the collecting walk, C2_BNX_DONE when complete
 *   [2..3] next literal record inside that image -- the batch boundary does
 *          NOT fall on an image boundary: the measured plane holds 766, 363,
 *          124, 27, 0 and 284 kind-5/8 records, so the first batch of 1,024
 *          ends inside the second image
 *   [4..5] queue entries pending in the current batch
 *   [6..7] symbols already present in the index
 *   [8]    index-built flag
 *   [9]    reserved, always zero -- a non-zero byte fails the phase closed */
/* Both phases read and write the header, and neither slice has room for its
 * own copy of the seam, so it is resident and paid once (src/c2_product_runtime.c
 * -- the same owner that invalidates the header on return and on abort). */
void c2_boot_name_index_head_get(uint8_t *head);
void c2_boot_name_index_head_put(const uint8_t *head);
#define v2_bnx_head_get c2_boot_name_index_head_get
#define v2_bnx_head_put c2_boot_name_index_head_put
#endif

/* Boot-only collecting phase.  The record walk of decoder phase 10 with the
 * interning and the resolution write replaced by one six-byte queue entry.
 * Nothing is interned here, so the collecting walk creates no symbol on its
 * own authority and an abort before the resolving phase creates none at all --
 * that is the one stated behavioural difference from today's abort path. */
#if C2_STREAM_V2_PHASE == 17
/* One queue entry: 24-bit shelf payload offset, name length, resolution slot. */
__attribute__((noinline)) static void v2_bnx_post(uint16_t n, uint32_t payload,
                                    uint16_t length, uint16_t slot) {
    uint8_t e[C2_BNX_ENTRY];
    e[0] = (uint8_t)payload; e[1] = (uint8_t)(payload >> 8);
    e[2] = (uint8_t)(payload >> 16); e[3] = (uint8_t)length;
    v2_w16(e + 4, slot);
    c2_facade_c2_dma((uint16_t)(uintptr_t)e, 0u,
                     (uint16_t)(C2_BNX_QUEUE + n * C2_BNX_ENTRY),
                     C2_BNX_BANK, C2_BNX_ENTRY);
}
C2_V2_SLICE(10a) uint8_t c2_stream_phase_10a(void *opaque) {
    c2_stream_context *c = opaque;
    uint8_t im[20], h[24], r[8], head[C2_BNX_HEAD_BYTES];
    uint16_t image, i, lc, lo, so, sb, base, a, queued = 0, resume, cursor;
    uint32_t meta, payload, arg1;
    if (!c || c->phase != 10u || c->error || c->image_first)
        return C2_STREAM_ERR_STATE;
    v2_bnx_head_get(head);
    /* A pending batch means the resolving phase did not run: fail closed
     * rather than overwrite queue entries that own resolutions. */
    if (head[9] || v2_r16(head + 4) || v2_r16(head) == C2_BNX_DONE)
        return v2_fail(c, C2_STREAM_ERR_STATE);
    resume = v2_r16(head); cursor = v2_r16(head + 2);
    for (image = resume; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im)) return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h)))
            return v2_fail(c, C2_STREAM_ERR_IO);
        lc = v2_r16(h + 12); lo = v2_r16(h + 16);
        so = v2_r16(h + 18); sb = v2_r16(h + 20);
        for (i = (image == resume) ? cursor : 0u; i < lc; ++i) {
            uint8_t kind;
            if (!c2_stream_shelf_read(meta + lo + (uint32_t)i * 8u, r, sizeof(r)))
                return v2_fail(c, C2_STREAM_ERR_IO);
            kind = r[0];
            if (kind != 5u && kind != 8u) continue;
            a = v2_r16(r + 2); arg1 = v2_r24(r + 4);
            if (r[1] || r[7] || !v2_string_record(meta + so, sb, arg1, a, &payload)
                || !v2_canonical_name(payload, a))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            /* The batch is full: suspend on THIS record, which is not yet
             * queued, and let the resolving phase drain.  Suspending inside an
             * image is what removes the queue's dependence on any per-image
             * record bound: no admission assumption is left in the runtime. */
            if (queued == C2_BNX_BATCH) {
                v2_w16(head, image); v2_w16(head + 2, i);
                v2_w16(head + 4, queued);
                v2_bnx_head_put(head);
                return C2_STREAM_OK;    /* phase stays 10: resume after 10b */
            }
            v2_bnx_post(queued++, payload, a, (uint16_t)(base + i));
        }
    }
    v2_w16(head, C2_BNX_DONE); v2_w16(head + 2, 0u);
    v2_w16(head + 4, queued);
    v2_bnx_head_put(head);
    return C2_STREAM_OK;
}
#endif

/* Boot-only resolving phase. */
#if C2_STREAM_V2_PHASE == 16
#include "symbol.h"
#include "mem.h"
/* `intern` keeps its own linear path for append, require and interactive
 * interning; the resolving phase creates a symbol it has already proven
 * absent, so it needs the creation half on its own. */
extern obj sym_create(const char *name);

__attribute__((noinline)) uint16_t v2_bnx_hash(const char *p) {
    uint16_t h = 0;
    while (*p) h = (uint16_t)((uint16_t)(h << 5) + h) ^ (uint8_t)*p++;
    return h;
}
C2_BNX_HERE static uint16_t v2_bnx_get(uint16_t slot) {
    uint8_t b[2];
    (void)c2_boot_name_index_read((uint16_t)(C2_BNX_INDEX + slot * 2u), b, 2u);
    return v2_r16(b);
}
__attribute__((noinline)) void v2_bnx_put(uint16_t slot, uint16_t word) {
    uint8_t b[2];
    v2_w16(b, word);
    c2_facade_c2_dma((uint16_t)(uintptr_t)b, 0u,
                     (uint16_t)(C2_BNX_INDEX + slot * 2u), C2_BNX_BANK, 2u);
}
/* Returns the symbol, or NIL with *slot at the first empty probe slot.  A tag
 * match is never taken as equality: the full canonical name decides.  This
 * probe does not fit beside the phase body inside the 1,792-byte slice; it is
 * the card's named resident spend. */
__attribute__((noinline)) obj v2_bnx_find(const char *name, uint16_t h,
                                                 uint16_t *slot) {
    uint16_t s = h & (C2_BNX_SLOTS - 1u), word, idx;
    uint16_t left = C2_BNX_SLOTS;
    *slot = 0xffffu;
    while (left--) {
        word = v2_bnx_get(s);
        if (!word) { *slot = s; return NIL; }
        if (!(word & 0x3ffu) || (word & 0x3ffu) > sym_count())
            return NIL;
        idx = (uint16_t)((word & 0x3ffu) - 1u);
        if ((uint8_t)(word >> 10) == (uint8_t)(h >> 10 & 0x3fu)) {
            const char *known = symname(MK_SYMI(idx)); uint8_t i = 0;
            while (known[i] == name[i] && name[i]) ++i;
            if (known[i] == name[i]) return MK_SYMI(idx);
        }
        s = (uint16_t)((s + 1u) & (C2_BNX_SLOTS - 1u));
    }
    return NIL;
}
/* Absence is only provable while every symbol below *indexed is in the index. */
__attribute__((noinline)) void v2_bnx_catch_up(uint16_t *indexed) {
    char name[LISP65_SYMBOL_NAME_BUFFER]; uint16_t slot, h; uint8_t i;
    while (*indexed < sym_count()) {
        const char *known = symname(MK_SYMI(*indexed));
        for (i = 0; (name[i] = known[i]) != 0; ++i) {}
        h = v2_bnx_hash(name);
        if (v2_bnx_find(name, h, &slot) != NIL) {
            ++*indexed; continue;
        }
        if (slot == 0xffffu) { *indexed = 0xffffu; return; }
        v2_bnx_put(slot, (uint16_t)((*indexed + 1u)
            | (uint16_t)(h >> 10 & 0x3fu) << 10));
        ++*indexed;
    }
}
C2_V2_SLICE(10b) uint16_t v2_bnx_build(void) {
    uint16_t h, indexed = 0;
    for (h = 0; h < C2_BNX_SLOTS; ++h) v2_bnx_put(h, 0u);
    v2_bnx_catch_up(&indexed);
    return indexed;
}
C2_V2_SLICE(10b) uint8_t c2_stream_phase_10b(void *opaque) {
    c2_stream_context *c = opaque;
    uint8_t e[C2_BNX_ENTRY], b[2], head[C2_BNX_HEAD_BYTES];
    char name[LISP65_SYMBOL_NAME_BUFFER];
    uint16_t n, count, indexed, h, slot; uint32_t payload; obj s;
    if (!c || c->phase != 10u || c->error || c->image_first)
        return C2_STREAM_ERR_STATE;
    v2_bnx_head_get(head);
    count = v2_r16(head + 4);
    if (head[9] || count > C2_BNX_BATCH) return v2_fail(c, C2_STREAM_ERR_STATE);
    if (!head[8]) { v2_w16(head + 6, v2_bnx_build()); head[8] = 1u; }
    indexed = v2_r16(head + 6);
    for (n = 0; n < count; ++n) {
        (void)c2_boot_name_index_read(
            (uint16_t)(C2_BNX_QUEUE + n * C2_BNX_ENTRY), e, C2_BNX_ENTRY);
        payload = v2_r24(e);
        /* The query name lives here, never in sym_name_scratch: confirming a
         * hit calls symname(), which overwrites that buffer. */
        if (!e[3] || e[3] > LISP65_SYMBOL_NAME_MAX
            || !c2_stream_shelf_read(payload, (uint8_t *)name, e[3]))
            return v2_fail(c, C2_STREAM_ERR_IO);
        name[e[3]] = 0;
        v2_bnx_catch_up(&indexed);
        if (indexed == 0xffffu)
            return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
        h = v2_bnx_hash(name);
        s = v2_bnx_find(name, h, &slot);
        if (s == NIL) {
            if (slot == 0xffffu)
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            s = sym_create(name);
            if (s == NIL || mem_oom)
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            if (SYMI_IDX(s) == indexed) {
                v2_bnx_put(slot, (uint16_t)((indexed + 1u)
                    | (uint16_t)(h >> 10 & 0x3fu) << 10));
                ++indexed;
            }
        }
        v2_w16(b, (uint16_t)s);
        if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset
            + v2_r16(e + 4) * 2u), b, 2)) return v2_fail(c, C2_STREAM_ERR_IO);
        ++c->resolution_cursor;
    }
    v2_w16(head + 4, 0u);
    v2_w16(head + 6, indexed);
    /* Last batch: leave phase 10 so the resident driver's alternation ends.
     * The driver invalidates the owner on that return and on abort. */
    if (v2_r16(head) == C2_BNX_DONE) c->phase = 11;
    v2_bnx_head_put(head);
    return C2_STREAM_OK;
}
#endif
