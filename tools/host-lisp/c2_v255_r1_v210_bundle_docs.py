#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = the 2.5.5 candidate-time gate (r1).

Immutable predecessors: the 2.5.4 ship-time v210 successor (r2) and its receipt.
build/record: exclusive config/c2-v255-r1-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v254_r2_v210_bundle_docs as P
import c2_v255_r1_bundle_docs_gate as LIVE
import c2_v255_r1_common as S

HISTORY = {'tools/host-lisp/c2_v254_r2_v210_bundle_docs.py':
               'c60243e8808cb88ca003d5d3b4e6e4e61531b3d698a826373a3574464ae7dada',
           'config/c2-v254-r2-v210-bundle-docs-receipt.json':
               '5e62d493af09cc8545af1cb50dfb3f68c6266f6153797e35da86cb12d7bac79e'}
RECEIPT = 'config/c2-v255-r1-v210-bundle-docs-receipt.json'
CLAIM = 'Host documentation/source successor for 2.5.5; no product, emulator or device claim'


def derive():
    S.history(P.HISTORY)
    S.history(P.P.HISTORY)
    S.history(P.P.P.HISTORY)
    S.history(P.P.P2.HISTORY)
    S.history(P.P.P0.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v255-r1-bundle-docs.json'), claim=CLAIM)
