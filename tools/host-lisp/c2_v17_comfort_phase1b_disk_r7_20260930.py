"""Dated r7 successor: exact predecessor replay plus current disk proof."""
import c2_v17_comfort_phase1b_o2_lite_20260929 as H
import disk_r7_consumers_20260930 as S
RECEIPT = 'config/c2-v17-comfort-phase1b-disk-r7-receipt-20260930.json'
HISTORY = {**H.HISTORY, **{'tools/host-lisp/c2_v17_comfort_phase1b_o2_lite_20260929.py': 'f26ca8556dbcc17914507dc0f9329351eef879f62a27cb5252c150e366d194e3', 'config/c2-v17-comfort-phase1b-o2-lite-receipt-20260929.json': 'd656ce9bf6f2baaf2f07c9236deb41152f827757f23ec6d0f2af585caf8b7c6a'}}
def derive():
    S.S.history(HISTORY)
    return S.replay(H)
if __name__ == '__main__':
    S.finish('c2_v17_comfort_phase1b', derive, RECEIPT, H, (__file__, H.__file__))
