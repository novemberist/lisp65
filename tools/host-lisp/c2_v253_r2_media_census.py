#!/usr/bin/env python3
"""Register the 2.5.3 standalone public media producers (r1 retained, r2 for Final r8); retain the 2.5.2 census and controls.

Successor of c2_v252_r1_media_census (immutable). The 2.5.3 packer
(c2_v253_r2_public_media_reproduction) writes its D81 with its own standalone
assembler, exactly like the 2.5.2 one; the inherited structural detector
(call to `MEDIA.assemble` whose result is written to a .d81) discovers it, and
the registered population must equal the observed population as before. The
2.5.2 packer stays registered (its source is retained and exported).

selftest: derive the census and every control without step-4 outputs.
record/check: additionally require the two checked public reproductions
(c2_v253_r2_reproduction_gate), so they are red until step 4 has run.
"""
import argparse
import copy
import hashlib
import json

import c2_v252_r1_media_census as H
import c2_v253_r2_reproduction_gate as R

G = H.G
# The unshipped r1 packer stays in the tree (retained, exported) and is discovered structurally, so it stays
# registered next to the r2 packer; the registered population must equal the observed one.
ADDED = {'tools/host-lisp/c2_v253_r1_public_media_reproduction.py',
         'tools/host-lisp/c2_v253_r2_public_media_reproduction.py'}
G.REGISTERED = G.REGISTERED | ADDED
RECEIPT = G.ROOT / 'config/c2-v253-r2-media-census-receipt.json'
HISTORY = {'tools/host-lisp/c2_v252_r1_media_census.py':
               '745c991cf732057117bb119beffb9e162c291ec8cc814b9de86f5b2dfbb99512',
           'config/c2-v252-r1-media-census-receipt.json':
               'd978bdf0c0f5f7bcba389f3c93b977b448c093e5d2d6e08f6bfcae230feaf0ef'}

_prior_discover = G.discover


def discover(overrides=None):
    """The inherited discovery plus the 2.5.3 standalone packer (same structural shape as 2.5.2)."""
    found = _prior_discover(overrides)
    for path in sorted(ADDED):
        source = (overrides or {}).get(path)
        if source is None:
            file = G.ROOT / path
            G.require(file.is_file() and not file.is_symlink(), 'media-builder candidate absent: ' + path)
            source = file.read_text(encoding='utf-8')
        if H.standalone_assembler(source):
            found[path] = sorted(set(found.get(path, [])) | {'standalone-d81-assembler'})
    return dict(sorted(found.items()))


G.discover = discover


def derive(strict=True):
    actual = {p: hashlib.sha256((G.ROOT / p).read_bytes()).hexdigest() for p in HISTORY}
    G.require(actual == HISTORY, 'v252 census predecessor drift')
    v = H.derive(strict=strict)
    rejected = []
    for name in sorted(ADDED):
        trial = copy.deepcopy(v)
        trial['builders']['observed'].pop(name)
        try:
            G.audit(trial)
        except G.EnumerationError:
            rejected.append(name)
        else:
            raise ValueError('2.5.3 builder omission survived')
    G.require(set(v['builders']['observed']) >= ADDED, '2.5.3 builder not discovered')
    policy = R.derive_policy() if not strict else json.loads(R.POLICY.read_text())
    v['v253_successor'] = dict(history=HISTORY, mutations=rejected,
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
            G.require(RECEIPT.read_bytes() == raw, '2.5.3 media census drift')
    print('2.5.3 media census ' + a.action + ': PASS')
