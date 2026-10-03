"""2.5.3 dated Comfort-REPL successor.

The 2026-09-29 O2-lite receipt measures two things. (1) The resident/Seed
loader-content lane compares against frozen 2.5.2 product planes; it must be
evaluated in the sealed 2.5.2 source world (the editor product list domain gate
rightly rejects the frozen resident nth against today's domain-tier1). (2) The
live ship-input regression suite, which is measured live and therefore carries
the 2.5.3 nth change (%nth-after-domain-check): exactly one more function and
object, seven more code and directory bytes and 45 more steps, nothing else.
The predecessor tool and receipt stay immutable.
"""
import copy
from unittest.mock import patch

import c2_v160_comfort_repl_o2_lite_20260929 as P
import o2_lite_consumers_20260929 as S

RECEIPT = 'config/c2-v160-comfort-repl-o2-lite-v253-receipt-20260930.json'
ERA252 = '49d128599c73a5b6eb6b8595431923cd30b84491'
HISTORY = {**P.HISTORY,
           'tools/host-lisp/c2_v160_comfort_repl_o2_lite_20260929.py': S.S.bind('tools/host-lisp/c2_v160_comfort_repl_o2_lite_20260929.py')['sha256'],
           P.RECEIPT: S.S.bind(P.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / P.RECEIPT).read_bytes())['inputs']]
NTH = dict(functions=1, objects=1, code_bytes=7, directory_bytes=7, steps=45)


def continuity(current, old):
    expected = copy.deepcopy(old)
    for key, delta in NTH.items():
        expected['live_ship'][key] += delta
    S.S.require(current == expected, 'Comfort-REPL measurement moved beyond the nth domain change')
    trial = copy.deepcopy(current)
    trial['live_ship']['steps'] += 1
    S.S.require(trial != expected, 'Comfort-REPL nth delta mutation survived')
    return current


def derive():
    original = S.live
    def era_live():
        with S.E.host_source_world(ERA252):
            return original()
    with patch.object(S, 'live', era_live):
        current = P.derive()
    old = S.json.loads((S.ROOT / P.RECEIPT).read_bytes())['current']
    return continuity(current, old)


if __name__ == '__main__':
    S.finish('c2-v160-comfort-repl', derive, RECEIPT, HISTORY,
             (__file__, P.__file__, *INPUTS, P.H.__file__, 'tools/host-lisp/strings_generated_r11_20260929.py'))
