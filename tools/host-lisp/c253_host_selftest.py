#!/usr/bin/env python3
"""Pure-host rehearsal of the NEW c253_product helpers.  Writes only objdump logs into a deleted temp dir.

Run with the installed layout's import path, e.g.
  PYTHONPATH=<prep>/tools:<repo>/tools/host-lisp PYTHONDONTWRITEBYTECODE=1 python3 -B host_selftest_c253.py
Covers synthetic controls plus read-only checks against the real frozen 2.5.2 (r7c) inputs.
"""
import copy, hashlib, json, struct, sys
from types import SimpleNamespace as N
import c253_config as CFG
import c253_product as P

def reject(log, name, fn):
    try:
        fn()
    except (AssertionError, KeyError, ValueError):
        log.append(name)
    else:
        raise SystemExit('NEGATIVE SURVIVED: ' + name)

log = []
R = CFG.ROOT
# 1. stdlib header projection against the REAL frozen native input and frozen r7c manifest
derived = json.loads((R / CFG.BASE_NATIVE / 'derived-inputs.json').read_text())
rows = [r for r in derived['all_generated'] if r['path'].endswith('stdlib-p0.h')]
assert len(rows) == 2
raw = (R / rows[0]['path']).read_bytes()
man = json.loads((R / json.loads((R / CFG.BASE_PLANE / 'product/substitution-artifacts.json').read_text())['manifests'][0]['path']).read_text())
same, changed = P.stdlib_header_projection(raw, man, man, raw.decode())
assert same == raw and changed == []
cand = raw.decode().replace('STDLIB_OBJECT_COUNT 404u', 'STDLIB_OBJECT_COUNT 405u').replace('STDLIB_DIRECTORY_BYTES 2828u', 'STDLIB_DIRECTORY_BYTES 2836u')
out, changed = P.stdlib_header_projection(raw, man, man, cand)
assert out.decode() == cand and [c[0] for c in changed] == ['OBJECT_COUNT', 'DIRECTORY_BYTES'], changed
new_man = copy.deepcopy(man)
reject(log, 'frozen header != r7c manifest', lambda: P.stdlib_header_projection(raw, dict(man, code_bytes=man['code_bytes'] + 1), man, raw.decode()))
reject(log, 'macro population drift', lambda: P.stdlib_header_projection(raw, man, man, cand + '#define LISP65_BYTECODE_STDLIB_EXTRA 1u\n'))
reject(log, 'unclassified header text change', lambda: P.stdlib_header_projection(raw, man, man, cand.replace('uint8_t', 'uint16_t', 1) if 'uint8_t' in cand else cand + 'x'))
# 2. eval.c pins vs the real files (read-only)
assert hashlib.sha256((R / 'src/eval.c').read_bytes()).hexdigest() == CFG.EVAL_AUTHORITY_SHA256
ev = [r for r in derived['all_generated'] if r['path'].endswith('generated-product-sources/eval.c')]
assert len(ev) == 1 and ev[0]['sha256'] == CFG.EVAL_BASE_SHA256
# 3. native attribution on stand-ins
def sec(n, a, s, t='SHT_PROGBITS', f=2): return N(name=n, address=a, bytes=s, section_type=t, flags=f)
def sym(i, n, v, b, s='.text'): return N(index=i, name=n, value=v, bytes=b, section=s, symbol_type='Function')
def rel(off, kind, tgt, add=0): return N(source_section='.text', offset=off, relocation_type=kind, target_symbol_index=tgt, target='sym%d' % tgt, addend=add)
def elf(text, syms, rels, sections=None):
    sections = sections or [sec('.text', 0x2000, len(text))]
    return N(sections=sections, symbols=syms, relocations=rels, section=lambda n: next(s for s in sections if s.name == n),
             section_bytes=lambda n: text if n == '.text' else b'')
