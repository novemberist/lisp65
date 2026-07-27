/* Cursor-split product transport for the C2 decoder.
 *
 * Each exported entry is a runtime-overlay resident.  Scratch and cursors are
 * deliberately resident: they are the small facade state that survives a
 * transport, while all validation/allocation work lives in the banked slice.
 */
#include "c2_product_decoder.h"

#ifdef LISP65_C2_PRODUCT_CUT

#ifndef C2_STREAM_PRODUCT_V3
#define C2_STREAM_PRODUCT_V3 1
#endif
#include "c2-stream-v2-decoder.h"

#define C2_SECTION(name) __attribute__((noinline, section(".lisp65_rt_c2d_" name)))
#define C2_INLINE static __attribute__((always_inline)) inline
#define C2_SESSION_SOURCE_TAG 0x800000UL

typedef struct {
    c2_stream_context *owner;
    c2_stream_materialize_context *materialize;
    uint16_t image;
    uint16_t local;
    uint16_t root;
    uint16_t base;
    uint16_t count;
    uint16_t first;
    uint16_t strings;
    uint16_t string_bytes;
    uint16_t name;
    uint16_t value;
    uint16_t car_value;
    uint16_t cdr_value;
    uint32_t meta;
    uint32_t payload;
    uint32_t arg1;
    uint8_t loaded;
    uint8_t pending;
    uint8_t s[32];
    uint8_t im[20];
    uint8_t h[24];
    uint8_t e[16];
    uint8_t d[20];
    uint8_t de[10];
    uint8_t r[8];
    uint8_t b[4];
} c2_product_decode_work;

static c2_product_decode_work work;

C2_INLINE uint16_t r16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
C2_INLINE uint32_t r24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}
C2_INLINE void w16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
C2_INLINE uint8_t fail(c2_stream_context *c, uint8_t status) {
    c->error = status; return status;
}
C2_INLINE uint16_t roots_offset(const c2_stream_context *c) {
    return c->roots_offset;
}
C2_INLINE uint8_t pointer_value(uint16_t value) {
    return (uint8_t)((value & 0x8000u) == 0u && (value & 1u) == 0u && value != 0u);
}

C2_INLINE uint8_t image_read(c2_stream_context *c, uint16_t image, uint8_t out[20]) {
    uint8_t raw[32]; uint32_t tag, code, meta;
    if (image >= c->image_count
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
        || raw[3] || r16(raw + 4) != c->generation) return 0;
    out[0] = (uint8_t)image; out[1] = raw[0];
    w16(out + 2, r16(raw + 6)); w16(out + 4, r16(raw + 8));
    w16(out + 6, r16(raw + 10)); w16(out + 8, r16(raw + 12));
    tag = raw[0] ? C2_SESSION_SOURCE_TAG : 0u;
    code = r24(raw + 18) | tag; meta = r24(raw + 23) | tag;
    out[10] = (uint8_t)code; out[11] = (uint8_t)(code >> 8);
    out[12] = (uint8_t)(code >> 16);
    out[13] = (uint8_t)meta; out[14] = (uint8_t)(meta >> 8);
    out[15] = (uint8_t)(meta >> 16);
    w16(out + 16, r16(raw + 21)); w16(out + 18, r16(raw + 26));
    return 1;
}

C2_INLINE uint8_t string_record(uint32_t pool, uint16_t bytes, uint32_t wanted,
                             uint16_t expected, uint32_t *payload) {
    uint8_t b[2]; uint16_t cursor = 0, n;
    if (wanted > 0xffffUL) return 0;
    while (cursor < bytes) {
        if ((uint16_t)(bytes - cursor) < 2u
            || !c2_stream_shelf_read(pool + cursor, b, 2u)) return 0;
        n = r16(b);
        if (n > (uint16_t)(bytes - cursor - 2u)) return 0;
        if (cursor == (uint16_t)wanted) {
            if (n != expected) return 0;
            *payload = pool + cursor + 2u; return 1;
        }
        cursor = (uint16_t)(cursor + 2u + n);
    }
    return 0;
}

