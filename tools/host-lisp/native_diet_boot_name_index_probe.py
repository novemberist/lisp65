"""Price a boot-only phase-10 name index off product (no link, no Seed).

The candidate replaces, only while the boot decoder runs phase 10 over the
whole world (image_first == 0), the resident linear intern with a transient
open-addressed index in the Bank-5 free tail. The index holds no truth: every
hit is confirmed by full name equality, a count catch-up covers symbols made
elsewhere, validity is stack-scoped to the one phase call, and append,
require and interactive intern keep the unchanged resident path.

Prices are paired, non-LTO object projections against the accepted Set-A
producer's command and include closure, like the other native-diet probes.
"""
import argparse
import json
from pathlib import Path
import shlex
from native_diet_object_probe import ROOT, BASE, sha, put, run
from elf_truth import ElfTruth

INDEX = r'''
#if C2_STREAM_V2_PHASE == 10
/* Boot-only transient name index (Bank 5 free tail). Holds no truth:
 * a hit is confirmed by full name equality; an absent slot proves absence
 * only because every symbol below `indexed` is present and the count is
 * caught up before each query. Validity is this phase call's stack frame. */
#include "symbol.h"
#include "mem.h"
#include "c2_kernal_facade.h"
void c2_dma_read_or_abort(uint8_t bank, uint16_t offset, uint16_t length,
                          uint8_t *destination);
#define C2_BIX_SLOTS 1024u
#define C2_BIX_BANK 5u
#define C2_BIX_BASE 0xde80u
extern obj sym_create(const char *name);
C2_V2_LOCAL uint16_t v2_bix_hash(const char *p) {
    uint16_t h = 0;
    while (*p) h = (uint16_t)((uint16_t)(h << 5) + h) ^ (uint8_t)*p++;
    return h;
}
C2_V2_LOCAL uint16_t v2_bix_get(uint16_t slot) {
    uint8_t b[2];
    c2_dma_read_or_abort(C2_BIX_BANK, (uint16_t)(C2_BIX_BASE + slot * 2u), 2u, b);
    return v2_r16(b);
}
C2_V2_LOCAL void v2_bix_put(uint16_t slot, uint16_t word) {
    uint8_t b[2];
    v2_w16(b, word);
    c2_facade_c2_dma((uint16_t)(uintptr_t)b, 0u,
                     (uint16_t)(C2_BIX_BASE + slot * 2u), C2_BIX_BANK, 2u);
}
/* Returns the symbol, or NIL with *slot at the first empty probe slot. */
C2_V2_LOCAL obj v2_bix_find(const char *name, uint16_t h, uint16_t *slot) {
    uint16_t s = h & (C2_BIX_SLOTS - 1u), word, idx;
    while ((word = v2_bix_get(s)) != 0u) {
        idx = (uint16_t)((word & 0x3ffu) - 1u);
        if ((uint8_t)(word >> 10) == (uint8_t)(h >> 10 & 0x3fu)) {
            const char *known = symname(MK_SYMI(idx)); uint8_t i = 0;
            while (known[i] == name[i] && name[i]) ++i;
            if (known[i] == name[i]) return MK_SYMI(idx);
        }
        s = (uint16_t)((s + 1u) & (C2_BIX_SLOTS - 1u));
    }
    *slot = s;
    return NIL;
}
C2_V2_LOCAL void v2_bix_catch_up(uint16_t *indexed) {
    char name[LISP65_SYMBOL_NAME_BUFFER]; uint16_t slot; uint8_t i;
    while (*indexed < sym_count()) {
        const char *known = symname(MK_SYMI(*indexed));
        for (i = 0; (name[i] = known[i]) != 0; ++i) {}
        (void)v2_bix_find(name, v2_bix_hash(name), &slot);
        v2_bix_put(slot, (uint16_t)((*indexed + 1u)
            | (uint16_t)(v2_bix_hash(name) >> 10 & 0x3fu) << 10));
        ++*indexed;
    }
}
C2_V2_LOCAL uint8_t v2_bix_begin(uint16_t *indexed) {
    uint8_t zero[32]; uint16_t at;
    for (at = 0; at < sizeof zero; ++at) zero[at] = 0;
    for (at = 0; at < C2_BIX_SLOTS * 2u; at = (uint16_t)(at + sizeof zero))
        c2_facade_c2_dma((uint16_t)(uintptr_t)zero, 0u,
                         (uint16_t)(C2_BIX_BASE + at), C2_BIX_BANK, sizeof zero);
    *indexed = 0;
    v2_bix_catch_up(indexed);
    return 1u;
}
C2_V2_LOCAL uint8_t v2_bix_value(uint16_t *indexed, uint32_t payload,
                                 uint16_t length, uint16_t *value) {
    char name[LISP65_SYMBOL_NAME_BUFFER]; uint16_t h, slot; obj s;
    if (!length || length > LISP65_SYMBOL_NAME_MAX
        || !c2_stream_shelf_read(payload, (uint8_t *)name, length)) return 0;
    name[length] = 0;
    v2_bix_catch_up(indexed);
    h = v2_bix_hash(name);
    s = v2_bix_find(name, h, &slot);
    if (s == NIL) {
        s = sym_create(name);
        if (s == NIL || mem_oom) return 0;
        if (SYMI_IDX(s) == *indexed) {
            v2_bix_put(slot, (uint16_t)((*indexed + 1u) | (uint16_t)(h >> 10 & 0x3fu) << 10));
            ++*indexed;
        }
    }
    *value = (uint16_t)s;
    return 1u;
}
#endif
'''

