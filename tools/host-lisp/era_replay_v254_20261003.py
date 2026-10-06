"""Shared runner for 2.5.4 era-scoped replays of immutable 2.5.3 consumers.

The O2-lite consumer era pins the exact Comfort-plane sources
(o2_lite_consumers_20260929.SOURCES: lib/lite-hot.lisp,
lib/repl-comfort-v250.lisp and the REPL-COMFORT suite
config/comfort-default-plane/libraries/repl-comfort-suite.json among them).
The 2.5.4 package card changes three of them on purpose (RP1 result guard,
HIST1 comment scan, two new suite functions), and the IDE/LCC cards change
further Lisp sources and suites.  Consumers that witness historical (2.5.2 /
2.5.3) artifacts are therefore replayed unchanged in the sealed 2.5.3 source
world: lib/*.lisp, tests/bytecode JSON and the REPL-COMFORT suite are read
from the 2.5.3 sealing commit.  Receipts, tools, media and the byte ledger
stay live.  Child suite runs that the O2-lite routing starts in a fresh
process (outside any era world, as in 2.5.3) use the 2.5.4 live pin.  A consumer that already replays the 2.5.2 world (the v253 era
wrappers) keeps it: the inner world takes precedence for Lisp sources and
suites, the outer 2.5.3 world only supplies the suite configuration, whose
2.5.3 bytes equal the 2.5.2 bytes.  The 2.5.4 changes are gated by the 2.5.4
suites, harnesses and live successors, not by these replays.
"""
import runpy
import sys
from pathlib import Path

import evidence_era as E
import c2_v254_r1_common as C
import o2_lite_consumers_20260929 as O
import o2_lite_consumers_v254_20261003 as V

COMMIT = C.ERA_V253
ROOT = Path(__file__).resolve().parents[2]
EXTRA = ['config/comfort-default-plane/libraries/repl-comfort-suite.json']


def world():
    return E.host_source_world(COMMIT, EXTRA)


def controls():
    """The immutable O2-lite pin is exactly the sealed 2.5.3 world."""
    for path, digest in O.SOURCES.items():
        C.require(E.era_bind(COMMIT, path)['sha256'] == digest, 'O2-lite pin is not the 2.5.3 era: ' + path)
    C.require(set(EXTRA) <= set(O.SOURCES), 'replayed configuration is not an O2-lite pinned source')


def run(target, allowed, me):
    if allowed is not None and sys.argv[1:] not in allowed:
        raise SystemExit('usage: %s %s' % (me, ' | '.join(' '.join(a) for a in allowed)))
    controls()
    V.route_children()
    with world() as reads:
        runpy.run_path(str(ROOT / 'tools/host-lisp' / target), run_name='__main__')
    if not reads:
        raise E.EraError('2.5.3-era replay of %s consumed no host sources' % target)


def run_live(target, allowed, me):
    """Run a live consumer under the 2.5.4 O2-lite pin (o2_lite_consumers_v254_20261003)."""
    if allowed is not None and sys.argv[1:] not in allowed:
        raise SystemExit('usage: %s %s' % (me, ' | '.join(' '.join(a) for a in allowed)))
    V.route_children()
    V.install()
    runpy.run_path(str(ROOT / 'tools/host-lisp' / target), run_name='__main__')


def pin_disk_r7_source_controls():
    """2.5.4 form of era_replay_v253_20260930.pin_disk_r7_source_controls.

    disk_r7_consumers_20260930.source_controls() pins lib/m65-disk.lisp, the
    r7 suites and (through o2_lite_consumers_20260929.controls) the O2-lite
    sources.  They are checked in the sealed 2.5.2 world, as in 2.5.3, with
    the REPL-COMFORT suite configuration read from that world too and the
    immutable O2-lite pin restored for the check (a live 2.5.4 pin installed by
    the caller applies to everything else).
    """
    import disk_r7_consumers_20260930 as D
    import era_replay_v253_20260930 as R253
    original = D.source_controls
    def source_controls():
        pinned = O.SOURCES
        O.SOURCES = V.PREDECESSOR
        try:
            with E.host_source_world(R253.COMMIT, EXTRA):
                original()
        finally:
            O.SOURCES = pinned
    D.source_controls = source_controls
