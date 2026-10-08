#!/usr/bin/env python3
"""2.5.5 candidate-time naming successor (r1): inherited classifications/mutations over the 2.5.5 User Guide.

Immutable predecessors: the 2.5.4 ship-time naming successor (r2) and its receipt (the r2 receipt binds the
2.5.4 guide and stays as recorded; the derivation is reused over the live guide). record: exclusive creation
of config/c2-v255-r1-public-naming-receipt.json.
"""
import c2_v254_r2_public_naming as P
import c2_v255_r1_common as S

HISTORY = {'tools/host-lisp/c2_v254_r2_public_naming.py':
               '9de32f094ff6d603534b7ab84ef69cf74e9afd7ea03431e74ed0ee45c1895947',
           'config/c2-v254-r2-public-naming-receipt.json':
               '07b7cce26daa3d488b6c46c8bb4f211e02528e385d0f868398173d904037b076'}
RECEIPT = 'config/c2-v255-r1-public-naming-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.5; no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    return P.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, P.__file__, P.P.__file__, P.P.P.__file__, P.P.P.P.__file__, P.P.P.P.H.__file__,
              P.P.P.P.H.H.__file__, 'docs/user-guide.md'), claim=CLAIM)
