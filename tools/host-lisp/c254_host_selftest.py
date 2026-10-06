#!/usr/bin/env python3
"""Pure-host rehearsal of the c254_product helpers.  Writes only objdump logs into a deleted temp dir.

Successor of c253_host_selftest.py.  Run from the repository root:
  PYTHONDONTWRITEBYTECODE=1 python3 -B tools/host-lisp/c254_host_selftest.py
Covers synthetic controls plus read-only checks against the real frozen 2.5.3 (Seed/Final r8) inputs and
against REAL earlier link pairs, so that everything the Seed decides after its one link has already decided
the same question on real data:
  5c  2.5.2 r6 -> r7c   a constants-only release link: must pass the complete 2.5.4 native rule
  5d  2.5.3 r7 -> r8    constants + one changed function (repl +2 B): the 2.5.4 rule must REFUSE it, and
                        accept it once `repl` is named (proves the rule is exact, not an allowance)
  5e  immediate-shape prediction: silent for identity, and it retro-predicts the 2.5.3 `main` +2 B
"""
import copy, hashlib, json, struct, sys
from types import SimpleNamespace as N
import c254_config as CFG
import c254_product as P


def reject(log, name, fn):
    try:
        fn()
    except (AssertionError, KeyError, ValueError):
        log.append(name)
    else:
        raise SystemExit('NEGATIVE SURVIVED: ' + name)


log = []
R = CFG.ROOT
# 1. resident header projection against the REAL frozen r8 native input and the r8 resident manifest
derived = json.loads((R / CFG.BASE_NATIVE / 'derived-inputs.json').read_text())
rows = [r for r in derived['all_generated'] if r['path'].endswith('stdlib-p0.h')]
assert len(rows) == 2
raw = (R / rows[0]['path']).read_bytes()
man = json.loads((R / json.loads((R / CFG.BASE_PLANE / 'product/substitution-artifacts.json').read_text())['manifests'][0]['path']).read_text())
same, changed = P.stdlib_header_projection(raw, man, man, raw.decode())
assert same == raw and changed == []
cand = raw.decode().replace('STDLIB_BLOB_BYTES 19814u', 'STDLIB_BLOB_BYTES 19860u')
out, changed = P.stdlib_header_projection(raw, man, man, cand)
assert out.decode() == cand and [c[0] for c in changed] == ['BLOB_BYTES'], changed
reject(log, 'frozen header != r8 manifest', lambda: P.stdlib_header_projection(raw, dict(man, code_bytes=man['code_bytes'] + 1), man, raw.decode()))
reject(log, 'macro population drift', lambda: P.stdlib_header_projection(raw, man, man, cand + '#define LISP65_BYTECODE_STDLIB_EXTRA 1u\n'))
reject(log, 'unclassified header text change', lambda: P.stdlib_header_projection(raw, man, man, cand.replace('uint8_t', 'uint16_t', 1) if 'uint8_t' in cand else cand + 'x'))
# 2.5.4 rule: a resident object count / directory size / ENTRY index move means a resident function was added,
# removed or reordered -- not in scope, and the ENTRY indexes are immediates of `repl`.
for macro, a, b in (('OBJECT_COUNT', '405u', '406u'), ('DIRECTORY_BYTES', '2835u', '2842u'),
                    ('REPL_BANNER_ENTRY', '239u', '240u'), ('NATIVE_READ_LINE_ENTRY', '390u', '391u')):
    line = '#define LISP65_BYTECODE_STDLIB_%s %s' % (macro, a)
    assert raw.decode().count(line) == 1, macro
    reject(log, 'resident header macro moved: ' + macro,
           lambda: P.stdlib_header_projection(raw, man, man, raw.decode().replace(line, line[:-len(a)] + b)))
