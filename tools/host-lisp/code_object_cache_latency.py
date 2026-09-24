"""Explicit optimization attribution; retains the stationary gate and every sample.

The stationary gate intentionally stops on large negative as well as positive
changes. This successor does not relabel that receipt: it admits an intentional
cache improvement only with identical repeats, equal lookup/GC populations,
fewer directory reads in every bracket, and no slower bracket. No GC exclusion.
"""
from collections import Counter
from pathlib import Path
import copy
import json
from elf_truth import ElfTruth
import native_cycle_stationary as N
from code_object_cache_producer import ROOT, HERE, bind

NAMES=('c2_product_entry_record','c2_stream_c2d_read','c2_stream_c2d_write','gc_collect')

def qualify(a,b):
    assert a['lookups']==b['lookups']>0
    assert a['writes']==b['writes']==0
    assert a['gc']==b['gc']
    assert 0<a['reads']-b['reads']<=a['lookups']
    assert 0<b['cycles']<a['cycles']


def main():
    inputs=[];worlds={};results={}
    def load(path):
        p=ROOT/path;inputs.append(bind(p));return json.loads(p.read_text())
    def pc(binding):
        p=N.checked_binding(binding);inputs.append(bind(p))
        return Counter({int(a[1]):int(a[2]) for line in p.read_text().splitlines() if (a:=line.split())[0]=='P'})
    def sample(row,index):
        elf=N.checked_binding(row['ELF']);key=str(elf)
        if key not in worlds:
            inputs.append(bind(elf));t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
            worlds[key]={n:t.symbol(n).value for n in NAMES}
        pair=row['pc_samples'][index];delta=pc(pair['after']);delta.subtract(pc(pair['before']))
        assert all(n>=0 for n in delta.values())
        count=[delta[worlds[key][n]] for n in NAMES]
        return dict(zip(('lookups','reads','writes','gc'),count),cycles=row['cycle_deltas'][index])
    for mode in ('natural','equal-phase'):
        receipt=load(f'build/code-object-cache-native-{mode}-r1/receipt.json')
        N.validate(receipt['rows'],receipt)
        assert receipt['status']=='HALT_ATTRIBUTION'
        lanes={}
        for cap in (1,8):
            pair={r['world']:r for r in receipt['rows'] if r['batch_cap']==cap}
            for row in pair.values():N.verify_completion(row);N.verify_trace(row)
            samples=[]
            for i in range(len(pair['baseline']['cycle_deltas'])):
                a,b=(sample(pair[role],i) for role in ('baseline','candidate'))
                qualify(a,b);samples.append(dict(index=i,baseline=a,candidate=b,reads_avoided=a['reads']-b['reads']))
            assert receipt['lanes'][str(cap)]['excluded_sample_indices']==[]
            lanes[str(cap)]=dict(samples=samples,all_samples_ratio=receipt['ratios'][str(cap)],excluded_samples=[])
        results[mode]=lanes
    repeat=load('build/code-object-cache-native-natural-r2/receipt.json')
    first=load('build/code-object-cache-native-natural-r1/receipt.json')
    N.validate(repeat['rows'],repeat)
    for a,b in zip(first['rows'],repeat['rows']):
        assert (a['world'],a['batch_cap'],a['cycle_deltas'])==(b['world'],b['batch_cap'],b['cycle_deltas'])
        N.verify_completion(b);N.verify_trace(b)
    mutations=[]
    a,b=[results['natural']['8']['samples'][0][r] for r in ('baseline','candidate')]
    for name,field,value in [('slower','cycles',a['cycles']+1),('no-read-saving','reads',a['reads']),('different-lookups','lookups',a['lookups']-1),('hidden-gc','gc',a['gc']+1),('write','writes',1)]:
        mutant=copy.deepcopy(b);mutant[field]=value
        try:qualify(a,mutant)
        except AssertionError:mutations.append(name)
        else:raise AssertionError('control survived: '+name)
    value=dict(status='PASS: ATTRIBUTED CACHE OPTIMIZATION; ALL SAMPLES RETAINED',
        lanes=results,natural_repeat_cycles_identical=True,mutations_rejected=mutations,
        inputs=inputs+[bind(Path(__file__))],
        claim='Emulated CPU/DMA input completion; same lookup and GC calls, fewer directory reads. Not a physical-keyboard measurement or exact per-instruction cycle decomposition.',
        predecessor_status='HALT_ATTRIBUTION receipts preserved unchanged')
    target=HERE/'latency-qualification.json';assert not target.exists();target.write_text(json.dumps(value,indent=2)+'\n')
    print(value['status']);print({m:{k:v['all_samples_ratio'] for k,v in rows.items()} for m,rows in results.items()})
if __name__=='__main__':main()
