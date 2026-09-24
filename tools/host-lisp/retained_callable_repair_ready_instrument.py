"""Ready-instrument receipt for anchor-vs-repair lanes; reuses the anchor's observer binary.

No observer or product build.  The anchor card's candidate observer
(build/dirty-anchor-ready-instrument-r1) is bound to entry, paused PC, entry
code, main, start signature and vm_callprim; each is re-read from the repair
Seed ELF and must be identical, and the linked-byte inventory proves every
resident byte outside the two Session members and derived Build-ID data equal.
"""
import json
from pathlib import Path
import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/retained-callable-repair-r1/ready-instrument.json'


def constants(elf):
    t = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    def at(addr, n):
        rows = [s for s in t.sections if s.section_type == 'SHT_PROGBITS' and 'SHF_ALLOC' in s.flags
                and s.address <= addr < s.address+s.bytes and s.address+s.bytes >= addr+n]
        assert rows, hex(addr)
        d = t.section_bytes(rows[0].name)
        return d[addr-rows[0].address:addr-rows[0].address+n].hex()
    return t, at


def main():
    parent = ROOT/'build/dirty-anchor-card-r1/ready-instrument.json'
    anchor = json.loads(parent.read_text())
    world = next(w for w in anchor['worlds'] if w['role'] == 'candidate')
    packed = json.loads((ROOT/'build/retained-callable-repair-seed-medium-r1/packed-receipt.json').read_text())
    elf = N.checked_binding(packed['elf'])
    base_elf = N.checked_binding(world['ELF'])
    rows = []
    for path in (base_elf, elf):
        t, at = constants(path)
        rows.append(dict(entry_code=at(world['entry'], len(world['entry_code'])//2),
                         signature=at(world['main'], len(world['signature'])//2),
                         vm_callprim=t.symbol('vm_callprim').value))
    assert rows[0] == rows[1] == dict(entry_code=world['entry_code'], signature=world['signature'],
                                      vm_callprim=world['vm_callprim']), rows
    inventory = ROOT/'build/retained-callable-repair-seed-inventory-r1/inventory.json'
    inv = json.loads(inventory.read_text())
    assert inv['status'].startswith('PASS') and inv['ELFs'][1]['sha256'] == packed['elf']['sha256']
    baseline = dict(world, role='baseline')
    candidate = dict(world, role='candidate', ELF=packed['elf'], medium=packed['medium'])
    value = dict(anchor, authority='e0be22c1', parent=N.bind(parent), worlds=[baseline, candidate],
                 binary=world['binary'], unchanged_sources=None, changed_sources=[],
                 replacement=None, observer_builds=0, driver=N.bind(Path(__file__)),
                 resident_identity=N.bind(inventory),
                 claim='Anchor candidate observer reused unchanged for both worlds; constants re-read from both ELFs.')
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print('READY INSTRUMENT REUSED; constants identical', rows[1])


if __name__ == '__main__':
    main()
