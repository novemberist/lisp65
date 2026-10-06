#!/usr/bin/env python3
"""2.5.4 LCC nesting ladder r2: the 20261003 gate without a self-written bound file.

Successor of lcc_nesting_ladder_v254_20261003 (immutable tool and receipt).  The
20261003 receipt bound build/lcc-nesting-ladder-v254-20261003-live/resident/suite.json,
a file its own check rewrites on every run; the sealed runner mounts every path
named in a tracked JSON binding row read-only, so the sealed run died with
EROFS.  Same ladder, same limits, same derivation (the v253 module and the
20261003 module are imported and reused); what changes is the I/O contract:

  scratch    Everything build/check/selftest writes (resident projection, control
             and candidate emissions of the inherited v253 module) goes into one
             fresh tempfile.mkdtemp(dir=build/, prefix=lcc-nesting-ladder-v254-)
             directory, removed at the end also on failure.  Set
             LISP65_LADDER_KEEP_SCRATCH=1 to keep it for debugging.
  receipt    Binds only stable inputs: the frozen 2.5.3 product resident suite the
             projection starts from (build/card-253-preflight-r7/projection/
             stdlib-p0/suite.json, written once by the 2.5.3 card preflight r7 run
             of 2026-10-01 and by no gate), the tracked domain-tier1, compiler
             sources, images, and the era commit.  The projected resident domain
             is recorded as content hashes only (domain text; suite JSON with the
             scratch and repository paths replaced by fixed tokens).
  guard      The receipt must not bind any path under a lcc-nesting-ladder-v254-*
             directory of build/; selftest proves the guard refuses exactly the
             20261003 defect (the committed 20261003 receipt is the control).

The ladder content (35 shapes, candidate >= 2.5.2 and >= 2.5.3, r7 negative control,
emission control) must equal the 20261003 receipt except for the input-binding
fields; the tool re-checks that on every run.

Usage: lcc_nesting_ladder_v254_r2_20261004.py build | check | selftest
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import lcc_nesting_ladder_v254_20261003 as P
import lcc_nesting_ladder_v253_20261002 as L
import c2_v254_r1_common as C

ROOT = L.ROOT
PREDECESSOR_V254 = 'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v254-20261003.json'
HISTORY = dict(P.HISTORY)
HISTORY.update({'tools/host-lisp/lcc_nesting_ladder_v254_20261003.py':
                    'ad3d379403886b961479dc7a7674333c88ec3a9cbdb945864a826fbd3b0a1796',
                PREDECESSOR_V254:
                    '07d3f13832c8ef988b2611d7d410b745191d2e5fd2664718fa9896c0a1892902'})
FORMAT = 'lisp65-lcc-nesting-ladder-v254-r2-20261004'
RECEIPT_REL = 'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v254-r2-20261004.json'
RECEIPT = ROOT / RECEIPT_REL
BASE_RESIDENT = P.BASE_RESIDENT       # build/card-253-preflight-r7/projection/stdlib-p0/suite.json
DOMAIN = P.DOMAIN
SEALED = P.SEALED
SCRATCH_PREFIX = 'lcc-nesting-ladder-v254-'
KEEP_ENV = 'LISP65_LADDER_KEEP_SCRATCH'
SCRATCH_TOKEN = '@LADDER-SCRATCH@'
ROOT_TOKEN = '@ROOT@'
# receipt fields that may differ from the 20261003 receipt (input binding only)
INPUT_FIELDS = ('format', 'inputs', 'resident_domain_projection')


def sha(raw):
    return L.sha(raw)


def binding_rows(value):
    """Same row definition as tools/host-lisp/sealed_check_run.py."""
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and 'sha256' in value:
            yield value
        for child in value.values():
            yield from binding_rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from binding_rows(child)


def guard(value):
    """Refuse a receipt that binds a path of this gate's scratch/output area (the 20261003 defect),
    or any build/ path other than the single frozen 2.5.3 resident suite."""
    for row in binding_rows(value):
        path = os.path.normpath(row['path'])
        top = path.split(os.sep)
        if top[0] == 'build':
            L.require(len(top) > 1 and not top[1].startswith(SCRATCH_PREFIX),
                      'receipt binds a path under the gate scratch/output area: ' + row['path'])
            L.require(path == BASE_RESIDENT,
                      'receipt binds an unexpected build/ path: ' + row['path'])


def normalise(text, scratch):
    return text.replace(str(scratch), SCRATCH_TOKEN).replace(str(ROOT), ROOT_TOKEN)


def new_scratch():
    return Path(tempfile.mkdtemp(dir=ROOT / 'build', prefix=SCRATCH_PREFIX))


def resident_v254(scratch):
    """Project the live domain-tier1 onto the frozen 2.5.3 resident suite, inside `scratch`."""
    L.require((ROOT / BASE_RESIDENT).is_file(),
              'missing 2.5.3 product resident suite (local build tree): ' + BASE_RESIDENT)
    suite = json.loads((ROOT / BASE_RESIDENT).read_text())
    hits = [i for i, s in enumerate(suite['sources']) if os.path.basename(s) == SEALED]
    L.require(len(hits) == 1, 'resident suite sealed domain seam')
    sealed = open(suite['sources'][hits[0]]).read()
    era = L.era_text(C.ERA_V253, DOMAIN)
    text, mode = L.project_text(sealed, era, (ROOT / DOMAIN).read_text(), DOMAIN)
    L.require(text != sealed, 'live domain projection did not move the sealed resident domain')
    out = scratch / 'resident'
    (out / 'sources').mkdir(parents=True, exist_ok=True)
    (out / 'sources' / SEALED).write_text(text)
    suite['sources'][hits[0]] = str(out / 'sources' / SEALED)
    raw = json.dumps(suite, indent=2) + '\n'
    (out / 'suite.json').write_text(raw)
    L.require(str(out / 'suite.json').startswith(str(ROOT / 'build' / SCRATCH_PREFIX)), 'scratch placement')
    projection = dict(base_suite=C.bind(BASE_RESIDENT), domain=C.bind(DOMAIN), era=C.ERA_V253, mode=mode,
                      era_domain_sha256=sha(era.encode()),
                      projected_domain_sha256=sha(text.encode()), projected_domain_bytes=len(text.encode()),
                      projected_suite_sha256=sha(normalise(raw, scratch).encode()),
                      projected_suite_normalisation=[str(SCRATCH_TOKEN), str(ROOT_TOKEN)])
    return str((out / 'suite.json').relative_to(ROOT)), projection


def derive(scratch):
    """Full derivation inside `scratch`; returns the receipt value."""
    os.chdir(ROOT)
    C.history(HISTORY)
    L.LIVE = scratch                       # the inherited v253 module writes control/candidate here
    L.RESIDENT_SUITE, projection = resident_v254(scratch)
    data = L.render()
    data['format'] = FORMAT
    data['v253_predecessor'] = dict(receipt=C.bind(str(P.PREDECESSOR.relative_to(ROOT))),
                                    improved=P.compare_253(data), shapes_not_lower=len(data['ladder']))
    data['inputs']['resident_suite'] = projection['base_suite']
    data['resident_domain_projection'] = projection
    old = json.loads((ROOT / PREDECESSOR_V254).read_text())
    cur = json.loads(L.canonical(data))
    for key in sorted(set(old) | set(cur)):
        if key not in INPUT_FIELDS:
            L.require(old.get(key) == cur.get(key), 'ladder content differs from 20261003 receipt: ' + key)
    for key in sorted(set(old['inputs']) | set(cur['inputs'])):
        if key != 'resident_suite':
            L.require(old['inputs'].get(key) == cur['inputs'].get(key), 'inputs differ from 20261003: ' + key)
    guard(data)
    return data


def run(action):
    scratch = new_scratch()
    try:
        data = derive(scratch)
        raw = L.canonical(data)
        if action == 'build':
            with RECEIPT.open('xb') as stream:
                stream.write(raw)
        else:
            L.require(RECEIPT.read_bytes() == raw, 'receipt drift: ' + RECEIPT_REL)
    finally:
        if os.environ.get(KEEP_ENV):
            print('lcc-nesting-ladder-v254-r2: scratch kept: %s' % scratch, file=sys.stderr)
        else:
            shutil.rmtree(scratch, ignore_errors=True)
    return data


def refused(value):
    try:
        guard(value)
    except L.LadderError:
        return True
    return False


def selftest():
    row = lambda p: dict(path=p, bytes=1, sha256='0' * 64)
    # the guard accepts the stable inputs ...
    L.require(not refused({'inputs': [row(BASE_RESIDENT), row('lib/domain-tier1.lisp')]}), 'guard refuses stable inputs')
    # ... and refuses the 20261003 defect class, in any nesting and for any scratch name
    for bad in ('build/lcc-nesting-ladder-v254-20261003-live/resident/suite.json',
                'build/lcc-nesting-ladder-v254-abc123/resident/suite.json',
                'build/lcc-nesting-ladder-v254-abc123/lcc.blob.bin'):
        L.require(refused({'a': {'b': [row(bad)]}}), 'guard accepts a bound scratch path: ' + bad)
    L.require(refused({'x': row('build/some-other-run/file.json')}), 'guard accepts an unexpected build/ path')
    # the committed 20261003 receipt is the real negative control
    L.require(refused(json.loads((ROOT / PREDECESSOR_V254).read_text())),
              'negative control: the 20261003 receipt is not refused')
    # the committed r2 receipt (when present) and the fresh derivation must pass the guard
    if RECEIPT.is_file():
        L.require(not refused(json.loads(RECEIPT.read_text())), 'the r2 receipt binds its own scratch area')
    # scratch lifecycle: fresh, unique, under build/, removed also on failure
    first, second = new_scratch(), new_scratch()
    try:
        L.require(first != second and first.parent == ROOT / 'build' and first.name.startswith(SCRATCH_PREFIX),
                  'scratch placement')
    finally:
        shutil.rmtree(first, ignore_errors=True)
        shutil.rmtree(second, ignore_errors=True)
    L.require(not first.exists() and not second.exists(), 'scratch not removed')
    before = set(os.listdir(ROOT / 'build'))
    try:
        original = globals()['derive']
        globals()['derive'] = lambda scratch: (_ for _ in ()).throw(L.LadderError('injected failure'))
        try:
            run('check')
        except L.LadderError:
            pass
        else:
            raise L.LadderError('injected failure not raised')
    finally:
        globals()['derive'] = original
    L.require(set(os.listdir(ROOT / 'build')) == before, 'failed run leaked its scratch directory')
    # the suite hash does not depend on the scratch name
    a, b = ROOT / 'build' / (SCRATCH_PREFIX + 'one'), ROOT / 'build' / (SCRATCH_PREFIX + 'two')
    L.require(normalise('"%s/resident/x"' % a, a) == normalise('"%s/resident/x"' % b, b), 'normalisation')


def main(argv):
    if argv not in (['build'], ['check'], ['selftest']):
        raise SystemExit('usage: lcc_nesting_ladder_v254_r2_20261004.py build | check | selftest')
    try:
        if argv == ['selftest']:
            selftest()
            print('lcc-nesting-ladder-v254-r2: selftest PASS (guard refuses a bound scratch path and the '
                  '20261003 receipt; scratch fresh, unique, removed also on failure)')
            return 0
        data = run(argv[0])
    except (L.LadderError, ValueError) as exc:
        print('lcc-nesting-ladder-v254-r2: FAIL: %s' % exc, file=sys.stderr)
        return 1
    print('lcc-nesting-ladder-v254-r2: %s PASS shapes=%d candidate>=2.5.2 and >=2.5.3 everywhere; improved: %s'
          % (argv[0], len(data['ladder']),
             ','.join('%s %d->%d' % (r['shape'], r['v253'], r['v254'])
                      for r in data['v253_predecessor']['improved'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
