"""Matched cold boot, including first input poll after retirement; no product link.

Reuse Card L boot observer with one explicit keyboard-event predicate.
ELF vm_callprim, A in 13/14/60, only after banner-return. This charges
retirement and prompt rendering independent of inlined keyboard helpers.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import traceback
import time
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import d81_persistence_fault as D
from card_l_r1_common import arguments
from nested_error_recovery_lanes import cost_config
from boot_ledger_observer import configure
from c2_crc_codegen_gate import disassembly_rows,_direct_operand
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-fifth-cold-boot-r4'
BASE=ROOT/'build/card-l-boot-instrument-r2/candidate'


def build():
    OUT.mkdir(exist_ok=False)
    prior=P.load(ROOT/'build/card-l-r1/instrument-comfort.json')['worlds'][0]
    baseline=dict(role='baseline',ELF=prior['ELF'],medium=prior['medium'])
    candidate=dict(role='candidate',ELF=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'))
    # Comfort augments only the library directory; its consumed cold loader
    # and all boot payloads remain identical to Card L's bound loader.
    a=D.visible_files(N.checked_binding(prior['medium']).read_bytes())
    b=D.visible_files((ROOT/'build/card-l-seed-medium-r2/media-seed/card-l.d81').read_bytes())
    assert all(a[k]==v for k,v in b.items() if k!=b'L65INDEX')
    recipe=P.load(ROOT/'build/card-l-boot-instrument-r2/configuration.json')['worlds'][1]['command']
    worlds=[]
    for world,loader in [(baseline,ROOT/'build/card-l-seed-medium-r2/media-seed/autoboot.c65.elf'),(candidate,ROOT/'build/set-b-seed-medium-r6/media-seed/autoboot.c65.elf')]:
        dest=OUT/world['role'];dest.mkdir()
        subprocess.run(['cp','-a','--reflink=auto',str(BASE/'observer'),str(dest/'observer')],check=True)
        elf=N.checked_binding(world['ELF']);configure(dest,paths=[loader,elf],medium=world['medium'])
        t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        main=t.symbol('main');dump=subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-d','--no-show-raw-insn',str(elf)],text=True)
        calls=[r for r in disassembly_rows(dump) if r['section']==main.section and main.value<=r['address']<main.value+main.bytes and r['opcode']=='jsr' and _direct_operand(r)==t.symbol('vm_runtime_overlay_install_island').value]
        assert len(calls)==1
        changes=dict(CARRIER_START=t.symbol('__lisp65_boot_carrier_start').value,CARRIER_END=t.symbol('__lisp65_boot_carrier_end').value,CARRIER_MAIN=main.value,CARRIER_RETURN=calls[0]['address']+3)
        header=dest/'observer/xemu/boot_observer.h';raw=header.read_text()
        for key,value in changes.items():raw,n=re.subn(r'#define '+key+r' \d+u',f'#define {key} {value}u',raw);assert n==1
        guard='        if(CPU65.pc!=b->pc || in_hypervisor || boot_last_linear!=b->pc)continue;'
        assert raw.count(guard)==1
        raw=raw.replace(guard,guard+'\n        if(i==BOOT_N-1 && (!boot_seen[11] || !(CPU65.a==13 || CPU65.a==14 || CPU65.a==60)))continue;')
        header.write_text(raw)
        poll=t.symbol('vm_callprim');sec=t.section(poll.section);sig=t.section_bytes(sec.name)[poll.value-sec.address:poll.value-sec.address+16];assert len(sig)==16
        header=dest/'observer/xemu/boot_boundaries.h';raw=header.read_text();assert raw.count('\n};')==1
        raw=raw.replace('\n};','\n{1,%d,"first-keyboard-primitive",{%s}},\n};'%(poll.value,','.join(str(x) for x in sig)));header.write_text(raw)
        config=P.load(dest/'configuration.json');assert len(config['boundaries'])==12
        config['boundaries'].append(dict(world=1,name='first-keyboard-primitive',pc=poll.value,section=poll.section,signature=sig.hex()))
        config['carrier']=changes;P.write(dest/'configuration.json',config)
        # Exact observer code inherited; only two configuration headers differ.
        for name in ['xemu/cpu65.c','targets/mega65/mega65.c','targets/mega65/uart_monitor.c']:
            assert (BASE/'observer'/name).read_bytes()==(dest/'observer'/name).read_bytes()
        (dest/'observer/xemu/cpu65.c').touch()
        cmd=[a.replace(str(BASE),str(dest)) for a in recipe]
        done=subprocess.run(cmd,cwd=ROOT,capture_output=True);(dest/'build.log').write_bytes(done.stdout+done.stderr)
        P.write(dest/'build.json',dict(command=cmd,exit=done.returncode,driver=P.bind(Path(__file__)),configuration=P.bind(dest/'configuration.json'),parent=P.bind(ROOT/'build/card-l-boot-instrument-r2/configuration.json'),product_links=0))
        assert done.returncode==0,done.stderr.decode()
        world.update(binary=P.bind(dest/'observer/build/bin/xmega65.native'),cost_config=cost_config(elf),configuration=P.bind(dest/'configuration.json'))
        worlds.append(world);print('observer built',world['role'],flush=True)
    P.write(OUT/'instrument.json',dict(status='CONFIGURED; LIVE GATES PENDING',worlds=worlds,observer_builds=2,product_links=0,driver=P.bind(Path(__file__))))


def run():
    instrument=P.load(OUT/'instrument.json');rows=[];error=None;launches=0
    old=R.ProbeMonitor
    class Monitor(old):
        def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=180)
    R.ProbeMonitor=Monitor
    try:
        for w in instrument['worlds']:
            dest=OUT/w['role']/'measurement';dest.mkdir();guest=None
            os.environ['LISP65_BOOT_LEDGER']=str(dest/'boot.txt');os.environ['LISP65_CARRIER_WATCH']=str(dest/'writes.txt');os.environ['LISP65_COST_CONFIG']=w['cost_config']
            try:
                launches+=1
                guest=R.start_run('cold',N.checked_binding(w['medium']),dest,arguments(w,600));m=guest['monitor']
                deadline=time.monotonic()+10
                while not any(line.startswith('E 12 ') for line in (dest/'boot.txt').read_text().splitlines()):
                    assert time.monotonic()<deadline,'first actual input-event boundary missing'
                    time.sleep(.05)
                m.command('t1');prompt=m.screen();(dest/'prompt.txt').write_text(prompt)
                events={}
                for line in (dest/'boot.txt').read_text().splitlines():
                    f=line.split()
                    if f[0]=='E':events.setdefault(int(f[1]),int(f[2]))
                assert {0,10,11,12}<=events.keys(),events
                keyboard=next(line.split() for line in (dest/'boot.txt').read_text().splitlines() if line.startswith('E 12 '))
                assert int(keyboard[3]) in (13,14,60) and events[12]>events[11]
                (dest/'keyboard-boundary.json').write_text(__import__('json').dumps(dict(event=keyboard,rule='ELF vm_callprim, A=read-key13/poll-key14/key-event60, after banner return'))+'\n')
                writes=(dest/'writes.txt').read_text().splitlines();assert len(writes)==1 and writes[0].startswith('END ')
                _,low,count=writes[0].split();assert int(low)>=0xce00 and int(count)==0
                t=ElfTruth.read(N.checked_binding(w['ELF']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
                ready=m.memory16(t.symbol('c2_ready').value)[0];assert ready==1
                arm=None
                if w['role']=='candidate':
                    arm=m.memory16(t.symbol('c2r_boot_count').value)[0];assert arm&128
                    assert m.memory_range(0x5de80,8192)==(S.PRODUCT/'set-b-tenants.bin').read_bytes()
                rows.append(dict(world=w,initializing_cycles=events[10]-events[0],banner_return_cycles=events[11]-events[0],input_ready_cycles=events[12]-events[0],stack_low=int(low),carrier_writes=int(count),ready=ready,arm=arm,prompt=P.bind(dest/'prompt.txt'),ledger=P.bind(dest/'boot.txt'),writes=P.bind(dest/'writes.txt')))
                print(w['role'],'cold input cycles',rows[-1]['input_ready_cycles'],flush=True)
            finally:
                if guest:R.finish_run(guest)
        assert N.checked_binding(rows[0]['prompt']).read_bytes()==N.checked_binding(rows[1]['prompt']).read_bytes(),'prompt identity differs'
        delta=rows[1]['input_ready_cycles']-rows[0]['input_ready_cycles']
        assert delta<=20250000,('cold boot exceeds Card L +0.5s at 40.5MHz',delta)
    except BaseException:error=traceback.format_exc()
    P.write(OUT/'receipt.json',dict(status='HALT' if error else 'PASS: MATCHED COLD BOOT THROUGH FIRST INPUT POLL',rows=rows,error=error,delta_cycles=rows[1]['input_ready_cycles']-rows[0]['input_ready_cycles'] if len(rows)==2 else None,allowance_cycles=20250000,clock_hz=40500000,observer_builds=2,guest_launches=launches,product_links=0,device_contacts=0))
    if error:print(error,flush=True);raise SystemExit(1)
    print('PASS matched cold boot',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['build','run']);a=ap.parse_args()
    build() if a.mode=='build' else run()
