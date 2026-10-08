#!/usr/bin/env python3
"""The "historical host pin" rule, 2.5.5 successor of historical_host_pin_20261004.py (immutable).

The rule is unchanged (reviewer decision 2026-10-04): a host tool row of a PAST release is accepted when its
recorded hash equals a pin in that release's own committed reproduction policy.  The live /usr/bin binary is not
required to match for a past release.  The live host is verified only for the CURRENT release; the rule refuses
to be used for it.

What changes with 2.5.5: the current release is 2.5.5 (live pins: c2_v255_r1_toolchain.py, one pin set, because
Seed, Final and reproductions ran on the same Fedora 45 host), and 2.5.4 becomes a past release.  2.5.4 has two
pin sets in its committed policy (config/c2-v254-r1-reproduction-policy.json): `host_tools`, the Fedora 45
reproduction host, and `host_qualification.final_host_tools`, the Fedora 44 host its Final was linked on.  A row
of 2.5.4 is accepted when its hash is a pin of either set; the answer names the set.  The 2.5.4 reproduction-host
pins happen to equal today's live binaries.  The rule does not use that: it never reads a live binary, so the
2.5.4 authority keeps verifying after the next host update, exactly as 2.5.3 and 2.5.2 did after the last one.

The rule changes nothing else: a row whose hash is not one of the release's own pins fails, a missing or foreign
policy fails, a path outside /usr/bin fails.  One alias is reviewed: /usr/bin/gcc is the binary /usr/bin/cc
resolves to (the 2.5.2 Seed receipts bind the resolved name, the policies pin the invoked name).

Users: c2_release_era_host_pin_v255_20261007.py (2.5.4, 2.5.3 and 2.5.2 historical preflights) and
c2_v255_r1_card5_product.py (2.5.2 r7 product receipts).  disk_r7_product_receipts_v254_r2_20261004.py keeps the
predecessor module: it asks about 2.5.2 only, which both modules answer alike, and it reads no live binary.
"""
import argparse
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CURRENT = '2.5.5'
POLICIES = {'2.5.4': 'config/c2-v254-r1-reproduction-policy.json',
            '2.5.3': 'config/c2-v253-r2-reproduction-policy.json',
            '2.5.2': 'config/c2-v252-r1-reproduction-policy.json'}
ALIASES = {'/usr/bin/gcc': '/usr/bin/cc'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin_sets(release, root=ROOT, policies=None):
    """{set name: {path: sha256}} of a past release; `host_tools` always, `final_host_tools` when the release's
    policy records a separate Final host (2.5.4)."""
    policies = POLICIES if policies is None else policies
    require(release != CURRENT, 'the historical host pin rule is not available for the current release')
    require(release in policies, 'no committed host pins for release ' + str(release))
    path = root / policies[release]
    require(path.is_file(), 'toolchain record of the release is missing: ' + policies[release])
    policy = json.loads(path.read_bytes())
    require(policy.get('release') == release and policy.get('host_tools'), 'toolchain record is for another release')
    rows = {'host_tools': policy['host_tools']}
    final = (policy.get('host_qualification') or {}).get('final_host_tools')
    if final is not None:
        require(final and [r['path'] for r in final] == [r['path'] for r in policy['host_tools']],
                'Final-host pin set does not name the same tools')
        rows['final_host_tools'] = final
    sets = {}
    for name, value in rows.items():
        sets[name] = {r['path']: r['sha256'] for r in value}
        require(len(sets[name]) == len(value) and all(p.startswith('/usr/bin/') for p in sets[name]),
                'toolchain record host pins malformed')
    return sets


def pins(release, root=ROOT, policies=None):
    """The reproduction-host pins of a past release (its policy's `host_tools`)."""
    return pin_sets(release, root, policies)['host_tools']


def accept(release, row, root=ROOT, policies=None):
    """Raise unless `row` (path, sha256[, bytes]) is a host tool pin of `release`."""
    sets = pin_sets(release, root, policies)
    path = row['path']
    require(isinstance(path, str) and path.startswith('/usr/bin/'), 'not a host tool row: ' + str(path))
    for label, known in sets.items():
        name = path if path in known else ALIASES.get(path)
        if name in known and row.get('sha256') == known[name]:
            return dict(path=path, pinned_as=name, sha256=known[name], release=release, pin_set=label)
    require(False, 'host tool row is not a pin of release %s: %s' % (release, path))


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
        CURRENT: 'config/c2-v255-r1-reproduction-policy.json'})))
    refused('unknown release', lambda: pins('2.5.1'))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'config').mkdir()
        bad = json.loads((ROOT / POLICIES['2.5.4']).read_bytes())
        bad['host_qualification']['final_host_tools'] = bad['host_qualification']['final_host_tools'][1:]
        (root / POLICIES['2.5.4']).write_text(json.dumps(bad))
        refused('Final-host pin set with another tool population', lambda: pin_sets('2.5.4', root))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        refused('missing toolchain record', lambda: pins('2.5.3', root))
        (root / 'config').mkdir()
        (root / POLICIES['2.5.3']).write_bytes((ROOT / POLICIES['2.5.2']).read_bytes())
        refused('record of another release', lambda: pins('2.5.3', root))
        (root / POLICIES['2.5.2']).write_text(json.dumps(dict(release='2.5.2', host_tools=[])))
        refused('record without pins', lambda: pins('2.5.2', root))
    # The live host is NOT what the rule looks at.  The current release's own tool verifies the live host; the
    # pins of 2.5.3 and 2.5.2 (and the Final-host set of 2.5.4) differ from the live binaries, and the rule
    # accepts them all the same.  The 2.5.4 reproduction-host pins equal the live ones today; the rule would
    # accept them after a host update too, which the last control shows with a host that has other binaries.
    import c2_v255_r1_toolchain as LIVE
    LIVE.host_tools()
    for release in ('2.5.3', '2.5.2'):
        require(all(LIVE.HOST_TOOLS[p] != pins(release)[p] for p in LIVE.HOST_TOOLS), 'past pins equal the live host pins')
    both = pin_sets('2.5.4')
    require(set(both) == {'host_tools', 'final_host_tools'} and
            all(both['host_tools'][p] != both['final_host_tools'][p] for p in both['host_tools']), '2.5.4 pin sets')
    require(all(LIVE.HOST_TOOLS[p] != both['final_host_tools'][p] for p in LIVE.HOST_TOOLS),
            'the 2.5.4 Final-host pins equal the live host pins')
    for label, known in both.items():
        for path, digest in known.items():
            require(accept('2.5.4', dict(path=path, sha256=digest))['pin_set'] == label, '2.5.4 pin set label')
    require(set(pin_sets('2.5.3')) == set(pin_sets('2.5.2')) == {'host_tools'}, 'single pin set of the older releases')
    refused('2.5.4 row with a pin of neither set', lambda: accept('2.5.4', dict(path='/usr/bin/cc', sha256='4' * 64)))
    # accept() must never read a live host binary.
    real = Path.read_bytes

    def guarded(self):
        require(not str(self).startswith('/usr/bin/'), 'the rule read a live host binary')
        return real(self)
    with patch.object(Path, 'read_bytes', guarded):
        for release in POLICIES:
            for path, digest in pins(release).items():
                accept(release, dict(path=path, sha256=digest))

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
