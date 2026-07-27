/* Independent C2I-v2/C2D-v1 decoder proof; never part of a shipped product. */
#include <stdint.h>
#ifndef C2_TARGET_LINK_ONLY
#include <stdio.h>
#endif
#include "c2-full-vectors.h"

#define MAX_DESC 8u

volatile uint8_t c2_full_target_sink;

static uint16_t r16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
static uint32_t r24(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
}
static uint32_t r32(const uint8_t *p) {
    return (uint32_t)r16(p) | (uint32_t)r16(p + 2) << 16;
}
static uint32_t crc32_bytes(const uint8_t *p, uint16_t n) {
    uint32_t crc = 0xffffffffUL;
    uint16_t i; uint8_t bit;
    for (i = 0; i < n; ++i) {
        crc ^= p[i];
        for (bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320UL & (uint32_t)-(int32_t)(crc & 1));
    }
    return ~crc;
}
static int magic4(const uint8_t *p, const char *s) {
    return p[0] == (uint8_t)s[0] && p[1] == (uint8_t)s[1] &&
           p[2] == (uint8_t)s[2] && p[3] == (uint8_t)s[3];
}
static int canonical_name(const uint8_t *p, uint16_t n) {
    uint16_t i;
    if (!n || n > 255u) return 0;
    for (i = 0; i < n; ++i) if (p[i] < 0x21u || p[i] > 0x7eu) return 0;
    return 1;
}
static int record_at(const uint8_t *pool, uint16_t bytes, uint32_t offset,
                     const uint8_t **value, uint16_t *result_length) {
    uint16_t cursor = 0, length;
    if (offset > 0xffffUL) return 0;
    while (cursor < bytes) {
        if ((uint16_t)(bytes - cursor) < 2u) return 0;
        length = r16(pool + cursor);
        if (length > (uint16_t)(bytes - cursor - 2u)) return 0;
        if (cursor == (uint16_t)offset) {
            *value = pool + cursor + 2u;
            *result_length = length;
            return 1;
        }
        cursor = (uint16_t)(cursor + 2u + length);
    }
    return 0;
}
static int string_at(const uint8_t *pool, uint16_t bytes, uint32_t offset,
                     uint16_t expected, const uint8_t **value) {
    uint16_t length;
    return record_at(pool, bytes, offset, value, &length) && length == expected;
}

/* One forward pass: pair references are strictly backward; no recursion. */
__attribute__((noinline))
static int decode_c2i_v2(const uint8_t *code, uint16_t code_bytes,
                         const uint8_t *m, uint16_t bytes,
                         uint16_t *literal_count, uint8_t *maximum_depth) {
    uint16_t ec, lc, eo, lo, so, sb, expected, i;
    uint8_t depth[MAX_DESC];
    if (bytes < 24u || !magic4(m, "C2I") || m[3] || m[4] != 2u) return 20;
    if (m[5] != 24u || m[6] != 16u || m[7] != 8u || r16(m + 8) || r16(m + 22)) return 21;
    ec = r16(m + 10); lc = r16(m + 12); eo = r16(m + 14);
    lo = r16(m + 16); so = r16(m + 18); sb = r16(m + 20);
    if (lc > MAX_DESC || eo != 24u || lo != (uint16_t)(eo + ec * 16u) ||
        so != (uint16_t)(lo + lc * 8u)) return 22;
    expected = (uint16_t)((so + sb + 1u) & (uint16_t)~1u);
    if (expected != bytes || ((uint16_t)(so + sb) != expected && m[expected - 1u])) return 23;
    for (i = 0; i < ec; ++i) {
        const uint8_t *r = m + eo + i * 16u;
        uint32_t co = r24(r); uint16_t cl = r16(r + 3), first = r16(r + 5);
        uint8_t count = r[7]; uint16_t name = r16(r + 8), reserved = r16(r + 14);
        const uint8_t *obj; uint16_t name_length;
        if (!cl || co + cl > code_bytes || first + count > lc) return 33;
        if ((r[11] & (uint8_t)~3u) || reserved || (name == 0xffffu && r[11])) return 34;
        if (name != 0xffffu && (!record_at(m + so, sb, name, &obj, &name_length) ||
                               !canonical_name(obj, name_length))) return 35;
        obj = code + (uint16_t)co;
        if (cl < 7u || obj[0] != 0xb5u || obj[1] != r[10] || obj[6] != count ||
            (uint16_t)(7u + 2u * count + r16(obj + 4)) != cl) return 36;
        { uint8_t k; for (k = 0; k < count; ++k)
            if (obj[7u + 2u * k] || obj[8u + 2u * k]) return 37; }
    }
    *maximum_depth = 0;
    for (i = 0; i < lc; ++i) {
        const uint8_t *r = m + lo + i * 8u;
        const uint8_t *text = 0;
        uint8_t kind = r[0]; uint16_t a = r16(r + 2); uint32_t b = r24(r + 4);
        if (kind > 8u || r[1] || r[7]) return 24;
        depth[i] = 0;
        switch (kind) {
        case 0: case 1:
            if (a || b) return 25;
            break;
        case 2: {
            int16_t value = (int16_t)a;
            if (value < -16384 || value > 16383 || b) return 26;
            break;
        }
        case 3:
            if (!string_at(m + so, sb, b, a, &text)) return 27;
            break;
        case 4:
            if (a >= ec || b) return 28;
            break;
        case 5: case 8:
            if (!string_at(m + so, sb, b, a, &text) || !canonical_name(text, a)) return 29;
            if (kind == 5u && !(a == 5u && text[0] == 'k' && text[1] == 'n' &&
                                text[2] == 'o' && text[3] == 'w' && text[4] == 'n')) return 30;
            break;
        case 6:
            if (b) return 31;
            break;
        default:
            if (a >= i || b >= i || b > 0xffffUL) return 32;
            depth[i] = (uint8_t)((depth[a] > depth[(uint16_t)b] ? depth[a] : depth[(uint16_t)b]) + 1u);
            if (depth[i] > *maximum_depth) *maximum_depth = depth[i];
            break;
        }
    }
    *literal_count = lc;
    return 0;
}

