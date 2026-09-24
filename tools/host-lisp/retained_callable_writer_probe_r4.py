"""ca9af627: which top level form shape triggers the transient rollback wipe.

Host-only on the anchor Final; reads memory, feeds the keyboard queue, never
edits guest memory.  No build, link, Seed or device contact.
"""
import argparse, json, os, traceback
from pathlib import Path
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
from elf_truth import ElfTruth
import retained_callable_writer_probe_r2 as P

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-writer-r4'

SHAPES = [
    ('plain', '(defun shapea () 7)', '(shapea)'),
    ('eval', "(eval '(defun shapeb () 7))", '(shapeb)'),
    ('progn', '(progn (defun shapec () 7) 1)', '(shapec)'),
    ('dotimes', '(dotimes (n 1) (defun shaped () 7))', '(shaped)'),
    ('let', '(let ((q 1)) (defun shapee () 7))', '(shapee)'),
    ('dotimes-eval', "(dotimes (n 1) (eval '(defun shapef () 7)))", '(shapef)'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(OUT))
    options = parser.parse_args()
    out = Path(options.out)
    out.mkdir(exist_ok=False, parents=True)
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
        run = R.start_run('shapes', medium, out, args)
        m = run['monitor']
        P.submit(m, out, 'require', '(require "defstruct")', steps)
        m.command('t1'); P.dump(m, out, 'baseline', captures); m.command('t0')
        for label, define, call in SHAPES:
            P.submit(m, out, f'define-{label}', define, steps)
            m.command('t1'); P.dump(m, out, f'define-{label}', captures); m.command('t0')
            P.submit(m, out, f'call-{label}', call, steps)
    except BaseException:
        error = traceback.format_exc()
        print(error, flush=True)
    finally:
        output = R.finish_run(run) if run else None
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else 'CAPTURED: FORM SHAPE DISCRIMINATION',
            authority='ca9af627', world=world, vm_status_address=status, shapes=SHAPES,
            steps=steps, captures=captures, output=output, error=error,
            driver=N.bind(Path(__file__)), builds=0, links=0, seeds=0, device_contacts=0), indent=2) + '\n')
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
