"""Matched live-state and full instruction-population GC check: anchor Final (baseline) vs repair Seed.

Baseline is the accepted anchor collection (its forced cycles equal the anchor
card's accepted 5,383,354).  The unforced companion is reported with its delta."""
from collections import Counter
import json
from pathlib import Path
from elf_truth import ElfTruth
from retained_callable_repair_r2_producer import ROOT,HERE,bind
import native_cycle_stationary as N

def main():
    inputs=[];rows={};populations={}
    for role in ('baseline','candidate'):
        out=ROOT/f'build/retained-callable-repair-r2-gc-equal-{role}-1'
        p=out/'receipt.json';inputs.append(bind(p));r=json.loads(p.read_text())
        assert r['natural_count']==1 and r['forced_count']==1 and not r['excluded_collections']
        rows[role]=next(x for x in r['collections'] if x['phase']=='forced')
        elf=N.checked_binding(r['ELF']);inputs.append(bind(elf));t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        def pc(phase):
            p=out/f'pc-1-{phase}.txt';inputs.append(bind(p))
            return Counter({int(a[1]):int(a[2]) for line in p.read_text().splitlines() if (a:=line.split())[0]=='P'})
        counts=pc('after');counts.subtract(pc('before'));normalized=Counter()
        for pc,count in counts.items():
            assert count>=0
            if not count:continue
            matches=[s for s in t.symbols if s.symbol_type=='Function' and s.value<=pc<s.value+s.bytes]
            s=min(matches,key=lambda s:(s.bytes,s.name)) if matches else None
            normalized[(s.name,pc-s.value) if s else ('absolute',pc)]+=count
        populations[role]=normalized
    a,b=(rows[r] for r in ('baseline','candidate'))
    for field in ('graph','root_bytes','symbols','gc_frozen'):
        assert a['entry_state'][field]==b['entry_state'][field],field
    assert a['marked']==b['marked'] and populations['baseline']==populations['candidate']
    # Existing prep's equal-state GC materiality is 0.05%, not the 2% input wall.
    fraction=abs(b['cycles']-a['cycles'])/a['cycles'];assert fraction<=0.0005
    warm={}
    for role in ('baseline','candidate'):
        r=json.loads((ROOT/f'build/retained-callable-repair-r2-gc-equal-{role}-1/receipt.json').read_text())
        warm[role]=next(x for x in r['collections'] if x['phase']=='warmup')
    assert warm['baseline']['marked']['count']==warm['candidate']['marked']['count']
    result=dict(status='PASS: MATCHED GC WITHIN EXISTING 0.05% MATERIALITY',
        forced_delta=b['cycles']-a['cycles'],
        warmup=dict(baseline=warm['baseline']['cycles'],candidate=warm['candidate']['cycles'],
                    delta=warm['candidate']['cycles']-warm['baseline']['cycles'],
                    marked_cells=warm['candidate']['marked']['count']),
        anchor_accepted_forced_cycles=5383354,
        cycles={r:v['cycles'] for r,v in rows.items()},fraction=fraction,ceiling=0.0005,
        instruction_population_identical=True,instructions=sum(populations['candidate'].values()),
        live_graph_and_marks_identical=True,marked_cells=b['marked']['count'],collections_each=2,
        attribution='Same live input graph and normalized executed PC population. All observed collections retained; the receipt does not assert a cause for any residual cycle difference.',
        limitation='Instruction population and measured cost, not an exact branch-outcome cycle decomposition.',
        inputs=inputs+[bind(ROOT/'docs/planning/code-object-cache-prep.md'),bind(ROOT/'build/dirty-anchor-card-r1/gc-accepted.json'),bind(Path(__file__))])
    p=HERE/'gc-qualification.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['cycles'],fraction)
if __name__=='__main__':main()
