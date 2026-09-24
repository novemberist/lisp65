"""Close the one retained-callable repair Final against Seed 2, the exact-HEAD
source run and the existing Seed-2 medium; then seal the card's evidence.

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
STEM = 'retained-callable-repair-final-20260923'
H = ROOT/'build/retained-callable-repair-final-r1'
SEED_ELF = '815b60a5fb4baf405d5b8e14dac5ad9e593c9bf3f73877efc6b6f63499dc26a1'
SOURCE_HEAD = 'a6b827b5eee4db64d0dd04b00f22c0876a737030'
COPY_LIMIT = 200_000
NO_COPY = ('generated-product-sources', 'objects', 'setup-owned', 'world-data-derivation', 'generated-0')
ROOTS = ['build/retained-callable-repair-r2', 'build/retained-callable-repair-object-probe-r3',
         'build/retained-callable-repair-r2-link-preprobe-r1', 'build/retained-callable-repair-r2-e000-preprobe-r1',
         'build/retained-callable-repair-r2-capacity-seed-r1', 'build/retained-callable-repair-r2-seed-inventory-r1',
         'build/retained-callable-repair-r2-seed-inventory-r2', 'build/retained-callable-repair-product-r2',
         'build/retained-callable-repair-product-r2-preflight', 'build/retained-callable-repair-seed-medium-r2',
         'build/retained-callable-repair-r2-native-boot-r1', 'build/retained-callable-repair-r2-instrument-r1',
         'build/input-cost-natural-retained-callable-repair-r2', 'build/retained-callable-repair-r2-gc-equal-baseline-1',
         'build/retained-callable-repair-r2-gc-equal-candidate-1', 'build/retained-callable-repair-r2-usage-baseline-r1',
         'build/retained-callable-repair-r2-usage-candidate-r1', 'build/retained-callable-repair-r2-gates-lambda-r1',
         'build/retained-callable-repair-r2-gates-wipe-r1', 'build/retained-callable-repair-r2-gates-sweep-r1',
         'build/retained-callable-repair-r2-gates-sweep54-r1', 'build/retained-callable-repair-r2-gates-overflow-r1',
         'build/retained-callable-repair-r2-gates-overflow-baseline-r1',
         'build/retained-callable-repair-r2-gates-overflow-baseline-r2',
         'build/retained-callable-repair-check-source-r1', 'build/retained-callable-repair-source-qualification-r1',
         'build/retained-callable-repair-final-r1']
LOOSE = ['build/retained-callable-repair-r2-link-preprobe-r1.log', 'build/retained-callable-repair-r2-e000-preprobe-r1.log',
         'build/retained-callable-repair-r2-capacity-seed-r1.log', 'build/retained-callable-repair-r2-gc-pc-baseline-r1.txt',
         'build/retained-callable-repair-r2-gc-pc-candidate-r1.txt', 'build/retained-callable-repair-source-final-r1.log',
         'config/retained-callable-repair-seed.json', 'config/retained-callable-repair-r2-native/include-closure.json',
         'config/retained-callable-repair-r2-native/includes/c2-stream-v2-decoder.c', 'src/c2_product_runtime.c',
         'build/dirty-anchor-final-r3/wplto/lisp65-c2-substitution-linked.prg.elf',
         'build/dirty-anchor-seed-medium-r1/packed/hardware-sp-seed.d81',
         'tests/bytecode/dialect-v2/evidence/architecture-blocks/retained-callable-repair-halt-20260923.json']


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


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
    seed = load('config/retained-callable-repair-seed.json', inputs)
    assert seed['status'] == 'PASS: EXECUTED RETAINED-CALLABLE REPAIR SEED'
    for row in seed['inputs']:
        verify(row)
    final = load('build/retained-callable-repair-final-r1/final-identity.json', inputs)
    assert final['status'] == 'PASS' and final['ELF_byteidentical'] and final['budget'] == dict(seed=1, final=1, link=1)
    for row in final['seed'] + final['final']:
        verify(row)
    for old, new in zip(final['seed'][:3], final['final'][:3]):
        assert old['sha256'] == new['sha256']
    assert final['final'][1]['sha256'] == SEED_ELF
    assert verify(final['Bank2_seed'])['sha256'] == verify(final['Bank2_final'])['sha256']
    attempt = load('build/retained-callable-repair-final-r1/final-attempt.json', inputs)
    assert attempt == dict(calls=['reused-seed', 'final'], seed_rebuilds=0, final=1)
    invocation = load('build/retained-callable-repair-final-r1/final-invocation.json', inputs)
    assert invocation['budget'] == dict(seed=0, final=1, link=1)
    consumed = load('build/retained-callable-repair-final-r1/final-command-consumption.json', inputs)
    assert consumed['status'] == 'PASS' and consumed['commands_consumed'] == 75
    verify(consumed['admission'])
    source = load('build/retained-callable-repair-check-source-r1/receipt.json', inputs)
    assert source['target'] == 'make -k check-source'
    assert source['exit_code'] == source['changed_protected_files'] == 0
    assert not source['changed_files'] and not source['changed_sealed_artifacts']
    assert source['head_before'] == source['head_after'] == SOURCE_HEAD
    verify(source['log'])
    assert load('build/retained-callable-repair-source-qualification-r1/full-source-run.json', inputs) == source
    medium = load('build/retained-callable-repair-seed-medium-r2/packed-receipt.json', inputs)
    extended = load('build/retained-callable-repair-seed-medium-r2/extended-resident.json', inputs)
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
    gc = load('build/retained-callable-repair-r2/gc-qualification.json', inputs)
    assert gc['forced_delta'] == 0 and gc['warmup']['delta'] == 0
    inputs.append(bind(Path(__file__)))
    value = dict(status='PASS: RETAINED-CALLABLE REPAIR FINAL', binding='d3d5044b',
                 rebinding='2026-09-23 reviewer decision: member 1 withdrawn, 2/1/1',
                 authority='dafc1f47', runtime_member_authority='e0be22c1',
                 source_head=SOURCE_HEAD, source_exit=0, source_seconds=source['seconds'],
                 protected_files=source['protected_files'], sealed_artifacts=source['sealed_artifacts_read_only'],
                 final=final, compiler_commands_consumed=75, existing_medium=medium['medium'],
                 medium_reuse='Final PRG, ELF, LTO object and Bank-2 plane equal Seed 2; carrier payload and '
                              'CODE.BIN read back byte-exactly from the existing Seed-2 D81; no new pack or build.',
                 carrier=carriers[0], packed_code=code_files[0], raw_plane_prefix_bytes=len(raw_plane),
                 packed_code_bytes=len(packed_plane),
                 budget=dict(seed=2, final=1, product_link=1), halted_seed='41861dd7 (Seed 1, gate-3 halt)',
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
    selected.update((ROOT/'tools/host-lisp').glob('retained_callable_repair_*.py'))
    selected.update(ROOT/p for p in LOOSE)
    intermediate = []
    # Earlier revisions of the gates driver ran lambda/wipe/sweep (a) and the
    # first, asserting overflow control (b); both are reconstructed
    # byte-exactly next to the card and bound instead of the live file.
    historical = {
        '6d1721f7c0fc1122': 'build/retained-callable-repair-r2/gates-driver-as-run-a.py',
        'cf75c83e06a29445': 'build/retained-callable-repair-r2/gates-driver-as-run-b.py',
        '8fe95d9ed40cc4c5': 'build/retained-callable-repair-r2/inventory-driver-as-run-r1.py',
        'b693ea7298eca89a': 'build/retained-callable-repair-r2/final-seal-driver-as-run-1.py'}
    superseded = []

    def verify(v):
        if isinstance(v, dict):
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str) \
                    and (v['path'].endswith('retained_callable_repair_r2_gates.py')
                         or v['path'].endswith('retained_callable_repair_final_seal.py')
                         or v['path'].endswith('retained_callable_repair_r2_inventory.py')) \
                    and v['sha256'][:16] in historical:
                actual = bind(ROOT/historical[v['sha256'][:16]])
                assert actual['sha256'] == v['sha256']
                superseded.append(dict(bound=v, reconstructed=actual))
                v = {k: x for k, x in v.items() if k not in ('path', 'sha256')}
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str):
                p = (ROOT/v['path']).resolve()
                if p.is_file() and p.is_relative_to(ROOT) and 'system-sd.img' != p.name:
                    actual = bind(p)
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
            if data is not None and rel.parts[1] != 'retained-callable-repair-check-source-r1':
                verify(data)
            if p.stat().st_size <= COPY_LIMIT and not any(x in rel.parts for x in NO_COPY):
                dest = ARCH/STEM/rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                assert not dest.exists()
                shutil.copyfile(p, dest)
                copies.append(bind(dest))
        row = bind(p)
        closure_rows[row['path']] = row
    result = dict(status=value['status'], binding='d3d5044b', authority='dafc1f47',
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
    import sys
    if sys.argv[1:] == ['seal-existing-closure']:
        value = json.loads((H/'closure.json').read_text())
        assert value['status'] == 'PASS: RETAINED-CALLABLE REPAIR FINAL'
        for row in value['inputs']:
            if row['path'] == 'tools/host-lisp/retained_callable_repair_final_seal.py':
                # The closure was written by the first revision of this tool
                # (its seal step then stopped on the gates-driver revision);
                # that revision is reconstructed byte-exactly.
                row = dict(row, path='build/retained-callable-repair-r2/final-seal-driver-as-run-1.py')
            assert bind(ROOT/row['path'])['sha256'] == row['sha256'], row['path']
        seal(value)
    else:
        seal(closure())
