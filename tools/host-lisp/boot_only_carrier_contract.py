"""Permanent source/extent contract; no producer or registered output writes."""
from pathlib import Path
import re

import boot_only_carrier_linker as L
import boot_only_carrier_prg as P

ROOT=Path(__file__).resolve().parents[2]


def validate(sources, fragment):
    expected={'src/vm_boot_overlay.c':'vm_install_staged_boot_overlay',
              'src/vm_runtime_overlay.c':'vm_runtime_overlay_install_island'}
    for path,name in expected.items():
        text=re.sub(r'/\*.*?\*/','',sources[path],flags=re.S)
        needle=(r'#ifdef LISP65_BOOT_ONLY_CARRIER\s+'
                r'__attribute__\(\(section\("\.lisp65_boot_carrier"\)\)\)\s+'
                r'#endif\s+[^;{}]*\b'+name+r'\s*\(')
        if len(re.findall(needle,text))!=1:
            raise ValueError('carrier opt-in/function admission: '+path)
        if text.count('section(".lisp65_boot_carrier")')!=1:
            raise ValueError('carrier population: '+path)
    for needle in ('KEEP(*(.lisp65_boot_carrier))','<= 704',
                   '__lisp65_workbench_required_boot_stack == 512','__lisp65_workbench_runtime_overlay_limit'):
        if needle not in fragment:
            raise ValueError('carrier linker contract: '+needle)


def main():
    sources={p:(ROOT/p).read_text() for p in ('src/vm_boot_overlay.c','src/vm_runtime_overlay.c')}
    validate(sources,L.FRAGMENT)
    cases=[]
    for path in sources:
        mutant=dict(sources);mutant[path]=mutant[path].replace('#ifdef LISP65_BOOT_ONLY_CARRIER','#if 1')
        cases.append((mutant,L.FRAGMENT))
        mutant=dict(sources);mutant[path]+='\n__attribute__((section(".lisp65_boot_carrier")))\n'
        cases.append((mutant,L.FRAGMENT))
    for needle in ('<= 704','__lisp65_workbench_required_boot_stack == 512','__lisp65_workbench_runtime_overlay_limit'):
        cases.append((sources,L.FRAGMENT.replace(needle,'REMOVED')))
    for source,fragment in cases:
        try: validate(source,fragment)
        except ValueError: pass
        else: raise AssertionError('carrier contract mutation survived')
    P.selftest()
    print('boot-only-carrier-contract: PASS; 7 source/linker and 10 PRG negative controls')


if __name__=='__main__': main()
