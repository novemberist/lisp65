"""Measured anchor record traffic, priced from frozen r3 lookup costs; no product build."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2]
H=ROOT/'build/anchor-cache-projection-r1'
R6=ROOT/'build/input-cost-attribution-r6'
NAT=ROOT/'build/input-cost-natural-anchor-final-r1'

def bind(p):
    p=p.resolve()
    with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=digest)

def snap(binding):
    result=Counter();valid=False
    for line in N.checked_binding(binding).read_text().splitlines():
        w=line.split()
        if w[0]=='K':
            assert int(w[1])==0 and int(w[4])==int(w[5])==0
            valid=True
        if w[0] in ('P','G'): result[(w[0],int(w[1]))]=int(w[2])
    assert valid
    return result

def main():
    inputs=[]
    def load(p):
        inputs.append(bind(p));return json.loads(p.read_text())
    measured=load(NAT/'receipt.json')
    assert measured['status'].startswith('PASS') and measured['excluded_samples']==0
    identity=load(H/'instrument.json');world=identity['worlds'][0]
    for key in ('ELF','medium','binary'): inputs.append(bind(N.checked_binding(world[key])))
    t=ElfTruth.read(N.checked_binding(world['ELF']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    addresses={name:t.symbol(name).value for name in ('c2_product_entry_record','c2_stream_c2d_read','c2_stream_c2d_write','gc_collect')}
    prior=load(ROOT/'build/dirty-anchor-native-natural-r1/receipt.json')
    old={r['batch_cap']:r for r in prior['rows'] if r['world']=='candidate'}
    calibration=load(R6/'attribution.json')
    cal=[]
    for role in ('baseline','candidate'):
        rows=[r for r in calibration['rows'] if (r['world'],r['lane'],r['cap'])==(role,'REPL',1)]
        assert len(rows)==40
        cal.append(dict(world=role,lookups=sum(r['native_calls']['c2_product_entry_record'] for r in rows),
            reads=sum(r['native_calls']['c2_stream_c2d_read'] for r in rows),
            lookup_cycles=sum(r['classes']['code_lookup'] for r in rows)))
    assert [r['lookups'] for r in cal]==[37277,37277]
    assert [r['reads'] for r in cal]==[62162,32912]
    price=(cal[0]['lookup_cycles']-cal[1]['lookup_cycles'])/37277
    read_price=(62162-32912)/37277
    assert round(cal[0]['lookup_cycles']/37277)==1853 and round(cal[1]['lookup_cycles']/37277)==1310
    sensitivity=load(R6/'projection.json')
    allowance={r['cap']:r['overhead_envelope']/r['keys'] for r in sensitivity['rows']}
    details=[];lanes=[]
    for row in measured['rows']:
        N.verify_trace(row);cap=row['batch_cap']
        assert row['characters']==40 and len(row['pc_samples'])==len(row['cycle_deltas'])==40//cap
        assert row['cycle_deltas']==old[cap]['cycle_deltas'] and row['gc_samples']==old[cap]['gc_samples']
        totals=Counter()
        for index,(pair,cycles) in enumerate(zip(row['pc_samples'],row['cycle_deltas'])):
            a,b=snap(pair['before']),snap(pair['after']);delta=b.copy();delta.subtract(a)
            assert all(n>=0 for n in delta.values())
            values={name:delta[('P',pc)] for name,pc in addresses.items()}
            assert values['c2_stream_c2d_write']==0
            totals.update(values)
            details.append(dict(cap=cap,index=index,keys=cap,cycles=cycles,
                lookups=values['c2_product_entry_record'],reads=values['c2_stream_c2d_read'],
                writes=values['c2_stream_c2d_write'],GC=values['gc_collect'],lookup_cycles=delta[('G',1)]))
            inputs.extend([bind(N.checked_binding(pair['before'])),bind(N.checked_binding(pair['after']))])
        assert totals['gc_collect']==1
        keys=40;lookups=totals['c2_product_entry_record']/keys;reads=totals['c2_stream_c2d_read']/keys
        cycles=row['total_cycles']/keys;gross=lookups*price
        scenarios=[]
        for name,fraction,extra in [('nominal',1,0),('full-saving-plus-prior-allowance',1,allowance[cap]),
                                    ('half-saving-plus-prior-allowance',.5,allowance[cap])]:
            saved=gross*fraction-extra
            scenarios.append(dict(name=name,saving_fraction=fraction,added_cycles_per_key=extra,
                saved_cycles_per_key=saved,saved_ms_per_key=saved/40500,
                projected_cycles_per_key=cycles-saved,ratio=(cycles-saved)/cycles,gain_fraction=saved/cycles))
        lanes.append(dict(cap=cap,brackets=40//cap,keys=keys,cycles_per_key=cycles,
            lookups=totals['c2_product_entry_record'],lookups_per_key=lookups,
            reads=totals['c2_stream_c2d_read'],reads_per_key=reads,
            lookup_cycles_per_key=sum(r['lookup_cycles'] for r in details if r['cap']==cap)/keys,
            projected_avoided_reads_per_key=lookups*read_price,
            projected_reads_per_key=reads-lookups*read_price,
            rounded_543_saved_cycles_per_key=lookups*543,GC=1,scenarios=scenarios))
    assert len(details)==45
    for name in ('verification.json','selftest.json','instrument.json','source-audit.json'):
        load(R6/name)
    assert not subprocess.check_output(['git','diff','HEAD','--','src','lib'],cwd=ROOT)
    result=dict(status='PASS: HOST-ONLY REMAINING CACHE PROJECTION',authority='a982b117',
        accepted_world='dirty-anchor Final 1e210f3f',addresses=addresses,calibration=cal,
        cycles_saved_per_lookup=price,reads_saved_per_lookup=read_price,
        sensitivity_allowance_cycles_per_key=allowance,lanes=lanes,brackets=details,
        exact_cycle_neutrality_brackets=45,excluded_samples=0,product_builds=0,observer_builds=0,
        links=0,seeds=0,device_contacts=0,product_source_diff_empty=True,
        threshold=.15,threshold_met=lanes[0]['scenarios'][0]['gain_fraction']>=.15,
        assumptions=['The r3 single-key per-lookup mean saving and avoided reads transfer to both anchor lanes; no anchor-plus-cache product is built or measured.',
            'Exact measured calibration is used; 1853 to 1310 and 543 cycles are rounded display values.',
            'The unchanged prior added-op allowances are carried as sensitivity charges, not claimed incremental anchor/cache costs or statistical bounds.',
            'The half-saving scenario retains that same full allowance, as in 741f7361.',
            'No GC, rendering or polling saving is credited; all brackets and both collections are retained.',
            'Milliseconds are cycle equivalents at 40.5 MHz, not physical-device wall time.'],inputs=inputs+[bind(Path(__file__))])
    out=H/'projection.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    with (H/'per-bracket.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
    print(json.dumps({k:result[k] for k in ('cycles_saved_per_lookup','reads_saved_per_lookup','lanes','threshold_met')},indent=2))

if __name__=='__main__':main()
