"""Price the boot-name-index phase split off product (no link, no Seed).

Three paired, non-LTO object projections against the accepted native-diet r4
world (`build/native-diet-product-r4/wplto`), using that world's own pinned
compiler command and include closure:

  baseline       the world's decoder phase 10 and symbol.c, unmodified
  single-slice   the withdrawn one-phase index form, but with every index
                 helper forced into the phase-10 slice section (the r2 probe
                 left them in ordinary resident text, which is why that price
                 read 1,974 slice + 778 resident)
  split          decoder phase 10 collects name coordinates into a transient
                 Bank-5 queue; a NEW phase (slice `10b`) owns the index, the
                 interner and the resolution writes

Nothing here links, seeds, or touches a product source: every generated file is
a fresh copy under build/.  Slice numbers are object-section sizes, not final
link sizes.
"""
import argparse
import json
from pathlib import Path
import shlex

from native_diet_object_probe import ROOT, sha, put, run
from elf_truth import ElfTruth

BASE = ROOT / 'build/native-diet-product-r4/wplto'
SLICE_CAP = 1792

# --------------------------------------------------------------------------
# Shared transient Bank-5 owner geometry.  The conservative free interval of
# the storage owner manifest begins at $5DE80 and ends at the bank end; the
# index takes its first 2,048 bytes and the queue follows.
GEOMETRY = '''
/* Transient boot owner in the Bank-5 free tail ($5DE80..$60000).  Holds no
 * truth: every index hit is confirmed by a full canonical name comparison,
 * absence is only provable because the count is caught up first, and the
 * whole owner is dead again when the phase sequence leaves phase 10. */
#define C2_BNX_BANK 5u
#define C2_BNX_INDEX 0xde80u
#define C2_BNX_SLOTS 1024u
#define C2_BNX_QUEUE (uint16_t)(C2_BNX_INDEX + C2_BNX_SLOTS * 2u)
#define C2_BNX_ENTRY 6u
#define C2_BNX_BATCH 1024u
'''

# --------------------------------------------------------------------------
# Index body.  `TAG` picks the section attribute: C2_V2_SLICE(10) for the
# single-slice variant, C2_V2_SLICE(10b) for the split's resolve phase.
INDEX_BODY = '''
#include "symbol.h"
#include "mem.h"
#include "c2_kernal_facade.h"
void c2_dma_read_or_abort(uint8_t bank, uint16_t offset, uint16_t length,
                          uint8_t *destination);
extern obj sym_create(const char *name);
/* The two word accessors are placed in the slice but stay inlinable: the phase
 * body pays their bytes only where it uses them. */
#define C2_BNX_HERE __attribute__((section(".lisp65_rt_c2d_" __SL__)))
C2_BNX_HERE static uint16_t v2_bnx_hash(const char *p) {
    uint16_t h = 0;
    while (*p) h = (uint16_t)((uint16_t)(h << 5) + h) ^ (uint8_t)*p++;
    return h;
}
C2_BNX_HERE static uint16_t v2_bnx_get(uint16_t slot) {
    uint8_t b[2];
    c2_dma_read_or_abort(C2_BNX_BANK, (uint16_t)(C2_BNX_INDEX + slot * 2u), 2u, b);
    return v2_r16(b);
}
C2_BNX_HERE static void v2_bnx_put(uint16_t slot, uint16_t word) {
    uint8_t b[2];
    v2_w16(b, word);
    c2_facade_c2_dma((uint16_t)(uintptr_t)b, 0u,
                     (uint16_t)(C2_BNX_INDEX + slot * 2u), C2_BNX_BANK, 2u);
}
/* Returns the symbol, or NIL with *slot at the first empty probe slot.  A tag
 * match is never taken as equality: the full canonical name decides. */
__FIND__ obj v2_bnx_find(const char *name, uint16_t h, uint16_t *slot) {
    uint16_t s = h & (C2_BNX_SLOTS - 1u), word, idx;
    while ((word = v2_bnx_get(s)) != 0u) {
        idx = (uint16_t)((word & 0x3ffu) - 1u);
        if ((uint8_t)(word >> 10) == (uint8_t)(h >> 10 & 0x3fu)) {
            const char *known = symname(MK_SYMI(idx)); uint8_t i = 0;
            while (known[i] == name[i] && name[i]) ++i;
            if (known[i] == name[i]) return MK_SYMI(idx);
        }
        s = (uint16_t)((s + 1u) & (C2_BNX_SLOTS - 1u));
    }
    *slot = s;
    return NIL;
}
/* Absence is only provable while every symbol below *indexed is in the index. */
__CU__ void v2_bnx_catch_up(uint16_t *indexed) {
    char name[LISP65_SYMBOL_NAME_BUFFER]; uint16_t slot, h; uint8_t i;
    while (*indexed < sym_count()) {
        const char *known = symname(MK_SYMI(*indexed));
        for (i = 0; (name[i] = known[i]) != 0; ++i) {}
        h = v2_bnx_hash(name);
        (void)v2_bnx_find(name, h, &slot);
        v2_bnx_put(slot, (uint16_t)((*indexed + 1u)
            | (uint16_t)(h >> 10 & 0x3fu) << 10));
        ++*indexed;
    }
}
__BUILD__ uint16_t v2_bnx_build(void) {
    uint16_t h, indexed = 0;
    for (h = 0; h < C2_BNX_SLOTS; ++h) v2_bnx_put(h, 0u);
    v2_bnx_catch_up(&indexed);
    return indexed;
}
'''

