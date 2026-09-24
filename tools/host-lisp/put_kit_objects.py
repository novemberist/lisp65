"""Off-product Put-Kit price experiment; never a Seed or an admission.

Replay the current world's compiler flags and SHA-checked Include closure.
Only generated experiment copies change. All sections, not just the moved
kit, are counted. The guarded probe is shared by decoder and publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from boot_name_index_link_preprobe import compile_command_of
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/boot-only-carrier-product-r1/wplto'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Put-Kit source seam changed: ' + old)
    return text.replace(old, new, 1)


def decoder_form(text):
    for kind, name in [('uint16_t', 'hash'), ('void', 'put')]:
        text = once(text, f'C2_BNX_HERE static {kind} v2_bnx_{name}',
                    f'__attribute__((noinline)) {kind} v2_bnx_{name}')
    text = once(text, '__attribute__((noinline)) static obj v2_bnx_find',
                '__attribute__((noinline)) obj v2_bnx_find')
    text = once(text, 'C2_V2_SLICE(10b) void v2_bnx_catch_up',
                '__attribute__((noinline)) void v2_bnx_catch_up')
    text = once(text,
                '    uint16_t s = h & (C2_BNX_SLOTS - 1u), word, idx;\n'
                '    while ((word = v2_bnx_get(s)) != 0u) {',
                '    uint16_t s = h & (C2_BNX_SLOTS - 1u), word, idx;\n'
                '    uint16_t left = C2_BNX_SLOTS;\n'
                '    *slot = 0xffffu;\n'
                '    while (left--) {\n'
                '        word = v2_bnx_get(s);\n'
                '        if (!word) { *slot = s; return NIL; }\n'
                '        if (!(word & 0x3ffu) || (word & 0x3ffu) > sym_count())\n'
                '            return NIL;')
    text = once(text, '    *slot = s;\n    return NIL;', '    return NIL;')
    text = once(text, '        (void)v2_bnx_find(name, h, &slot);\n',
                '        if (v2_bnx_find(name, h, &slot) != NIL) {\n'
                '            ++*indexed; continue;\n'
                '        }\n'
                '        if (slot == 0xffffu) { *indexed = 0xffffu; return; }\n')
    text = once(text, '        v2_bnx_catch_up(&indexed);\n',
                '        v2_bnx_catch_up(&indexed);\n'
                '        if (indexed == 0xffffu)\n'
                '            return v2_fail(c, C2_STREAM_ERR_RESOLUTION);\n')
    text = once(text, '        if (s == NIL) {\n            s = sym_create(name);',
                '        if (s == NIL) {\n'
                '            if (slot == 0xffffu)\n'
                '                return v2_fail(c, C2_STREAM_ERR_RESOLUTION);\n'
                '            s = sym_create(name);')
    return text


def runtime_form(text):
    start = text.index('/* The resolve slice reads the boot name index')
    end = text.index('\n#endif', start)
    replacement = '''/* Put-Kit experiment: owner live only during boot publication.
 * The caller's indexed frontier is local, not a second persistent truth.
 * Any incomplete owner falls back to the existing linear interner. */
extern uint16_t v2_bnx_hash(const char *name);
extern obj v2_bnx_find(const char *name, uint16_t hash, uint16_t *slot);
extern void v2_bnx_put(uint16_t slot, uint16_t word);
extern void v2_bnx_catch_up(uint16_t *indexed);
extern obj sym_create(const char *name);
#define C2_PUBLISH_BNX_LIVE(head) \\
    ((head)[8] == 1u && (head)[9] == 0u \\
     && c2_u16(head) == LISP65_C2_BNX_DONE && c2_u16((head) + 4) == 0u \\
     && c2_u16((head) + 6) <= sym_count())
C2_APPEND_SECTION("publish_plan_resolve")
static obj c2_publish_bnx_lookup(const uint8_t *row, uint16_t *indexed) {
    char name[LISP65_SYMBOL_NAME_BUFFER];
    uint16_t h, slot; obj symbol;
    uint8_t length = row[3];
    if (*indexed == 0xffffu || !length || length > LISP65_SYMBOL_NAME_MAX
        || !c2_stream_shelf_read(c2_u24(row) + 2u, name, length)) return NIL;
    name[length] = 0;
    v2_bnx_catch_up(indexed);
    if (*indexed != sym_count()) return NIL;
    h = v2_bnx_hash(name);
    symbol = v2_bnx_find(name, h, &slot);
    if (symbol != NIL) return symbol;
    if (slot == 0xffffu) { *indexed = 0xffffu; return NIL; }
    symbol = sym_create(name);
    if (symbol == NIL || mem_oom) return NIL;
    v2_bnx_put(slot, (uint16_t)((SYMI_IDX(symbol) + 1u)
        | (uint16_t)(h >> 10 & 0x3fu) << 10));
    *indexed = sym_count();
    return symbol;
}'''
    text = text[:start] + replacement + text[end:]
    text = once(text, '    uint8_t head[LISP65_C2_BNX_HEAD_BYTES], live;',
                '    uint8_t head[LISP65_C2_BNX_HEAD_BYTES], live;\n'
                '    uint16_t indexed;')
    text = once(text, '    /* Read once; the owner is never written from here. */',
                '    /* The index may grow; the header frontier stays conservative. */')
    text = once(text, '    live = (uint8_t)C2_PUBLISH_BNX_LIVE(head);',
                '    live = (uint8_t)C2_PUBLISH_BNX_LIVE(head);\n'
                '    indexed = c2_u16(head + 6);')
    text = once(text, 'c2_publish_bnx_lookup(row)', 'c2_publish_bnx_lookup(row, &indexed)')
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=False)
    proof = json.loads((BASE / 'command-proof.json').read_text())
    closure = json.loads((BASE / 'active-include-check/receipt.json').read_text())
    allowed = {(ROOT / d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}
    commands = [c for c in proof['commands'] if '-c' in c and
                Path(c[c.index('-c') + 1]).name in
                ('c2_product_runtime.c', 'c2-stream-v2-phase-10b.c')]
    assert len(commands) == 2
    decoders = [p for p in allowed if p.name == 'c2-stream-v2-decoder.c']
    assert len(decoders) == 1
    decoder = decoders[0]
    assert sha(decoder) == allowed[decoder]
    rows = []
    for variant in ('baseline', 'put-kit'):
        folder = out / variant
        folder.mkdir()
        changed = set()
        include = folder / decoder.name
        include.write_text(decoder.read_text() if variant == 'baseline'
                           else decoder_form(decoder.read_text()))
        changed.add(include.resolve())
        for command in commands:
            flags, consumed, _ = compile_command_of(command)
            original = (ROOT / consumed).resolve()
            assert sha(original) == allowed[original]
            source = folder / original.name
            text = original.read_text()
            if variant == 'put-kit' and source.name == 'c2_product_runtime.c':
                text = runtime_form(text)
            source.write_text(text)
            changed.add(source.resolve())
            dep = subprocess.check_output([command[0], *flags, '-M', '-MT', 'probe',
                                           str(source)], text=True)
            inputs = []
            for name in shlex.split(dep.replace('\\\n', ' ').split(':', 1)[1]):
                p = (ROOT / name).resolve()
                if p not in changed:
                    assert p in allowed and sha(p) == allowed[p], 'unbound Include: ' + str(p)
                inputs.append(dict(path=str(p.relative_to(ROOT)), sha256=sha(p)))
            obj = source.with_suffix('.o')
            cc = [command[0], *flags, '-fno-lto', '-c', str(source), '-o', str(obj)]
            result = subprocess.run(cc, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            source.with_suffix('.log').write_text(result.stdout)
            result.check_returncode()
            elf = ElfTruth.read(obj, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',
                                include_section_data=True)
            sections = {s.name: dict(bytes=s.bytes,
                                    sha256=hashlib.sha256(elf.section_bytes(s.name)).hexdigest())
                        for s in elf.sections if s.section_type != 'SHT_NOBITS'
                        and s.name.startswith(('.text', '.rodata', '.lisp65'))}
            functions = [dict(name=s.name, bytes=s.bytes, section=s.section)
                         for s in elf.symbols if s.symbol_type == 'Function' and s.bytes]
            rows.append(dict(variant=variant, unit=source.name, sections=sections,
                             functions=functions, command=cc, inputs=inputs, object_sha256=sha(obj)))
    totals = {}
    for variant in ('baseline', 'put-kit'):
        totals[variant] = {}
        for row in rows:
            if row['variant'] != variant:
                continue
            for name, section in row['sections'].items():
                totals[variant][name] = totals[variant].get(name, 0) + section['bytes']
    delta = {name: totals['put-kit'].get(name, 0) - totals['baseline'].get(name, 0)
             for name in totals['put-kit'].keys() | totals['baseline'].keys()}
    receipt = dict(claim='OFF-PRODUCT NON-LTO PRICE ONLY; NOT SEED ADMISSION',
                   authority='e497ad71', tool_sha256=sha(Path(__file__)),
                   decoder=dict(path=str(decoder.relative_to(ROOT)), sha256=sha(decoder)),
                   budget=dict(seed=0, finale=0, link=0), totals=totals,
                   section_deltas=delta, rows=rows)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in delta.items() if v}, indent=2))


if __name__ == '__main__':
    main()