CALL_OLD = '''                || !v2_canonical_name(payload, a)
                || !c2_stream_name_value(kind, payload, a, &value))'''
CALL_NEW = '''                || !v2_canonical_name(payload, a)
                || !(boot ? v2_bix_value(&indexed, payload, a, &value)
                          : c2_stream_name_value(kind, payload, a, &value)))'''
ENTRY_OLD = '''    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;'''
ENTRY_NEW = '''    uint16_t indexed = 0; uint8_t boot;
    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;
    boot = (uint8_t)(!c->image_first && v2_bix_begin(&indexed));'''
PHASE_MARK = '/* Resolve exported-call and general-symbol spellings through one interner. */'

SYMBOL_OLD = 'static obj new_symbol(const char *name) {'
SYMBOL_NEW = '__attribute__((noinline)) obj sym_create(const char *name) {'


def candidate_decoder(text):
    for old in (CALL_OLD, ENTRY_OLD, PHASE_MARK):
        if text.count(old) != 1 and old != CALL_OLD:
            raise ValueError('anchor not unique: ' + old[:50])
    begin = text.index('#if C2_STREAM_V2_PHASE == 10\nC2_V2_SLICE(10)')
    end = text.index('#endif', begin)
    body = text[begin:end]
    if body.count(CALL_OLD) != 1 or body.count(ENTRY_OLD) != 1:
        raise ValueError('phase-10 anchors changed')
    body = body.replace(CALL_OLD, CALL_NEW).replace(ENTRY_OLD, ENTRY_NEW)
    head = text[:begin].replace(PHASE_MARK, INDEX + PHASE_MARK, 1)
    return head + body + text[end:]


def candidate_symbol(text):
    if text.count(SYMBOL_OLD) != 1 or text.count('return new_symbol(name);') != 1:
        raise ValueError('symbol.c anchors changed')
    text = text.replace(SYMBOL_OLD, SYMBOL_NEW)
    return text.replace('return new_symbol(name);', 'return sym_create(name);')


def compile_one(directory, command, wrapper, allowed, owned):
    flags = command[1:command.index('-c')]
    deps = run([command[0], *flags, '-M', '-MT', 'probe', str(wrapper)])
    put(directory / (wrapper.stem + '.d'), deps)
    inputs = []
    for path in shlex.split(deps.replace('\\\n', ' ').split(':', 1)[1]):
        p = (ROOT / path).resolve()
        if p not in owned:
            if p not in allowed or sha(p) != allowed[p]:
                raise ValueError('unbound include: ' + str(p))
        inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p)})
    obj = directory / (wrapper.stem + '.o')
    if obj.exists():
        raise ValueError('experiment artifact already exists: ' + str(obj))
    cc = [command[0], *flags, '-fno-lto', '-c', str(wrapper), '-o', str(obj)]
    put(directory / (wrapper.stem + '.log'), run(cc))
    truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    sections = {s.name: s.bytes for s in truth.sections
                if s.name.startswith(('.text', '.rodata', '.data', '.bss', '.lisp65_rt_'))}
    return dict(sections=sections, inputs=inputs, command=cc, object_sha256=sha(obj))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-diet-boot-name-index-probe-r1')
    out = parser.parse_args().out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('outputs must be fresh experiment artifacts')
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

    decoder_source = generated / 'c2-stream-v2-decoder.c'
    symbol_source = ROOT / 'src/symbol.c'
    original_decoder = decoder_source.read_text()
    original_symbol = symbol_source.read_text()
    results = []
    for variant, decoder_text, symbol_text in [
            ('baseline', original_decoder, original_symbol),
            ('boot-name-index', candidate_decoder(original_decoder),
             candidate_symbol(original_symbol))]:
        directory = out / variant
        directory.mkdir(exist_ok=True)
        decoder = directory / 'c2-stream-v2-decoder.c'
        put(decoder, decoder_text)
        wrapper = directory / 'c2-stream-v2-phase-10.c'
        put(wrapper, (generated / 'c2-stream-v2-phase-10.c').read_bytes())
        row = compile_one(directory, command_for('/c2-stream-v2-phase-10.c'),
                          wrapper, allowed, {decoder, wrapper})
        results.append(dict(variant=variant, unit='phase-10', **row))
        symbol = directory / 'symbol.c'
        put(symbol, symbol_text)
        row = compile_one(directory, command_for('src/symbol.c'),
                          symbol, allowed, {symbol})
        results.append(dict(variant=variant, unit='symbol.c', **row))
    receipt = dict(claim='NON-LTO OBJECT PLACEMENT PROJECTION ONLY; NOT A SEED OR LINK PRICE',
                   budget=dict(seed=0, finale=0, link=0),
                   decoder_sha256=sha(decoder_source), symbol_sha256=sha(symbol_source),
                   include_closure_sha256=sha(closure_path),
                   slice_capacity=1792, results=results)
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    for row in results:
        print(row['variant'], row['unit'], row['sections'])


if __name__ == '__main__':
    main()