SINGLE_VALUE = '''
C2_V2_SLICE(10) uint8_t v2_bnx_value(uint16_t *indexed, uint32_t payload,
                                     uint16_t length, uint16_t *value) {
    char name[LISP65_SYMBOL_NAME_BUFFER]; uint16_t h, slot; obj s;
    if (!length || length > LISP65_SYMBOL_NAME_MAX
        || !c2_stream_shelf_read(payload, (uint8_t *)name, length)) return 0;
    name[length] = 0;
    v2_bnx_catch_up(indexed);
    h = v2_bnx_hash(name);
    s = v2_bnx_find(name, h, &slot);
    if (s == NIL) {
        s = sym_create(name);
        if (s == NIL || mem_oom) return 0;
        if (SYMI_IDX(s) == *indexed) {
            v2_bnx_put(slot, (uint16_t)((*indexed + 1u)
                | (uint16_t)(h >> 10 & 0x3fu) << 10));
            ++*indexed;
        }
    }
    *value = (uint16_t)s;
    return 1u;
}
'''

RESOLVE_PHASE = '''
/* New decoder phase: resolve the collected spellings through the transient
 * index.  Entries are consumed in queue order, which is exactly the record walk
 * order of phase 10, so the creation order of new symbols -- and with it every
 * symbol index, the Bank-5 table layout and the name pool -- is what the
 * unsplit walk produces.  The query name may NOT live in sym_name_scratch:
 * confirming a hit overwrites that buffer. */
C2_V2_SLICE(10b) uint8_t c2_stream_phase_10b(void *opaque) {
    c2_stream_context *c = opaque;
    uint8_t e[C2_BNX_ENTRY], b[2]; char name[LISP65_SYMBOL_NAME_BUFFER];
    uint16_t n, indexed, h, slot; uint32_t payload; obj s;
    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;
    if (!c->collect_ready) {
        c->collect_indexed = v2_bnx_build(); c->collect_ready = 1u;
    }
    indexed = c->collect_indexed;
    for (n = 0; n < c->collect_count; ++n) {
        c2_dma_read_or_abort(C2_BNX_BANK,
            (uint16_t)(C2_BNX_QUEUE + n * C2_BNX_ENTRY), C2_BNX_ENTRY, e);
        payload = v2_r24(e);
        if (!e[3] || e[3] > LISP65_SYMBOL_NAME_MAX
            || !c2_stream_shelf_read(payload, (uint8_t *)name, e[3]))
            return v2_fail(c, C2_STREAM_ERR_IO);
        name[e[3]] = 0;
        v2_bnx_catch_up(&indexed);
        h = v2_bnx_hash(name);
        s = v2_bnx_find(name, h, &slot);
        if (s == NIL) {
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
    c->collect_indexed = indexed;
    c->collect_count = 0;
    if (c->collect_image == 0xffffu) {      /* last batch: the owner dies here */
        c->collect_image = 0; c->collect_indexed = 0; c->collect_ready = 0;
        c->phase = 11;
    }
    return C2_STREAM_OK;
}
'''

