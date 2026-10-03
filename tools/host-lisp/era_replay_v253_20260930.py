"""Shared runner for 2.5.3 era-scoped replays of immutable 2.5.2 consumers.

The r7 disk consumers pin the exact 2.5.2 Lisp sources (lib/m65-disk.lisp
etc.) and suites. The 2.5.3 candidate changes those sources on purpose (D3
lossless load, D5 full-directory remount), so the historical consumers are
replayed unchanged in the sealed 2.5.2 source world. Receipts, tools, media
and the byte ledger stay live; only lib/*.lisp and tests/bytecode JSON are
read from the sealing commit. The 2.5.3 disk changes are gated by the
2.5.3 suites and receipts, not by these replays.
"""
import runpy
import sys
from pathlib import Path

import evidence_era as E

COMMIT = '49d128599c73a5b6eb6b8595431923cd30b84491'
ROOT = Path(__file__).resolve().parents[2]


def run(target, allowed, me):
    if sys.argv[1:] not in allowed:
        raise SystemExit('usage: %s %s' % (me, ' | '.join(' '.join(a) for a in allowed)))
    with E.host_source_world(COMMIT) as reads:
        runpy.run_path(str(ROOT / 'tools/host-lisp' / target), run_name='__main__')
    if not reads:
        raise E.EraError('historical replay of %s consumed no host sources' % target)


def pin_disk_r7_source_controls():
    """Run the immutable r7 source pins against the sealed 2.5.2 world.

    disk_r7_consumers_20260930.finish() pins lib/m65-disk.lisp and the r7
    suites by content hash before deriving. For a live 2.5.3 derive those pins
    are checked in the era that sealed them; the derived measurements and the
    bound input hashes stay live.
    """
    import disk_r7_consumers_20260930 as D
    original = D.source_controls
    def controls():
        with E.host_source_world(COMMIT):
            original()
    D.source_controls = controls
