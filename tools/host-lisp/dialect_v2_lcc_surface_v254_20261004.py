#!/usr/bin/env python3
"""2.5.4 dated LCC surface fixture: funcall of a literal lambda and eq/eql/bit-operation arity.

The base fixture tests/bytecode/dialect-v2/lcc-surface/cases.json is frozen by
the exact id population of dialect_v2_lcc_surface (REQUIRED_IDS).  The 2.5.4
LCC changes get their own dated fixture, run by the unchanged harness:

  funcall-lambda-*   (funcall (lambda ...) ...) is compiled directly: it reads and
                     assigns the enclosing let, keeps argument order and is refused
                     at compile time for a wrong argument count
  arity-*            eq, eql, logand, logior, logxor, ash with other than two
                     arguments are refused instead of silently dropping arguments

Each row records the frozen dialect-v1 observation (the pre-2.5.4 behaviour
class: surplus arguments dropped, the enclosing variable not assigned) and the
live dialect-v2 observation.  Modes: selftest (fixture shape, id population,
mutations) and check (both binaries, as dialect-v2-lcc-surface-check).
"""
import argparse
import copy
import json
from pathlib import Path

import dialect_v2_lcc_surface as L

FIXTURE = L.ROOT / 'tests/bytecode/dialect-v2/lcc-surface/cases-v254-20261004.json'
REFUSED = '!error:code=59:symbol=%lcc-error-invalid-parameter-list'
IDS = {
    'arity-ash-one-argument-refused', 'arity-ash-three-arguments-refused', 'arity-ash-two-arguments',
    'arity-eq-in-defun-refused', 'arity-eq-one-argument-refused', 'arity-eq-surplus-argument-not-dropped',
    'arity-eq-three-arguments-refused', 'arity-eq-two-arguments', 'arity-eql-one-argument-refused',
    'arity-eql-three-arguments-refused', 'arity-logand-one-argument-refused',
    'arity-logand-three-arguments-refused', 'arity-logand-two-arguments',
    'arity-logior-three-arguments-refused', 'arity-logxor-three-arguments-refused',
    'funcall-lambda-argument-order', 'funcall-lambda-arguments', 'funcall-lambda-constant',
    'funcall-lambda-nested', 'funcall-lambda-optional-default', 'funcall-lambda-reads-enclosing-let',
    'funcall-lambda-rest', 'funcall-lambda-setq-enclosing-let', 'funcall-lambda-too-few-refused',
    'funcall-lambda-too-many-refused',
}


def validate(value):
    L.REQUIRED_IDS = IDS
    cases = L.validate_fixture(value)
    for case in cases:
        refused = case['id'].endswith('-refused') or case['id'] == 'arity-eq-surplus-argument-not-dropped'
        if (case['dialect-v2'] == REFUSED) != refused:
            raise L.SurfaceError('v254 refusal population drift: ' + case['id'])
        if case['dialect-v1'] == REFUSED:
            raise L.SurfaceError('frozen dialect-v1 cannot carry the 2.5.4 refusal: ' + case['id'])
    return cases


def selftest():
    original = json.loads(FIXTURE.read_bytes())
    cases = validate(original)
    mutations = []
    missing = copy.deepcopy(original)
    missing['cases'].pop()
    mutations.append(missing)
    accepted = copy.deepcopy(original)
    next(c for c in accepted['cases'] if c['id'] == 'arity-eq-three-arguments-refused')['dialect-v2'] = 't'
    mutations.append(accepted)
    spurious = copy.deepcopy(original)
    next(c for c in spurious['cases'] if c['id'] == 'arity-eq-two-arguments')['dialect-v2'] = REFUSED
    mutations.append(spurious)
    for index, value in enumerate(mutations):
        try:
            validate(value)
        except L.SurfaceError:
            continue
        raise L.SurfaceError('v254 selftest mutation %d was accepted' % index)
    print('dialect-v2-lcc-surface-v254: SELFTEST PASS cases=%d mutations=%d' % (len(cases), len(mutations)))


def check(args):
    validate(json.loads(FIXTURE.read_bytes()))
    L.run(FIXTURE, args.binary_v1, args.binary_v2, args.source_root_v1, args.source_root_v2)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['selftest', 'check'])
    p.add_argument('--binary-v1', type=Path, default=L.DEFAULT_V1_BINARY)
    p.add_argument('--binary-v2', type=Path, default=L.DEFAULT_V2_BINARY)
    p.add_argument('--source-root-v1', type=Path)
    p.add_argument('--source-root-v2', type=Path, default=L.ROOT)
    a = p.parse_args()
    try:
        if a.mode == 'selftest':
            selftest()
        else:
            if a.source_root_v1 is None:
                p.error('--source-root-v1 required')
            check(a)
    except L.SurfaceError as exc:
        raise SystemExit('dialect-v2-lcc-surface-v254: FAIL: %s' % exc)
