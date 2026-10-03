#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = the 2.5.3 ship-time gate (r3).

Immutable predecessors: the r2 v210 successor and its receipt.
build/record: exclusive config/c2-v253-r3-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v252_r1_v210_bundle_docs as P0
import c2_v253_r2_v210_bundle_docs as P
import c2_v253_r3_bundle_docs_gate as LIVE
import c2_v253_r2_common as S

HISTORY = {'tools/host-lisp/c2_v253_r2_v210_bundle_docs.py':
               '6859ed8469a66318f6d9f75c9193d96576e1f8a63c1acb451c955cd159b4c020',
           'config/c2-v253-r2-v210-bundle-docs-receipt.json':
               '3835cf9dedfd61b2ff68ca7ed498ebb8c65bc26fe868df07dfbd037442579172'}
RECEIPT = 'config/c2-v253-r3-v210-bundle-docs-receipt.json'


def derive():
    S.history(P.HISTORY)
    S.history(P0.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v253-r3-bundle-docs.json'))
