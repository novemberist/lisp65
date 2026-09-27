"""Execute the parked resolver's complete world gate on captured directories."""
from pathlib import Path
import sys
sys.setrecursionlimit(12000)
import set_b_producer as P
import bytecode_p0_stdlib as L
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-world-checks-r1'
PROP=ROOT/'build/set-b-load-repair-proposal-r5'

def main():
    OUT.mkdir(exist_ok=False);C,B=L.C,L.B
    def forms(s):return {f[1]:f for f in C.parse_all(s) if isinstance(f,list) and len(f)>=4 and f[0]=='defun'}
    fs=forms((PROP/'candidate/lib/stdlib-require.lisp').read_text());common=forms((ROOT/'lib/prelude-m1.lisp').read_text())
    fs.update({n:common[n] for n in ('nth','1+','1-')})
    h=C.prepare_heap(sorted(fs));codes={}
    for n,f in fs.items():
        name,code,helpers=C.compile_top_form_with_helpers(f,h,strict_arity=True,abi_profile='dialect-v2',prebuilt_primitives=True)
        assert name==n and not helpers;codes[n]=code
    class VM(B.P0VM):
        def _callprim(self,pid,argc,stack,**kw):
            if pid!=67:return super()._callprim(pid,argc,stack,**kw)
            a=[B.fixval(x) for x in self._pop_args(argc,stack)];self.reads+=1
            if argc==1:
                # Exact Seed's native owner table, not a widened 64K arena.
                owners=[60758,64,2048,4096,1536,4,4096,1648]
                return B.mkfix(1 if a[0]==16 else (owners[a[0]//2]>>(8*(a[0]%2)))&255)
            assert argc==2 and all(0<=v<=255 for v in a)
            return B.mkfix(self.raw[a[0]+256*a[1]])
    rows=[]
    def run(label,raw,want):
        heap=h.clone();directory={heap.intern(n):c for n,c in codes.items()}
        vm=VM(heap=heap,directory=directory,max_steps=4000000,abi_profile='dialect-v2',abi_ledger=P.load(ROOT/'config/bytecode-abi-ledger.json'));vm.raw=bytes(raw);vm.reads=0
        got=vm.run(directory[heap.intern('%require-world')],[B.NIL])
        if got==B.NIL:actual=None
        else:
            low=heap.cell(heap.cell(got).b).a
            actual=B.fixval(heap.cell(low).a)+256*B.fixval(heap.cell(low).b)
        rows.append(dict(case=label,expected=want,actual=actual,steps=vm.steps,c2d_reads=vm.reads));P.write(OUT/'rows.json',rows)
        assert actual==want,rows[-1]
    root=ROOT/'build/set-b-load-attribution-r1'
    for n in (0,1,2):run(f'captured-definitions-{n}',(root/f'definitions-{n}/before-load-c2d.bin').read_bytes(),50691+10*n)
    raw=bytearray((root/'definitions-2/before-load-c2d.bin').read_bytes())
    # Both user entry rows retired, last image removed; code stays charged.
    retired=bytearray(raw);retired[12:14]=(8).to_bytes(2,'little');retired[0x130:0x150]=bytes(32)
    for i in (804,805):retired[0x830+i*10]=255
    run('retired-tail-after-last-image-removed',retired,50711)
    for label,off,value in [('overlap',0x130+18,2),('reserved',0x130+1,1),('generation',0x130+4,2),('source-index',0x130+2,3),('zero-entry-size',0x830+805*10+4,0)]:
        bad=bytearray(raw);bad[off]=value;run(label,bad,None)
    bad=bytearray(raw);bad[0x830+805*10+2:0x830+805*10+4]=(60750).to_bytes(2,'little')
    run('entry-end-crosses-60758-owner-boundary',bad,None)
    P.write(OUT/'receipt.json',dict(status='PASS: 10 COMPLETE WORLD-GATE HOST ROWS',driver=P.bind(Path(__file__)),candidate=P.bind(PROP/'candidate/lib/stdlib-require.lisp'),rows=P.bind(OUT/'rows.json'),
        limits='Host compiler/reference VM with exact raw snapshots and read-only primitive seam. No media I/O, native timing, fast-note sequence or product execution claimed.',product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PASS 10 full world-gate rows')

if __name__=='__main__':main()
