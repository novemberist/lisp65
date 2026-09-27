"""Set B read-path halt: executed reset boundaries on the unchanged third Seed.

Uses the existing r6 observer with ELF-derived cost coordinates for stopped
memory/framebuffer rows only. No timing/histogram qualification is claimed.
Only copied SD/D81 images are opened; no device access, no product build.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import re
sys.dont_write_bytecode = True
import set_b_producer as P
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
import nested_error_recovery_gates as G
from nested_error_recovery_lanes import cost_config
from elf_truth import ElfTruth

ROOT = P.ROOT
MEDIAROOT = ROOT/'build/set-b-seed-medium-r4'


def registers(m):
    raw=m.command('r')
    matches=list(re.finditer(r"(?m)^([0-9A-F]{4}) ([0-9A-F]{2}) ([0-9A-F]{2}) ([0-9A-F]{2}) ([0-9A-F]{2}) ([0-9A-F]{2}) ([0-9A-F]{4})",raw))
    assert matches,raw
    match=matches[-1]
    return dict(zip(('pc','a','x','y','z','b','sp'),(int(v,16) for v in match.groups())),raw=raw)


def boundary(m,pc,label,rows,opcode):
    # The qualified observer stops AFTER executing the breakpoint opcode.
    # Its unsolicited pre-instruction register row is not current state.
    m.command(f'b {pc:04x}')
    m.command('t0')
    until=time.monotonic()+180
    while time.monotonic()<until:
        r=registers(m)
        if f'{pc:04X} ' in r['raw']:
            if r['b']==0 and m.memory_range(pc,len(opcode)//2)==bytes.fromhex(opcode):break
            m.command('t0') # Same PC in ROM or another mapped overlay.
        time.sleep(.02)
    else:raise AssertionError(f'Boundary {label} not reached: {r}')
    r.update(label=label,breakpoint_pc=pc,ready=m.memory16(0x8c)[0],arm=m.memory16(0x31)[0],
        zp=m.memory_range(0,32).hex(),journal=m.memory_range(0x5de20,72).hex(),
        stack=m.memory_range(0x100,256).hex(),opcode=m.memory16(pc).hex())
    rows.append(r)
    print(label,hex(pc),'post PC',hex(r['pc']),'READY',r['ready'],'arm',r['arm'],flush=True)
    return r


def main(out, role):
    out.mkdir(exist_ok=False,parents=True)
    parent_path = ROOT/'build/card-l-r1/instrument-comfort.json'
    parent = P.load(parent_path); prior = parent['worlds'][0]
    baseline_elf = N.checked_binding(prior['ELF'])
    assert cost_config(baseline_elf) == prior['cost_config']
    binary = N.checked_binding(parent['binary'])
    assert P.load(MEDIAROOT/'readback.json')['status'] == 'PASS: INDEPENDENT MEDIA READBACK'
    elf = baseline_elf if role == 'baseline' else ROOT/'build/set-b-product-r3/wplto/resident-island-seed.prg.elf'
    medium = N.checked_binding(prior['medium']) if role == 'baseline' else MEDIAROOT/'media-seed/set-b-comfort.d81'
    truth = ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    world = dict(role=role, ELF=P.bind(elf), medium=P.bind(medium), binary=P.bind(binary), cost_config=cost_config(elf))
    P.write(out/'instrument.json',dict(world=world,parent=P.bind(parent_path),driver=P.bind(Path(__file__)),
        control_config_reproduced=True,scope='boot, framebuffer and stopped-memory only; no timing or histogram claim',product_builds=0,observer_builds=0))
    run_dir = out/'run-boot'; run_dir.mkdir()
    sd = run_dir/'system-sd.img'; source_sd = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'))
    subprocess.run(['cp','--reflink=auto','--sparse=always',str(source_sd),str(sd)],check=True)
    disk = run_dir/medium.name; shutil.copyfile(medium,disk); disk.chmod(0o444)
    rom = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
    monitor_path = Path('/tmp')/f'l65-set-b-{os.getpid()}-{role}.sock'
    assert not monitor_path.exists()
    memory = run_dir/'memory.bin'; screenpath = run_dir/'framebuffer.txt'; logpath = run_dir/'xemu.log'
    command = [str(R.SAFE_RUNNER),str(memory), '600',str(binary), '-skipconfigfile','-headless','-testing','-sleepless','-besure','-fastboot','-nosound',
               '-rom',str(rom),'-sdimg',str(sd),'-8',str(disk),'-autoload','-uartmon',str(monitor_path),'-dumpscreen',str(screenpath),'-dumpmem',str(memory)]
    env = dict(os.environ,LISP65_COST_CONFIG=world['cost_config'],LISP65_DWX_PC_OUTPUT=str(out/'pc-current.txt'))
    P.write(out/'launch.json',dict(command=command,rom=N.bind(rom),source_medium=P.bind(medium),source_sd=str(source_sd),
        sd_policy='fresh reflink/sparse copy; original SD not opened by emulator',environment={k:env[k] for k in ('LISP65_COST_CONFIG','LISP65_DWX_PC_OUTPUT')}))
    proc = None; monitor = None; error = None; result = {}; steps = []
    with logpath.open('wb') as log:
        try:
            proc = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            deadline = time.monotonic()+12
            while not monitor_path.exists() and time.monotonic() < deadline:
                if proc.poll() is not None: raise RuntimeError(f'Observer exited before monitor: {proc.returncode}')
                time.sleep(.05)
            assert monitor_path.exists(), 'Observer UART monitor unavailable'
            monitor = R.ProbeMonitor(monitor_path)
            monitor.begin_breakpoint_connection()
            monitor.command('t1')
            # All PCs bound to the immutable Seed below, never to overlapping
            # overlay names. Enter slot 62 only after the slot-55 return in main.
            assert world['ELF']['sha256']=='1eb22d5282acae5e39c1a1ea37bd749d6e524c9fb45005791b298a26bb5b71cf'
            boundary(monitor,0xa85d,'stage succeeded; call reset',steps,'20e1fe')
            read=boundary(monitor,0xc3f4,'reset physical-read call',steps,'20ebb5')
            zp=bytes.fromhex(read['zp']); destination=int.from_bytes(zp[6:8],'little')
            result['read_destination']=destination
            result['destination_before']=monitor.memory16(destination)[0]
            boundary(monitor,0x2354,'selector entry',steps,'48daba')
            trace=[]
            for _ in range(32):
                r=registers(monitor);r['opcode']=monitor.memory16(r['pc']).hex();trace.append(r)
                if r['pc']==0x2b00:break
                monitor.command('t')
            result['selector_steps']=trace
            assert trace[-1]['pc']==0x2b00,trace
            boundary(monitor,0xc3f7,'misrouted read returns',steps,'a003aa')
            result['destination_after']=monitor.memory16(destination)[0]
            boundary(monitor,0xc416,'reset status selected',steps,'984818')
            boundary(monitor,0xa860,'reset returned; before READY',steps,'a201')
            boundary(monitor,0xa862,'READY set',steps,'868c')
            monitor.end_breakpoint_connection()
            monitor.command('t0')
            screen=monitor.wait_screen(['LISP65>'],timeout=180)
            (out/'boot-screen.txt').write_text(screen)
            monitor.command('t1')
            result['ready_at_prompt']=monitor.memory16(0x8c)[0]
            result['arm_at_prompt']=monitor.memory16(0x31)[0]
            assert result['ready_at_prompt']==1 and result['arm_at_prompt']==0
            assert result['destination_before']==result['destination_after']==255
            assert steps[4]['a']==3 and steps[4]['y']==3
            print('PASS: reset refuses an unread sentinel after wrong overlay dispatch',flush=True)
        except BaseException:
            error = traceback.format_exc()
        finally:
            if monitor is not None:
                try:
                    if getattr(monitor, '_breakpoint_socket', None) is not None:
                        monitor.end_breakpoint_connection()
                    (out/'last-screen.txt').write_text(monitor.screen())
                    (out/'last-registers.txt').write_text(monitor.command('r'))
                    monitor.command('~exit')
                except Exception as e: result['monitor_shutdown_error'] = repr(e)
            if proc is not None:
                if proc.poll() is None and monitor is None:
                    # Token helper targets only this emulator, never its parents.
                    subprocess.run([sys.executable,str(ROOT/'scripts/kill-xmega65-by-token.py'),str(memory)],cwd=ROOT,check=True)
                try: result['process_exit'] = proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    subprocess.run([sys.executable,str(ROOT/'scripts/kill-xmega65-by-token.py'),str(memory)],cwd=ROOT,check=True)
                    result['process_exit'] = proc.wait(timeout=15)
            monitor_path.unlink(missing_ok=True)
    assert P.bind(disk)['sha256'] == P.bind(medium)['sha256']
    P.write(out/'receipt.json',dict(status='HALT' if error else 'PASS: EXECUTED RESET REFUSAL ATTRIBUTION',world=world,
        driver=P.bind(Path(__file__)),result=result,steps=steps,error=error,log=P.bind(logpath),
        cold_boot_timing='NOT MEASURED',histograms='NOT QUALIFIED',product_builds=0,product_links=0,observer_builds=0,device_contacts=0))
    if error: print(error,flush=True); raise SystemExit(1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--role',choices=['candidate'],required=True)
    args = ap.parse_args(); main(args.out.resolve(),args.role)
