#!/usr/bin/env python3
"""Keep the 2.1 historical replay and mixed-keymap control; live docs = 2.5.2 gate.

Immutable predecessors: the doc-status v210 successor and its receipt.
build/record: exclusive config/c2-v252-r1-v210-bundle-docs-receipt.json.
"""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v252_doc_status_r1_20260929_v210_bundle_docs as P
import c2_v252_r1_bundle_docs_gate as LIVE
import c2_v252_r1_common as S

HISTORY = {'tools/host-lisp/c2_v252_doc_status_r1_20260929_v210_bundle_docs.py':
               'f377c8cff38c928184b43536eb6edd0df14bf5de3f1bfb36e45af516be7c4413',
           'config/c2-v252-doc-status-r1-20260929-v210-bundle-docs-receipt.json':
               'c27ae6449022493cfe69bbe3c6ed5f29e7300f5139185033199949e9e30913bd'}
RECEIPT = 'config/c2-v252-r1-v210-bundle-docs-receipt.json'


def derive():
    S.history(P.HISTORY)
    S.history(H.HISTORY)
    H.LIVE = LIVE
    return H.derive()


if __name__ == '__main__':
    S.finish('v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, H.__file__, H.S.KEYMAP, 'docs/user-guide.md',
              'docs/generated/ide-keymap.md', 'config/c2-v252-r1-bundle-docs.json'))