# ---- collect side: queue writer, session tail and suspend stay resident ----
COLLECT_HELPER = '''
#include "c2_kernal_facade.h"
/* One queue entry: 24-bit shelf payload offset, name length, resolution slot.
 * Nothing is interned here, so no symbol is created on collection authority and
 * an abort before the resolve phase creates none at all. */
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
/* Session/require path: the unchanged direct interner, out of the slice. */
__attribute__((noinline)) static uint8_t v2_bnx_direct(c2_stream_context *c,
        uint8_t kind, uint32_t payload, uint16_t length, uint16_t slot) {
    uint8_t b[2]; uint16_t value;
    if (!c2_stream_name_value(kind, payload, length, &value)) return 0;
    v2_w16(b, value);
    if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset + slot * 2u), b, 2))
        return 0;
    ++c->resolution_cursor;
    return 1;
}
__attribute__((noinline)) static void v2_bnx_suspend(c2_stream_context *c,
                                                     uint16_t image, uint16_t queued) {
    c->collect_image = image; c->collect_count = queued;
}
'''

COLLECT_ENTRY_OLD = \
    '''    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;'''
COLLECT_ENTRY_NEW = '''    uint16_t queued = 0; uint8_t boot;
    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;
    boot = (uint8_t)!c->image_first;'''

COLLECT_LOOP_OLD = \
    '''    for (image = c->image_first; image < c->image_count; ++image) {'''
COLLECT_LOOP_NEW = \
    '''    for (image = boot ? c->collect_image : c->image_first;
         image < c->image_count; ++image) {'''

COLLECT_TAIL_OLD = '''            v2_w16(b, value);
            if (!c2_stream_c2d_write((uint16_t)(c->resolutions_offset
                + (base + i) * 2u), b, 2)) return v2_fail(c, C2_STREAM_ERR_IO);
            ++c->resolution_cursor;
        }
    }
    c->phase = 11; return C2_STREAM_OK;'''
COLLECT_TAIL_NEW = '''            if (boot) {
                v2_bnx_post(queued++, payload, a, (uint16_t)(base + i));
                continue;
            }
            if (!v2_bnx_direct(c, kind, payload, a, (uint16_t)(base + i)))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
        }
        if (boot && queued > (uint16_t)(C2_BNX_BATCH - lc)) {
            v2_bnx_suspend(c, (uint16_t)(image + 1u), queued);
            return C2_STREAM_OK;              /* phase stays 10: resume later */
        }
    }
    if (boot) {
        v2_bnx_suspend(c, 0xffffu, queued);
        return C2_STREAM_OK;
    }
    c->phase = 11; return C2_STREAM_OK;'''

CALL_OLD = '''                || !v2_canonical_name(payload, a)
                || !c2_stream_name_value(kind, payload, a, &value))'''
CALL_COLLECT = '''                || !v2_canonical_name(payload, a))'''
CALL_SINGLE = '''                || !v2_canonical_name(payload, a)
                || !(boot ? v2_bnx_value(&indexed, payload, a, &value)
                          : c2_stream_name_value(kind, payload, a, &value)))'''
SINGLE_ENTRY_NEW = '''    uint16_t indexed = 0; uint8_t boot;
    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;
    boot = (uint8_t)!c->image_first;
    if (boot) indexed = v2_bnx_build();'''

