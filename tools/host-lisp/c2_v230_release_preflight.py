#!/usr/bin/env python3
"""Historical 2.3.0 source preflight, never a live build or reproduction."""
from pathlib import Path
import json
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import evidence_era as E
import c2_v230_public_native as N
import c2_v230_public_product as P

COMMIT = 'bc9dd376d66e5ced0fa4a740f2779de053b96f88'


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
            return data + b'\n/* changed historical source */\n' if path == 'src/repl.c' else data
        with patch.object(E, 'era_blob', corrupt), E.host_source_world(COMMIT, paths):
            try:
                P.public_preflight()
            except ValueError as error:
                N.require('input identity drift: src/repl.c' in str(error), str(error))
                rejected.append('mutated-historical-source')
            else:
                raise ValueError('historical source mutation survived')
    N.require(N.bound is original, 'live producer reader not restored')
    N.require('src/repl.c' in captured and len(rejected) == 3,
              'historical native source or controls not consumed')
    print(json.dumps(dict(status='PASS: HISTORICAL V230 SOURCE PREFLIGHT',
        commit=COMMIT, source_reads=len(captured),
        native_controls=native['mutations_rejected'], era_controls=rejected,
        translation_units=producer['translation_units'], compiler_invocations=0,
        claim='Historical projection and source consistency; not live product qualification or a new reproduction.'), indent=2))


if __name__ == '__main__':
    main()
