#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = 2.5.3 gate.

Immutable predecessors: the 2.5.2 v210 successor and its receipt.
build/record: exclusive config/c2-v253-r2-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v252_r1_v210_bundle_docs as P
import c2_v253_r2_bundle_docs_gate as LIVE
import c2_v253_r2_common as S

HISTORY = {'tools/host-lisp/c2_v252_r1_v210_bundle_docs.py':
               '3d61aa43abfc3c35f3e14de7a5772c7824e1e2b85d4afc906ef8df50eba3f268',
           'config/c2-v252-r1-v210-bundle-docs-receipt.json':
               '9baedc63a57070800d0588b81b1a43fe32a4c33c49bdd913c32af89d806cf584'}
RECEIPT = 'config/c2-v253-r2-v210-bundle-docs-receipt.json'


def derive():
    S.history(P.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v253-r2-bundle-docs.json'))
