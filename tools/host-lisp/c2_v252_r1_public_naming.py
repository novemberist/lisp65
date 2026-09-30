#!/usr/bin/env python3
"""2.5.2 naming successor: inherited classifications/mutations over the 2.5.2 User Guide.

Immutable predecessors: the doc-status naming successor and its receipt.
record: exclusive creation of config/c2-v252-r1-public-naming-receipt.json.
"""
import c2_v252_doc_status_r1_20260929_public_naming as H
import c2_v252_r1_common as S

HISTORY = {'tools/host-lisp/c2_v252_doc_status_r1_20260929_public_naming.py':
               '71b8014c5015b6d8bcae9a9231776c306f3ba29b7eb851fb3aa8bbadb6e198fd',
           'config/c2-v252-doc-status-r1-20260929-public-naming-receipt.json':
               'fbf75b074f9a0331ae26940a4e6833c1c72f32e30f6395b0945fcfa57d81c38a'}
RECEIPT = 'config/c2-v252-r1-public-naming-receipt.json'


def derive():
    S.history(H.HISTORY)
    return H.derive()


if __name__ == '__main__':
    S.finish('public-naming', derive, RECEIPT, HISTORY, (__file__, S.__file__, H.__file__, 'docs/user-guide.md'))
