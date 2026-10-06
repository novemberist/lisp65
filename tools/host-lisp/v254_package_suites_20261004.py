#!/usr/bin/env python3
"""2.5.4 package and stdlib case suites as a permanent host gate (RP1, HIST1, LIB1, mapcan).

  tests/bytecode/libs/p0-repl-comfort-r254.json    RP1 bounded result print + HIST1 comment scan,
      run like the O2-lite Comfort regressions: live REPL-COMFORT sources (2.5.4 O2-lite pin) over
      the O2-lite resident (o2_lite_r3_host.setup, local build tree).  That frozen resident
      carries the pre-2.5.3 nth and the pre-2.5.4 mapcan, so the editor product list domain
      pre-check is waived for this one suite exactly as in
      c2_v253_r2_public_libraries.comfort_reemission (the Seed re-seals the resident projection)
  tests/bytecode/libs/p0-defstruct-names-r254.json LIB1 generated-name collision refusal
  tests/bytecode/libs/p0-stdlib-mapcan-r254.json   mapcan beyond the 12-argument call limit

Controls (the suites must discriminate the 2.5.3 sources of the sealed 2.5.3 commit):
  Comfort suite with the 2.5.3 lite-hot/repl-comfort sources  -> must fail
  defstruct suite with the 2.5.3 lib/defstruct.lisp           -> must fail
  mapcan suite with the 2.5.3 lib/stdlib-lists.lisp           -> must fail
Modes: selftest (declared populations, no VM), check (all of the above).
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import bytecode_p0_stdlib as P
import evidence_era as E
import c2_v254_r1_common as C
import o2_lite_consumers_v254_20261003 as V
from strings_scratch_20260928 import scratch

COMFORT = 'tests/bytecode/libs/p0-repl-comfort-r254.json'
DEFSTRUCT = 'tests/bytecode/libs/p0-defstruct-names-r254.json'
MAPCAN = 'tests/bytecode/libs/p0-stdlib-mapcan-r254.json'
# total cases, cases declared by the r254 suite itself
POPULATION = {COMFORT: (61, 29), DEFSTRUCT: (31, 17), MAPCAN: (195, 7)}
OLD = {COMFORT: ('lib/lite-hot.lisp', 'lib/repl-comfort-v250.lisp'), DEFSTRUCT: ('lib/defstruct.lisp',),
       MAPCAN: ('lib/stdlib-lists.lisp',)}


def declared():
    for path, (_total, own) in POPULATION.items():
        raw = json.loads((C.ROOT / path).read_bytes())
        C.require(len(raw['cases']) == own and len({c['name'] for c in raw['cases']}) == own,
                  'r254 suite declaration drift: ' + path)
    C.require(json.loads((C.ROOT / MAPCAN).read_bytes()).get('max_call_args') == 12, 'mapcan suite call limit')


def with_era_sources(suite, names, out):
    """The same suite with the named sources as the sealed 2.5.3 commit carried them."""
    trial = dict(suite)
    sources = []
    for source in suite['sources']:
        rel = Path(source).resolve().relative_to(C.ROOT.resolve()).as_posix() if Path(source).is_absolute() else source
        if rel in names:
            copy = out / ('era-' + Path(rel).name)
            copy.write_bytes(E.era_blob(C.ERA_V253, rel))
            source = str(copy)
        sources.append(source)
    C.require(sources != list(suite['sources']), 'control replaced no source')
    trial['sources'] = sources
    return trial


def run(path, suite, out, rows):
    total = POPULATION[path][0]
    result = P.check_suite(path, suite)
    C.require(result['cases'] == total, 'r254 suite population drift: ' + path)
    try:
        P.check_suite(path, with_era_sources(suite, OLD[path], out))
    except Exception as exc:  # the 2.5.3 sources must not satisfy the suite
        control = type(exc).__name__ + ': ' + str(exc)[:80]
    else:
        raise ValueError('r254 suite does not discriminate the 2.5.3 sources: ' + path)
    rows.append(dict(suite=path, cases=total, control_2_5_3_sources='FAIL ' + control))


def check():
    import o2_lite_r3_host as H
    declared()
    V.route_children()
    O = V.install()
    rows = []
    with O.suites(), scratch() as out:
        H.setup(out)
        suite = P._read_suite(str(C.ROOT / COMFORT))
        suite['resident_suite'] = str(out / 'resident.json')
        import editor_product_list_domain  # noqa: F401  (the waived pre-check lives here)
        with patch('editor_product_list_domain.check_suite', lambda s: None):
            run(COMFORT, suite, out, rows)
        for path in (DEFSTRUCT, MAPCAN):
            run(path, P._read_suite(str(C.ROOT / path)), out, rows)
    return dict(status='PASS', suites=rows)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['selftest', 'check'])
    a = p.parse_args()
    if a.mode == 'selftest':
        declared()
        result = dict(status='PASS', suites=len(POPULATION))
    else:
        result = check()
    print(json.dumps(result, indent=2))
