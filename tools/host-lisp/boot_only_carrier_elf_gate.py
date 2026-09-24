"""Carrier-specific successor admission; historical resident audits stay intact.

All incoming relocations must be the two main JSRs. Numeric direct branches are
checked independently, including branches to the middle of either function.
This gate does not infer a complete dynamic writer proof from ELF geometry.
"""
import argparse
import json
from pathlib import Path
import subprocess

from elf_truth import ElfTruth
from c2_crc_codegen_gate import disassembly_rows, _direct_operand
from boot_only_carrier_geometry import validate
from boot_only_carrier_prg import SECTION

ROOT = Path(__file__).resolve().parents[2]
NAMES = {'vm_install_staged_boot_overlay', 'vm_runtime_overlay_install_island'}


def check(elf):
    truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',
                          include_section_data=True)
    s = truth.section(SECTION)
    if set(s.flags) != {'SHF_ALLOC', 'SHF_EXECINSTR'}:
        raise ValueError('carrier must be executable immutable PROGBITS')
    values = truth.symbol_values()
    functions = [f for f in truth.symbols if f.section == SECTION and f.symbol_type == 'Function']
    if {f.name for f in functions} != NAMES or any(
            f.bytes <= 0 or f.value < s.address or f.value+f.bytes > s.address+s.bytes
            for f in functions):
        raise ValueError('carrier function population or bounds')
    expected = (max(values['__lisp65_workbench_overlay_end'],
                    values['__lisp65_boot_bank3_stage_end'])+1)&~1
    if s.address != expected:
        raise ValueError('carrier not derived from live window ends')
    validate(s.address, s.bytes, values['__lisp65_workbench_boot_slice_limit'],
             values['__stack'], [
                 ('BSS startup clear', values['__bss_start'], values['__bss_end']),
                 ('runtime replacement', values['__lisp65_workbench_overlay_start'],
                  values['__lisp65_workbench_runtime_overlay_limit']),
                 ('Workbench copy/wipe', values['__lisp65_workbench_overlay_start'],
                  values['__lisp65_workbench_overlay_end']),
                 ('cold record', values['__lisp65_boot_bank3_stage_start'],
                  values['__lisp65_boot_bank3_stage_end']),
                 ('island wipe', 0x1800, 0x2000)])
    if 'vm_boot_stack_probe_begin' in values:
        raise ValueError('boot canary writer needs a separate lifetime proof')
    main = truth.symbol('main')
    dump = subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),
                                   '-d', '--no-show-raw-insn', str(elf)], text=True)
    rows = disassembly_rows(dump)
    incoming = []
    for row in rows:
        target = _direct_operand(row)
        if target is None or not s.address <= target < s.address+s.bytes:
            continue
        # Data operands may legitimately read an address with this numeric
        # value in another bank; only control transfers are considered here.
        if row['opcode'] not in ('jsr','jmp','bra','beq','bne','bcc','bcs','bmi','bpl','bvc','bvs'):
            continue
        if row['section'] == SECTION:
            continue
        if (row['opcode'] != 'jsr' or row['section'] != main.section or
                not main.value <= row['address'] < main.value+main.bytes or
                target not in {values[n] for n in NAMES}):
            raise ValueError('unowned carrier entry: '+repr(row))
        incoming.append({**row,'target':target})
    if sorted(r['target'] for r in incoming) != sorted(values[n] for n in NAMES):
        raise ValueError('expected exactly the two direct main calls')
    for r in truth.relocations:
        if r.target not in NAMES or r.source_section == SECTION:
            continue
        if r.source_section != main.section or not main.value <= r.offset < main.value+main.bytes:
            raise ValueError('escaped carrier function reference: '+repr(r))
    return dict(status='PASS', carrier_bytes=s.bytes, start=s.address,
                end=s.address+s.bytes, incoming=incoming,
                claim='LINKED ENTRY/GEOMETRY; DYNAMIC LIFETIME WITNESS SEPARATE')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('elf',type=Path)
    print(json.dumps(check(p.parse_args().elf),indent=2))
