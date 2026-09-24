"""Record the extra live anchor root without weakening the matched-GC gate."""
from pathlib import Path
from collections import Counter
import json
from dirty_anchor_producer import ROOT,HERE,bind
from elf_truth import ElfTruth
import native_cycle_stationary as N

def main():
    rows={};counts={};truths={};inputs=[]
    for role in ('baseline','candidate'):
        h=ROOT/f'build/dirty-anchor-gc-equal-{role}-3';p=h/'receipt.json';d=json.loads(p.read_text());inputs.append(bind(p))
        assert d['natural_count']==d['forced_count']==1 and not d['excluded_collections']
        rows[role]=next(r for r in d['collections'] if r['phase']=='forced')
        elf=N.checked_binding(d['ELF']);inputs.append(bind(elf));truths[role]=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        def pc(phase):
            p=h/f'pc-1-{phase}.txt';inputs.append(bind(p));return Counter({int(a[1]):int(a[2]) for l in p.read_text().splitlines() if (a:=l.split())[0]=='P'})
        c=pc('after');c.subtract(pc('before'));assert all(v>=0 for v in c.values());counts[role]=c
    a,b=[rows[k] for k in ('baseline','candidate')];ea,eb=[r['entry_state'] for r in (a,b)]
    assert ea['graph']['nodes']==eb['graph']['nodes'] and a['marked']==b['marked']
    assert ea['shadow_count']==39 and eb['shadow_count']==40
    assert ea['graph']['roots']==eb['graph']['roots'][:22]+eb['graph']['roots'][23:]
    assert eb['graph']['roots'][22]==eb['graph']['roots'][20]=={'ref':35}
    assert ea['root_bytes']==eb['root_bytes'][:88]+eb['root_bytes'][92:]
    for field in ('symbols','gc_frozen','shadow_cells'):assert ea[field]==eb[field]
    diff=counts['candidate'].copy();diff.subtract(counts['baseline']);delta=[];owners=Counter()
    for pc,n in sorted(diff.items()):
        if not n:continue
        assert n==1
        t=truths['candidate'];syms=[s for s in t.symbols if s.symbol_type=='Function' and s.value<=pc<s.value+s.bytes];s=min(syms,key=lambda s:(s.bytes,s.name))
        assert s.name in ('gc_collect','gc_mark1');owners[s.name]+=n
        old=truths['baseline'].symbol(s.name);assert (old.value,old.bytes,old.section)==(s.value,s.bytes,s.section)
        bodies=[]
        for t,x in ((truths['baseline'],old),(truths['candidate'],s)):
            sec=t.section(x.section);bodies.append(t.section_bytes(sec.name)[x.value-sec.address:x.value-sec.address+x.bytes])
        assert bodies[0]==bodies[1]
        delta.append(dict(pc=pc,function=s.name,offset=pc-s.value,count=n))
    assert sum(owners.values())==101 and dict(owners)=={'gc_collect':22,'gc_mark1':79}
    fraction=(b['cycles']-a['cycles'])/a['cycles'];assert b['cycles']-a['cycles']==318
    result=dict(status='HALT: MATCHED-GC ROOT POPULATION DIFFERS',authority='d0f00e98',
        measured_cycles={k:v['cycles'] for k,v in rows.items()},delta_cycles=318,fraction=fraction,
        roots={'baseline':39,'candidate':40,'added_index':22,'duplicate_of_index':20,'canonical_reference':35,'raw_root':eb['root_bytes'][88:92]},
        unique_graph_nodes=len(ea['graph']['nodes']),canonical_nodes_identical=True,marked_identical=True,marked_cells=a['marked']['count'],
        symbols_and_frozen_cells_identical=True,extra_instructions=101,extra_by_function=dict(owners),pc_delta=delta,
        native_GC_function_bytes_and_addresses_identical=True,collections_each={'natural':1,'forced':1},excluded_collections=0,
        interpretation='The fifth %rl-put argument adds one duplicate live root. Reachable nodes and marks are identical, but shadow roots and executed instruction populations are not. This is additional marking work, not code-placement timing; the 0.05% placement allowance is not used.',
        limitation='The +318 cycles are measured; the PC delta identifies 101 extra instructions, not an exact CPU/DMA/IRQ cycle decomposition.',
        stopped_before=['usage','full check-source','Final','product link'],budget_consumed={'seed':1,'final':0,'product_link':0},
        inputs=inputs+[bind(Path(__file__)),bind(ROOT/'tools/host-lisp/dirty_anchor_gc.py'),bind(HERE/'gc-qualification.log')])
    p=HERE/'gc-halt.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['roots'],'+318 cycles, +101 instructions')
if __name__=='__main__':main()
