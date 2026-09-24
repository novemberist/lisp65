"""Owner-bound natural-lane gate, retaining every bracket and collection."""
from pathlib import Path
from collections import Counter
import copy,json
import native_cycle_stationary as N
from elf_truth import ElfTruth
from dirty_anchor_producer import ROOT,HERE,bind

def gate(ratio,screen_equal,gc):
    assert 0<ratio<=0.70,'natural single-key lane exceeds 0.70'
    assert screen_equal,'screen-write population changed'
    assert gc=={'baseline':1,'candidate':1},'one executed GC per lane required'

def main():
    p=ROOT/'build/dirty-anchor-native-natural-r1/receipt.json';r=json.loads(p.read_text())
    N.validate(r['rows'],r)
    inputs=[bind(p)];lanes={}
    def counts(binding):
        p=N.checked_binding(binding);inputs.append(bind(p))
        return Counter({(a[0],int(a[1])):int(a[2]) for line in p.read_text().splitlines() if (a:=line.split())[0] in ('P','D')})
    for cap in (1,8):
        pair={x['world']:x for x in r['rows'] if x['batch_cap']==cap};observed={}
        for role,row in pair.items():
            N.verify_completion(row);N.verify_trace(row)
            t=ElfTruth.read(N.checked_binding(row['ELF']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
            gc=t.symbol('gc_collect').value;samples=[]
            for item in row['pc_samples']:
                d=counts(item['after']);d.subtract(counts(item['before']));assert all(v>=0 for v in d.values())
                samples.append(dict(gc=d['P',gc],screen_writes=d['D',11]))
            observed[role]=dict(samples=samples,cycles=sum(row['cycle_deltas']),gc=sum(s['gc'] for s in samples))
        screen_equal=[s['screen_writes'] for s in observed['baseline']['samples']]==[s['screen_writes'] for s in observed['candidate']['samples']]
        gc={k:v['gc'] for k,v in observed.items()};ratio=observed['candidate']['cycles']/observed['baseline']['cycles']
        assert screen_equal and gc=={'baseline':1,'candidate':1}
        assert r['lanes'][str(cap)]['excluded_sample_indices']==[]
        if cap==1:gate(ratio,screen_equal,gc)
        lanes[str(cap)]=dict(ratio=ratio,worlds=observed,excluded_samples=[])
    controls=[]
    for name,args in [('above-wall',(0.700001,True,{'baseline':1,'candidate':1})),('screen-write-change',(0.6,False,{'baseline':1,'candidate':1})),('missing-collection',(0.6,True,{'baseline':1,'candidate':0}))]:
        try:gate(*args)
        except AssertionError:controls.append(name)
        else:raise AssertionError('negative control survived')
    value=dict(status='PASS: NATURAL SINGLE-KEY <=0.70',authority='d0f00e98',lanes=lanes,mutations_rejected=controls,
        predecessor_stationary_status=r['status'],explanation='Intentional anchored traversal saving. Stationary HALT_ATTRIBUTION remains unchanged; this is the commissioned optimization gate, with all samples and GC included.',inputs=inputs+[bind(Path(__file__))])
    out=HERE/'latency-qualification.json';assert not out.exists();out.write_text(json.dumps(value,indent=2)+'\n');print(value['status'],{k:v['ratio'] for k,v in lanes.items()})
if __name__=='__main__':main()
