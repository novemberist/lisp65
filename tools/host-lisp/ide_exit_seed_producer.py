#!/usr/bin/env python3
"""Write-once IDE exit rebound producer. No implicit retry or Final.

command-probe is budget-free and requires committed, clean authority.
seed emits the candidate and replays exactly 75 commands (one product link).
price, inventory and media are separate artifact-only acceptance stages.
--selftest uses synthetic inputs only and never invokes product commands.
"""
import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
AUTH = '7b35c8ce'
HERE = ROOT / 'build/ide-exit-r5/seed'
BUILD = ROOT / 'build/ide-exit-product-r2'
FINAL = ROOT / 'build/comfort-default-final-r1'
RECIPE = ROOT / 'config/c2-v250-public-replay.json'
PLANE = ROOT / 'build/nested-error-recovery-product-r1-preflight/setup-owned/static-plane/narrow-static'
KEYMAP = ROOT / 'lib/ide-keymap-generated.lisp'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
PRIORITY = ['nice', '-n', '18', 'ionice', '-c3']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                bytes=len(raw), sha256=sha(raw))


def checked(row):
    path = ROOT / row['path']
    actual = bind(path)
    assert all(actual[k] == row[k] for k in ('bytes', 'sha256') if k in row), row
    return path.read_bytes()


def load(path):
    return json.loads(Path(path).read_text())


def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(raw, str):
        raw = raw.encode()
    if path.exists():
        assert path.read_bytes() == raw, f'write-once mismatch: {path}'
    else:
        path.write_bytes(raw)


def save(path, value):
    once(path, json.dumps(value, indent=2, sort_keys=True) + '\n')


def save_suite(path, value):
    # disk_files order is the virtual D81 directory order, including the
    # historical reserved first slot. Sorting it changes behavioral fixtures.
    once(path, json.dumps(value, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(PRIORITY + ['git', *args], cwd=ROOT, env=ENV).decode().strip()


def run(command, log):
    command = PRIORITY + list(map(str, command))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('xb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=ENV, stdout=stream,
                                stderr=subprocess.STDOUT)
    assert result.returncode == 0, f'command exit {result.returncode}: {log}'
    return log.read_bytes()


def snapshot(path, rows):
    path = Path(path).resolve()
    row = bind(path)
    target = HERE / 'inputs' / path.relative_to(ROOT)
    once(target, checked(row))
    rows[str(path)] = dict(source=row, restored=bind(target))
    return target


def authority():
    subprocess.run(PRIORITY + ['git', 'merge-base', '--is-ancestor', AUTH, 'HEAD'],
                   cwd=ROOT, env=ENV, check=True)
    allowed = {'tools/host-lisp/ide_exit_seed_producer.py',
               'docs/planning/post-2.4.0-plan.md'}
    changed = set(git('diff', '--name-only', AUTH, 'HEAD').splitlines())
    assert changed <= allowed, ('authority drift', sorted(changed - allowed))
    assert not git('status', '--porcelain', '--untracked-files=no'), 'tracked tree must be clean'
    assert KEYMAP.read_bytes() == subprocess.check_output(
        PRIORITY + ['git', 'show', AUTH + ':lib/ide-keymap-generated.lisp'], cwd=ROOT, env=ENV)


def command_probe():
    authority()
    assert not BUILD.exists(), 'product root already exists'
    HERE.mkdir(parents=True, exist_ok=False)
    recipe = load(RECIPE)
    final = load(FINAL / 'final-invocation.json')
    original_commands = final['commands']
    public = [[a.replace('build/comfort-default-product-r2/wplto/',
                         'build/comfort-default-final-r1/wplto/') for a in c]
              for c in recipe['commands']]
    assert [[a.removeprefix(str(ROOT) + '/') for a in c] for c in original_commands] == public
    for row in recipe['raw_pair'].values():
        checked(row)
    media = load(ROOT / 'config/c2-v250-public-media.json')
    checked(media['medium'])
    assert media['medium']['sha256'] == '137bfa51589f096eb715bc1e71c66196b79a365db65c1373696ea82f04dc34e5'
    native = []
    for row in recipe['inputs']:
        raw = checked(row['source'])
        target = HERE / 'native-inputs' / row['materialized_path']
        once(target, raw)
        # Use the exact Final input, without public comment normalization.
        assert (ROOT / row['materialized_path']).read_bytes() == raw
        native.append(dict(source=row['source'], original=row['materialized_path'], restored=bind(target)))
    prefix = str((HERE / 'native-inputs').relative_to(ROOT)) + '/'
    oldout = 'build/comfort-default-final-r1/wplto/'
    newout = str(BUILD.relative_to(ROOT)) + '/wplto/'
    def rebase(a):
        a = a.replace(oldout, newout)
        if a.startswith('build/comfort-default-r2/'):
            return prefix + a
        for token in ('-Wl,-L,', '-Wl,-T,'):
            if a.startswith(token + 'build/comfort-default-r2/'):
                return token + prefix + a[len(token):]
        return a
    commands = [[rebase(a) for a in c] for c in original_commands]
    assert len(commands) == 75
    save(HERE / 'baseline-command-proof.json', dict(status='COMMAND PROBE ONLY', commands=commands))
    rows = {}
    product = load(PLANE / 'product/substitution-artifacts.json')
    manifests = []
    for row in product['manifests']:
        checked(row)
        path = ROOT / row['path']
        target = snapshot(path, rows)
        manifest = load(path)
        blob = Path(manifest['blob'])
        assert sha(blob.read_bytes()) == manifest['blob_sha256']
        snapshot(blob, rows)
        manifests.append(str(target))
    ide = load(ROOT / product['manifests'][1]['path'])
    visited = {}
    def suite(path):
        path = Path(path).resolve()
        if str(path) in visited:
            return
        target = snapshot(path, rows)
        value = load(target)
        visited[str(path)] = str(target)
        for source in value.get('sources', []):
            snapshot(ROOT / source, rows)
        for resident in value.get('resident_suites', []):
            suite(ROOT / resident)
    suite(ide['suite'])
    old_keymap = next(Path(p) for p in ide['sources'] if p.endswith('/ide-keymap-generated.lisp'))
    old, new = old_keymap.read_text(), KEYMAP.read_text()
    assert new.replace('13 1013 113 1015', '13 1013') == old, 'unexpected source delta'
    once(HERE / 'keymap.patch', ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
         fromfile=str(old_keymap.relative_to(ROOT)), tofile='lib/ide-keymap-generated.lisp')))
    snapshot(KEYMAP, rows)
    for path in (RECIPE, FINAL / 'final-invocation.json', PLANE / 'product/substitution-artifacts.json',
                 ROOT / 'config/c2-v250-public-media.json',
                 PLANE / 'v6-semantics/initial.c2d-v6.bin',
                 PLANE / 'v6-semantics/bank2-static-code.bin',
                 PLANE / 'product/product-shelf-v4-direct.bin'):
        snapshot(path, rows)
    for path in sorted((FINAL / 'media').rglob('*')):
        if path.is_file() and path.suffix in ('.json', '.bin'):
            snapshot(path, rows)
    for package in load(FINAL / 'media/runtime-receipt.json')['packages']:
        path = ROOT / package['manifest']['path']
        checked(package['manifest'])
        snapshot(path, rows)
        manifest = load(path)
        snapshot(ROOT / manifest['blob'], rows)
    for path in (ROOT / 'build/nested-error-recovery-seed-medium-r1/packed').iterdir():
        if path.is_file() and path.suffix in ('.json', '.c', '.h'):
            snapshot(path, rows)
    # Bind the complete Python producer population; restored data sources are
    # independently checked against reproduced baseline code and metadata.
    tools = [bind(p) for p in sorted((ROOT / 'tools/host-lisp').glob('*.py')) if p != Path(__file__).resolve()]
    ready = dict(status='PASS: COMMAND PROBE ONLY', authority=AUTH, driver=bind(Path(__file__)),
        base_native=recipe['raw_pair'], base_media=media['medium'], native=native,
        closure=list(rows.values()), tools=tools, manifests=manifests,
        suites=visited, ide_suite=ide['suite'], old_keymap=str(old_keymap),
        commands=bind(HERE / 'baseline-command-proof.json'),
        reach=dict(stdlib_header='unchanged; does not contain IDE literals',
                   native=['LISP65_C2_PRODUCT_BUILD_ID', 'LISP65_C2_PRODUCT_SHELF_BYTES',
                           'c2_phase02a_shelf_crc16[6]', 'c2_phase02a_c2d_crc16[6]'],
                   media=['SHELF.BIN', 'C2D.BIN', 'native-derived runtime files',
                          'six disk package build IDs', 'L65INDEX', 'BOOT.ID']),
        budget=dict(seed=0, final=0, product_link=0))
    save(HERE / 'command-ready.json', ready)
    return dict(status=ready['status'], native_inputs=len(native), frozen_commands=len(commands),
                product_link_required=True, budget=ready['budget'])


