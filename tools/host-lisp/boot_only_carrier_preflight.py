"""Budget-free aggregate admission; no product compiler/link and no device.

Stack evidence is explicitly compositional: unchanged projected bodies and
the existing 512-byte boot contract, plus the normal-path native observation.
The linked candidate must repeat the entry/owner gates and native observation.
"""
import hashlib
import json
from pathlib import Path
import subprocess

from elf_truth import ElfTruth
import boot_only_carrier_geometry as GEO
import boot_only_carrier_prg as PRG
import c2_preinstall_island_guard as ISLAND

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/boot-only-carrier-r1'
ELF=GEO.DEFAULT


def bind(path):
    return dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    evidence=[]
    def read(relative):
        path=ROOT/relative
        evidence.append(bind(path))
        return json.loads(path.read_text())
    obj=read('build/boot-only-carrier-objects-r1/receipt.json')
    assert obj['feature_off_sections_identical'] and obj['relocated_bodies_identical']
    assert obj['total_carrier_bytes']<=704
    link=read('build/boot-only-carrier-link-preprobe-r1/receipt.json')
    assert link['status']=='PASS' and link['new_findings_count']==0
    edge=read('build/boot-only-carrier-e000-preprobe-r1/e000-low-edges-receipt.json')
    assert edge['status']=='PASS'
    fixture=read('build/boot-only-carrier-linker-fixture-r1/receipt.json')
    assert [r['accepted'] for r in fixture['results']]==[True,False,False,False,False]
    observation=read('build/boot-only-carrier-observer-r2/qualification.json')
    assert observation['stack_low']>=0xce00 and observation['carrier_writes']==0
    assert observation['boot_ledger_identical'] and observation['prompt_identical']
    for path,sha in observation['files'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
        evidence.append(bind(ROOT/path))
    read('build/boot-only-carrier-capacity-r1/slice-capacity-preflight.json')
    scripts=read('build/boot-only-carrier-r1/linker-scripts-carrier-successor.json')
    assert scripts['pre_injection_changed']==[]
    truth=ElfTruth.read(ELF,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    values=truth.symbol_values()
    assert 'vm_boot_stack_probe_begin' not in values
    start=(max(values['__lisp65_workbench_overlay_end'],values['__lisp65_boot_bank3_stage_end'])+1)&~1
    writers=[('startup BSS clear',values['__bss_start'],values['__bss_end']),
             ('fixed/noinit owner',0xc000,values['__heap_start']),
             ('Workbench copy/wipe',values['__lisp65_workbench_overlay_start'],values['__lisp65_workbench_overlay_end']),
             ('cold load',values['__lisp65_boot_bank3_stage_start'],values['__lisp65_boot_bank3_stage_end']),
             ('runtime copy/wipe',values['__lisp65_workbench_overlay_start'],values['__lisp65_workbench_runtime_overlay_limit']),
             ('island install/wipe',0x1800,0x2000),
             ('IRQ hardware stack',0x100,0x200),('IRQ state/ring',0xe000,0x10000)]
    GEO.validate(start,704,values['__lisp65_workbench_boot_slice_limit'],values['__stack'],writers)
    native_island=ISLAND.static_elf_gate(ELF)
    assert not native_island['unguarded_or_consuming_data_references']
    outputs={}
    for name in ('bootstrap-host','transaction-host'):
        exe=OUT/name
        outputs[name]=subprocess.check_output([str(exe)],text=True)
        assert 'PASS' in outputs[name]
        evidence.append(bind(exe))
    PRG.selftest()
    # The admitted transformation is exclusively a guarded section attribute.
    # Pin all live source inputs consumed by the projection, including IRQ and
    # assembly commit seam; final-LTO frame/control checks remain mandatory.
    for path in ('src/main.c','src/vm_boot_overlay.c','src/vm_runtime_overlay.c',
                 'src/c2_boot_chain_commit.s','src/c2_kernal_map.s',
                 'src/optional/c2_kernal_input_capture.s'):
        evidence.append(bind(ROOT/path))
    evidence.append(bind(ELF))
    for path in sorted((ROOT/'tools/host-lisp').glob('boot_only_carrier*.py')):
        evidence.append(bind(path))
    result=dict(status='PASS',authority='4cd7eac3',budget=dict(seed=0,finale=0,link=0),
                evidence=evidence,writers=writers,host_errors=outputs,
                predecessor_island=native_island,
                boot_stack=dict(contract_bytes=512,observed_low=observation['stack_low'],
                    argument='projected relocation adds no instructions, frames or calls on success or error; existing contract unchanged',
                    limitation='normal native observation, not exhaustive native fault injection'),
                seed_obligations=['linked carrier entry/flags/geometry and unchanged frame ABI',
                                  'full-prefix ELF equality and complete PRG destination CRC',
                                  'native carrier-live observer, prompt, lanes, GC and intern',
                                  'all owner floors and >=600 ordinary text bytes recovered'])
    target=OUT/'preflight-admission.json'
    raw=json.dumps(result,indent=2)+'\n'
    if target.exists() and target.read_text()!=raw:
        raise ValueError('admission is immutable; use an explicit successor')
    if not target.exists(): target.write_text(raw)
    print('PASS: carrier preflight; Seed 0/1, Finale 0/1, Link 0/1')


if __name__=='__main__': main()
