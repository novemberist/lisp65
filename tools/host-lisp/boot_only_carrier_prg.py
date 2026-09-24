"""Explicit extended-PRG contract for the boot-only carrier (no linker)."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
SECTION = '.lisp65_boot_carrier'


def compose(prefix, resident_end, start, payload, floor):
    if len(prefix) < 3:
        raise ValueError('missing resident PRG')
    base = struct.unpack_from('<H', prefix)[0]
    if len(prefix) != resident_end - base + 2:
        raise ValueError('resident prefix extent mismatch')
    if not base < resident_end <= start or start & 1:
        raise ValueError('invalid carrier placement')
    if not 0 < len(payload) <= 704 or start + len(payload) > floor:
        raise ValueError('carrier violates cap/boot stack')
    if not floor <= 0x10000:
        raise ValueError('not a Bank-0 PRG')
    return prefix + bytes(start-resident_end) + payload


def verify(candidate, prefix, resident_end, start, payload, floor):
    expected = compose(prefix,resident_end,start,payload,floor)
    if candidate != expected:
        raise ValueError('noncanonical or corrupted carrier PRG')


def from_elf(elf, prefix, publication_dir=None):
    truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',
                          include_section_data=True)
    section = truth.section(SECTION)
    expected_names = {'vm_install_staged_boot_overlay', 'vm_runtime_overlay_install_island'}
    functions = [s for s in truth.symbols if s.section == SECTION and s.symbol_type == 'Function']
    if {s.name for s in functions} != expected_names:
        raise ValueError('carrier function population mismatch')
    if any(s.bytes <= 0 or s.value < section.address or
           s.value+s.bytes > section.address+section.bytes for s in functions):
        raise ValueError('function escaped carrier')
    values = truth.symbol_values()
    expected_start = (max(values['__lisp65_workbench_overlay_end'],
                          values['__lisp65_boot_bank3_stage_end'])+1)&~1
    if section.address != expected_start:
        raise ValueError('carrier VMA not derived from live execution owners')
    floor = values['__lisp65_workbench_boot_slice_limit']
    if floor != values['__stack']-512:
        raise ValueError('boot stack reservation changed')
    base = struct.unpack_from('<H',prefix)[0]
    unbound=prefix
    if publication_dir is not None:
        receipt=json.loads((publication_dir/'total-publish-last-domain.json').read_text())
        unbound=(publication_dir/'lisp65-c2-substitution-unbound.prg').read_bytes()
        if (receipt['status']!='passed' or receipt['changes_outside_declared_domains']!=0
                or hashlib.sha256(prefix).hexdigest()!=receipt['bound_product_sha256']
                or hashlib.sha256(unbound).hexdigest()!=receipt['unbound_product_sha256']):
            raise ValueError('unbound/published prefix identity drift')
        expected={}
        table=(publication_dir/'runtime-overlay-verifier-bindings.bin').read_bytes()
        section=truth.section('.lisp65_runtime_overlay_verifier_bindings')
        expected.update({section.address-base+2+i:v for i,v in enumerate(table)})
        binding=json.loads((publication_dir/'kernal-window-publish-last.json').read_text())
        for operand in binding['binding_operands']:
            expected[operand['file_offset']]=operand['published_value']
        if (len(prefix)!=len(unbound) or len(expected)!=receipt['declared_domain_bytes']
                or any(prefix[i]!=v for i,v in expected.items())
                or any(a!=b and i not in expected for i,(a,b) in enumerate(zip(prefix,unbound)))):
            raise ValueError('publication altered undeclared prefix bytes')
    # VMA is not load ownership: mapped Bank-2 sections have overlapping VMAs
    # below the heap. PT_LOAD physical addresses identify the PRG bytes, and
    # also include zero-page initializers whose VMA is outside the prefix.
    headers=json.loads(subprocess.check_output([
        str(ROOT/'tools/llvm-mos/bin/llvm-readobj'),'--program-headers',
        '--elf-output-style=JSON',str(elf)],text=True))[0]['ProgramHeaders']
    image=elf.read_bytes()
    resident_end=max(row['ProgramHeader']['PhysicalAddress']+row['ProgramHeader']['FileSize']
                     for row in headers if row['ProgramHeader']['Type']['Name']=='PT_LOAD'
                     and row['ProgramHeader']['FileSize']>0
                     and base<=row['ProgramHeader']['PhysicalAddress']<values['__heap_start'])
    if resident_end>values['__heap_start']:
        raise ValueError('resident load owner exceeds heap floor')
    for row in headers:
        resident=row['ProgramHeader']
        at=resident['PhysicalAddress']; size=resident['FileSize']
        if (resident['Type']['Name']!='PT_LOAD' or not size
                or not base<=at<values['__heap_start']):
            continue
        offset=at-base+2; source=resident['Offset']
        if at+size>values['__heap_start'] or unbound[offset:offset+size]!=image[source:source+size]:
            raise ValueError('resident ELF/PRG prefix mismatch at '+hex(at))
    # The historical file_end predates fixed Bank-0 code at $c218. The actual
    # PRG prefix extends to the final Bank-0 load owner and MUST be preserved.
    # Using file_end would silently zero that executable owner in the gap.
    carrier=truth.section(SECTION)
    return compose(prefix,resident_end,
                   carrier.address,truth.section_bytes(SECTION),floor)


def selftest():
    prefix = struct.pack('<H',0x2001)+b'RESIDENT'
    end = 0x2009
    start = 0xca9e
    payload = bytes(range(256))*2 + bytes(186)
    expected = compose(prefix,end,start,payload,0xce00)
    assert expected[:len(prefix)] == prefix
    assert expected[2+start-0x2001:] == payload
    # Nonzero fixed-owner bytes beyond an old ordinary-text file-end survive.
    fixed_prefix = struct.pack('<H',0x2001)+bytes(0xc218-0x2001)+b'FIXED-CODE'
    fixed_end = 0x2001+len(fixed_prefix)-2
    fixed = compose(fixed_prefix,fixed_end,start,payload,0xce00)
    assert fixed[:len(fixed_prefix)] == fixed_prefix
    try:
        compose(fixed_prefix,0xb9b4,start,payload,0xce00)
    except ValueError:
        pass
    else:
        raise AssertionError('obsolete ordinary file-end accepted')
    bad = {
        'missing': expected[:-len(payload)],
        'corrupt': expected[:-1]+b'\x01',
        'mispositioned': expected[:-len(payload)]+b'\0'+payload,
        'extra byte': expected+b'\0',
        'resident changed': expected[:2]+b'X'+expected[3:],
        'gap changed': expected[:len(prefix)]+b'X'+expected[len(prefix)+1:],
        'LMA substituted': prefix+payload,
    }
    for name, candidate in bad.items():
        try:
            verify(candidate,prefix,end,start,payload,0xce00)
        except ValueError:
            pass
        else:
            raise AssertionError(name)
    for n in (0,705):
        try:
            compose(prefix,end,start,bytes(n),0xce00)
        except ValueError:
            pass
        else:
            raise AssertionError('size cap')
    print('boot-only-carrier-prg: PASS 10 negative controls; model only')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest',action='store_true',required=True)
    parser.parse_args()
    selftest()
