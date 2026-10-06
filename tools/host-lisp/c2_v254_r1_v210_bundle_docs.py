#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = the 2.5.4 candidate-time gate (r1).

Immutable predecessors: the 2.5.3 ship-time v210 successor (r3) and its receipt.
build/record: exclusive config/c2-v254-r1-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v252_r1_v210_bundle_docs as P0
import c2_v253_r2_v210_bundle_docs as P2
import c2_v253_r3_v210_bundle_docs as P
import c2_v254_r1_bundle_docs_gate as LIVE
import c2_v254_r1_common as S

HISTORY = {'tools/host-lisp/c2_v253_r3_v210_bundle_docs.py':
               'd9aec4255cb663d63ada8824291c1da7609ffe05d6cd3e9c2542f2fe93add347',
           'config/c2-v253-r3-v210-bundle-docs-receipt.json':
               '62c8f650d6b807b9c6681426717c6ce167ce40ba08f84e72f1fb88006300b834'}
RECEIPT = 'config/c2-v254-r1-v210-bundle-docs-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.4; no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    S.history(P2.HISTORY)
    S.history(P0.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v254-r1-bundle-docs.json'), claim=CLAIM)