C2_INLINE uint8_t canonical_name(uint32_t at, uint16_t length) {
    uint8_t block[16]; uint16_t done = 0, i;
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

/* Phase 2: transport one shelf/C2D record pair, then validate it. */
C2_SECTION("02a") uint8_t c2_product_decode_02a(void *opaque) {
    c2_stream_context *c = opaque;
    if (!c || c->phase != 2u || c->error) return C2_STREAM_ERR_STATE;
    if (work.owner != c) { work.owner = c; work.image = 0; }
    if (work.image >= c->image_count) {
        if (c->entry_cursor != c->entry_count
            || c->resolution_cursor != c->resolution_count)
            return fail(c, C2_STREAM_ERR_C2D);
        c->entry_cursor = 0; c->resolution_cursor = 0;
        work.owner = 0; c->phase = 3; return C2_STREAM_OK;
    }
    if (!c2_stream_shelf_read(32u + (uint32_t)work.image * 32u,
                              work.s, sizeof work.s)
        || !image_read(c, work.image, work.d))
        return fail(c, C2_STREAM_ERR_IO);
    return C2_STREAM_OK;
}

C2_SECTION("02b") uint8_t c2_product_decode_02b(void *opaque) {
    c2_stream_context *c = opaque; uint32_t co, mo;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 2u) return C2_STREAM_OK;
    co = r24(work.s + 8); mo = r24(work.s + 13);
    if (work.d[0] != work.image || work.d[1]
        || r16(work.d + 2) != c->entry_cursor
        || r16(work.d + 6) != c->resolution_cursor
        || r24(work.d + 10) != co || r24(work.d + 13) != mo
        || r16(work.d + 16) != r16(work.s + 11)
        || r16(work.d + 18) != r16(work.s + 16)
        || !r16(work.s + 11) || !r16(work.s + 16)
        || work.s[30] != 1u || work.s[31]
        || co + r16(work.s + 11) > c->shelf_bytes
        || mo + r16(work.s + 16) > c->shelf_bytes)
        return fail(c, C2_STREAM_ERR_SHELF);
    c->entry_cursor = (uint16_t)(c->entry_cursor + r16(work.d + 4));
    c->resolution_cursor = (uint16_t)(c->resolution_cursor + r16(work.d + 8));
    ++work.image; return C2_STREAM_OK;
}

/* Phase 5: bind one entry at a time to its mutable directory row. */
C2_SECTION("05a") uint8_t c2_product_decode_05a(void *opaque) {
    c2_stream_context *c = opaque;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 5u) return C2_STREAM_OK;
    if (work.owner != c) {
        work.owner = c; work.image = c->image_first; work.loaded = 0;
    }
    if (work.image >= c->image_count) {
        work.owner = 0; c->phase = 6; return C2_STREAM_OK;
    }
    if (!work.loaded) {
        if (!image_read(c, work.image, work.im)) return fail(c, C2_STREAM_ERR_IO);
        work.meta = r24(work.im + 13);
        if (!c2_stream_shelf_read(work.meta, work.h, sizeof work.h))
            return fail(c, C2_STREAM_ERR_IO);
        work.local = 0; work.loaded = 1;
    }
    return C2_STREAM_OK;
}

