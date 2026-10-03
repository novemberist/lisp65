"""Fourth dated successor for 2.5.3 IDE source allocation: re-pin after
the lib/lcc.lisp P5 fixpoint fix (fixed-arity guards moved into %lcc-unary-checked /
%lcc-binary-checked) and the matching allow_omitted_defuns declarations in the bound stdlib suites.

The unchanged r3 derivation (dated r8 product closure, symbol budget 749 -> 751)
must reproduce the complete r3 measurement (asserted); only the bound world
moved. The r3 tool and receipt stay immutable.
"""
import hashlib

import c2_v126_editor_allocation_o2_lite_r3_20261001 as R3

S, R2, G = R3.S, R3.R2, R3.G
RECEIPT = 'config/c2-v126-editor-allocation-o2-lite-receipt-r4-20261001.json'
HISTORY = {**R3.HISTORY, **{p: hashlib.sha256((S.ROOT / p).read_bytes()).hexdigest() for p in (
    'tools/host-lisp/c2_v126_editor_allocation_o2_lite_r3_20261001.py', R3.RECEIPT)}}


def derive():
    value = R3.derive()
    S.S.require(value == S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['current'],
                'editor allocation measurement moved (r4 is a re-pin only)')
    return value


if __name__ == '__main__':
    S.finish('c2_v126_editor_allocation', derive, RECEIPT, HISTORY,
             (__file__, R3.CLOSURE, G.__file__, *R2.INPUTS, R2.__file__, R2.H.__file__, R2.P.__file__, R2.Q.__file__,
              R3.__file__))
