"""Matched object price of the host-qualified synchronous publication prerequisite."""
from pathlib import Path
import shutil
import subprocess
from collections import defaultdict
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_clear_sync_20260927 as CARD
from elf_truth import ElfTruth
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=CARD.OUT/'native'
UNITS=('c2_product_runtime.c','c2_platform_dma.c')


def main():
    authority=S.require_auth()
    host=P.load(CARD.OUT/'roots/result.json')
    assert host['status']=='PASS root prerequisite' and host['candidate_rows']==240 and host['falling_controls']==3
    OUT.mkdir(exist_ok=False)
    srcdir=S.PRODUCT/'wplto/generated-product-sources'
    commands=P.load(S.PRODUCT/'commands.json');rows=[];truths={}
    for label in ('before','candidate'):
        tree=OUT/label/'generated-product-sources';shutil.copytree(srcdir,tree)
        (tree/'optional').mkdir(exist_ok=True)
        for p in (ROOT/'src/optional').iterdir():
            if p.is_file():shutil.copyfile(p,tree/'optional'/p.name)
        # Matched baseline is the parked barrier-read candidate, not the seed.
        for p in CARD.PREVIOUS.CANDIDATE.rglob('*'):
            if p.is_file() and p.is_relative_to(CARD.PREVIOUS.CANDIDATE/'src'):
                dest=tree/p.relative_to(CARD.PREVIOUS.CANDIDATE/'src');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        shutil.copyfile(ROOT/'src/c2_platform_dma.h',tree/'c2_platform_dma.h')
        if label=='candidate':
            for p in CARD.CANDIDATE.rglob('*'):
                if p.is_file() and p.is_relative_to(CARD.CANDIDATE/'src'):
                    dest=tree/p.relative_to(CARD.CANDIDATE/'src');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        for unit in UNITS:
            cc=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/'+unit))
            obj=OUT/label/(unit+'.o')
            cmd=[str(tree.relative_to(ROOT)) if x==str(srcdir.relative_to(ROOT)) else x for x in cc]
            cmd[cmd.index('-c')+1]=str((tree/unit).relative_to(ROOT));cmd[cmd.index('-o')+1]=str(obj.relative_to(ROOT));cmd+=['-fno-lto']
            rows.append(dict(world=label,unit=unit,command=cmd,status='charged before execution'))
            P.write(OUT/'commands.json',rows)
            r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/label/(unit+'.log');log.write_text(r.stdout+r.stderr)
            rows[-1].update(exit=r.returncode,log=P.bind(log));P.write(OUT/'commands.json',rows)
            assert r.returncode==0,r.stderr
            rows[-1]['object']=P.bind(obj)
            dc=cmd.copy();i=dc.index('-o');del dc[i:i+2];dc.remove('-c');dc+=['-M','-MT',unit]
            rows[-1]['dependencies']=dict(command=dc,status='charged before execution');P.write(OUT/'commands.json',rows)
            r=subprocess.run(dc,cwd=ROOT,capture_output=True,text=True)
            dp=OUT/label/(unit+'.deps');dp.write_text(r.stdout+r.stderr)
            assert r.returncode==0,r.stderr
            inputs=[]
            for raw in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
                p=(ROOT/raw).resolve();inputs.append(P.bind(p) if p.is_relative_to(ROOT) else external_binding(p))
            rows[-1]['dependencies']=dict(command=dc,exit=0,inputs=inputs,log=P.bind(dp));P.write(OUT/'commands.json',rows)
            truths[label,unit]=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
            (OUT/label/(unit+'.disassembly.txt')).write_text(subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(obj)],text=True))
    asm=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/c2_map_cpu_read.s')).copy()
    asm[asm.index('-c')+1]=str((CARD.CANDIDATE/'src/optional/c2_map_cpu_write.s').relative_to(ROOT))
    obj=OUT/'c2_map_cpu_write.o';asm[asm.index('-o')+1]=str(obj.relative_to(ROOT))
    P.write(OUT/'assembler.json',dict(command=asm,status='assembler attempt1 charged before execution'))
    r=subprocess.run(asm,cwd=ROOT,capture_output=True,text=True);(OUT/'assembler.log').write_text(r.stdout+r.stderr)
    P.write(OUT/'assembler.json',dict(command=asm,exit=r.returncode,log=P.bind(OUT/'assembler.log')))
    assert r.returncode==0,r.stderr
    write_truth=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    (OUT/'c2_map_cpu_write.disassembly.txt').write_text(subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(obj)],text=True))
    differences=[];same=[]
    def rel(t,n):return [(r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==n]
    for unit in UNITS:
        a,b=truths['before',unit],truths['candidate',unit]
        sa={s.name:s for s in a.sections if 'SHF_ALLOC' in s.flags};sb={s.name:s for s in b.sections if 'SHF_ALLOC' in s.flags}
        for name in sorted(sa.keys()|sb.keys()):
            x,y=sa.get(name),sb.get(name)
            equal=x and y and x.bytes==y.bytes and rel(a,name)==rel(b,name)
            if equal and x.section_type!='SHT_NOBITS':equal=a.section_bytes(name)==b.section_bytes(name)
            if equal:same.append([unit,name])
            else:differences.append(dict(unit=unit,section=name,before=x.bytes if x else 0,after=y.bytes if y else 0,delta=(y.bytes if y else 0)-(x.bytes if x else 0)))
    for s in write_truth.sections:
        if 'SHF_ALLOC' in s.flags and s.bytes:
            differences.append(dict(unit='c2_map_cpu_write.s',section=s.name,before=0,after=s.bytes,delta=s.bytes))
    totals=defaultdict(int)
    for d in differences:totals[d['section']]+=d['delta']
    ordinary=sum(d for n,d in totals.items() if n.startswith(('.text','.rodata')))
    e000=totals['.lisp65_c2_kernal_window.c2_resident'];bss=sum(d for n,d in totals.items() if n.startswith(('.bss','.noinit')))
    checks=[dict(owner='ordinary',previous_margin=8,delta=ordinary,margin=8-ordinary,pass_gate=ordinary<=8),
        dict(owner='E000',previous_margin=25,delta=e000,margin=25-e000,pass_gate=e000<=25),
        dict(owner='high-BSS',previous_margin=1,delta=bss,margin=1-bss,pass_gate=bss<=1)]
    failures=[r for r in checks if not r['pass_gate']]
    P.write(OUT/'receipt.json',dict(status='HALT at prerequisite capacity' if failures else 'PASS prerequisite capacity projection',execution_head=CARD.HEAD,
        source_authority=authority,driver=P.bind(Path(__file__)),host=P.bind(CARD.OUT/'roots/result.json'),patch=P.bind(CARD.OUT/'authored.patch'),commands=P.bind(OUT/'commands.json'),
        assembler=P.bind(OUT/'assembler.json'),assembler_object=P.bind(obj),differences=differences,unchanged_allocated_sections=same,checks=checks,failures=failures,
        native_object_calls=4,native_dependencies=4,assembler_calls=1,product_builds=0,product_links=0,seeds=0,finals=0,guest=0,device=0,
        limit='Host-qualified publication prerequisite only, measured before adding terminal controller. Non-LTO matched deltas; no final link, placement, target execution or complete CLEAR qualification. Remaining controller cannot be credited with unmeasured savings.'))
    print(P.load(OUT/'receipt.json')['status'],checks,flush=True)

if __name__=='__main__':main()
