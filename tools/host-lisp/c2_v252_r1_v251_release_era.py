#!/usr/bin/env python3
"""Verify the immutable 2.5.1 public authorities as release commit 0914096898884 saw them.

2.5.2 successor of the historical v251 route (the live comfort-default suite
moved with O2-lite, so the 2.5.1 preflight can no longer read live files).
Mirrors c2_v251_v250_release_era: the 2.5.1 preflight, bundle-docs gate and
reproduction gate run inside the private proof commit's host source world;
a corrupted historical native source must be rejected. Policy modes:
  policy    exclusive creation of config/c2-v252-r1-v251-release-era.json
  check     the era verification above
  selftest  synthetic closure controls, no Git or build work
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import c2_v252_r1_common as C

POLICY = 'config/c2-v252-r1-v251-release-era.json'
COMMIT = '0914096898884ada960cab965107c63848276b36'
ROOTS = ['config/c2-v251-r2-20260929-public-build-authority.json', 'config/c2-v251-r2-20260929-public-replay.json',
         'config/c2-v251-r2-20260929-public-media.json', 'config/c2-v251-r2-20260929-reproductions.json',
         'config/c2-v251-r2-20260929-bundle-docs.json']
VICTIM = 'config/comfort-default-native/sources/repl.c'


def closure(value):
    paths = set()

    def visit(v):
        if isinstance(v, dict):
            if {'path', 'bytes', 'sha256'} <= v.keys() and not v['path'].startswith('build/'):
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
    return dict(format='lisp65-v252-v251-release-era-v1', release='2.5.1', private_commit=COMMIT, roots=ROOTS,
                mutation_victim=VICTIM,
                rule='Private proof commit of the published 2.5.1 release; public main lacks private evidence.')


def check():
    import evidence_era as E
    import c2_v251_r2_20260929_public_product as P
    import c2_v251_r2_20260929_bundle_docs_gate as D
    import c2_v251_r2_20260929_reproduction_gate as R
    p = json.loads((C.ROOT / POLICY).read_bytes())
    C.require(p == derive_policy(), 'era policy drift')
    commit = p['private_commit']
    paths = set(p['roots']) | D.REQUIRED
    for name in p['roots']:  # one level, as the v250 reader: each root and the paths it binds
        paths |= closure(json.loads(E.era_blob(commit, name)))
    with E.host_source_world(commit, paths) as reads:
        native = P.preflight()
        D.check(P.ROOT)
        R.validate(json.loads(R.RECEIPT.read_bytes()))
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
    return dict(status='PASS', release='2.5.1', private_commit=commit, historical_reads=len(reads),
                native=native['status'] if isinstance(native, dict) and 'status' in native else 'PASS',
                mutation_rejected=True)


def selftest():
    v = {'a': [dict(path='config/a.json', bytes=1, sha256='a'), dict(path='build/old', bytes=1, sha256='b')]}
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