# ---- boot-only collecting phase, its own slice, phase 10 left untouched ----
BOOT_COLLECT_PHASE = '''
#include "c2_kernal_facade.h"
C2_V2_SLICE(10a) void v2_bnx_post(uint16_t n, uint32_t payload,
                                  uint16_t length, uint16_t slot) {
    uint8_t e[C2_BNX_ENTRY];
    e[0] = (uint8_t)payload; e[1] = (uint8_t)(payload >> 8);
    e[2] = (uint8_t)(payload >> 16); e[3] = (uint8_t)length;
    v2_w16(e + 4, slot);
    c2_facade_c2_dma((uint16_t)(uintptr_t)e, 0u,
                     (uint16_t)(C2_BNX_QUEUE + n * C2_BNX_ENTRY),
                     C2_BNX_BANK, C2_BNX_ENTRY);
}
/* Boot-only collecting walk.  image_first is zero by construction; nothing is
 * interned and no resolution is written here, so decoder phase 10 keeps its
 * present body byte for byte for every session append and require. */
C2_V2_SLICE(10a) uint8_t c2_stream_phase_10a(void *opaque) {
    c2_stream_context *c = opaque; uint8_t im[20], h[24], r[8];
    uint16_t image, i, lc, lo, so, sb, base, a, queued = 0;
    uint32_t meta, payload, arg1;
    if (!c || c->phase != 10u || c->error || c->image_first)
        return C2_STREAM_ERR_STATE;
    for (image = c->collect_image; image < c->image_count; ++image) {
        if (!v2_image_read(c, image, im)) return v2_fail(c, C2_STREAM_ERR_IO);
        meta = v2_r24(im + 13); base = v2_r16(im + 6);
        if (!c2_stream_shelf_read(meta, h, sizeof(h)))
            return v2_fail(c, C2_STREAM_ERR_IO);
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
                || !v2_canonical_name(payload, a))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            v2_bnx_post(queued++, payload, a, (uint16_t)(base + i));
        }
        if (queued > (uint16_t)(C2_BNX_BATCH - lc)) {
            c->collect_image = (uint16_t)(image + 1u);
            c->collect_count = queued;
            return C2_STREAM_OK;
        }
    }
    c->collect_image = 0xffffu; c->collect_count = queued;
    return C2_STREAM_OK;
}
'''

PHASE_MARK = \
    '/* Resolve exported-call and general-symbol spellings through one interner. */'
PHASE10_BEGIN = '#if C2_STREAM_V2_PHASE == 10\nC2_V2_SLICE(10)'

SYMBOL_OLD = 'static obj new_symbol(const char *name) {'
SYMBOL_NEW = '__attribute__((noinline)) obj sym_create(const char *name) {'


def _one(text, old, what):
    if text.count(old) != 1:
        raise ValueError('anchor not unique (%d): %s' % (text.count(old), what))
    return text


def index_body(slice_name, find, catch_up, build):
    return (INDEX_BODY.replace('__SL__', '"%s"' % slice_name)
                      .replace('__FIND__', find)
                      .replace('__CU__', catch_up)
                      .replace('__BUILD__', build))


def phase10_body(text):
    begin = text.index(PHASE10_BEGIN)
    end = text.index('#endif', begin)
    return begin, end, text[begin:end]


def _head(text, begin, block):
    return _one(text[:begin], PHASE_MARK, 'phase mark').replace(
        PHASE_MARK, '#if C2_STREAM_V2_PHASE == 10\n' + block + '#endif\n' + PHASE_MARK, 1)


def decoder_single(text):
    """The withdrawn one-phase form, every helper inside the phase-10 slice."""
    begin, end, body = phase10_body(text)
    for old, what in ((CALL_OLD, 'single call site'),
                      (COLLECT_ENTRY_OLD, 'single entry')):
        _one(body, old, what)
    body = body.replace(CALL_OLD, CALL_SINGLE).replace(
        COLLECT_ENTRY_OLD, SINGLE_ENTRY_NEW)
    block = GEOMETRY + index_body('10', 'C2_V2_SLICE(10)', 'C2_V2_SLICE(10)',
                                  'C2_V2_SLICE(10)') + SINGLE_VALUE
    return _head(text, begin, block) + body + text[end:]