C2_SECTION("05b") uint8_t c2_product_decode_05b(void *opaque) {
    c2_stream_context *c = opaque; uint16_t ec, lc, at, length, first, name;
    uint32_t code_at;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 5u) return C2_STREAM_OK;
    ec = r16(work.h + 10); lc = r16(work.h + 12);
    if (work.local >= ec) {
        ++work.image; work.loaded = 0; return C2_STREAM_OK;
    }
    at = (uint16_t)(r16(work.h + 14) + work.local * 16u);
    if (!c2_stream_shelf_read(work.meta + at, work.e, sizeof work.e)
        || !c2_stream_c2d_read((uint16_t)(c->entries_offset
            + (r16(work.im + 2) + work.local) * 10u), work.de, sizeof work.de))
        return fail(c, C2_STREAM_ERR_IO);
    code_at = r24(work.e); length = r16(work.e + 3);
    first = r16(work.e + 5); name = r16(work.e + 8);
    if (!length || code_at + length > r16(work.im + 16)
        || first + work.e[7] > lc || (work.e[11] & (uint8_t)~3u)
        || r16(work.e + 14) || (name == 0xffffu && work.e[11])
        || work.de[0] != work.image || work.de[1]
        || r16(work.de + 2) != work.local || r16(work.de + 4) != length
        || r16(work.de + 6) != (uint16_t)(r16(work.im + 6) + first)
        || r16(work.de + 8) != c->generation)
        return fail(c, C2_STREAM_ERR_ENTRY);
    ++work.local; return C2_STREAM_OK;
}

/* Phase 6: structural code validation and export-name validation are separate
 * residents.  The cursor advances only after both have accepted one entry. */
C2_SECTION("06a") uint8_t c2_product_decode_06a(void *opaque) {
    c2_stream_context *c = opaque;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 6u) return C2_STREAM_OK;
    if (work.owner != c) {
        work.owner = c; work.image = c->image_first; work.loaded = 0; work.pending = 0;
    }
    if (work.image >= c->image_count) {
        work.owner = 0; c->phase = 7; return C2_STREAM_OK;
    }
    if (!work.loaded) {
        if (!image_read(c, work.image, work.im)) return fail(c, C2_STREAM_ERR_IO);
        work.meta = r24(work.im + 13);
        if (!c2_stream_shelf_read(work.meta, work.h, sizeof work.h))
            return fail(c, C2_STREAM_ERR_IO);
        work.local = 0; work.loaded = 1;
    }
    if (work.local >= r16(work.h + 10)) {
        ++work.image; work.loaded = 0; work.pending = 0; return C2_STREAM_OK;
    }
    if (!c2_stream_shelf_read(work.meta + r16(work.h + 14)
            + (uint32_t)work.local * 16u, work.e, sizeof work.e))
        return fail(c, C2_STREAM_ERR_IO);
    work.pending = 1; return C2_STREAM_OK;
}

C2_SECTION("06b") uint8_t c2_product_decode_06b(void *opaque) {
    c2_stream_context *c = opaque; uint8_t co[7], zeros[16];
    uint16_t done = 0, bytes, z, n; uint32_t at;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 6u || !work.pending) return C2_STREAM_OK;
    at = r24(work.e);
    if (!c2_stream_shelf_read(r24(work.im + 10) + at, co, sizeof co))
        return fail(c, C2_STREAM_ERR_IO);
    if (co[0] != 0xb5u || co[1] != work.e[10] || co[6] != work.e[7]
        || (uint32_t)7u + (uint32_t)2u * co[6] + r16(co + 4) != r16(work.e + 3))
        return fail(c, C2_STREAM_ERR_ENTRY);
    bytes = (uint16_t)(2u * co[6]);
    while (done < bytes) {
        n = (uint16_t)(bytes - done); if (n > sizeof zeros) n = sizeof zeros;
        if (!c2_stream_shelf_read(r24(work.im + 10) + at + 7u + done, zeros, n))
            return fail(c, C2_STREAM_ERR_IO);
        for (z = 0; z < n; ++z) if (zeros[z]) return fail(c, C2_STREAM_ERR_ENTRY);
        done = (uint16_t)(done + n);
    }
    return C2_STREAM_OK;
}

