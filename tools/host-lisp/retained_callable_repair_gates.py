"""Binding gates 1-4 on the retained-callable repair Seed medium (host emulator only).

Host-only, read-only on the guest: memory/register reads, pause/resume, one
write watchpoint (re-pointed at a constant .rodata byte to disarm), one PC
breakpoint that keeps Xemu stepping instructions, and the keyboard queue.  No
guest-memory edits, no builds, links, Seeds or device contact.  Every address
is derived from the Seed ELF; the two transient code bases are predictions
taken from the anchor receipts (build/retained-callable-attribution-r3 for the
lambda form, build/retained-callable-writer-r2/loop-1 for the dotimes/eval
form) and are asserted by the observed transitions, not assumed.

Modes (each a fresh boot, each output directory write-once):
  lambda  gate 3 (+4 on the lambda form): savedlambda -> 19, funcall -> 27
  wipe    gate 4 on the dotimes/eval N = 1 form, then the call -> 7
  sweep   gates 1 and 2: N = 1, 2, 16, 54 loops, each followed by its call
"""
import argparse
import json
import os
import re
import time
import traceback
from pathlib import Path

import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
PROMPT = 'LISP65>'
INSTRUMENT = ROOT/'build/retained-callable-repair-instrument-r1/instrument.json'
LAMBDA = '(progn (setq savedlambda (lambda () 27)) 19)'