def decoder_collect(text):
    """Shape A: phase 10 collects at boot and keeps the direct session path."""
    begin, end, body = phase10_body(text)
    for old, what in ((CALL_OLD, 'collect call site'),
                      (COLLECT_ENTRY_OLD, 'collect entry'),
                      (COLLECT_LOOP_OLD, 'collect image loop'),
                      (COLLECT_TAIL_OLD, 'collect tail')):
        _one(body, old, what)
    body = (body.replace(CALL_OLD, CALL_COLLECT)
                .replace(COLLECT_ENTRY_OLD, COLLECT_ENTRY_NEW)
                .replace(COLLECT_LOOP_OLD, COLLECT_LOOP_NEW)
                .replace(COLLECT_TAIL_OLD, COLLECT_TAIL_NEW))
    return _head(text, begin, GEOMETRY + COLLECT_HELPER) + body + text[end:]


def decoder_boot_collect(text):
    """Shape C: a dedicated boot-only collect phase; phase 10 stays untouched."""
    return text + ('\n#if C2_STREAM_V2_PHASE == 17\n' + GEOMETRY
                   + BOOT_COLLECT_PHASE + '#endif\n')


def decoder_resolve(text):
    """The new resolve phase (wrapper phase number 16, slice `10b`)."""
    return text + ('\n#if C2_STREAM_V2_PHASE == 16\n' + GEOMETRY
                   + index_body('10b', RESIDENT, 'C2_V2_SLICE(10b)',
                                'C2_V2_SLICE(10b)')
                   + RESOLVE_PHASE + '#endif\n')


RESIDENT = '__attribute__((noinline)) static'


def candidate_symbol(text):
    _one(text, SYMBOL_OLD, 'symbol.c new_symbol')
    _one(text, 'return new_symbol(name);', 'symbol.c intern call')
    return (text.replace(SYMBOL_OLD, SYMBOL_NEW)
                .replace('return new_symbol(name);', 'return sym_create(name);'))


def compile_one(directory, command, wrapper, allowed, owned):
    flags = list(command[1:command.index('-c')])
    deps = run([command[0], *flags, '-M', '-MT', 'probe', str(wrapper)])
    put(directory / (wrapper.stem + '.d'), deps)
    inputs = []
    for path in shlex.split(deps.replace('\\\n', ' ').split(':', 1)[1]):
        q = (ROOT / path).resolve()
        if q not in owned:
            if q not in allowed or sha(q) != allowed[q]:
                raise ValueError('unbound include: ' + str(q))
        inputs.append({'path': str(q.relative_to(ROOT)), 'sha256': sha(q)})
    obj = directory / (wrapper.stem + '.o')
    if obj.exists():
        raise ValueError('experiment artifact already exists: ' + str(obj))
    cc = [command[0], *flags, '-fno-lto', '-c', str(wrapper), '-o', str(obj)]
    put(directory / (wrapper.stem + '.log'), run(cc))
    truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    sections = {s.name: s.bytes for s in truth.sections
                if s.name.startswith(('.text', '.rodata', '.data', '.bss',
                                      '.lisp65_rt_')) and s.bytes}
    symbols = {s.name: s.bytes for s in truth.symbols if s.bytes}
    return dict(sections=sections, symbols=symbols, inputs=inputs, command=cc,
                object_sha256=sha(obj))


def summarize(sections):
    slices = {k: v for k, v in sections.items() if k.startswith('.lisp65_rt_')}
    return dict(slice_sections=slices, slice_bytes=sum(slices.values()),
                slice_headroom=SLICE_CAP - sum(slices.values()),
                ordinary_text=sum(v for k, v in sections.items()
                                  if k.startswith('.text')),
                rodata=sum(v for k, v in sections.items() if k.startswith('.rodata')),
                bss=sum(v for k, v in sections.items() if k.startswith('.bss')),
                data=sum(v for k, v in sections.items() if k.startswith('.data')))


