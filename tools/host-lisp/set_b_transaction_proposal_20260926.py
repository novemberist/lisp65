"""Park and price resident transaction ownership; two objects, no product link."""
from pathlib import Path
from dataclasses import asdict
import difflib
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-transaction-proposal-r1'
HELPER='''/* Transaction ownership belongs to the resident caller, outside C356.
 * Cleanup still runs when transaction_end refuses; its failure is propagated
 * after the tenant releases scratch, preserving replay-before-disarm. */
__attribute__((noinline)) static uint8_t c2_retire_call(c2r_dispatch *d){
 uint8_t ok=1;
 if(d->next==56u){
  if(d->mode==0u && !d->auth){
   if(vm_runtime_overlay_transaction_begin(LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,c2_runtime.generation)!=VM_RUNTIME_OVERLAY_OK)return 0;
   d->auth=1u;
  }
  if(d->mode>=3u && d->auth){
   d->auth=0;
   if(vm_runtime_overlay_transaction_end()!=VM_RUNTIME_OVERLAY_OK)ok=0;
  }
 }
 return c2_overlay_call(d->next,d) && ok;
}
'''


def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    paths=['src/c2_product_runtime.c','src/optional/set_b_retire_control.c']
    old={p:(ROOT/p).read_text() for p in paths};new=dict(old)
    marker='__attribute__((noinline,used)) uint8_t c2_retire_run(uint8_t mode){'
    assert old[paths[0]].count(marker)==1
    s=old[paths[0]].replace(marker,HELPER+marker)
    assert s.count('if(!c2_overlay_call(d.next,&d)){')==1
    s=s.replace('if(!c2_overlay_call(d.next,&d)){','if(!c2_retire_call(&d)){')
    assert s.count('(void)c2_overlay_call(56u,&d);')==1
    s=s.replace('(void)c2_overlay_call(56u,&d);','d.next=56u;\n  (void)c2_retire_call(&d);')
    new[paths[0]]=s
    s=old[paths[1]]
    for line in ['  if(d->auth && vm_runtime_overlay_transaction_end()!=VM_RUNTIME_OVERLAY_OK)ok=0;\n',
                 '  d->auth=0;\n',
                 '  if(vm_runtime_overlay_transaction_begin(LISP65_RUNTIME_OVERLAY_FAMILY_SESSION,c2_runtime.generation)!=VM_RUNTIME_OVERLAY_OK)return C2_STREAM_ERR_STATE;\n',
                 '  d->auth=1u;\n']:
        assert s.count(line)==1;s=s.replace(line,'')
    new[paths[1]]=s
    patch=''.join(''.join(difflib.unified_diff(old[p].splitlines(True),new[p].splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in paths)
    (OUT/'authored.patch').write_text(patch)
    for p in paths:
        dest=OUT/'candidate'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(new[p])
    # Exact source hunk transfer into the consumed, generated runtime root.
    before=old[paths[0]][old[paths[0]].index(marker):]
    after=new[paths[0]][new[paths[0]].index(HELPER):]
    commands=P.load(S.PRODUCT/'commands.json')
    cc=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/c2_product_runtime.c'))
    srcdir=S.PRODUCT/'wplto/generated-product-sources';truths={};compiles=[];dep_rows=[];closures={}
    for label in ['before','after']:
        tree=OUT/label/'generated-product-sources';shutil.copytree(srcdir,tree)
        (tree/'optional').mkdir(exist_ok=True)
        for p in (ROOT/'src/optional').iterdir():
            if p.is_file():shutil.copyfile(p,tree/'optional'/p.name)
        if label=='after':
            p=tree/'c2_product_runtime.c';s=p.read_text();assert s.count(before)==1;p.write_text(s.replace(before,after))
            (tree/'optional/set_b_retire_control.c').write_text(new[paths[1]])
        obj=OUT/label/'005-c2_product_runtime.c.o'
        c=[str(tree.relative_to(ROOT)) if a==str(srcdir.relative_to(ROOT)) else a for a in cc]
        c[c.index('-c')+1]=str((tree/'c2_product_runtime.c').relative_to(ROOT))
        c[c.index('-o')+1]=str(obj.relative_to(ROOT));c+=['-fno-lto']
        run=subprocess.run(c,cwd=ROOT,capture_output=True,text=True);log=OUT/label/'compile.txt';log.write_text(run.stdout+run.stderr)
        compiles.append(dict(label=label,command=c,exit=run.returncode,log=P.bind(log)))
        P.write(OUT/'compile-receipt.json',dict(driver=P.bind(Path(__file__)),compiles=compiles,product_links=0))
        assert run.returncode==0,run.stderr
        compiles[-1]['object']=P.bind(obj)
        truths[label]=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        dc=c.copy();i=dc.index('-o');del dc[i:i+2];dc.remove('-c');dc+=['-M','-MT','runtime']
        dep=subprocess.run(dc,cwd=ROOT,capture_output=True,text=True);assert dep.returncode==0,dep.stderr
        (OUT/label/'dependencies.txt').write_text(dep.stdout+dep.stderr)
        rows=[];closure={}
        for raw in dep.stdout.replace('\\\n',' ').split(':',1)[1].split():
            p=(ROOT/raw).resolve();name='generated/'+str(p.relative_to(tree)) if p.is_relative_to(tree) else str(p.relative_to(ROOT))
            rows.append(dict(logical=name,binding=P.bind(p)));closure[name]=P.bind(p)['sha256']
        closures[label]=closure;dep_rows.append(dict(label=label,command=dc,exit=0,inputs=rows))
        cmd=[str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(obj)]
        (OUT/label/'disassembly.txt').write_text(subprocess.check_output(cmd,text=True))
        print(label,'compiled and dependency closure recorded',flush=True)
    P.write(OUT/'compile-receipt.json',dict(driver=P.bind(Path(__file__)),compiles=compiles,product_links=0))
    P.write(OUT/'dependencies.json',dep_rows)
    assert closures['before'].keys()==closures['after'].keys()
    changed_inputs=[n for n in closures['before'] if closures['before'][n]!=closures['after'][n]]
    assert set(changed_inputs)=={'generated/c2_product_runtime.c','generated/optional/set_b_retire_control.c'},changed_inputs
    a,b=truths['before'],truths['after'];sections=[];unchanged=[]
    sa={s.name:s for s in a.sections if 'SHF_ALLOC' in s.flags};sb={s.name:s for s in b.sections if 'SHF_ALLOC' in s.flags}
    def rel(t,n):return [(r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==n]
    for name in sorted(sa.keys()|sb.keys()):
        x,y=sa.get(name),sb.get(name)
        same=x is not None and y is not None and x.bytes==y.bytes and rel(a,name)==rel(b,name)
        if same and x.section_type!='SHT_NOBITS':same=a.section_bytes(name)==b.section_bytes(name)
        if same:unchanged.append(name)
        else:sections.append(dict(section=name,before=x.bytes if x else 0,after=y.bytes if y else 0,delta=(y.bytes if y else 0)-(x.bytes if x else 0),relocations_before=rel(a,name),relocations_after=rel(b,name)))
    allowed={'.text.c2_retire_run','.text.c2_retire_call','.lisp65_rt_c2append_retire_control'}
    assert {r['section'] for r in sections}<=allowed,[(r['section'],r['delta']) for r in sections]
    assert {r.target for r in b.relocations if r.target.startswith('vm_runtime_overlay_transaction_') and r.source_section.startswith('.lisp65_rt_c2append_retire')}==set()
    linked=ElfTruth.read(S.PRODUCT/'wplto/resident-island-seed.prg.elf',llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    resident_delta=sum(r['delta'] for r in sections if r['section'].startswith('.text.'))
    control=next(r for r in sections if r['section']=='.lisp65_rt_c2append_retire_control')
    P.write(OUT/'receipt.json',dict(status='PASS: PARKED RESIDENT TRANSACTION REPAIR OBJECT PROJECTION',
        driver=P.bind(Path(__file__)),authority=S.require_auth(),patch=P.bind(OUT/'authored.patch'),
        seed=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),changes=sections,unchanged_allocated_sections=unchanged,
        consumed_input_differences=changed_inputs,compile_receipt=P.bind(OUT/'compile-receipt.json'),dependencies=P.bind(OUT/'dependencies.json'),
        resident_delta=resident_delta,existing_resident_admission=246,proposed_resident_admission=246+resident_delta,
        text_free_before=1009,text_free_projection=1009-resident_delta,text_floor=32,
        control_code_before=linked.section(control['section']).bytes,control_code_projection=linked.section(control['section']).bytes+control['delta'],
        control_record_extent=448,tenant_extent=6752,tenant_tail=1440,
        new_bss_bytes=0,new_slots=0,product_links=0,seeds=0,finals=0,device_contacts=0,
        limits='Non-LTO matched object projection only; exact whole-program layout and all execution gates remain outstanding. Admission limit increase is proposed, not granted.'))
    print('PASS object projection; resident delta',resident_delta,'text air projection',1009-resident_delta,flush=True)


if __name__=='__main__':main()
