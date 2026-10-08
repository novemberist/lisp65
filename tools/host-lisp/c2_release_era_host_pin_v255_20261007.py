#!/usr/bin/env python3
"""Run the public authorities of the past releases 2.5.4, 2.5.3 and 2.5.2 under the "historical host pin" rule.

2.5.5 successor of c2_release_era_host_pin_v254_20261004.py (immutable; its rule module names 2.5.4 as the current
release).  With 2.5.5 as the current release, 2.5.4 is a past release: every route that verified 2.5.4 against the
LIVE /usr/bin binaries moves under the rule here, as 5fb181fd moved 2.5.3 and 2.5.2.
  2.5.4  c2_v254_r1_public_product.preflight + the 2.5.4 reproduction receipt validation
                                                    (route v254-public-authority-check)
  2.5.3  c2_v253_release_era_v254_20261004.check   (route v253-public-authority-check)
  2.5.2  c2_v253_r1_v252_release_era.check          (route v252-public-authority-check)
Each preflight binds the host tools of the release's replay recipe against the live binaries (host_bound).  Rule
(historical_host_pin_v255_20261007): for a past release a recorded host tool row is accepted when its hash is a
pin in that release's own committed reproduction policy.  Nothing else changes: the readers' code, their era
policies, the preflight, the receipt validation and the corrupted-source control run unmodified.
2.5.4 needs no source-era reader yet: no file its preflight reads has moved with 2.5.5 (only the IDE library
sources changed, and the 2.5.4 plane travels as compiled blobs), so its preflight runs on the live tree.  The
control for it is the same as for the era readers: a corrupted frozen native input must be rejected.  When a
later release moves a source the 2.5.4 preflight reads, an era reader for 2.5.4 comes first (the 2.5.3 pattern).
The live host is verified for the current release only (c2_v255_r1_toolchain.py, route v255-public-authority-check).
The 2.5.4 reproduction-gate SELFTEST (its dry-run binds the live host through c2_v254_r1_toolchain) leaves the
route for the same reason the 2.5.3 one did; its receipt `check` stays.

modes
  selftest      the rule's controls plus the controls of this wrapper (no Git or build work)
  check 2.5.4   the 2.5.4 public preflight and receipt validation under the rule
  check 2.5.3   the 2.5.3 era reader's check under the rule
  check 2.5.2   the 2.5.2 era reader's check under the rule
"""
import argparse
import importlib
import json

import historical_host_pin_v255_20261007 as H

READERS = {'2.5.4': (None, 'c2_v254_r1_public_native'),
           '2.5.3': ('c2_v253_release_era_v254_20261004', 'c2_v253_r2_public_native'),
           '2.5.2': ('c2_v253_r1_v252_release_era', 'c2_v252_r1_public_native')}
# 2.5.4, live tree: the frozen native input whose corruption the preflight must reject (same file role as the
# mutation victims of the era readers: the stream decoder source of the 2.5.4 replay inputs).
VICTIM_254 = 'c2-stream-decoder.c'


class Live254:
    """The 2.5.4 authority on the live tree, with the result shape of the era readers."""

    @staticmethod
    def check():
        from unittest.mock import patch
        from pathlib import Path
        import c2_v254_r1_public_native as N
        import c2_v254_r1_public_product as P
        import c2_v254_r1_reproduction_gate as R
        native = P.preflight()
        H.require(str(native.get('status', '')).startswith('PASS: 2.5.4 FINAL IDENTITY'), '2.5.4 preflight did not pass')
        policy = json.loads(R.POLICY.read_bytes())
        H.require(policy == R.derive_policy(), 'reproduction policy stale')
        R.validate(json.loads(R.RECEIPT.read_bytes()), policy)
        victims = [r['source']['path'] for r in json.loads(N.RECIPE.read_bytes())['inputs']
                   if r['source']['path'].endswith('/' + VICTIM_254) and r['source']['path'].startswith('config/')]
        H.require(victims, 'no mutation victim among the 2.5.4 replay inputs')
        victim = str(N.ROOT / victims[0])
        real = Path.read_bytes

        def corrupt(self):
            raw = real(self)
            return raw + b'changed' if str(self) == victim else raw
        with patch.object(Path, 'read_bytes', corrupt):
            try:
                N.check()
            except ValueError:
                pass
            else:
                raise ValueError('corrupted historical source survived')
        return dict(status='PASS', release='2.5.4', source_world='live tree (no moved source)', native=native['status'],
                    mutation_victim=victims[0], mutation_rejected=True)



def check(release):
    H.require(release in READERS and release != H.CURRENT, 'no historical era reader for release ' + str(release))
    name, native = READERS[release]
    reader = Live254 if name is None else importlib.import_module(name)
    native = importlib.import_module(native)
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
    H.require([r for r, (reader, _) in READERS.items() if reader is None] == ['2.5.4'], 'live-tree reader population')
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
