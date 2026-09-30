"""Dated r7 successor: exact predecessor replay plus current disk proof."""
import c2_v160_hybrid_strings_r2_20260928 as H
import disk_r7_consumers_20260930 as S
RECEIPT = 'config/c2-v160-hybrid-disk-r7-receipt-20260930.json'
HISTORY = {**H.HISTORY, **{'tools/host-lisp/c2_v160_hybrid_strings_r2_20260928.py': '803e6be4a0aa25623d06181a02e7f468fddcbfeee9e77a222c07268dff7b307f', 'config/c2-v160-hybrid-receipt-strings-r2-20260928.json': 'fea555b51f83daf0d778639b6447bbaae1cb811bcb2dbe92441dc65c18b78932'}}
def derive():
    S.S.history(HISTORY)
    with S.O.E.host_source_world(S.O.ERA, extra_paths=('config/comfort-default-plane/libraries/repl-comfort-suite.json',)), S.O.scratch():
        value = H.derive()
    old = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())
    S.require(value == old['current'], 'inherited hybrid world drift')
    return dict(inherited=value, live_o2_lite=S.O.live(), disk_r7=S.measure())
if __name__ == '__main__':
    S.finish('c2_v160_hybrid', derive, RECEIPT, H, (__file__, H.__file__))
