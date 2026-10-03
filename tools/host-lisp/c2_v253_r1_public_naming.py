#!/usr/bin/env python3
"""2.5.3 naming successor: inherited classifications/mutations over the 2.5.3 User Guide.

Immutable predecessors: the 2.5.2 naming successor and its receipt (the 2.5.2
receipt binds the 2.5.2 guide and stays as recorded; the derivation is reused
over the live guide). record: exclusive creation of
config/c2-v253-r1-public-naming-receipt.json.
"""
import c2_v252_r1_public_naming as H
import c2_v253_r1_common as S

HISTORY = {'tools/host-lisp/c2_v252_r1_public_naming.py':
               'a649be48df09b7590aaa2c6a9cca7dcf71075768a3ca514382da4ce1566f4e74',
           'config/c2-v252-r1-public-naming-receipt.json':
               '353742543e856b003da1bade2fc972777ebddb491e850e8e73fc932a45ff7fc2'}
RECEIPT = 'config/c2-v253-r1-public-naming-receipt.json'


def derive():
    return H.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY, (__file__, S.__file__, H.__file__, H.H.__file__, 'docs/user-guide.md'))