C2_SECTION("06c") uint8_t c2_product_decode_06c(void *opaque) {
    c2_stream_context *c = opaque; uint16_t length; uint32_t payload;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 6u || !work.pending) return C2_STREAM_OK;
    work.name = r16(work.e + 8);
    if (work.name != 0xffffu
        && (!string_record(work.meta + r16(work.h + 18), r16(work.h + 20),
                          work.name, (uint16_t)-1, &payload))) {
        /* The name record's stored length is authoritative here. */
        uint8_t b[2];
        if (!c2_stream_shelf_read(work.meta + r16(work.h + 18) + work.name, b, 2u))
            return fail(c, C2_STREAM_ERR_ENTRY);
        length = r16(b);
        if (!string_record(work.meta + r16(work.h + 18), r16(work.h + 20),
                           work.name, length, &payload)
            || !canonical_name(payload, length)) return fail(c, C2_STREAM_ERR_ENTRY);
    }
    work.pending = 0; ++work.local; return C2_STREAM_OK;
}

/* Shared scan setup for descriptor phases 9--11. */
C2_INLINE uint8_t scan_prepare(c2_stream_context *c, uint8_t phase) {
    if (work.owner != c) {
        work.owner = c; work.image = c->image_first; work.loaded = 0; work.pending = 0;
        if (phase == 9u) work.root = c->root_first;
    }
    while (work.image < c->image_count) {
        if (!work.loaded) {
            if (!image_read(c, work.image, work.im)) return fail(c, C2_STREAM_ERR_IO);
            work.meta = r24(work.im + 13); work.base = r16(work.im + 6);
            if (!c2_stream_shelf_read(work.meta, work.h, sizeof work.h))
                return fail(c, C2_STREAM_ERR_IO);
            work.count = r16(work.h + 12); work.local = 0; work.loaded = 1;
        }
        if (work.local < work.count) return C2_STREAM_OK;
        ++work.image; work.loaded = 0;
    }
    return C2_STREAM_OK;
}

C2_SECTION("09a") uint8_t c2_product_decode_09a(void *opaque) {
    c2_stream_context *c = opaque; uint8_t kind;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 9u) return C2_STREAM_OK;
    if (scan_prepare(c, 9u) != C2_STREAM_OK) return c->error;
    if (work.image >= c->image_count) {
        work.owner = 0; c->phase = 10; return C2_STREAM_OK;
    }
    if (!c2_stream_shelf_read(work.meta + r16(work.h + 16)
            + (uint32_t)work.local * 8u, work.r, sizeof work.r))
        return fail(c, C2_STREAM_ERR_IO);
    kind = work.r[0]; work.pending = (uint8_t)(kind == 3u);
    if (!work.pending) { ++work.local; return C2_STREAM_OK; }
    work.value = r16(work.r + 2); work.arg1 = r24(work.r + 4);
    work.strings = r16(work.h + 18); work.string_bytes = r16(work.h + 20);
    return C2_STREAM_OK;
}

C2_SECTION("09b") uint8_t c2_product_decode_09b(void *opaque) {
    c2_stream_context *c = opaque; uint16_t value, root;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 9u || !work.pending) return C2_STREAM_OK;
    if (work.r[1] || work.r[7]
        || !string_record(work.meta + work.strings, work.string_bytes,
                          work.arg1, work.value, &work.payload)
        || !c2_stream_name_value(3u, work.payload, work.value, &value)
        || !pointer_value(value)
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
            + (work.base + work.local) * 2u), work.b, 2u))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    root = r16(work.b);
    if (root >= c->c2_root_count) return fail(c, C2_STREAM_ERR_RESOLUTION);
    w16(work.b, value);
    if (!c2_stream_c2d_write((uint16_t)(roots_offset(c) + root * 2u), work.b, 2u)
        || !c2_stream_gc_checkpoint(roots_offset(c), c->c2_root_count))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    ++c->resolution_cursor; ++work.local; work.pending = 0; return C2_STREAM_OK;
}

