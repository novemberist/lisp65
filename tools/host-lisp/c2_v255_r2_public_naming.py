#!/usr/bin/env python3
"""2.5.5 ship-time naming successor (r2): inherited classifications/mutations over the ship-time User Guide.

Immutable predecessors: the 2.5.5 candidate-time naming successor (r1) and its receipt (the r1 receipt binds the
candidate-time guide and stays as recorded; the derivation is reused over the live guide). record: exclusive
creation of config/c2-v255-r2-public-naming-receipt.json.
"""
import c2_v255_r1_public_naming as P
import c2_v255_r1_common as S

HISTORY = {'tools/host-lisp/c2_v255_r1_public_naming.py':
               '1ad00d9c79a44af2d407ae7110ea578a338e60648b7916f3a8273eb5686fb23a',
           'config/c2-v255-r1-public-naming-receipt.json':
               '078b61ad6688af33c2ac173be022cf6e9493b1f7b3b9e8a3517b50ecac64b351'}
RECEIPT = 'config/c2-v255-r2-public-naming-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.5 (ship time); no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    return P.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, P.__file__, P.P.__file__, P.P.P.__file__, P.P.P.P.__file__, P.P.P.P.P.__file__,
              P.P.P.P.P.H.__file__, P.P.P.P.P.H.H.__file__, 'docs/user-guide.md'), claim=CLAIM)
