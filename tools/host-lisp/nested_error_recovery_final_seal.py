"""Close the one nested-error recovery Final against the Seed, the exact-HEAD
source run and the existing Seed medium; then seal the card's evidence.

Read-only on product artifacts: no compiler, linker, pack or emulator.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import legacy_ide_delivery as MEDIA

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'nested-error-recovery-final-20260924'
H = ROOT/'build/nested-error-recovery-final-r1'
SEED_ELF = '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
SOURCE_HEAD = '6f3166b6b94661326a51ff8458afa4e086dd9c6f'
COPY_LIMIT = 200_000
NO_COPY = ('generated-product-sources', 'objects', 'setup-owned', 'world-data-derivation', 'generated-0')
ROOTS = ['build/nested-error-recovery-r1', 'build/nested-error-recovery-link-preprobe-r1',
         'build/nested-error-recovery-e000-preprobe-r1', 'build/nested-error-recovery-capacity-r1',
         'build/nested-error-recovery-capacity-seed-r1', 'build/nested-error-recovery-seed-inventory-r1',
         'build/nested-error-recovery-product-r1', 'build/nested-error-recovery-product-r1-preflight',
         'build/nested-error-recovery-seed-medium-r1', 'build/nested-error-recovery-native-boot-r1',
         'build/nested-error-recovery-instrument-r1', 'build/input-cost-natural-nested-error-recovery-r1',
         'build/nested-error-recovery-ready-instrument-r1',
         'build/nested-error-recovery-gc-equal-baseline-1', 'build/nested-error-recovery-gc-equal-candidate-1',
         'build/nested-error-recovery-gates-nested-r1', 'build/nested-error-recovery-gates-depth2-r1',
         'build/nested-error-recovery-gates-nested-g1', 'build/nested-error-recovery-gates-depth2-g1',
         'build/nested-error-recovery-gates-normalpath-g1', 'build/nested-error-recovery-gates-overcap-g1',
         'build/nested-error-recovery-gates-cumulative-g1', 'build/nested-error-recovery-reg-lambda-r1',
         'build/nested-error-recovery-reg-wipe-r1', 'build/nested-error-recovery-reg-sweep-r1',
         'build/nested-error-recovery-reg-sweep54-r1', 'build/nested-error-recovery-usage-baseline-r1',
         'build/nested-error-recovery-usage-candidate-r1',
         'build/nested-error-recovery-check-source-r1', 'build/nested-error-recovery-source-qualification-r1',
         'build/nested-error-recovery-final-r1']
LOOSE = ['build/nested-error-recovery-link-preprobe-r1.log', 'build/nested-error-recovery-e000-preprobe-r1.log',
         'build/nested-error-recovery-capacity-r1.log', 'build/nested-error-recovery-capacity-seed-r1.log',
         'build/nested-error-recovery-gc-pc-baseline-r1.txt', 'build/nested-error-recovery-gc-pc-candidate-r1.txt',
         'build/nested-error-recovery-source-final-r1.log',
         'config/nested-error-recovery-seed.json', 'config/retained-callable-repair-r2-native/include-closure.json',
         'config/retained-callable-repair-r2-native/includes/c2-stream-v2-decoder.c', 'src/c2_product_runtime.c',
         'build/retained-callable-repair-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf',
         'build/retained-callable-repair-seed-medium-r2/packed/hardware-sp-seed.d81',
         'tests/bytecode/dialect-v2/evidence/architecture-blocks/nested-error-recovery-halt-20260923.json']
# Tracked documents bound by receipts at an earlier committed version (the
# plan gains entries while the card runs): accepted when equal to a committed
# blob of the same path; recorded.
TRACKED = ('docs/planning/post-2.3.0-plan.md', 'docs/planning/nested-error-recovery-halt-report.md')


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def committed(row):
    """True when the bound SHA equals the path's blob at one of its commits."""
    revs = subprocess.check_output(['git', 'rev-list', 'HEAD', '-n', '40', '--', row['path']],
                                   cwd=ROOT, text=True).split()
    return any(hashlib.sha256(subprocess.check_output(['git', 'show', r+':'+row['path']], cwd=ROOT)).hexdigest()
               == row['sha256'] for r in revs)


def load(path, inputs):
    p = ROOT/path
    inputs.append(bind(p))
    return json.loads(p.read_text())


