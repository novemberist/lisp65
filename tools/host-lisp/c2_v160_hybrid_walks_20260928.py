"""Walks successor retaining the complete predecessor derivation."""
import c2_v160_hybrid_backspace_20260928 as H
import walks_successor_20260928 as W
RECEIPT='config/c2-v160-hybrid-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_hybrid_backspace_20260928.py': 'be607ed25ace1f787d72241af5df98621208963681fe41998d11e01fad113dc3', 'config/c2-v160-hybrid-receipt-backspace-20260928.json': '0d2e7c15d7d9f0f27713630ead619a54a2763061b18f140c9c1a756ae636f017'}
if __name__=='__main__':
    W.finish('c2-v160-hybrid',H.derive,RECEIPT,HISTORY,(__file__,H.__file__))
