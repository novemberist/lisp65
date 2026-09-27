"""Measure isolated lifecycle integration against matched fifth-Seed objects."""
from pathlib import Path
import shutil
import subprocess
import traceback
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_shared_front_r2_20260926 as K
import set_b_load_preflight_native_r2_20260926 as N
import set_b_front_integration_r2_20260926 as I
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-integration-native-r1'
UNITS=('c2_product_runtime.c','vm.c','c2-stream-phase-05b.c')

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    srcdir=S.PRODUCT/'wplto/generated-product-sources'
    commands=P.load(S.PRODUCT/'commands.json');rows=[];truths={}
    for label in ('before','candidate'):
        tree=OUT/label/'generated-product-sources';shutil.copytree(srcdir,tree)
        (tree/'optional').mkdir(exist_ok=True)
        for p in (ROOT/'src/optional').iterdir():
            if p.is_file():shutil.copyfile(p,tree/'optional'/p.name)
        if label=='candidate':
            p=tree/'c2_product_runtime.c';s=p.read_text();assert s.endswith('\n#endif\n')
            p.write_text(I.runtime(s[:-len('\n#endif\n')]+'\n'+K.HELPER+'\n#endif\n'))
            p=tree/'vm.c';s=p.read_text();assert s.count(N.VM_OLD)==1
            p.write_text(I.vm(s.replace(N.VM_OLD,N.VM_NEW)))
            p=tree/'c2-stream-decoder.c';p.write_text(I.decoder(p.read_text()))
            for n in ('set_b_retire_reset.c','set_b_retire_control.c'):
                shutil.copyfile(I.OUT/'candidate/src/optional'/n,tree/'optional'/n)
        for unit in UNITS:
            cc=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/'+unit))
            obj=OUT/label/(unit+'.o')
            cmd=[str(tree.relative_to(ROOT)) if x==str(srcdir.relative_to(ROOT)) else x for x in cc]
            cmd[cmd.index('-c')+1]=str((tree/unit).relative_to(ROOT))
            cmd[cmd.index('-o')+1]=str(obj.relative_to(ROOT));cmd+=['-fno-lto']
            r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            log=OUT/label/(unit+'.log');log.write_text(r.stdout+r.stderr)
            rows.append(dict(world=label,unit=unit,command=cmd,exit=r.returncode,log=P.bind(log)))
            P.write(OUT/'commands.json',rows);assert r.returncode==0,r.stderr
            rows[-1]['object']=P.bind(obj)
            dc=cmd.copy();i=dc.index('-o');del dc[i:i+2];dc.remove('-c');dc+=['-M','-MT',unit]
            r=subprocess.run(dc,cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
            inputs=[]
            for raw in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
                p=(ROOT/raw).resolve()
                logical='generated/'+str(p.relative_to(tree)) if p.is_relative_to(tree) else str(p.relative_to(ROOT))
                inputs.append(dict(logical=logical,binding=P.bind(p)))
            rows[-1]['dependencies']=dict(command=dc,exit=0,inputs=inputs)
            truths[label,unit]=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
            (OUT/label/(unit+'.disassembly.txt')).write_text(subprocess.check_output(
                [str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(obj)],text=True))
    P.write(OUT/'commands.json',rows);diffs=[];same=[]
    def rel(t,n):return [(r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==n]
    for unit in UNITS:
        a,b=truths['before',unit],truths['candidate',unit]
        sa={s.name:s for s in a.sections if 'SHF_ALLOC' in s.flags};sb={s.name:s for s in b.sections if 'SHF_ALLOC' in s.flags}
        for name in sorted(sa.keys()|sb.keys()):
            x,y=sa.get(name),sb.get(name)
            equal=x and y and x.bytes==y.bytes and rel(a,name)==rel(b,name)
            if equal and x.section_type!='SHT_NOBITS':equal=a.section_bytes(name)==b.section_bytes(name)
            if equal:same.append([unit,name])
            else:diffs.append(dict(unit=unit,section=name,before=x.bytes if x else 0,
                after=y.bytes if y else 0,delta=(y.bytes if y else 0)-(x.bytes if x else 0)))
    ordinary=sum(x['delta'] for x in diffs if x['section'].startswith('.text.'))
    bss=sum(x['delta'] for x in diffs if x['section'].startswith('.bss.'))
    P.write(OUT/'receipt.json',dict(status='ISOLATED MATCHED OBJECT MEASUREMENT; NO PRODUCT ADMISSION',
        driver=P.bind(Path(__file__)),source_authority=authority,patch=P.bind(I.OUT/'authored.patch'),
        commands=P.bind(OUT/'commands.json'),changes=diffs,unchanged_allocated_sections=same,
        ordinary_text_delta=ordinary,high_bss_delta=bss,native_object_compiles=6,dependency_calls=6,
        product_builds=0,product_links=0,seeds=0,device_contacts=0,
        limits='Object projection only; no linked layout, execution time, stack or product consumer qualification.'))
    print('ordinary',ordinary,'BSS',bss,'changes',diffs,flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