def closure():
    inputs = []

    def verify(row):
        actual = bind(ROOT/row['path'])
        assert actual['sha256'] == row['sha256'], row['path']
        if 'bytes' in row:
            assert actual['bytes'] == row['bytes'], row['path']
        return actual
    seed = load('config/nested-error-recovery-seed.json', inputs)
    assert seed['status'] == 'PASS: EXECUTED NESTED-ERROR RECOVERY SEED'
    for row in seed['inputs']:
        if row['path'] in TRACKED and bind(ROOT/row['path'])['sha256'] != row['sha256']:
            assert committed(row), row['path']
            continue
        verify(row)
    final = load('build/nested-error-recovery-final-r1/final-identity.json', inputs)
    assert final['status'] == 'PASS' and final['ELF_byteidentical'] and final['budget'] == dict(seed=1, final=1, link=1)
    for row in final['seed'] + final['final']:
        verify(row)
    for old, new in zip(final['seed'][:3], final['final'][:3]):
        assert old['sha256'] == new['sha256']
    assert final['final'][1]['sha256'] == SEED_ELF
    assert verify(final['Bank2_seed'])['sha256'] == verify(final['Bank2_final'])['sha256']
    attempt = load('build/nested-error-recovery-final-r1/final-attempt.json', inputs)
    assert attempt == dict(calls=['reused-seed', 'final'], seed_rebuilds=0, final=1)
    invocation = load('build/nested-error-recovery-final-r1/final-invocation.json', inputs)
    assert invocation['budget'] == dict(seed=0, final=1, link=1)
    consumed = load('build/nested-error-recovery-final-r1/final-command-consumption.json', inputs)
    assert consumed['status'] == 'PASS' and consumed['commands_consumed'] == 75
    verify(consumed['admission'])
    source = load('build/nested-error-recovery-check-source-r1/receipt.json', inputs)
    assert source['target'] == 'make -k check-source'
    assert source['exit_code'] == source['changed_protected_files'] == 0
    assert not source['changed_files'] and not source['changed_sealed_artifacts']
    assert source['head_before'] == source['head_after'] == SOURCE_HEAD
    verify(source['log'])
    assert load('build/nested-error-recovery-source-qualification-r1/full-source-run.json', inputs) == source
    medium = load('build/nested-error-recovery-seed-medium-r1/packed-receipt.json', inputs)
    extended = load('build/nested-error-recovery-seed-medium-r1/extended-resident.json', inputs)
    assert extended['status'] == 'PASS'
    for row in [medium['medium'], medium['elf'], *medium['artifacts'].values(),
                extended['elf'], extended['prefix'], extended['extended']]:
        verify(row)
    assert medium['elf']['sha256'] == extended['elf']['sha256'] == final['final'][1]['sha256']
    packed_plane = (ROOT/medium['artifacts']['c2-bank2-static-code-plane']['path']).read_bytes()
    raw_plane = (ROOT/final['Bank2_final']['path']).read_bytes()
    assert packed_plane[:len(raw_plane)] == raw_plane
    assert medium['artifacts']['c2-resident-prg']['sha256'] == extended['prefix']['sha256']
    files = MEDIA.inventory((ROOT/medium['medium']['path']).read_bytes())
    payload = (ROOT/extended['extended']['path']).read_bytes()
    carriers = [name for name, row in files.items() if row['data'] == payload]
    code_files = [name for name, row in files.items() if row['data'] == packed_plane]
    assert len(carriers) == 1 and len(code_files) == 1
    gc = load('build/nested-error-recovery-r1/gc-qualification.json', inputs)
    c = gc['collections']
    assert (c['warmup']['measured_delta'], c['forced']['measured_delta'], c['forced']['expected_placement_delta']) == (2905, 2641, 2751)
    assert all(x['fully_attributed'] for x in c.values())
    gates = load('build/nested-error-recovery-r1/gate-analysis.json', inputs)
    assert gates['status'] == 'PASS: GATES 1-4; GATE 5 BATCHED DEVICE ROW'
    inputs.append(bind(Path(__file__)))
    value = dict(status='PASS: NESTED-ERROR RECOVERY FINAL', binding='44c021ee',
                 decision='eaf59c62: GC placement accepted as named cost (+2,905 natural, +2,641 forced measured, '
                          '+2,751 forced placement expected); Seed continues',
                 authority='90b5f9f2',
                 source_head=SOURCE_HEAD, source_exit=0, source_seconds=source['seconds'],
                 protected_files=source['protected_files'], sealed_artifacts=source['sealed_artifacts_read_only'],
                 final=final, compiler_commands_consumed=75, existing_medium=medium['medium'],
                 medium_reuse='Final PRG, ELF, LTO object and Bank-2 plane equal the Seed; carrier payload and '
                              'CODE.BIN read back byte-exactly from the existing Seed D81; no new pack or build.',
                 carrier=carriers[0], packed_code=code_files[0], raw_plane_prefix_bytes=len(raw_plane),
                 packed_code_bytes=len(packed_plane),
                 budget=dict(seed=1, final=1, product_link=1, replacement_seed=0),
                 gate5='RUN/STOP not injectable on the host; batched device row',
                 device_contacts=0, inputs=inputs)
    p = H/'closure.json'
    assert not p.exists()
    p.write_text(json.dumps(value, indent=2)+'\n')
    return value