# function g calls h via R_MOS_ADDR16 at offset 1; h moves because f grew
f_a = bytes([0xea] * 4); g_a = bytes([0x20, 0, 0, 0x60]); h_a = bytes([0x60])
f_b = bytes([0xea] * 6); g_b = bytes([0x20, 0, 0, 0x60]); h_b = h_a
ta, tb = f_a + g_a + h_a, f_b + g_b + h_b
def mk(text, f_len, g_val, h_val):
    syms = [sym(0, 'f', 0x2000, f_len), sym(1, 'g', 0x2000 + f_len, 4), sym(2, 'h', 0x2000 + f_len + 4, 1)]
    return elf(text, syms, [rel(0x2000 + f_len + 1, 'R_MOS_ADDR16', 2)])
a, b = mk(bytearray(ta), 4, 0, 0), mk(bytearray(tb), 6, 0, 0)
# operand bytes differ because the target moved: patch them
ta2 = bytearray(ta); ta2[5:7] = struct.pack('<H', 0x2000 + 8)
tb2 = bytearray(tb); tb2[7:9] = struct.pack('<H', 0x2000 + 10)
a, b = mk(bytes(ta2), 4, 0, 0), mk(bytes(tb2), 6, 0, 0)
res = P.text_attribution(a, b, expected_changed=('f',))
assert res['relocated'] == ['g'] and res['exact'] == ['h'] and [c['name'] for c in res['changed']] == ['f'], res
reject(log, 'unexpected .text change', lambda: P.text_attribution(a, b, expected_changed=('g',)))
tb3 = bytearray(tb2); tb3[6 + 3] = 0xea   # g's RTS changed: not a relocation operand
reject(log, 'non-relocation code drift', lambda: P.text_attribution(a, mk(bytes(tb3), 6, 0, 0), expected_changed=('f',)))
# 4. constants
const = dict(before_product=dict(product_build_id_u32=0x8d22c8e6, artifacts=dict(shelf=dict(bytes=99555))),
             after_product=dict(product_build_id_u32=0x11223344, artifacts=dict(shelf=dict(bytes=99600))),
             before_geometry=dict(code_bytes=50063), after_geometry=dict(code_bytes=50100),
             crc_tables=[dict(table='shelf', before=[0x1234], after=[0x4321])])
