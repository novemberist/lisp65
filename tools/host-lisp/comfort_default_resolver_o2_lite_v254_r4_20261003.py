"""2.5.4 r4 resolver successor: the mapcan domain change moves the compile summary.

lib/domain-tier1.lisp folds mapcan pairwise (2.5.4 LIB2).  The target Bank-2
compile of the resolver world therefore reports 46 more code bytes, 62 more
ext bytes, one more literal node/patch and 334 more steps; no new function,
object or directory byte.  The inherited v253 derivation runs unchanged with
its delta table extended by exactly these fields (its references are the
2026-09-27 successor and the 2026-09-28 r2 receipt, so the table is the 2.5.3
nth delta plus the 2.5.4 mapcan delta), including both inherited mutation
controls; against the r3 receipt (which reproduced the v253 measurement) only
the mapcan delta is admitted.  The r3 tool and receipt stay immutable; the
O2-lite source pin is the 2.5.4 live pin.
"""
import copy
import sys
from unittest.mock import patch

import o2_lite_consumers_v254_20261003 as V254
import comfort_default_resolver_o2_lite_v253_r3_20261001 as R3

Q, S = R3.Q, R3.S
RECEIPT = 'config/comfort-default-resolver-v254-r4-20261003-receipt.json'
HISTORY = {**R3.HISTORY,
           'tools/host-lisp/comfort_default_resolver_o2_lite_v253_r3_20261001.py':
               S.S.bind('tools/host-lisp/comfort_default_resolver_o2_lite_v253_r3_20261001.py')['sha256'],
           R3.RECEIPT: S.S.bind(R3.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['inputs']]
MAPCAN = [dict(code_bytes=46, steps=334),
          dict(code_bytes=46, ext_bytes=62),
          dict(literal_nodes=1, literal_patches=1, steps=334)]


def combined(a, b):
    return [{k: x.get(k, 0) + y.get(k, 0) for k in set(x) | set(y)} for x, y in zip(a, b, strict=True)]


def derive():
    with patch.object(Q, 'DELTAS', combined(Q.DELTAS, MAPCAN)):
        current = Q.derive()
    old = S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['current']
    with patch.object(Q, 'DELTAS', MAPCAN):
        S.S.require(Q.nth_equal(current, old), 'resolver moved beyond the mapcan delta against r3')
        trial = copy.deepcopy(current)
        trial['target_bank2_compile']['summary'][2] = trial['target_bank2_compile']['summary'][2].replace('steps=', 'steps=1')
        S.S.require(not Q.nth_equal(trial, old), 'resolver mapcan-delta mutation survived')
    return current


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append('check')
    V254.route_children()
    V254.install()
    S.finish('comfort_default_resolver', derive, RECEIPT, HISTORY, (__file__, V254.__file__, R3.__file__, Q.__file__, *INPUTS))