def seal(value):
    target = ARCH/(STEM+'.json')
    assert not target.exists()
    selected, closure_rows, copies, skipped = set(), {}, [], 0
    for root in ROOTS:
        for p in (ROOT/root).rglob('*'):
            if p.is_file() and not p.is_symlink():
                parts = p.relative_to(ROOT).parts
                if p.name == 'system-sd.img' or 'generated-0' in parts or 'xdg-data' in parts \
                        or 'xdg-config' in parts or 'xdg-run' in parts or 'ssh' in parts \
                        or (len(parts) > 2 and parts[2] == 'observer'):
                    skipped += 1
                    continue
                selected.add(p.resolve())
    selected.update((ROOT/'tools/host-lisp').glob('nested_error_recovery_*.py'))
    selected.update(ROOT/p for p in LOOSE)
    intermediate = []
    # Earlier revisions of the gates driver ran lambda/wipe/sweep (a) and the
    # first, asserting overflow control (b); both are reconstructed
    # byte-exactly next to the card and bound instead of the live file.
    # The two post-halt diagnostic rows ran the gates driver as committed in
    # 62acee68; that revision is reconstructed byte-exactly and bound instead.
    historical = {'5d02288a12eac284': 'build/nested-error-recovery-r1/gates-driver-as-run-diagnostic.py'}
    at_commit = []
    superseded = []

    def verify(v):
        if isinstance(v, dict):
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str) \
                    and v['path'].endswith('nested_error_recovery_gates.py') \
                    and v['sha256'][:16] in historical:
                actual = bind(ROOT/historical[v['sha256'][:16]])
                assert actual['sha256'] == v['sha256']
                superseded.append(dict(bound=v, reconstructed=actual))
                v = {k: x for k, x in v.items() if k not in ('path', 'sha256')}
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str):
                p = (ROOT/v['path']).resolve()
                if p.is_file() and p.is_relative_to(ROOT) and 'system-sd.img' != p.name:
                    actual = bind(p)
                    if actual['sha256'] != v['sha256'] and actual['path'] in TRACKED:
                        assert committed(dict(v, path=actual['path'])), v['path']
                        at_commit.append(dict(v))
                        v = dict(v, sha256=actual['sha256'])
                    assert actual['sha256'] == v['sha256'], v['path']
                    closure_rows[actual['path']] = actual
            for k, child in v.items():
                if k == 'medium_before_boot_stamp':
                    intermediate.append({k: child})
                    continue
                verify(child)
        elif isinstance(v, list):
            for child in v:
                verify(child)
    for p in sorted(selected):
        rel = p.relative_to(ROOT)
        if p.suffix == '.json' and rel.parts[0] == 'build':
            try:
                data = json.loads(p.read_text())
            except ValueError:
                data = None
            if data is not None and rel.parts[1] != 'nested-error-recovery-check-source-r1':
                verify(data)
            if p.stat().st_size <= COPY_LIMIT and not any(x in rel.parts for x in NO_COPY):
                dest = ARCH/STEM/rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                assert not dest.exists()
                shutil.copyfile(p, dest)
                copies.append(bind(dest))
        row = bind(p)
        closure_rows[row['path']] = row
    result = dict(status=value['status'], binding='44c021ee', authority='90b5f9f2', decision='eaf59c62',
                  bound_at_committed_version=at_commit,
                  source_head=SOURCE_HEAD,
                  sealed_at_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  final_ELF=SEED_ELF, closure=bind(H/'closure.json'), budget=value['budget'],
                  inputs=sorted(closure_rows.values(), key=lambda x: x['path']), receipt_copies=copies,
                  intermediate_bindings=intermediate, superseded_driver_bindings=superseded,
                  excluded=dict(rule='mutable SD scratch, sealed-run private generated/xdg/ssh trees, copied Xemu '
                                     'observer source tree', count=skipped),
                  device_contacts=0)
    target.write_text(json.dumps(result, indent=2)+'\n')
    print('PASS:', len(closure_rows), 'verified bindings;', len(copies), 'receipt copies')


if __name__ == '__main__':
    seal(closure())
