#!/usr/bin/env python3
"""Dated successor: verify released 2.4.0 inputs in their recorded Git world.

The live Make routes may evolve. Historical tools and receipts stay intact;
this read-only check neither authorizes nor runs a product reproduction.
"""
from pathlib import Path
import json
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import evidence_era as E
import c2_v240_public_native as N
import c2_v240_public_product as P

COMMIT = '068069108ac47b53d8fa2b6ff1aaa717a44c83ee'


def population():
    paths = set()
    def visit(value):
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= set(value):
                N.local(value['path'])
                paths.add(value['path'])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for path in (N.AUTHORITY, N.MANIFEST, P.INPUTS, P.RECIPE):
        name = path.relative_to(ROOT).as_posix()
        paths.add(name)
        visit(json.loads(E.era_blob(COMMIT, name)))
    return paths


def main():
    paths = population()
    live_routing = (ROOT/'mk/workbench.mk').read_bytes()
    original = N.bound
    def historical(row):
        N.require(E.host_source_commit() == COMMIT,
                  'historical producer read selected the live or wrong era')
        N.require(row['path'] in paths, 'undeclared historical input')
        return original(row)
    with patch.object(N, 'bound', historical):
        with E.host_source_world(COMMIT, paths) as reads:
            native = N.selftest()
            producer = P.public_preflight()
        captured = dict(reads)
        rejected = []
        sample = json.loads(E.era_blob(COMMIT, N.MANIFEST.relative_to(ROOT).as_posix()))['sources'][0]['source']
        for name, era in (('live-source-fallback', None), ('wrong-era', '0' * 40)):
            token = E._host_source_commit.set(era)
            try:
                try:
                    historical(sample)
                except ValueError:
                    rejected.append(name)
                else:
                    raise ValueError('historical read mutation survived: ' + name)
            finally:
                E._host_source_commit.reset(token)
        blob = E.era_blob
        def corrupt(commit, path):
            data = blob(commit, path)
            return data + b'\n/* changed historical source */\n' if path == 'mk/workbench.mk' else data
        with patch.object(E, 'era_blob', corrupt), E.host_source_world(COMMIT, paths):
            try:
                P.public_preflight()
            except ValueError as error:
                N.require('input identity drift: mk/workbench.mk' in str(error), str(error))
                rejected.append('mutated-historical-routing')
            else:
                raise ValueError('historical source mutation survived')
        def live_substitution(commit, path):
            return live_routing if path == 'mk/workbench.mk' else blob(commit, path)
        with patch.object(E, 'era_blob', live_substitution), E.host_source_world(COMMIT, paths):
            try:
                P.public_preflight()
            except ValueError as error:
                N.require('input identity drift: mk/workbench.mk' in str(error), str(error))
                rejected.append('live-routing-as-release-bytes')
            else:
                raise ValueError('live routing accepted as released bytes')
    N.require(N.bound is original, 'live producer reader not restored')
    N.require('mk/workbench.mk' in captured and len(rejected) == 4,
              'historical native source or controls not consumed')
    print(json.dumps(dict(status='PASS: HISTORICAL V240 SOURCE PREFLIGHT',
        commit=COMMIT, source_reads=len(captured),
        native_controls=native['mutations_rejected'], era_controls=rejected,
        translation_units=producer['translation_units'], compiler_invocations=0,
        claim='Historical projection and source consistency; not live product qualification or a new reproduction.'), indent=2))


if __name__ == '__main__':
    main()
