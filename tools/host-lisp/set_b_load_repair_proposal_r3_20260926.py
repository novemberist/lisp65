"""Park a gap-aware resolver and post-INIT latch; host/object pricing only.

No maintained product source is changed, no product build or link occurs.
The Lisp candidate is executed with raw guest C2D snapshots through a
read-only primitive seam; native changes receive matched object pricing.
"""
from pathlib import Path
import difflib
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import bytecode_p0_stdlib as L
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-repair-proposal-r3'
EXTRA='''; Retired entries remain charged. Scan the published entry high-water,
; including owner 255, exactly as native c2_lite_bank2_scan does.
(defun %require-charged-row-end (base generation)
  (if (%require-u16= (%require-row-u16 base 8) generation)
      (let ((size (%require-row-u16 base 4)))
        (if (%require-u16-zero-p size) nil
            (let ((end (%require-u16-add-wide
                         (%require-row-u16 base 2) size)))
              (if end (if (%require-u16<= end (cons 0 256)) end nil)
                  nil))))
      nil))

(defun %require-charged-front (slot count generation low)
  (if (< slot count)
      (let ((end (%require-charged-row-end
                   (%require-address (cons 48 8) slot 10) generation)))
        (if end
            (%require-charged-front (1+ slot) count generation
              (if (%require-u16<= low end) end low))
            nil))
      low))

'''