__attribute__((noinline))
static int decode_shelf(const uint8_t *shelf, uint16_t bytes,
                        const uint8_t **code, uint16_t *code_bytes,
                        const uint8_t **metadata, uint16_t *metadata_bytes,
                        uint16_t *code_offset, uint16_t *metadata_offset,
                        uint32_t *catalog_crc) {
    const uint8_t *record; uint16_t payload, catalog, total, cl, ml;
    uint32_t co, mo;
    if (bytes < 64u || !magic4(shelf, "L65S") || shelf[4] != 4u) return 1;
    if (shelf[5] != 32u || shelf[6] != 32u || shelf[7] != 1u || r16(shelf + 8) != 32u) return 2;
    payload = (uint16_t)r24(shelf + 10); total = (uint16_t)r24(shelf + 13);
    catalog = r16(shelf + 16); *catalog_crc = r32(shelf + 18);
    if (payload != 64u || total != bytes || catalog != 32u || r16(shelf + 26) != 1u ||
        shelf[28] || shelf[29] || shelf[30] || shelf[31]) return 3;
    if (crc32_bytes(shelf + 32, catalog) != *catalog_crc) return 4;
    record = shelf + 32; co = r24(record + 8); cl = r16(record + 11);
    mo = r24(record + 13); ml = r16(record + 16);
    if (!cl || !ml || co != payload || mo != co + cl || mo + ml != total ||
        record[30] != 1u || record[31]) return 5;
    if (crc32_bytes(shelf + (uint16_t)co, cl) != r32(record + 18) ||
        crc32_bytes(shelf + (uint16_t)mo, ml) != r32(record + 22) ||
        crc32_bytes(shelf + (uint16_t)co, (uint16_t)(cl + ml)) != r32(record + 26)) return 6;
    *code = shelf + (uint16_t)co; *code_bytes = cl;
    *metadata = shelf + (uint16_t)mo; *metadata_bytes = ml;
    *code_offset = (uint16_t)co; *metadata_offset = (uint16_t)mo;
    return 0;
}

__attribute__((noinline))
static int decode_c2d(const uint8_t *d, uint16_t bytes, uint32_t catalog_crc,
                      uint16_t code_offset, uint16_t metadata_offset,
                      uint16_t code_bytes, uint16_t metadata_bytes,
                      uint16_t *resolution_count) {
    uint16_t ic, ec, rc, io, eo, ro, total;
    if (bytes < 32u || !magic4(d, "C2D") || d[3] || d[4] != 1u) return 40;
    if (d[5] != 32u || d[6] != 20u || d[7] != 10u || r16(d + 8) || !r16(d + 10)) return 41;
    ic = r16(d + 12); ec = r16(d + 14); rc = r16(d + 16);
    io = r16(d + 18); eo = r16(d + 20); ro = r16(d + 22); total = r16(d + 24);
    if (r16(d + 26) || r32(d + 28) != catalog_crc) return 42;
    if (io != 32u || eo != (uint16_t)(io + ic * 20u) ||
        ro != (uint16_t)(eo + ec * 10u) || total != (uint16_t)(ro + rc * 2u) || total != bytes) return 43;
    if (ic != 1u || ec != 1u || rc != 4u) return 44;
    if (d[io] || d[io + 1] || r16(d + io + 2) || r16(d + io + 4) != 1u ||
        r16(d + io + 6) || r16(d + io + 8) != 4u ||
        r24(d + io + 10) != code_offset || r24(d + io + 13) != metadata_offset ||
        r16(d + io + 16) != code_bytes || r16(d + io + 18) != metadata_bytes) return 45;
    if (d[eo] || d[eo + 1] || r16(d + eo + 2) || r16(d + eo + 4) != code_bytes ||
        r16(d + eo + 6) != 4u || r16(d + eo + 8) != 1u) return 46;
    *resolution_count = rc;
    return 0;
}

__attribute__((noinline))
static int proof_run(void) {
    const uint8_t *code = 0, *metadata = 0;
    uint16_t code_bytes = 0, metadata_bytes = 0, code_offset = 0, metadata_offset = 0;
    uint16_t literals = 0, resolutions = 0;
    uint8_t depth = 0; uint32_t catalog_crc = 0; int err;
    if ((err = decode_shelf(c2_full_shelf, C2_FULL_SHELF_BYTES, &code, &code_bytes,
                            &metadata, &metadata_bytes, &code_offset, &metadata_offset,
                            &catalog_crc))) return err;
    if ((err = decode_c2i_v2(code, code_bytes, metadata, metadata_bytes, &literals, &depth))) return err;
    if ((err = decode_c2d(c2_full_c2d, C2_FULL_C2D_BYTES, catalog_crc,
                          code_offset, metadata_offset, code_bytes, metadata_bytes,
                          &resolutions))) return err;
    if (literals != 4u || resolutions != 4u || depth != 2u) return 60;
    c2_full_target_sink = (uint8_t)(literals ^ resolutions ^ depth);
#ifndef C2_TARGET_LINK_ONLY
    printf("c2-full-target: PASS entries=1 descriptors=%u depth=%u c2d=%u sink=%u\n",
           literals, depth, C2_FULL_C2D_BYTES, c2_full_target_sink);
#endif
    return 0;
}

int main(void) { return proof_run(); }
