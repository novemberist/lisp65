"""ca9af627: reproduce both retained-callable defect classes on the public 2.3.0 medium.

Host-only, read-only on the guest: memory/register reads, pause/resume, keyboard
queue.  No build, no link, no Seed, no device contact.  All addresses are derived
from the 2.3.0 ELF; no anchor address is reused.
"""
import argparse, hashlib, json, os, re, time, traceback
from pathlib import Path
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth
import retained_callable_writer_probe_r2 as P

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-writer-r3'
V230 = ROOT / 'build/retained-callable-writer-r1/v230/lisp65-2.3.0'
ELF230 = V230 / 'product/lisp65-c2-substitution-linked.prg.elf'
D81230 = V230 / 'media/lisp65-product.d81'
ELF230_SHA = '6a144e8aeebf94d26dba68d4ce72c44d3db8e4f6a4d733ce2a3f32ecf0ba7375'
D81230_SHA = 'd98e6d7520ae7afe358795c093f78d2fcea35cc5ff0459fd1668f8469706b73b'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--counts', default='1,54')
    options = parser.parse_args()
    out = Path(options.out)
    out.mkdir(exist_ok=False, parents=True)
    counts = [int(x) for x in options.counts.split(',') if x]
    assert sha256(ELF230) == ELF230_SHA, 'released 2.3.0 ELF SHA drift'
    assert sha256(D81230) == D81230_SHA, 'released 2.3.0 product D81 SHA drift'
    identity = json.loads((ROOT / 'build/anchor-cache-projection-r1/instrument.json').read_text())
    world = identity['worlds'][0]
    # Cost instrumentation is only required for the observer to start; this card
    # makes no cycle or performance claim on any of its runs.
    os.environ['LISP65_COST_CONFIG'] = world['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT'] = str(out / 'pc-current.txt')
    binary = N.checked_binding(world['binary'])
    truth = ElfTruth.read(ELF230, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    symbols = {name: truth.symbol(name).value for name in
               ['vm_status', 'lisp65_c2_phase_scratch', 'c2_runtime', 'c2_decode_active',
                'c2_append_rollback_wipe_chip_phase', 'c2_append_rollback_zero_chip_code',
                'c2_facade_c2_dma', 'c2_append_rollback_prepare_phase']}
    print('2.3.0 symbols', {k: hex(v) for k, v in symbols.items()}, flush=True)
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)
    parent = R.ProbeMonitor

    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=180)

    R.ProbeMonitor = Monitor
    run = None
    captures = []
    steps = []
    error = None
    vm_status = None
    try:
        run = R.start_run('v230', D81230, out, args)
        m = run['monitor']
        m.command('t1'); P.dump(m, out, 'boot', captures, ('c2d', 'bank2', 'bank0')); m.command('t0')
        # Class (a): retained anonymous callable in a top level form.
        P.submit(m, out, 'lambda', '(progn (setq savedlambda (lambda () 27)) 19)', steps)
        m.command('t1'); P.dump(m, out, 'lambda', captures, ('c2d', 'bank2', 'bank0')); m.command('t0')
        P.submit(m, out, 'lambda-call', '(funcall savedlambda)', steps)
        # Class (b): eval-published redefinition loop.
        P.submit(m, out, 'require', '(require "defstruct")', steps)
        m.command('t1'); P.dump(m, out, 'require', captures); m.command('t0')
        for count in counts:
            name = f'capn{count}'
            P.submit(m, out, f'loop-{count}', f"(dotimes (n {count}) (eval '(defun {name} () 7)))", steps)
            m.command('t1'); P.dump(m, out, f'loop-{count}', captures); m.command('t0')
            P.submit(m, out, f'call-{count}', f'({name})', steps)
            m.command('t1'); P.dump(m, out, f'call-{count}', captures); m.command('t0')
        m.command('t1'); P.dump(m, out, 'final', captures, ('c2d', 'bank2', 'bank0')); m.command('t0')
        vm_status = m.memory16(symbols['vm_status'])[0]
    except BaseException:
        error = traceback.format_exc()
        print(error, flush=True)
    finally:
        output = R.finish_run(run) if run else None
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT: PROBE ERROR' if error else 'CAPTURED: 2.3.0 REPRODUCTION',
            authority='ca9af627', counts=counts, release='lisp65-2.3.0',
            elf=dict(path=str(ELF230.relative_to(ROOT)), sha256=ELF230_SHA),
            medium=dict(path=str(D81230.relative_to(ROOT)), sha256=D81230_SHA),
            observer=world['binary'], symbols=symbols, vm_status_at_end=vm_status,
            steps=steps, captures=captures, output=output, error=error,
            driver=N.bind(Path(__file__)), sweep_driver=N.bind(ROOT / 'tools/host-lisp/retained_callable_writer_probe_r2.py'),
            builds=0, links=0, seeds=0, device_contacts=0), indent=2) + '\n')
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
