"""Ready-instrument receipt for repair-Final-vs-Seed GC; rebinds the PC observer to the Seed.

No product build.  The baseline world is the accepted repair Final with the
observer it was measured with (build/dirty-anchor-ready-instrument-r1, whose
constants the repair card re-read as identical).  The candidate observer is
that observer's source copied unchanged except the ELF-derived
dwx_pc_init(main, vm_callprim) constants and the _start signature (method of
build/diet-card-1-r1/ready-instrument.py): the Seed moves vm_callprim by the
ordinary-text growth, _start and the E000 entry do not move.  The build
command is the parent observer's own.  Guest CPU/DMA cycle calculation is
unchanged; only host-side histogram coordinates change.
"""
import json
import shutil
import subprocess
from pathlib import Path

import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/nested-error-recovery-r1/ready-instrument.json'
PARENT = ROOT/'build/retained-callable-repair-r2/ready-instrument.json'
SOURCE = ROOT/'build/dirty-anchor-ready-instrument-r1/xemu'
BUILD = ROOT/'build/nested-error-recovery-ready-instrument-r1'
WORLDS = [('baseline', 'build/retained-callable-repair-seed-medium-r2'),
          ('candidate', 'build/nested-error-recovery-seed-medium-r1')]


def world(role, path):
    packed = json.loads((ROOT/path/'packed-receipt.json').read_text())
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
    inventory = json.loads((ROOT/'build/nested-error-recovery-seed-inventory-r1/inventory.json').read_text())
    assert inventory['status'].startswith('PASS')
    assert candidate['vm_callprim'] == baseline['vm_callprim'] + inventory['address_map']['delta']
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
    command = json.loads((ROOT/'build/dirty-anchor-card-r1/ready-instrument.json').read_text())['build_command'][:]
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
    value = dict(authority='90b5f9f2', binding='44c021ee', parent=N.bind(PARENT), worlds=[baseline, candidate],
                 binary=prior['binary'], unchanged_sources=same,
                 changed_sources=[N.bind(dest/p) for p in changed_files],
                 replacement=dict(before=old, after=new), driver=N.bind(Path(__file__)), build_command=command,
                 resident_identity=N.bind(ROOT/'build/nested-error-recovery-seed-inventory-r1/inventory.json'),
                 observer_builds=1, product_builds=0,
                 claim='Only the ELF-derived vm_callprim histogram coordinate changed (address drift by the '
                       'ordinary-text growth); guest CPU/DMA cycle calculation unchanged.')
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print('READY OBSERVER REBOUND', same, changed_files, old, '->', new)


if __name__ == '__main__':
    main()
