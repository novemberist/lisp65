"""Seal failed Set B Seed and parser attribution; never executes a product tool."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
ROOT=P.ROOT
STEP=ROOT/'build/set-b-r1/step4-r2'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-seed-link-halt-20260926'

def main():
    target=ARCH/(STEM+'.json');assert not target.exists()
    assert P.require_auth().startswith('4f843a79')
    assert P.load(STEP/'seed-result.json')['status']=='HALT'
    assert not (ROOT/'build/set-b-product-r1/wplto/resident-island-seed.prg.elf').exists()
    assert P.load(STEP/'link-syntax-attribution/receipt.json')['status'].startswith('PASS:')
    authority=STEP/'authority-at-start.md';assert not authority.exists()
    authority.write_bytes(subprocess.check_output(['git','show','bad4c939:docs/planning/post-2.4.0-plan.md'],cwd=ROOT))
    selected=set();closure={};copies=[]
    roots=[STEP,ROOT/'build/set-b-product-r1']
    for root in roots:selected.update(p for p in root.rglob('*') if p.is_file())
    selected.update(ROOT/p for p in P.authority_files())
    selected.update((ROOT/'tools/host-lisp').glob('set_b_*20260926.py'))
    selected.update(ROOT/p for p in ['tools/host-lisp/boot_name_index_link_preprobe.py',
        'tools/host-lisp/slice_capacity_preflight_20260924.py','tools/host-lisp/slice_capacity_preflight.py',
        'build/set-b-step4-preflight-r2.log','build/set-b-seed-execution-r1.log',
        'docs/planning/set-b-seed-link-halt-report.md','docs/planning/codex-handover-2026-09-26.md',
        'build/set-b-r1/step3/objects/summary-resident-246.json',
        'build/set-b-r1/step3/step3b-gate-matrix.json',
        'build/card-l-final-r1/final-command-consumption.json',
        'tests/bytecode/dialect-v2/evidence/architecture-blocks/card-l-final-20260925.json'])
    selected.add(P.FINAL)
    def verify(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and 'sha256' in value:
                path=(ROOT/value['path']).resolve()
                if path.is_file() and path.is_relative_to(ROOT):
                    actual=P.bind(path);assert actual['sha256']==value['sha256'],value['path']
                    if 'bytes' in value:assert actual['bytes']==value['bytes'],value['path']
                    closure[actual['path']]=actual
            for v in value.values():verify(v)
        elif isinstance(value,list):
            for v in value:verify(v)
    for path in sorted(selected):
        if path.suffix=='.json' and any(path.is_relative_to(r) for r in roots):
            verify(P.load(path))
            # Immutable receipts/commands are committed; bulky compiled artifacts remain SHA-bound.
            if path.name!='commands.json' and path.name!='command-proof.json':
                dest=ARCH/STEM/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
                assert not dest.exists();shutil.copyfile(path,dest);copies.append(P.bind(dest))
        row=P.bind(path);closure[row['path']]=row
    patch=STEP/'link-syntax-attribution/proposed-correction.patch'
    dest=ARCH/STEM/'proposed-correction.patch';shutil.copyfile(patch,dest);copies.append(P.bind(dest))
    seal=dict(status='HALT: FIRST PRODUCT LINK FAILED; NO EXECUTABLE SEED',
        source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        authority=P.require_auth(),accepted_world='Card L Final',
        seed_attempts=1,final_attempts=0,product_link_attempts=1,successful_product_links=0,
        replacement_seed_attempts=0,synthetic_parser_links=2,device_contacts=0,emulator_runs=0,
        report='docs/planning/set-b-seed-link-halt-report.md',
        inputs=sorted(closure.values(),key=lambda r:r['path']),receipt_copies=copies,
        source_correction_applied=False,next_product_link_requires_rebinding=True)
    target.write_text(json.dumps(seal,indent=2)+'\n')
    print('PASS halt seal:',len(closure),'bindings,',len(copies),'receipt/patch copies')
if __name__=='__main__':main()
