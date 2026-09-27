"""Run the real indexed resolver and fast-note with exact media/snapshot replay.

Prim18 is an explicitly limited append fixture: it relocates a published
library's captured row populations. It does not emulate native transactions
or execute library bodies. Every source span and identity comes from Seed5.
"""
from pathlib import Path
import sys
sys.setrecursionlimit(12000)
import struct
import traceback
from set_b_host_snapshot_heap_r2_20260926 import SnapshotHeap, selftest
import set_b_producer as P
import bytecode_p0 as B
import c2_link75_real_require_resolver_host as H
import c2_require_resolver_gate as I
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-index-r3'
PACK=ROOT/'build/set-b-load-preflight-pack-r1'
MEDIA=ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'
SNAPS=ROOT/'build/set-b-load-attribution-r1'
u=lambda b,a:int.from_bytes(b[a:a+2],'little')
def put(b,a,v):struct.pack_into('<H',b,a,v)

def main():
    OUT.mkdir(exist_ok=False);assert selftest()==3
    media=MEDIA.read_bytes();locators,payloads=H.media_locators(media)
    index=I.decode_index(payloads['l65index']);indexed={r['name']:r for r in index}
    H.STDLIB=PACK/'candidate/stdlib-p0.manifest.json'
    elf=ROOT/'build/set-b-product-r5/wplto/resident-island-seed.prg.elf'
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    sym=truth.symbol('c2_resolver_owner_parts');sec=next(x for x in truth.sections if x.index==sym.section_index)
    raw=truth.section_bytes(sec.name)[sym.value-sec.address:sym.value-sec.address+sym.bytes];parts=[u(raw,a) for a in range(0,len(raw),2)]
    templates={}
    for name,folder,label,slot in [('place','definitions-0','before-load',6),('string-extra','definitions-0','before-load',7),('defstruct','definitions-1','after-load',9)]:
        cp=SNAPS/folder/(label+'-c2d.bin');bp=SNAPS/folder/(label+'-bank2.bin');c=cp.read_bytes();code=bp.read_bytes();row=c[48+slot*32:80+slot*32]
        assert int.from_bytes(row[28:32],'little')==indexed[name]['combined_crc32']
        templates[name]=(c,code,row)
    class Trace:
        def __init__(self):self.scans=[];self.calls={}
        def enter(self,name,code,args):
            self.calls[name]=self.calls.get(name,0)+1
            if name=='%require-charged-front' and B.fixval(args[0])==0:self.scans.append(B.fixval(args[1]))
    class VM(B.P0VM):
        def __init__(self,bound,c,mutation):
            self.observer=Trace()
            super().__init__(heap=bound.heap,directory=bound.directory,macro_symbols=bound.macros,code_names=bound.code_names,
                max_steps=15000000,abi_profile='dialect-v2',abi_ledger=bound.ledger,trace=self.observer)
            self.heap=SnapshotHeap(self.heap,lambda: self.directory)
            self.c=bytearray(c);self.mutation=mutation;self.appends=[];self.reads=0;self.sectors=0
        def _disk_read_sector_impl(self,t,s):
            self.sectors+=1;self.disk_buf=list(H.D81.get_sector(media,t,s));return True
        def _callprim(self,pid,argc,stack,**kw):
            if pid not in (18,67):return super()._callprim(pid,argc,stack,**kw)
            args=self._pop_args(argc,stack)
            if pid==67:
                a=[B.fixval(x) for x in args];self.reads+=1
                if argc==1:return B.mkfix(1 if a[0]==16 else parts[a[0]])
                assert argc==2 and all(0<=v<=255 for v in a)
                return B.mkfix(self.c[a[0]+256*a[1]])
            if argc in (0,1):return B.NIL
            assert argc==2
            at=tuple(B.fixval(x) for x in args);name=next((n for n in templates if locators[n]==at),None)
            assert name is not None,('unexpected publication',at)
            self.appends.append(name)
            if self.mutation=='success-without-publication':return self.heap.t_obj
            source,code,row=templates[name];c=self.c;slot=u(c,12);ec=u(c,16);rc=u(c,20);hc=u(c,24)
            low=max(u(c,0x830+i*10+2)+u(c,0x830+i*10+4) for i in range(ec))
            olde,olde_n,oldr,oldr_n,oldh,oldh_n=[u(row,a) for a in (6,8,10,12,14,16)]
            oldbase=u(row,18);new=bytearray(row);new[2]=slot-6
            for a,v in [(6,ec),(10,rc),(14,hc),(18,low)]:put(new,a,v)
            for i in range(olde_n):
                e=bytearray(source[0x830+(olde+i)*10:0x830+(olde+i+1)*10]);e[0]=slot
                put(e,2,u(e,2)+low-oldbase);put(e,6,u(e,6)+rc-oldr)
                c[0x830+(ec+i)*10:0x830+(ec+i+1)*10]=e
            c[0x5830+rc*2:0x5830+(rc+oldr_n)*2]=source[0x5830+oldr*2:0x5830+(oldr+oldr_n)*2]
            c[0x7830+hc*2:0x7830+(hc+oldh_n)*2]=source[0x7830+oldh*2:0x7830+(oldh+oldh_n)*2]
            c[48+slot*32:80+slot*32]=new
            for a,v in [(12,slot+1),(16,ec+olde_n),(20,rc+oldr_n),(24,hc+oldh_n)]:put(c,a,v)
            if self.mutation=='wrong-published-identity':c[48+slot*32+28]^=1
            return self.heap.t_obj
    rows=[]
    def run(label,c,names,wants,mutation='none'):
        bound=H.BoundStdlib();vm=VM(bound,c,mutation);results=[]
        for name,want in zip(names,wants):
            reads=vm.reads;sectors=vm.sectors;appends=len(vm.appends)
            value=vm.run(vm.directory[bound.require_symbol],[vm.heap.string_from_text(name)])
            got=value!=B.NIL
            results.append(dict(library=name,expected=want,actual=got,steps=vm.steps,reads=vm.reads-reads,sectors=vm.sectors-sectors,appends=vm.appends[appends:],heap_cells=len(vm.heap.cells),host_collections=len(vm.heap.collections)))
            P.write(OUT/'in-progress.json',dict(case=label,results=results));assert got==want,results[-1]
        row=dict(case=label,results=results,scan_entry_counts=vm.observer.scans,fast_note_calls=vm.observer.calls.get('%require-fast-note',0),fast_loaded_calls=vm.observer.calls.get('%require-fast-loaded-p',0))
        rows.append(row);P.write(OUT/'rows.json',rows);print(label,'PASS',flush=True)
    for n in (0,1,2):
        c=(SNAPS/f'definitions-{n}/before-load-c2d.bin').read_bytes()
        run(f'definitions-{n}',c,['defstruct','defstruct'],[True,True])
    c=bytearray((SNAPS/'definitions-2/before-load-c2d.bin').read_bytes())
    for mut in ('success-without-publication','wrong-published-identity'):run(mut,c,['defstruct'],[False],mut)
    for label,at in [('live-overlap',0x130+18),('bad-generation',0x130+4)]:
        bad=bytearray(c);bad[at]=2;run(label,bad,['defstruct'],[False])
    # Source snapshots bind the two actual INIT publications. Restore just
    # their pre-INIT counters; data above the published high-water is inert.
    before=bytearray((SNAPS/'definitions-0/before-load-c2d.bin').read_bytes())
    first=templates['place'][2]
    for a,v in [(12,6),(16,u(first,6)),(20,u(first,10)),(24,u(first,14))]:put(before,a,v)
    before[48+6*32:48+8*32]=bytes(64)
    run('exact-init-libraries',before,['place','string-extra'],[True,True])
    assert all(r['results'][1]['appends']==[] and r['results'][1]['sectors']==0 for r in rows[:3])
    P.write(OUT/'receipt.json',dict(status='PASS: REAL INDEXED RESOLVER/FAST-NOTE HOST SUCCESSOR',driver=P.bind(Path(__file__)),media=P.bind(MEDIA),candidate=P.bind(H.STDLIB),rows=P.bind(OUT/'rows.json'),
        template_sources=[P.bind(SNAPS/folder/(label+'-'+region+'.bin')) for folder,label in [('definitions-0','before-load'),('definitions-1','after-load')] for region in ('c2d','bank2')],
        bound_index=index,owner_parts=parts,limits='Real canonical Lisp/index/D81 reads. Prim18 replays captured row populations with rebased offsets; conservative nonmoving host heap retains active reference-VM frames and code/global roots; no native transaction, library-body, GC or emulator timing claim.',product_builds=0,product_links=0,seeds=0,device_contacts=0,guest_launches=0))
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
