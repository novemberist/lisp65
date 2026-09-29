"""Revised strings successor of immutable walks evidence; host only."""
import c2_v160_hybrid_walks_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v160-hybrid-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_hybrid_walks_20260928.py': 'ddf0a55b0cf32fb756d889cd2206a3a4b273057646f9276055473b281f409647', 'config/c2-v160-hybrid-receipt-walks-20260928.json': 'a511788847dd61b8099f1a107e90bc65ceeced1e0f882cc8f9585fc045d87ec0'}
def derive():
    with S.predecessor_world():
        inherited=H.H.derive()
    return dict(inherited=inherited,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2_v160_hybrid',derive,RECEIPT,HISTORY,(__file__,H.__file__))
