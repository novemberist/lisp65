"""Seal the authorized replacement halt and read-only placement attribution."""
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P

ROOT=P.ROOT
STEP=ROOT/'build/set-b-r1/step4-r3'
PRODUCT=ROOT/'build/set-b-product-r2'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-replacement-halt-20260926'

def main():
    target=ARCH/(STEM+'.json');assert not target.exists()
    assert P.require_auth().startswith('7bef0c2c')
    assert P.load(STEP/'seed-result.json')['status']=='HALT'
    assert P.load(STEP/'halt-attribution/receipt.json')['status']=='HALT ATTRIBUTED; NO EXECUTABLE SEED'
    assert not (PRODUCT/'wplto/resident-island-seed.prg.elf').exists()
    authority=STEP/'authority-at-start.md';assert not authority.exists()
    authority.write_bytes(subprocess.check_output(['git','show','f4ec7c98:docs/planning/post-2.4.0-plan.md'],cwd=ROOT))
    admission=P.load(STEP/'admission.json')
    selected=set();copies=[]
    # Predecessor before-identities are historical. Revalidate unchanged files
    # plus the two explicitly admitted AFTER identities, never rewrite history.
    for row in admission['verified_unchanged']+[r['after'] for r in admission['admitted_changes']]:
        assert P.bind(ROOT/row['path'])==row,row['path']
        selected.add(ROOT/row['path'])
    for root in (STEP,PRODUCT):selected.update(p for p in root.rglob('*') if p.is_file())
    selected.update(ROOT/p for p in P.authority_files())
    selected.update((ROOT/'tools/host-lisp').glob('set_b_replacement*20260926.py'))
    selected.update(ROOT/p for p in [
        'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-seed-link-halt-20260926.json',
        'build/set-b-seed-execution-r2.log','build/set-b-seed-execution-r3.log',
        'docs/planning/set-b-replacement-seed-halt-report.md'])
    def current_bindings(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and 'sha256' in value:
                p=ROOT/value['path'];actual=P.bind(p)
                assert actual['sha256']==value['sha256'],value['path']
                if 'bytes' in value:assert actual['bytes']==value['bytes']
                selected.add(p)
            for v in value.values():current_bindings(v)
        elif isinstance(value,list):
            for v in value:current_bindings(v)
    for p in [STEP/'seed-invocation.json',STEP/'halt-attribution/receipt.json',STEP/'command-preview/receipt.json']:
        current_bindings(P.load(p))
    copy_paths=[p for p in STEP.rglob('*.json') if p.name!='commands.json']
    copy_paths += list((STEP/'halt-attribution').glob('*.txt'))
    copy_paths += [PRODUCT/'invocation.json',PRODUCT/'command-075.log',
                   PRODUCT/'wplto/resident-island-seed.prg.map',
                   ROOT/'build/set-b-seed-execution-r2.log',ROOT/'build/set-b-seed-execution-r3.log',authority]
    for p in sorted(copy_paths):
        dest=ARCH/STEM/p.relative_to(ROOT);assert not dest.exists()
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);copies.append(P.bind(dest))
    seal=dict(status='HALT: REPLACEMENT LINK PLACEMENT; NO EXECUTABLE SEED',
        source_head='f4ec7c98',authority=P.require_auth(),accepted_world='Card L Final',
        seed_attempts=2,final_attempts=0,product_link_attempts=2,successful_product_links=0,
        replacement_seed_attempts=1,third_seed_attempts=0,device_contacts=0,emulator_runs=0,
        pre_invocation_clean_tree_refusals=1,pre_invocation_refusal_builds=0,
        report='docs/planning/set-b-replacement-seed-halt-report.md',
        inputs=[P.bind(p) for p in sorted(selected)],receipt_copies=copies,
        source_correction_applied=True,placement_correction_applied=False,
        next_product_link_requires_rebinding=True)
    P.write(target,seal)
    print('PASS replacement halt seal:',len(selected),'inputs,',len(copies),'receipt/diagnostic copies')

if __name__=='__main__':main()