C2_SECTION("10a") uint8_t c2_product_decode_10a(void *opaque) {
    c2_stream_context *c = opaque; uint8_t kind;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 10u) return C2_STREAM_OK;
    if (scan_prepare(c, 10u) != C2_STREAM_OK) return c->error;
    if (work.image >= c->image_count) {
        work.owner = 0; c->phase = 11; return C2_STREAM_OK;
    }
    if (!c2_stream_shelf_read(work.meta + r16(work.h + 16)
            + (uint32_t)work.local * 8u, work.r, sizeof work.r))
        return fail(c, C2_STREAM_ERR_IO);
    kind = work.r[0]; work.pending = (uint8_t)(kind == 5u || kind == 8u);
    if (!work.pending) { ++work.local; return C2_STREAM_OK; }
    work.value = r16(work.r + 2); work.arg1 = r24(work.r + 4);
    work.strings = r16(work.h + 18); work.string_bytes = r16(work.h + 20);
    return C2_STREAM_OK;
}

C2_SECTION("10b") uint8_t c2_product_decode_10b(void *opaque) {
    c2_stream_context *c = opaque; uint16_t value;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 10u || !work.pending) return C2_STREAM_OK;
    if (work.r[1] || work.r[7]
        || !string_record(work.meta + work.strings, work.string_bytes,
                          work.arg1, work.value, &work.payload)
        || !canonical_name(work.payload, work.value)
        || !c2_stream_name_value(work.r[0], work.payload, work.value, &value))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    w16(work.b, value);
    if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset
            + (work.base + work.local) * 2u), work.b, 2u))
        return fail(c, C2_STREAM_ERR_IO);
    ++c->resolution_cursor; ++work.local; work.pending = 0; return C2_STREAM_OK;
}

C2_INLINE uint8_t child_value(c2_stream_context *c, uint16_t local, uint16_t *value) {
    uint8_t descriptor[8], b[2]; uint16_t word;
    if (!c2_stream_shelf_read(work.meta + r16(work.h + 16)
            + (uint32_t)local * 8u, descriptor, sizeof descriptor)
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
            + (work.base + local) * 2u), b, 2u)) return 0;
    word = r16(b);
    if (descriptor[0] == 3u || descriptor[0] == 7u) {
        if (word >= c->c2_root_count
            || !c2_stream_c2d_read((uint16_t)(roots_offset(c) + word * 2u), b, 2u))
            return 0;
        word = r16(b); if (!pointer_value(word)) return 0;
    }
    *value = word; return 1;
}

C2_SECTION("11a") uint8_t c2_product_decode_11a(void *opaque) {
    c2_stream_context *c = opaque; uint16_t a;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 11u) return C2_STREAM_OK;
    if (scan_prepare(c, 11u) != C2_STREAM_OK) return c->error;
    if (work.image >= c->image_count) {
        if (c->resolution_cursor != c->resolution_count)
            return fail(c, C2_STREAM_ERR_RESOLUTION);
        work.owner = 0; c->phase = 12; return C2_STREAM_OK;
    }
    if (!c2_stream_shelf_read(work.meta + r16(work.h + 16)
            + (uint32_t)work.local * 8u, work.r, sizeof work.r))
        return fail(c, C2_STREAM_ERR_IO);
    work.pending = (uint8_t)(work.r[0] == 7u);
    if (!work.pending) { ++work.local; return C2_STREAM_OK; }
    a = r16(work.r + 2); work.arg1 = r24(work.r + 4);
    if (work.r[1] || work.r[7] || a >= work.local
        || work.arg1 >= work.local || work.arg1 > 0xffffUL)
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    work.value = a;
    return C2_STREAM_OK;
}

C2_SECTION("11b") uint8_t c2_product_decode_11b(void *opaque) {
    c2_stream_context *c = opaque;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 11u || !work.pending) return C2_STREAM_OK;
    if (!child_value(c, work.value, &work.car_value))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    return C2_STREAM_OK;
}

C2_SECTION("11c") uint8_t c2_product_decode_11c(void *opaque) {
    c2_stream_context *c = opaque;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 11u || !work.pending) return C2_STREAM_OK;
    if (!child_value(c, (uint16_t)work.arg1, &work.cdr_value))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    return C2_STREAM_OK;
}

