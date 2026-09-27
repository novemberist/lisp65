"""First executed Set B gate: qualified observer, medium boot and live prompt.

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
            screen = monitor.wait_screen(['LISP65>'],timeout=180)
            (out/'boot-screen.txt').write_text(screen)
            assert C.active(screen) == 'LISP65>'
            monitor.command('t1')
            try:
                result['registers'] = monitor.command('r')
                result['ready'] = monitor.memory16(truth.symbol('c2_ready').value)[0]
                assert result['ready'] == 1
                if role != 'baseline':
                    result['retirement_latch'] = monitor.memory16(truth.symbol('c2r_boot_count').value)[0]
                    assert result['retirement_latch'] & 128, 'Positive boot failed to arm retirement'
                    image = monitor.memory_range(0x5de80,8192)
                    (out/'tenant-readback.bin').write_bytes(image)
                    assert image == (MEDIAROOT/'media-seed/set-b-tenants.bin').read_bytes(), 'Tenant image differs at first prompt'
            finally: monitor.command('t0')
            G.submit(monitor,out,'arithmetic','(+ 4 5)','9',steps,timeout=180)
            print('PASS',role,'medium boot, READY=1 and arithmetic; candidate arm/tenant check',flush=True)
        except BaseException:
            error = traceback.format_exc()
        finally:
            if monitor is not None:
                try:
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
    P.write(out/'receipt.json',dict(status='HALT' if error else 'PASS: MEDIUM BOOT AND LIVE PROMPT',world=world,
        driver=P.bind(Path(__file__)),result=result,steps=steps,error=error,log=P.bind(logpath),
        cold_boot_timing='NOT MEASURED',histograms='NOT QUALIFIED',product_builds=0,product_links=0,observer_builds=0,device_contacts=0))
    if error: print(error,flush=True); raise SystemExit(1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--role',choices=['baseline','candidate'],required=True)
    args = ap.parse_args(); main(args.out.resolve(),args.role)
