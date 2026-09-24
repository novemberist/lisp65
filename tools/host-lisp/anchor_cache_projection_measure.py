"""a982b117: reuse qualified r6 observer on accepted anchor, no native build/link."""
import json
from pathlib import Path
import sys
import traceback
import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/anchor-cache-projection-r1'
NATURAL=ROOT/'build/input-cost-natural-anchor-final-r1'

def main():
    assert not OUT.exists() and not NATURAL.exists()
    OUT.mkdir()
    parent=ROOT/'build/input-cost-attribution-r6/instrument.json'
    qualified=json.loads(parent.read_text())
    old=qualified['worlds'][0]
    binary=N.checked_binding(qualified['binary'])
    ready=json.loads((ROOT/'build/dirty-anchor-card-r1/ready-instrument.json').read_text())
    world=next(w for w in ready['worlds'] if w['role']=='candidate')
    final=ROOT/'build/dirty-anchor-final-r3/wplto/lisp65-c2-substitution-linked.prg.elf'
    assert N.bind(final)['sha256']==world['ELF']['sha256']=='6aa3040c3f6533a94c053b7b64b932be15514d856dd05f675da771a1f1ea1811'
    t=ElfTruth.read(final,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    vm=t.symbol('vm_run_inner');sec=t.section(vm.section)
    body=t.section_bytes(vm.section)[vm.value-sec.address:vm.value-sec.address+vm.bytes]
    sig=bytes.fromhex('85040604a6047c');assert body.count(sig)==1
    config=[world['vm_callprim'],vm.value+body.index(sig),t.symbol('vm_buf_bank').value,
        t.symbol('vm_buf_off').value,t.symbol('gc_collect').value,t.symbol('c2_product_entry_record').value]
    config += [t.symbol(n).value for n in ('lisp_input_event','vm_key_event','c2_kernal_event_poll','c2_kernal_input_take','vm_soft_sp')]
    cost_config=','.join(map(str,config))
    assert cost_config==old['cost_config'], 'unexpected observer address mapping'
    for key in ('entry','paused_pc','entry_code','main','signature','vm_callprim'):
        assert world[key]==old[key], key
    world=dict(world,role='anchor',ELF=N.bind(final),binary=N.bind(binary),cost_config=cost_config)
    identity=dict(authority='a982b117',worlds=[world],binary=N.bind(binary),
        parent=N.bind(parent),cost_header=qualified['cost_header'],
        driver=N.bind(Path(__file__)),product_builds=0,observer_builds=0,links=0,seeds=0)
    instrument=OUT/'instrument.json';instrument.write_text(json.dumps(identity,indent=2)+'\n')
    source=ROOT/'build/input-cost-attribution-r6/lanes.py'
    raw=source.read_text()
    raw=raw.replace("instrument=ROOT/'build/input-cost-attribution-r6/instrument.json'", "instrument=ROOT/'build/anchor-cache-projection-r1/instrument.json'")
    raw=raw.replace("[('baseline','build/put-kit-seed-medium-r1'),('candidate','build/code-object-cache-seed-medium-r1')]", "[('anchor','build/dirty-anchor-seed-medium-r1')]")
    tail="result=N.derive(rows);N.validate(rows,result)"
    assert raw.count(tail)==1
    raw=raw[:raw.index(tail)]+'''prior=json.loads((ROOT/'build/dirty-anchor-native-natural-r1/receipt.json').read_text())
old=[r for r in prior['rows'] if r['world']=='candidate']
assert len(rows)==len(old)==2
for row,previous in zip(rows,old):
    assert row['batch_cap']==previous['batch_cap']
    assert row['cycle_deltas']==previous['cycle_deltas'], 'observer cycle neutrality'
result=dict(status='PASS: ANCHOR R6 OBSERVER; EVERY BRACKET CYCLE IDENTICAL',rows=rows,
    instrument=N.bind(instrument),parent_driver=N.bind(ROOT/'build/input-cost-attribution-r6/lanes.py'),
    prior=N.bind(ROOT/'build/dirty-anchor-native-natural-r1/receipt.json'),
    observer=N.bind(OUT/'observer.py'),driver=N.bind(Path(__file__)),
    mutations_rejected=N.selftest()+N.completion_selftest()+N.readiness_selftest(),
    product_builds=0,observer_builds=0,links=0,seeds=0,device_contacts=0,excluded_samples=0)
(OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\\n')
print(result['status'],flush=True)
'''
    target=OUT/'lanes.py';target.write_text(raw)
    sys.argv=[str(target),'--attempt','anchor-final-r1']
    try:
        exec(compile(raw,str(target),'exec'),dict(__name__='__main__',__file__=str(target)))
    except BaseException:
        (OUT/'halt.json').write_text(json.dumps(dict(status='HALT',error=traceback.format_exc(),
            instrument=N.bind(instrument),driver=N.bind(Path(__file__)),product_builds=0,links=0,seeds=0),indent=2)+'\n')
        raise

if __name__=='__main__': main()
