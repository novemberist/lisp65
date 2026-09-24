"""Seal existing host projection evidence without build, link or device access."""
import json
from pathlib import Path
import shutil
import subprocess
from anchor_cache_projection_report import ROOT,H,R6,NAT,bind

ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='anchor-cache-projection-20260923'

def main():
    target=ARCH/(STEM+'.json');assert not target.exists()
    result=json.loads((H/'projection.json').read_text())
    assert result['status']=='PASS: HOST-ONLY REMAINING CACHE PROJECTION'
    assert result['exact_cycle_neutrality_brackets']==45 and not result['threshold_met']
    assert all(result[k]==0 for k in ('product_builds','observer_builds','links','seeds','device_contacts','excluded_samples'))
    assert not subprocess.check_output(['git','diff','HEAD','--','src','lib'],cwd=ROOT)
    authority=H/'authority-at-start.md'
    assert not authority.exists()
    authority.write_bytes(subprocess.check_output(['git','show','a982b117:docs/planning/post-2.3.0-plan.md'],cwd=ROOT))
    selected=set()
    for root in (H,NAT):
        selected.update(p.resolve() for p in root.rglob('*') if p.is_file() and p.name!='system-sd.img')
    selected.update((ROOT/'tools/host-lisp').glob('anchor_cache_projection_*.py'))
    selected.update([ROOT/'docs/planning/anchor-cache-remaining-gain-report.md',ROOT/'build/anchor-cache-projection-r1.log',
        ROOT/'tools/host-lisp/native_cycle_stationary.py',ROOT/'tools/host-lisp/dwx_retroactive_red_replay.py',
        ROOT/'config/bytecode-abi-ledger.json',R6/'lanes.py',R6/'cost.h',R6/'instrument.json',
        R6/'selftest.json',R6/'verification.json',R6/'source-audit.json',R6/'attribution.json',R6/'projection.json',
        ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/input-call-render-attribution-20260923.json',
        ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/dirty-anchor-final-20260923.json'])
    closure={};copies=[]
    def verify(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and 'sha256' in value:
                p=(ROOT/value['path']).resolve()
                if p.is_file() and p.is_relative_to(ROOT):
                    actual=bind(p)
                    assert actual['sha256']==value['sha256'],value['path']
                    if 'bytes' in value: assert actual['bytes']==value['bytes'],value['path']
                    closure[actual['path']]=actual
            for child in value.values():verify(child)
        elif isinstance(value,list):
            for child in value:verify(child)
    # Historical seals are themselves bound. Their full large artifact populations
    # need no replay; verify the selected observer and measurement inputs directly.
    historical=json.loads((ARCH/'input-call-render-attribution-20260923.json').read_text())
    pins={str((ROOT/r['path']).resolve()):r for r in historical['inputs']}
    for p in (R6/'instrument.json',R6/'cost.h',R6/'attribution.json',R6/'projection.json',R6/'selftest.json',R6/'verification.json',R6/'xemu/build/bin/xmega65.native'):
        assert str(p) in pins
        verify(pins[str(p)])
    for p in sorted(selected):
        if p.suffix=='.json' and p.is_relative_to(ROOT/'build'):
            verify(json.loads(p.read_text()))
            if p.is_relative_to(H) or p.is_relative_to(NAT):
                dest=ARCH/STEM/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
                assert not dest.exists();shutil.copyfile(p,dest);copies.append(bind(dest))
        row=bind(p);closure[row['path']]=row
    record=dict(status='PASS: BUDGET-FREE ANCHOR CACHE PROJECTION',authority='a982b117',
        accepted_world='1e210f3f',source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        inputs=sorted(closure.values(),key=lambda r:r['path']),receipt_copies=copies,
        nominal_ratios=[r['scenarios'][0]['ratio'] for r in result['lanes']],threshold_met=False,
        product_builds=0,observer_builds=0,links=0,seeds=0,device_contacts=0,
        excluded_from_seal=['mutable scratch system-sd.img; delivered D81 and observer binary are bound'])
    target.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS',len(closure),'bindings;',len(copies),'committed receipt copies')

if __name__=='__main__':main()
