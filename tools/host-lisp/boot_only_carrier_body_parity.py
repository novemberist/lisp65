"""Linked-body parity including every error branch and stack instruction.

Normalize only retained ELF relocations and four locally proven profile-ID
comparisons. All remaining instruction bytes must match the accepted world.
"""
import hashlib
import json
from pathlib import Path
import re

from elf_truth import ElfTruth
from boot_only_carrier_elf_gate import NAMES

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'build/ov-crc16-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf'
NEW=ROOT/'build/boot-only-carrier-product-r1/wplto/resident-island-seed.prg.elf'


def normalized(t,name,build_id):
    f=t.symbol(name); s=t.section(f.section)
    body=bytearray(t.section_bytes(f.section)[f.value-s.address:f.value-s.address+f.bytes])
    edges=[]; profiles=[]
    for r in t.relocations:
        if r.source_section!=f.section or not f.value<=r.offset<f.value+f.bytes: continue
        off=r.offset-f.value
        widths={'R_MOS_ADDR8':1,'R_MOS_ADDR16':2,'R_MOS_ADDR16_LO':1,'R_MOS_ADDR16_HI':1}
        if r.relocation_type not in widths: raise ValueError('unreviewed relocation '+r.relocation_type)
        target,addend=r.target,r.addend
        if target==f.section and f.value<=s.address+addend<f.value+f.bytes:
            target,addend=name,s.address+addend-f.value
        edges.append((off,r.relocation_type,target,addend))
        body[off:off+widths[r.relocation_type]]=bytes(widths[r.relocation_type])
        if (name=='vm_install_staged_boot_overlay' and r.target=='__lisp65_workbench_overlay_start'
                and r.addend in (6,7,8,9) and r.relocation_type=='R_MOS_ADDR16'):
            # LDX header[n]; CPX #profile-byte; BEQ past failure JMP. Prove rather
            # than blanket-mask the four byte differences observed in a diff.
            assert body[off-1]==0xae and body[off+2]==0xe0 and body[off+4]==0xf0
            assert body[off+3]==(build_id>>(8*(r.addend-6)))&255
            profiles.append(off+3);body[off+3]=0
    assert len(profiles)==(4 if name=='vm_install_staged_boot_overlay' else 0)
    return bytes(body),edges,profiles


def main():
    worlds=[]
    for p in (OLD,NEW):
        t=ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        header=(p.parent/'stage-config.h').read_text()
        ids=re.findall(r'^#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID (0x[0-9a-f]+)UL$',header,re.M)
        assert len(ids)==1
        worlds.append((t,int(ids[0],16)))
    rows=[]
    for name in sorted(NAMES):
        left=normalized(worlds[0][0],name,worlds[0][1])
        right=normalized(worlds[1][0],name,worlds[1][1])
        assert left==right, 'linked body or relocation contract differs: '+name
        rows.append(dict(name=name,bytes=len(left[0]),relocations=len(left[1]),
                         profile_operands=left[2],normalized_sha256=hashlib.sha256(left[0]).hexdigest()))
    result=dict(status='PASS: LINKED INSTRUCTION/STACK/ERROR-PATH PARITY',functions=rows,
                inputs=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (OLD,NEW)],
                normalization='retained relocation identity, local target offset, bound profile immediate only')
    out=ROOT/'build/boot-only-carrier-r1/linked-body-parity.json'
    value=json.dumps(result,indent=2)+'\n'
    if out.exists() and out.read_text()!=value: raise ValueError('parity receipt overwrite')
    if not out.exists(): out.write_text(value)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
