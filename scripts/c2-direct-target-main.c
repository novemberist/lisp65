/* Isolated C2.1 target proof. It is not part of either Workbench product. */
#include <stddef.h>
#include <stdint.h>
#ifndef C2_TARGET_LINK_ONLY
#include <stdio.h>
#endif
#include "c2-direct-vectors.h"

#define C2_MAX_ENTRIES 8
#define C2_MAX_LITERALS 8
#define C2_WINDOW 8
#define C2_BUILD_ID 0xc2210001UL

enum { V_NIL, V_INT, V_BCODE, V_PAIR, V_CLOSURE };
typedef struct { uint8_t kind; int16_t value; uint16_t generation; } value;
typedef struct { value car, cdr; } pair;
typedef struct { value target; } closure;
typedef struct {
    uint32_t code_off;
    uint16_t code_len, lit_first, diagnostic_ordinal;
    uint8_t lit_count, arity;
    uint16_t payload_off, payload_len;
} entry;
typedef struct {
    const uint8_t *shelf, *code, *metadata;
    uint16_t shelf_len, code_len, metadata_len, generation;
    uint8_t entry_count, literal_count;
    entry entries[C2_MAX_ENTRIES];
    value literals[C2_MAX_LITERALS];
} image;
typedef struct {
    const image *im;
    uint8_t bytes[C2_WINDOW];
    uint16_t start, count, refills, steps;
    uint8_t owner;
    pair pairs[4];
    closure closures[2];
    uint8_t npairs, nclosures;
} vm;

volatile uint8_t c2_target_sink;

/*
 * The ordinary host/MOS proof reads its generated near-memory vector.  The
 * receipt-less hardware smoke binds this one seam to an Enhanced-DMA refill
 * from a separately staged Attic shelf.  Keeping the decoder and executor in
 * this translation unit means the device smoke exercises the same proof
 * implementation instead of a second, friendlier model.
 */
#ifdef C2_TARGET_REFILL_FUNCTION
uint8_t C2_TARGET_REFILL_FUNCTION(uint16_t shelf_offset, uint8_t *dst,
                                  uint8_t length);
#endif

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
static int same4(const uint8_t *p, const char *s) {
    return p[0] == (uint8_t)s[0] && p[1] == (uint8_t)s[1] &&
           p[2] == (uint8_t)s[2] && p[3] == (uint8_t)s[3];
}
static int same8(const uint8_t *p, const char *s) {
    uint8_t i;
    for (i = 0; i < 8; ++i) if (p[i] != (uint8_t)s[i]) return 0;
    return 1;
}
static value vnil(void) { value v = {V_NIL, 0, 0}; return v; }
static value vint(int16_t n) { value v = {V_INT, n, 0}; return v; }
static value vbcode(uint16_t generation, uint16_t ordinal) {
    value v = {V_BCODE, (int16_t)ordinal, generation}; return v;
}

/* Decode the exact owner-approved 24/16/8 C2I envelope. */
__attribute__((noinline))
static int decode_metadata(image *out) {
    const uint8_t *m = out->metadata;
    uint16_t ec, lc, eo, lo, so, sb, expected, i;
    if (out->metadata_len < 24 || !same4(m, "C2I") || m[3] != 0 || m[4] != 1) return 20;
    if (m[5] != 24 || m[6] != 16 || m[7] != 8 || r16(m + 8) || r16(m + 22)) return 21;
    ec = r16(m + 10); lc = r16(m + 12); eo = r16(m + 14);
    lo = r16(m + 16); so = r16(m + 18); sb = r16(m + 20);
    if (ec > C2_MAX_ENTRIES || lc > C2_MAX_LITERALS || eo != 24 ||
        lo != (uint16_t)(eo + ec * 16u) || so != (uint16_t)(lo + lc * 8u)) return 22;
    expected = (uint16_t)((so + sb + 1u) & ~1u);
    if (expected != out->metadata_len || ((so + sb) != expected && m[expected - 1])) return 23;
    out->entry_count = (uint8_t)ec; out->literal_count = (uint8_t)lc;
    for (i = 0; i < ec; ++i) {
        const uint8_t *r = m + eo + i * 16u;
        const uint8_t *co;
        entry *e = &out->entries[i];
        uint16_t export_off = r16(r + 8), reserved = r16(r + 14);
        e->code_off = r24(r); e->code_len = r16(r + 3);
        e->lit_first = r16(r + 5); e->lit_count = r[7];
        e->arity = r[10]; e->diagnostic_ordinal = r16(r + 12);
        if (!e->code_len || e->code_off + e->code_len > out->code_len ||
            e->lit_first + e->lit_count > lc) return 24;
        if ((r[11] & (uint8_t)~3u) || reserved || (export_off == 0xffffu && r[11])) return 25;
        if (export_off != 0xffffu) return 26; /* proof image intentionally has no export */
        co = out->code + (uint16_t)e->code_off;
        if (e->code_len < 7 || co[0] != 0xb5 || co[1] != e->arity || co[6] != e->lit_count) return 27;
        e->payload_len = r16(co + 4); e->payload_off = (uint16_t)(7 + 2u * co[6]);
        if (e->payload_off + e->payload_len != e->code_len) return 28;
        { uint16_t k; for (k = 7; k < e->payload_off; ++k) if (co[k]) return 29; }
    }
    for (i = 0; i < lc; ++i) {
        const uint8_t *r = m + lo + i * 8u;
        if (r[0] != 4 || r[1] || r24(r + 4) || r[7] || r16(r + 2) >= ec) return 30;
        out->literals[i] = vbcode(out->generation, r16(r + 2));
    }
    return 0;
}

