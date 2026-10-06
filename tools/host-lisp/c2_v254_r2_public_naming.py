#!/usr/bin/env python3
"""2.5.4 ship-time naming successor (r2): inherited classifications/mutations over the ship-time User Guide.

Immutable predecessors: the 2.5.4 candidate-time naming successor (r1) and its receipt (the r1 receipt binds the
candidate-time guide and stays as recorded; the derivation is reused over the live guide). record: exclusive
creation of config/c2-v254-r2-public-naming-receipt.json.
"""
import c2_v254_r1_public_naming as P
import c2_v254_r1_common as S

HISTORY = {'tools/host-lisp/c2_v254_r1_public_naming.py':
               '67c030468eece04216375a00bbe4fb44e6dc98ba96ae364b32c2e32d8d27c0de',
           'config/c2-v254-r1-public-naming-receipt.json':
               '4d14e5a6ffe277da6524e09f06187321b9814bfbb2bdac093bca1f8542334c3b'}
RECEIPT = 'config/c2-v254-r2-public-naming-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.4 (ship time); no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    return P.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, P.__file__, P.P.__file__, P.P.P.__file__, P.P.P.H.__file__, P.P.P.H.H.__file__,
              'docs/user-guide.md'), claim=CLAIM)
