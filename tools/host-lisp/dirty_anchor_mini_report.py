"""Report both IDE lanes without imposing an uncommissioned speed gate."""
import json
from collections import Counter
from pathlib import Path
from dirty_anchor_producer import ROOT,HERE,bind
from elf_truth import ElfTruth
import native_cycle_stationary as N

def main():
    rows={};inputs=[]
    for role in ('baseline','candidate'):
        p=ROOT/f'build/dirty-anchor-mini-r1/native-entry-probe-{role}/receipt.json';d=json.loads(p.read_text());inputs.append(bind(p))
        assert d['status'].startswith('PASS') and not d.get('error') and len(d['keys'])==17
        t=ElfTruth.read(N.checked_binding(d['ELF']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj');gc=t.symbol('gc_collect').value
        def snap(b):
            p=N.checked_binding(b);inputs.append(bind(p));return Counter({(a[0],int(a[1])):int(a[2]) for l in p.read_text().splitlines() if (a:=l.split())[0] in ('P','D')})
        def delta(a,b):
            c=snap(b);c.subtract(snap(a));assert all(v>=0 for v in c.values());return dict(gc=c['P',gc],screen_writes=c['D',11])
        samples=[]
        for k in d['keys']:
            assert all(b-a==1 for a,b in zip(k['counters_before'],k['counters_after']))
            samples.append(dict(tag=k['tag'],cycles=k['cycles'],service_cycles=k['service_cycles'],row=k['row'],**delta(k['before_pc'],k['after_pc'])))
        rows[role]=dict(mx_cycles=d['open_cycles'],mx=delta(d['ready_pc'],d['open_pc']),samples=samples,
            typing_cycles=sum(k['cycles'] for k in samples[1:]),typing_service_cycles=sum(k['service_cycles'] for k in samples[1:]))
    for a,b in zip(rows['baseline']['samples'],rows['candidate']['samples']):
        assert a['tag']==b['tag'] and a['row']==b['row'] and a['screen_writes']==b['screen_writes']
    for r in rows.values():assert r['mx']['gc']==0 and r['samples'][0]['gc']==0 and sum(k['gc'] for k in r['samples'][1:])==1
    result=dict(status='PASS: PAIRED IDE ROWS, REPORT ONLY',authority='d0f00e98',rows=rows,ratios={k:rows['candidate'][k]/rows['baseline'][k] for k in ('mx_cycles','typing_cycles','typing_service_cycles')},inputs=inputs+[bind(Path(__file__))])
    p=HERE/'mini-qualification.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['ratios'])
if __name__=='__main__':main()