C2_SECTION("11d") uint8_t c2_product_decode_11d(void *opaque) {
    c2_stream_context *c = opaque; uint16_t value, root;
    if (!c || c->error) return C2_STREAM_ERR_STATE;
    if (c->phase != 11u || !work.pending) return C2_STREAM_OK;
    if (!c2_stream_pair_value(work.car_value, work.cdr_value, &value)
        || !pointer_value(value)
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
            + (work.base + work.local) * 2u), work.b, 2u))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    root = r16(work.b);
    if (root >= c->c2_root_count) return fail(c, C2_STREAM_ERR_RESOLUTION);
    w16(work.b, value);
    if (!c2_stream_c2d_write((uint16_t)(roots_offset(c) + root * 2u), work.b, 2u)
        || !c2_stream_gc_checkpoint(roots_offset(c), c->c2_root_count))
        return fail(c, C2_STREAM_ERR_RESOLUTION);
    ++c->resolution_cursor; ++work.local; work.pending = 0; return C2_STREAM_OK;
}

/* Phase 13: bind the entry once, then materialize one literal per transport. */
C2_SECTION("13a") uint8_t c2_product_decode_13a(void *opaque) {
    c2_stream_materialize_context *m = opaque; c2_stream_context *c;
    uint16_t image, local;
    if (!m || !(c = m->stream) || !m->hot_values || !c->finished
        || c->phase != 13u || m->directory_ordinal >= c->entry_count)
        return C2_STREAM_ERR_STATE;
    if (!c2_stream_c2d_read((uint16_t)(c->entries_offset
            + m->directory_ordinal * 10u), work.de, sizeof work.de))
        return C2_STREAM_ERR_IO;
    image = work.de[0]; local = r16(work.de + 2);
    if (image >= c->image_count || !image_read(c, image, work.im))
        return C2_STREAM_ERR_ENTRY;
    work.meta = r24(work.im + 13); work.base = r16(work.im + 6);
    if (!c2_stream_shelf_read(work.meta, work.h, sizeof work.h)) return C2_STREAM_ERR_IO;
    if (local >= r16(work.h + 10)
        || !c2_stream_shelf_read(work.meta + r16(work.h + 14)
            + (uint32_t)local * 16u, work.e, sizeof work.e)) return C2_STREAM_ERR_ENTRY;
    work.first = r16(work.e + 5); m->hot_count = work.e[7];
    if (m->hot_count > m->hot_capacity
        || (uint16_t)(work.first + m->hot_count) > r16(work.h + 12))
        return C2_STREAM_ERR_ENTRY;
    work.materialize = m; work.local = 0; return C2_STREAM_OK;
}

C2_SECTION("13b") uint8_t c2_product_decode_13b(void *opaque) {
    c2_stream_materialize_context *m = opaque; c2_stream_context *c;
    uint16_t word;
    if (!m || m != work.materialize || !(c = m->stream)
        || work.local >= m->hot_count) return C2_STREAM_ERR_STATE;
    if (!c2_stream_shelf_read(work.meta + r16(work.h + 16)
            + (uint32_t)(work.first + work.local) * 8u, work.r, sizeof work.r)
        || !c2_stream_c2d_read((uint16_t)(c->resolutions_offset
            + (work.base + work.first + work.local) * 2u), work.b, 2u))
        return C2_STREAM_ERR_IO;
    word = r16(work.b);
    if (work.r[0] == 3u || work.r[0] == 7u) {
        if (word >= c->c2_root_count
            || !c2_stream_c2d_read((uint16_t)(roots_offset(c) + word * 2u), work.b, 2u)
            || !pointer_value(r16(work.b))) return C2_STREAM_ERR_RESOLUTION;
        word = r16(work.b);
    }
    m->hot_values[work.local++] = word; return C2_STREAM_OK;
}

#endif
