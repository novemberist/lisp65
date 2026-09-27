"""Seal the successful third link and its inventory-scope halt; no execution."""
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P

ROOT=P.ROOT
STEP=ROOT/'build/set-b-r1/step4-r4'
PRODUCT=ROOT/'build/set-b-product-r3'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-third-seed-inventory-halt-20260926'

def main():
    target=ARCH/(STEM+'.json');assert not target.exists()
    assert P.require_auth().startswith('7a4e43fa')
    assert P.load(STEP/'seed-result.json')['status'].startswith('PASS: LINKED AND EXTRACTED')
    halt=STEP/'inventory-halt-r1/inventory-halt.json'
    assert P.load(halt)['status'].startswith('HALT: ADDRESS-MODE DRIFT')
    assert P.load(PRODUCT/'linked.json')['elf']==P.bind(PRODUCT/'wplto/resident-island-seed.prg.elf')
    authority=STEP/'authority-at-start.md';assert not authority.exists()
    authority.write_bytes(subprocess.check_output(['git','show','7c659dfd:docs/planning/post-2.4.0-plan.md'],cwd=ROOT))
    selected=set();copies=[]
    for root in (STEP,PRODUCT):selected.update(p for p in root.rglob('*') if p.is_file())
    selected.update(ROOT/p for p in P.authority_files())
    selected.update((ROOT/'tools/host-lisp').glob('set_b_third_seed*20260926.py'))
    selected.update(ROOT/p for p in [
        'docs/planning/set-b-third-seed-inventory-halt-report.md',
        'build/set-b-seed-execution-r4.log','build/set-b-third-seed-inventory-halt-r1.log',
        'tools/host-lisp/elf_truth.py','tools/host-lisp/boot_name_index_link_preprobe.py',
        'tools/llvm-mos/bin/mos-mega65-clang','tools/llvm-mos/bin/llvm-readobj','tools/llvm-mos/bin/llvm-objdump',
        'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-placement-revision-20260926.json'])
    admission=P.load(STEP/'admission.json')
    for row in admission['verified_unchanged']+[r['after'] for r in admission['normalized_auth_changes']]:
        assert P.bind(ROOT/row['path'])==row,row['path'];selected.add(ROOT/row['path'])
    def verify(v):
        if isinstance(v,dict):
            if isinstance(v.get('path'),str) and 'sha256' in v:
                path=ROOT/v['path'];actual=P.bind(path)
                assert actual['sha256']==v['sha256'],v['path']
                if 'bytes' in v:assert actual['bytes']==v['bytes'],v['path']
                selected.add(path)
            for x in v.values():verify(x)
        elif isinstance(v,list):
            for x in v:verify(x)
    for path in [halt,STEP/'inventory-halt-r1/price.json',STEP/'seed-invocation.json',
                 STEP/'command-preview/receipt.json',PRODUCT/'linked.json']:
        verify(P.load(path))
    copy_paths=[p for p in STEP.rglob('*.json') if p.name not in ('commands.json','command-proof.json')]
    copy_paths += [PRODUCT/'invocation.json',PRODUCT/'linked.json',PRODUCT/'command-075.log',authority,
                   ROOT/'build/set-b-seed-execution-r4.log',ROOT/'build/set-b-third-seed-inventory-halt-r1.log']
    for path in sorted(copy_paths):
        dest=ARCH/STEM/path.relative_to(ROOT);assert not dest.exists()
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest);copies.append(P.bind(dest))
    P.write(target,dict(status='HALT: THIRD SEED LINKED, INVENTORY SCOPE DECISION REQUIRED',
        source_head='7c659dfd',source_authority=P.require_auth(),accepted_world='Card L Final',
        seed=P.bind(PRODUCT/'wplto/resident-island-seed.prg.elf'),tenant_image=P.bind(PRODUCT/'set-b-tenants.bin'),
        seed_attempts=3,finals=0,product_link_attempts=3,successful_product_links=1,
        media_builds=0,emulator_runs=0,device_contacts=0,complete_inventory=False,
        unclassified_bytes='not exhaustively counted; no zero-unclassified claim',
        report='docs/planning/set-b-third-seed-inventory-halt-report.md',
        inputs=[P.bind(p) for p in sorted(selected)],receipt_copies=copies,
        further_link_authorized=False,review_existing_seed_without_link=True))
    print('PASS third-Seed halt seal:',len(selected),'inputs;',len(copies),'receipt copies')

if __name__=='__main__':main()
