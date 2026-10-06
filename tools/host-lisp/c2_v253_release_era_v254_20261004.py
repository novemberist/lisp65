#!/usr/bin/env python3
"""Verify the immutable 2.5.3 public authorities as the 2.5.3 sealing commit saw them.

2.5.4 successor of the historical v253 route: the live host sources moved with
2.5.4 (REPL-COMFORT sources and suite, lite-hot, IDE, LCC, list libraries), so the
2.5.3 preflight can no longer read live files (first drift: the Comfort re-emission
binding of config/comfort-default-plane/libraries/repl-comfort-suite.json).
Mirrors c2_v253_r1_v252_release_era: the 2.5.3 preflight and the reproduction-gate
receipt validation run inside the 2.5.3 commit's host source world; a corrupted
historical native source must be rejected. The 2.5.3 bundle-docs gate is not part
of this route (it stays live in v250-bundle-docs-check; 2.5.4 has not moved a document).
Policy modes:
  policy    exclusive creation of config/c2-v253-release-era-v254-20261004.json
  check     the era verification above
  selftest  synthetic closure controls, no Git or build work
"""
import argparse
import json
from unittest.mock import patch

import c2_v254_r1_common as C

POLICY = 'config/c2-v253-release-era-v254-20261004.json'
COMMIT = C.ERA_V253
ROOTS = ['config/c2-v253-r2-public-build-authority.json', 'config/c2-v253-r2-public-replay.json',
         'config/c2-v253-r2-public-media-reproduction.json', 'config/c2-v253-r2-reproductions.json',
         'config/c2-v253-r2-reproduction-policy.json',
         'config/c2-v253-r2-public-plane.json', 'config/c2-v253-r2-public-include-closure.json',
         'config/c2-v253-r2-public-normalization.json', 'config/c2-v253-r2-public-comfort-reemission.json']
VICTIM = ('config/c2-v253-r2-public-replay-inputs/build/card-253-product-r8/native/candidate-inputs/build/walks-r3/'
          'seed/candidate-inputs/build/backspace-r3/seed/candidate-inputs/build/ide-exit-r5/seed/native-inputs/'
          'build/comfort-default-r2/seed/inputs/build/nested-error-recovery-product-r1/wplto/'
          'generated-product-sources/c2-stream-decoder.c')
# The live files whose 2.5.4 change makes the live 2.5.3 preflight red; each must be read from the era.
MOVED = ['config/comfort-default-plane/libraries/repl-comfort-suite.json', 'lib/lite-hot.lisp',
         'lib/repl-comfort-v250.lisp']


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
    return dict(format='lisp65-v254-v253-release-era-v1', release='2.5.3', private_commit=COMMIT, roots=ROOTS,
                mutation_victim=VICTIM, moved_live_sources=MOVED,
                rule='Private sealing commit of the published 2.5.3 release; public main lacks private evidence.')


def check():
    import evidence_era as E
    import c2_v253_r2_public_product as P
    import c2_v253_r2_reproduction_gate as R
    p = json.loads((C.ROOT / POLICY).read_bytes())
    C.require(p == derive_policy(), 'era policy drift')
    commit = p['private_commit']
    paths = set(p['roots'])
    for name in p['roots']:  # one level, as the v252 reader: each root and the paths it binds
        paths |= closure(json.loads(E.era_blob(commit, name)))
    with E.host_source_world(commit, paths) as reads:
        native = P.preflight()
        policy = json.loads(R.POLICY.read_bytes())
        C.require(policy == R.derive_policy(), 'reproduction policy stale')
        R.validate(json.loads(R.RECEIPT.read_bytes()), policy)
    for name in p['moved_live_sources']:
        C.require(name in reads, 'moved live source not read from the era: ' + name)
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
    return dict(status='PASS', release='2.5.3', private_commit=commit, historical_reads=len(reads),
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
