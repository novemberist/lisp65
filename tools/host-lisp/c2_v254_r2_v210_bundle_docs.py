#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = the 2.5.4 ship-time gate (r2).

Immutable predecessors: the 2.5.4 candidate-time v210 successor (r1) and its receipt.
build/record: exclusive config/c2-v254-r2-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v254_r1_v210_bundle_docs as P
import c2_v254_r2_bundle_docs_gate as LIVE
import c2_v254_r1_common as S

HISTORY = {'tools/host-lisp/c2_v254_r1_v210_bundle_docs.py':
               '554d60316d22970296675142e4f1a55477d16600a8ad7500582b5be148153acf',
           'config/c2-v254-r1-v210-bundle-docs-receipt.json':
               'b0de323c15b14b2206529b1acc7fb9cf27f40c80b71e8885e23c07138a24b680'}
RECEIPT = 'config/c2-v254-r2-v210-bundle-docs-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.4 (ship time); no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    S.history(P.P.HISTORY)
    S.history(P.P2.HISTORY)
    S.history(P.P0.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v254-r2-bundle-docs.json'), claim=CLAIM)
