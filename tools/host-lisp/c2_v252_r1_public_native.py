#!/usr/bin/env python3
"""2.5.2 public source authority for the O2-lite r7c Final; no reproduction claim.

check: every frozen public input (native replay copies, plane, media sources,
policies) is bound and the 75-command r7c recipe has its exact shape.
private (preflight only): additionally binds the sealed Final and proves each
public copy equals the Seed input the Final consumed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'c2-v252-r1-public'
AUTHORITY = ROOT / ('config/%s-build-authority.json' % PREFIX)
RECIPE = ROOT / ('config/%s-replay.json' % PREFIX)
FINAL_SHA = {
    'ELF': '4edcc037a3fd729cc124ae40d8c85349889ba17941e3468f1ffe8c2de2aa4abd',
    'PRG': 'f74ca2df859d0f521f3926a6e9306f0cb9d53e7fe686c35899239eaca3281972',
    'LTO': 'af01c0a83d94429fcc747534cfcd76ad920a050a52d72cba3b07430966c1cf2a',
    'D81': 'ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d',
}
FINAL_DIR = 'build/o2-lite-final-r7c'
POLICIES = ['replay', 'normalization', 'include-closure', 'plane', 'media-reproduction', 'comfort-reemission']
TREES = ['replay-inputs', 'plane', 'media']


def canonical(v):
    return (json.dumps(v, indent=2, sort_keys=True) + '\n').encode()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def local(name):
    p = Path(name)
    require(p.parts and not p.is_absolute() and '..' not in p.parts, 'non-local path: ' + str(name))
    result = ROOT / p
    require(not any((ROOT / Path(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts) + 1)),
            'symlink path: ' + str(name))
    return result


def bound(row):
    """Exact bytes, or the reviewed exported (normalized) form of a bound row."""
    p = local(row['path'])
    require(p.is_file(), 'missing input: ' + row['path'])
    raw = p.read_bytes()
    expected = {k: row[k] for k in ('bytes', 'sha256')}
    if identity(raw) != expected:
        import c2_v252_r1_public_normalization as Z
        require(Z.accepts(row['path'], raw, expected), 'input identity drift: ' + row['path'])
    return raw


def host_bound(row):
    p = Path(row['path'])
    require(p.is_absolute() and str(p).startswith('/usr/bin/'), 'host tool outside /usr/bin')
    require(identity(p.read_bytes()) == {k: row[k] for k in ('bytes', 'sha256')},
            'host tool drift (pinned Final environment): ' + row['path'])


def load(path):
    return json.loads(Path(path).read_bytes())


def expected_population():
    names = {'config/%s-%s.json' % (PREFIX, n) for n in POLICIES}
    for tree in TREES:
        names |= {str(p.relative_to(ROOT)) for p in (ROOT / 'config' / ('%s-%s' % (PREFIX, tree))).rglob('*') if p.is_file()}
    return names


def validate_recipe(recipe, pinned=None):
    if pinned is not None:
        require(identity(canonical(recipe)) == {k: pinned[k] for k in ('bytes', 'sha256')}, 'replay recipe drift')
    commands = recipe['commands']
    require(recipe['format'] == 'lisp65-v252-o2-lite-r7c-public-replay-v1', 'wrong replay format')
    require(len(commands) == 75 and all(c.count('-o') == 1 for c in commands), 'native command population')
    require(all('-c' in c and c[0] == 'tools/llvm-mos/bin/mos-mega65-clang' for c in commands[:73]), 'compile shape')
    require(commands[73][0] == '/usr/bin/llvm-link' and '-c' not in commands[73], 'bitcode merge shape')
    require(commands[74][:4] == ['/usr/bin/setarch', 'x86_64', '-R', 'tools/llvm-mos/bin/mos-mega65-clang'] and
            '-c' not in commands[74] and '-Wl,--emit-relocs' in commands[74], 'single product link shape')
    outputs = [c[c.index('-o') + 1] for c in commands]
    require(len(set(outputs)) == 75 and all(o.startswith(FINAL_DIR + '/wplto/') for o in outputs), 'native output layout')
    require(outputs[74] == FINAL_DIR + '/wplto/resident-island-seed.prg', 'product output')
    require(set(recipe['raw_pair']) == set(FINAL_SHA) and
            all(recipe['raw_pair'][k]['sha256'] == v for k, v in FINAL_SHA.items()), 'wrong Final raw pair')
    paths = [r['materialized_path'] for r in recipe['inputs']]
    require(len(paths) == len(set(paths)), 'duplicate replay input')
    copies = [r for r in recipe['inputs'] if not r['materialized_path'].startswith('tools/llvm-mos/')]
    require(len(copies) == 235 and all(r['source']['path'] == 'config/%s-replay-inputs/%s' % (PREFIX, r['materialized_path'])
                                       for r in copies), 'replay copy population/location')
    for r in recipe['inputs']:
        bound(r['source'])
    for row in recipe['host_tools']:
        host_bound(row)
    return len(copies), len(recipe['inputs']) - len(copies)


def validate(a, private=False):
    require(a['format'] == 'lisp65-v252-public-build-authority-v1' and a['release'] == '2.5.2', 'release/format drift')
    require(a['product_build_id'] == '0x8d22c8e6', 'wrong product build ID')
    require(all(a['raw_pair'][k]['sha256'] == v for k, v in FINAL_SHA.items()), 'wrong Final raw pair')
    rows = a['source_authorities']
    require({r['path'] for r in rows} == expected_population() and len(rows) == len(expected_population()),
            'source authority population drift')
    for row in rows:
        bound(row)
    bound(a['export_policy'])
    pinned = next(r for r in rows if r['path'] == 'config/%s-replay.json' % PREFIX)
    recipe = json.loads(bound(pinned))
    require(recipe['raw_pair'] == a['raw_pair'], 'authority/recipe raw pair mismatch')
    copies, toolchain = validate_recipe(recipe, pinned)
    result = dict(status='PASS: O2-LITE R7C PUBLIC SOURCE AUTHORITY', inputs=len(rows), native_copies=copies,
                  toolchain_inputs=toolchain, compiler_invocations=0, public_reproduction=False)
    if private:
        result['private'] = private_check(a, recipe)
    return result


def private_check(a, recipe):
    """Final seal + Seed-input equality; only possible in the private tree."""
    for key in ('final_identity', 'final_seal', 'final_invocation', 'final_media_readback'):
        bound(a[key])
    final = load(local(a['final_identity']['path']))
    seal = load(local(a['final_seal']['path']))
    require(final['status'] == 'PASS' and final['native_commands_consumed'] == 75 and
            final['product_links_claimed'] == 1 and final['budget'] == dict(final=1, link=1, seed_rebuilds=0),
            'Final not accepted')
    require(seal['status'] == 'PASS' and seal['format'] == 'o2-lite-final-r7c-seal-v1' and
            seal['final']['artifacts'] == final['artifacts'], 'Final seal mismatch')
    pairs = {p['role']: p for p in final['artifacts']}
    for role, row in a['raw_pair'].items():
        require(pairs[role]['final'] == row and pairs[role]['byteidentical'] is True, 'Final pair drift: ' + role)
        bound(row)
    invocation = load(local(a['final_invocation']['path']))
    private = str(ROOT) + '/'
    require([[x.replace(private, '') for x in c] for c in invocation['commands']] == recipe['commands'],
            'public recipe differs from the Final native commands')
    for r in recipe['inputs']:
        if not r['materialized_path'].startswith('tools/'):
            require(local(r['materialized_path']).read_bytes() == local(r['source']['path']).read_bytes(),
                    'public copy differs from consumed Seed input: ' + r['materialized_path'])
    return dict(final=a['final_identity'], seal=a['final_seal'], seed_inputs_equal=True)


def check(private=False):
    return validate(load(AUTHORITY), private)


def selftest():
    a = load(AUTHORITY)
    result = validate(a)
    trials = []
    v = copy.deepcopy(a); v['source_authorities'].pop(); trials.append(v)
    v = copy.deepcopy(a); v['source_authorities'][0]['sha256'] = '0' * 64; trials.append(v)
    v = copy.deepcopy(a); v['raw_pair']['ELF']['sha256'] = '0' * 64; trials.append(v)
    v = copy.deepcopy(a); v['release'] = '2.5.1'; trials.append(v)
    v = copy.deepcopy(a); v['source_authorities'][0]['path'] = '../escape'; trials.append(v)
    for v in trials:
        try:
            validate(v)
        except ValueError:
            pass
        else:
            raise ValueError('authority mutation survived')
    recipe = load(RECIPE)
    pinned = next(r for r in a['source_authorities'] if r['path'] == 'config/%s-replay.json' % PREFIX)
    for mutate in (lambda r: r['commands'][74].append('-DUNREVIEWED'), lambda r: r['commands'].pop(),
                   lambda r: r['inputs'].pop(), lambda r: r['inputs'][0]['source'].update(sha256='0' * 64)):
        r = copy.deepcopy(recipe); mutate(r)
        try:
            validate_recipe(r, pinned)
        except (ValueError, StopIteration, IndexError):
            continue
        raise ValueError('recipe mutation survived')
    return dict(result, mutations_rejected=len(trials) + 4)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['check', 'selftest', 'private']); a = p.parse_args()
    print(json.dumps(selftest() if a.mode == 'selftest' else check(a.mode == 'private'), indent=2))
