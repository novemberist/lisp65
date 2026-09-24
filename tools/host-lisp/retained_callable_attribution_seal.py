"""Seal existing halt evidence. No emulator, compiler, linker or product execution."""
import json
import shutil
import subprocess
from pathlib import Path
from retained_callable_attribution_report import ROOT, OUT, bind
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'retained-callable-attribution-halt-20260923'

def main():
    target=ARCH/(STEM+'.json')
    assert not target.exists()
    result=json.loads((OUT/'attribution.json').read_text())
    assert result['status'].startswith('HALT: PUBLISHED CODE CORRUPTION')
    assert all(result[k]==0 for k in ('product_builds','observer_builds','links','seeds','device_contacts'))
    assert not subprocess.check_output(['git','diff','HEAD','--','src','lib'],cwd=ROOT)
    authority=OUT/'authority-at-start.md'
    authority_bytes=subprocess.check_output(['git','show','43448850:docs/planning/post-2.3.0-plan.md'],cwd=ROOT)
    if authority.exists():assert authority.read_bytes()==authority_bytes
    else:authority.write_bytes(authority_bytes)
    selected=set(); closure={}; copies=[]
    roots=[OUT]+[ROOT/f'build/retained-callable-attribution-r{i}' for i in range(1,5)]
    for root in roots:
        selected.update(p.resolve() for p in root.rglob('*') if p.is_file() and p.name!='system-sd.img')
    selected.update((ROOT/'tools/host-lisp').glob('retained_callable_*.py'))
    selected.update(ROOT/f'build/retained-callable-attribution-r{i}.log' for i in range(1,5))
    selected.update(ROOT/p for p in [
        'docs/planning/retained-callable-attribution-halt-report.md',
        'tools/host-lisp/native_cycle_stationary.py','tools/host-lisp/dwx_retroactive_red_replay.py',
        'tools/host-lisp/dwx_comfort_resume.py','tools/host-lisp/dwx_mirrored_prefilter_rows.py',
        'tools/host-lisp/elf_truth.py','scripts/xmega65-safe-run.sh',
        'scripts/equivalence-main.c','src/c2_product_runtime.h','src/obj.h','src/vm.c','src/c2_phase_scratch.h',
        'build/anchor-cache-projection-r1/instrument.json',
        'build/input-cost-attribution-r6/cost.h',
        'build/input-cost-attribution-r6/xemu/targets/mega65/uart_monitor.c',
        'build/input-cost-attribution-r6/xemu/targets/mega65/mega65.c',
        'tests/bytecode/dialect-v2/evidence/architecture-blocks/input-call-render-attribution-20260923.json',
        'tests/bytecode/dialect-v2/evidence/architecture-blocks/dirty-anchor-final-20260923.json'])
    consumed=ROOT/'build/dirty-anchor-product-r1/wplto/generated-product-sources'
    selected.update(consumed/n for n in ['c2-stream-v2-decoder.c','c2-stream-decoder.h','c2_product_runtime.c','c2_session_emitter.c','c2-stream-v2-phase-12.c'])
    def verify(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and 'sha256' in value:
                p=(ROOT/value['path']).resolve()
                if p.is_file() and p.is_relative_to(ROOT):
                    actual=bind(p)
                    assert actual['sha256']==value['sha256'],value['path']
                    if 'bytes' in value:assert actual['bytes']==value['bytes'],value['path']
                    closure[actual['path']]=actual
            for child in value.values():verify(child)
        elif isinstance(value,list):
            for child in value:verify(child)
    for p in sorted(selected):
        if p.suffix=='.json' and any(p.is_relative_to(root) for root in roots):
            verify(json.loads(p.read_text()))
            dest=ARCH/STEM/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
            assert not dest.exists();shutil.copyfile(p,dest);copies.append(bind(dest))
        row=bind(p);closure[row['path']]=row
    seal=dict(status=result['status'],authority='43448850',accepted_world='1e210f3f',
        source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        inputs=sorted(closure.values(),key=lambda x:x['path']),receipt_copies=copies,
        product_builds=0,observer_builds=0,links=0,seeds=0,device_contacts=0,
        excluded=['mutable system-sd.img scratch copies'],
        next_card_started=False,repair_priced=False,remaining_rows_executed=False)
    target.write_text(json.dumps(seal,indent=2)+'\n')
    print('PASS:',len(closure),'verified bindings;',len(copies),'committed receipt copies; product HALT preserved')
if __name__=='__main__':main()
