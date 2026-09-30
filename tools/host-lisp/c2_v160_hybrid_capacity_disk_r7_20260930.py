"""Dated r7 successor: exact predecessor replay plus current disk proof."""
import c2_v160_hybrid_capacity_strings_r2_20260928 as H
import disk_r7_consumers_20260930 as S
RECEIPT = 'config/c2-v160-hybrid-capacity-disk-r7-receipt-20260930.json'
HISTORY = {**H.HISTORY, **{'tools/host-lisp/c2_v160_hybrid_capacity_strings_r2_20260928.py': '21b73ef134dae603a27fff07cc9f9154d8f454044b5fbc19c3311fd9067ccf11', 'config/c2-v160-hybrid-capacity-receipt-strings-r2-20260928.json': '28ec6a09f0c88f76d8f5b9a76b399401898c49afe5cbb0bb381f1a46a6d7f8de'}}
def derive():
    S.S.history(HISTORY)
    with S.O.E.host_source_world(S.O.ERA, extra_paths=('config/comfort-default-plane/libraries/repl-comfort-suite.json',)), S.O.scratch():
        value = H.derive()
    old = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())
    S.require(value == old['current'], 'inherited hybrid world drift')
    return dict(inherited=value, live_o2_lite=S.O.live(), disk_r7=S.measure())
if __name__ == '__main__':
    S.finish('c2_v160_hybrid_capacity', derive, RECEIPT, H, (__file__, H.__file__))