def verify_ready(*, acceptance=False):
    ready = load(HERE / 'command-ready.json')
    authority()
    assert ready['authority'] == AUTH
    if acceptance:
        # The write-once Seed retains its original producer binding. Acceptance
        # repairs must be committed/clean, but do not rewrite Seed provenance.
        frozen = subprocess.check_output(PRIORITY + ['git', 'show',
            SEED_DRIVER_COMMIT + ':' + ready['driver']['path']], cwd=ROOT, env=ENV)
        assert len(frozen) == ready['driver']['bytes'] and sha(frozen) == ready['driver']['sha256']
    else:
        checked(ready['driver'])
    for row in ready['native']:
        checked(row['restored'])
    for row in ready['closure']:
        checked(row['source'])
        checked(row['restored'])
    for row in ready['tools']:
        checked(row)
    for row in ready['base_native'].values():
        checked(row)
    checked(ready['base_media'])
    checked(ready['commands'])
    return ready


def emit_ide(ready, restored, out, side):
    suite_paths = {p: out / ('suite-' + sha(p.encode())[:12] + '.json') for p in ready['suites']}
    for original, target in suite_paths.items():
        value = load(restored[original])
        assert not value.get('cases_from_suites') and not value.get('extends')
        value['sources'] = [restored[str((ROOT / p).resolve())] for p in value.get('sources', [])]
        value['resident_suites'] = [str(suite_paths[str((ROOT / p).resolve())]) for p in value.get('resident_suites', [])]
        if side == 'candidate':
            value['sources'] = [restored[str(KEYMAP)] if p == restored[ready['old_keymap']] else p for p in value['sources']]
        save_suite(target, value)
    command = [sys.executable, '-B', 'tools/host-lisp/bytecode_p0_stdlib.py',
               '--emit-artifacts', str(out / 'ide'), '--artifact-role', 'disk-lib', '--base-addr',
               '0x000000', str(suite_paths[ready['ide_suite']])]
    save(out / 'command.json', PRIORITY + command)
    run(command, out / 'emission.log')


def emit_planes(ready):
    import c2_full_emission as F
    import c2_substitution_artifacts as SUB
    import c2_lite_v6_product_probe as V6
    restored = {str(ROOT / r['source']['path']): str(ROOT / r['restored']['path'])
                for r in ready['closure']}
    compiled = {}
    for side in ('baseline', 'candidate'):
        out = BUILD / 'plane' / side
        out.mkdir(parents=True)
        emit_ide(ready, restored, out, side)
        specs = []
        for key, frozen in zip(('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc'), ready['manifests']):
            if key == 'ide':
                path = out / 'ide.manifest.json'
            else:
                value = load(frozen)
                value['blob'] = restored[str((ROOT / value['blob']).resolve())]
                path = out / (key + '.manifest.json')
                save(path, value)
            specs.append((key, 'stdlib' if key == 'stdlib-p0' else key, path))
        SUB.BUILD, SUB.SPECS = out / 'product', tuple(specs)
        product = SUB.build()
        V6.PRODUCT_IDENTITY = SUB.BUILD / 'substitution-artifacts.json'
        images = [F.emit_image(*spec) for spec in specs]
        V6.STATIC_CODE_BYTES = sum(len(i.code) for i in images)
        plane, geometry = V6.static_plane(images)
        once(out / 'CODE.BIN', bytes(plane.code[:plane.code_low]))
        once(out / 'C2D.BIN', bytes(plane.c2d))
        once(out / 'SHELF.BIN', (SUB.BUILD / 'product-shelf-v4-direct.bin').read_bytes())
        compiled[side] = dict(product=product, geometry=geometry, images=images, manifest=load(out / 'ide.manifest.json'))
    base, new = compiled['baseline'], compiled['candidate']
    expected = {'CODE.BIN': PLANE / 'v6-semantics/bank2-static-code.bin',
                'C2D.BIN': PLANE / 'v6-semantics/initial.c2d-v6.bin',
                'SHELF.BIN': PLANE / 'product/product-shelf-v4-direct.bin'}
    for name, path in expected.items():
        assert (BUILD / 'plane/baseline' / name).read_bytes() == Path(restored[str(path)]).read_bytes(), ('baseline reproduction', name)
    # Object-code identity and semantic literal ownership, independent of all
    # compiler heap placeholders, source paths and manifest numbering.
    entries = []
    for a, b in zip(base['manifest']['entries'], new['manifest']['entries'], strict=True):
        assert a['name'] == b['name']
        wanted = copy.deepcopy(a['literals'])
        if a['name'] == '%ide-prefix-command':
            assert wanted[1][-2:] == [13, 1013]
            wanted[1] += [113, 1015]
        assert b['literals'] == wanted, a['name']
        assert (a['blob_offset'], a['length'], a['lit_count']) == (b['blob_offset'], b['length'], b['lit_count'])
        entries.append(dict(name=a['name'], bytes=a['length'], literals_identical=a['literals'] == b['literals']))
    for a, b in zip(base['images'], new['images'], strict=True):
        assert a.code == b.code, a.key
        if a.key != 'ide':
            assert a.metadata == b.metadata, a.key
    deltas = {name: (BUILD / 'plane/candidate' / name).stat().st_size - (BUILD / 'plane/baseline' / name).stat().st_size for name in expected}
    literal_delta = len(new['images'][1].metadata) - len(base['images'][1].metadata)
    assert deltas['CODE.BIN'] == 0 and deltas['C2D.BIN'] == 0 and deltas['SHELF.BIN'] == literal_delta
    result = dict(status='PASS', baseline_exact=True, entries=entries, codegen_drift_bytes=0,
                  plane_deltas=deltas, literal_metadata_delta=literal_delta,
                  before_geometry=base['geometry'], after_geometry=new['geometry'],
                  before_product=base['product'], after_product=new['product'],
                  bound=64, total_growth=sum(deltas.values()))
    result['artifacts'] = [bind(BUILD / 'plane' / side / name) for side in ('baseline', 'candidate') for name in expected]
    save(HERE / 'plane-price.json', result)
    assert result['total_growth'] <= 64, 'plane price exceeds +64'
    return result


def derived_commands(ready, plane):
    import runtime_overlay_bank as BANK
    commands = load(HERE / 'baseline-command-proof.json')['commands']
    source = ROOT / commands[29][commands[29].index('-c') + 1]
    original = source.read_text()
    projected = original
    changes = []
    for name, file, offset in [('shelf', 'SHELF.BIN', 32), ('c2d', 'C2D.BIN', None)]:
        raw = [(BUILD / 'plane' / side / file).read_bytes() for side in ('baseline', 'candidate')]
        if offset is None:
            offset = struct.unpack_from('<H', raw[0], 28)[0]
            assert offset == struct.unpack_from('<H', raw[1], 28)[0]
        values = [[BANK.crc16_ccitt_false(data[offset+i*32:offset+(i+1)*32]) for i in range(6)] for data in raw]
        def emitted(crcs):
            return 'c2_phase02a_' + name + '_crc16:\\n' + '\\n'.join(f'.short 0x{x:04x}' for x in crcs) + '\\n'
        old, new = map(emitted, values)
        assert projected.count(old) == 1, name
        projected = projected.replace(old, new)
        changes.append(dict(table=name, before=values[0], after=values[1]))
    target = HERE / 'derived' / source.relative_to(HERE / 'native-inputs')
    # Keep quoted decoder includes at their frozen locations through -I.
    once(target, projected)
    before, after = plane['before_product'], plane['after_product']
    replacements = {str(source.relative_to(ROOT)): str(target.relative_to(ROOT)),
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + before['product_build_id_hex'] + 'UL':
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + after['product_build_id_hex'] + 'UL',
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(before['artifacts']['shelf']['bytes']) + 'UL':
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(after['artifacts']['shelf']['bytes']) + 'UL'}
    assert len(commands) == 75
    assert all(any(key in command for command in commands) for key in replacements), 'derived input not consumed'
    updated = [[replacements.get(a, a) for a in c] for c in commands]
    save(HERE / 'derived-inputs.json', dict(replacements=replacements, crc_tables=changes,
         generated=bind(target), before=bind(source), stdlib_header_changed=False))
    save(HERE / 'command-proof.json', dict(commands=updated, authority=ready['authority'],
         allowed_substitutions=replacements, frozen=ready['commands']))
    return updated


