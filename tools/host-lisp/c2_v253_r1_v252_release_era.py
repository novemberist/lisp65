#!/usr/bin/env python3
"""Verify the immutable 2.5.2 public authorities as release commit 054ab18d saw them.

2.5.3 successor of the historical v252 route: the live host sources moved with
2.5.3 (nth, IDE, LCC, M65D libraries; documents), so the 2.5.2 preflight and
bundle-docs gate can no longer read live files. Mirrors c2_v252_r1_v251_release_era:
the 2.5.2 preflight, bundle-docs gate and reproduction-gate receipt validation run inside the
private proof commit's host source world; a corrupted historical native source must be rejected.
Policy modes:
  policy    exclusive creation of config/c2-v253-r1-v252-release-era.json
  check     the era verification above
  selftest  synthetic closure controls, no Git or build work
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import c2_v253_r1_common as C

POLICY = 'config/c2-v253-r1-v252-release-era.json'
COMMIT = '054ab18d3e5f851c1d9d175de4fcd77f4bfdf57c'
ROOTS = ['config/c2-v252-r1-public-build-authority.json', 'config/c2-v252-r1-public-replay.json',
         'config/c2-v252-r1-public-media-reproduction.json', 'config/c2-v252-r1-reproductions.json',
         'config/c2-v252-r1-reproduction-policy.json', 'config/c2-v252-r1-bundle-docs.json',
         'config/c2-v252-r1-public-plane.json', 'config/c2-v252-r1-public-include-closure.json',
         'config/c2-v252-r1-public-normalization.json', 'config/c2-v252-r1-public-comfort-reemission.json']
VICTIM = ('config/c2-v252-r1-public-replay-inputs/build/o2-lite-product-r7c/native/candidate-inputs/build/walks-r3/'
          'seed/candidate-inputs/build/backspace-r3/seed/candidate-inputs/build/ide-exit-r5/seed/native-inputs/'
          'build/comfort-default-r2/seed/inputs/build/nested-error-recovery-product-r1/wplto/'
          'generated-product-sources/c2-stream-decoder.c')


def closure(value):
    paths = set()

    def visit(v):
        if isinstance(v, dict):
            if {'path', 'bytes', 'sha256'} <= v.keys() and not v['path'].startswith(('build/', 'tools/llvm-mos/')):
                name = v['path']
                prefix = str(C.ROOT) + '/'
                name = name[len(prefix):] if name.startswith(prefix) else name
                if not name.startswith('/'):
                    paths.add(name)
            for x in v.values():
                visit(x)
        elif isinstance(v, list):
            for x in v:
                visit(x)
    visit(value)
    return paths


def derive_policy():
    return dict(format='lisp65-v253-v252-release-era-v1', release='2.5.2', private_commit=COMMIT, roots=ROOTS,
                mutation_victim=VICTIM,
                rule='Private proof commit of the published 2.5.2 release; public main lacks private evidence.')


def check():
    import evidence_era as E
    import c2_v252_r1_public_product as P
    import c2_v252_r1_bundle_docs_gate as D
    import c2_v252_r1_reproduction_gate as R
    p = json.loads((C.ROOT / POLICY).read_bytes())
    C.require(p == derive_policy(), 'era policy drift')
    commit = p['private_commit']
    paths = set(p['roots']) | D.REQUIRED
    for name in p['roots']:  # one level, as the v250 reader: each root and the paths it binds
        paths |= closure(json.loads(E.era_blob(commit, name)))
    # The 2.5.2 contract pins further documents (development.md, the 2.5.1 notes) that 2.5.3 edits or moves on.
    paths |= set(json.loads(E.era_blob(commit, 'config/c2-v252-r1-bundle-docs.json'))['additional_documents'])
    with E.host_source_world(commit, paths) as reads:
        native = P.preflight()
        D.check(P.ROOT)
        R.validate(json.loads(R.RECEIPT.read_bytes()), json.loads(R.POLICY.read_bytes()))
    original = E.era_blob
    C.require(p['mutation_victim'] in paths, 'unread mutation victim')

    def corrupt(c, n):
        return original(c, n) + (b'changed' if n == p['mutation_victim'] else b'')
    with patch.object(E, 'era_blob', corrupt), E.host_source_world(commit, paths):
        try:
            P.preflight()
        except ValueError:
            pass
        else:
            raise ValueError('corrupted historical source survived')
    return dict(status='PASS', release='2.5.2', private_commit=commit, historical_reads=len(reads),
                native=native['status'] if isinstance(native, dict) and 'status' in native else 'PASS',
                mutation_rejected=True)


def selftest():
    v = {'a': [dict(path='config/a.json', bytes=1, sha256='a'), dict(path='build/old', bytes=1, sha256='b'),
               dict(path='tools/llvm-mos/bin/x', bytes=1, sha256='c')]}
    C.require(closure(v) == {'config/a.json'} and closure([v, v]) == {'config/a.json'}, 'closure control')
    C.require(derive_policy()['private_commit'] == COMMIT and len(COMMIT) == 40, 'policy commit')
    return dict(status='PASS', synthetic_tests=2)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['policy', 'check', 'selftest'])
    a = p.parse_args()
    if a.mode == 'policy':
        with (C.ROOT / POLICY).open('xb') as f:
            f.write(C.canonical(derive_policy()))
        result = dict(status='PASS', policy=POLICY)
    elif a.mode == 'selftest':
        result = selftest()
    else:
        result = check()
    print(json.dumps(result, indent=2))
