"""ca9af627: the 2.3.0 N = 54 capfill row only (r3 was interrupted inside it).

Host-only, read-only on the guest: memory/register reads, pause/resume and the
keyboard queue.  Addresses come from the 2.3.0 ELF.  No build, link, Seed or
device contact.
"""
import argparse, json, os, traceback
from pathlib import Path
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
from elf_truth import ElfTruth
import retained_callable_writer_probe_r2 as P
import retained_callable_writer_probe_r3 as V

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-writer-r6'


def main():
    OUT.mkdir(exist_ok=False)
    assert V.sha256(V.ELF230) == V.ELF230_SHA and V.sha256(V.D81230) == V.D81230_SHA
    world = json.loads((ROOT / 'build/anchor-cache-projection-r1/instrument.json').read_text())['worlds'][0]
    os.environ['LISP65_COST_CONFIG'] = world['cost_config']   # observer start only; no cost claim
    os.environ['LISP65_DWX_PC_OUTPUT'] = str(OUT / 'pc-current.txt')
    binary = N.checked_binding(world['binary'])
    status = ElfTruth.read(V.ELF230, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj').symbol('vm_status').value
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)
    parent = R.ProbeMonitor

    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=180)

    R.ProbeMonitor = Monitor
    run = None; captures = []; steps = []; error = None
    try:
        run = R.start_run('v230-n54', V.D81230, OUT, args)
        m = run['monitor']
        P.submit(m, OUT, 'require', '(require "defstruct")', steps)
        m.command('t1'); P.dump(m, OUT, 'require', captures); m.command('t0')
        P.submit(m, OUT, 'loop-54', "(dotimes (n 54) (eval '(defun capn54 () 7)))", steps, timeout=1800)
        m.command('t1'); P.dump(m, OUT, 'loop-54', captures); m.command('t0')
        P.submit(m, OUT, 'call-54', '(capn54)', steps)
        m.command('t1'); P.dump(m, OUT, 'call-54', captures, ('c2d', 'bank2', 'bank0')); m.command('t0')
    except BaseException:
        error = traceback.format_exc(); print(error, flush=True)
    finally:
        output = R.finish_run(run) if run else None
        (OUT / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else 'CAPTURED: 2.3.0 N=54 ROW',
            authority='ca9af627', release='lisp65-2.3.0',
            elf=dict(path=str(V.ELF230.relative_to(ROOT)), sha256=V.ELF230_SHA),
            medium=dict(path=str(V.D81230.relative_to(ROOT)), sha256=V.D81230_SHA),
            observer=world['binary'], vm_status_address=status, steps=steps, captures=captures,
            output=output, error=error, driver=N.bind(Path(__file__)),
            helpers=[N.bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r2.py'),
                     N.bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r3.py')],
            builds=0, links=0, seeds=0, device_contacts=0), indent=2) + '\n')
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
