"""Write-once host closure over existing carrier artifacts; never a producer."""
import hashlib
import json
from pathlib import Path
import legacy_ide_delivery as MEDIA
import slice_capacity_preflight as CAPACITY

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks/put-kit-final.json'


def bind(path):
    path = ROOT / path
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def verify(row):
    actual = bind(row['path'])
    assert actual['sha256'] == row['sha256'], row['path']
    if 'bytes' in row:
        assert actual['bytes'] == row['bytes'], row['path']
    return actual


def main():
    inputs = []

    def load(path):
        inputs.append(bind(path))
        return json.loads((ROOT / path).read_text())

    seed = load('config/put-kit-seed.json')
    assert seed['status'] == 'PASS: EXECUTED PUT-KIT SEED'
    for row in seed['inputs']:
        verify(row)
    final = load('build/put-kit-r4/final-identity.json')
    assert final['status'] == 'PASS' and final['ELF_byteidentical']
    for row in final['seed'] + final['final']:
        verify(row)
    # Raw linked PRG and LTO object, not merely ELF, must also match.
    for old, new in zip(final['seed'][:3], final['final'][:3]):
        assert old['sha256'] == new['sha256']
    attempt = load('build/put-kit-r4/final-attempt.json')
    assert attempt == dict(calls=['reused-seed', 'final'], seed_rebuilds=0, final=1)
    load('build/put-kit-r4/final-invocation.json')
    source = load('build/put-kit-source-qualification-r2/receipt.json')
    assert source['exit_code'] == 0 and source['changed_protected_files'] == 0
    assert not source['changed_files'] and not source['changed_sealed_artifacts']
    assert source['head_before'] == source['head_after']
    verify(source['log'])
    alias = load('build/put-kit-source-qualification-r1/full-source-run.json')
    assert alias == source  # r1's failed receipt remains separate and unchanged.
    load('build/put-kit-source-qualification-r1/receipt.json')

    medium = load('build/put-kit-seed-medium-r1/packed-receipt.json')
    extended = load('build/put-kit-seed-medium-r1/extended-resident.json')
    assert extended['status'] == 'PASS'
    for row in [medium['medium'], medium['elf'], *medium['artifacts'].values(),
                extended['elf'], extended['prefix'], extended['extended']]:
        verify(row)
    assert medium['elf']['sha256'] == final['final'][1]['sha256']
    assert extended['elf']['sha256'] == final['final'][1]['sha256']
    # The inherited producer-input inventory names the published prefix;
    # the extent adapter substitutes its derived artifact at descriptor entry.
    assert medium['artifacts']['c2-resident-prg']['sha256'] == extended['prefix']['sha256']
    files = MEDIA.inventory((ROOT / medium['medium']['path']).read_bytes())
    payload = (ROOT / extended['extended']['path']).read_bytes()
    carrier_files = [name for name, row in files.items() if row['data'] == payload]
    assert len(carrier_files) == 1, 'extended PRG must be read back from the medium'
    file_bindings = {name: dict(bytes=len(row['data']),
                               sha256=hashlib.sha256(row['data']).hexdigest())
                     for name, row in files.items()}
    assert extended['extent_delta'] == 2546

    boot = {}
    for role, path in (
        ('predecessor', 'build/boot-only-carrier-native-boot-r1/capture-r1/boot.txt'),
        ('candidate', 'build/put-kit-native-boot-r2/capture-r1/boot.txt'),
    ):
        inputs.append(bind(path))
        events = {}
        for line in (ROOT / path).read_text().splitlines():
            fields = line.split()
            if fields and fields[0] == 'E':
                events.setdefault(int(fields[1]), int(fields[2]))
        boot[role] = {name: dict(cycles=events[event] - events[0],
                                seconds=(events[event] - events[0]) / 40500000)
                      for name, event in [('stager', 4), ('initializing', 10), ('banner', 11)]}
    vm = load('build/put-kit-vm-lanes-r1/receipt.json')
    assert vm['status']=='PASS' and max(vm['ratios'].values())<=1.02
    capacities = {}
    for family in ('session','boot'):
        manifest = load(f'build/put-kit-seed-medium-r1/materialized/runtime-overlays-{family}-final.json')
        capacities[family]=CAPACITY.family_report(manifest)
    assert [capacities['session'][f'region{n}']['free'] for n in range(3)]==[1351,140,872]
    for path in ('tools/host-lisp/put_kit_final.py','build/put-kit-r4/final-expanded-driver.py',
                 'build/put-kit-r4/final-preflight.json'):
        inputs.append(bind(path))
    result = dict(
        format='lisp65-put-kit-final-v1',
        status='PASS: HOST CLOSED; DEVICE NOT CONTACTED', authority='3bd13625',
        inputs=inputs, seed_qualification=seed,
        final_identity=final, medium=verify(medium['medium']),
        medium_files=file_bindings, extended_PRG_filename=carrier_files[0],
        medium_promotion='Existing Seed measurement bytes adopted after Final identity; no repack or replacement stager.',
        source_qualification=source, boot_ledger=boot, capacities=capacities, vm_lanes=vm,
        boot_gain_seconds=boot['predecessor']['banner']['seconds']-boot['candidate']['banner']['seconds'],
        budget=dict(seed=1, final=1, link=1, device_contacts=0),
        boundaries=[
            'Native lifetime capture is normal boot, not exhaustive native error injection.',
            'Index lifetime and abort admission are compositional source and host-replay checks, not exhaustive native fault injection.',
            'GC first raw pair and exact PC-instrumented pair are both retained; no new tolerance.',
            'No new user-code recovery, image-slot reclamation or device acceptance is claimed.',
        ],
    )
    raw = json.dumps(result, indent=2) + '\n'
    if OUT.exists():
        assert OUT.read_text() == raw, 'never replace a final seal'
    else:
        OUT.write_text(raw)
    print(json.dumps(dict(status=result['status'], seal=bind(OUT), boot=boot), indent=2))


if __name__ == '__main__':
    main()
