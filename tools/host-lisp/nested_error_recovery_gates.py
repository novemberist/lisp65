"""Nested-error recovery gates as emulator rows (host emulator only).

Host-only, read-only on the guest: memory/register reads, pause/resume and the
keyboard queue.  No guest-memory edits, builds, links, Seeds or device contact.
Every address is derived from the world's ELF.  Each mode is a fresh boot with
a write-once output directory; the directory planes (C2D header, images,
entries, resolutions, roots) and all 64 KiB of Bank 2 are dumped from memory
around every form and compared by nested_error_recovery_gate_analysis.py.

Modes:
  nested  gate 1: (let ((q 1)) (eval '(capzz))) at 9 images -> the exact
          error, live prompt, c2_ready = 1, then (+ 4 5) -> 9
  depth2  gate 3: two nested evals (the error raised two transients deep),
          the inner-transient variant, and the normal-path control (an
          error-free form with a temporary image), then (+ 4 5) -> 9
  normalpath  gate 3 control: a PC breakpoint on the fast path's PREPARE
          result test; a depth-1 runtime error reaches it with result NONE
          (0, old path), an error-free transient form never reaches it, the
          nested error reaches it with PREPARED (2, new retirement)
  overcap gate 2 minimal: fresh boot, one 60-iteration eval/defun loop past
          the cap -> OUT OF MEMORY at 63 images, then one more refused group
  cumulative gate 2 cumulative: 1, 2, 16 (each called), 54 past the cap, then
          one more refused group; every definition still callable
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
INSTRUMENT = ROOT/'build/nested-error-recovery-instrument-r1/instrument.json'
ERROR = '*** UNDEFINED FUNCTION: CAPZZ'
NESTED = "(let ((q 1)) (eval '(capzz)))"
DEPTH2 = "(let ((q 1)) (eval '(let ((r 2)) (eval '(capzz)))))"
INNER = "(let ((q 1)) (eval '(let ((r 2)) (capzz))))"
NORMAL = "(let ((q 1)) (eval '(+ 4 5)))"
OOM = '*** VM: OUT OF MEMORY'
PLAIN = '(let ((q 1)) (+ q 8))'
DEPTH1 = '(let ((q 1)) (capzz))'


def result_test(elf, truth):
    """Address of the fast path's PREPARE-result load and the result byte, from the ELF."""
    import subprocess
    member = truth.symbol('c2_abort_empty_journal_derived')
    text = subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'), '-d', '--no-show-raw-insn',
                                    f'--start-address={member.value}',
                                    f'--stop-address={member.value+member.bytes}', str(elf)], text=True)
    rows = [(int(m[1], 16), m[2]) for m in re.finditer(r'^\s+([0-9a-f]+):\s+(.*)$', text, re.M)]
    calls = [i for i, (_, ins) in enumerate(rows) if ins.startswith('jsr') and '<c2_overlay_call>' in ins]
    assert len(calls) == 4, calls
    scratch = truth.symbol('lisp65_c2_phase_scratch').value
    for at, ins in rows[calls[1]+1:]:
        m = re.match(r'ldx\s+\$([0-9a-f]+)\s', ins+' ')
        if m and int(m[1], 16) - scratch == 0xd5:
            return at, int(m[1], 16)
    raise AssertionError('PREPARE result load not found')


def dump(m, out, label, captures, symbols, regions=('c2d', 'bank2', 'bank0')):
    known = {'bank0': 0, 'bank2': 0x20000, 'c2d': 0x50000}
    record = dict(label=label, registers=m.command('r'), regions={},
                  c2_ready=m.memory16(symbols['c2_ready'])[0])
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
    print('dump', label, 'c2_ready', record['c2_ready'], flush=True)
    return record


