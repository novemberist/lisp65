#!/usr/bin/env python3
"""2.5.3 keymap entry point; generator, test cases and documentation unchanged.

Delegates to the immutable c2_v252_r1_keymap (which delegates to the immutable
c2_v251_r2_20260929_keymap, render seam included). 2.5.3 changed no key binding
(the IDE edits clear the mark internally; `C-x Space` is unchanged); that is
bound by c2_v253_r1_keymap_receipt.
"""
import sys
import c2_v252_r1_keymap as K
import c2_v253_r1_common as C

HISTORY = {'tools/host-lisp/c2_v252_r1_keymap.py':
               'c9b4ea372edf05101e8c9696ffbd78a4222b4110968ef204f82d44e57210d3e8',
           'tools/host-lisp/c2_v251_r2_20260929_keymap.py':
               '2e995d7bbbe7b53947af219316d0701808ac6fa8c36d13fdb13d4e90a3fded01'}


def run(argv):
    C.history(HISTORY)
    return K.run(argv)


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1:]))
