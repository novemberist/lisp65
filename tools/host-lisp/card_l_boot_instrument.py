"""Build a separate ELF-bound boot ledger observer; never run it or build product code."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from elf_truth import ElfTruth
from c2_crc_codegen_gate import disassembly_rows, _direct_operand
from card_l_r1_common import ROOT, worlds, N

BASE = ROOT/'build/nested-error-recovery-native-boot-r1'
OUT = ROOT/'build/card-l-boot-instrument-r1'

def main():
    baseline, candidate = worlds()
    OUT.mkdir(exist_ok=False)
    shutil.copytree(BASE/'observer', OUT/'observer')
    source = ROOT/'build/ov-crc16-r1/boot_ledger_observer.py'
    raw = source.read_text()
    old = "    p=ROOT/'build/ov-crc16-seed-medium-r1/packed-receipt.json';r=json.loads(p.read_text())\n    paths=[p.parent/'packed/autoboot.c65.elf',ROOT/r['elf']['path']]"
    new = "    p=ROOT/'build/card-l-r1/instrument-seed.json';w=json.loads(p.read_text())['worlds'][0];r=dict(elf=w['ELF'],medium=w['medium'])\n    paths=[ROOT/'build/card-l-seed-medium-r1/media-seed/autoboot.c65.elf',ROOT/r['elf']['path']]"
    assert raw.count(old)==1
    ns=dict(__name__='boot_configuration',__file__=str(source))
    exec(compile(raw.replace(old,new),str(source),'exec'),ns)
    ns['configure'](OUT)
    elf=N.checked_binding(candidate['ELF'])
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    main=t.symbol('main');values=t.symbol_values()
    dump=subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-d','--no-show-raw-insn',str(elf)],text=True)
    calls=[r for r in disassembly_rows(dump) if r['section']==main.section and main.value<=r['address']<main.value+main.bytes and r['opcode']=='jsr' and _direct_operand(r)==values['vm_runtime_overlay_install_island']]
    assert len(calls)==1
    changes=dict(CARRIER_START=values['__lisp65_boot_carrier_start'],CARRIER_END=values['__lisp65_boot_carrier_end'],CARRIER_MAIN=main.value,CARRIER_RETURN=calls[0]['address']+3)
    p=OUT/'observer/xemu/boot_observer.h';raw=p.read_text()
    for key,value in changes.items():
        raw,n=re.subn(r'#define '+key+r' \d+u',f'#define {key} {value}u',raw);assert n==1
    p.write_text(raw)
    command=json.loads((BASE/'build.json').read_text())['command']
    command=[x.replace(str(BASE),str(OUT)) for x in command]
    with (OUT/'build.log').open('w') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    changed=[]
    for p in (BASE/'observer').rglob('*'):
        if p.is_file() and p.suffix in ('.c','.h','.s'):
            relative=p.relative_to(BASE/'observer')
            if p.read_bytes() != (OUT/'observer'/relative).read_bytes(): changed.append(str(relative))
    assert set(changed)<= {'xemu/boot_boundaries.h','xemu/boot_observer.h','build/objs/m-native-mega65-xmega65--make-buildinfo.c'}
    baseline['binary']=N.bind(BASE/'observer/build/bin/xmega65.native')
    candidate['binary']=N.bind(OUT/'observer/build/bin/xmega65.native')
    (OUT/'instrument.json').write_text(json.dumps(dict(worlds=[baseline,candidate],changes=changes,changed_sources=changed,command=command,configuration=N.bind(OUT/'configuration.json'),parent=N.bind(BASE/'configuration.json'),product_builds=0,observer_builds=1),indent=2)+'\n')
    print('BOOT OBSERVER BUILT',changed)
if __name__=='__main__':main()
