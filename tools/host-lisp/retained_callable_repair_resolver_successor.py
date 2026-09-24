"""Record the dated library-require resolver successor for the retained-callable repair.

Run inside the isolated option-a host workspace (the gate's generated
populations are private copies there): the live gate executes unchanged and
writes its fresh receipt to the writable build/check-result-successors tree;
the caller then commits that exact file as the dated successor named in the
gate.  The Put-Kit successor stays unchanged.  Only the runtime binding
(member 2, e0be22c1) and the gate's own path binding are expected to differ.
"""
import json
import sys
from pathlib import Path

import c2_require_resolver_gate as G

TARGET = G.SUCCESSOR_RECEIPT
assert TARGET.name == 'library-require-resolver-retained-callable-repair-successor-20260923.json'
assert not TARGET.exists()
G.SUCCESSOR_RECEIPT = G.ROOT/'build/check-result-successors'/TARGET.name
assert not G.SUCCESSOR_RECEIPT.exists()
code = G.main(record_successor=True)
if code == 0:
    old = json.loads((TARGET.with_name('library-require-resolver-put-kit-successor-20260922.json')).read_text())
    new = json.loads(G.SUCCESSOR_RECEIPT.read_text())
    def paths(a, b, prefix=''):
        if isinstance(a, dict) and isinstance(b, dict):
            out = []
            for k in sorted(set(a) | set(b)):
                out += paths(a.get(k), b.get(k), prefix+'.'+k if prefix else k)
            return out
        return [] if a == b else [prefix]
    print('changed paths versus Put-Kit successor:', paths(old, new))
sys.exit(code)
