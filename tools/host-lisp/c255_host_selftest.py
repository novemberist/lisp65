#!/usr/bin/env python3
"""Pure-host rehearsal of the c255_product helpers.  Writes only objdump logs into a scratch directory below
build/ (tempfile.mkdtemp(dir=...), removed at the end); never TMPDIR.

Successor of c254_host_selftest.py.  Run from the repository root:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/host-lisp python3 -B tools/host-lisp/c255_host_selftest.py
Covers synthetic controls plus read-only checks against the real frozen 2.5.4 inputs (Seed receipts r1b, link
attempt r1, Final r1) and against REAL earlier link pairs, so that everything the Seed decides after its one link
has already decided the same question on real data:
  5c  2.5.2 r6 -> r7c   a constants-only release link: must pass the complete 2.5.5 native rule
  5d  2.5.3 r7 -> r8    constants + one changed function (repl +2 B): the rule must REFUSE it, and accept it once
                        `repl` is named (proves the rule is exact, not an allowance)
  5f  2.5.3 r8 -> 2.5.4 constants + ONE swapped instruction pair (the reviewed commuting pair of the 2.5.4
                        continuation): the 2.5.5 rule, which does NOT carry that class, must refuse exactly the
                        section .lisp65_rt_c2d_00b and nothing else.  This is what a pair that flips back in the
                        2.5.5 link would look like: a halt in the inventory, for review.
  5e  immediate-shape prediction on the 2.5.4 ELF and the carried site table: silent for identity, flags a
      created coincidence and a zero build-id byte
  2b  the native seam derivation in memory on the real frozen 2.5.4 inputs (a shrinking static plane)
  6   the real projection 2.5.4 -> working tree with the two L2 seams, on the real 2.5.4 product IDE sources
  host  the pinned Fedora 45 tools, the Fedora 44 pins refused, the committed reproduction evidence
The Final-side qualification (section 7 of the 2.5.4 selftest) belongs to the Final-side successor (D-FIN).
"""
import copy, hashlib, json, shutil, struct, sys, tempfile
from pathlib import Path as _P
from types import SimpleNamespace as N
import c255_config as CFG
import c255_product as P


def reject(log, name, fn):
    try:
        fn()
    except (AssertionError, KeyError, ValueError):
        log.append(name)
    else:
        raise SystemExit('NEGATIVE SURVIVED: ' + name)


log = []
R = CFG.ROOT
# 0. host and baseline: the live tools are the pinned Fedora 45 binaries; the baseline's own pins are refused here;
#    the committed 2.5.4 reproductions say that the pinned tools give the baseline artifacts byte for byte.
host = P.host_identity()
assert [t['path'] for t in host['tools']] == sorted(CFG.HOST_TOOLS) and host['host'] == 'Fedora 45'
reject(log, 'Fedora 44 host tool pins on this host', lambda: CFG.host_tools(CFG.BASE_HOST_TOOLS))
assert CFG.host_equivalence() == [], CFG.host_equivalence()
assert CFG.baseline_link_problems() == [], CFG.baseline_link_problems()
import c2_v254_r1_toolchain as TC
assert TC.HOST_TOOLS == CFG.HOST_TOOLS and TC.FINAL_HOST_TOOLS == CFG.BASE_HOST_TOOLS, 'host pins differ from the committed 2.5.4 toolchain record'
import c254_final_pins as OLDPINS
assert (OLDPINS.SEED_NAME, OLDPINS.SEED_LINK_NAME) == (CFG.BASE, CFG.BASE_LINK)
assert OLDPINS.ARTIFACT_SHA == dict(D81=CFG.BASE_MEDIUM_SHA, ELF=CFG.BASE_ELF_SHA, PRG=CFG.BASE_PRG_SHA, LTO=CFG.BASE_LTO_SHA)
assert (OLDPINS.SEED_RECEIPT_SHA, OLDPINS.RECIPE_SHA) == (CFG.BASE_SEED_RECEIPT_SHA, CFG.BASE_RECIPE_SHA)
assert {name: getattr(OLDPINS, pin) for name, pin in OLDPINS.R1_RECORDS} == dict(CFG.BASE_LINK_RECORDS)
probe = R / 'build/hosttool-probe-4yeo_6mo/newbc.elf.elf'       # optional local evidence (not committed)
host_probe = 'absent'
if probe.is_file():
    assert hashlib.sha256(probe.read_bytes()).hexdigest() == CFG.BASE_ELF_SHA, 'host-tool probe ELF differs from the baseline'
    host_probe = 'Fedora 45 llvm-link + 2.5.4 inputs -> the 2.5.4 ELF (byte-identical)'
