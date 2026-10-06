#!/usr/bin/env python3
"""2.5.4 LCC nesting ladder: the v253 gate on the 2.5.4 candidate, required >= 2.5.3.

Successor of lcc_nesting_ladder_v253_20261002 (immutable tool and receipt).  The
whole v253 derivation runs unchanged (2.5.2 / 2.5.3-r7 worlds, emission
control, calibration against the emulator points, candidate >= 2.5.2 with no
higher high-water, r7 negative control, multi-pair setq, F2 forms, candidate
semantics) with two adaptations:

  resident suite  The v253 candidate is emitted against the 2.5.3 product
                  resident suite (local build tree).  Its sealed domain-tier1
                  projection carries the 2.5.3 mapcan; the 2.5.4 LIB2 mapcan
                  (lib/domain-tier1.lisp) is projected onto it with the same
                  hunk rule (project_text, era 2.5.3 -> live) into this gate's
                  scratch tree, so the editor product list domain check sees
                  the live domain.  Nothing else in the suite changes.
  >= 2.5.3        The 2.5.3 candidate column of the v253 receipt is the
                  delivered 2.5.3 LCC (same projection rule and blob).  Every
                  shape of the 2.5.4 candidate must reach at least that depth,
                  with no higher frame or root high-water at any 2.5.3 depth.
                  The 2.5.4 improvements are recorded per shape.

Usage: lcc_nesting_ladder_v254_20261003.py generate | check   (receipt is write-once)
Scratch output: build/lcc-nesting-ladder-v254-20261003-live/ (never bound by the receipt).
"""
from __future__ import annotations

import json
import os
import sys

import lcc_nesting_ladder_v253_20261002 as L
import c2_v254_r1_common as C

ROOT = L.ROOT
PREDECESSOR = L.RECEIPT
HISTORY = {'tools/host-lisp/lcc_nesting_ladder_v253_20261002.py':
               '6d60e0c4e4435f37a19bec096a6f2ffea100d356d51df8a16673b1c7e5bb8f3e',
           'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v253-20261002.json':
               'd6ca4762a2db8ed5d314a28fb7652611ebe0c59cf8961a8a3cb4da60195ffad4'}
L.FORMAT = 'lisp65-lcc-nesting-ladder-v254-20261003'
L.RECEIPT = ROOT / 'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v254-20261003.json'
L.LIVE = ROOT / 'build/lcc-nesting-ladder-v254-20261003-live'
BASE_RESIDENT = L.RESIDENT_SUITE
DOMAIN = 'lib/domain-tier1.lisp'
SEALED = 'domain-tier1-sealed.lisp'


def resident_v254():
    """Project the live domain-tier1 onto the sealed copy of the 2.5.3 resident suite."""
    L.require((ROOT / BASE_RESIDENT).is_file(), 'missing 2.5.3 product resident suite (local build tree): ' + BASE_RESIDENT)
    suite = json.loads((ROOT / BASE_RESIDENT).read_text())
    hits = [i for i, s in enumerate(suite['sources']) if os.path.basename(s) == SEALED]
    L.require(len(hits) == 1, 'resident suite sealed domain seam')
    sealed = open(suite['sources'][hits[0]]).read()
    text, mode = L.project_text(sealed, L.era_text(C.ERA_V253, DOMAIN), (ROOT / DOMAIN).read_text(), DOMAIN)
    L.require(text != sealed, 'live domain projection did not move the sealed resident domain')
    out = L.LIVE / 'resident'
    (out / 'sources').mkdir(parents=True, exist_ok=True)
    (out / 'sources' / SEALED).write_text(text)
    suite['sources'][hits[0]] = str(out / 'sources' / SEALED)
    (out / 'suite.json').write_text(json.dumps(suite, indent=2) + '\n')
    return str((out / 'suite.json').relative_to(ROOT)), mode


def compare_253(data):
    data = json.loads(L.canonical(data))     # the receipt's own key/tuple normalisation
    old = json.loads(PREDECESSOR.read_text())
    rows = {r['shape']: r for r in old['ladder']}
    improved = []
    for row in data['ladder']:
        then = rows[row['shape']]['candidate']
        L.require(row['candidate'] >= then, 'REGRESSION vs 2.5.3 %s: %d < %d' % (row['shape'], row['candidate'], then))
        if row['candidate'] > then:
            improved.append(dict(shape=row['shape'], v253=then, v254=row['candidate']))
        for depth, (f, r) in old['high_water']['candidate'][row['shape']].items():
            cf, cr = data['high_water']['candidate'][row['shape']][depth]
            L.require(cf <= f and cr <= r, 'high-water above 2.5.3: %s depth %s frames %d/%d roots %d/%d'
                      % (row['shape'], depth, cf, f, cr, r))
    L.require(len(data['ladder']) == len(rows), 'shape population drift against 2.5.3')
    return improved


def main(argv):
    if argv not in (['generate'], ['check']):
        raise SystemExit('usage: lcc_nesting_ladder_v254_20261003.py generate | check')
    os.chdir(ROOT)
    try:
        C.history(HISTORY)
        L.RESIDENT_SUITE, mode = resident_v254()
        data = L.render()
        data['v253_predecessor'] = dict(receipt=C.bind(str(PREDECESSOR.relative_to(ROOT))),
                                        improved=compare_253(data), shapes_not_lower=len(data['ladder']))
        data['resident_domain_projection'] = dict(base_suite=BASE_RESIDENT, domain=C.bind(DOMAIN),
                                                  era=C.ERA_V253, mode=mode)
        raw = L.canonical(data)
        if argv == ['generate']:
            with L.RECEIPT.open('xb') as stream:
                stream.write(raw)
        else:
            L.require(L.RECEIPT.read_bytes() == raw, 'receipt drift: ' + str(L.RECEIPT.relative_to(ROOT)))
    except (L.LadderError, ValueError) as exc:
        print('lcc-nesting-ladder-v254: FAIL: %s' % exc, file=sys.stderr)
        return 1
    print('lcc-nesting-ladder-v254: PASS shapes=%d candidate>=2.5.2 and >=2.5.3 everywhere; improved: %s'
          % (len(data['ladder']), ','.join('%s %d->%d' % (r['shape'], r['v253'], r['v254'])
                                          for r in data['v253_predecessor']['improved'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