# 2. native premise on the real files: the recipe compiles only the r8 materialised inputs, no compiled source
#    names the resident COUNT macros, and src/ is the 2.5.3 src/.
proof = json.loads((R / CFG.BASE_NATIVE / 'command-proof.json').read_text())['commands']
compiled = [c[c.index('-c') + 1] for c in proof[:73]]
assert len(proof) == CFG.NATIVE_COMMANDS and all(p.startswith(CFG.BASE_NATIVE + '/') for p in compiled)
assert compiled[CFG.CRC_TABLE_COMMAND_INDEX].endswith('c2-stream-phase-02a.c')
counts = [b'LISP65_BYTECODE_STDLIB_' + m.encode() for m in ('OBJECT_COUNT', 'EMBED_COUNT', 'DIRECTORY_BYTES') + CFG.STDLIB_HEADER_MAY_CHANGE]
users = sorted({r['path'].rsplit('/', 1)[1] for r in derived['all_generated']
                if not r['path'].endswith('stdlib-p0.h') and any(m in (R / r['path']).read_bytes() for m in counts)})
assert users == [], ('a native input consumes a resident COUNT macro (review the immediate sites)', users)
assert CFG._git('diff', '--quiet', CFG.BASE_AUTHORITY, '--', *CFG.NATIVE_UNCHANGED_ROOTS, check=False).returncode == 0, 'src/ differs from 2.5.3'
# 3. native attribution on stand-ins
def sec(n, a, s, t='SHT_PROGBITS', f=2): return N(name=n, address=a, bytes=s, section_type=t, flags=f)
def sym(i, n, v, b, s='.text'): return N(index=i, name=n, value=v, bytes=b, section=s, symbol_type='Function')
def rel(off, kind, tgt, add=0): return N(source_section='.text', offset=off, relocation_type=kind, target_symbol_index=tgt, target='sym%d' % tgt, addend=add)
def elf(text, syms, rels, sections=None):
    sections = sections or [sec('.text', 0x2000, len(text))]
    return N(sections=sections, symbols=syms, relocations=rels, section=lambda n: next(s for s in sections if s.name == n),
             section_bytes=lambda n: text if n == '.text' else b'')
f_a = bytes([0xea] * 4); g_a = bytes([0x20, 0, 0, 0x60]); h_a = bytes([0x60])
f_b = bytes([0xea] * 6); g_b = bytes([0x20, 0, 0, 0x60]); h_b = h_a
ta, tb = f_a + g_a + h_a, f_b + g_b + h_b
def mk(text, f_len, g_val, h_val):
    syms = [sym(0, 'f', 0x2000, f_len), sym(1, 'g', 0x2000 + f_len, 4), sym(2, 'h', 0x2000 + f_len + 4, 1)]
    return elf(text, syms, [rel(0x2000 + f_len + 1, 'R_MOS_ADDR16', 2)])
ta2 = bytearray(ta); ta2[5:7] = struct.pack('<H', 0x2000 + 8)
tb2 = bytearray(tb); tb2[7:9] = struct.pack('<H', 0x2000 + 10)
a, b = mk(bytes(ta2), 4, 0, 0), mk(bytes(tb2), 6, 0, 0)
res = P.text_attribution(a, b, expected_changed=('f',))
assert res['relocated'] == ['g'] and res['exact'] == ['h'] and [c['name'] for c in res['changed']] == ['f'], res
reject(log, 'a changed function under the 2.5.4 default (none expected)', lambda: P.text_attribution(a, b))
tb3 = bytearray(tb2); tb3[6 + 3] = 0xea
reject(log, 'non-relocation code drift', lambda: P.text_attribution(a, mk(bytes(tb3), 6, 0, 0), expected_changed=('f',)))
# 4. constants
const = dict(before_product=dict(product_build_id_u32=0xaff6dfd2, artifacts=dict(shelf=dict(bytes=100729))),
             after_product=dict(product_build_id_u32=0x11223344, artifacts=dict(shelf=dict(bytes=100987))),
             before_geometry=dict(code_bytes=50643), after_geometry=dict(code_bytes=50901),
             crc_tables=[dict(table='shelf', before=[0x1234], after=[0x4321])])