def parked_sources():
    paths=['lib/stdlib-require.lisp','src/optional/set_b_retire_reset.c',
           'src/optional/set_b_retire_control.c']
    old={p:(ROOT/p).read_text() for p in paths};new=dict(old)
    s=old[paths[0]];a=s.index('(defun %require-persistent-row-size');b=s.index('(defun %require-persistent-row-p',a)
    part=s[a:b];needle='(%require-u16=\n                        (%require-row-u16 base 18) code-low)'
    assert part.count(needle)==1
    part=part.replace(needle,'(%require-u16<=\n                        code-low (%require-row-u16 base 18))')
    s=s[:a]+part+s[b:]
    a=s.index('(defun %require-active-prefix');b=s.index('(defun %require-identity-loaded-at-value',a)
    part=s[a:b];assert part.count('(%require-u16-add-wide code-low size)')==1
    part=part.replace('(%require-u16-add-wide code-low size)',
                      '(%require-u16-add-wide\n                              (%require-row-u16 base 18) size)')
    s=s[:a]+part+s[b:]
    a=s.index('(defun %require-world-tail');b=s.index('(defun %require-world (',a)
    part=s[a:b];assert part.count('(list state code-low fronts)')==1
    part=part.replace('(list state code-low fronts)',
        '''(let ((charged (%require-charged-front
                       0 (nth 2 state) (nth 0 state) code-low)))
          (if charged
              (if (%require-u16<= charged (nth 4 fronts))
                  (list state charged fronts) nil)
              nil))''')
    new[paths[0]]=s[:a]+EXTRA+part+s[b:]
    needle='c2r_boot_count=(uint8_t)c2_runtime.image_count|128u;'
    assert old[paths[1]].count(needle)==1
    new[paths[1]]=old[paths[1]].replace(needle,
        'c2r_boot_count=128u; /* Trusted, prefix pending until first prompt. */')
    needle=' x->first=c2r_boot_count&127u;'
    assert old[paths[2]].count(needle)==1
    new[paths[2]]=old[paths[2]].replace(needle,''' /* Only normal, quiescent entry may capture the post-INIT prefix.
  * Recovery above enters replay; failed boot remains disarmed. */
 if(c2r_boot_count==128u){
  if(c2_runtime.image_count<6u || c2_runtime.image_count>64u)return C2_STREAM_ERR_STATE;
  c2r_boot_count|=(uint8_t)c2_runtime.image_count;
 }
'''+needle)
    for p in paths:
        dest=OUT/'candidate'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(new[p])
    (OUT/'authored.patch').write_text(''.join(''.join(difflib.unified_diff(
        old[p].splitlines(True),new[p].splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in paths))
    return old,new

def lisp_projection(old,new):
    C,B=L.C,L.B
    def forms(source):
        return {f[1]:f for f in C.parse_all(source) if isinstance(f,list) and len(f)>=4 and f[0]=='defun'}
    common=forms((ROOT/'lib/prelude-m1.lisp').read_text())
    sets={key:forms(d['lib/stdlib-require.lisp']) for key,d in [('before',old),('after',new)]}
    names=sorted(set(sets['before'])|set(sets['after'])|{'nth'})
    sizes={};compiled={};heaps={};changes=[]
    for label,fs in sets.items():
        h=C.prepare_heap(names);codes={}
        for name,f in dict(nth=common['nth'],**fs).items():
            nm,code,helpers=C.compile_top_form_with_helpers(f,h,strict_arity=True,abi_profile='dialect-v2',prebuilt_primitives=True)
            assert nm==name and not helpers
            codes[nm]=code
            dest=OUT/'lisp-objects'/label/(name.replace('%','private-')+'.bin');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(code.encode())
        sizes[label]={n:len(c.encode()) for n,c in codes.items()};compiled[label]=codes;heaps[label]=h
    for n in names:
        if sets['before'].get(n)!=sets['after'].get(n):
            changes.append(dict(name=n,before=sizes['before'].get(n,0),after=sizes['after'].get(n,0),delta=sizes['after'].get(n,0)-sizes['before'].get(n,0)))
    assert max(r['after'] for r in changes)<=255
    class SnapshotVM(B.P0VM):
        def _callprim(self,pid,argc,stack,**kw):
            if pid==67:
                assert argc==2
                lo,hi=[B.fixval(x) for x in self._pop_args(argc,stack)]
                assert 0<=lo<=255 and 0<=hi<=255
                self.reads+=1
                return B.mkfix(self.raw[lo+256*hi])
            return super()._callprim(pid,argc,stack,**kw)
    rows=[]
    def run(label,tag,raw,entry,args,expected):
        h=heaps[label].clone();codes=compiled[label]
        directory={h.intern(n):c for n,c in codes.items()}
        vm=SnapshotVM(heap=h,directory=directory,max_steps=3000000,abi_profile='dialect-v2',abi_ledger=P.load(ROOT/'config/bytecode-abi-ledger.json'));vm.raw=raw;vm.reads=0
        def obj(v):
            if isinstance(v,tuple):return h.alloc(B.T_CONS,obj(v[0]),obj(v[1]))
            return B.mkfix(v)
        value=vm.run(directory[h.intern(entry)],[obj(x) for x in args])
        actual=None if value==B.NIL else (B.fixval(h.cell(value).a),B.fixval(h.cell(value).b))
        row=dict(world=label,case=tag,entry=entry,arguments=args,expected=expected,actual=actual,steps=vm.steps,reads=vm.reads)
        rows.append(row);P.write(OUT/'host-rows.json',rows)
        assert actual==expected,row
    root=ROOT/'build/set-b-load-attribution-r1'
    for n in [0,1,2]:
        raw=(root/f'definitions-{n}/before-load-c2d.bin').read_bytes()
        count=int.from_bytes(raw[16:18],'little');gen=(raw[10],raw[11]);end=8 if n==0 else 9
        # Image-prefix comparison excludes catalog identity; the concrete
        # predicate operands use the captured row and predecessor end.
        if n:
            for label in ['before','after']:
                run(label,f'definitions-{n}-row',raw,'%require-persistent-row-size',[(48,1),8,gen,(3,198)],None if label=='before' and n==2 else (10,0))
        expected=50691 if n==0 else 50701 if n==1 else 50711
        run('after',f'definitions-{n}-charged',raw,'%require-charged-front',[0,count,gen,(0,0)],(expected%256,expected//256))
    raw=bytearray((root/'definitions-2/before-load-c2d.bin').read_bytes());count=int.from_bytes(raw[16:18],'little')
    # Last entry is made a tombstone in a host fixture. It still raises the
    # charged high-water to C617; this is not a write to a running guest.
    raw[0x830+(count-1)*10]=255
    run('after','retired-tail-remains-charged',raw,'%require-charged-front',[0,count,(1,0),(3,198)],(23,198))
    for case,offset,value in [('zero-size',0x830+(count-1)*10+4,0),('wrong-generation',0x830+(count-1)*10+8,2)]:
        bad=bytearray(raw);bad[offset]=value
        run('after',case,bad,'%require-charged-front',[0,count,(1,0),(3,198)],None)
    bad=bytearray(raw);bad[0x830+(count-1)*10+2:0x830+(count-1)*10+4]=b'\xfc\xff'
    run('after','code-end-overflow',bad,'%require-charged-front',[0,count,(1,0),(3,198)],None)
    bad=bytearray(raw);bad[0x130+18:0x130+20]=b'\x02\xc6'
    run('after','live-span-overlap',bad,'%require-persistent-row-size',[(48,1),8,(1,0),(3,198)],None)
    P.write(OUT/'lisp-price.json',dict(changes=changes,code_delta=sum(r['delta'] for r in changes),new_entries=2,
        limit='Isolated bytecode objects, no product packing/link or literal/root/resolution closure. Full resolver and fast-note fixtures remain required.',host_rows=len(rows)))

def native_projection(new):
    srcdir=S.PRODUCT/'wplto/generated-product-sources'
    cc=next(c for c in P.load(S.PRODUCT/'commands.json') if '-c' in c and c[c.index('-c')+1].endswith('/c2_product_runtime.c'))
    truths={};receipts=[];closures={}
    for label in ['before','after']:
        tree=OUT/label/'generated-product-sources';shutil.copytree(srcdir,tree)
        (tree/'optional').mkdir(exist_ok=True)
        for p in (ROOT/'src/optional').iterdir():
            if p.is_file():shutil.copyfile(p,tree/'optional'/p.name)
        if label=='after':
            for name in ['src/optional/set_b_retire_reset.c','src/optional/set_b_retire_control.c']:
                (tree/'optional'/Path(name).name).write_text(new[name])
        obj=OUT/label/'runtime.o';cmd=[str(tree.relative_to(ROOT)) if a==str(srcdir.relative_to(ROOT)) else a for a in cc]
        cmd[cmd.index('-c')+1]=str((tree/'c2_product_runtime.c').relative_to(ROOT));cmd[cmd.index('-o')+1]=str(obj.relative_to(ROOT));cmd+=['-fno-lto']
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/label/'compile.txt';log.write_text(r.stdout+r.stderr)
        receipts.append(dict(world=label,command=cmd,exit=r.returncode,log=P.bind(log)));P.write(OUT/'compiles.json',receipts)
        assert r.returncode==0,r.stderr
        receipts[-1]['object']=P.bind(obj)
        dc=cmd.copy();i=dc.index('-o');del dc[i:i+2];dc.remove('-c');dc+=['-M','-MT','runtime']
        r=subprocess.run(dc,cwd=ROOT,capture_output=True,text=True);assert r.returncode==0
        (OUT/label/'dependencies.txt').write_text(r.stdout+r.stderr);rows=[];closure={}
        for raw in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
            p=(ROOT/raw).resolve();logical='generated/'+str(p.relative_to(tree)) if p.is_relative_to(tree) else str(p.relative_to(ROOT))
            rows.append(dict(logical=logical,binding=P.bind(p)));closure[logical]=P.bind(p)['sha256']
        closures[label]=closure;receipts[-1]['dependencies']=dict(command=dc,exit=0,inputs=rows)
        truths[label]=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        (OUT/label/'disassembly.txt').write_text(subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(obj)],text=True))
    P.write(OUT/'compiles.json',receipts)
    assert closures['before'].keys()==closures['after'].keys()
    changed=[n for n in closures['before'] if closures['before'][n]!=closures['after'][n]]
    assert set(changed)=={'generated/optional/set_b_retire_reset.c','generated/optional/set_b_retire_control.c'}
    a,b=truths['before'],truths['after'];sa={s.name:s for s in a.sections if 'SHF_ALLOC' in s.flags};sb={s.name:s for s in b.sections if 'SHF_ALLOC' in s.flags};changes=[];same=[]
    def rel(t,n):return [(r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==n]
    for n in sorted(sa.keys()|sb.keys()):
        x,y=sa.get(n),sb.get(n)
        equal=x is not None and y is not None and x.bytes==y.bytes and rel(a,n)==rel(b,n)
        if equal and x.section_type!='SHT_NOBITS':equal=a.section_bytes(n)==b.section_bytes(n)
        if equal:same.append(n)
        else:changes.append(dict(section=n,before=x.bytes if x else 0,after=y.bytes if y else 0,delta=(y.bytes if y else 0)-(x.bytes if x else 0)))
    assert {r['section'] for r in changes}<={'.lisp65_rt_c2append_retire_control','.lisp65_rt_c2append_retire_reset'}
    P.write(OUT/'native-price.json',dict(changes=changes,unchanged_allocated_sections=same,input_differences=changed,
        product_links=0,new_bss=0,new_resident_bytes=0,new_catalog_slots=0,limit='Non-LTO matched object projection; linked layout and all execution gates pending.'))

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    old,new=parked_sources();lisp_projection(old,new);native_projection(new)
    P.write(OUT/'receipt.json',dict(status='PASS: PARKED REPAIR; HOST LISP AND MATCHED NATIVE OBJECT PRICES',
        driver=P.bind(Path(__file__)),authority=S.require_auth(),patch=P.bind(OUT/'authored.patch'),
        seed=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),lisp_price=P.bind(OUT/'lisp-price.json'),native_price=P.bind(OUT/'native-price.json'),
        product_builds=0,product_links=0,seeds=0,device_contacts=0,host_lisp_fixture_compilations=2,native_object_compiles=2,dependency_calls=2))
    print('PASS parked repair proposal; no product changes/link',flush=True)

if __name__=='__main__':main()