def include_closure(commands, ready):
    allowed = {str((ROOT / r['restored']['path']).resolve()): r['restored'] for r in ready['native']}
    generated = load(HERE / 'derived-inputs.json')['generated']
    allowed[str((ROOT / generated['path']).resolve())] = generated
    # Toolchain includes are explicit public replay bindings, consumed in place.
    for r in ready['native']:
        if r['source']['path'].startswith('tools/llvm-mos/'):
            allowed[str((ROOT / r['source']['path']).resolve())] = r['source']
    rows = []
    for i, command in enumerate(commands[:73]):
        source = command[command.index('-c')+1]
        if source.endswith('.s'):
            dirs = [ROOT] + [ROOT / command[j+1] for j, a in enumerate(command) if a == '-I']
            pending, deps = [ROOT / source], set()
            while pending:
                path = pending.pop().resolve()
                if str(path) in deps:
                    continue
                deps.add(str(path))
                for name in re.findall(r'^\s*\.include\s+"([^"]+)"', path.read_text(), re.M):
                    found = next((d / name for d in dirs if (d / name).is_file()), None)
                    assert found is not None, name
                    pending.append(found)
        else:
            c = list(command)
            at = c.index('-o')
            del c[at:at+2]
            c.remove('-c')
            raw = run(c + ['-E', '-M', '-MT', 'input'], HERE / 'include-logs' / f'{i:03d}.log')
            deps = {str((ROOT / p).resolve()) for p in shlex.split(raw.decode().replace('\\\n', ' ').split(':', 1)[1])}
        for path in deps:
            assert path in allowed, ('unbound dependency', path)
            checked(allowed[path])
        rows.append(dict(source=source, dependencies=[allowed[p] for p in sorted(deps)]))
    save(HERE / 'include-closure.json', dict(status='PASS', translation_units=73, rows=rows))


def price():
    verify_ready(acceptance=True)
    seeded = load(BUILD / 'seed.json')
    assert seeded['commands_consumed'] == 75 and seeded['product_link_attempts'] == 1
    for row in seeded['native'].values():
        checked(row)
    assert not (HERE / 'price.json').exists(), 'price receipt already exists'
    from elf_truth import ElfTruth
    paths = [FINAL / 'wplto/resident-island-seed.prg.elf', BUILD / 'wplto/resident-island-seed.prg.elf']
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in paths]
    a, b = truths
    def sizes(t):
        return {'.text': t.section('.text').bytes, '.rodata': t.section('.rodata').bytes,
                'BSS': sum(s.bytes for s in t.sections if s.section_type == 'SHT_NOBITS' and 'SHF_ALLOC' in s.flags),
                'CRT_zero_bytes': t.symbol('__bss_end').value - t.symbol('__bss_start').value}
    old, new = map(sizes, truths)
    delta = {k: new[k] - v for k, v in old.items()}
    sites = []
    for x in a.symbols:
        if not x.bytes or x.symbol_type not in ('Function', 'Object'):
            continue
        ys = [y for y in b.symbols_by_name.get(x.name, []) if y.section == x.section and y.symbol_type == x.symbol_type]
        if len(ys) != 1:
            continue
        y = ys[0]
        if x.bytes != y.bytes:
            sites.append(dict(name=x.name, section=x.section, before=x.bytes, after=y.bytes, delta=y.bytes-x.bytes))
    sections = [dict(name=s.name, before=a.section(s.name).bytes, after=s.bytes, delta=s.bytes-a.section(s.name).bytes)
                for s in b.sections if 'SHF_ALLOC' in s.flags and s.name in a.sections_by_name and s.bytes != a.section(s.name).bytes]
    plane = load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        checked(row)
    assert plane['status'] == 'PASS' and plane['total_growth'] <= 64
    passed = not any(delta.values())
    result = dict(status='PASS' if passed else 'HALT: NONZERO NATIVE PRICE',
        ELF=[bind(p) for p in paths], before=old, after=new, delta=delta, bound=0,
        plane=plane['plane_deltas'], plane_total=plane['total_growth'], plane_bound=64,
        section_deltas=sections, per_site_bytes=sites,
        free_after=dict(text=0xb3b0-b.section('.text').address-b.section('.text').bytes,
                        rodata=0xb98c-b.section('.rodata').address-b.section('.rodata').bytes,
                        high_bss=0xc000-b.symbol('__bss_end').value))
    save(HERE / 'price.json', result)
    return result


def seed():
    ready = verify_ready()
    assert not BUILD.exists(), 'Seed already claimed; no implicit retry'
    BUILD.mkdir()
    save(BUILD / 'attempt.json', dict(authority=AUTH, seed=1, final=0, product_link_attempts=0,
                                     command_probe=bind(HERE / 'command-ready.json')))
    state = dict(status='STARTED', authority=AUTH, seed=1, final=0, product_link_attempts=0)
    try:
        plane = emit_planes(ready)
        commands = derived_commands(ready, plane)
        include_closure(commands, ready)
        for i, command in enumerate(commands):
            if i == 74:
                state['product_link_attempts'] = 1
                save(BUILD / 'product-link-claim.json', state)
            output = ROOT / command[command.index('-o')+1]
            output.parent.mkdir(parents=True, exist_ok=True)
            run(command, BUILD / f'command-{i:03d}.log')
            state['commands_consumed'] = i+1
            print(f'completed frozen command {i+1}/75', flush=True)
        state['native'] = {role: bind(BUILD / 'wplto' / Path(row['path']).name) for role, row in ready['base_native'].items()}
        state['status'] = 'LINKED: run price, inventory, media in order'
    except BaseException as error:
        state.update(status='HALT', error=str(error))
        raise
    finally:
        save(BUILD / 'seed.json', state)
    return state



def classify_bytes(before, after, domains):
    """Exact expected byte pairs, never blanket changed-section exemptions."""
    rows, unknown = [], []
    for i in range(max(len(before), len(after))):
        a = before[i] if i < len(before) else None
        b = after[i] if i < len(after) else None
        if a == b:
            continue
        expected = domains.get(i)
        owner = expected[2] if expected and expected[:2] == (a, b) else 'UNCLASSIFIED'
        rows.append(dict(offset=i, before=a, after=b, owner=owner))
        if owner == 'UNCLASSIFIED':
            unknown.append(i)
    return dict(rows=rows, changed_bytes=len(rows), unclassified_bytes=len(unknown))


# This is a proof for one already-linked pair, not a generic relaxation.
DRIFT_SECTION = '.lisp65_rt_c2emit_final_crc'
DRIFT_ALLOWLIST = {DRIFT_SECTION: dict(
    before=1243, after=1244, max_growth=1, vma=0xc356,
    before_sha256='69e22202c62879c359239eb5bc2217422efc31b5641aa10ca68174c1ed5befd7')}
SEED_DRIVER_COMMIT = '712450b78c75eac82da190f698068875154d8e5f'
BASE_ELF_SHA = 'd555f01fbac51bb5fbc035b2b595e95e3c8e3bedc584c87112bca8b073e31444'


def prove_final_crc(a, b):
    """Project instructions/relocations from the baseline, never from new bytes.

    At c677, DEC A (A=17) and LDA #16 have identical A/N/Z and leave
    C/V/D/I/X/Y/memory unchanged. The four build-ID bytes are data.
    Every other instruction is identical under the one-byte address map.
    """
    spec = DRIFT_ALLOWLIST[DRIFT_SECTION]
    old, new = a.section_bytes(DRIFT_SECTION), b.section_bytes(DRIFT_SECTION)
    assert len(old) == spec['before'] and len(new) == spec['after']
    assert len(new)-len(old) == spec['max_growth']
    assert sha(old) == spec['before_sha256']
    assert a.section(DRIFT_SECTION).address == b.section(DRIFT_SECTION).address == spec['vma']
    start, cut = spec['vma'], 0xc677
    expected = bytearray(old)
    # Straight-line, no call/branch between LDA #17 and DEC A. Loads/stores
    # of X/Y do not modify A; both replacement forms define N/Z identically.
    prefix = bytes.fromhex('a00ba917a29484048505a0ad84068607a2003a')
    assert old[0xc665-start:cut-start+1] == prefix
    for address, before, after in ((0xc666, 0x0b, 0x15), (0xc668, 0x17, 0xfb),
                                   (0xc66a, 0x94, 0xa6), (0xc670, 0xad, 0xf5)):
        assert expected[address-start] == before
        expected[address-start] = after
    # Only section-relative absolute targets move. PC-relative branches
    # must retain their displacement (both endpoints on the same side).
    moved = 0
    for r in a.relocations:
        if r.source_section != DRIFT_SECTION or r.target != DRIFT_SECTION:
            continue
        assert r.relocation_type in ('R_MOS_ADDR16', 'R_MOS_PCREL8')
        target = start+r.addend
        if r.relocation_type == 'R_MOS_PCREL8':
            assert (r.offset > cut) == (target > cut)
        elif target > cut:
            at = r.offset-start
            assert struct.unpack_from('<H', old, at)[0] == target
            struct.pack_into('<H', expected, at, target+1)
            moved += 1
    expected[cut-start:cut-start+1] = b'\xa9\x16'
    assert bytes(expected) == new, 'unproven final CRC instruction drift'
    return dict(section=DRIFT_SECTION, growth=1, bound=1,
                before_sha256=sha(old), after_sha256=sha(new),
                replacement='c677: 3a (DEC A, A=17) -> a9 16 (LDA #16)',
                rebased_absolute_targets=moved)


