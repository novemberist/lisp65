#!/usr/bin/env python3
"""Re-measure the registered m65-hw pilot without touching product bytes.

This bounded compiler projection is not a delivered-world price or approval.
Live loaded-world GC/responsiveness and packed closure are separate obligations.
"""
import hashlib
import json
from pathlib import Path
from evidence_era import stable_recorded_on

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/capacity-parity/parity-pricing-r1'

def bind(p):
    return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def main():
    base=json.loads((OUT/'base.manifest.json').read_text())
    pilot=json.loads((OUT/'pilot.manifest.json').read_text())
    contract=json.loads((ROOT/'config/c2-m65-hw-contract.json').read_text())
    old={e['name']:e for e in base['entries']}; new={e['name']:e for e in pilot['entries']}
    assert set(old)<=set(new)
    added=[e for name,e in new.items() if name not in old]
    base_code=(OUT/'base.blob.bin').read_bytes(); pilot_code=(OUT/'pilot.blob.bin').read_bytes()
    changed=[]; attributed=[]
    def normalized(m, e, code):
        start=e['blob_offset']; result=bytearray(code[start:start+e['length']])
        patches=[p for p in m['literal_patches'] if start<=p['blob_offset']<start+e['length']]
        assert len(patches)==e['lit_count']
        for p in patches:
            at=p['blob_offset']-start
            assert 0<=at<at+2<=len(result)
            result[at:at+2]=b'\0\0'
        return bytes(result)
    for name,e in old.items():
        n=new[name]
        if e['length']!=n['length'] or e['literals']!=n['literals'] or normalized(base,e,base_code)!=normalized(pilot,n,pilot_code):
            changed.append(name)
        elif base_code[e['blob_offset']:e['blob_offset']+e['length']] != pilot_code[n['blob_offset']:n['blob_offset']+n['length']]:
            attributed.append(name)
    assert not changed, changed
    code=sum(e['length'] for e in added)
    assert code==pilot['code_bytes']-base['code_bytes']
    observations=json.loads((OUT/'observations.json').read_text())['suites'][0]['observations']
    rows=[r for r in observations if r['name'].startswith('m65-')]
    symbols=sum(len(e['name'].encode())+1 for e in added)
    largest=max(added,key=lambda e:e['length'])
    result=dict(recorded_on=stable_recorded_on(OUT/'projection.json'),
        status='HOST PROJECTION MEASURED; NOT A GREEN TOTAL PRICE',
        authority=bind(ROOT/'config/c2-m65-hw-contract.json'),
        register=bind(ROOT/'docs/reference/parked-items-register.md'),
        manifests=[bind(OUT/(x+'.manifest.json')) for x in ('base','pilot')],
        sources=[bind(ROOT/x) for x in ('lib/m65-hw.lisp','lib/m65-hw-registers.lisp')],
        code_bytes=code, code_budget=contract['placement']['admission_budget_bytes'],
        objects=len(added), registered_object_name_bytes=symbols,
        largest_object=dict(name=largest['name'],bytes=largest['length']),
        entries=[dict(name=e['name'],bytes=e['length']) for e in added],
        unchanged_baseline_semantics_objects=len(old), changed_baseline_objects=changed,
        literal_relocation_only_objects=attributed,
        generated_external_image_delta=pilot['external_image']['bytes']-base['external_image']['bytes'],
        extra_literal_nodes=len(pilot['literal_nodes'])-len(base['literal_nodes']),
        executed_pilot_cases=len(rows), observations=bind(OUT/'observations.json'),
        d5_name_only_projection=dict(baseline_slots=107,baseline_name_bytes=1467,
            remaining_slots=107-len(added),remaining_name_bytes=1467-symbols,
            claim='only object names; not loaded D5: literal symbols, loader state and module metadata not included'),
        native_product_builds=0, device_contacts=0,
        unpaid=['packed library on renderer world; no resident override',
            'transitive closure and generation coherence over packed bytes',
            'loaded configuration D5 including literal names and loader state',
            'both responsiveness lanes and GC-time wall on loaded renderer world',
            'hardware/register owner validation against current composed map'],
        limit='historical suite population, re-executed with current host compiler; not the entire BASIC65 module graph')
    (OUT/'projection.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('code_bytes','objects','registered_object_name_bytes','largest_object','executed_pilot_cases','changed_baseline_objects')}))

if __name__=='__main__': main()