def dump(m, out, label, captures, regions=('c2d', 'bank2', 'bank0')):
    known = {'bank0': 0, 'bank2': 0x20000, 'c2d': 0x50000}
    record = dict(label=label, registers=m.command('r'), regions={})
    for name in regions:
        address = known[name]
        data = bytearray()
        for at in range(address, address + 65536, 256):
            response = m.command(f'M {at:08x}')
            rows = re.findall(r':([0-9A-Fa-f]{8}):([0-9A-Fa-f]{32})', response)
            assert [int(a, 16) for a, b in rows] == list(range(at, at + 256, 16)), label
            data.extend(b''.join(bytes.fromhex(b) for a, b in rows))
        p = out / f'{label}-{name}.bin'
        p.write_bytes(data)
        record['regions'][name] = N.bind(p)
    p = out / f'{label}-screen.txt'
    p.write_text(m.screen())
    record['screen'] = N.bind(p)
    captures.append(record)
    (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    print('dump', label, flush=True)
    return record


def submit(m, out, label, form, expected, steps, timeout=900):
    """Type one form; wait for a fresh expected result and the live prompt."""
    before = m.screen()
    m.type_text(form + '\n')
    deadline = time.monotonic() + timeout
    screen = before
    while time.monotonic() < deadline:
        screen = m.screen()
        if C.active(screen) == PROMPT and C.fresh_result(before, screen, expected):
            break
        time.sleep(.1)
    decoded = R.ROWS.decoded_framebuffer(screen).splitlines()
    tail = [line.rstrip() for line in decoded if line.strip()][-6:]
    path = out / f'step-{label}-screen.txt'
    path.write_text(screen)
    ok = C.active(screen) == PROMPT and C.fresh_result(before, screen, expected)
    row = dict(label=label, form=form, expected=expected, passed=ok, tail=tail, screen=N.bind(path))
    steps.append(row)
    (out / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
    print('form', label, form, '->', tail[-2:], 'PASS' if ok else 'FAIL', flush=True)
    if not ok:
        raise AssertionError('expected result absent: ' + form + ' => ' + expected)
    return row


def watched(m, out, form, watch, captures, transitions, final, timeout=600):
    """Type `form` with a write watch on `watch`; capture every transition.

    Stops after `final(before, after)` is true, disarms by re-pointing the
    watch at a constant byte, clears the PC breakpoint and resumes."""
    screen_before = m.screen()
    m.command('t1')
    previous = m.memory16(watch)[0]
    m.begin_breakpoint_connection()
    try:
        m.command(f'w {watch:08x}')
        m.command(f'b {STATUS_ERROR:04x}')
        m.command('t0')
        m.type_text(form + '\n')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = m.memory16(watch)[0]
            if value != previous:
                m.command('t1')
                label = f'watch-{len(transitions)}'
                dump(m, out, label, captures)
                transitions.append(dict(label=label, before=previous, after=value))
                print('watch', transitions[-1], flush=True)
                done = final(previous, value)
                previous = value
                if done:
                    break
                m.command('t0')
            time.sleep(.02)
        else:
            raise AssertionError('watched transition absent')
        m.command(f'w {CONSTANT:08x}')
    finally:
        m.end_breakpoint_connection()
    m.command('t0')
    return screen_before


def finish(m, out, label, form, expected, before, steps, timeout=900):
    """Wait for the watched form's own fresh result and live prompt."""
    deadline = time.monotonic() + timeout
    screen = m.screen()
    while time.monotonic() < deadline:
        screen = m.screen()
        if C.active(screen) == PROMPT and C.fresh_result(before, screen, expected):
            break
        time.sleep(.1)
    path = out / f'step-{label}-screen.txt'
    path.write_text(screen)
    tail = [l.rstrip() for l in R.ROWS.decoded_framebuffer(screen).splitlines() if l.strip()][-6:]
    ok = C.active(screen) == PROMPT and C.fresh_result(before, screen, expected)
    steps.append(dict(label=label, form=form, expected=expected, passed=ok, tail=tail, screen=N.bind(path)))
    (out / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
    print('form', label, form, '->', tail[-2:], 'PASS' if ok else 'FAIL', flush=True)
    if not ok:
        raise AssertionError('expected result absent: ' + form + ' => ' + expected)


def main():
    global STATUS_ERROR, CONSTANT
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['lambda', 'wipe', 'sweep'])
    parser.add_argument('--attempt', default='r1')
    options = parser.parse_args()
    out = ROOT / f'build/retained-callable-repair-gates-{options.mode}-{options.attempt}'
    out.mkdir(exist_ok=False, parents=True)
    identity = json.loads(INSTRUMENT.read_text())
    world = next(w for w in identity['worlds'] if w['role'] == 'candidate')
    os.environ['LISP65_COST_CONFIG'] = world['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT'] = str(out / 'pc-current.txt')
    elf = N.checked_binding(world['ELF'])
    binary = N.checked_binding(world['binary'])
    medium = N.checked_binding(world['medium'])
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    STATUS_ERROR = truth.symbol('vm_status_error_code').value
    CONSTANT = truth.section('.rodata').address
    symbols = {n: truth.symbol(n).value for n in ('vm_status', 'vm_status_error_code', 'lisp65_c2_phase_scratch',
                                                   'c2_runtime', 'c2_append_rollback_prepare_phase',
                                                   'c2_append_rollback_wipe_chip_phase',
                                                   'c2_append_rollback_zero_chip_code', 'c2_facade_c2_dma')}
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)
    parent = R.ProbeMonitor

    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=120)

    R.ProbeMonitor = Monitor
    run = None
    captures, steps, transitions = [], [], []
    error = None
    plan = {}
    try:
        run = R.start_run(options.mode, medium, out, args)
        m = run['monitor']
        if options.mode == 'lambda':
            plan = dict(watch=0x2ED39, source='build/retained-callable-attribution-r3 (entry 2046 at Bank 2 $ED39)')
            m.command('t1'); dump(m, out, 'boot', captures); m.command('t0')
            before = watched(m, out, LAMBDA, plan['watch'], captures, transitions,
                             lambda before, after: before != 0 and after == 0)
            finish(m, out, 'lambda', LAMBDA, '19', before, steps)
            m.command('t1'); dump(m, out, 'after-lambda', captures); m.command('t0')
            submit(m, out, 'funcall', '(funcall savedlambda)', '27', steps)
            m.command('t1'); dump(m, out, 'after-funcall', captures); m.command('t0')
        elif options.mode == 'wipe':
            plan = dict(watch=0x2ED25, source='build/retained-callable-writer-r2 loop-1 remnant $ED25-$ED55')
            submit(m, out, 'require', '(require "defstruct")', 'T', steps)
            m.command('t1'); dump(m, out, 'package', captures); m.command('t0')
            form = "(dotimes (n 1) (eval '(defun capw () 7)))"
            before = watched(m, out, form, plan['watch'], captures, transitions,
                             lambda before, after: before != 0 and after == 0)
            finish(m, out, 'loop', form, 'NIL', before, steps)
            m.command('t1'); dump(m, out, 'after-loop', captures); m.command('t0')
            submit(m, out, 'call', '(capw)', '7', steps)
            m.command('t1'); dump(m, out, 'after-call', captures); m.command('t0')
        else:
            submit(m, out, 'require', '(require "defstruct")', 'T', steps)
            m.command('t1'); dump(m, out, 'package', captures); m.command('t0')
            for count in (1, 2, 16, 54):
                name = f'capn{count}'
                submit(m, out, f'loop-{count}', f"(dotimes (n {count}) (eval '(defun {name} () 7)))", 'NIL', steps)
                m.command('t1'); dump(m, out, f'loop-{count}', captures); m.command('t0')
                submit(m, out, f'call-{count}', f'({name})', '7', steps)
                m.command('t1'); dump(m, out, f'call-{count}', captures); m.command('t0')
        vm_status = m.memory16(symbols['vm_status'])[0]
    except BaseException:
        error = traceback.format_exc()
        vm_status = None
        print(error, flush=True)
    finally:
        output = R.finish_run(run) if run else None
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else 'CAPTURED: ' + options.mode.upper(),
            binding='d3d5044b', authority='e0be22c1', mode=options.mode, plan=plan, world=world,
            symbols=symbols, vm_status_at_end=vm_status, steps=steps, transitions=transitions,
            captures=captures, output=output, error=error, driver=N.bind(Path(__file__)),
            builds=0, links=0, seeds=0, device_contacts=0), indent=2) + '\n')
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
