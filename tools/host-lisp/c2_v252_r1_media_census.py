#!/usr/bin/env python3
"""Register the 2.5.2 standalone public media producer; retain the 2.5.1 census and controls.

Successor of c2_v251_r2_20260929_media_census (immutable). The 2.5.2 packer
(c2_v252_r1_public_media_reproduction) writes its D81 with its own standalone
assembler, not through the canonical builders the inherited discovery scans
for; the structural detector below adds exactly that shape (a call to
`MEDIA.assemble` whose result is written to a .d81) and nothing else, and the
registered population must equal the observed population as before.

selftest: derive the census and every control without step-4 outputs.
record/check: additionally require the two checked public reproductions
(c2_v252_r1_reproduction_gate), so they are red until step 4 has run.
"""
import argparse
import ast
import copy
import hashlib
import json

import c2_v251_r2_20260929_media_census as H
import c2_v252_r1_reproduction_gate as R

G = H.G
ADDED = {'tools/host-lisp/c2_v252_r1_public_media_reproduction.py'}
G.REGISTERED = G.REGISTERED | ADDED
RECEIPT = G.ROOT / 'config/c2-v252-r1-media-census-receipt.json'
HISTORY = {'tools/host-lisp/c2_v251_r2_20260929_media_census.py':
               '37ebf11978f987877425e82d9c9e85fde5bf5a13444cc97bff26a60292128c23',
           'config/c2-v251-r2-20260929-media-census-receipt.json':
               'e0060107536d5a7f30f7a28baf81260fb8b6557e94721c613880ec32483334db'}
_discover = G.discover


def standalone_assembler(source):
    """Structural shape: `<x>.write_bytes(MEDIA.assemble(...))` on a .d81 path."""
    tree = ast.parse(source)
    calls = [ast.unparse(c.func) for c in ast.walk(tree) if isinstance(c, ast.Call)]
    d81 = any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.endswith('.d81')
              for n in ast.walk(tree))
    return 'MEDIA.assemble' in calls and d81


def discover(overrides=None):
    found = _discover(overrides)
    for path in sorted(ADDED | set(overrides or {})):
        source = (overrides or {}).get(path)
        if source is None:
            file = G.ROOT / path
            G.require(file.is_file() and not file.is_symlink(), 'media-builder candidate absent: ' + path)
            source = file.read_text(encoding='utf-8')
        if path.startswith('tools/host-lisp/') and path.endswith('.py') and standalone_assembler(source):
            found[path] = sorted(set(found.get(path, [])) | {'standalone-d81-assembler'})
    return dict(sorted(found.items()))


G.discover = discover


def derive(strict=True):
    actual = {p: hashlib.sha256((G.ROOT / p).read_bytes()).hexdigest() for p in HISTORY}
    G.require(actual == HISTORY, 'v251 census predecessor drift')
    v = H.derive()
    rejected = []
    for name in sorted(ADDED):
        trial = copy.deepcopy(v)
        trial['builders']['observed'].pop(name)
        try:
            G.audit(trial)
        except G.EnumerationError:
            rejected.append(name)
        else:
            raise ValueError('2.5.2 builder omission survived')
    synthetic = {'tools/host-lisp/c2_unregistered_standalone_builder.py':
                 "def build(p):\n    p.write_bytes(MEDIA.assemble([]))\n    return 'x.d81'\n"}
    try:
        G.require(set(discover(synthetic)) == G.REGISTERED, 'unregistered standalone builder rejected')
    except G.EnumerationError:
        rejected.append('standalone-builder-outside-enumeration')
    else:
        raise ValueError('unregistered standalone builder survived')
    policy = R.derive_policy() if not strict else json.loads(R.POLICY.read_text())
    v['v252_successor'] = dict(history=HISTORY, mutations=rejected,
                               reproductions=(R.validate(json.loads(R.RECEIPT.read_text()), policy) if strict
                                              else 'not evaluated (selftest)'))
    return v


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['record', 'selftest', 'check'])
    a = p.parse_args()
    if a.action == 'selftest':
        derive(strict=False)
    else:
        raw = G.canonical(derive())
        if a.action == 'record':
            with RECEIPT.open('xb') as f:
                f.write(raw)
        else:
            G.require(RECEIPT.read_bytes() == raw, '2.5.2 media census drift')
    print('2.5.2 media census ' + a.action + ': PASS')
