"""ca9af627: receipts for run directories interrupted by the host session crash.

Offline only.  Binds what the interrupted emulator runs left on disk (dumps,
screens, step records, the medium copy and the non-authoritative Xemu log) plus
the inputs and drivers; never fabricates a missing capture.  The mutable 4-GiB
scratch SD copy is excluded, as in the halt card.
"""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = {
    'build/retained-callable-writer-r2': dict(
        driver='tools/host-lisp/retained_callable_writer_probe_r2.py',
        medium='build/dirty-anchor-seed-medium-r1/packed/hardware-sp-seed.d81',
        elf='build/dirty-anchor-final-r3/wplto/lisp65-c2-substitution-linked.prg.elf',
        planned_counts=[1, 2, 3, 4, 8, 16, 54],
        completed='require, plain control (3 definitions, 3 calls), N = 1, 2, 3, 4, 8, 16 '
                  '(loop and call dumps each); interrupted inside the N = 54 loop'),
    'build/retained-callable-writer-r3': dict(
        driver='tools/host-lisp/retained_callable_writer_probe_r3.py',
        medium='build/retained-callable-writer-r1/v230/lisp65-2.3.0/media/lisp65-product.d81',
        elf='build/retained-callable-writer-r1/v230/lisp65-2.3.0/product/lisp65-c2-substitution-linked.prg.elf',
        planned_counts=[1, 54],
        completed='boot, class (a) lambda and funcall, require, N = 1 (loop and call dumps); '
                  'interrupted inside the N = 54 loop'),
}
OBSERVER = 'build/input-cost-attribution-r6/xemu/build/bin/xmega65.native'


def bind(path):
    path = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    for rel, meta in RUNS.items():
        out = ROOT / rel
        target = out / 'receipt.json'
        assert not target.exists(), f'{target} already exists; never overwritten'
        files = [bind(p) for p in sorted(out.rglob('*'))
                 if p.is_file() and p.name != 'system-sd.img' and p.name != 'receipt.json']
        receipt = dict(
            status='PARTIAL: INTERRUPTED BY HOST SESSION CRASH',
            authority='ca9af627', completed=meta['completed'], planned_counts=meta['planned_counts'],
            note='Emulator process killed with the host desktop session; no shutdown '
                 'memory, no shutdown framebuffer and no medium-unchanged check exist for '
                 'this run. Every capture listed is a completed dump written before the crash.',
            steps=json.loads((out / 'steps.json').read_text()),
            captures=json.loads((out / 'captures.json').read_text()),
            inputs=[bind(meta['elf']), bind(meta['medium']), bind(OBSERVER)],
            driver=bind(meta['driver']), receipt_writer=bind(Path(__file__)),
            files=files, excluded=['run-*/system-sd.img (mutable 4-GiB scratch SD copy)'],
            builds=0, links=0, seeds=0, device_contacts=0)
        target.write_text(json.dumps(receipt, indent=2) + '\n')
        print(rel, receipt['status'], len(files), 'files bound')


if __name__ == '__main__':
    main()
