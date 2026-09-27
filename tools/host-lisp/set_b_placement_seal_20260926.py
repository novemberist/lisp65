"""Seal the completed object/packing revision without granting another Seed."""
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P

ROOT=P.ROOT
BASE=ROOT/'build/set-b-placement-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-placement-revision-20260926'

def main():
    target=ARCH/(STEM+'.json');assert not target.exists()
    assert P.AUTH=='AUTH_PENDING'
    assert P.load(BASE/'validation-r2/receipt.json')['status'].startswith('PASS:')
    assert P.load(BASE/'review-r2/e000-edges.json')['status']=='PASS'
    authority=BASE/'authority-at-start.md';assert not authority.exists()
    authority.write_bytes(subprocess.check_output(['git','show','0d3a2043:docs/planning/post-2.4.0-plan.md'],cwd=ROOT))
    patch=BASE/'authored-revision.patch';assert not patch.exists()
    paths=['src/c2_product_runtime.c','config/set-b-native/include-closure.json',
           'config/set-b-native/set-b-inputs.json','config/set-b-native/set-b-placement.h',
           'tools/host-lisp/set_b_producer.py','tools/host-lisp/set_b_seed_media.py']
    patch.write_bytes(subprocess.check_output(['git','diff','0d3a2043','--',*paths],cwd=ROOT))
    selected={p for p in BASE.rglob('*') if p.is_file()}
    selected.update(ROOT/p for p in P.authority_files())
    selected.update((ROOT/'tools/host-lisp').glob('set_b_placement*20260926.py'))
    selected.update(ROOT/p for p in [
        'docs/planning/set-b-placement-revision-report.md',
        'build/set-b-placement-probe-r1.log','build/set-b-placement-review-r2.log',
        'build/set-b-placement-validation-r1.log','build/set-b-placement-validation-r2.log',
        'build/set-b-r1/step4-r3/halt-attribution/receipt.json',
        'build/set-b-product-r2/wplto/resident-island-seed.prg.map',
        'tools/host-lisp/elf_truth.py','tools/host-lisp/runtime_overlay_bank.py',
        'tools/host-lisp/boot_name_index_link_preprobe.py',
        'tools/llvm-mos/bin/mos-mega65-clang','tools/llvm-mos/bin/llvm-readobj','tools/llvm-mos/bin/llvm-objdump',
        'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-replacement-halt-20260926.json'])
    def verify(v):
        if isinstance(v,dict):
            if isinstance(v.get('path'),str) and 'sha256' in v:
                p=ROOT/v['path'];actual=P.bind(p)
                assert actual['sha256']==v['sha256'],v['path']
                if 'bytes' in v:assert actual['bytes']==v['bytes'],v['path']
                selected.add(p)
            for x in v.values():verify(x)
        elif isinstance(v,list):
            for x in v:verify(x)
    for p in [BASE/'validation-r2/receipt.json',BASE/'compile-receipt.json',
              BASE/'review-r2/proposal.json',BASE/'geometry-r3/receipt.json']:
        verify(P.load(p))
    for p in P.load(BASE/'review-r2/e000-edges.json')['objects']:
        selected.add(Path(p) if Path(p).is_absolute() else ROOT/p)
    for row in P.load(BASE/'source-census-r2/metadata-refresh.json')['updated']:
        assert P.bind(ROOT/row['after']['path'])==row['after']
    copy_paths=[BASE/p for p in [
        'start.json','compile-receipt.json','e000-edges.json',
        'review-r2/e000-edges.json','review-r2/proposal.json','geometry-r3/receipt.json',
        'validation-r1/receipt.json','validation-r2/receipt.json',
        'validation-r2/command-preview/receipt.json',
        'source-census-r2/metadata-refresh.json','source-census-r2/invocation.json',
        'source-census-r2/inputs-before-metadata-refresh.json',
        'authority-at-start.md','authored-revision.patch']]
    copy_paths += [ROOT/p for p in ['build/set-b-placement-probe-r1.log',
        'build/set-b-placement-review-r2.log','build/set-b-placement-validation-r1.log','build/set-b-placement-validation-r2.log']]
    copies=[]
    for p in copy_paths:
        dest=ARCH/STEM/p.relative_to(ROOT);assert not dest.exists()
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);copies.append(P.bind(dest))
    P.write(target,dict(status='HOST PLACEMENT REVISION COMPLETE; SEED AUTHORITY PENDING',
        starting_head='0d3a2043',accepted_world='Card L Final',source_authority='AUTH_PENDING',
        report='docs/planning/set-b-placement-revision-report.md',
        object_compiles=2,product_links=0,seeds=0,finals=0,emulator_runs=0,device_contacts=0,
        cumulative_charged=dict(seed_attempts=2,finals=0,product_link_attempts=2),
        proposed_ceiling_not_authorized=dict(seed_attempts=3,finals=1,product_link_attempts=3),
        validated_host_checks=9,rejected_negative_controls=7,
        inputs=[P.bind(p) for p in sorted(selected)],receipt_copies=copies))
    print('PASS placement seal:',len(selected),'inputs;',len(copies),'receipt/diagnostic copies')

if __name__=='__main__':main()