pats = P.constant_patterns(const)
assert len(pats) == 5   # id, shelf (u32), code (u32 + u16), one CRC word
old = b'\0' + struct.pack('<I', 0x8d22c8e6) + struct.pack('<H', 50063)
new = b'\0' + struct.pack('<I', 0x11223344) + struct.pack('<H', 50100)
assert P.explained(old, new, pats)
reject(log, 'unexplained byte', lambda: (_ for _ in ()).throw(AssertionError()) if P.explained(old, new[:-1] + b'\x99', pats) is False else None)
# 5. geometry policy
base = [sec('.text', 0x2023, 1000), sec('.rodata', 0xb61d, 10), sec('.lisp65_rt_x', 0xc000, 8)]
assert P.geometry_policy(base, [sec('.text', 0x2023, 1215)] + base[1:])['.text']['delta'] == 215
reject(log, 'text over cap', lambda: P.geometry_policy(base, [sec('.text', 0x2023, 1000 + CFG.NATIVE_TEXT_CAP + 1)] + base[1:]))
assert P.geometry_policy(base, [sec('.text', 0x2023, 1000 + CFG.NATIVE_TEXT_CAP)] + base[1:])['.text']['delta'] == CFG.NATIVE_TEXT_CAP
reject(log, 'rodata size change', lambda: P.geometry_policy(base, [base[0], sec('.rodata', 0xb61d, 12), base[2]]))
# 5b. alloc flags as ElfTruth reports them (tuple of names)
assert P.is_alloc(N(flags=('SHF_ALLOC', 'SHF_EXECINSTR'))) and not P.is_alloc(N(flags=())) and P.is_alloc(N(flags=2))
meta = [sec('.lisp65_error_callsites', 0, 10, f=())]
assert '.lisp65_error_callsites' in P.geometry_policy(base + meta, base + [sec('.lisp65_error_callsites', 0, 11, f=())])
reject(log, 'metadata delta wrong', lambda: P.geometry_policy(base + meta, base + [sec('.lisp65_error_callsites', 0, 13, f=())]))
# 5c. real-data immediate attribution: 2.5.2 r6 -> r7c ELF (constants-only change).  The draft
#     relocation-only attribution would call `main` changed; objdump-verified #imm operands explain it.
import tempfile
from pathlib import Path as _P
from elf_truth import ElfTruth
with tempfile.TemporaryDirectory(prefix='c253-host-selftest-') as tmp:
    P.HERE = _P(tmp)
    paths = [R / 'build/o2-lite-product-r6/wplto/resident-island-seed.prg.elf', R / CFG.BASE / 'wplto/resident-island-seed.prg.elf']
    ea, eb = [ElfTruth.read(x, llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for x in paths]
    c7 = json.loads((R / CFG.BASE_PREFLIGHT / 'constants.json').read_text())
    allowed, L = P.immediate_pairs(c7, []), P.Listings()
    res = P.text_attribution(ea, eb, expected_changed=(), allowed=allowed, listing=L, paths=paths)
    assert [x['name'] for x in res['immediate']] == ['main'] and not res['changed'], res['changed']
    assert all(r['explained'] for r in P.data_attribution(ea, eb, P.constant_patterns(c7, []), allowed=allowed, listing=L, paths=paths))
    reject(log, 'relocation-only attribution of a constants change', lambda: P.text_attribution(ea, eb, expected_changed=()))
    reject(log, 'immediate outside the known constant pairs', lambda: P.text_attribution(ea, eb, expected_changed=(), allowed=set(), listing=L, paths=paths))
    reject(log, 'overlay immediates without constant pairs', lambda: P.data_attribution(ea, eb, [], allowed=set(), listing=L, paths=paths))
# 5d. real-data SHIFT control: an earlier product link whose .text grew by 145 B (36,419 -> 36,564),
#     the closest frozen analogue of the +215 B F2 growth.  Section-relative relocation targets
#     (`.text` + addend) must be resolved to (symbol, offset): then exactly the one really changed
#     function differs; with raw addends 114 functions would look changed and the Seed would HALT
#     after its link.  Non-loaded bookkeeping sections (.rela.text) may change size.
def _elf(name):
    path = R / 'build' / name / 'wplto/resident-island-seed.prg.elf'
    return ElfTruth.read(path, llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
ga, gb = _elf('retained-callable-repair-product-r2'), _elf('nested-error-recovery-product-r1')
moved = P.geometry_policy(ga.sections, gb.sections, text_cap=256, metadata={})
assert moved['.text']['delta'] == 145 and moved['.rela.text'].get('loaded') is False and set(moved) == {'.text', '.rela.text'}, moved
shift = P.text_attribution(ga, gb, expected_changed=('c2_abort_empty_journal_derived',))
assert len(shift['relocated']) > 100 and not shift['immediate']
_saved = P.reloc_index
P.reloc_index = lambda t, s: {r.offset: (r.relocation_type, r.target, r.addend) for r in t.relocations if r.source_section == s}
try:
    raw = P.text_attribution(ga, gb, expected_changed=(), enforce=False)
    assert len(raw['changed']) > 50, 'raw section+addend comparison unexpectedly stable'
    log.append('raw section-relative relocation targets (%d false changes)' % len(raw['changed']))
finally:
    P.reloc_index = _saved
reject(log, 'growth over cap on the real shifted link', lambda: P.geometry_policy(ga.sections, gb.sections, text_cap=144, metadata={}))
reject(log, 'shifted link with the wrong expected function', lambda: P.text_attribution(ga, gb, expected_changed=('main',)))
for s in ga.sections:   # moved .text targets inside every other loaded section are explained by relocations
    if s.name != '.text' and P.is_alloc(s) and s.section_type != 'SHT_NOBITS':
        assert P.reloc_index(ga, s.name) == P.reloc_index(gb, s.name), s.name
# 5e. real-data control: the Seed r6 link (retained HALT build/card-253-product-r6, +338 B .text) against the
#     2.5.2 r7c ELF.  Pins the owner decision (cap 352), the measured changed set and the jump-table rule.
_r6 = R / 'build/card-253-product-r6/wplto/resident-island-seed.prg.elf'
assert hashlib.sha256(_r6.read_bytes()).hexdigest() == '47519653518fcffdb98eec5c069f23ed1db544221b4ed95eea33b27fea5ab57b'
ha = ElfTruth.read(R / CFG.BASE / 'wplto/resident-island-seed.prg.elf', llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
hb = ElfTruth.read(_r6, llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
# r8: cap 368 (owner decision 2026-10-02) and + repl; the r6/r7 link (same ELF) keeps its own measured pair.
assert CFG.NATIVE_TEXT_CAP == 368 and CFG.NATIVE_TEXT_EXPECTED_CHANGED == ('eval_v2_workbench_service', 'main', 'repl')
R7_CHANGED = ('eval_v2_workbench_service', 'main')
moved = P.geometry_policy(ha.sections, hb.sections)
assert moved['.text']['delta'] == 338 and moved['.lisp65_error_callsites']['delta'] == 1, moved
reject(log, 'r6 growth over the old 256 B cap', lambda: P.geometry_policy(ha.sections, hb.sections, text_cap=256))
reject(log, 'r6 growth over a 337 B cap', lambda: P.geometry_policy(ha.sections, hb.sections, text_cap=337))
with tempfile.TemporaryDirectory(prefix='c253-host-selftest-') as tmp:
    P.HERE = _P(tmp)
    r6paths = [R / CFG.BASE / 'wplto/resident-island-seed.prg.elf', _r6]
    hres = P.text_attribution(ha, hb, expected_changed=R7_CHANGED, allowed=set(), listing=None, paths=r6paths)
    assert [x['name'] for x in hres['changed']] == ['eval_v2_workbench_service', 'main'] and not hres['added'] and not hres['removed']
    assert 'repl' in hres['relocated'] + hres['exact'], 'repl already differs on the r6/r7 link'
    reject(log, 'r6 link with the old single expected function', lambda: P.text_attribution(ha, hb, expected_changed=('eval_v2_workbench_service',)))
    # The r8 set is an EXACT set, not an allowance: a link in which repl did not change halts.
    reject(log, 'r6/r7 link against the r8 expected set (repl unchanged)', lambda: P.text_attribution(ha, hb, allowed=set(), listing=None, paths=r6paths))
    # The service switch jump table (.rodata.eval_v2_workbench_service, 16 label addresses) moves inside the
    # changed function.  Without the changed-function rule the Seed HALTed after its link on this very section.
    # Real constants of the r6 preflight/link (build id, SHELF, static code, header counts, CRC words).
    c6 = json.loads((R / 'build/card-253-preflight-r6/constants.json').read_text())
    hp = P.header_value_pairs(json.loads((R / 'build/card-253-product-r6/native/derived-inputs.json').read_text()))
    pat6, allow6, L6 = P.constant_patterns(c6, hp), P.immediate_pairs(c6, hp), P.Listings()
    reject(log, 'r6 jump table without the changed-function rule', lambda: P.data_attribution(ha, hb, pat6, allowed=allow6, listing=L6, paths=r6paths))
    rows = P.data_attribution(ha, hb, pat6, allowed=allow6, listing=L6, paths=r6paths, changed=frozenset(('eval_v2_workbench_service', 'main')))
    assert any(r['section'] == '.lisp65_c2_kernal_window.profile_rodata' and r['explained'] for r in rows), rows
    reject(log, 'jump table rule for an unrelated changed function', lambda: P.data_attribution(ha, hb, pat6, allowed=allow6, listing=L6, paths=r6paths, changed=frozenset(('main',))))
# 5f. r8 native seam on the REAL files: the frozen command-18 Comfort-default repl.c copy and src/repl.c.
_proof = json.loads((R / CFG.BASE_NATIVE / 'command-proof.json').read_text())['commands']
_repl = [c[c.index('-c') + 1] for c in _proof[:73] if c[c.index('-c') + 1].endswith('/repl.c')]
assert len(_repl) == 1 and _proof[CFG.REPL_COMMAND_INDEX][_proof[CFG.REPL_COMMAND_INDEX].index('-c') + 1] == _repl[0]
_frozen, _auth = (R / _repl[0]).read_bytes(), (R / 'src/repl.c').read_bytes()
_out, _seam = P.repl_landing_projection(_frozen, _auth)
assert hashlib.sha256(_out).hexdigest() == CFG.REPL_PRODUCT_SHA256 and _out.count(b'mem_oom = 0;') == 2, _seam
assert sum(1 for r in derived['all_generated'] if r['path'] == _repl[0]) == 1
_others = [r for r in derived['all_generated'] if r['path'].endswith('/repl.c') and r['path'] != _repl[0]]
assert _others and not any(r['path'] in (c[c.index('-c') + 1] for c in _proof[:73]) for r in _others), 'uncompiled repl.c copies'
_old, _new = CFG.repl_landing_hunk()
reject(log, 'repl seam on a copy without the landing', lambda: P.repl_landing_projection(_frozen.replace(_old.encode(), b''), _auth))
reject(log, 'repl seam on the 2.5.2 src/repl.c (no hunk)', lambda: P.repl_landing_projection(_frozen, _auth.replace(_new.encode(), _old.encode())))
reject(log, 'repl seam applied twice', lambda: P.repl_landing_projection(_out, _auth))
# 6. config
assert CFG.selftest()['status'] == 'PASS'
# 7. Final/replay/seal qualification on REAL data (only once a Seed is pinned for the Final).
import c253_final_pins as PINS
final_controls = 'skipped: no pinned Seed for ' + CFG.SEED
if PINS.SEED_NAME == CFG.SEED and (R / CFG.SEED / 'complete.json').is_file():
    import gzip, os, subprocess
    from unittest.mock import patch
    # 7a. Pins live outside c253_config.py: the Seed receipts bind the config bytes, and the Final
    #     re-enters the producer, which re-checks them.  (Draft defect: [SET-AFTER-SEED] in the config.)
    assert PINS.problems() == [], PINS.problems()
    ident = P.tool_identity()
    assert {k: v['sha256'] for k, v in ident.items()} == PINS.SEED_TOOL_SHA
    for where in (CFG.SEED, CFG.PREFLIGHT, CFG.SELFTEST):
        assert json.loads((R / where / 'attempt.json').read_text())['tools'] == ident, where
    P.verify_preflight()                                   # what Final admission and media() call
    reject(log, 'Final pins in c253_config (placeholders must stay unset)', CFG.artifacts)
    with patch.object(CFG, 'SEED_RECEIPT_SHA', PINS.SEED_RECEIPT_SHA):
        assert any('placeholders' in x for x in PINS.problems())
    log.append('filled c253_config placeholder detected')
    with patch.dict(PINS.ARTIFACT_SHA, ELF='0' * 64):
        assert PINS.problems() == ['ARTIFACT_SHA drift: ELF', 'Seed receipt names another ELF', 'linked.json names another ELF/link count']
    log.append('wrong ELF pin detected')
    with patch.dict(PINS.SEED_TOOL_SHA, config='0' * 64):
        assert sum('c253_config.py' in x for x in PINS.problems()) == 4
    log.append('edited Seed tool detected')
    with patch.object(PINS, 'SEED_NAME', 'build/card-253-product-r6'):
        reject(log, 'pins for another Seed attempt', PINS.artifacts)
    # 7b. The tools themselves, on the real Seed r7 receipts (c253_final import = pins accepted).
    import c253_final as FN
    import c253_replay as RP
    import c253_seal as SL
    assert FN.ARTIFACTS == PINS.artifacts() and FN.SEED == CFG.SEED and FN.FINAL == CFG.FINAL and RP.MEDIA == 'media-253'
    assert FN.ARTIFACTS['D81'][0] == 'media-253/c253.d81' and (R / CFG.SEED / FN.ARTIFACTS['D81'][0]).is_file()
    assert set(FN.support_tools()) == {'tools/host-lisp/' + n for n in (
        'c253_final_pins.py', 'c253_product.py', 'c253_seed_producer.py', 'c253_config.py')}
    assert all((R / n).is_dir() for n in RP.CLOSURE_ROOTS) and all((R / n).is_file() for n in RP.REFERENCE_ROOTS + RP.EXTRA_INPUTS)
    for legacy, stable_copy in RP.PROVENANCE_COPIES.items():
        assert (R / stable_copy).is_file() and not stable_copy.startswith(('build/bytecode/', 'build/c2-lite/')), legacy
    assert hashlib.sha256((R / RP.PROVENANCE_COPIES['build/c2-lite/product-shaped-v6-probe/c2d-v6-entry-emitter-host.so']).read_bytes()
                          ).hexdigest() == 'b5f8d051c48c955ec5cfd9181f8ddf5fa199f452a8ae3fd7ce1407da6b354a2f'
    assert RP.symbol_tool() == RP.HW.NM and os.access(RP.symbol_tool(), os.X_OK)
    proof = json.loads((R / CFG.SEED / 'native/command-proof.json').read_text())
    d = FN.Driver('build/host-selftest-source-never-admitted', 'build/host-selftest-replay-never-read.json', '0' * 64)
    native = d.rebase(proof['commands'], {CFG.SEED + '/wplto': CFG.FINAL + '/wplto'})
    outs = [c[c.index('-o') + 1] for c in native]
    assert len(set(outs)) == 75 and all(o.startswith(CFG.FINAL + '/wplto/') for o in outs)
    assert [[x.replace(CFG.FINAL + '/wplto', CFG.SEED + '/wplto') for x in c] for c in native] == proof['commands']
    assert sum(CFG.FINAL in x for c in native for x in c) > 150 and not any(CFG.SEED + '/wplto' in x for c in native for x in c)
    assert native[74][:3] == ['/usr/bin/setarch', 'x86_64', '-R'] and outs[74] == CFG.FINAL + '/' + FN.ARTIFACTS['PRG'][0]
    assert '-Wl,--lto-obj-path=' + CFG.FINAL + '/' + FN.ARTIFACTS['LTO'][0] in native[74]
    reject(log, 'recipe with an unknown embedded Seed output reference', lambda: d.rebase(
        proof['commands'][:74] + [proof['commands'][74] + ['--x=' + CFG.SEED + '/wplto/y']], {CFG.SEED + '/wplto': CFG.FINAL + '/wplto'}))
    # r7c recipe duplicate: the CRC table source is `generated` AND a member of `all_generated`.
    dv = json.loads((R / CFG.SEED / 'native/derived-inputs.json').read_text())
    twins = [r for r in dv['all_generated'] if r['path'] == dv['generated']['path']]
    assert twins == [dv['generated']], 'CRC source row is no longer the single identical duplicate'
    assert dv['code_bytes_before'] == CFG.BASE_STATIC_CODE_BYTES == 50063 and dv['code_bytes_after'] == CFG.CANDIDATE_STATIC_CODE_BYTES == 50643
    assert dv['repl_c'] == dict(base_sha256=CFG.REPL_BASE_SHA256, authority_sha256=CFG.REPL_AUTHORITY_SHA256,
                                product_sha256=CFG.REPL_PRODUCT_SHA256, command=CFG.REPL_COMMAND_INDEX, census=1), dv['repl_c']
    assert dv['stdlib_header_changed'] is True and dv['eval_c']['authority_sha256'] == CFG.EVAL_AUTHORITY_SHA256
    seed_media = json.loads((R / CFG.SEED / 'media.json').read_text())
    medium = d.bind(CFG.SEED + '/' + FN.ARTIFACTS['D81'][0])
    RP.verify_readback(d, seed_media, medium)              # real 20-file persisted readback of c253.d81
    reject(log, 'readback against another medium binding', lambda: RP.verify_readback(d, seed_media, dict(medium, sha256='0' * 64)))
    reject(log, 'readback with a dropped file', lambda: RP.verify_readback(
        d, dict(seed_media, files={k: v for k, v in list(seed_media['files'].items())[1:]}), medium))
    inv = json.loads((R / CFG.SEED / 'native/inventory.json').read_text())
    # Measured on Seed r8 (build/card-253-product-r8/native/inventory.json; r7: 338).
    R8_TEXT_DELTA = 340
    assert R8_TEXT_DELTA is not None, 'set R8_TEXT_DELTA from SEED/native/inventory.json after the r8 Seed'
    assert inv['price']['text_delta'] == R8_TEXT_DELTA and inv['price']['cap'] == CFG.NATIVE_TEXT_CAP and \
        [c['name'] for c in inv['text']['changed']] == list(CFG.NATIVE_TEXT_EXPECTED_CHANGED), inv['price']
    # 7c. Final idle rule: emulator sessions of THIS checkout and sealed runs block the Final.
    def ps(*lines):
        return patch.object(subprocess, 'check_output', return_value='PID COMMAND\n' + '\n'.join(lines) + '\n')
    with ps('7 /usr/bin/zsh -c make -k check-source; python3 c253_rows.py', '8 python3 -B other.py',
            '9 /other/checkout/xemu/build/bin/xmega65.native -headless'):
        d.idle()
    for label, line in (('emulator row driver', '7 python3 -B tools/host-lisp/c253_emulator.py new x'),
                        ('Xemu of this checkout', '7 ' + str(R) + '/build/x/xemu/build/bin/xmega65.native -headless'),
                        ('sealed run', '7 python3 -B tools/host-lisp/sealed_check_run.py --out build/x -- make -k check-source'),
                        ('check-host', '7 make -k check-host'), ('Seed producer', '7 python3 -B tools/host-lisp/c253_seed_producer.py seed')):
        with ps(line):
            reject(log, 'Final while active: ' + label, d.idle)
    # 7d. Seal copy rule on real receipts: > 50 MB JSON exists in the closure and gzip is deterministic.
    assert SL.LIMIT == 50_000_000 and SL.DEFAULT == CFG.FINAL + '/seal.json' and SL.FORMAT == CFG.FORMAT_SEAL
    big = [n for n in RP.tree_files() if n.endswith('.json') and (R / n).stat().st_size > SL.LIMIT]
    assert len(big) >= 3, big
    small = (R / CFG.SEED / 'media.json').read_bytes()
    assert gzip.compress(small, compresslevel=9, mtime=0) == gzip.compress(small, compresslevel=9, mtime=0)
    assert gzip.decompress(gzip.compress(small, compresslevel=9, mtime=0)) == small
    # 7e. ELF-truth housekeeping gate over the working-tree tool population (2.5.2 Final r2 red:
    #     a new tool that names a column tool without the shared parser fails check-source).
    import comfort_default_elf_truth_20260927 as ET
    assert json.loads(ET.RECEIPT.read_text()) == ET.derive(), 'ELF-truth gate drift (new c253 tool names a column tool?)'
    assert ET.P.delegated_parsers("TOOLS = ('llvm-readobj', 'llvm-nm')\n", set()) is None
    log.append('column-tool tuple without an accountable parser is a hand parser')
    # 7f. GC stress pins follow the Final pins and fail closed before the seal.
    import c253_gc_stress as GC
    assert (GC.D81_SHA, GC.ELF_SHA) == (PINS.ARTIFACT_SHA['D81'], PINS.ARTIFACT_SHA['ELF'])
    if GC.SEAL_SHA is None:
        reject(log, 'GC stress world before the seal', lambda: GC.world('lite'))
    final_controls = 'real Seed %s receipts verified' % CFG.ATTEMPT
print(json.dumps(dict(status='PASS', negative_controls=log, eval_pins='real files verified', header_projection='real frozen r7c header verified',
                      final_controls=final_controls)))
