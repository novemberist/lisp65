"""Paired off-product object proof for the authorized two-function placement."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from elf_truth import ElfTruth
from boot_name_index_link_preprobe import compile_command_of

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/ov-crc16-product-r1/wplto'
OUT = ROOT/'build/boot-only-carrier-objects-r1'
MEMBERS = {'vm_boot_overlay.c': ('vm_install_staged_boot_overlay',
           '__attribute__((noinline)) uint8_t vm_install_staged_boot_overlay(void)'),
           'vm_runtime_overlay.c': ('vm_runtime_overlay_install_island',
           'RTOV_NOINLINE\nvm_runtime_overlay_status vm_runtime_overlay_install_island(void)')}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    proof = json.loads((BASE/'command-proof.json').read_text())
    closure = json.loads((BASE/'active-include-check/receipt.json').read_text())
    allowed = {(ROOT/d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}
    results = []
    for filename, (function, signature) in MEMBERS.items():
        commands = [c for c in proof['commands'] if '-c' in c and
                    Path(c[c.index('-c')+1]).name == filename]
        assert len(commands) == 1
        command = commands[0]
        flags, consumed, _ = compile_command_of(command)
        original = (ROOT/consumed).read_text()
        live = (ROOT/'src'/filename).read_text()
        end = live.index(signature)
        start = live.rfind('#ifdef LISP65_BOOT_ONLY_CARRIER',0,end)
        assert start >= 0 and original.count(signature) == 1
        guard = live[start:end]
        assert guard.count('__attribute__((section(".lisp65_boot_carrier")))') == 1
        candidate = original.replace(signature,guard+signature,1)
        variants = {}
        for mode,text,extra in [('baseline',original,[]),('disabled',candidate,[]),
                                ('enabled',candidate,['-DLISP65_BOOT_ONLY_CARRIER'])]:
            folder = OUT/mode
            folder.mkdir(exist_ok=True)
            source = folder/filename
            source.write_text(text)
            obj = source.with_suffix('.o')
            deps = subprocess.check_output([command[0],*flags,*extra,'-M','-MT','probe',str(source)],text=True)
            bound = []
            for path in shlex.split(deps.replace('\\\n',' ').split(':',1)[1]):
                p = (ROOT/path).resolve()
                if p != source:
                    assert p in allowed and digest(p) == allowed[p], 'unbound include '+str(p)
                bound.append(dict(path=str(p.relative_to(ROOT)),sha256=digest(p)))
            cc = [command[0],*flags,*extra,'-fno-lto','-c',str(source),'-o',str(obj)]
            subprocess.run(cc,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            truth = ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
            sym = truth.symbol(function)
            section = truth.section(sym.section)
            body = truth.section_bytes(sym.section)[sym.value-section.address:sym.value-section.address+sym.bytes]
            sections = {s.name: hashlib.sha256(truth.section_bytes(s.name)).hexdigest()
                        for s in truth.sections if s.name.startswith(('.text','.rodata','.lisp65'))
                        and s.section_type != 'SHT_NOBITS'}
            variants[mode] = dict(bytes=sym.bytes,section=sym.section,
                                 body_sha256=hashlib.sha256(body).hexdigest(),
                                 sections=sections,command=cc,inputs=bound)
        assert variants['disabled']['sections'] == variants['baseline']['sections']
        assert variants['enabled']['body_sha256'] == variants['baseline']['body_sha256']
        assert variants['enabled']['section'] == '.lisp65_boot_carrier'
        results.append(dict(function=function,variants=variants))
    total = sum(r['variants']['enabled']['bytes'] for r in results)
    assert total <= 704
    receipt = dict(claim='NON-LTO OBJECT PROOF ONLY',total_carrier_bytes=total,
                   feature_off_sections_identical=True, relocated_bodies_identical=True,
                   functions=results,budget=dict(seed=0,finale=0,link=0))
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'boot-only-carrier-objects: PASS {total}/704 bytes; feature-off identical; budget 0/0/0')


if __name__ == '__main__':
    main()
