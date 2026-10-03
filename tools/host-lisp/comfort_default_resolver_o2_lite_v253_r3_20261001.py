"""2.5.3 r3 resolver successor: re-pin after the lib/lcc.lisp P5 fixpoint fix (fixed-arity guards moved into %lcc-unary-checked /
%lcc-binary-checked) and the matching allow_omitted_defuns declarations in the bound stdlib suites.

The measurement and all continuity controls are inherited unchanged; the
complete r2 measurement must be reproduced (asserted). The r2 tool and receipt
stay immutable.
"""
import sys

import comfort_default_resolver_o2_lite_v253_r2_20260930 as R2

Q, S = R2.Q, R2.S
RECEIPT = 'config/comfort-default-resolver-v253-r3-20261001-receipt.json'
HISTORY = {**R2.HISTORY,
           'tools/host-lisp/comfort_default_resolver_o2_lite_v253_r2_20260930.py': S.S.bind('tools/host-lisp/comfort_default_resolver_o2_lite_v253_r2_20260930.py')['sha256'],
           R2.RECEIPT: S.S.bind(R2.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['inputs']]


def derive():
    value = Q.derive()
    S.S.require(value == S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['current'],
                'resolver measurement moved (r3 is a re-pin only)')
    return value


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append('check')
    S.finish('comfort_default_resolver', derive, RECEIPT, HISTORY, (__file__, R2.__file__, *INPUTS))
