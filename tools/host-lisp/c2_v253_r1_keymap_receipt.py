#!/usr/bin/env python3
"""2.5.3 keymap receipt: the immutable 2.5.2 keymap derivation plus the v253 entry point.

Immutable predecessors: the 2.5.2 keymap-receipt successor, its receipt and the
2.5.2 keymap entry point. The inherited derive re-runs the generator
selftest/check and requires equality with the 2.5.2 receipt, i.e. that no key
binding, generated keymap document or keymap test case moved in 2.5.3.
"""
import c2_v252_r1_keymap_receipt as H
import c2_v253_r1_common as S
import c2_v253_r1_keymap as K

HISTORY = {'tools/host-lisp/c2_v252_r1_keymap_receipt.py':
               '48fc8f6d4aeca63aa22b522bcff552e05b6bce4e82424e0a5578d73d6e8dd608',
           'config/c2-v252-r1-keymap-receipt.json':
               '218286821d46b324eaef7b9bf3aec7e816f3bff139d44f41896a38bb99b64a44',
           'tools/host-lisp/c2_v252_r1_keymap.py':
               'c9b4ea372edf05101e8c9696ffbd78a4222b4110968ef204f82d44e57210d3e8'}
RECEIPT = 'config/c2-v253-r1-keymap-receipt.json'


def derive():
    S.history(K.HISTORY)
    S.history(HISTORY)
    inherited = H.derive()
    old = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['current']
    S.require(inherited == old, '2.5.2 keymap receipt drift')
    return dict(inherited=inherited, entry_point=S.bind('tools/host-lisp/c2_v253_r1_keymap.py'))


if __name__ == '__main__':
    S.finish('keymap-receipt', derive, RECEIPT, HISTORY, (__file__, S.__file__, K.__file__, H.__file__))