def project_drift(raw, a, b):
    """Exact physical ELF projection for the bounded instruction proof.

    File packing adds one byte, aligns the following NOBITS boundary to 2,
    then consumes the two old bytes of padding before the aligned symtab.
    No size/address/relocation exception is inferred from the candidate.
    """
    from dataclasses import replace
    assert sha(raw) == BASE_ELF_SHA, 'drift proof baseline binding'
    proof = prove_final_crc(a, b)
    start, cut = 0xc356, 0xc677
    assert len(a.sections) == len(b.sections) and len(a.symbols) == len(b.symbols)
    for x, y in zip(a.sections, b.sections):
        assert y == (replace(x, bytes=x.bytes+1) if x.name == DRIFT_SECTION else x), 'unallowed section geometry'
    for x, y in zip(a.symbols, b.symbols):
        expected = x
        if x.section == DRIFT_SECTION:
            if x.name == 'c2_session_emit_final_crc_phase':
                assert (x.value, x.bytes) == (start, 893)
                expected = replace(x, bytes=894)
            elif x.value > cut:
                assert x.name in ('c2e_crc', 'c2e_w32', '__lisp65_rt_c2emit_final_crc_end')
                expected = replace(x, value=x.value+1)
        assert y == expected, 'unallowed symbol drift'
    expected_relocs = []
    for r in a.relocations:
        changes = {}
        if r.source_section == DRIFT_SECTION:
            if r.offset > cut:
                changes['offset'] = r.offset+1
            if r.target == DRIFT_SECTION and start+r.addend > cut:
                changes['addend'] = r.addend+1
        expected_relocs.append(replace(r, **changes))
    assert b.relocations == expected_relocs, 'unallowed relocation drift'
    shoff = struct.unpack_from('<I', raw, 32)[0]
    phoff = struct.unpack_from('<I', raw, 28)[0]
    assert (shoff, phoff) == (653936, 52)
    assert struct.unpack_from('<HHHH', raw, 42) == (32, 109, 40, 222)
    # Replace the proven section; shift packed successors and preserve all
    # contents, including non-allocated sections. Padding is checked as zero.
    assert raw[136062:136064] == bytes(2)
    expected = bytearray(raw[:91616] + b.section_bytes(DRIFT_SECTION)
                         + raw[92859:124370] + b'\0'
                         + raw[124370:136062] + raw[136064:])
    assert len(expected) == len(raw)
    for i in range(222):
        at = shoff+i*40
        if i == 81:
            struct.pack_into('<I', expected, at+20, 1244)
        delta = 1 if 82 <= i <= 109 else 2 if 110 <= i <= 130 or i == 1 else 0
        if delta:
            oldoff = struct.unpack_from('<I', raw, at+16)[0]
            struct.pack_into('<I', expected, at+16, oldoff+delta)
    for i in range(109):
        at = phoff+i*32
        if i == 60:
            struct.pack_into('<II', expected, at+16, 1244, 1244)
        delta = 1 if 61 <= i <= 88 else 2 if 89 <= i <= 107 else 0
        if delta:
            struct.pack_into('<I', expected, at+4, struct.unpack_from('<I', raw, at+4)[0]+delta)
        if 61 <= i <= 86 or 104 <= i <= 107:
            struct.pack_into('<I', expected, at+12, struct.unpack_from('<I', raw, at+12)[0]+1)
    # ELF32 symbol values/sizes and RELA offsets/addends follow the same map.
    for x, y in zip(a.symbols, b.symbols):
        if x != y:
            struct.pack_into('<II', expected, 136064+x.index*16+4, y.value, y.bytes)
    relsec = a.section('.rela'+DRIFT_SECTION)
    off = struct.unpack_from('<I', raw, shoff+relsec.index*40+16)[0]
    rows = [r for r in expected_relocs if r.source_section == DRIFT_SECTION]
    assert relsec.bytes == len(rows)*12
    for i, r in enumerate(rows):
        struct.pack_into('<I', expected, off+12*i, r.offset)
        struct.pack_into('<i', expected, off+12*i+8, r.addend)
    return expected, proof


def inventory():
    from elf_truth import ElfTruth
    verify_ready(acceptance=True)
    priced = load(HERE / 'price.json')
    assert priced['status'] == 'PASS'
    assert not (HERE / 'inventory.json').exists(), 'inventory already exists'
    paths = [ROOT / r['path'] for r in priced['ELF']]
    raws = [checked(r) for r in priced['ELF']]
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj',
                           include_section_data=True) for p in paths]
    result = inventory_analysis(paths, raws, truths)
    result.update(ELFs=priced['ELF'], plane=bind(HERE / 'plane-price.json'),
                  derived=bind(HERE / 'derived-inputs.json'))
    save(HERE / 'inventory.json', result)
    assert result['unclassified_bytes'] == 0, 'unclassified ELF bytes'
    return result


def inventory_analysis(paths, raws, truths, listing_reader=None):
    """Read-only classification core; acceptance receipt is written by inventory."""
    a, b = truths
    drift = a.sections != b.sections
    if drift:
        expected, proof = project_drift(raws[0], a, b)
    else:
        assert a.symbols == b.symbols and a.relocations == b.relocations, 'ELF identity drift'
        expected, proof = bytearray(raws[0]), None
    plane = load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        checked(row)
    derived = load(HERE / 'derived-inputs.json')
    labels = ['proven final CRC codegen / ELF packing metadata' if drift else 'unchanged']*len(expected)
    def add(section, offset, old, new, owner):
        assert len(old) == len(new)
        for truth, payload in zip(truths, (old, new)):
            assert truth.section_bytes(section)[offset:offset+len(payload)] == payload
        shoff = struct.unpack_from('<I', raws[0], 32)[0]
        shsize = struct.unpack_from('<H', raws[0], 46)[0]
        fileoff = struct.unpack_from('<I', expected, shoff+a.section(section).index*shsize+16)[0]
        assert expected[fileoff+offset:fileoff+offset+len(old)] == old
        expected[fileoff+offset:fileoff+offset+len(new)] = new
        labels[fileoff+offset:fileoff+offset+len(new)] = [owner]*len(new)
    for row in derived['crc_tables']:
        symbol = a.symbol('c2_phase02a_' + row['table'] + '_crc16')
        add(symbol.section, symbol.value-a.section(symbol.section).address,
            struct.pack('<6H', *row['before']), struct.pack('<6H', *row['after']),
            'derived ' + row['table'] + ' directory CRC16 array')
    pairs = []
    for key in ('before_product', 'after_product'):
        product = plane[key]
        pairs.append((int(product['product_build_id_hex'], 16), product['artifacts']['shelf']['bytes']))
    if drift:
        assert pairs[0][0] == 0x94ad170b and pairs[1][0] == 0xa6f5fb15
    # Decode immediate instruction boundaries in the known constant consumers.
    # Outside the proven overlay, opcodes, relocations, symbols and VMAs stay fixed.
    consumers = {
        'c2_stream_phase_00': 0, 'c2_stream_phase_00b': 0,
        'c2_stream_phase_01': 0, 'c2_append_envelope_phase': 0,
        'c2_session_emit_final_crc_phase': 0, 'c2_stream_shelf_read': 1, 'c2_product_boot': 1,
        'main': 1,  # c2_product_boot is inlined by the frozen Final LTO

    }
    for name, kind in consumers.items():
        if name not in a.symbols_by_name or (drift and name == 'c2_session_emit_final_crc_phase'):
            continue
        symbol = a.symbol(name)
        command = [str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-d',
                   '--section=' + symbol.section, '--start-address=' + str(symbol.value),
                   '--stop-address=' + str(symbol.value+symbol.bytes), str(paths[0])]
        listing = (listing_reader(command, name) if listing_reader else
                   run(command, HERE / 'inventory-logs' / (name + '.log')).decode())
        # Unsigned offset > limit can be lowered as offset >= limit+1.
        adjustments = (0, 1) if name == 'c2_stream_shelf_read' else (0,)
        allowed = {(x, y) for adjustment in adjustments
                   for x, y in zip(struct.pack('<I', pairs[0][kind]+adjustment),
                                   struct.pack('<I', pairs[1][kind]+adjustment)) if x != y}
        for line in listing.splitlines():
            match = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s+(?:lda|ldx|ldy|cmp|cpx|cpy|eor|ora|and|adc|sbc)\s+#', line)
            if not match:
                continue
            offset = int(match[1], 16)-a.section(symbol.section).address
            old = a.section_bytes(symbol.section)[offset:offset+2]
            new = b.section_bytes(symbol.section)[offset:offset+2]
            assert old == bytes.fromhex(match[2]+match[3])
            if old[0] == new[0] and (old[1], new[1]) in allowed:
                add(symbol.section, offset+1, old[1:], new[1:], 'derived immediate: '+name)
    domains = {i: (old, new, labels[i]) for i, (old, new) in enumerate(zip(raws[0], expected))
               if old != new}
    result = classify_bytes(*raws, domains)
    result.update(status='PASS' if result['unclassified_bytes'] == 0 else 'HALT: UNCLASSIFIED',
                  geometry_proof=proof, expected_elf_sha256=sha(expected))
    return result


