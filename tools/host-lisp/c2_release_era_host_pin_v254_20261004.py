#!/usr/bin/env python3
"""Run the historical 2.5.3 and 2.5.2 public-authority era readers under the "historical host pin" rule.

Successor of the `check` lines of two committed, immutable era readers:
  2.5.3  c2_v253_release_era_v254_20261004.check   (route v253-public-authority-check)
  2.5.2  c2_v253_r1_v252_release_era.check          (route v252-public-authority-check)
Both run the release's public preflight inside the release's own source era.  That preflight binds the host tools
of the release's replay recipe against the LIVE /usr/bin binaries; since the build host moved to Fedora 45
(2026-10-04) those binaries are no longer the ones the releases were built with, so the readers fail on the host
alone.  Rule (historical_host_pin_20261004): for a past release a recorded host tool row is accepted when its hash
is the pin in that release's own committed reproduction policy.  Nothing else changes: the readers' code, their
era policies, the preflight, the receipt validation and the corrupted-source control run unmodified.
The live host is verified for the current release only (c2_v254_r1_toolchain.py, route v254-public-authority-check).

modes
  selftest      the rule's controls plus the controls of this wrapper (no Git or build work)
  check 2.5.3   the 2.5.3 era reader's check under the rule
  check 2.5.2   the 2.5.2 era reader's check under the rule
"""
import argparse
import importlib
import json

import historical_host_pin_20261004 as H

READERS = {'2.5.3': ('c2_v253_release_era_v254_20261004', 'c2_v253_r2_public_native'),
           '2.5.2': ('c2_v253_r1_v252_release_era', 'c2_v252_r1_public_native')}


def check(release):
    H.require(release in READERS and release != H.CURRENT, 'no historical era reader for release ' + str(release))
    reader, native = (importlib.import_module(n) for n in READERS[release])
    recipe = json.loads(native.RECIPE.read_bytes())
    rows = [H.accept(release, row) for row in recipe['host_tools']]
    with H.native_world(release, native) as seen:
        result = reader.check()
    H.require(result['status'] == 'PASS' and result['release'] == release and result['mutation_rejected'] is True,
              'historical era reader did not pass')
    H.require(len(seen) >= len(rows), 'historical preflight bound fewer host tools than its recipe names')
    return dict(result, host_rule='historical host pin', host_rows=rows, host_bindings=len(seen))


def selftest():
    rule = H.selftest()
    rejected = []

    def refused(label, fn):
        try:
            fn()
        except ValueError:
            rejected.append(label)
            return
        raise AssertionError('era host pin control survived: ' + label)
    refused('current release', lambda: check(H.CURRENT))
    refused('unknown release', lambda: check('2.5.1'))
    H.require(set(READERS) == set(H.POLICIES), 'reader/policy population')
    for release, (reader, native) in READERS.items():
        module = importlib.import_module(native)
        recipe = json.loads(module.RECIPE.read_bytes())
        H.require(recipe['host_tools'], 'historical recipe names no host tool: ' + release)
        for row in recipe['host_tools']:
            H.accept(release, row)
            refused('recipe row with a foreign hash ' + release,
                    lambda: H.accept(release, dict(row, sha256='0' * 64)))
        # Without the rule the committed authority still verifies the live host (and fails after the upgrade
        # exactly there); the wrapper must not have replaced that function outside its world.
        H.require(module.host_bound.__module__ == native, 'live host binding replaced outside the rule world')
    return dict(status='PASS', rule=rule, controls_rejected=len(rejected), readers=sorted(READERS))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['selftest', 'check'])
    p.add_argument('release', nargs='?')
    a = p.parse_args()
    print(json.dumps(selftest() if a.mode == 'selftest' else check(a.release), indent=2))