def submit(m, out, label, form, expected, steps, timeout=180):
    """Type one form; wait for a fresh expected result and the live prompt."""
    before = m.screen()
    t0 = time.monotonic()
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
    row = dict(label=label, form=form, expected=expected, passed=ok, tail=tail, screen=N.bind(path),
               wall_seconds=round(time.monotonic()-t0, 1))
    steps.append(row)
    (out / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
    print('form', label, form, '->', tail[-2:], 'PASS' if ok else 'FAIL', flush=True)
    if not ok:
        raise AssertionError('expected result absent: ' + form + ' => ' + expected)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['nested', 'depth2', 'normalpath', 'overcap', 'cumulative'])
    parser.add_argument('--world', choices=['candidate', 'baseline'], default='candidate')
    parser.add_argument('--attempt', default='r1')
    parser.add_argument('--label', default='')
    options = parser.parse_args()
    suffix = ('-baseline' if options.world == 'baseline' else '') + f'-{options.attempt}'
    out = ROOT / f'build/nested-error-recovery-gates-{options.mode}{suffix}'
    out.mkdir(exist_ok=False, parents=True)
    identity = json.loads(INSTRUMENT.read_text())
    world = next(w for w in identity['worlds'] if w['role'] == {'candidate': 'candidate', 'baseline': 'anchor'}[options.world])
    os.environ['LISP65_COST_CONFIG'] = world['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT'] = str(out / 'pc-current.txt')
    elf = N.checked_binding(world['ELF'])
    binary = N.checked_binding(world['binary'])
    medium = N.checked_binding(world['medium'])
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    symbols = {n: truth.symbol(n).value for n in ('vm_status', 'c2_ready', 'lisp65_c2_phase_scratch', 'c2_runtime',
                                                   'c2_abort_empty_journal_derived', 'pending_code')}
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)
    parent = R.ProbeMonitor

    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=120)

    R.ProbeMonitor = Monitor
    BREAK = result_test(elf, truth)
    run = None
    captures, steps, breaks = [], [], []
    error = None
    try:
        run = R.start_run(options.mode, medium, out, args)
        m = run['monitor']

        def snap(label):
            m.command('t1'); dump(m, out, label, captures, symbols); m.command('t0')
        def breakpoint_row(label, form, expected, want_hit):
            bp, result = BREAK
            before = m.screen()
            m.command('t1')
            m.begin_breakpoint_connection()
            hit = None
            try:
                m.command(f'b {bp:04x}')
                m.command('t0')
                m.type_text(form + '\n')
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    regs = m.command('r')
                    if f'{bp:04X} ' in regs:
                        hit = dict(pc=bp, result=m.memory16(result)[0], registers=regs)
                        dump(m, out, label+'-bp', captures, symbols)
                        break
                    screen = m.screen()
                    if not want_hit and C.active(screen) == PROMPT and C.fresh_result(before, screen, expected):
                        break
                    time.sleep(.05)
            finally:
                m.end_breakpoint_connection()
            m.command('t0')
            breaks.append(dict(label=label, form=form, want_hit=want_hit, hit=hit))
            (out / 'breakpoints.json').write_text(json.dumps(breaks, indent=2) + '\n')
            print('breakpoint', label, 'hit' if hit else 'no hit', hit and hit['result'], flush=True)
            deadline = time.monotonic() + 120
            screen = m.screen()
            while time.monotonic() < deadline:
                screen = m.screen()
                if C.active(screen) == PROMPT and C.fresh_result(before, screen, expected):
                    break
                time.sleep(.1)
            path = out / f'step-{label}-screen.txt'
            path.write_text(screen)
            ok = C.active(screen) == PROMPT and C.fresh_result(before, screen, expected)
            tail = [l.rstrip() for l in R.ROWS.decoded_framebuffer(screen).splitlines() if l.strip()][-6:]
            steps.append(dict(label=label, form=form, expected=expected, passed=ok, tail=tail, screen=N.bind(path)))
            (out / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
            print('form', label, form, '->', tail[-2:], 'PASS' if ok else 'FAIL', flush=True)
            if not ok:
                raise AssertionError('expected result absent: ' + form + ' => ' + expected)
        submit(m, out, 'require', '(require "defstruct")', 'T', steps)
        snap('package')
        if options.mode == 'normalpath':
            breakpoint_row('depth1', DEPTH1, ERROR, True)
            snap('after-depth1')
            breakpoint_row('plain', PLAIN, '9', False)
            snap('after-plain')
            breakpoint_row('nested', NESTED, ERROR, True)
            snap('after-nested')
            submit(m, out, 'arith', '(+ 4 5)', '9', steps)
            snap('end')
        elif options.mode == 'overcap':
            submit(m, out, 'min', "(dotimes (n 60) (eval '(defun capm () 7)))", OOM, steps, timeout=300)
            snap('after-min')
            submit(m, out, 'call-min', '(capm)', '7', steps)
            submit(m, out, 'arith', '(+ 4 5)', '9', steps)
            snap('after-min-calls')
            submit(m, out, 'refused', "(dotimes (n 1) (eval '(defun capb () 7)))", OOM, steps)
            snap('after-refused')
            submit(m, out, 'call-end', '(capm)', '7', steps)
            snap('end')
        elif options.mode == 'cumulative':
            for count in (1, 2, 16):
                submit(m, out, f'loop-{count}', f"(dotimes (n {count}) (eval '(defun capn{count} () 7)))", 'NIL', steps)
                snap(f'loop-{count}')
                submit(m, out, f'call-{count}', f'(capn{count})', '7', steps)
                snap(f'call-{count}')
            submit(m, out, 'loop-54', "(dotimes (n 54) (eval '(defun capn54 () 7)))", OOM, steps, timeout=300)
            snap('after-54')
            for count in (1, 2, 16, 54):
                submit(m, out, f'recall-{count}', f'(capn{count})', '7', steps)
            snap('after-54-calls')
            submit(m, out, 'refused', "(dotimes (n 1) (eval '(defun capx () 7)))", OOM, steps)
            snap('after-refused')
            submit(m, out, 'arith', '(+ 4 5)', '9', steps)
            snap('end')
        elif options.mode == 'nested':
            submit(m, out, 'nested', NESTED, ERROR, steps)
            snap('after-nested')
            submit(m, out, 'arith', '(+ 4 5)', '9', steps)
            snap('end')
        else:
            submit(m, out, 'depth2', DEPTH2, ERROR, steps)
            snap('after-depth2')
            submit(m, out, 'inner', INNER, ERROR, steps)
            snap('after-inner')
            submit(m, out, 'normal', NORMAL, '9', steps)
            snap('after-normal')
            submit(m, out, 'arith', '(+ 4 5)', '9', steps)
            snap('end')
        vm_status = m.memory16(symbols['vm_status'])[0]
    except BaseException:
        error = traceback.format_exc()
        vm_status = None
        print(error, flush=True)
    finally:
        output = R.finish_run(run) if run else None
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else 'CAPTURED: ' + options.mode.upper(),
            binding='44c021ee', authority='90b5f9f2', mode=options.mode, label=options.label, world=world,
            symbols=symbols, vm_status_at_end=vm_status, steps=steps, captures=captures, output=output,
            breakpoint=dict(pc=BREAK[0], result_address=BREAK[1]), breakpoints=breaks,
            error=error, driver=N.bind(Path(__file__)), builds=0, links=0, seeds=0, device_contacts=0,
            guest_memory_writes=0), indent=2) + '\n')
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