def rebind_family(C, fam, value, regions, a, b, elf):
    """Comfort lineage: rebind every payload, record, directory and header CRC."""
    BANK = C.BANK
    for row in value['slices']:
        old, new = a.section_bytes(row['section']), b.section_bytes(row['section'])
        off, rid = row['file_offset'], row['region_id']
        assert len(old) == row['file_size']
        if len(old) != len(new):
            assert fam == 'session' and row['section'] in DRIFT_ALLOWLIST
            prove_final_crc(a, b)
            assert (row['id'], rid, off, row['vma']) == (22, 0, 29664, 0xc356)
            assert row['memory_size'] == len(old)
            following = min(r['file_offset'] for r in value['slices']
                            if r['region_id'] == rid and r['file_offset'] > off)
            assert following == 30912 and off+len(new) <= following
            assert len(new) <= value['policy']['max_slice_bytes'] == 1792
            assert regions[rid][off+len(old):following] == bytes(following-off-len(old))
            row.update(file_size=len(new), memory_size=len(new), end=row['vma']+len(new))
            at = 32+32*row['id']
            struct.pack_into('<H', regions[0], at+6, len(new))
            struct.pack_into('<H', regions[0], at+10, len(new))
        assert regions[rid][off:off+len(old)] == old
        regions[rid][off:off+len(new)] = new
        row.update(sha256=sha(new), crc16=BANK.crc16_ccitt_false(new))
        at = 32+32*row['id']
        struct.pack_into('<H', regions[0], at+20, row['crc16'])
        regions[0][at+22:at+24] = bytes(2)
        row['record_crc16'] = BANK.crc16_ccitt_false(regions[0][at:at+32])
        struct.pack_into('<H', regions[0], at+22, row['record_crc16'])
    over = regions[1]
    crc = BANK.crc16_ccitt_false(over)
    struct.pack_into('<I', regions[0], 28, len(over) | ((crc if over else 0) << 16))
    BANK._refresh_catalog_crcs(regions[0])
    value['overflow_storage'].update(crc16=crc, sha256=sha(over))
    value['storage'].update(crc16=BANK.crc16_ccitt_false(regions[0]), sha256=sha(regions[0]))
    value['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26], 'little'),
                            header_crc16=int.from_bytes(regions[0][26:28], 'little'))
    if fam == 'session':
        value['external_storage'].update(crc16=BANK.crc16_ccitt_false(regions[2]), sha256=sha(regions[2]))
    value['elf'] = dict(bind(elf), file=str(elf))
    return C.validate_family(fam, value, regions, a, b)


def replace_file(image, name, payload, domains):
    """Classify exact D81 transaction bytes, including allocation and directory."""
    import d81_persistence_fault as D
    if D.visible_files(image)[name.upper().encode()] == payload:
        return image
    slot, = [s for s in D.directory_slots(image) if s.record[2] and D.entry_name(s.record) == name.upper().encode()]
    chain = list(D.file_chain(image, slot.record))
    count = (len(payload)+253)//254
    assert count and count <= 0xffff
    state = bytearray(image)
    freed = chain[count:]
    chain = chain[:count]
    for track in list(range(1, 40))+list(range(41, 81)):
        for sector in range(40):
            if len(chain) < count and D.sector_is_free(state, track, sector):
                chain.append((track, sector))
                D.set_sector_free(state, track, sector, False)
    assert len(chain) == count, 'D81 full'
    for track, sector in freed:
        D.set_sector_free(state, track, sector, True)
    for index, (track, sector) in enumerate(chain):
        at = D.sector_offset(track, sector)
        state[at:at+256] = D.chain_sector(payload, tuple(chain), index)
    at = D.sector_offset(slot.track, slot.sector)+slot.index*32
    state[at+3:at+5] = bytes(chain[0])
    struct.pack_into('<H', state, at+30, count)
    # Compute expected edits from this deterministic allocation plan. The
    # ledger is later compared to the actual persisted image, byte for byte.
    data_offsets = {D.sector_offset(t, sec)+i for t, sec in chain for i in range(256)}
    for i, (old, new) in enumerate(zip(image, state)):
        if old != new:
            kind = 'file-chain' if i in data_offsets else 'directory' if at <= i < at+32 else 'BAM'
            original = domains[i][0] if i in domains else old
            domains[i] = (original, new, name + ': ' + kind)
    state = bytes(state)
    D.validate_bam(state)
    assert D.visible_files(state)[name.upper().encode()] == payload
    return state


def pack_media(C, med, artifacts, before_raw, packages, build_id):
    D, L = C.L.D81, C.L
    before = D.visible_files(before_raw)
    expected = {name: (artifacts / name.decode().lower()).read_bytes() for name in before}
    raw, domains = before_raw, {}
    for name, payload in expected.items():
        if name != b'L65INDEX':
            raw = replace_file(raw, name.decode(), payload, domains)
    # Package locators are final before the index is encoded.
    medium = med / 'locator-image.d81'
    once(medium, raw)
    locators = L.L65I.d81_locators(medium)
    rows, payloads = [], {}
    for row in packages:
        name = row['name']
        entry, payload = L.F.measured_row(name, name, row['shelf'], ROOT / row['manifest']['path'],
            tuple(row['dependencies']), *locators[name], product_build_id=build_id)
        assert payload == expected[name.upper().encode()]
        rows.append(entry); payloads[name] = payload
    index = L.L65I.encode_index(rows)
    expected[b'L65INDEX'] = index
    raw = replace_file(raw, 'l65index', index, domains)
    final = med / 'ide-exit.d81'
    once(final, raw)
    D.validate_bam(raw)
    raw = final.read_bytes()
    actual = D.visible_files(raw)
    assert actual == expected, 'every file must read back exactly'
    assert L.L65I.decode_index(actual[b'L65INDEX'], payloads, artifact_build_id=build_id) == rows
    mutations = L.L65I.mutation_gate(index, payloads, artifact_build_id=build_id)
    diff = classify_bytes(before_raw, raw, domains)
    assert diff['unclassified_bytes'] == 0
    save(med / 'd81-byte-diff.json', diff)
    return dict(status='PASS', medium=bind(final), base_sha256=sha(before_raw),
        every_file_read_back=True, files={n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in actual.items()},
        unclassified_bytes=0, diff=bind(med / 'd81-byte-diff.json'), mutations=mutations,
        product_links=0, emulator_runs=0, device_contacts=0)


def media_plane_control(ready, before):
    """Compare emission with frozen emission, and delivery with delivery."""
    import c2_lite_media_product as M
    sources = {'CODE.BIN': PLANE / 'v6-semantics/bank2-static-code.bin',
               'C2D.BIN': PLANE / 'v6-semantics/initial.c2d-v6.bin',
               'SHELF.BIN': PLANE / 'product/product-shelf-v4-direct.bin'}
    closure = {str((ROOT / r['source']['path']).resolve()): r for r in ready['closure']}
    proof = {}
    for name, source in sources.items():
        row = closure[str(source.resolve())]
        baseline = (BUILD / 'plane/baseline' / name).read_bytes()
        assert baseline == checked(row['source']) == checked(row['restored']), ('pre-media baseline', name)
        delivered = before[name.encode()]
        if name == 'C2D.BIN':
            assert len(baseline) == M.C2D_PREFIX_BYTES
            expected = baseline + bytes(M.C2D_RESET_DOMAIN_BYTES - len(baseline))
            assert delivered == expected, 'complete C2D reset-domain control'
        elif name == 'SHELF.BIN':
            assert delivered == baseline, 'complete shelf control'
        else:
            assert len(delivered) >= len(baseline) and delivered[:len(baseline)] == baseline, 'static code control'
        proof[name] = dict(emitted_bytes=len(baseline), emitted_sha256=sha(baseline),
                           delivered_bytes=len(delivered), delivered_sha256=sha(delivered),
                           suffix_bytes=len(delivered)-len(baseline), frozen=row['restored'])
    return dict(status='PASS', comparison='frozen pre-media emission; exact delivery projection', files=proof)


