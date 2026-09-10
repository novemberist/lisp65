#!/usr/bin/env python3
"""Run the existing renderer rows headlessly, with optional PC observation.

Uses the already packed and qualified medium unchanged. Never rebuilds media.
Counter snapshots are host output; framebuffer and D5 remain guest oracles.
"""
import argparse
import json
import os
from pathlib import Path
import time

import renderer_native_session_prefilter as SESSION
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

ROOT = SESSION.ROOT
OUT = ROOT/'build/capacity/card0-r3'

def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')

def execute(group, observer, attempt):
    cfg = SESSION.contract()
    SESSION.M.check()
    instrument = json.loads((OUT/'instrument-build.json').read_text())
    baseline = json.loads((ROOT/'build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json').read_text())
    binding = instrument['binary'] if observer else baseline['binary']
    binary = ROOT/binding['path']
    assert SESSION.M.bind(binary)['sha256'] == binding['sha256']
    packed = json.loads((SESSION.OUT/'packed-receipt.json').read_text())
    medium = Path(packed['medium']['path'])
    output = OUT/('observed' if observer else 'control')/attempt/group
    output.mkdir(parents=True)
    histogram = output/'pc-current.txt'
    if observer: os.environ['LISP65_DWX_PC_OUTPUT'] = str(histogram)
    else: os.environ.pop('LISP65_DWX_PC_OUTPUT', None)
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=240)
    truth = ElfTruth.read(Path(cfg['pair']['elf']['path']), llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    selected = next(g for g in cfg['groups'] if g['id'] == group)
    # f05b6d41 superseded the draft frame-only E29 oracle. This observation
    # must never certify printer safety or replace its sealed watermark proof.
    if group == 'printer-known-issue':
        selected['rows'][-1].pop('failure')
        selected['rows'][-1]['watermark'] = 'wrap observed; normal framebuffer is not stack safety'
    rows = []; run = None; error = None
    def snapshot(m, name):
        if observer:
            answer = m.command('~pcsave')
            assert 'DWX PC save: 0' in answer, answer
            target = output/(name+'-pc.txt')
            target.write_bytes(histogram.read_bytes())
            return SESSION.M.bind(target)
    original_monitor = R.ProbeMonitor
    class StartupMonitor(original_monitor):
        def wait_screen(self, required, timeout=20):
            try:
                return super().wait_screen(required, timeout=60)
            except Exception:
                self.command('t1')
                (output/'startup-stop.txt').write_text(self.screen())
                self.command('~exit')
                raise
    R.ProbeMonitor = StartupMonitor
    try:
        run = R.start_run(group, medium, output, args); m = run['monitor']
        m.command('t1'); screen = m.screen()
        decoded = R.ROWS.decoded_framebuffer(screen)
        assert 'WORKBENCH 2.0.0' in decoded and C.active(screen) == 'LISP65>'
        (output/'boot-framebuffer.txt').write_text(screen)
        rows.append(dict(id='boot', passed=True, histogram=snapshot(m, 'boot')))
        m.command('t0')
        for row in selected['rows']:
            if observer: m.command('~pcrowreset')
            before = m.screen(); m.type_text(row['form']+'\n')
            deadline = time.monotonic()+35; okay = False
            while time.monotonic() < deadline:
                screen = m.screen(); decoded = R.ROWS.decoded_framebuffer(screen)
                if row.get('watermark'):
                    # Completion is only a bounded sampling cutpoint. Wrap is
                    # checked from the host push observer below, not this text.
                    okay = C.active(screen) == 'LISP65>' and C.fresh_result(before, screen, '823')
                elif row.get('failure'): okay = decoded.count('*** E29') >= 2
                elif 'max_frames' in row:
                    okay = C.active(screen) == 'LISP65>' and any(C.fresh_result(before, screen, str(n)+' '+row['value']) for n in range(row['max_frames']+1))
                else: okay = C.active(screen) == 'LISP65>' and C.fresh_result(before, screen, row['value'])
                if okay: break
                time.sleep(.03)
            m.command('t1'); screen = m.screen()
            path = output/(row['id']+'-framebuffer.txt'); path.write_text(screen)
            result = dict(id=row['id'], passed=okay, oracle=SESSION.M.bind(path), expected=row,
                          histogram=snapshot(m, row['id']))
            if row.get('watermark') and observer:
                stack = next(line.split() for line in histogram.read_text().splitlines() if line.startswith('S '))
                result['watermark'] = dict(min_sp=int(stack[1]), wraps=int(stack[2]))
                okay = okay and int(stack[1]) == 0 and int(stack[2]) >= 1
                result['passed'] = okay
            if row.get('watermark') and not observer:
                result['watermark'] = 'not instrumented; no stack-safety claim'
            rows.append(result)
            print(group, row['id'], okay, flush=True)
            assert okay, 'bound framebuffer row failed: '+row['id']
            if row['id'] == 'd5-marker':
                result['d5'] = {}
                for name in ('nsym', 'npool'):
                    s = truth.symbol(name); raw = m.memory_range(s.value, s.bytes)
                    result['d5'][name] = dict(address=s.value, bytes=raw.hex(), used=int.from_bytes(raw,'little'))
            if not row.get('failure') and not row.get('watermark'): m.command('t0')
    except Exception as exc:
        error = repr(exc)
        raise
    finally:
        R.ProbeMonitor = original_monitor
        if run:
            run['monitor'].command('t1'); R.finish_run(run)
        receipt = output/'receipt.json'
        write(receipt, dict(recorded_on=stable_recorded_on(receipt),
            status='RED' if error else 'ROWS PASS; NOT A POPULATION QUALIFICATION',
            error=error, product=cfg['pair'], medium=SESSION.M.bind(medium), binary=SESSION.M.bind(binary),
            group=selected, rows=rows, observer=observer, device_claim=False))

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('group', choices=[g['id'] for g in SESSION.contract()['groups']])
    p.add_argument('--observer', action='store_true'); p.add_argument('--attempt', default='r2')
    a = p.parse_args(); execute(a.group, a.observer, a.attempt)
