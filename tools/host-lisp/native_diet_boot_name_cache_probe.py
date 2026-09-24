"""Price a boot-only phase-10 repeat cache for name resolution (no link, no Seed).

Off-product, paired non-LTO object projection like the other native-diet
probes. Only while the boot decoder runs phase 10 over the whole world
(image_first == 0), a stack cache maps a name hash to the symbol the
resident interner returned for it. A hit requires full equality with that
symbol's stored spelling, so it returns exactly what intern would. Misses,
appends, require and interactive intern are unchanged. No memory owner,
transport seam or resident code is added.
"""
import argparse
import json
from pathlib import Path
from native_diet_object_probe import ROOT, BASE, sha, put
from native_diet_boot_name_index_probe import compile_one

CACHE_DECL = r'''
#if C2_STREAM_V2_PHASE == 10
/* Boot-only repeat cache for phase 10 (stack-scoped, holds no truth).
 * A hit is accepted only after full name equality with the cached symbol's
 * stored spelling; every miss takes the unchanged resident interner. */
#include "symbol.h"
#include <string.h>
#ifndef C2_BOOT_NAME_CACHE
#define C2_BOOT_NAME_CACHE 32u
#endif
/* Returns the cached symbol whose stored spelling equals the shelf name, or 0.
 * A read failure is a miss; the unchanged resident path then reports it. */
C2_V2_SLICE(10) static uint16_t v2_boot_name_hit(uint16_t *cache, uint32_t payload,
                                                 uint8_t length, uint8_t *slot) {
    char name[LISP65_SYMBOL_NAME_BUFFER]; uint16_t hash = 0; uint8_t j;
    if (!c2_stream_shelf_read(payload, (uint8_t *)name, length)) return 0;
    name[length] = 0;
    for (j = 0; j < length; ++j)
        hash = (uint16_t)((uint16_t)(hash << 5) + hash) ^ (uint8_t)name[j];
    *slot = (uint8_t)(hash & (C2_BOOT_NAME_CACHE - 1u));
    if (!cache[*slot]) return 0;
    {
        const char *known = symname((obj)cache[*slot]);
        for (j = 0; known[j] == name[j] && name[j]; ++j) {}
        return known[j] == name[j] ? cache[*slot] : 0u;
    }
}
#endif
'''

CALL_OLD = '''            if (r[1] || r[7] || !v2_string_record(meta + so, sb, arg1, a, &payload)
                || !v2_canonical_name(payload, a)
                || !c2_stream_name_value(kind, payload, a, &value))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);'''
CALL_NEW = '''            if (r[1] || r[7] || !v2_string_record(meta + so, sb, arg1, a, &payload)
                || !v2_canonical_name(payload, a))
                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
            slot = 0;
            value = (boot && a <= LISP65_SYMBOL_NAME_MAX)
                ? v2_boot_name_hit(cache, payload, (uint8_t)a, &slot) : 0u;
            if (!value) {
                if (!c2_stream_name_value(kind, payload, a, &value))
                    return v2_fail(c, C2_STREAM_ERR_RESOLUTION);
                if (boot) cache[slot] = value;
            }'''
ENTRY_OLD = '''    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;'''
ENTRY_NEW = '''    uint16_t cache[C2_BOOT_NAME_CACHE]; uint8_t boot, slot;
    if (!c || c->phase != 10u || c->error) return C2_STREAM_ERR_STATE;
    boot = (uint8_t)!c->image_first;
    if (boot) memset(cache, 0, sizeof cache);'''
PHASE_MARK = '/* Resolve exported-call and general-symbol spellings through one interner. */'


def candidate_decoder(text, entries):
    begin = text.index('#if C2_STREAM_V2_PHASE == 10\nC2_V2_SLICE(10)')
    end = text.index('#endif', begin)
    body = text[begin:end]
    if body.count(CALL_OLD) != 1 or body.count(ENTRY_OLD) != 1 or text.count(PHASE_MARK) != 1:
        raise ValueError('phase-10 anchors changed')
    body = body.replace(CALL_OLD, CALL_NEW).replace(ENTRY_OLD, ENTRY_NEW)
    decl = CACHE_DECL.replace('#ifndef C2_BOOT_NAME_CACHE',
                              '#define C2_BOOT_NAME_CACHE %du\n#ifndef C2_BOOT_NAME_CACHE' % entries)
    head = text[:begin].replace(PHASE_MARK, decl + PHASE_MARK, 1)
    return head + body + text[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-diet-boot-name-cache-probe-r3')
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
    command = next(c for c in proof['commands'] if '-c' in c
                   and c[c.index('-c') + 1].endswith('/c2-stream-v2-phase-10.c'))
    decoder_source = generated / 'c2-stream-v2-decoder.c'
    original = decoder_source.read_text()
    results = []
    variants = [('baseline', original)] + [
        ('boot-name-cache-%d' % n, candidate_decoder(original, n)) for n in (16, 32, 64)]
    for variant, text in variants:
        directory = out / variant
        directory.mkdir(exist_ok=True)
        decoder = directory / 'c2-stream-v2-decoder.c'
        put(decoder, text)
        wrapper = directory / 'c2-stream-v2-phase-10.c'
        put(wrapper, (generated / 'c2-stream-v2-phase-10.c').read_bytes())
        row = compile_one(directory, command, wrapper, allowed, {decoder, wrapper})
        results.append(dict(variant=variant, unit='phase-10', **row))
    receipt = dict(claim='NON-LTO OBJECT PLACEMENT PROJECTION ONLY; NOT A SEED OR LINK PRICE',
                   budget=dict(seed=0, finale=0, link=0),
                   decoder_sha256=sha(decoder_source),
                   include_closure_sha256=sha(closure_path),
                   slice_capacity=1792, results=results)
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    for row in results:
        print(row['variant'], row['sections'])


if __name__ == '__main__':
    main()