CONTEXT_OLD = """    uint8_t phase;
    uint8_t finished;
    uint8_t error;
    uint8_t reserved;
} c2_stream_context;"""
CONTEXT_NEW = """    uint8_t phase;
    uint8_t finished;
    uint8_t error;
    uint8_t reserved;
    /* Boot-name-index split: resumption of the collecting walk and progress of
     * the transient index owner.  Zero for every session append. */
    uint16_t collect_image;
    uint16_t collect_count;
    uint16_t collect_indexed;
    uint8_t collect_ready;
    uint8_t collect_pad;
} c2_stream_context;"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path,
                    default=ROOT / 'build/boot-name-index-split-probe-r1')
    out = ap.parse_args().out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('outputs must be fresh experiment artifacts under build/')
    out.mkdir(parents=True, exist_ok=True)
    generated = BASE / 'generated-product-sources'
    proof = json.loads((BASE / 'command-proof.json').read_text())
    closure_path = BASE / 'active-include-check/receipt.json'
    closure = json.loads(closure_path.read_text())
    allowed = {(ROOT / d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}

    def command_for(suffix):
        return next(c for c in proof['commands'] if '-c' in c
                    and c[c.index('-c') + 1].endswith(suffix))

    phase10_cmd = command_for('/c2-stream-v2-phase-10.c')
    symbol_cmd = command_for('src/symbol.c')
    decoder = (generated / 'c2-stream-v2-decoder.c').read_text()
    v2_header = (generated / 'c2-stream-v2-decoder.h').read_text()
    v1_header = (generated / 'c2-stream-decoder.h').read_text()
    symbol = (ROOT / 'src/symbol.c').read_text()
    wrapper10 = (generated / 'c2-stream-v2-phase-10.c').read_bytes()
    split_header = _one(v1_header, CONTEXT_OLD, 'context tail').replace(
        CONTEXT_OLD, CONTEXT_NEW)
    results = []

    def unit(variant, files, cmd, wrapper_name, label, note):
        directory = out / variant
        directory.mkdir(exist_ok=True)
        owned = set()
        for name, data in files.items():
            path = directory / name
            put(path, data)
            owned.add(path.resolve())
        row = compile_one(directory, cmd, directory / wrapper_name, allowed, owned)
        results.append(dict(variant=variant, unit=label, note=note,
                            summary=summarize(row['sections']), **row))

    headers = {'c2-stream-v2-decoder.h': v2_header,
               'c2-stream-decoder.h': split_header}

    unit('baseline-phase-10',
         {'c2-stream-v2-decoder.c': decoder,
          'c2-stream-v2-phase-10.c': wrapper10},
         phase10_cmd, 'c2-stream-v2-phase-10.c', 'phase-10',
         'the accepted r4 world, unmodified')
    unit('baseline-symbol', {'symbol.c': symbol}, symbol_cmd, 'symbol.c',
         'symbol.c', 'the accepted r4 world, unmodified')
    unit('one-phase-in-slice',
         {'c2-stream-v2-decoder.c': decoder_single(decoder),
          'c2-stream-v2-phase-10.c': wrapper10},
         phase10_cmd, 'c2-stream-v2-phase-10.c', 'phase-10',
         'withdrawn one-phase form with every helper inside the slice')
    unit('split-a-collect',
         dict(headers, **{'c2-stream-v2-decoder.c': decoder_collect(decoder),
                          'c2-stream-v2-phase-10.c': wrapper10}),
         phase10_cmd, 'c2-stream-v2-phase-10.c', 'phase-10',
         'shape A: phase 10 collects at boot, direct session path kept')
    unit('split-c-collect',
         dict(headers, **{'c2-stream-v2-decoder.c': decoder_boot_collect(decoder),
                          'c2-stream-v2-phase-10a.c':
                              '#define C2_STREAM_V2_PHASE 17\n'
                              '#include "c2-stream-v2-decoder.c"\n'}),
         phase10_cmd, 'c2-stream-v2-phase-10a.c', 'phase-10a',
         'shape C: dedicated boot-only collect phase; phase 10 untouched')
    unit('split-resolve',
         dict(headers, **{'c2-stream-v2-decoder.c': decoder_resolve(decoder),
                          'c2-stream-v2-phase-10b.c':
                              '#define C2_STREAM_V2_PHASE 16\n'
                              '#include "c2-stream-v2-decoder.c"\n'}),
         phase10_cmd, 'c2-stream-v2-phase-10b.c', 'phase-10b',
         'the new resolve phase, shared by shapes A and C')
    unit('split-symbol', {'symbol.c': candidate_symbol(symbol)}, symbol_cmd,
         'symbol.c', 'symbol.c', 'new_symbol exported as sym_create')

    by = {r['variant']: r['summary'] for r in results}
    base_text = by['baseline-symbol']['ordinary_text']
    shapes = {
        'one-phase': dict(
            new_slices=0,
            slice_bytes={'10': by['one-phase-in-slice']['slice_bytes']},
            resident_delta=by['one-phase-in-slice']['ordinary_text']
                           + by['split-symbol']['ordinary_text'] - base_text,
            holds_cap=by['one-phase-in-slice']['slice_bytes'] <= SLICE_CAP),
        'shape-a': dict(
            new_slices=1,
            slice_bytes={'10': by['split-a-collect']['slice_bytes'],
                         '10b': by['split-resolve']['slice_bytes']},
            resident_delta=by['split-a-collect']['ordinary_text']
                           + by['split-resolve']['ordinary_text']
                           + by['split-symbol']['ordinary_text'] - base_text,
            holds_cap=max(by['split-a-collect']['slice_bytes'],
                          by['split-resolve']['slice_bytes']) <= SLICE_CAP),
        'shape-c': dict(
            new_slices=2,
            slice_bytes={'10': by['baseline-phase-10']['slice_bytes'],
                         '10a': by['split-c-collect']['slice_bytes'],
                         '10b': by['split-resolve']['slice_bytes']},
            resident_delta=by['split-c-collect']['ordinary_text']
                           + by['split-resolve']['ordinary_text']
                           + by['split-symbol']['ordinary_text'] - base_text,
            holds_cap=max(by['split-c-collect']['slice_bytes'],
                          by['split-resolve']['slice_bytes']) <= SLICE_CAP),
    }

    receipt = dict(
        claim='PAIRED NON-LTO OBJECT PROJECTION ONLY; NOT A SEED OR LINK PRICE',
        budget=dict(seed=0, finale=0, link=0, device_contacts=0),
        world=str(BASE.relative_to(ROOT)),
        world_final_sha256=sha(BASE / 'resident-island-seed.prg.elf'),
        command_proof_sha256=sha(BASE / 'command-proof.json'),
        include_closure_sha256=sha(closure_path),
        compiler_sha256=sha(Path(phase10_cmd[0])),
        slice_capacity=SLICE_CAP,
        linked_phase_10_bytes_in_world=1288,
        overlay_slices_used_in_world=62,
        overlay_slice_catalog_capacity=64,
        bank5=dict(free_interval='offset 56,960 .. 65,535 of bank 5',
                   free_interval_bytes=8576, manifest_free_floor=8576,
                   index_slots=1024, index_bytes=2048,
                   queue_entry_bytes=6, queue_batch_entries=1024,
                   queue_bytes=6144, transient_total=8192,
                   floor_after_rebinding=384,
                   unbatched_queue_bytes_required=12426),
        shapes=shapes, results=results)
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    for r in results:
        s = r['summary']
        print('%-20s %-10s slices=%-40s text=%4d rodata=%d bss=%d' % (
            r['variant'], r['unit'], s['slice_sections'], s['ordinary_text'],
            s['rodata'], s['bss']))
    print()
    print(json.dumps(shapes, indent=2))


if __name__ == '__main__':
    main()
