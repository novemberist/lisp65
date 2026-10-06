#!/usr/bin/env python3
"""2.5.4 candidate-time naming successor (r1): inherited classifications/mutations over the 2.5.4 User Guide.

Immutable predecessors: the 2.5.3 ship-time naming successor (r3) and its receipt (the r3 receipt binds the
2.5.3 guide and stays as recorded; the derivation is reused over the live guide). record: exclusive creation
of config/c2-v254-r1-public-naming-receipt.json.
"""
import c2_v253_r3_public_naming as P
import c2_v254_r1_common as S

HISTORY = {'tools/host-lisp/c2_v253_r3_public_naming.py':
               'fc7a64fc1b0966cfa71c210b32a981482bea87b011f0aaa7d09ed5a280effcb1',
           'config/c2-v253-r3-public-naming-receipt.json':
               '85d225a1752ce7f6e67d28e5758ed9b535b1f78faba14d63d85d27373e2e1c77'}
RECEIPT = 'config/c2-v254-r1-public-naming-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.4; no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    return P.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, P.__file__, P.P.__file__, P.P.H.__file__, P.P.H.H.__file__, 'docs/user-guide.md'),
             claim=CLAIM)
