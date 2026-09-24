"""ca9af627: minimal-reproduction sweep for the retained-callable published-code wipe.

Host-only. Reads emulator memory/registers and feeds the keyboard queue; never
edits guest memory, never builds, links or contacts a device.
"""
import argparse, json, os, re, time, traceback
from pathlib import Path
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-writer-r2'
PROMPT = 'LISP65>'


def dump(m, out, label, captures, regions=('c2d', 'bank2')):
    known = {'bank0': 0, 'bank1': 0x10000, 'bank2': 0x20000, 'c2d': 0x50000}
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


def submit(m, out, label, expression, steps, timeout=900):
    """Type one form, wait for the prompt to come back, record the screen."""
    before = m.screen()
    m.type_text(expression + '\n')
    deadline = time.monotonic() + timeout
    screen = before
    stable = 0
    while time.monotonic() < deadline:
        screen = m.screen()
        if C.active(screen) == PROMPT and screen != before:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        time.sleep(.1)
    decoded = R.ROWS.decoded_framebuffer(screen).splitlines()
    tail = [line.rstrip() for line in decoded if line.strip()][-6:]
    path = out / f'step-{label}-screen.txt'
    path.write_text(screen)
    row = dict(label=label, form=expression, tail=tail, returned_to_prompt=C.active(screen) == PROMPT,
               screen=N.bind(path))
    steps.append(row)
    (out / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
    print('form', label, expression, '->', tail[-2:], flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--counts', default='1,2,3,4,8,16,54')
    options = parser.parse_args()
    out = Path(options.out)
    out.mkdir(exist_ok=False, parents=True)
    counts = [int(x) for x in options.counts.split(',') if x]
    identity = json.loads((ROOT / 'build/anchor-cache-projection-r1/instrument.json').read_text())
    world = identity['worlds'][0]
    os.environ['LISP65_COST_CONFIG'] = world['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT'] = str(out / 'pc-current.txt')
    elf = N.checked_binding(world['ELF'])
    binary = N.checked_binding(world['binary'])
    medium = N.checked_binding(world['medium'])
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    status = truth.symbol('vm_status').value
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)
    parent = R.ProbeMonitor

    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=120)

    R.ProbeMonitor = Monitor
    run = None
    captures = []
    steps = []
    error = None
    try:
        run = R.start_run('sweep', medium, out, args)
        m = run['monitor']
        submit(m, out, 'require', '(require "defstruct")', steps)
        m.command('t1'); dump(m, out, 'baseline', captures, ('c2d', 'bank2', 'bank0')); m.command('t0')
        # Plain top level defun, no eval, no dotimes: the control lane.
        submit(m, out, 'plain-define-1', '(defun capplain () 7)', steps)
        submit(m, out, 'plain-call-1', '(capplain)', steps)
        submit(m, out, 'plain-define-2', '(defun capplain () 7)', steps)
        submit(m, out, 'plain-call-2', '(capplain)', steps)
        submit(m, out, 'plain-define-3', '(defun capplain () 7)', steps)
        submit(m, out, 'plain-call-3', '(capplain)', steps)
        m.command('t1'); dump(m, out, 'plain', captures); m.command('t0')
        for count in counts:
            name = f'capn{count}'
            submit(m, out, f'loop-{count}', f"(dotimes (n {count}) (eval '(defun {name} () 7)))", steps)
            m.command('t1'); dump(m, out, f'loop-{count}', captures); m.command('t0')
            submit(m, out, f'call-{count}', f'({name})', steps)
            m.command('t1'); dump(m, out, f'call-{count}', captures); m.command('t0')
        m.command('t1'); dump(m, out, 'final', captures, ('c2d', 'bank2', 'bank0')); m.command('t0')
        vm_status = m.memory16(status)[0]
    except BaseException:
        error = traceback.format_exc()
        vm_status = None
        print(error, flush=True)
    finally:
        output = R.finish_run(run) if run else None
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else 'CAPTURED: MINIMAL REPRODUCTION SWEEP',
            authority='ca9af627', counts=counts, world=world, vm_status_address=status,
            vm_status_at_end=vm_status, steps=steps, captures=captures, output=output, error=error,
            driver=N.bind(Path(__file__)), builds=0, links=0, seeds=0, device_contacts=0), indent=2) + '\n')
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