def media(output=None):
    import comfort_default_media as C
    ready = verify_ready(acceptance=True)
    inv = load(HERE / 'inventory.json')
    assert inv['status'] == 'PASS' and inv['unclassified_bytes'] == 0
    assert load(HERE / 'price.json')['status'] == 'PASS'
    for row in load(BUILD / 'seed.json')['native'].values():
        checked(row)
    for row in inv['ELFs']:
        checked(row)
    checked(inv['plane']); checked(inv['derived'])
    for row in load(HERE / 'plane-price.json')['artifacts']:
        checked(row)
    authority_media = load(ROOT / 'config/c2-v250-public-media.json')
    checked(authority_media['builder'])
    before_raw = checked(authority_media['medium'])
    assert sha(before_raw) == '137bfa51589f096eb715bc1e71c66196b79a365db65c1373696ea82f04dc34e5'
    before = C.L.D81.visible_files(before_raw)
    assert {n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in before.items()} == authority_media['files']
    control = media_plane_control(ready, before)
    med = output if output is not None else BUILD / 'media'
    med.mkdir(exist_ok=False)
    artifacts = med / 'artifacts'
    artifacts.mkdir()
    save(med / 'plane-control.json', control)
    for name, data in before.items():
        once(artifacts / name.decode().lower(), data)
    elf = ROOT / inv['ELFs'][1]['path']
    a, b = [C.ElfTruth.read(ROOT / r['path'], llvm_readobj=C.READOBJ, include_section_data=True) for r in inv['ELFs']]
    families, manifests = {}, []
    for fam in ('boot', 'session'):
        value = load(FINAL / 'media' / ('runtime-overlays-'+fam+'-final.json'))
        regions = {0: bytearray(before[(fam+'.bin').upper().encode()]),
                   1: bytearray((FINAL / 'media' / value['overflow_storage']['file']).read_bytes())}
        if fam == 'session':
            regions[2] = bytearray(a.section_bytes('.lisp65_rt_card2b_disk'))
        families[fam] = rebind_family(C, fam, value, regions, a, b, elf)
        (artifacts / (fam+'.bin')).write_bytes(regions[0])
        once(med / value['overflow_storage']['file'], regions[1])
        if fam == 'session':
            (artifacts / 'region1.bin').write_bytes(regions[1])
            code = bytearray(before[b'CODE.BIN'])
            assert code[0xee00:0xee00+len(regions[2])] == a.section_bytes('.lisp65_rt_card2b_disk')
            code[0xee00:0xee00+len(regions[2])] = regions[2]
            (artifacts / 'code.bin').write_bytes(code)
        path = med / ('runtime-overlays-'+fam+'-final.json')
        save(path, value); manifests.append(path)
    window = bytearray(before[b'WINDOW.BIN'])
    for section in a.sections:
        if section.name.startswith('.lisp65_c2_kernal_window.') and section.section_type != 'SHT_NOBITS':
            old, new = a.section_bytes(section.name), b.section_bytes(section.name)
            at = section.address-0xe000
            assert 0 <= at and at+len(old) <= len(window) and len(old) == len(new)
            assert window[at:at+len(old)] == old
            window[at:at+len(new)] = new
        elif section.name.startswith('.lisp65_c2_mapped_') and section.section_type != 'SHT_NOBITS':
            assert a.section_bytes(section.name) == b.section_bytes(section.name), section.name
    (artifacts / 'window.bin').write_bytes(window)
    assert a.section_bytes('.lisp65_c2_vectors') == b.section_bytes('.lisp65_c2_vectors')
    code = bytearray((artifacts / 'code.bin').read_bytes())
    baseline_code = (BUILD / 'plane/baseline/CODE.BIN').read_bytes()
    candidate_code = (BUILD / 'plane/candidate/CODE.BIN').read_bytes()
    assert code[:len(baseline_code)] == baseline_code and len(candidate_code) == len(baseline_code)
    code[:len(candidate_code)] = candidate_code
    (artifacts / 'code.bin').write_bytes(code)
    for name in ('SHELF.BIN', 'C2D.BIN'):
        candidate = (BUILD / 'plane/candidate' / name).read_bytes()
        if name == 'C2D.BIN':
            assert len(candidate) == C.M.C2D_PREFIX_BYTES
            candidate += bytes(C.M.C2D_RESET_DOMAIN_BYTES - len(candidate))
        (artifacts / name.lower()).write_bytes(candidate)
    table = C.P.verifier_binding_bytes(*manifests)+C.P.family_stage_binding_bytes(*manifests)
    assert len(table) == 40
    once(med / 'runtime-overlay-verifier-bindings.bin', table)
    prg = med / 'lisp65-c2-substitution-linked.prg'
    once(prg, elf.with_suffix('').read_bytes())
    C.FACADE.materialize_facade(prg, elf, med / 'facade-materialization.json')
    unbound = prg.read_bytes()
    once(med / 'lisp65-c2-substitution-unbound.prg', unbound)
    C.PRG.from_elf(elf, unbound)
    raw = bytearray(unbound)
    at = b.section('.lisp65_runtime_overlay_verifier_bindings').address-int.from_bytes(raw[:2], 'little')+2
    raw[at:at+40] = table
    binding = load(FINAL / 'media/kernal-window-publish-last.json')
    crc = C.BANK.crc16_ccitt_false(window)
    binding['single_product_link_window'] = dict(bind(artifacts / 'window.bin'), crc16=f'0x{crc:04x}')
    for row in binding['binding_operands']:
        assert raw[row['file_offset']] == row['compiled_value']
        row['published_value'] = (crc >> 8) & 255 if row['name'].endswith('high') else crc & 255
        raw[row['file_offset']] = row['published_value']
    save(med / 'kernal-window-publish-last.json', binding)
    domain = set(range(at, at+40)) | {r['file_offset'] for r in binding['binding_operands']}
    assert len(raw) == len(unbound) and all(x == y or i in domain for i, (x, y) in enumerate(zip(unbound, raw)))
    save(med / 'total-publish-last-domain.json', dict(status='passed', changes_outside_declared_domains=0,
        declared_domain_bytes=len(domain), bound_product_sha256=sha(raw), unbound_product_sha256=sha(unbound)))
    prg.write_bytes(raw)
    (artifacts / 'lisp65.prg').write_bytes(C.PRG.from_elf(elf, bytes(raw), publication_dir=med))
    C.CAN.ARTIFACTS = artifacts
    _, geometry = C.CAN.build_boot_stage(elf, artifacts / 'profile')
    product = load(HERE / 'plane-price.json')['after_product']
    build_id = int(product['product_build_id_hex'], 16)
    packages = load(FINAL / 'media/runtime-receipt.json')['packages']
    assert len(packages) == 6 and {r['name'] for r in packages} == {r['name'] for r in authority_media['packages']}
    for row in packages:
        checked(row['manifest'])
        _, payload = C.L.F.measured_row(row['name'], row['name'], row['shelf'], ROOT / row['manifest']['path'],
            tuple(row['dependencies']), 1, 1, product_build_id=build_id)
        (artifacts / row['name']).write_bytes(payload)
    save(med / 'runtime-receipt.json', dict(status='PASS', ELF=bind(elf), families=families,
        boot_geometry=geometry, product_build_id=build_id, packages=packages))
    # The inherited cold delivery stager is not another product link.
    C.MED, C.ART, C.OUT, C.ELF = med, artifacts, HERE, elf
    C.run = lambda cmd: run(cmd, med / ('host-'+sha(str(cmd).encode())[:16]+'.log')).decode('latin1')
    C.M.ASM_CONTRACT_INCLUDE = med / 'stager-contract.inc'
    assembly = C.M.STAGER_S.read_text().replace(C.M.ASM_CONTRACT_INCLUDE_TOKEN,
        '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"')
    C.M.ASM_CONTRACT_INCLUDE_TOKEN = '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"'
    C.M.STAGER_S = med / 'cold-stager-chain.s'
    once(C.M.STAGER_S, assembly)
    C.M.run = lambda cmd, label: run(cmd, med / ('stager-'+sha(label.encode())[:16]+'.log')).decode('latin1')
    C.stager()
    result = pack_media(C, med, artifacts, before_raw, packages, build_id)
    result['plane_control'] = bind(med / 'plane-control.json')
    save(HERE / 'media.json', result)
    return result


