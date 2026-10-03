#!/usr/bin/env python3
"""2.5.3 ship-time naming successor (r3): inherited classifications/mutations over the ship-time User Guide.

Immutable predecessors: the r2 naming successor and its receipt (the r2 receipt binds the candidate-time guide
and stays as recorded; the derivation is reused over the live guide). record: exclusive creation of
config/c2-v253-r3-public-naming-receipt.json.
"""
import c2_v253_r2_public_naming as P
import c2_v253_r2_common as S

HISTORY = {'tools/host-lisp/c2_v253_r2_public_naming.py':
               'd013fddb058f69326a40a4e8d27c1cb238095623ee1b5916c10e7875954bd4f2',
           'config/c2-v253-r2-public-naming-receipt.json':
               '379c653c88b9cd7153b2b728d9bd02a30601efcdd34ce91d9d510b808379b11b'}
RECEIPT = 'config/c2-v253-r3-public-naming-receipt.json'


def derive():
    S.history(P.HISTORY)
    return P.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, P.__file__, P.H.__file__, P.H.H.__file__, 'docs/user-guide.md'))