pats = P.constant_patterns(const)
assert len(pats) == 5   # id (u32), shelf (u32), code (u32 + u16), one CRC word
old = b'\0' + struct.pack('<I', 0xaff6dfd2) + struct.pack('<H', 50643)
new = b'\0' + struct.pack('<I', 0x11223344) + struct.pack('<H', 50901)
assert P.explained(old, new, pats)
reject(log, 'unexplained byte', lambda: (_ for _ in ()).throw(AssertionError()) if P.explained(old, new[:-1] + b'\x99', pats) is False else None)
# 5. geometry policy, 2.5.4: nothing loaded may move, .text keeps its size, no new error call site
base = [sec('.text', 0x2023, 1000), sec('.rodata', 0xb61d, 10), sec('.lisp65_rt_x', 0xc000, 8)]
assert CFG.NATIVE_TEXT_CAP == 0 and CFG.NATIVE_TEXT_EXPECTED_CHANGED == () and CFG.BASE_TEXT_BYTES == 36899
assert P.geometry_policy(base, base) == {}
reject(log, 'text +1', lambda: P.geometry_policy(base, [sec('.text', 0x2023, 1001)] + base[1:]))
reject(log, 'text -2', lambda: P.geometry_policy(base, [sec('.text', 0x2023, 998)] + base[1:]))
reject(log, 'rodata size change', lambda: P.geometry_policy(base, [base[0], sec('.rodata', 0xb61d, 12), base[2]]))
assert P.is_alloc(N(flags=('SHF_ALLOC', 'SHF_EXECINSTR'))) and not P.is_alloc(N(flags=())) and P.is_alloc(N(flags=2))
meta = [sec('.lisp65_error_callsites', 0, 10, f=())]
assert P.geometry_policy(base + meta, base + meta)['.lisp65_error_callsites']['delta'] == 0
reject(log, 'new error call site', lambda: P.geometry_policy(base + meta, base + [sec('.lisp65_error_callsites', 0, 11, f=())]))
# 5c. REAL constants-only release link: 2.5.2 r6 -> r7c (m65d-only static change).  It must pass the complete
#     2.5.4 native rule: same geometry, no changed function, `.text` immediates only in the reviewed set,
#     every other allocated section explained.
import tempfile
from pathlib import Path as _P
from elf_truth import ElfTruth
def _elf(name):
    path = R / 'build' / name / 'wplto/resident-island-seed.prg.elf'
    return path, ElfTruth.read(path, llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
with tempfile.TemporaryDirectory(prefix='c254-host-selftest-') as tmp:
    P.HERE = _P(tmp)
    (pa, ea), (pb, eb) = _elf('o2-lite-product-r6'), _elf('o2-lite-product-r7c')
    c7 = json.loads((R / 'build/o2-lite-r7-preflight-d/constants.json').read_text())
    moved = P.geometry_policy(ea.sections, eb.sections)
    assert '.text' not in moved and not any(m.get('loaded', True) and m['delta'] for m in moved.values()), moved
    allowed, L = P.immediate_pairs(c7, []), P.Listings()
    res = P.text_attribution(ea, eb, allowed=allowed, listing=L, paths=[pa, pb])
    assert [x['name'] for x in res['immediate']] == ['main'] and not res['changed'] and not res['added'] and not res['removed']
    assert set(x['name'] for x in res['immediate']) <= set(CFG.NATIVE_TEXT_IMMEDIATE_ALLOWED)
    assert all(r['explained'] for r in P.data_attribution(ea, eb, P.constant_patterns(c7, []), allowed=allowed, listing=L, paths=[pa, pb]))
    reject(log, 'relocation-only attribution of a constants change', lambda: P.text_attribution(ea, eb))
    reject(log, 'immediate outside the known constant pairs', lambda: P.text_attribution(ea, eb, allowed=set(), listing=L, paths=[pa, pb]))
    reject(log, 'overlay immediates without constant pairs', lambda: P.data_attribution(ea, eb, [], allowed=set(), listing=L, paths=[pa, pb]))
# 5d. REAL pair 2.5.3 Seed r7 -> Seed r8: constants (build id, SHELF, static code, CRC) plus ONE changed
#     function (repl +2 B).  The 2.5.4 rule refuses it at every level; naming repl makes it pass.
with tempfile.TemporaryDirectory(prefix='c254-host-selftest-') as tmp:
    P.HERE = _P(tmp)
    (pa, ea), (pb, eb) = _elf('card-253-product-r7'), _elf('card-253-product-r8')
    assert hashlib.sha256(pb.read_bytes()).hexdigest() == CFG.BASE_ELF_SHA
    k7, k8 = [json.loads((R / 'build' / d / 'constants.json').read_text()) for d in ('card-253-preflight-r7', 'card-253-preflight-r8')]
    pair = dict(before_product=k7['after_product'], after_product=k8['after_product'], before_geometry=k7['after_geometry'],
                after_geometry=k8['after_geometry'],
                crc_tables=[dict(table=x['table'], before=x['after'], after=y['after']) for x, y in zip(k7['crc_tables'], k8['crc_tables'])])
    reject(log, 'r7 -> r8 geometry under the 2.5.4 rule (.text +2)', lambda: P.geometry_policy(ea.sections, eb.sections))
    assert P.geometry_policy(ea.sections, eb.sections, text_cap=2)['.text']['delta'] == 2
    allowed, L = P.immediate_pairs(pair, []), P.Listings()
    reject(log, 'r7 -> r8 text under the 2.5.4 rule (repl changed)', lambda: P.text_attribution(ea, eb, allowed=allowed, listing=L, paths=[pa, pb]))
    res = P.text_attribution(ea, eb, expected_changed=('repl',), allowed=allowed, listing=L, paths=[pa, pb])
    assert [x['name'] for x in res['immediate']] == ['main'] and [x['name'] for x in res['changed']] == ['repl']
    rows = P.data_attribution(ea, eb, P.constant_patterns(pair, []), allowed=allowed, listing=L, paths=[pa, pb], changed=frozenset(('repl',)))
    assert all(r['explained'] for r in rows) and len(rows) >= 10
    # 5e. immediate-shape prediction on the REAL baseline ELF and site table.
    table = P.load_sites()
    assert len(table['sites']) == 28 and {s['constant'] for s in table['sites']} == {'build_id', 'shelf_bytes', 'static_code_bytes'}
    ident = dict(before_product=k8['after_product'], after_product=k8['after_product'], before_geometry=k8['after_geometry'],
                 after_geometry=k8['after_geometry'])
    assert P.immediate_shape(ident, pb)['flags'] == []
    # Retro-prediction: going from the 2.5.3 SHELF size (0x018979) back to the 2.5.2 one (0x0184E3) must flag
    # `main` (0x84 coincides with the next immediate): that coincidence is what made 2.5.3 `main` 2 B larger.
    P.HERE = _P(tmp) / 'retro'
    back = copy.deepcopy(ident); back['after_product'] = dict(back['after_product'], artifacts=dict(shelf=dict(bytes=99555)))
    flags = [f['id'] for f in P.immediate_shape(back, pb)['flags']]
    assert any(f.startswith('main@') and 'none->eq' in f for f in flags), flags
    log.append('immediate-shape prediction flags the real 2.5.2/2.5.3 main size change')
    P.HERE = _P(tmp) / 'zero'
    zero = copy.deepcopy(ident); zero['after_product'] = dict(zero['after_product'], product_build_id_u32=0xaff600d2)
    assert sum(':zero' in f['id'] for f in P.immediate_shape(zero, pb)['flags']) >= 5
    log.append('immediate-shape prediction flags a zero build-id byte at every compare/load site')
# 6. config, and the product-world E3 verdict (D-E3; synthetic negatives of c254_e3_product.verdict)
assert CFG.selftest()['status'] == 'PASS'
import c254_e3_product as E3P
log.extend(E3P.selftest())
assert set(P.tool_identity()) == {'product', 'producer', 'config', 'e3'}
assert tuple(CFG.CANDIDATE_BLOBS['ide']) == tuple(CFG.E3_PROOF_IDE_BLOB)
# 7. Final/replay/seal qualification on REAL data (only once the Final-side tools are installed -- D-FIN: after
#    the Seed -- and a Seed is pinned for the Final).
PINS = None
final_controls = 'skipped: Final-side tools not installed (D-FIN: installed and pinned after the Seed)'
if (_P(__file__).resolve().parent / 'c254_final_pins.py').is_file():
    import c254_final_pins as PINS
    final_controls = 'skipped: no pinned Seed for ' + CFG.SEED
if PINS is not None and PINS.SEED_NAME == CFG.SEED and (R / CFG.SEED / 'complete.json').is_file():
    import gzip, os, subprocess
    from unittest.mock import patch
    assert PINS.problems() == [], PINS.problems()
    ident = P.tool_identity()
    assert {k: v['sha256'] for k, v in ident.items()} == PINS.SEED_TOOL_SHA
    for where in (CFG.SEED, CFG.PREFLIGHT, CFG.SELFTEST):
        assert json.loads((R / where / 'attempt.json').read_text())['tools'] == ident, where
    P.verify_preflight()
    reject(log, 'Final pins in c254_config (placeholders must stay unset)', CFG.artifacts)
    with patch.object(CFG, 'SEED_RECEIPT_SHA', PINS.SEED_RECEIPT_SHA):
        assert any('placeholders' in x for x in PINS.problems())
    log.append('filled c254_config placeholder detected')
    with patch.dict(PINS.ARTIFACT_SHA, ELF='0' * 64):
        assert PINS.problems() == ['ARTIFACT_SHA drift: ELF', 'Seed receipt names another ELF', 'linked.json names another ELF/link count']
    log.append('wrong ELF pin detected')
    with patch.dict(PINS.SEED_TOOL_SHA, config='0' * 64):
        assert sum('c254_config.py' in x for x in PINS.problems()) == 4
    log.append('edited Seed tool detected')
    with patch.object(PINS, 'SEED_NAME', 'build/card-254-product-r0'):
        reject(log, 'pins for another Seed attempt', PINS.artifacts)
    import c254_final as FN
    import c254_replay as RP
    import c254_seal as SL
    assert FN.ARTIFACTS == PINS.artifacts() and FN.SEED == CFG.SEED and FN.FINAL == CFG.FINAL and RP.MEDIA == CFG.MEDIA_DIR
    assert FN.ARTIFACTS['D81'][0] == CFG.MEDIA_DIR + '/' + CFG.MEDIA_NAME and (R / CFG.SEED / FN.ARTIFACTS['D81'][0]).is_file()
    assert set(FN.support_tools()) >= {'tools/host-lisp/' + n for n in (
        'c254_final_pins.py', 'c254_product.py', 'c254_seed_producer.py', 'c254_config.py')}
    assert 'tools/host-lisp/' + CFG.SITES_TOOL in set(FN.support_tools()) | set(RP.EXTRA_INPUTS), 'site table not bound by the Final'
    assert all((R / n).is_dir() for n in RP.CLOSURE_ROOTS) and all((R / n).is_file() for n in RP.REFERENCE_ROOTS + RP.EXTRA_INPUTS)
    proof = json.loads((R / CFG.SEED / 'native/command-proof.json').read_text())
    d = FN.Driver('build/host-selftest-source-never-admitted', 'build/host-selftest-replay-never-read.json', '0' * 64)
    native = d.rebase(proof['commands'], {CFG.SEED + '/wplto': CFG.FINAL + '/wplto'})
    outs = [c[c.index('-o') + 1] for c in native]
    assert len(set(outs)) == 75 and all(o.startswith(CFG.FINAL + '/wplto/') for o in outs)
    assert [[x.replace(CFG.FINAL + '/wplto', CFG.SEED + '/wplto') for x in c] for c in native] == proof['commands']
    assert native[74][:3] == ['/usr/bin/setarch', 'x86_64', '-R'] and outs[74] == CFG.FINAL + '/' + FN.ARTIFACTS['PRG'][0]
    dv = json.loads((R / CFG.SEED / 'native/derived-inputs.json').read_text())
    assert dv['code_bytes_before'] == CFG.BASE_STATIC_CODE_BYTES == 50643 and dv['code_bytes_after'] == CFG.CANDIDATE_STATIC_CODE_BYTES
    assert dv['native_sources'] == 'identical to 2.5.3 Seed r8' and set(dv['census']) == {'stdlib_header', 'static_plane', 'asserts'}
    assert 'eval_c' not in dv and 'repl_c' not in dv
    # every compiled source of the new recipe is byte-identical to its r8 twin unless it is a declared seam
    seams = {c['after']['path'] for c in dv['header_changes']}
    old_proof = json.loads((R / CFG.BASE_NATIVE / 'command-proof.json').read_text())['commands']
    for new_c, old_c in zip(proof['commands'][:73], old_proof[:73], strict=True):
        n, o = new_c[new_c.index('-c') + 1], old_c[old_c.index('-c') + 1]
        assert n in seams or (R / n).read_bytes() == (R / o).read_bytes(), ('compiled source differs from 2.5.3', n)
    seed_media = json.loads((R / CFG.SEED / 'media.json').read_text())
    assert seed_media['index_exact'] is False and seed_media['index_changed_rows'] == [n for n in CFG.PACKAGE_NAMES if n in CFG.PACKAGES_REEMIT]
    medium = d.bind(CFG.SEED + '/' + FN.ARTIFACTS['D81'][0])
    RP.verify_readback(d, seed_media, medium)
    reject(log, 'readback against another medium binding', lambda: RP.verify_readback(d, seed_media, dict(medium, sha256='0' * 64)))
    inv = json.loads((R / CFG.SEED / 'native/inventory.json').read_text())
    assert inv['price'] == dict(text_delta=0, cap=0, text_bytes=CFG.BASE_TEXT_BYTES) and inv['text']['changed'] == [], inv['price']
    assert set(x['name'] for x in inv['text']['immediate']) <= set(CFG.NATIVE_TEXT_IMMEDIATE_ALLOWED)
    def ps(*lines):
        return patch.object(subprocess, 'check_output', return_value='PID COMMAND\n' + '\n'.join(lines) + '\n')
    for label, line in (('emulator row driver', '7 python3 -B tools/host-lisp/c254_emulator.py new x'),
                        ('sealed run', '7 python3 -B tools/host-lisp/sealed_check_run.py --out build/x -- make -k check-source'),
                        ('check-host', '7 make -k check-host'), ('Seed producer', '7 python3 -B tools/host-lisp/c254_seed_producer.py seed')):
        with ps(line):
            reject(log, 'Final while active: ' + label, d.idle)
    assert SL.DEFAULT == CFG.FINAL + '/seal.json' and SL.FORMAT == CFG.FORMAT_SEAL
    import comfort_default_elf_truth_20260927 as ET
    assert json.loads(ET.RECEIPT.read_text()) == ET.derive(), 'ELF-truth gate drift (new c254 tool names a column tool?)'
    import c254_gc_stress as GC
    assert (GC.D81_SHA, GC.ELF_SHA) == (PINS.ARTIFACT_SHA['D81'], PINS.ARTIFACT_SHA['ELF'])
    if GC.SEAL_SHA is None:
        reject(log, 'GC stress world before the seal', lambda: GC.world('lite'))
    final_controls = 'real Seed %s receipts verified' % CFG.ATTEMPT
print(json.dumps(dict(status='PASS', negative_controls=log, native_premise='real r8 recipe and src/ verified',
                      header_projection='real frozen r8 header verified', real_pairs=['2.5.2 r6->r7c', '2.5.3 r7->r8'],
                      final_controls=final_controls)))
