#!/usr/bin/env python3
"""IDE-exit naming successor; immutable v250 receipt and inherited mutations."""
import c2_v250_public_naming_20260928 as H
ROOT = H.H.ROOT
HISTORY = {'tools/host-lisp/c2_v250_public_naming_20260928.py': '1b49b420df54fac6a3637935bffeead280c0135eb5e879b608a87579aa11da3f', 'config/c2-v250-public-naming-receipt-20260928.json': '482c9b511c62a489f709f73751735295a2b5ca9ad691a3d32199107d26eb7031'}

def history_check():
    import hashlib
    rows = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in HISTORY}
    def validate(rows):
        if rows != HISTORY:
            raise ValueError('IDE exit predecessor drift')
    validate(rows)
    for path in rows:
        trial = dict(rows)
        trial[path] = '0' * 64
        try:
            validate(trial)
        except ValueError:
            pass
        else:
            raise ValueError('predecessor mutation survived')

if __name__ == '__main__':
    history_check()
    H.HISTORY = dict(H.HISTORY, **HISTORY)
    H.RECEIPT = ROOT / 'config/c2-v251-r2-20260929-public-naming-receipt.json'
    H.main()
