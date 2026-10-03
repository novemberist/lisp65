#!/usr/bin/env python3
"""2.5.3 successor route of c2_top_level_macro_redispatch.py (unchanged, historical).

The tracked Link-95 host receipt binds the live LCC profile source
(authorities/current_sources/profile).  The reviewer LCC arity fix changes
lib/dialect-v2/lcc-profile.lisp; the live actual-LCC semantics the gate executes
are unchanged.  This successor writes/checks a dated receipt and requires that it
differs from the sealed Link-95 receipt ONLY in that profile binding (plus the
rebuilt actual-LCC binary/driver hashes, which the original already excludes from
its live predicate).
"""
import json
import sys

import c2_top_level_macro_redispatch as M

ORIGINAL = M.RECEIPT
SUCCESSOR = M.ROOT / ('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
                      'c2.3-link95-top-level-macro-publication-receipt-v253-20261001.json')
ADMITTED = ('/authorities/current_sources/profile/', '/authorities/actual_lcc_binary/', '/authorities/driver/')


def drift(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                yield from drift(a.get(key), b.get(key), f'{path}/{key}')
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                yield from drift(x, y, f'{path}[{i}]')
    else:
        yield path + '/'


def only_profile_drift():
    paths = list(drift(json.loads(ORIGINAL.read_text()), json.loads(SUCCESSOR.read_text())))
    bad = [p for p in paths if not p.startswith(ADMITTED)]
    M.require(not bad, 'successor receipt drifts beyond the profile binding: ' + repr(bad))
    M.require(any(p.startswith(ADMITTED[0]) for p in paths), 'successor receipt does not carry the new profile binding')
    return paths


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode not in ('write', 'check'):
        return M.main()                       # selftest: unchanged, against the sealed original
    try:
        value = M.load(M.CONTRACT)
        M.validate_contract(value)
        receipt = M.build_receipt(value)      # reads the SEALED original for historical provenance
        if mode == 'write':
            M.require(not SUCCESSOR.exists(), 'successor receipt is write-once')
            SUCCESSOR.write_bytes(M.canonical(receipt))
        else:
            M.require(SUCCESSOR.is_file(), f'receipt absent: {SUCCESSOR}')
            sealed = M.load(SUCCESSOR)
            M.require(SUCCESSOR.read_bytes() == M.canonical(M.sealed_receipt_projection(receipt, sealed)),
                      'tracked Link 95 v253 host receipt drift')
        paths = only_profile_drift()
    except M.RedispatchError as exc:
        print(f'c2-top-level-macro-redispatch-v253: FAIL: {exc}')
        return 1
    print(f'c2-top-level-macro-redispatch-v253: {mode.upper()} PASS admitted-drift={paths}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
