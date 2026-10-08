#!/usr/bin/env python3
"""Register the 2.5.5 standalone public media producer; retain the 2.5.2 census and controls and the 2.5.3/2.5.4 packers.

Successor of c2_v254_r1_media_census (immutable, pinned by hash together with its receipt), built like it on
c2_v252_r1_media_census. The 2.5.5 packer (c2_v255_r1_public_media_reproduction) writes its D81 with its own
standalone assembler, exactly like the 2.5.2, 2.5.3 and 2.5.4 ones; the inherited structural detector (call to
`MEDIA.assemble` whose result is written to a .d81) discovers it, and the registered population must equal the
observed population as before. The 2.5.2, 2.5.3 and 2.5.4 packers stay registered (their sources are retained and
exported).

selftest: derive the census and every control without reproduction outputs.
record/check: additionally require the two checked public reproductions
(c2_v255_r1_reproduction_gate), so they are red until the reproductions have run.
"""
import argparse
import copy
import hashlib
import json

import c2_v252_r1_media_census as H
import c2_v255_r1_reproduction_gate as R

G = H.G
# The two 2.5.3 packers (unshipped r1, published r2) and the published 2.5.4 packer stay in the tree (retained,
# exported) and stay registered next to the 2.5.5 packer; the registered population must equal the observed one.
ADDED = {'tools/host-lisp/c2_v253_r1_public_media_reproduction.py',
         'tools/host-lisp/c2_v253_r2_public_media_reproduction.py',
         'tools/host-lisp/c2_v254_r1_public_media_reproduction.py',
         'tools/host-lisp/c2_v255_r1_public_media_reproduction.py'}
G.REGISTERED = G.REGISTERED | ADDED
RECEIPT = G.ROOT / 'config/c2-v255-r1-media-census-receipt.json'
HISTORY = {'tools/host-lisp/c2_v252_r1_media_census.py':
               '745c991cf732057117bb119beffb9e162c291ec8cc814b9de86f5b2dfbb99512',
           'config/c2-v252-r1-media-census-receipt.json':
               'd978bdf0c0f5f7bcba389f3c93b977b448c093e5d2d6e08f6bfcae230feaf0ef',
           'tools/host-lisp/c2_v253_r2_media_census.py':
               'bb60e61dcfb40f32a2978cb634bcd1a7aaa7f3d24ee3e52a0f6bfa1a3835cd02',
           'config/c2-v253-r2-media-census-receipt.json':
               '1a1bc9d9557d34eabece333eed7156c1091cf1b661eedd21d8030c2233e66523',
           'tools/host-lisp/c2_v254_r1_media_census.py':
               'c5c3f2bee39a84937fe1ebd930278058320fd7007267fb59af4f1bdce88a8c03',
           'config/c2-v254-r1-media-census-receipt.json':
               '4efc00e512607068fa6d5c0f922c1fe500bc298956c31d675e879cdd771cf9c6'}

_prior_discover = G.discover


def discover(overrides=None):
    """The inherited discovery plus the 2.5.3, 2.5.4 and 2.5.5 standalone packers (same structural shape as 2.5.2)."""
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
    G.require(actual == HISTORY, 'census predecessor drift')
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
            raise ValueError('2.5.5 builder omission survived')
    G.require(set(v['builders']['observed']) >= ADDED, '2.5.5 builder not discovered')
    policy = R.derive_policy() if not strict else json.loads(R.POLICY.read_text())
    v['v255_successor'] = dict(history=HISTORY, mutations=rejected,
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
            G.require(RECEIPT.read_bytes() == raw, '2.5.5 media census drift')
    print('2.5.5 media census ' + a.action + ': PASS')
