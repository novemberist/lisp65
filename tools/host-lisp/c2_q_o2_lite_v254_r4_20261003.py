"""2.5.4 r4 C2-Q successor: the mapcan domain change moves the measurement.

lib/domain-tier1.lisp folds mapcan pairwise (2.5.4 LIB2: no argument-count
cliff above 12 results).  Every C2-Q world that loads the list tier carries
the larger mapcan object: +46 code bytes, no new object, +334 steps in the
two source runs; nothing else may move.  Baseline and candidate move
identically (the Comfort price over baseline, the tracked Q cases and the
oracle are unchanged).  The continuity control is the inherited v253 one
with the 2.5.4 deltas, measured against the r3 receipt (which reproduced the
v253 measurement).  The r3 tool and receipt stay immutable; the O2-lite
source pin is the 2.5.4 live pin.
"""
from unittest.mock import patch

import o2_lite_consumers_v254_20261003 as V254
import c2_q_o2_lite_v253_r3_20261001 as R3

Q, S = R3.Q, R3.S
RECEIPT = 'config/c2-q-v254-r4-20261003-receipt.json'
HISTORY = {**R3.HISTORY,
           'tools/host-lisp/c2_q_o2_lite_v253_r3_20261001.py': S.S.bind('tools/host-lisp/c2_q_o2_lite_v253_r3_20261001.py')['sha256'],
           R3.RECEIPT: S.S.bind(R3.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['inputs']]
MAPCAN_OBJECTS, MAPCAN_CODE_BYTES, MAPCAN_STEPS = 0, 46, 334


def derive():
    with S.suites():
        current = Q.H.derive()
    old = S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['current']
    with patch.object(Q, 'NTH_OBJECTS', MAPCAN_OBJECTS), patch.object(Q, 'NTH_CODE_BYTES', MAPCAN_CODE_BYTES), \
         patch.object(Q, 'NTH_STEPS', MAPCAN_STEPS):
        return Q.nth_continuity(current, old)


if __name__ == '__main__':
    V254.route_children()
    V254.install()
    S.finish('c2_q', derive, RECEIPT, HISTORY, (__file__, V254.__file__, R3.__file__, Q.__file__, *INPUTS))
