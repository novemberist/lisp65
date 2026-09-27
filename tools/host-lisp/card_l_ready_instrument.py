"""Card L Seed ready observer rebind; only histogram coordinates change. No product build."""
import json
import shutil
import subprocess
from pathlib import Path

import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/card-l-r1/ready-instrument.json'
PARENT = ROOT/'build/nested-error-recovery-r1/ready-instrument.json'
SOURCE = ROOT/'build/nested-error-recovery-ready-instrument-r1/xemu'
BUILD = ROOT/'build/card-l-ready-instrument-r1'
WORLDS = [('baseline', 'build/nested-error-recovery-seed-medium-r1'),
          ('candidate', 'build/card-l-seed-medium-r1')]


def world(role, path):
    receipt = ROOT/path/'packed-receipt.json'
    if receipt.exists():
        packed = json.loads(receipt.read_text())
    else:
        assert role == 'candidate'
        seed = json.loads((ROOT/'build/card-l-r1/instrument-seed.json').read_text())['worlds'][0]
        packed = dict(elf=seed['ELF'], medium=seed['medium'])
        print('Candidate packed-receipt.json absent: deriving world fields directly from Seed ELF and medium SHA-256.')
    elf = N.checked_binding(packed['elf'])
    N.checked_binding(packed['medium'])
    t = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)

    def code(name, size=None):
        s = t.symbol(name)
        sec = t.section(s.section)
        return s.value, t.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+(size or s.bytes)]
    main, signature = code('_start', 16)
    entry, raw = code('c2_kernal_input_take')
    assert raw[0] == 0xaa
    return dict(role=role, ELF=packed['elf'], medium=packed['medium'], entry=entry, paused_pc=entry+1,
                entry_code=raw.hex(), main=main, signature=signature.hex(),
                vm_callprim=t.symbol('vm_callprim').value)


def main():
    assert not OUT.exists() and not BUILD.exists()
    parent = json.loads(PARENT.read_text())
    prior = next(w for w in parent['worlds'] if w['role'] == 'candidate')
    baseline, candidate = [world(r, p) for r, p in WORLDS]
    for key in ('entry', 'paused_pc', 'entry_code', 'main', 'signature', 'vm_callprim'):
        assert baseline[key] == prior[key], key
    for key in ('entry', 'paused_pc', 'entry_code', 'main', 'signature'):
        assert candidate[key] == baseline[key], key
    inventory_path = ROOT/'build/card-l-r1/inventory-r5/inventory.json'
    inventory = json.loads(inventory_path.read_text())
    assert inventory['status'] == 'PASS'
    address_map = json.loads((inventory_path.parent/'codegen-function-equivalence.json').read_text())
    def rows(value):
        if isinstance(value, dict):
            yield value
            for v in value.values(): yield from rows(v)
        elif isinstance(value, list):
            for v in value: yield from rows(v)
    placement = next(r for r in rows(address_map) if r.get('function') == 'vm_callprim')
    assert (baseline['vm_callprim'], candidate['vm_callprim']) == (placement['before_address'], placement['after_address'])
    assert inventory['ELFs'][1]['sha256'] == candidate['ELF']['sha256']
    BUILD.mkdir()
    dest = BUILD/'xemu'
    shutil.copytree(SOURCE, dest)
    cpu = (SOURCE/'xemu/cpu65.c').read_text()
    old = f"dwx_pc_init(&dwx_histogram, {baseline['main']}, {baseline['vm_callprim']});"
    new = f"dwx_pc_init(&dwx_histogram, {candidate['main']}, {candidate['vm_callprim']});"
    assert cpu.count(old) == 1
    changed = cpu.replace(old, new)
    (dest/'xemu/cpu65.c').write_text(changed)
    command = parent['build_command'][:]
    command[command.index('-C')+1] = str(dest/'targets/mega65')
    with (BUILD/'build.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    changed_files, same = [], 0
    for p in SOURCE.rglob('*'):
        if not p.is_file() or p.suffix not in ('.c', '.h', '.s'):
            continue
        other = dest/p.relative_to(SOURCE)
        assert other.is_file()
        if p.read_bytes() == other.read_bytes():
            same += 1
        else:
            changed_files.append(p.relative_to(SOURCE).as_posix())
    assert sorted(p for p in changed_files if not p.startswith('build/objs/')) == ['xemu/cpu65.c'], changed_files
    assert all(p in ('xemu/cpu65.c', 'build/objs/m-native-mega65-xmega65--make-buildinfo.c') for p in changed_files)
    baseline['binary'] = prior['binary']
    candidate['binary'] = N.bind(dest/'build/bin/xmega65.native')
    value = dict(authority='67133afb', binding='Card L Seed 2026-09-25', parent=N.bind(PARENT), worlds=[baseline, candidate],
                 binary=prior['binary'], unchanged_sources=same,
                 changed_sources=[N.bind(dest/p) for p in changed_files],
                 replacement=dict(before=old, after=new), driver=N.bind(Path(__file__)), build_command=command,
                 resident_identity=N.bind(inventory_path),
                 observer_builds=1, product_builds=0,
                 claim='Only the ELF-derived vm_callprim histogram coordinate changed: +145 by the '
                       'proved function placement map, despite net text growth +13; guest CPU/DMA cycles unchanged.')
    value['candidate_world_derivation'] = 'No packed-receipt.json: fields derived from Seed ELF and verified medium SHA-256.'
    value['address_delta'] = candidate['vm_callprim']-baseline['vm_callprim']
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    from nested_error_recovery_lanes import cost_config
    for w in (baseline, candidate):
        w['cost_config'] = cost_config(N.checked_binding(w['ELF']))
    lanes = dict(value, worlds=[baseline, candidate], binary=candidate['binary'],
                 claim='2.4.0 Final and Card L Seed; per-world ELF-derived cost config and coordinate-bound observer binary.')
    (OUT.parent/'instrument-lanes.json').write_text(json.dumps(lanes, indent=2)+'\n')
    print('READY OBSERVER REBOUND', same, changed_files, old, '->', new)


if __name__ == '__main__':
    main()
