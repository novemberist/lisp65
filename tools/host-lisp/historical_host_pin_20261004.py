#!/usr/bin/env python3
"""The "historical host pin" rule (reviewer decision 2026-10-04, after the build host moved to Fedora 45).

A host tool row of a PAST release is accepted when its recorded hash equals the pin in that release's own
committed reproduction policy (config/...-reproduction-policy.json, field host_tools).  The live /usr/bin binary
is not required to match for a past release: the release was built and reproduced on the host of its time, and
that host no longer exists.  The live host is verified only for the CURRENT release (2.5.4: the Fedora 45 pins of
c2_v254_r1_toolchain.py); the rule refuses to be used for it.

The rule changes nothing else: a row whose hash is not the release's own pin fails, a missing or foreign policy
fails, a path outside /usr/bin fails.  One alias is reviewed: /usr/bin/gcc is the binary /usr/bin/cc resolves to
(the 2.5.2 Seed receipts bind the resolved name, the policies pin the invoked name).

Users: c2_release_era_host_pin_v254_20261004.py (2.5.3 and 2.5.2 historical preflights),
disk_r7_product_receipts_v254_r2_20261004.py and c2_v254_r1_card5_product.py (2.5.2 r7 product receipts).
"""
import argparse
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CURRENT = '2.5.4'
POLICIES = {'2.5.3': 'config/c2-v253-r2-reproduction-policy.json',
            '2.5.2': 'config/c2-v252-r1-reproduction-policy.json'}
ALIASES = {'/usr/bin/gcc': '/usr/bin/cc'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pins(release, root=ROOT, policies=None):
    policies = POLICIES if policies is None else policies
    require(release != CURRENT, 'the historical host pin rule is not available for the current release')
    require(release in policies, 'no committed host pins for release ' + str(release))
    path = root / policies[release]
    require(path.is_file(), 'toolchain record of the release is missing: ' + policies[release])
    policy = json.loads(path.read_bytes())
    require(policy.get('release') == release and policy.get('host_tools'), 'toolchain record is for another release')
    value = {r['path']: r['sha256'] for r in policy['host_tools']}
    require(len(value) == len(policy['host_tools']) and all(p.startswith('/usr/bin/') for p in value),
            'toolchain record host pins malformed')
    return value


def accept(release, row, root=ROOT, policies=None):
    """Raise unless `row` (path, sha256[, bytes]) is a host tool pin of `release`."""
    known = pins(release, root, policies)
    path = row['path']
    require(isinstance(path, str) and path.startswith('/usr/bin/'), 'not a host tool row: ' + str(path))
    name = path if path in known else ALIASES.get(path)
    require(name in known and row.get('sha256') == known[name],
            'host tool row is not a pin of release %s: %s' % (release, path))
    return dict(path=path, pinned_as=name, sha256=known[name], release=release)


def is_host_row(row):
    return isinstance(row, dict) and isinstance(row.get('path'), str) and row['path'].startswith('/usr/bin/')


@contextmanager
def native_world(release, module):
    """Inside: `module.host_bound(row)` (a public-native authority of a past release) applies the rule."""
    seen = []
    with patch.object(module, 'host_bound', lambda row: seen.append(accept(release, row))):
        yield seen
    require(seen, 'historical preflight bound no host tool')


@contextmanager
def checked_world(release, module):
    """Inside: `module.checked(row)` applies the rule to host tool rows and is unchanged for every other row."""
    seen = []
    original = module.checked

    def checked(row):
        if is_host_row(row) or str(row.get('path', '')) in ALIASES:
            seen.append(accept(release, row))
            return b''
        return original(row)
    with patch.object(module, 'checked', checked):
        yield seen
    require(seen, 'historical receipts bound no host tool')


def selftest():
    import tempfile
    rejected = []

    def refused(label, fn):
        try:
            fn()
        except ValueError:
            rejected.append(label)
            return
        raise AssertionError('historical host pin control survived: ' + label)
    for release in POLICIES:
        known = pins(release)
        for path, digest in known.items():
            require(accept(release, dict(path=path, sha256=digest))['pinned_as'] == path, 'own pin refused')
            refused('foreign hash ' + release + ' ' + path, lambda: accept(release, dict(path=path, sha256='0' * 64)))
        require(accept(release, dict(path='/usr/bin/gcc', sha256=known['/usr/bin/cc']))['pinned_as'] == '/usr/bin/cc',
                'reviewed alias refused')
        refused('alias with foreign hash ' + release, lambda: accept(release, dict(path='/usr/bin/gcc', sha256='1' * 64)))
        refused('unknown tool ' + release, lambda: accept(release, dict(path='/usr/bin/ld', sha256=known['/usr/bin/cc'])))
        refused('path outside /usr/bin ' + release,
                lambda: accept(release, dict(path='tools/llvm-mos/bin/clang', sha256=known['/usr/bin/cc'])))
    # The current release cannot use the rule, with or without a policy of its own.
    refused('current release', lambda: pins(CURRENT))
    refused('current release with a policy', lambda: pins(CURRENT, policies=dict(POLICIES, **{
        CURRENT: 'config/c2-v254-r1-reproduction-policy.json'})))
    refused('unknown release', lambda: pins('2.5.1'))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        refused('missing toolchain record', lambda: pins('2.5.3', root))
        (root / 'config').mkdir()
        (root / POLICIES['2.5.3']).write_bytes((ROOT / POLICIES['2.5.2']).read_bytes())
        refused('record of another release', lambda: pins('2.5.3', root))
        (root / POLICIES['2.5.2']).write_text(json.dumps(dict(release='2.5.2', host_tools=[])))
        refused('record without pins', lambda: pins('2.5.2', root))
    # The live host is NOT what the rule looks at: the pins of the past releases differ from the live binaries
    # after the upgrade, and the current release's own tool still verifies the live host.
    import c2_v254_r1_toolchain as LIVE
    LIVE.host_tools()
    require(all(LIVE.HOST_TOOLS[p] != pins('2.5.3')[p] for p in LIVE.HOST_TOOLS), 'past pins equal the live host pins')

    class Module:
        @staticmethod
        def host_bound(row):
            raise AssertionError('live binding reached')

        @staticmethod
        def checked(row):
            return b'live'
    with native_world('2.5.3', Module) as seen:
        Module.host_bound(dict(path='/usr/bin/setarch', sha256=pins('2.5.3')['/usr/bin/setarch']))
    require(len(seen) == 1, 'native world')

    def unused_world():
        with native_world('2.5.3', Module):
            pass
    refused('native world without a host row', unused_world)
    with checked_world('2.5.2', Module) as seen:
        require(Module.checked(dict(path='config/x.json', sha256='0')) == b'live', 'non-host row changed')
        Module.checked(dict(path='/usr/bin/gcc', sha256=pins('2.5.2')['/usr/bin/cc'], bytes=1))
        refused('checked world foreign hash', lambda: Module.checked(dict(path='/usr/bin/gcc', sha256='2' * 64)))
    require(len(seen) == 1 and Module.checked(dict(path='a')) == b'live', 'checked world not restored')
    return dict(status='PASS', releases=sorted(POLICIES), current=CURRENT, controls_rejected=len(rejected))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['selftest'])
    p.parse_args()
    print(json.dumps(selftest(), indent=2))
