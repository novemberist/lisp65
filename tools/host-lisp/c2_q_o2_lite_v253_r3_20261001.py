"""2.5.3 r3 C2-Q successor: re-pin after the lib/lcc.lisp P5 fixpoint fix (fixed-arity guards moved into %lcc-unary-checked /
%lcc-binary-checked) and the matching allow_omitted_defuns declarations in the bound stdlib suites.

The measurement and every continuity control are inherited unchanged from the
v253 tool; the complete r2 measurement must be reproduced (asserted), only the
bound world moved. The r2 tool and receipt stay immutable.
"""
import c2_q_o2_lite_v253_r2_20260930 as R2

Q, S = R2.Q, R2.S
RECEIPT = 'config/c2-q-v253-r3-20261001-receipt.json'
HISTORY = {**R2.HISTORY,
           'tools/host-lisp/c2_q_o2_lite_v253_r2_20260930.py': S.S.bind('tools/host-lisp/c2_q_o2_lite_v253_r2_20260930.py')['sha256'],
           R2.RECEIPT: S.S.bind(R2.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['inputs']]


def derive():
    value = Q.derive()
    S.S.require(value == S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['current'],
                'C2-Q measurement moved (r3 is a re-pin only)')
    return value


if __name__ == '__main__':
    S.finish('c2_q', derive, RECEIPT, HISTORY, (__file__, R2.__file__, *INPUTS))