/* Decode inherited 32/32 L65S-v4 split regions and device CRC/build identity. */
__attribute__((noinline))
static int decode_shelf(image *out, const uint8_t *shelf, uint16_t length, uint16_t generation) {
    const uint8_t *record = 0; uint16_t payload, total, catalog_len;
    uint8_t count, i;
    uint32_t co, mo; uint16_t cl, ml;
    if (length < 64 || !same4(shelf, "L65S") || shelf[4] != 4) return 1;
    count = shelf[7];
    if (shelf[5] != 32 || shelf[6] != 32 || !count || r16(shelf + 8) != 32) return 2;
    payload = (uint16_t)r24(shelf + 10); total = (uint16_t)r24(shelf + 13);
    catalog_len = r16(shelf + 16);
    if (payload != (uint16_t)(32 + (uint16_t)count * 32u) || total != length ||
        catalog_len != (uint16_t)count * 32u || r16(shelf + 26) != 1 ||
        shelf[28] || shelf[29] || shelf[30] || shelf[31]) return 3;
    if (r32(shelf + 22) != C2_BUILD_ID) return 4;
    if (crc32_bytes(shelf + 32, catalog_len) != r32(shelf + 18)) return 5;
    for (i = 0; i < count; ++i) {
        const uint8_t *candidate = shelf + 32 + (uint16_t)i * 32u;
        if (same8(candidate, "c2proof")) {
            if (record) return 6;
            record = candidate;
        }
    }
    if (!record) return 6;
    if (record[30] != 1 || record[31]) return 6;
    co = r24(record + 8); cl = r16(record + 11);
    mo = r24(record + 13); ml = r16(record + 16);
    if (!cl || !ml || co != payload || mo != co + cl || mo + ml != total) return 7;
    if (crc32_bytes(shelf + (uint16_t)co, cl) != r32(record + 18) ||
        crc32_bytes(shelf + (uint16_t)mo, ml) != r32(record + 22) ||
        crc32_bytes(shelf + (uint16_t)co, (uint16_t)(cl + ml)) != r32(record + 26)) return 8;
    out->shelf = shelf; out->shelf_len = length;
    out->code = shelf + (uint16_t)co; out->code_len = cl;
    out->metadata = shelf + (uint16_t)mo; out->metadata_len = ml;
    out->generation = generation;
    return decode_metadata(out);
}

static int fetch(vm *m, const entry *e, uint16_t pc, uint8_t *result) {
    uint16_t absolute, start, end, k;
    if (pc >= e->payload_len) return 40;
    absolute = (uint16_t)(e->code_off + e->payload_off + pc);
    start = (uint16_t)(absolute & (uint16_t)~(C2_WINDOW - 1u));
    if (m->owner != (uint8_t)e->diagnostic_ordinal || absolute < m->start ||
        absolute >= (uint16_t)(m->start + m->count)) {
        end = (uint16_t)(start + C2_WINDOW);
        if (start < e->code_off) start = (uint16_t)e->code_off;
        if (end > e->code_off + e->code_len) end = (uint16_t)(e->code_off + e->code_len);
        if (start > absolute || end <= absolute || end - start > C2_WINDOW) return 41;
#ifdef C2_TARGET_REFILL_FUNCTION
        if (!C2_TARGET_REFILL_FUNCTION(
                (uint16_t)(m->im->code - m->im->shelf) + start,
                m->bytes, (uint8_t)(end - start))) return 42;
#else
        for (k = 0; k < end - start; ++k) m->bytes[k] = m->im->code[start + k];
#endif
        m->start = start; m->count = (uint16_t)(end - start);
        m->owner = (uint8_t)e->diagnostic_ordinal; ++m->refills;
    }
    *result = m->bytes[absolute - m->start]; return 0;
}

static int run_entry(vm *m, uint16_t ordinal, const value *args, uint8_t argc,
                     value *result, uint8_t depth);

static int invoke(vm *m, value fn, const value *args, uint8_t argc, value *result, uint8_t depth) {
    if (fn.kind == V_CLOSURE) {
        if ((uint16_t)fn.value >= m->nclosures) return 50;
        fn = m->closures[(uint16_t)fn.value].target;
    }
    if (fn.kind != V_BCODE || fn.generation != m->im->generation) return 51;
    return run_entry(m, (uint16_t)fn.value, args, argc, result, depth);
}

static int byte_at(vm *m, const entry *e, uint16_t *pc, uint8_t *out) {
    int err = fetch(m, e, *pc, out); if (!err) ++*pc; return err;
}

