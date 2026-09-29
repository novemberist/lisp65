#!/usr/bin/env python3
"""IDE-exit successor of the v250 keymap checks; retain every old mutation."""
import sys
from unittest.mock import patch
import c2_v250_keymap_20260928 as H
import c2_ide_exit_keymap_20260928 as S
ROOT = S.ROOT
HISTORY = {'tools/host-lisp/c2_v250_keymap_20260928.py': '1e966e02be4243887e6eaf4b3820b0895cfbb0418f16b92b940c40540c93b3eb', 'tools/host-lisp/c2_ide_exit_keymap_20260928.py': 'a24ef830df417ecc2f3e360b8271b2b3bb6a572fdf8fef77b0fc938be658c484'}

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
    if sys.argv[1:] == ['selftest']:
        # The document renderer is the sole outdated assumption in this test.
        with patch.object(H, 'render_docs', S.render_docs):
            H.selftest(S.load_contract())
    raise SystemExit(S.main(sys.argv[1:]))
