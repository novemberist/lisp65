#!/usr/bin/env python3
"""Verify the untouched IDE-exit predecessors in the published 2.5.0 era.

Only explicit source reads are redirected. No build, link or device operation.
"""
import json
from unittest.mock import patch
import evidence_era as E
import c2_v250_keymap_20260928 as K
import v11_wave3_fail_fast as F
import c2_v250_public_naming_20260928 as N
import c2_v250_bundle_docs_gate as D

COMMIT = '9665f97f7a37951364303ea13db91c92bffa9e7a'
PATHS = {
    'config/v11-l-lite-keymap.json',
    'config/v11-wave3-fail-fast.json',
    'lib/tests/ide-keymap-eval-cases.generated.json',
    'tests/bytecode/dialect-v2/ide/l-lite-hardware-cases.generated.json',
    'config/c2-v250-bundle-docs.json',
    'config/c2-v250-public-naming-receipt-20260928.json',
} | D.REQUIRED


def main():
    with E.host_source_world(COMMIT, PATHS) as reads:
        value = K.load_contract()
        K.selftest(value)
        K.check_outputs(value)
        F.selftest()
        F.check()
        expected = (json.dumps(N.derive(), indent=2, sort_keys=True) + '\n').encode()
        N.H.require(N.RECEIPT.read_bytes() == expected, 'historical naming receipt drift')
        D.check(D.ROOT)
    captured = dict(reads)
    original = E.era_blob
    for path in ('docs/user-guide.md', 'docs/generated/ide-keymap.md'):
        def corrupt(commit, name):
            raw = original(commit, name)
            return raw + b'\nchanged historical document\n' if name == path else raw
        with patch.object(E, 'era_blob', corrupt), E.host_source_world(COMMIT, PATHS):
            try:
                D.check(D.ROOT)
            except ValueError as error:
                if 'document drift: ' + path not in str(error):
                    raise
            else:
                raise ValueError('historical document mutation survived')
    print(json.dumps(dict(status='PASS', commit=COMMIT, historical_checks=7,
                          source_reads=captured, era_mutations=2), indent=2))


if __name__ == '__main__':
    main()
