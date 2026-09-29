"""Revised strings successor of immutable walks evidence; host only."""
import c2_v251_keymap_receipt_walks_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v251-keymap-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_keymap_receipt_walks_20260928.py': '6adcf0bc7587b63158c4cacdbb1a5bfee2efc219373689838162641ed5629606', 'config/c2-v251-keymap-receipt-walks-20260928.json': '7e0861da286387092eb9a124444abb4711029271f9271cce68e93eb8daa9dc6c'}
def derive():
    with S.predecessor_world():
        inherited=H.H.derive()
    return dict(inherited=inherited,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2_v251_keymap_receipt',derive,RECEIPT,HISTORY,(__file__,H.__file__))
