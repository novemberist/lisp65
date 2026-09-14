#!/usr/bin/env python3
"""A7: short-branch crossing ceilings for the four inventoried hot owners.

Counts potential taken-branch crossings, not dynamic frequency or cycles.
The default and ceiling authority is the immutable 2.2.0 ELF; --elf checks
a successor. Byte shifts are analytic controls, never product builds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from elf_truth import ElfTruth
from stack_layout_assumptions_gate import ROOT, LLVM, AUTHORITY, require

OWNERS = ('gc_collect', 'vm_run_inner',
          'c2_mapped_far_vm_code_load_converged', 'lisp_input_event')


def population(elf):
    truth = ElfTruth.read(elf, llvm_readobj=LLVM/'llvm-readobj', include_section_data=True)
    result = {}
    for name in OWNERS:
        owner = truth.symbol(name)
        require(owner.symbol_type == 'Function' and owner.bytes > 0, 'unsized hot owner: '+name)
        sec = truth.section(owner.section)
        raw = truth.section_bytes(owner.section)
        text = subprocess.check_output([str(LLVM/'llvm-objdump'), '-d', '--no-show-raw-insn',
                                        '--section='+owner.section, str(elf)], text=True)
        branches = []
        for line in text.splitlines():
            m = re.match(r'\s*([0-9a-f]+):\s+(b(?:eq|ne|cc|cs|mi|pl|vc|vs|ra))\s+\$([0-9a-f]+)', line)
            if not m:
                continue
            pc, target = int(m[1], 16), int(m[3], 16)
            if not owner.value <= pc < owner.value+owner.bytes:
                continue
            at = pc-sec.address
            require(raw[at] in (0x10,0x30,0x50,0x70,0x90,0xb0,0xd0,0xf0,0x80),
                    'non-PCRel8 branch in hot range')
            delta = int.from_bytes(raw[at+1:at+2], 'little', signed=True)
            require(pc+2+delta == target, 'decoded branch target differs from ELF bytes')
            require(owner.value <= target < owner.value+owner.bytes,
                    'external hot branch needs a separate placement contract: '+name)
            branches.append(dict(pc=pc, target=target, opcode=m[2]))
        require(branches, 'empty hot branch population: '+name)
        result[name] = dict(start=owner.value, bytes=owner.bytes, section=owner.section, branches=branches)
    return result


def crossings(row, shift=0):
    return sum((b['pc']+2+shift)//256 != (b['target']+shift)//256 for b in row['branches'])


def validate(actual, ceiling):
    require(set(actual) == set(ceiling) == set(OWNERS), 'hot-owner population drift')
    for name in OWNERS:
        require(crossings(actual[name]) <= ceiling[name], 'hot crossing ceiling exceeded: '+name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path)
    args = parser.parse_args()
    bound = json.loads(AUTHORITY.read_text())['raw_pair']['ELF']
    baseline = ROOT/bound['path']
    require(hashlib.sha256(baseline.read_bytes()).hexdigest() == bound['sha256'], 'ceiling ELF identity drift')
    before = population(baseline)
    after = population(args.elf) if args.elf else before
    ceiling = {name: crossings(row) for name, row in before.items()}
    validate(after, ceiling)
    rejected, rows = [], {}
    for name, row in before.items():
        shift = next((n for n in range(1, 256) if crossings(row, n) > ceiling[name]), None)
        require(shift is not None, 'no sharp shift control: '+name)
        mutant = dict(before)
        mutant[name] = dict(row, branches=[dict(b, pc=b['pc']+shift, target=b['target']+shift)
                                          for b in row['branches']])
        try:
            validate(mutant, ceiling)
        except RuntimeError:
            rejected.append(dict(owner=name, shift=shift, crossings=crossings(row, shift)))
        else:
            raise RuntimeError('shift control survived: '+name)
        current = after[name]
        rows[name] = dict(current, ceiling=ceiling[name], crossings=crossings(current),
            positive_shift_to_exceed_ceiling=next((n for n in range(1,256)
                if crossings(current,n)>ceiling[name]), None))
    out = ROOT/'build/hot-branch-pages/receipt.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(status='PASS', ceiling_elf=bound, rows=rows,
        mutations_rejected=rejected, scope='Four inventoried owners only; no execution-frequency or all-program timing claim.'),indent=2)+'\n')
    print('hot-branch-pages: PASS', ceiling)


if __name__ == '__main__':
    main()
