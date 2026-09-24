"""Rebind the qualified read-only boot/writer observer to the carrier Seed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from elf_truth import ElfTruth
from c2_crc_codegen_gate import disassembly_rows, _direct_operand

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/boot-only-carrier-observer-r2'
OUT=ROOT/'build/boot-only-carrier-native-boot-r1'
ELF=ROOT/'build/boot-only-carrier-seed-medium-r1/materialized/lisp65-c2-substitution-linked.prg.elf'


def bind(p):
    return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def build():
    OUT.mkdir(exist_ok=False)
    subprocess.run(['cp','-a','--reflink=auto',str(BASE/'observer'),str(OUT/'observer')],check=True)
    source=ROOT/'build/ov-crc16-r1/boot_ledger_observer.py'
    raw=source.read_text().replace('build/ov-crc16-seed-medium-r1/',
                                 'build/boot-only-carrier-seed-medium-r1/')
    scope=dict(__name__='carrier_boot_configuration',__file__=__file__)
    exec(compile(raw,str(source),'exec'),scope)
    scope['configure'](OUT)
    truth=ElfTruth.read(ELF,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    main=truth.symbol('main'); values=truth.symbol_values()
    dump=subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-d','--no-show-raw-insn',str(ELF)],text=True)
    calls=[r for r in disassembly_rows(dump) if r['section']==main.section
           and main.value<=r['address']<main.value+main.bytes and r['opcode']=='jsr'
           and _direct_operand(r)==values['vm_runtime_overlay_install_island']]
    assert len(calls)==1
    changes=dict(CARRIER_START=values['__lisp65_boot_carrier_start'],
                 CARRIER_END=values['__lisp65_boot_carrier_end'],
                 CARRIER_MAIN=main.value,CARRIER_RETURN=calls[0]['address']+3)
    header=OUT/'observer/xemu/boot_observer.h'
    old=header.read_text(); new=old
    for key,value in changes.items():
        new,n=re.subn(r'#define '+key+r' \d+u',f'#define {key} {value}u',new)
        assert n==1
    header.write_text(new)
    (OUT/'run.py').write_bytes((BASE/'run.py').read_bytes())
    command=json.loads((BASE/'build.json').read_text())['command']
    command=[arg.replace(str(BASE),str(OUT)) for arg in command]
    with (OUT/'build.log').open('w') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    (OUT/'build.json').write_text(json.dumps(dict(status='BUILT; NATIVE OBSERVATION PENDING',
        inherited_qualification=bind(BASE/'qualification.json'),elf=bind(ELF),changes=changes,
        baseline_header=bind(BASE/'observer/xemu/boot_observer.h'),header=bind(header),
        binary=bind(OUT/'observer/build/bin/xmega65.native'),command=command,
        product_builds=0,device_contacts=0),indent=2)+'\n')


def run():
    env={**os.environ,'LISP65_CARRIER_WATCH':str(OUT/'writes.txt')}
    subprocess.run(['python3','-B',str(OUT/'run.py'),'capture-r1'],env=env,check=True)
    lines=(OUT/'writes.txt').read_text().splitlines()
    assert len(lines)==1 and lines[0].startswith('END ')
    _,low,writes=lines[0].split()
    assert int(low)>=0xce00 and int(writes)==0
    assert (OUT/'capture-r1/prompt.txt').read_bytes()==(BASE/'capture-r1/prompt.txt').read_bytes()
    (OUT/'qualification.json').write_text(json.dumps(dict(status='PASS: NORMAL CARRIER-LIVE BOOT',
        stack_low=int(low),carrier_writes=int(writes),prompt_identical=True,
        inputs=[bind(OUT/'build.json'),bind(OUT/'configuration.json')],
        outputs=[bind(OUT/'writes.txt'),bind(OUT/'capture-r1/boot.txt'),bind(OUT/'capture-r1/receipt.json')],
        limits=['not exhaustive native error injection','not device acceptance']),indent=2)+'\n')
    print('PASS: carrier-live boot, zero writes, unchanged prompt; stack low',hex(int(low)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','run'])
    globals()[p.parse_args().action]()
