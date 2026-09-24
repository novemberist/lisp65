"""2026-09-22 control-audit successor for the two-function boot carrier.

The historical Workbench audit describes retired boot slices even on the
immediate predecessor. Do not pretend that changing its .text constant makes
it applicable. This successor composes current linked entry/geometry, exact
installer-body parity, and the existing preinstallation Island/wipe proof.
Historical audit inputs and expectations remain unchanged.
"""
import copy
from dataclasses import replace
import json
from unittest.mock import patch

import boot_only_carrier_elf_gate as G
import boot_only_carrier_body_parity as B
import c2_preinstall_island_guard as I
from boot_only_carrier_native_boot import bind, ROOT
from elf_truth import ElfTruth


def controls(elf):
    t = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    dump = G.subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),
                                    '-d', '--no-show-raw-insn', str(elf)], text=True)
    rows = G.disassembly_rows(dump)
    original = G.check(elf)
    s = t.section(G.SECTION)
    variants = {}
    for label, sections, symbols, relocations in [
        ('writable', [replace(x, flags=(*x.flags,'SHF_WRITE')) if x.name==G.SECTION else x for x in t.sections], t.symbols, t.relocations),
        ('oversize', [replace(x, bytes=705) if x.name==G.SECTION else x for x in t.sections], t.symbols, t.relocations),
        ('unowned-function', t.sections, [*t.symbols, replace(t.symbol('vm_install_staged_boot_overlay'), name='extra-function')], t.relocations),
        ('escaped-function', t.sections, [replace(x, value=s.address-1) if x.name=='vm_install_staged_boot_overlay' else x for x in t.symbols], t.relocations),
        ('unowned-reference', t.sections, t.symbols, [*t.relocations, replace(next(r for r in t.relocations if r.target in G.NAMES), source_section='.rodata', offset=0)]),
    ]:
        variants[label] = ElfTruth(sections=sections, symbols=symbols, relocations=relocations,
                                  section_data=t._section_data)
    rejected=[]
    for label, mutant in variants.items():
        with patch.object(G.ElfTruth,'read',return_value=mutant), patch.object(G.subprocess,'check_output',return_value=dump):
            try: G.check(elf)
            except ValueError: rejected.append(label)
            else: raise AssertionError('mutation survived: '+label)
    extra = dict(original['incoming'][0]); extra['address']=0x2222
    extra['operand']='$%04x'%(s.address+1)
    with patch.object(G,'disassembly_rows',return_value=[*rows,extra]):
        try: G.check(elf)
        except ValueError: rejected.append('entry-into-body')
        else: raise AssertionError('unowned direct entry survived')
    # A non-relocated opcode change must survive no normalization whatsoever.
    mutant=copy.deepcopy(t); f=t.symbol('vm_runtime_overlay_install_island')
    data=bytearray(mutant._section_data[s.index]); data[f.value-s.address]^=1
    mutant._section_data[s.index]=bytes(data)
    assert B.normalized(t,f.name,0)!=B.normalized(mutant,f.name,0)
    rejected.append('instruction-change')
    return original, rejected


def main():
    B.main()
    entry, negative = controls(B.NEW)
    before, after = [I.static_elf_gate(p) for p in (B.OLD,B.NEW)]
    assert before['reachable_functions']==after['reachable_functions']
    assert not after['unguarded_or_consuming_data_references']
    assert after['installer_root']['section']==G.SECTION
    result=dict(status='PASS', authority='4cd7eac3', entries=entry,
                rejected_mutations=negative, preinstall_island=after,
                predecessor_island=before, inputs=[bind(p) for p in (B.OLD,B.NEW)],
                scope='dated current-world successor; historical Workbench audit unchanged')
    target=ROOT/'build/boot-only-carrier-r1/control-audit.json'
    encoded=json.dumps(result,indent=2)+'\n'
    if target.exists(): assert target.read_text()==encoded, 'immutable audit receipt'
    else: target.write_text(encoded)
    print('PASS: carrier control-audit successor;',len(negative),'negative controls')


if __name__=='__main__': main()