# 1. resident header projection against the REAL frozen 2.5.4 native input and the 2.5.4 resident manifest.
#    2.5.5: the resident image is EXACT, so NO macro may move.
derived = json.loads((R / CFG.BASE_NATIVE / 'derived-inputs.json').read_text())
rows = [r for r in derived['all_generated'] if r['path'].endswith('stdlib-p0.h')]
assert len(rows) == 2 and all(r['path'].startswith(CFG.BASE_LINK + '/') for r in derived['all_generated'])
raw = (R / rows[0]['path']).read_bytes()
man = json.loads((R / json.loads((R / CFG.BASE_PLANE / 'product/substitution-artifacts.json').read_text())['manifests'][0]['path']).read_text())
same, changed = P.stdlib_header_projection(raw, man, man, raw.decode())
assert same == raw and changed == []
reject(log, 'frozen header != baseline manifest', lambda: P.stdlib_header_projection(raw, dict(man, code_bytes=man['code_bytes'] + 1), man, raw.decode()))
reject(log, 'macro population drift', lambda: P.stdlib_header_projection(raw, man, man, raw.decode() + '#define LISP65_BYTECODE_STDLIB_EXTRA 1u\n'))
for macro, a, b in (('BLOB_BYTES', '19860u', '19861u'), ('LITERAL_INDEX_COUNT', '967u', '968u'),
                    ('OBJECT_COUNT', '405u', '406u'), ('DIRECTORY_BYTES', '2835u', '2842u'),
                    ('REPL_BANNER_ENTRY', '239u', '240u'), ('NATIVE_READ_LINE_ENTRY', '390u', '391u')):
    line = '#define LISP65_BYTECODE_STDLIB_%s %s' % (macro, a)
    assert raw.decode().count(line) == 1, macro
    reject(log, 'resident header macro moved: ' + macro,
           lambda: P.stdlib_header_projection(raw, man, man, raw.decode().replace(line, line[:-len(a)] + b)))
# 2. native premise on the real files: the recipe compiles only the 2.5.4 materialised inputs (link attempt
#    directory), uses the pinned host tools, no compiled source names the resident COUNT macros, and src/ is the
#    2.5.4 src/.
proof = json.loads((R / CFG.BASE_NATIVE / 'command-proof.json').read_text())['commands']
compiled = [c[c.index('-c') + 1] for c in proof[:73]]
assert len(proof) == CFG.NATIVE_COMMANDS and all(p.startswith(CFG.BASE_NATIVE + '/') for p in compiled)
assert compiled[CFG.CRC_TABLE_COMMAND_INDEX].endswith('c2-stream-phase-02a.c')
assert proof[73][0] == '/usr/bin/llvm-link' and proof[74][:3] == ['/usr/bin/setarch', 'x86_64', '-R']
assert not any((CFG.BASE + '/') in arg for c in proof for arg in c), 'a frozen command names the continuation directory'
ready = json.loads((R / CFG.BASE_NATIVE / 'command-ready.json').read_text())
frozen_host = {r['source']['path']: r['source']['sha256'] for r in ready['native'] if r['source']['path'].startswith('/usr/bin/')}
assert frozen_host and all(CFG.BASE_HOST_TOOLS[p] == h != CFG.HOST_TOOLS[p] for p, h in frozen_host.items()), \
    'the frozen recipe is expected to record the Fedora 44 host tools'
commands, native_rows, native_tools = P.native_inputs()          # reads the frozen recipe, binds the LIVE host tools
assert not any(r['path'].startswith('/usr/bin/') and r['sha256'] in CFG.BASE_HOST_TOOLS.values() for r in native_tools)
counts = [b'LISP65_BYTECODE_STDLIB_' + m.encode() for m in ('OBJECT_COUNT', 'EMBED_COUNT', 'DIRECTORY_BYTES', 'BLOB_BYTES',
          'LITERAL_INDEX_COUNT', 'LITERAL_NODE_COUNT', 'LITERAL_PATCH_COUNT')]
