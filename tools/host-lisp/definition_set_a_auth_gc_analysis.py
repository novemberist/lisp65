"""Bind the charged GC traces and consume the existing attribution instruments."""
from pathlib import Path
import json, hashlib

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'build/definition-set-a-r3'
rows=[]
for role in ('baseline','candidate'):
    folder=ROOT/f'build/definition-set-a-auth-gc-charges-{role}-0'
    r=json.loads((folder/'receipt.json').read_text())
    c=next(c for c in r['collections'] if c['phase']=='forced')
    old=json.loads((ROOT/f'build/definition-set-a-auth-gc-equal-{role}-0/receipt.json').read_text())
    prior=next(c for c in old['collections'] if c['phase']=='forced')
    assert r['ELF']==old['ELF'] and r['medium']==old['medium']
    assert c['entry_state']['graph']==prior['entry_state']['graph'] and c['marked']==prior['marked']
    binary=ROOT/'build/minibuffer-frame-attribution-r1/cycle-observer/build/bin/xmega65.native'
    rows.append(dict(c,world=role,ELF=r['ELF'],medium=r['medium'],original_cycles=prior['cycles'],
        binary=dict(path=str(binary.relative_to(ROOT)),sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),
        observer_cycle_delta=c['cycles']-prior['cycles'],
        histograms=dict(entry=c['pc_before'],return_=c['pc_after'])))
    rows[-1]['histograms']['return']=rows[-1]['histograms'].pop('return_')
out=HERE/'gc-ledger';out.mkdir(exist_ok=True)
(out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
def run(path,changes):
    source=ROOT/path;raw=source.read_text()
    raw=raw.replace('HERE=Path(__file__).resolve().parent',"HERE=ROOT/'build/definition-set-a-r3'")
    raw=raw.replace('H=Path(__file__).resolve().parent;ROOT=H.parents[1]',"ROOT=Path.cwd();H=ROOT/'build/definition-set-a-r3'")
    for a,b in changes.items():
        assert a in raw,a
        raw=raw.replace(a,b)
    exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=str(source)))
run('build/library-delivery-r7/aggregate.py',{
 "HERE/'gc-r3'":"HERE/'gc-ledger'",
 'build/library-delivery-seed-ready-instrument-r5/xemu/xemu/cpu65_mega65_timings.h':'build/init-repair-seed-ready-instrument-r2/xemu/xemu/cpu65_mega65_timings.h'})
# Compare the instruction-charge observer to itself here: its complete CPU,
# DMA and IRQ accounting is subsequently compared to the original run.
# The separate rows retain the observed +110-cycle candidate IRQ difference.
run('build/storage-owner-r2/gc-charge-summary.py',{
 'build/storage-owner-gc-charges-':'build/definition-set-a-auth-gc-charges-',
 'build/storage-owner-gc-trace-':'build/definition-set-a-auth-gc-charges-'})
run('build/index-crc-r1/gc-heap.py',{'build/index-crc-gc-charges-':'build/definition-set-a-auth-gc-charges-'})
run('build/index-crc-r1/gc-code-identity.py',{
 'build/storage-owner-product-r2/':'build/transient-retirement-product-r1/',
 'build/index-crc-product-r1/':'build/definition-set-a-product-r2/'})
