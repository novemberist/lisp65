"""Aggregate executed Seed evidence; does not build or weaken a wall."""
from collections import Counter
import json
from pathlib import Path
from elf_truth import ElfTruth
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[2]

def bind(p):
    raw=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=sha256(raw).hexdigest())

H=ROOT/'build/put-kit-r4'


def main():
    inputs=[]
    def load(name):
        p=ROOT/name; inputs.append(bind(p)); return json.loads(p.read_text())
    price=load('build/put-kit-product-r4/wplto/put-kit-seed-price.json')
    assert price['candidate']['text_bytes']-price['predecessor']['text_bytes']==493
    assert load('build/put-kit-native-boot-r2/qualification.json')['status'].startswith('PASS')
    assert load('build/put-kit-usage-r1/receipt.json')['status']=='PASS'
    lanes={}
    for mode in ('natural','equal-phase'):
        row=load(f'build/put-kit-native-{mode}-r1/receipt.json')
        assert row['status']=='PASS' and max(row['ratios'].values())<=1.02
        lanes[mode]=row['ratios']
    intern={r:load(f'build/put-kit-intern-lane-{r}-r1/receipt.json') for r in ('baseline','candidate')}
    keys=lambda d:[(x['name'],x['phase'],x['before'],x['after'],x['result']) for x in d['rows']]
    assert all(x['status']=='PASS' for x in intern.values())
    assert keys(intern['baseline'])==keys(intern['candidate'])
    intern_ratios={phase:sum(x['cycles'] for x in intern['candidate']['rows'] if x['phase']==phase)/
                        sum(x['cycles'] for x in intern['baseline']['rows'] if x['phase']==phase)
                   for phase in ('new','existing')}
    assert max(intern_ratios.values())<=1.02
    gc={}
    histograms={}
    for role in ('baseline','candidate'):
        gc[role]={}
        for trial in (0,3):
            row=load(f'build/put-kit-gc-equal-{role}-{trial}/receipt.json')
            forced=[r for r in row['collections'] if r['phase']=='forced']
            assert len(forced)==1 and row['natural_count']==1 and not row['excluded_collections']
            gc[role][trial]=forced[0]
        elf=ROOT/row['ELF']['path']
        assert bind(elf)['sha256']==row['ELF']['sha256']
        t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        def read(phase):
            p=ROOT/f'build/put-kit-gc-equal-{role}-3/pc-1-{phase}.txt'
            inputs.append(bind(p))
            return Counter({int(a[1]):int(a[2]) for line in p.read_text().splitlines()
                            if (a:=line.split())[0]=='P'})
        counts=read('after'); counts.subtract(read('before'))
        normalized=Counter()
        for pc,count in counts.items():
            if not count: continue
            matches=[s for s in t.symbols if s.symbol_type=='Function' and s.value<=pc<s.value+s.bytes]
            # Same-address aliases are canonicalized by name; mapped windows
            # not executed during collection are absent from this population.
            if matches:
                s=min(matches,key=lambda s:(s.bytes,s.name))
                key=(s.name,pc-s.value)
            else: key=('absolute',pc)
            normalized[key]+=count
        histograms[role]=normalized
    for trial in (0,3):
        a,b=[gc[r][trial] for r in ('baseline','candidate')]
        for field in ('graph','root_bytes','symbols','gc_frozen'):
            assert a['entry_state'][field]==b['entry_state'][field],field
        assert a['marked']==b['marked']
    assert gc['baseline'][3]['cycles']==gc['candidate'][3]['cycles']
    assert histograms['baseline']==histograms['candidate'], 'GC instruction population changed'
    for name in ('extended-resident.json','packed-receipt.json'):
        load('build/put-kit-seed-medium-r1/'+name)
    for p in sorted((ROOT/'tools/host-lisp').glob('put_kit*.py')):
        inputs.append(bind(p))
    result=dict(status='PASS: EXECUTED PUT-KIT SEED',authority='3bd13625',inputs=inputs,
                price=price['candidate'],ordinary_text_cost=493,
                native_lanes=lanes,intern_ratios=intern_ratios,
                matched_gc=dict(trials={str(n):{r:gc[r][n]['cycles'] for r in gc} for n in (0,3)},
                    marked_cells=gc['candidate'][3]['marked']['count'],
                    matched_trace_instructions=sum(histograms['candidate'].values()),
                    normalized_pc_population_identical=True,
                    note='First pair retained (+110 raw cycles); PC-instrumented pair equal in cycles and instruction counts. No new tolerance or placement-cost acceptance.'),
                budget=dict(seed=1,finale=0,link=0),device_contacts=0)
    raw=json.dumps(result,indent=2)+'\n'
    # r1 aggregate above was an unsealed local summary. This is its explicit
    # complete-input successor, not an overwrite of that receipt.
    for target in (H/'seed-qualification-bound.json', ROOT/'config/put-kit-seed.json'):
        if target.exists(): assert target.read_text()==raw
        else: target.write_text(raw)
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},indent=2))


if __name__=='__main__': main()
