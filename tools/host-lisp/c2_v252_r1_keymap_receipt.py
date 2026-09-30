#!/usr/bin/env python3
"""2.5.2 keymap receipt: inherited O2-lite keymap derivation plus the v252 entry point.

Immutable predecessors: the O2-lite keymap-receipt successor and its receipt.
The inherited derive re-runs the generator selftest/check and requires that
only lib/stdlib-read-line.lisp moved relative to the 2.5.1 r2 receipt.
"""
import c2_v251_keymap_receipt_o2_lite_20260929 as H
import c2_v252_r1_common as S
import c2_v252_r1_keymap as K

HISTORY = {'tools/host-lisp/c2_v251_keymap_receipt_o2_lite_20260929.py':
               '538e1ef4ba5a798f515a00af1a5afa9d6ecb18bd1545ac200bec3a457f653d0b',
           'config/c2-v251-keymap-receipt-o2-lite-receipt-20260929.json':
               '95aadb8d13313320e3f569ab26c7bc085dc8265178847ec7d2f29366b21d27ed',
           'tools/host-lisp/c2_v251_r2_20260929_keymap.py':
               '2e995d7bbbe7b53947af219316d0701808ac6fa8c36d13fdb13d4e90a3fded01'}
RECEIPT = 'config/c2-v252-r1-keymap-receipt.json'


def derive():
    S.history(K.HISTORY)
    inherited = H.derive()
    old = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['current']
    S.require(inherited == old, 'O2-lite keymap receipt drift')
    return dict(inherited=inherited, entry_point=S.bind('tools/host-lisp/c2_v252_r1_keymap.py'))


if __name__ == '__main__':
    S.finish('keymap-receipt', derive, RECEIPT, HISTORY, (__file__, S.__file__, K.__file__, H.__file__))
