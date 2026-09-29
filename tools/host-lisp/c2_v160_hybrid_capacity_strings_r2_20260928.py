"""Revised strings successor of immutable walks evidence; host only."""
import c2_v160_hybrid_capacity_walks_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v160-hybrid-capacity-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_hybrid_capacity_walks_20260928.py': 'd1a52f6f31bed6384e79f1dda4521839e92a97af5d2eeba4bfc70ce669534b94', 'config/c2-v160-hybrid-capacity-receipt-walks-20260928.json': 'c09e196f843814b18b875e3a2877cc57949523ff3f7707ab93acb393ca301e51'}
def derive():
    with S.predecessor_world():
        inherited=H.H.derive()
    return dict(inherited=inherited,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2_v160_hybrid_capacity',derive,RECEIPT,HISTORY,(__file__,H.__file__))