static int run_entry(vm *m, uint16_t ordinal, const value *args, uint8_t argc,
                     value *result, uint8_t depth) {
    const entry *e; value stack[8]; uint8_t sp = 0, op, a, b; uint16_t pc = 0; int err;
    if (ordinal >= m->im->entry_count || depth > 8) return 52;
    e = &m->im->entries[ordinal]; if (argc != e->arity) return 53;
    while (pc < e->payload_len) {
        if ((err = byte_at(m, e, &pc, &op))) return err;
        if (++m->steps > 1000) return 54;
        switch (op) {
        case 1:
            if ((err = byte_at(m, e, &pc, &a)) || sp >= 8) return err ? err : 55;
            stack[sp++] = vint((int8_t)a); break;
        case 2:
            if (sp < 2 || stack[sp-1].kind != V_INT || stack[sp-2].kind != V_INT) return 56;
            stack[sp-2].value = (int16_t)(stack[sp-2].value + stack[sp-1].value); --sp; break;
        case 5:
            if (!sp) return 57;
            *result = stack[--sp];
            return 0;
        case 6:
            if ((err = byte_at(m, e, &pc, &a)) || a >= e->lit_count || sp >= 8) return err ? err : 58;
            stack[sp++] = m->im->literals[e->lit_first + a]; break;
        case 11:
            if (!argc || sp >= 8) return 59;
            stack[sp++] = args[0];
            break;
        case 43:
            if (sp >= 8) return 60;
            stack[sp++] = vnil();
            break;
        case 51:
            if (sp < 2 || m->npairs >= 4) return 61;
            m->pairs[m->npairs].car = stack[sp-2]; m->pairs[m->npairs].cdr = stack[sp-1];
            sp -= 2; stack[sp].kind = V_PAIR; stack[sp].value = m->npairs++; stack[sp].generation = 0; ++sp; break;
        case 60: case 62:
            if ((err = byte_at(m, e, &pc, &a)) || (err = byte_at(m, e, &pc, &b))) return err;
            if (a >= e->lit_count || b > sp) return 62;
            err = invoke(m, m->im->literals[e->lit_first + a], stack + sp - b, b, result, (uint8_t)(depth + 1));
            if (err || op == 62) return err;
            sp = (uint8_t)(sp - b);
            stack[sp++] = *result;
            break;
        case 61:
            if ((err = byte_at(m, e, &pc, &a)) || (err = byte_at(m, e, &pc, &b))) return err;
            if (b > sp || b < 2 || (a != 7 && a != 8)) return 63;
            if (a == 8) {
                err = invoke(m, stack[sp-b], stack + sp-b+1, (uint8_t)(b-1), result, (uint8_t)(depth+1));
            } else {
                value list = stack[sp-1], av[6]; uint8_t n = 0, prefix, k;
                prefix = (uint8_t)(b - 2);
                for (k = 0; k < prefix; ++k) av[n++] = stack[sp-b+1+k];
                while (list.kind != V_NIL) {
                    if (list.kind != V_PAIR || (uint16_t)list.value >= m->npairs || n >= 6) return 64;
                    av[n++] = m->pairs[(uint16_t)list.value].car;
                    list = m->pairs[(uint16_t)list.value].cdr;
                }
                err = invoke(m, stack[sp-b], av, n, result, (uint8_t)(depth+1));
            }
            if (err) return err;
            sp = (uint8_t)(sp - b);
            stack[sp++] = *result;
            break;
        case 63:
            if ((err = byte_at(m, e, &pc, &a)) || (err = byte_at(m, e, &pc, &b))) return err;
            if (a >= e->lit_count || b != 0 || m->nclosures >= 2 || sp >= 8) return 65;
            m->closures[m->nclosures].target = m->im->literals[e->lit_first + a];
            stack[sp].kind = V_CLOSURE; stack[sp].value = m->nclosures++; stack[sp].generation = 0; ++sp; break;
        default: return 66;
        }
    }
    return 67;
}

__attribute__((noinline))
static int proof_run(void) {
    image im = {0}; vm machine = {0}; value result; uint8_t ordinal; int err;
    uint32_t before = crc32_bytes(c2_direct_shelf, C2_DIRECT_SHELF_BYTES);
    if ((err = decode_shelf(&im, c2_direct_shelf, C2_DIRECT_SHELF_BYTES, 1))) return err;
    machine.im = &im; machine.owner = 0xff;
    for (ordinal = 1; ordinal <= 5; ++ordinal) {
        if ((err = run_entry(&machine, ordinal, 0, 0, &result, 1))) return err;
        if (result.kind != V_INT || result.value != 42) return 70;
    }
    if (before != crc32_bytes(c2_direct_shelf, C2_DIRECT_SHELF_BYTES)) return 71;
    c2_target_sink = (uint8_t)(machine.refills ^ machine.steps);
#ifndef C2_TARGET_LINK_ONLY
    printf("c2-direct-target: PASS routes=5 entries=%u refills=%u steps=%u sink=%u\n",
           im.entry_count, machine.refills, machine.steps, c2_target_sink);
#endif
    return 0;
}

#ifndef C2_TARGET_MAIN
#define C2_TARGET_MAIN main
#endif
int C2_TARGET_MAIN(void) { return proof_run(); }
