#!/usr/bin/env python3
"""2.5.2 keymap entry point; generator, test cases and documentation unchanged.

Delegates to the immutable c2_v251_r2_20260929_keymap (render seam included).
O2-lite changed only lib/stdlib-read-line.lisp, which adds no key binding;
that drift is bound by c2_v252_r1_keymap_receipt.
"""
import sys
from unittest.mock import patch
import c2_v251_r2_20260929_keymap as K
import c2_v252_r1_common as C

HISTORY = {'tools/host-lisp/c2_v251_r2_20260929_keymap.py':
               '2e995d7bbbe7b53947af219316d0701808ac6fa8c36d13fdb13d4e90a3fded01'}


def run(argv):
    C.history(HISTORY)
    K.H.history_check()
    with patch.object(K.S, 'render_docs', K.render_docs), patch.object(K.H.H, 'render_docs', K.render_docs):
        if argv == ['selftest']:
            K.H.H.selftest(K.S.load_contract())
        return K.S.main(argv)


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1:]))
