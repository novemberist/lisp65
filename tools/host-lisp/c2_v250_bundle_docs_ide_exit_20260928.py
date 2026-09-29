#!/usr/bin/env python3
"""IDE-exit source docs: exact successor bytes, all inherited claim mutations.

Use the immutable predecessor for released bundles, never this source contract.
"""
import c2_v250_bundle_docs_gate as H
ROOT = H.ROOT
HISTORY = {'tools/host-lisp/c2_v250_bundle_docs_gate.py': 'f8a15f01d0e6ac49feedc7d2db1fb2cc0a5c257396e30a5f44de96440243d66e', 'config/c2-v250-bundle-docs.json': 'a7c74c28cd00dee1092d372c7b3110ca486f4481efdfc74fe2d700f8fce91bc6'}

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
    H.CONTRACT = ROOT / 'config/c2-v250-bundle-docs-receipt-ide-exit-20260928.json'
    H.check(ROOT)
