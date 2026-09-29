"""Walks successor retaining the complete predecessor derivation."""
import c2_v160_hybrid_capacity_backspace_20260928 as H
import walks_successor_20260928 as W
RECEIPT='config/c2-v160-hybrid-capacity-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_hybrid_capacity_backspace_20260928.py': '39ca8585b3b490af1a310d8164dbb883d3c204a00831a091ac66dc15742a24ae', 'config/c2-v160-hybrid-capacity-receipt-backspace-20260928.json': '0134be8c5b0d5a5fdc6fceea6d3b9a7965b1606dc9a8c332d3ffe16599d14a90'}
if __name__=='__main__':
    W.finish('c2-v160-hybrid-capacity',H.derive,RECEIPT,HISTORY,(__file__,H.__file__))
