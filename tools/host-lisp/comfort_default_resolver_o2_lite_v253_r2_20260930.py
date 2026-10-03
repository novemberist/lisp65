"""2.5.3 r2 resolver successor: re-pin after the D3/D5 disk candidate.

The measurement and all continuity controls are inherited unchanged from the
v253 tool; only the bound world (p0-ide-lib.json fixtures) moved. The v253 tool
and receipt stay immutable.
"""
import sys

import comfort_default_resolver_o2_lite_v253_20260930 as Q

S = Q.S
RECEIPT = 'config/comfort-default-resolver-v253-r2-20260930-receipt.json'
HISTORY = {**Q.HISTORY,
           'tools/host-lisp/comfort_default_resolver_o2_lite_v253_20260930.py': S.S.bind('tools/host-lisp/comfort_default_resolver_o2_lite_v253_20260930.py')['sha256'],
           Q.RECEIPT: S.S.bind(Q.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / Q.RECEIPT).read_bytes())['inputs']]

if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append('check')
    S.finish('comfort_default_resolver', Q.derive, RECEIPT, HISTORY, (__file__, *INPUTS))
