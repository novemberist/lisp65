"""2.5.3 r2 Comfort-REPL successor: re-pin after the lib/lcc.lisp P5 fixpoint fix (fixed-arity guards moved into %lcc-unary-checked /
%lcc-binary-checked) and the matching allow_omitted_defuns declarations in the bound stdlib suites.

The v253 derivation (2.5.2-era loader lane, live ship lane with the asserted nth
delta) runs unchanged and must reproduce the complete v253 measurement
(asserted); only the bound world moved. The v253 tool and receipt stay immutable.
"""
import c2_v160_comfort_repl_o2_lite_v253_20260930 as V

P, S = V.P, V.S
RECEIPT = 'config/c2-v160-comfort-repl-o2-lite-v253-receipt-r2-20261001.json'
HISTORY = {**V.HISTORY,
           'tools/host-lisp/c2_v160_comfort_repl_o2_lite_v253_20260930.py': S.S.bind('tools/host-lisp/c2_v160_comfort_repl_o2_lite_v253_20260930.py')['sha256'],
           V.RECEIPT: S.S.bind(V.RECEIPT)['sha256']}


def derive():
    value = V.derive()
    S.S.require(value == S.json.loads((S.ROOT / V.RECEIPT).read_bytes())['current'],
                'Comfort-REPL measurement moved (r2 is a re-pin only)')
    return value


if __name__ == '__main__':
    S.finish('c2-v160-comfort-repl', derive, RECEIPT, HISTORY,
             (__file__, V.__file__, P.__file__, *V.INPUTS, P.H.__file__, 'tools/host-lisp/strings_generated_r11_20260929.py'))
