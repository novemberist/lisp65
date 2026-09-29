"""Next Card-5 successor, chained on the sealed editor-walks Card-5."""
import copy
from unittest.mock import patch
import c2_v251_card5_walks_20260928 as H
import c2_v17_comfort_phase1b_walks_20260928 as PHASE
import walks_successor_20260928 as W
RECEIPT='config/c2-v251-card5-phase1b-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_card5_walks_20260928.py': 'b73cbba34bdb1206e7e0f7c26133f458cde7fc2da432aa27f68ca8abcac12e36', 'config/c2-v251-card5-receipt-walks-20260928.json': 'ab8aa80c02ff97fef030c5d5de53e7f92387dc2aa0547ca50912265b26a05243'}
H.H.K.ROUTES=dict(H.H.K.ROUTES,**{
    'block-26-build-integrity-check':'c2_v251_card5_phase1b_walks_20260928.py'})
H.H.V.CHECK_HOST_ROUTES=copy.deepcopy(H.H.V.CHECK_HOST_ROUTES)
for targets in H.H.V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        targets[target]=[c.replace('c2_v251_card5_walks_20260928.py',
            'c2_v251_card5_phase1b_walks_20260928.py') for c in commands]
H.H.V.CHECK_HOST_ROUTES['mk/gates.mk']['c2-v17-comfort-phase1b-qualification-check']=[
    'c2_v17_comfort_phase1b_walks_20260928.py qualification-check']

def derive():
    return dict(inherited=H.derive(),qualification_receipt=W.S.bind(PHASE.RECEIPT))

if __name__=='__main__':
    with patch.object(W,'ERA','f9aa371b'):
        W.finish('c2-v251-card5-phase1b',derive,RECEIPT,HISTORY,
                 (__file__,H.__file__,PHASE.__file__,PHASE.RECEIPT,
                  'tools/host-lisp/editor_semantics_walks_20260928.py',
                  'mk/gates.mk'))
