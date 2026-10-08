#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = the 2.5.5 ship-time gate (r2).

Immutable predecessors: the 2.5.5 candidate-time v210 successor (r1) and its receipt.
build/record: exclusive config/c2-v255-r2-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v255_r1_v210_bundle_docs as P
import c2_v255_r2_bundle_docs_gate as LIVE
import c2_v255_r1_common as S

HISTORY = {'tools/host-lisp/c2_v255_r1_v210_bundle_docs.py':
               '01e90f7114e6188a366104d3e1e93be3a0b07be5cf9e5f55da216bb4441bdc02',
           'config/c2-v255-r1-v210-bundle-docs-receipt.json':
               'e7d58f9ece44d35554e9e08e8d06189cde6e5b7cf7c39c8fcc21efe3e1a80306'}
RECEIPT = 'config/c2-v255-r2-v210-bundle-docs-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.5 (ship time); no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    S.history(P.P.HISTORY)
    S.history(P.P.P.HISTORY)
    S.history(P.P.P.P.HISTORY)
    S.history(P.P.P.P2.HISTORY)
    S.history(P.P.P.P0.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v255-r2-bundle-docs.json'), claim=CLAIM)
