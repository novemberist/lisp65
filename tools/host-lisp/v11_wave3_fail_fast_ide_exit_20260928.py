#!/usr/bin/env python3
"""IDE-exit static matrix successor; no hardware execution or acceptance."""
import copy
import sys
from unittest.mock import patch
import v11_wave3_fail_fast as H
import c2_ide_exit_keymap_20260928 as S
ROOT = H.ROOT
HISTORY = {'tools/host-lisp/v11_wave3_fail_fast.py': 'a815e2c20e2d8b0fe23d7b2b1a72e3d4bb01cb67e03bcbfe1a30dd74af11acbc', 'tools/host-lisp/v11_l_lite_keymap.py': '9d79cbb524bf43c5e1755b9790e3bd9310ce7309bf5416beeb8bdab33f53a115', 'tools/host-lisp/c2_ide_exit_keymap_20260928.py': 'a24ef830df417ecc2f3e360b8271b2b3bb6a572fdf8fef77b0fc938be658c484'}

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

# Extend only the new-case inventory; retain the predecessor's ordering and
# fidelity validator, including its complete six-mutation selftest.
original_inputs = H.inputs

def inputs():
    args = list(original_inputs())
    args[0] = copy.deepcopy(args[0])
    args[0]['new_cases_first'].append('binding-cx-exit-q')
    return tuple(args)

HISTORY['config/v11-wave3-fail-fast.json'] = '46ec5e4033f49cf7b78799e11d233cf2ea0f9d08b537f55034fde9d99c651ed3'

if __name__ == '__main__':
    history_check()
    with patch.object(H, 'Keymap', S), patch.object(H, 'inputs', inputs):
        S.validate(S.load_contract())
        if sys.argv[1:] == ['selftest']:
            args = list(H.inputs())
            changed = copy.deepcopy(args[1])
            row = next(r for r in changed['cases'] if r['id'] == 'binding-cx-exit')
            row['fidelity'] = 'emulator-dry-plus-hardware'
            try:
                H.validate(args[0], changed, *args[2:])
            except H.FailFastError:
                pass
            else:
                raise H.FailFastError('physical Ctrl-C promotion survived')
        raise SystemExit(H.main(sys.argv[1:]))
