"""2.5.3 r2 C2-Q successor: re-pin after the D3/D5 disk candidate.

The v253 receipt bound lib/ide and p0-ide-lib.json before the D3 lossless-load
fixtures. The measurement and every continuity control are inherited unchanged
from the v253 tool; only the bound world moved, so a second dated receipt pins
it. The v253 tool and receipt stay immutable.
"""
import c2_q_o2_lite_v253_20260930 as Q

S = Q.S
RECEIPT = 'config/c2-q-v253-r2-20260930-receipt.json'
HISTORY = {**Q.HISTORY,
           'tools/host-lisp/c2_q_o2_lite_v253_20260930.py': S.S.bind('tools/host-lisp/c2_q_o2_lite_v253_20260930.py')['sha256'],
           Q.RECEIPT: S.S.bind(Q.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / Q.RECEIPT).read_bytes())['inputs']]

if __name__ == '__main__':
    S.finish('c2_q', Q.derive, RECEIPT, HISTORY, (__file__, *INPUTS))
