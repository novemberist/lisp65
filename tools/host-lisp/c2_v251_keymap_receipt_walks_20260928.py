"""Walks successor retaining the complete predecessor derivation."""
import c2_v251_keymap_receipt as H
import walks_successor_20260928 as W
RECEIPT='config/c2-v251-keymap-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_keymap_receipt.py': '0218b0fc61780f62952fa7a6c2cd80af62dafd2de4735ca8b791f8305085dc3b', 'config/c2-v251-keymap-receipt.json': '624937af4274fafb34baf405fe1417d76558aab5e03223e51762d39ddd495aa1'}
if __name__=='__main__':
    W.finish('c2-v251-keymap',H.derive,RECEIPT,HISTORY,(__file__,H.__file__))
