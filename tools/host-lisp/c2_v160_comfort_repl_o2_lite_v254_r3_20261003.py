"""2.5.4 r3 Comfort-REPL successor.

The v253 derivation has three lanes; each keeps its world:
(1) the historical strings lane (sealed O2-lite era, unchanged);
(2) the resident/Seed loader-content lane, compared against the frozen 2.5.2
    product planes and therefore evaluated in the sealed 2.5.2 source world.
    2.5.4 changes two pinned Comfort sources and the REPL-COMFORT suite
    configuration, so this lane now also reads that configuration from the
    2.5.2 world and checks the immutable O2-lite pin there (the 2.5.4 pin
    applies to the live lanes only);
(3) the live ship-input regression suite, measured live: it carries the
    2.5.4 mapcan change (lib/domain-tier1.lisp, LIB2) -- exactly 46 more code
    bytes and 334 more steps, no new function, object or directory
    byte -- on top of the asserted 2.5.3 nth delta.
The complete r2 measurement (which reproduced the v253 one) must be
reproduced except for that delta.  The r2 tool and receipt stay immutable.
"""
import copy
from unittest.mock import patch

import o2_lite_consumers_v254_20261003 as V254
import c2_v160_comfort_repl_o2_lite_v253_r2_20261001 as R2

V = R2.V
P, S = V.P, V.S
RECEIPT = 'config/c2-v160-comfort-repl-o2-lite-v254-receipt-r3-20261003.json'
HISTORY = {**R2.HISTORY,
           'tools/host-lisp/c2_v160_comfort_repl_o2_lite_v253_r2_20261001.py':
               S.S.bind('tools/host-lisp/c2_v160_comfort_repl_o2_lite_v253_r2_20261001.py')['sha256'],
           R2.RECEIPT: S.S.bind(R2.RECEIPT)['sha256']}
EXTRA = ('config/comfort-default-plane/libraries/repl-comfort-suite.json',)
MAPCAN = dict(code_bytes=46, steps=334)


def continuity(current, old):
    expected = copy.deepcopy(old)
    for key, delta in MAPCAN.items():
        expected['live_ship'][key] += delta
    S.S.require(current == expected, 'Comfort-REPL measurement moved beyond the mapcan domain change')
    trial = copy.deepcopy(current)
    trial['live_ship']['steps'] += 1
    S.S.require(trial != expected, 'Comfort-REPL mapcan delta mutation survived')
    return current


def derive():
    original = S.live
    def era_live():
        pinned = S.SOURCES
        S.SOURCES = V254.PREDECESSOR
        try:
            with S.E.host_source_world(V.ERA252, extra_paths=EXTRA):
                return original()
        finally:
            S.SOURCES = pinned
    with patch.object(S, 'live', era_live):
        current = P.derive()
    old = S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['current']
    return continuity(current, old)


if __name__ == '__main__':
    V254.route_children()
    V254.install()
    S.finish('c2-v160-comfort-repl', derive, RECEIPT, HISTORY,
             (__file__, V254.__file__, R2.__file__, V.__file__, P.__file__, *V.INPUTS, P.H.__file__,
              'tools/host-lisp/strings_generated_r11_20260929.py'))