def selftest():
    """Synthetic stage tests. A subprocess tripwire forbids product execution."""
    import tempfile
    from contextlib import ExitStack, redirect_stdout
    import io
    from dataclasses import asdict
    from types import SimpleNamespace as NS
    from unittest.mock import patch
    import elf_truth
    import runtime_overlay_bank as BANK
    import comfort_default_media as C
    import d81_persistence_fault as D
    tested = []
    def rejects(call):
        try:
            call()
        except (AssertionError, FileExistsError, BANK.OverlayBankError):
            return
        raise AssertionError('negative control survived')
    with tempfile.TemporaryDirectory(prefix='ide-exit-selftest-') as tmp, ExitStack() as stack:
        root = Path(tmp)
        here, build, final = root / 'receipts', root / 'product', root / 'final'
        for key, value in dict(ROOT=root, HERE=here, BUILD=build, FINAL=final).items():
            stack.enter_context(patch.dict(globals(), {key: value}))
        stack.enter_context(patch.object(subprocess, 'run', side_effect=AssertionError('selftest subprocess forbidden')))
        stack.enter_context(patch.object(subprocess, 'check_output', side_effect=AssertionError('selftest subprocess forbidden')))
        stack.enter_context(patch.dict(globals(), {'verify_ready': lambda **kw: {'authority': AUTH, 'base_native': {}}}))
        # Fixture insertion order is observable by the virtual disk emitter.
        original = root / 'suite.json'
        frozen = root / 'frozen.json'
        save_suite(frozen, {'disk_files': {'z-reserved': 'first', 'a-data': 'second'}, 'sources': []})
        ready = dict(suites={str(original): str(frozen)}, ide_suite=str(original), old_keymap='unused')
        def fake_emit(command, log):
            suite = load(command[-1])
            assert list(suite['disk_files']) == ['z-reserved', 'a-data']
            once(log, 'synthetic emission')
            return b''
        with patch.dict(globals(), {'run': fake_emit}):
            emit_ide(ready, {str(original): str(frozen)}, root / 'emission', 'candidate')
        tested.append('candidate emission fixture ordering (synthetic command boundary)')
        import c2_full_emission as F
        import c2_substitution_artifacts as SUB
        import c2_lite_v6_product_probe as V6
        emission_root = root / 'plane-emission'
        plane_root = emission_root / 'frozen'
        closure = []
        for suffix, raw in [('v6-semantics/bank2-static-code.bin', b'code'),
                            ('v6-semantics/initial.c2d-v6.bin', b'data'),
                            ('product/product-shelf-v4-direct.bin', b'shelf')]:
            path = plane_root / suffix
            once(path, raw); closure.append(dict(source=bind(path), restored=bind(path)))
        # emit_ide takes the restored original suite, just as the real probe does.
        once(original, frozen.read_bytes())
        closure.append(dict(source=bind(original), restored=bind(frozen)))
        manifests = []
        for name in ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc'):
            blob = emission_root / (name+'.blob'); once(blob, b'code')
            manifest = emission_root / (name+'.json'); save(manifest, dict(blob=str(blob)))
            manifests.append(str(manifest)); closure.append(dict(source=bind(blob), restored=bind(blob)))
        plane_ready = dict(ready, closure=closure, manifests=manifests)
        def fake_plane_emit(command, log):
            fake_emit(command, log)
            prefix = Path(command[command.index('--emit-artifacts')+1])
            literals = [0, [13, 1013]]
            if prefix.parent.name == 'candidate':
                literals[1] += [113, 1015]
            save(prefix.with_suffix('.manifest.json'), dict(entries=[dict(name='%ide-prefix-command',
                 literals=literals, blob_offset=0, length=4, lit_count=2)]))
            return b''
        def fake_product():
            data = b'shelf' + (b'!!!!' if SUB.BUILD.parent.name == 'candidate' else b'')
            once(SUB.BUILD / 'product-shelf-v4-direct.bin', data)
            return dict(product_build_id_hex='0x12345678', artifacts={'shelf': {'bytes': len(data)}})
        def fake_image(key, shelf, path):
            extra = b'!!!!' if key == 'ide' and Path(path).parent.name == 'candidate' else b''
            return NS(key=key, code=b'code', metadata=b'meta'+extra)
        with ExitStack() as emission_stack:
            emission_stack.enter_context(patch.dict(globals(), dict(HERE=emission_root / 'receipts',
                BUILD=emission_root / 'product', PLANE=plane_root, run=fake_plane_emit)))
            for module, key, value in [(SUB, 'BUILD', SUB.BUILD), (SUB, 'SPECS', SUB.SPECS),
                    (V6, 'PRODUCT_IDENTITY', V6.PRODUCT_IDENTITY), (V6, 'STATIC_CODE_BYTES', V6.STATIC_CODE_BYTES),
                    (SUB, 'build', fake_product), (F, 'emit_image', fake_image),
                    (V6, 'static_plane', lambda images: (NS(code=b'code', code_low=4, c2d=b'data'), {}))]:
                emission_stack.enter_context(patch.object(module, key, value))
            emitted = emit_planes(plane_ready)
            assert emitted['baseline_exact'] and emitted['total_growth'] == 4
            assert emitted['entries'][0]['literals_identical'] is False
        tested.append('complete dual emission, baseline reproduction, literal ownership and plane price')
        # Real generated-source projection: six CRCs in each array, two macros,
        # exactly 75 replay commands and no unrelated argument substitution.
        values = {}
        for side in ('baseline', 'candidate'):
            for name in ('SHELF.BIN', 'C2D.BIN', 'CODE.BIN'):
                raw = bytearray(256)
                struct.pack_into('<H', raw, 28, 32)
                if side == 'candidate':
                    raw[40] = 7
                once(build / 'plane' / side / name, raw)
                values[side, name] = bytes(raw)
        # Pre-media and delivered C2D have different, strictly checked geometry.
        control_build = root / 'plane-control'
        control_plane = root / 'frozen-control'
        control_closure, delivered = [], {}
        for name, suffix, size in (
                ('CODE.BIN', 'v6-semantics/bank2-static-code.bin', 16),
                ('SHELF.BIN', 'product/product-shelf-v4-direct.bin', 64),
                ('C2D.BIN', 'v6-semantics/initial.c2d-v6.bin', C.M.C2D_PREFIX_BYTES)):
            data = bytes([23]) * size
            path = control_plane / suffix
            once(path, data)
            control_closure.append(dict(source=bind(path), restored=bind(path)))
            once(control_build / 'plane/baseline' / name, data)
            delivered[name.encode()] = data
        delivered[b'CODE.BIN'] += b'native-tail'
        delivered[b'C2D.BIN'] += bytes(C.M.C2D_RESET_DOMAIN_BYTES-C.M.C2D_PREFIX_BYTES)
        with patch.dict(globals(), dict(BUILD=control_build, PLANE=control_plane)):
            control_ready = dict(closure=control_closure)
            assert media_plane_control(control_ready, delivered)['status'] == 'PASS'
            for name, offset in ((b'CODE.BIN', 0), (b'SHELF.BIN', 0),
                                 (b'C2D.BIN', 0), (b'C2D.BIN', -1)):
                broken = dict(delivered)
                data = bytearray(broken[name]); data[offset] ^= 1
                broken[name] = bytes(data)
                rejects(lambda: media_plane_control(control_ready, broken))
            broken = dict(delivered); broken[b'C2D.BIN'] = broken[b'C2D.BIN'][:-1]
            rejects(lambda: media_plane_control(control_ready, broken))
            path = control_build / 'plane/baseline/SHELF.BIN'
            path.write_bytes(b'wrong frozen emission')
            rejects(lambda: media_plane_control(control_ready, delivered))
        tested.append('frozen pre-media control; C2D padding, truncation and byte-drift rejection')
        source = here / 'native-inputs/generated.c'
        text = ''
        for name, file in (('shelf', 'SHELF.BIN'), ('c2d', 'C2D.BIN')):
            data = values['baseline', file]
            crcs = [BANK.crc16_ccitt_false(data[32+i*32:64+i*32]) for i in range(6)]
            text += 'c2_phase02a_'+name+'_crc16:\\n'+'\\n'.join(f'.short 0x{x:04x}' for x in crcs)+'\\n'
        once(source, text)
        commands = [['synthetic-cc', '-c', 'unchanged.c', '-DLISP65_C2_PRODUCT_BUILD_ID=0x01020304UL',
                     '-DLISP65_C2_PRODUCT_SHELF_BYTES=256UL', '-o', str(build.relative_to(root) / f'{i}.o')]
                    for i in range(75)]
        commands[29][2] = str(source.relative_to(root))
        save(here / 'baseline-command-proof.json', {'commands': commands})
        plane = dict(status='PASS', before_product=dict(product_build_id_hex='0x01020304', artifacts={'shelf': {'bytes': 256}}),
                     after_product=dict(product_build_id_hex='0x05060708', artifacts={'shelf': {'bytes': 260}}),
                     plane_deltas={'CODE.BIN': 0, 'SHELF.BIN': 4, 'C2D.BIN': 0}, total_growth=4,
                     artifacts=[])
        projected = derived_commands(dict(authority=AUTH, commands=bind(here / 'baseline-command-proof.json')), plane)
        assert len(projected) == 75
        assert projected[29][2] != commands[29][2]
        for i, (old, new) in enumerate(zip(commands, projected)):
            assert all(x == y or j in (3, 4) or (i == 29 and j == 2) for j, (x, y) in enumerate(zip(old, new)))
        assert all(len(r['before']) == len(r['after']) == 6 for r in load(here / 'derived-inputs.json')['crc_tables'])
        tested.append('derived native inputs and 75-command substitution')
        # Native price and physical inventory on a synthetic ELF layout. No
        # compiler, linker, readobj or objdump process can pass the tripwire.
        from elf_truth import Section, Symbol
        sections = [Section(i, n, addr, size, typ, ('SHF_ALLOC',), 0) for i, (n, addr, size, typ) in enumerate([
            ('.text', 0x2000, 24, 'SHT_PROGBITS'), ('.rodata', 0xb989, 3, 'SHT_PROGBITS'),
            ('.bss', 0xbff0, 8, 'SHT_NOBITS')])]
        symbols = [Symbol(0, '__bss_start', 0xbff0, 0, '', '', '.bss', 2),
                   Symbol(1, '__bss_end', 0xbff8, 0, '', '', '.bss', 2),
                   Symbol(2, 'c2_phase02a_shelf_crc16', 0x2000, 12, '', 'Object', '.text', 0),
                   Symbol(3, 'c2_phase02a_c2d_crc16', 0x200c, 12, '', 'Object', '.text', 0)]
        truth_pairs = []
        elfs = [final / 'wplto/resident-island-seed.prg.elf', build / 'wplto/resident-island-seed.prg.elf']
        derived = load(here / 'derived-inputs.json')
        for side, path in zip(('before', 'after'), elfs):
            data = b''.join(struct.pack('<6H', *row[side]) for row in derived['crc_tables'])
            raw = bytearray(512)
            struct.pack_into('<I', raw, 32, 64); struct.pack_into('<H', raw, 46, 40)
            struct.pack_into('<I', raw, 64+16, 256)
            raw[256:280] = data
            once(path, raw)
            truth = NS(sections=sections, symbols=symbols, relocations=[],
                       sections_by_name={s.name: s for s in sections},
                       symbols_by_name={s.name: [s] for s in symbols})
            truth.section = lambda name, t=truth: t.sections_by_name[name]
            truth.symbol = lambda name, t=truth: t.symbols_by_name[name][0]
            truth.section_bytes = lambda name, d=data: d if name == '.text' else bytes(3)
            truth_pairs.append(truth)
        save(here / 'plane-price.json', plane)
        save(build / 'seed.json', dict(commands_consumed=75, product_link_attempts=1, native={'elf': bind(elfs[1])}))
        with patch.object(elf_truth.ElfTruth, 'read', side_effect=lambda path, **kw: truth_pairs[elfs.index(path)]):
            assert price()['status'] == 'PASS'
            rejects(price)
            assert inventory()['unclassified_bytes'] == 0
        from dataclasses import replace
        bad_truth = copy.copy(truth_pairs[1])
        bad_truth.sections = [replace(v, bytes=v.bytes+1) if v.name == '.rodata' else v for v in sections]
        bad_truth.sections_by_name = {v.name: v for v in bad_truth.sections}
        bad_truth.section = lambda name: bad_truth.sections_by_name[name]
        bad_here = root / 'bad-price'
        save(bad_here / 'plane-price.json', plane)
        with patch.dict(globals(), {'HERE': bad_here}), patch.object(elf_truth.ElfTruth, 'read',
                side_effect=lambda path, **kw: truth_pairs[0] if path == elfs[0] else bad_truth):
            assert price()['status'] == 'HALT: NONZERO NATIVE PRICE'
        too_big = dict(plane, total_growth=65, plane_deltas={'CODE.BIN': 0, 'C2D.BIN': 0, 'SHELF.BIN': 65})
        bad_plane_here = root / 'bad-plane-price'
        save(bad_plane_here / 'plane-price.json', too_big)
        with patch.dict(globals(), {'HERE': bad_plane_here}), patch.object(elf_truth.ElfTruth, 'read',
                side_effect=lambda path, **kw: truth_pairs[elfs.index(path)]):
            rejects(price)
        assert classify_bytes(b'ab', b'ac', {1: (98, 99, 'derived')})['unclassified_bytes'] == 0
        assert classify_bytes(b'ab', b'ad', {1: (98, 99, 'derived')})['unclassified_bytes'] == 1
        assert classify_bytes(b'ab', b'abc', {})['unclassified_bytes'] == 1
        tested.append('native/plane price, write-once receipt, exhaustive inventory and foreign-byte rejection')
        # Exercise Seed claim/replay/stop behavior with all executable boundaries
        # replaced by pure synthetic operations. Actual command execution is forbidden.
        seed_build = root / 'synthetic-seed'
        consumed = []
        def fake_run(command, log):
            consumed.append(command)
            once(log, 'synthetic replay')
            return b''
        save(here / 'command-ready.json', {'synthetic': True})
        with patch.dict(globals(), dict(BUILD=seed_build, run=fake_run,
                emit_planes=lambda ready: plane, derived_commands=lambda ready, plane: projected,
                include_closure=lambda commands, ready: None)):
            with redirect_stdout(io.StringIO()):
                state = seed()
            assert state['commands_consumed'] == 75 and state['product_link_attempts'] == 1
            rejects(seed)
        assert consumed == projected
        tested.append('Seed one-attempt claim, serial 75-command replay, exactly one link claim, retry rejection')
        # Real runtime catalog CRC derivation and Comfort validator on synthetic
        # payloads. Corrupting a freshly rebound catalog must be rejected.
        specs = [BANK.SliceSpec(i, 'test'+str(i), '.test'+str(i), 'start'+str(i), 'end'+str(i), 'entry'+str(i),
                 BANK.FLAG_RUNTIME | BANK.FLAG_REUSABLE, 1, 0, 'entry') for i in range(2)]
        slices = [BANK.ExtractedSlice(s, 0xc200, 0xc210, 0xc200, bytes([s.id+1])*16) for s in specs]
        main, over, parsed = BANK.build_region_images(slices, profile_build_id=123,
            expected_vma=0xc200, max_slice_bytes=1792, format_version=4, main_source_base=0x30000, overflow_source_base=0x5bd00)
        value = dict(slices=[dict(asdict(r), section=specs[r.id].section, sha256=sha(slices[r.id].data)) for r in parsed.slices],
                     profile_build_id=123, policy=dict(common_vma=0xc200, max_slice_bytes=1792),
                     overflow_storage={}, storage={}, catalog={})
        a = NS(section_bytes=lambda name: slices[int(name[-1])].data)
        b = NS(section_bytes=lambda name: bytes([8+int(name[-1])])*16)
        regions = {0: bytearray(main), 1: bytearray(over)}
        assert rebind_family(C, 'boot', value, regions, a, b, elfs[1])['all_record_crcs']
        regions[0][26] ^= 1
        rejects(lambda: C.validate_family('boot', value, regions, a, b))
        tested.append('Comfort runtime media payload/record/directory/header CRC rebinding and stale-CRC rejection')
        # Six synthetic packages through the real shelf/index codecs, mutation
        # matrix, locator admission and whole-medium readback (no codec mocks).
        initial = D.seed_file(bytes(D.blank_image()), 'shelf.bin', b'old')
        med = root / 'media'; artifacts = med / 'artifacts'; artifacts.mkdir(parents=True)
        packages, old_rows = [], []
        for i in range(6):
            name = 'test'+str(i)
            blob = root / (name+'.blob')
            once(blob, bytes.fromhex('b5000000000000'))
            manifest = root / (name+'.json')
            save(manifest, dict(blob=str(blob), blob_sha256=sha(blob.read_bytes()), code_bytes=7,
                literal_nodes=[], literal_index=[], literal_patches=[],
                entries=[dict(name=name, blob_offset=0, length=7, lit_first=0, lit_count=0)]))
            row, payload = C.L.F.measured_row(name, name, name, manifest, (), 1, 1, product_build_id=123)
            initial = D.seed_file(initial, name, payload)
            slot, = [v for v in D.directory_slots(initial) if D.entry_name(v.record) == name.upper().encode()]
            row.update(track=slot.record[3], sector=slot.record[4])
            old_rows.append(row)
            _, successor = C.L.F.measured_row(name, name, name, manifest, (), 1, 1, product_build_id=456)
            once(artifacts / name, successor)
            packages.append(dict(name=name, shelf=name, manifest=bind(manifest), dependencies=[]))
        old_index = C.L.L65I.encode_index(old_rows)
        initial = D.seed_file(initial, 'l65index', old_index)
        domains = {}
        changed = replace_file(initial, 'shelf.bin', b'x'*99286, domains)
        assert D.visible_files(changed)[b'SHELF.BIN'] == b'x'*99286
        assert classify_bytes(initial, changed, domains)['unclassified_bytes'] == 0
        damaged = bytearray(changed)
        foreign = next(i for i in range(len(changed)) if i not in domains and initial[i] == changed[i])
        damaged[foreign] ^= 1
        assert classify_bytes(initial, damaged, domains)['unclassified_bytes'] == 1
        once(artifacts / 'shelf.bin', b'x'*99286); once(artifacts / 'l65index', old_index)
        result = pack_media(C, med, artifacts, initial, packages, 456)
        assert result['every_file_read_back'] and len(result['files']) == 8
        assert result['mutations']
        tested.append('six real package/index CRCs, mutation matrix, D81 >8 KiB growth, all-file readback and classified diff')
    return dict(status='PASS', synthetic_only=True, product_commands=0, stages=tested)


def main():
    global HERE
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['command-probe', 'seed', 'price', 'inventory', 'media'])
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--probe-output', type=Path, help='fresh budget-free probe receipt root; Seed always uses r5/seed')
    parser.add_argument('--media-output', type=Path, help='fresh media directory under build; preserves failed attempts')
    args = parser.parse_args()
    if args.media_output is not None:
        assert args.mode == 'media' and not args.selftest
        args.media_output = args.media_output.resolve()
        assert args.media_output.is_relative_to(ROOT / 'build') and not args.media_output.exists()
    if args.selftest:
        assert args.mode is None and args.probe_output is None
        result = selftest()
    else:
        assert args.mode is not None
        if args.probe_output is not None:
            assert args.mode == 'command-probe', 'custom root is probe-only'
            HERE = args.probe_output.resolve()
            assert HERE.is_relative_to(ROOT / 'build') and not HERE.exists()
        result = {'command-probe': command_probe, 'seed': seed, 'price': price,
                  'inventory': inventory, 'media': lambda: media(args.media_output)}[args.mode]()
    print(json.dumps(result, indent=2))
    if result['status'].startswith('HALT'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