users = sorted({r['path'].rsplit('/', 1)[1] for r in derived['all_generated']
                if not r['path'].endswith('stdlib-p0.h') and any(m in (R / r['path']).read_bytes() for m in counts)})
assert users == [], ('a native input consumes a resident COUNT macro (review the immediate sites)', users)
assert CFG._git('diff', '--quiet', CFG.BASE_AUTHORITY, '--', *CFG.NATIVE_UNCHANGED_ROOTS, check=False).returncode == 0, 'src/ differs from 2.5.4'
# 2b. the native seam derivation, in memory, on the REAL frozen 2.5.4 inputs: the real 2.5.4 constants as the old
#     side, synthetic SMALLER constants as the new side (the static plane shrinks in 2.5.5).  Seam census as in
#     2.5.4, every path rebased out of the link-attempt directory, nothing left that names a 2.5.4 directory.
k4 = json.loads((R / CFG.BASE_PREFLIGHT / 'constants.json').read_text())
new_product = copy.deepcopy(k4['after_product'])
new_product.update(product_build_id_u32=0x5a3c7e91, product_build_id_hex='0x5a3c7e91')
new_product['artifacts']['shelf']['bytes'] = CFG.BASE_SHELF_BYTES - 242
probe_const = dict(before_product=k4['after_product'], after_product=new_product, before_geometry=k4['after_geometry'],
                   after_geometry=dict(k4['after_geometry'], code_bytes=CFG.CANDIDATE_STATIC_CODE_BYTES),
                   LISP65_C2_PRODUCT_BUILD_ID='0x5a3c7e91', LISP65_C2_PRODUCT_SHELF_BYTES=CFG.BASE_SHELF_BYTES - 242,
                   LISP65_C2_LITE_STATIC_CODE_BYTES=CFG.CANDIDATE_STATIC_CODE_BYTES,
                   crc_tables=[dict(table=t['table'], before=t['after'], after=[(x * 7 + 3) & 0xffff for x in t['after']]) for t in k4['crc_tables']])
assert (k4['after_product']['product_build_id_hex'], k4['after_product']['artifacts']['shelf']['bytes'], k4['after_geometry']['code_bytes']) == \
    (CFG.BASE_PRODUCT_BUILD_ID, CFG.BASE_SHELF_BYTES, CFG.BASE_STATIC_CODE_BYTES)
frozen_header = P.S.native_stdlib_header((R / CFG.BASE_PREFLIGHT / 'emission/stdlib-p0/stdlib-p0.h').read_text())
d = P.derive_native(probe_const, man, frozen_header, P.BUILD / 'native', frozen_header)
census = P.seam_census(d, P.BUILD / 'native')
assert census['seen'] == dict(stdlib_header=2, static_plane=1, asserts=3) and census['commands'] == 75, census['seen']
assert census['materialised'] == census['distinct_targets'] == 235
assert not any('card-254' in arg for c in d['commands'] for arg in c), 'a derived command still names a 2.5.4 directory'
assert all(c[c.index('-o') + 1].startswith(CFG.SEED + '/') for c in d['commands'])
assert sorted(s['kind'] for c in census['changed'] for s in c['seams']) == \
    ['CRC16 table', 'CRC16 table', 'compiler assertion', 'compiler assertion', 'compiler assertion', 'resident stdlib counts',
     'resident stdlib counts', 'static code size']
assert all(s.get('counts', []) == [] for c in census['changed'] for s in c['seams'] if s['kind'] == 'resident stdlib counts')
reject(log, 'seam derivation with a wrong old build id', lambda: P.derive_native(
    dict(probe_const, before_product=dict(k4['after_product'], product_build_id_hex='0xaff6dfd2')), man, frozen_header, P.BUILD / 'native', frozen_header))
reject(log, 'seam derivation with a moved resident header', lambda: P.derive_native(
    probe_const, man, frozen_header.replace('STDLIB_BLOB_BYTES 19860u', 'STDLIB_BLOB_BYTES 19861u'), P.BUILD / 'native', frozen_header))
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
reject(log, 'a changed function under the 2.5.5 default (none expected)', lambda: P.text_attribution(a, b))
tb3 = bytearray(tb2); tb3[6 + 3] = 0xea
reject(log, 'non-relocation code drift', lambda: P.text_attribution(a, mk(bytes(tb3), 6, 0, 0), expected_changed=('f',)))
# 4. constants (synthetic; a SHRINKING static plane as in 2.5.5)
const = dict(before_product=dict(product_build_id_u32=0x829db958, artifacts=dict(shelf=dict(bytes=101155))),
             after_product=dict(product_build_id_u32=0x11223344, artifacts=dict(shelf=dict(bytes=100913))),
             before_geometry=dict(code_bytes=50901), after_geometry=dict(code_bytes=50759),
             crc_tables=[dict(table='shelf', before=[0x1234], after=[0x4321])])
