#!/usr/bin/env python3
"""2.5.4 successor route of c2_top_level_macro_redispatch (v253 route unchanged, historical).

The tracked Link-95 host receipt binds the live LCC profile source
(authorities/current_sources/profile).  2.5.4 changes
lib/dialect-v2/lcc-profile.lisp again (C2-A: logand/logior/logxor/ash arity
guard); the live actual-LCC semantics the gate executes are unchanged.  This
successor writes/checks its own dated receipt with the inherited v253 logic:
against the sealed Link-95 receipt it may differ ONLY in that profile binding
and the rebuilt actual-LCC binary/driver hashes.  Additionally, against the
v253 successor receipt only the profile binding may move.
"""
import json
import sys

import c2_top_level_macro_redispatch_v253_20261001 as V

M = V.M
PREDECESSOR = V.SUCCESSOR
V.SUCCESSOR = M.ROOT / ('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
                        'c2.3-link95-top-level-macro-publication-receipt-v254-20261003.json')


def predecessor_delta():
    paths = list(V.drift(json.loads(PREDECESSOR.read_text()), json.loads(V.SUCCESSOR.read_text())))
    M.require(paths and all(p.startswith(V.ADMITTED[0]) for p in paths),
              'v254 receipt moves beyond the profile binding against v253: ' + repr(paths))
    return paths


if __name__ == '__main__':
    code = V.main()
    if code == 0 and sys.argv[1:2] == ['check']:
        try:
            print('c2-top-level-macro-redispatch-v254: v253 delta=' + repr(predecessor_delta()))
        except M.RedispatchError as exc:
            print(f'c2-top-level-macro-redispatch-v254: FAIL: {exc}')
            code = 1
    raise SystemExit(code)
