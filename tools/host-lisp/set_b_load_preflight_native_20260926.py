"""Park/price an equivalent native entry scan; no product compile/link.

Private unary Prim67 selector17 returns the charged-front pair. Existing
byte and owner selectors retain their behavior. No new storage or PID.
"""
from pathlib import Path
import difflib
import shutil
import subprocess
import traceback
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-native-r1'
PROP=ROOT/'build/set-b-load-repair-proposal-r5/candidate'
HELPER='''/* Read-only resolver front. Include retired entries; never reclaim code.
 * Read the same published generation/count as the Lisp world validator.
 * Two fixnum arguments to cons need no additional GC root. */
__attribute__((noinline)) obj c2_resolver_charged_front(void){
 uint8_t row[10];uint16_t generation,count,i;uint32_t low=0,end;
 if(!c2_ready || !c2_stream_c2d_read(10u,row,8u))return NIL;
 generation=c2_u16(row);count=c2_u16(row+6);
 if(count>C2D_ENTRY_CAP)return NIL;
 for(i=0;i<count;++i){
  if(!c2_stream_c2d_read((uint16_t)(2096u+i*10u),row,10u)
     || c2_u16(row+8)!=generation || !c2_u16(row+4)
     || !c2_bank2_code_range(c2_u16(row+2),c2_u16(row+4)))return NIL;
  end=(uint32_t)c2_u16(row+2)+c2_u16(row+4);
  if(end>low)low=end;
 }
 return cons(MKFIX((uint16_t)low&255u),MKFIX((uint16_t)(low>>8)));
}
'''
VM_OLD='''            if (!vm_byte_args(a, n, 1u)) return NIL;
            part = c2_resolver_owner_part((uint8_t)FIXVAL(a[0]));'''
VM_NEW='''            if (!vm_byte_args(a, n, 1u)) return NIL;
            if (FIXVAL(a[0]) == 17) {
                extern obj c2_resolver_charged_front(void);
                return c2_resolver_charged_front();
            }
            part = c2_resolver_owner_part((uint8_t)FIXVAL(a[0]));'''

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    names=['lib/stdlib-require.lisp','src/c2_product_runtime.c','src/vm.c','src/optional/set_b_retire_reset.c','src/optional/set_b_retire_control.c']
    old={n:(ROOT/n).read_text() for n in names};new={n:(PROP/n).read_text() if (PROP/n).exists() else old[n] for n in names}
    s=new[names[0]];a=s.index('; Retired entries remain charged.');b=s.index('(defun %require-world-tail',a);s=s[:a]+s[b:]
    a=s.index('      (let ((charged (%require-charged-front');b=s.index('\n        nil)))',a)
    s=s[:a]+'''      (let ((charged (%c2d-byte 17)))
          (if charged
              (let ((low (if (%require-u16<= charged code-low)
                             code-low charged)))
                (if (%require-u16<= low (nth 4 fronts))
                    (list state low fronts) nil))
              nil))'''+s[b:]
    new[names[0]]=s
    assert new[names[1]].endswith('\n#endif\n');new[names[1]]=new[names[1]][:-len('\n#endif\n')]+'\n'+HELPER+'\n#endif\n'
    assert new[names[2]].count(VM_OLD)==1;new[names[2]]=new[names[2]].replace(VM_OLD,VM_NEW)
    for n in names:
        p=OUT/'candidate'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(new[n])
    (OUT/'authored.patch').write_text(''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in names))
    srcdir=S.PRODUCT/'wplto/generated-product-sources';commands=P.load(S.PRODUCT/'commands.json');rows=[];truths={}
    for label in ('before','candidate'):
        tree=OUT/label/'generated-product-sources';shutil.copytree(srcdir,tree);(tree/'optional').mkdir(exist_ok=True)
        for p in (ROOT/'src/optional').iterdir():
            if p.is_file():shutil.copyfile(p,tree/'optional'/p.name)
        if label=='candidate':
            p=tree/'c2_product_runtime.c';s=p.read_text();assert s.endswith('\n#endif\n');p.write_text(s[:-len('\n#endif\n')]+'\n'+HELPER+'\n#endif\n')
            p=tree/'vm.c';s=p.read_text();assert s.count(VM_OLD)==1;p.write_text(s.replace(VM_OLD,VM_NEW))
            for n in names[-2:]:(tree/'optional'/Path(n).name).write_text(new[n])
        for unit in ('c2_product_runtime.c','vm.c'):
            cc=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/'+unit))
            obj=OUT/label/(unit+'.o');cmd=[str(tree.relative_to(ROOT)) if x==str(srcdir.relative_to(ROOT)) else x for x in cc]
            cmd[cmd.index('-c')+1]=str((tree/unit).relative_to(ROOT));cmd[cmd.index('-o')+1]=str(obj.relative_to(ROOT));cmd+=['-fno-lto']
            r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/label/(unit+'.log');log.write_text(r.stdout+r.stderr)
            rows.append(dict(world=label,unit=unit,command=cmd,exit=r.returncode,log=P.bind(log)));P.write(OUT/'commands.json',rows);assert r.returncode==0,r.stderr
            rows[-1]['object']=P.bind(obj)
            dc=cmd.copy();i=dc.index('-o');del dc[i:i+2];dc.remove('-c');dc+=['-M','-MT',unit]
            r=subprocess.run(dc,cwd=ROOT,capture_output=True,text=True);assert r.returncode==0
            inputs=[]
            for raw in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
                p=(ROOT/raw).resolve();logical='generated/'+str(p.relative_to(tree)) if p.is_relative_to(tree) else str(p.relative_to(ROOT));inputs.append(dict(logical=logical,binding=P.bind(p)))
            rows[-1]['dependencies']=dict(command=dc,exit=0,inputs=inputs)
            t=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True);truths[label,unit]=t
            (OUT/label/(unit+'.disassembly.txt')).write_text(subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(obj)],text=True))
    P.write(OUT/'commands.json',rows);diffs=[];same=[]
    def rel(t,n):return [(r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==n]
    for unit in ('c2_product_runtime.c','vm.c'):
        a,b=truths['before',unit],truths['candidate',unit];sa={s.name:s for s in a.sections if 'SHF_ALLOC' in s.flags};sb={s.name:s for s in b.sections if 'SHF_ALLOC' in s.flags}
        for name in sa.keys()|sb.keys():
            x,y=sa.get(name),sb.get(name);equal=x and y and x.bytes==y.bytes and rel(a,name)==rel(b,name)
            if equal and x.section_type!='SHT_NOBITS':equal=a.section_bytes(name)==b.section_bytes(name)
            if equal:same.append([unit,name])
            else:diffs.append(dict(unit=unit,section=name,before=x.bytes if x else 0,after=y.bytes if y else 0,delta=(y.bytes if y else 0)-(x.bytes if x else 0)))
    P.write(OUT/'receipt.json',dict(status='PARKED NATIVE FRONT QUERY: MATCHED OBJECT PRICE',driver=P.bind(Path(__file__)),patch=P.bind(OUT/'authored.patch'),source_authority=S.require_auth(),changes=diffs,unchanged_allocated_sections=same,
        commands=P.bind(OUT/'commands.json'),native_object_compiles=4,dependency_calls=4,product_builds=0,product_links=0,seeds=0,device_contacts=0,
        limits='Private selector17 is proposed, not admitted. Whole-product layout, exact native time, query semantic/fault rows and consumer admission remain gates.'))
    print('Native proposal price',diffs,flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