pats = P.constant_patterns(const)
assert len(pats) == 5   # id (u32), shelf (u32), code (u32 + u16), one CRC word
old = b'\0' + struct.pack('<I', 0x829db958) + struct.pack('<H', 50901)
new = b'\0' + struct.pack('<I', 0x11223344) + struct.pack('<H', 50759)
assert P.explained(old, new, pats)
reject(log, 'unexplained byte', lambda: (_ for _ in ()).throw(AssertionError()) if P.explained(old, new[:-1] + b'\x99', pats) is False else None)
assert (0x23, 0x31) in P.immediate_pairs(const) and (0xd5, 0x47) in P.immediate_pairs(const)   # SHELF lo, static code lo
# 5. geometry policy: nothing loaded may move, .text keeps its size, no new error call site
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
# 5b. the delivery code plane may shrink (2.5.5); the freed bytes return to zero fill
plane = (R / CFG.BASE_PLANE / 'CODE.BIN').read_bytes()
delivered = plane + bytes(0xee00 - len(plane)) + b'native-suffix'
shrunk = P.project_delivery_code(delivered, plane, plane[:-142])
assert shrunk[:len(plane) - 142] == plane[:-142] and not any(shrunk[len(plane) - 142:0xee00]) and shrunk[0xee00:] == b'native-suffix'
reject(log, 'empty static plane', lambda: P.project_delivery_code(delivered, plane, b''))
reject(log, 'delivery code with another baseline plane', lambda: P.project_delivery_code(b'\xff' + delivered[1:], plane, plane[:-142]))
from elf_truth import ElfTruth
def _elf(name):
    path = R / 'build' / name / 'wplto/resident-island-seed.prg.elf'
    return path, ElfTruth.read(path, llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
scratch = _P(tempfile.mkdtemp(dir=CFG.scratch_root(), prefix='c255-host-selftest-'))
try:
    # 5c. REAL constants-only release link: 2.5.2 r6 -> r7c (m65d-only static change).  It must pass the complete
    #     2.5.5 native rule: same geometry, no changed function, `.text` immediates only in the reviewed set,
    #     every other allocated section explained.
    P.HERE = scratch / 'c'
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
    #     function (repl +2 B).  The rule refuses it at every level; naming repl makes it pass.
    P.HERE = scratch / 'd'
    (pa, ea), (pb, eb) = _elf('card-253-product-r7'), _elf('card-253-product-r8')
    k7, k8 = [json.loads((R / 'build' / d / 'constants.json').read_text()) for d in ('card-253-preflight-r7', 'card-253-preflight-r8')]
    pair = dict(before_product=k7['after_product'], after_product=k8['after_product'], before_geometry=k7['after_geometry'],
                after_geometry=k8['after_geometry'],
                crc_tables=[dict(table=x['table'], before=x['after'], after=y['after']) for x, y in zip(k7['crc_tables'], k8['crc_tables'])])
    reject(log, 'r7 -> r8 geometry under the 2.5.5 rule (.text +2)', lambda: P.geometry_policy(ea.sections, eb.sections))
    assert P.geometry_policy(ea.sections, eb.sections, text_cap=2)['.text']['delta'] == 2
    allowed, L = P.immediate_pairs(pair, []), P.Listings()
    reject(log, 'r7 -> r8 text under the 2.5.5 rule (repl changed)', lambda: P.text_attribution(ea, eb, allowed=allowed, listing=L, paths=[pa, pb]))
    res = P.text_attribution(ea, eb, expected_changed=('repl',), allowed=allowed, listing=L, paths=[pa, pb])
    assert [x['name'] for x in res['immediate']] == ['main'] and [x['name'] for x in res['changed']] == ['repl']
    rows = P.data_attribution(ea, eb, P.constant_patterns(pair, []), allowed=allowed, listing=L, paths=[pa, pb], changed=frozenset(('repl',)))
    assert all(r['explained'] for r in rows) and len(rows) >= 10
    # 5f. REAL pair 2.5.3 r8 -> 2.5.4 (the baseline of 2.5.5): constants plus the ONE swapped pair that the
    #     2.5.4 continuation reviewed.  Geometry and `.text` pass the rule; the data attribution WITHOUT the
    #     class must refuse exactly .lisp65_rt_c2d_00b.  (2.5.5 does not carry the class.)
    P.HERE = scratch / 'f'
    pb4 = R / CFG.BASE / 'wplto/resident-island-seed.prg.elf'
    assert hashlib.sha256(pb4.read_bytes()).hexdigest() == CFG.BASE_ELF_SHA == hashlib.sha256(
        (R / CFG.BASE_FINAL / 'wplto/resident-island-seed.prg.elf').read_bytes()).hexdigest()
    eb4 = ElfTruth.read(pb4, llvm_readobj=R / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    hp = P.header_value_pairs(derived)
    moved = P.geometry_policy(eb.sections, eb4.sections)
    assert '.text' not in moved and eb4.section('.text').bytes == CFG.BASE_TEXT_BYTES
    allowed, L = P.immediate_pairs(k4, hp), P.Listings()
    res = P.text_attribution(eb, eb4, allowed=allowed, listing=L, paths=[pb, pb4])
    assert [x['name'] for x in res['immediate']] == ['main'] and not res['changed']
    try:
        P.data_attribution(eb, eb4, P.constant_patterns(k4, hp), allowed=allowed, listing=L, paths=[pb, pb4])
    except AssertionError as error:
        assert error.args[0][1] == ['.lisp65_rt_c2d_00b'], error.args
        log.append('2.5.3 -> 2.5.4 swapped instruction pair is refused (no carried class): .lisp65_rt_c2d_00b only')
    else:
        raise SystemExit('NEGATIVE SURVIVED: the reviewed commuting pair of 2.5.4 passes the 2.5.5 rule')
    # 5e. immediate-shape prediction on the REAL baseline ELF (2.5.4) and the carried site table.
    P.HERE = scratch / 'e'
    table = P.load_sites()
    assert len(table['sites']) == 28 and {s['constant'] for s in table['sites']} == {'build_id', 'shelf_bytes', 'static_code_bytes'}
    assert table['elf_sha256'] == CFG.BASE_ELF_SHA and len({(s['section'], s['function']) for s in table['sites']}) == 9
    assert table['constants'] == dict(build_id=CFG.BASE_PRODUCT_BUILD_ID, shelf_bytes=f'{CFG.BASE_SHELF_BYTES:#x}',
                                      static_code_bytes=f'{CFG.BASE_STATIC_CODE_BYTES:#x}')
    ident = dict(before_product=k4['after_product'], after_product=k4['after_product'], before_geometry=k4['after_geometry'],
                 after_geometry=k4['after_geometry'])
    shape = P.immediate_shape(ident, pb4)
    assert shape['flags'] == [] and shape['sites'] == 28 and len(shape['functions']) == 9
    # A SHELF size whose middle byte becomes 0x84 creates the coincidence with `stx $c084`'s neighbour immediate
    # that made 2.5.3 `main` 2 B larger than 2.5.2 (retro-prediction, now from the 2.5.4 side).
    P.HERE = scratch / 'retro'
    back = copy.deepcopy(ident); back['after_product'] = dict(back['after_product'], artifacts=dict(shelf=dict(bytes=99555)))
    flags = [f['id'] for f in P.immediate_shape(back, pb4)['flags']]
    assert any(f.startswith('main@') and 'none->eq' in f for f in flags), flags
    log.append('immediate-shape prediction flags the real 2.5.2/2.5.3 main coincidence (SHELF 0x0184E3) on the 2.5.4 ELF')
    P.HERE = scratch / 'zero'
    zero = copy.deepcopy(ident); zero['after_product'] = dict(zero['after_product'], product_build_id_u32=0x829d0058)
    assert sum(':zero' in f['id'] for f in P.immediate_shape(zero, pb4)['flags']) >= 5
    log.append('immediate-shape prediction flags a zero build-id byte at every compare/load site')
    P.HERE = scratch / 'high'
    high = copy.deepcopy(ident); high['after_product'] = dict(high['after_product'], artifacts=dict(shelf=dict(bytes=65535)))
    assert any(f['id'] == 'shelf_bytes:high-byte' for f in P.immediate_shape(high, pb4)['flags'])
    log.append('immediate-shape prediction flags a SHELF size that loses its high byte')
finally:
    shutil.rmtree(scratch, ignore_errors=True)
# 6. config; the real projection of the 2.5.5 lib change onto the real 2.5.4 product IDE sources; E3 verdict.
assert CFG.selftest()['status'] == 'PASS'
suite = json.loads((R / CFG.BASE_PREFLIGHT / 'emission/ide/suite.json').read_text())
by_name = {_P(s).name: _P(s) for s in suite['sources']}
assert set(CFG.PROJECTIONS) == {'ide'} and set(CFG.PROJECTIONS['ide']) <= set(by_name)
modes = {}
for name, lib in CFG.PROJECTIONS['ide'].items():
    assert by_name[name].resolve().is_relative_to(R / CFG.BASE_PREFLIGHT / 'projection/ide/sources'), ('2.5.4 projected copy', name)
    old = CFG._git('show', CFG.BASE_AUTHORITY + ':' + lib).stdout
    new = (R / lib).read_text()
    assert old != new, ('projected lib file did not change', lib)
    seams = CFG.product_seams('ide', lib)
    text, info = P.project_text(by_name[name].read_text(), old, new, 'ide:' + lib, seams)
    modes[lib] = (info['mode'], info['transform'], len(info.get('hunks', [])), info.get('product_seams', 0))
    if seams:
        for seam in seams:
            assert text.count(seam['product_new']) == 1 and seam['product_old'] not in text, ('L2 seam result', seam['lib_hunk'])
        for seam in CFG.E3_PUBLICATION_SEAMS:        # the E3 harness reverts these to build its control world
            assert text.count(seam['product_new']) == 1, ('E3 publication text not exactly once in the product file', seam['lib_hunk'])
        reject(log, 'ide-ui projection without the L2 seams', lambda: P.project_text(by_name[name].read_text(), old, new, 'x', ()))
        reject(log, 'ide-ui projection with one L2 seam only', lambda: P.project_text(by_name[name].read_text(), old, new, 'x', seams[:1]))
        reject(log, 'ide-ui projection with a stale third seam', lambda: P.project_text(
            by_name[name].read_text(), old, new, 'x', seams + (dict(seams[0], lib_hunk_sha256='0' * 64),)))
assert modes == {'lib/ide-buffer.lisp': ('whole-file', 'rewrite_tokens', 0, 0),
                 'lib/ide-keymap-generated.lisp': ('whole-file', 'identity', 0, 0),
                 'lib/ide-ui.lisp': ('hunks', 'identity', 15, 2)}, modes
assert sorted(CFG.PROJECTIONS['ide'].values()) == sorted(CFG._git('diff', '--name-only', CFG.BASE_AUTHORITY, '--', 'lib').stdout.split()), \
    'changed lib files are not exactly the projected ones'
import c254_config as OLDCFG
assert [(s['product_old'], s['product_new']) for s in OLDCFG.PRODUCT_SEAMS[('ide', 'lib/ide-ui.lisp')] if s['action'] == 'replace'] == \
    [(s['product_old'], s['product_new']) for s in CFG.E3_PUBLICATION_SEAMS], 'E3 publication seams differ from the 2.5.4 product seams'
import c255_e3_product as E3P
e3_negatives = E3P.selftest()
assert len(e3_negatives) == 21, len(e3_negatives)
log.extend(e3_negatives)
assert set(P.tool_identity()) == {'product', 'producer', 'config', 'e3', 'e3_base'}
assert tuple(CFG.CANDIDATE_BLOBS['ide']) == tuple(CFG.E3_PROOF_IDE_BLOB)
print(json.dumps(dict(status='PASS', negative_controls=log, native_premise='real 2.5.4 recipe (link attempt r1) and src/ verified',
                      header_projection='real frozen 2.5.4 header verified (no macro may move)',
                      real_pairs=['2.5.2 r6->r7c', '2.5.3 r7->r8', '2.5.3 r8->2.5.4 (refused at the swapped pair)'],
                      projection=modes, host=dict(host=host['host'], python=P.python_runtime()['version'], probe=host_probe),
                      final_controls='not part of this selftest (Final-side successor, D-FIN)')))
