"""Revised strings successor of immutable walks evidence; host only."""
import c2_v16_defstruct_phase_a_walks_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v16-defstruct-phase-a-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v16_defstruct_phase_a_walks_20260928.py': 'a8b539f3fd5bbe978d36b012df5ea92ee8dcdb0d69fb46b897499740c971bb95', 'config/c2-v16-defstruct-phase-a-receipt-walks-20260928.json': '69e89b8ddc4d74f815ec63c59cbe5ee9ed59857143c22156483e850bec64eb1d'}
def derive():
    with S.predecessor_world():
        inherited=H.derive()
    return dict(inherited=inherited,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2_v16_defstruct_phase_a',derive,RECEIPT,HISTORY,(__file__,H.__file__))
