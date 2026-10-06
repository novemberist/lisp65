#!/usr/bin/env python3
"""2.5.4 public source authority for the 2.5.4 Final; no reproduction claim.

check: every frozen public input (native replay copies, plane, media sources,
policies) is bound and the 75-command 2.5.4 Final recipe has its exact shape.
private (preflight only): additionally binds the sealed Final and proves each
public copy equals the Seed input the Final consumed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'c2-v254-r1-public'
AUTHORITY = ROOT / ('config/%s-build-authority.json' % PREFIX)
RECIPE = ROOT / ('config/%s-replay.json' % PREFIX)
FINAL_SHA = {
    'ELF': '7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244',
    'PRG': '192138eb70b4dc46a992e95651f52180a4e1687cd138b9347f8e3b77e37d70c4',
    'LTO': 'e9d6dc850e01dac45efb0dc1163ac3b463a5d26e00a49c3107380073da472afc',
    'D81': '250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d',
}
FINAL_DIR = 'build/card-254-final-r1'
# Inherited 2.5.3 r8 seam, unchanged in 2.5.4 (native sources are unchanged; .text is byte-for-byte the same size):
# the ONE compiled repl.c (command 18) is the frozen Comfort-default copy with the reviewed mem_oom
# landing hunk already applied; the public replay input carries those projected bytes (nothing is re-derived).
REPL_COMMAND = 18
REPL_SUFFIX = 'build/comfort-default-r2/seed/repl.c'
REPL_PROJECTED_SHA256 = '6499b37cb5578f3175ae197eeee47de9400fbd05c834f094b664e1553b3bca28'
REPL_FROZEN_SHA256 = '3d0c39b098bad2de6011d46ada91c045c9365e89644557f135f5fe0054083a33'
REPL_AUTHORITY_SHA256 = '2124d0d074dcc6ddda158fdb9adc4bd8fc56440bf5039b15ebebe5a295fa4b2f'
POLICIES = ['replay', 'normalization', 'include-closure', 'plane', 'media-reproduction', 'comfort-reemission',
            'defstruct-reemission']
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
        import c2_v254_r1_public_normalization as Z
        require(Z.accepts(row['path'], raw, expected), 'input identity drift: ' + row['path'])
    return raw


def host_bound(row):
    p = Path(row['path'])
    require(p.is_absolute() and str(p).startswith('/usr/bin/'), 'host tool outside /usr/bin')
    require(identity(p.read_bytes()) == {k: row[k] for k in ('bytes', 'sha256')},
            'host tool drift (pinned reproduction host): ' + row['path'])


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
    require(recipe['format'] == 'lisp65-v254-card-254-r1-public-replay-v1', 'wrong replay format')
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
    compiled = [c[c.index('-c') + 1] for c in commands[:73] if c[c.index('-c') + 1].endswith('/repl.c')]
    require(len(compiled) == 1 and commands[REPL_COMMAND][commands[REPL_COMMAND].index('-c') + 1] == compiled[0] and
            compiled[0].endswith(REPL_SUFFIX), 'compiled repl.c population')
    seam = recipe['repl_seam']
    require(seam['compiled_source'] == compiled[0] and seam['command_index'] == REPL_COMMAND and
            seam['projected_sha256'] == REPL_PROJECTED_SHA256 and seam['frozen_comfort_copy_sha256'] == REPL_FROZEN_SHA256 and
            seam['authority_src_repl_sha256'] == REPL_AUTHORITY_SHA256, 'repl.c seam record drift')
    repl = [r for r in recipe['inputs'] if r['materialized_path'] == compiled[0]]
    require(len(repl) == 1 and repl[0]['source']['sha256'] == REPL_PROJECTED_SHA256, 'compiled repl.c is not the projection')
    copies = [r for r in recipe['inputs'] if not r['materialized_path'].startswith('tools/llvm-mos/')]
    require(len(copies) == 235 and all(r['source']['path'] == 'config/%s-replay-inputs/%s' % (PREFIX, r['materialized_path'])
                                       for r in copies), 'replay copy population/location')
    for r in recipe['inputs']:
        bound(r['source'])
    import c2_v254_r1_toolchain as HOSTPINS
    q = recipe['host_qualification']
    require({r['path']: r['sha256'] for r in recipe['host_tools']} ==
            {p: HOSTPINS.HOST_TOOLS[p] for p in ('/usr/bin/llvm-link', '/usr/bin/setarch')}, 'reproduction host pins')
    require({r['path']: r['sha256'] for r in q['final_host_tools']} ==
            {p: HOSTPINS.FINAL_HOST_TOOLS[p] for p in ('/usr/bin/llvm-link', '/usr/bin/setarch')}, 'Final host pins')
    require(q['reproduction_host'] == HOSTPINS.HOST and q['final_host'] == HOSTPINS.FINAL_HOST and
            q['rule'] == HOSTPINS.RULE, 'host qualification record drift')
    merged = commands[73][commands[73].index('-o') + 1]
    require(q['host_dependent_intermediate']['path'] == merged and merged not in
            {r['path'] for r in recipe['raw_pair'].values()}, 'host-dependent intermediate is not the merged bitcode')
    for row in recipe['host_tools']:
        host_bound(row)
    return len(copies), len(recipe['inputs']) - len(copies)


def validate(a, private=False):
    require(a['format'] == 'lisp65-v254-public-build-authority-v1' and a['release'] == '2.5.4', 'release/format drift')
    require(a['product_build_id'] == '0x829db958', 'wrong product build ID')
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
    result = dict(status='PASS: 2.5.4 PUBLIC SOURCE AUTHORITY', inputs=len(rows), native_copies=copies,
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
    require(seal['status'] == 'PASS' and seal['format'] == 'card254-final-seal-v1' and
            seal['final']['artifacts'] == final['artifacts'], 'Final seal mismatch')
    pairs = {p['role']: p for p in final['artifacts']}
    for role, row in a['raw_pair'].items():
        require(pairs[role]['final'] == row and pairs[role]['byteidentical'] is True, 'Final pair drift: ' + role)
        bound(row)
    invocation = load(local(a['final_invocation']['path']))
    # The Final-host identity of the merged bitcode is the file the sealed Final wrote.
    q = recipe['host_qualification']['host_dependent_intermediate']
    require(identity(local(q['path']).read_bytes()) == q['final_host'], 'Final-host merged bitcode record drift')
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
                   lambda r: r['host_tools'][0].update(sha256=r['host_qualification']['final_host_tools'][0]['sha256']),
                   lambda r: r['host_qualification'].update(rule='the merged bitcode equals the Final'),
                   lambda r: r['repl_seam'].update(projected_sha256='0' * 64),
                   lambda r: next(x for x in r['inputs'] if x['materialized_path'].endswith(REPL_SUFFIX))['source'].update(sha256=REPL_FROZEN_SHA256),
                   lambda r: r['inputs'].pop(), lambda r: r['inputs'][0]['source'].update(sha256='0' * 64)):
        r = copy.deepcopy(recipe); mutate(r)
        try:
            validate_recipe(r, pinned)
        except (ValueError, StopIteration, IndexError):
            continue
        raise ValueError('recipe mutation survived')
    return dict(result, mutations_rejected=len(trials) + 8)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['check', 'selftest', 'private']); a = p.parse_args()
    print(json.dumps(selftest() if a.mode == 'selftest' else check(a.mode == 'private'), indent=2))
