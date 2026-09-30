#!/usr/bin/env python3
"""Record/check two independent public 2.5.2 reproductions against the exact r7c Final.

Successor of c2_v251_r2_20260929_reproduction_gate (immutable).

modes
  policy    exclusive creation of config/c2-v252-r1-reproduction-policy.json
            (producer tools, their directly imported helpers, all v252 configs,
            expected artifacts, pinned host tools); derived, never hand-written
  record    --roots A B: retain both reproduction outputs and write
            config/c2-v252-r1-reproductions.json (exclusive)
  check     policy freshness + full receipt validation (red until step 4 ran)
  selftest  synthetic receipt, no step-4 output needed: valid passes, every
            mutation is rejected
"""
import argparse
import ast
import copy
import json
from pathlib import Path
import shutil
import tempfile

import c2_v252_r1_public_native as N
import c2_v252_r1_public_normalization as Z

ROOT = N.ROOT
POLICY = ROOT / 'config/c2-v252-r1-reproduction-policy.json'
RECEIPT = ROOT / 'config/c2-v252-r1-reproductions.json'
OUT = 'build/public-v2.5.2'
# repro-r1-* and repro-r2-* hold copies from two stopped record attempts: the
# frozen-source check (single-path lookup against the two-path policy) and the
# toolchain lookup (receipt paths are relative to tools/llvm-mos).
RETAIN = 'build/release-v2.5.2/repro-r3-%d'
TOOLCHAIN = 'build/release-v2.5.2/reproduction-qualification-r1/toolchain.json'
PRODUCER_NAMES = ('product', 'native', 'source', 'normalization', 'reproduction', 'media', 'media_reproduction',
                  'libraries', 'plane', 'includes', 'overlays')
CONFIG_NAMES = ('replay', 'normalization', 'include-closure', 'plane', 'media-reproduction', 'export-policy',
                'build-authority', 'comfort-reemission')
FORMAT = 'lisp65-v252-two-public-reproductions-v1'
POLICY_FORMAT = 'lisp65-v252-reproduction-policy-v1'
ENVIRONMENT_KEYS = ('PYTHONHASHSEED', 'LC_ALL', 'TZ')
TOOLS = ROOT / 'tools/host-lisp'


def bind(p):
    p = Path(p)
    return dict(path=str(p.resolve().relative_to(ROOT)), **N.identity(p.read_bytes()))


def producers():
    return ['tools/host-lisp/c2_v252_r1_public_%s.py' % n for n in PRODUCER_NAMES]


def helpers():
    """Host modules imported directly (top level or lazily) by the 11 producer tools."""
    local = {p.stem for p in TOOLS.glob('*.py')}
    own = {Path(p).stem for p in producers()}
    found = set()
    for path in producers():
        for node in ast.walk(ast.parse((ROOT / path).read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split('.')[0]]
            found |= {n for n in names if n in local and n not in own}
    return ['tools/host-lisp/%s.py' % n for n in sorted(found)]


def configs():
    return ['config/c2-v252-r1-public-%s.json' % n for n in CONFIG_NAMES]


def expected():
    rows = N.load(N.AUTHORITY)['raw_pair']
    return {k: {f: v[f] for f in ('bytes', 'sha256')} for k, v in rows.items()}


def derive_policy():
    import c2_v252_r1_toolchain as T
    return dict(format=POLICY_FORMAT, release='2.5.2', commands=75, translation_units=73, product_links=1,
                producers=producers(), helpers=helpers(), configs=configs(),
                producer_bindings=[bind(ROOT / p) for p in producers() + helpers() + configs()],
                helper_scope='directly imported host modules of the 11 producer tools; the whole tools tree is '
                             'additionally covered by the export manifest',
                artifacts=expected(), product_build_id='0x8d22c8e6',
                host_tools=[dict(path=p, sha256=d) for p, d in sorted(T.HOST_TOOLS.items())],
                toolchain_format='lisp65-v252-toolchain-v2',
                environment_keys=list(ENVIRONMENT_KEYS),
                comfort_reemission=dict(blob_bytes=2095, package_bytes=3725),
                rule='Two fresh exported roots with distinct absolute paths and differing PYTHONHASHSEED/LC_ALL/TZ; '
                     'ELF/PRG/LTO/D81 must equal the Final and each other.')


def toolchain(v, policy):
    raw = N.bound(v['toolchain_manifest'])
    t = json.loads(raw)
    N.require(t['format'] == policy['toolchain_format'] and t['status'] == 'PASS' and t['files'],
              'toolchain receipt not passed')
    N.require([dict(path=r['path'], sha256=r['sha256']) for r in t['host_tools']] == policy['host_tools'],
              'host tool pins differ from the toolchain receipt')
    recipe = N.load(N.RECIPE)
    N.require([dict(path=r['path'], sha256=r['sha256']) for r in recipe['host_tools']] ==
              [r for r in policy['host_tools'] if r['path'] != '/usr/bin/cc'],
              'replay recipe host tools differ from the pins')
    # The toolchain receipt lists paths relative to tools/llvm-mos.
    files = {'tools/llvm-mos/' + r['path']: r for r in t['files']}
    used = [r for r in recipe['inputs'] if r['materialized_path'].startswith('tools/llvm-mos/')]
    for r in used:
        row = files.get(r['materialized_path'])
        N.require(row is not None and row['kind'] == 'file' and row['sha256'] == r['source']['sha256'],
                  'recipe toolchain input not in receipt: ' + r['materialized_path'])
    return len(files), len(used)


def validate(v, policy):
    N.require(v['status'] == 'PASS' and v['format'] == FORMAT and len(v['reproductions']) == 2,
              'two successful reproductions required')
    reps = v['reproductions']
    N.require(reps[0]['root'] != reps[1]['root'], 'independent absolute roots required')
    N.require(reps[0]['source_manifest']['sha256'] == reps[1]['source_manifest']['sha256'], 'source exports differ')
    for key in policy['environment_keys']:
        a, b = reps[0]['environment'].get(key), reps[1]['environment'].get(key)
        N.require(a is not None and b is not None and a != b, 'environment must differ between roots: ' + key)
    N.require({r['path'] for r in v['producer_bindings']} ==
              set(policy['producers'] + policy['helpers'] + policy['configs']), 'producer binding population drift')
    N.require(v['producer_bindings'] == policy['producer_bindings'], 'producer bindings differ from the policy')
    for row in v['producer_bindings']:
        N.bound(row)
    files, used = toolchain(v, policy)
    want = policy['artifacts']
    final_rows = N.load(N.AUTHORITY)['raw_pair']
    N.require(want == expected(), 'policy artifacts differ from the build authority')
    for r in reps:
        for k in ('source_manifest', 'commands', 'normalization', 'include_closure', 'media_receipt'):
            N.bound(r[k])
        N.require(r['commands_consumed'] == policy['commands'] and r['product_links'] == policy['product_links'],
                  'incomplete public replay')
        proof = json.loads(N.bound(r['normalization']))
        N.require(proof['byteidentical'] and proof['status'] == 'PASS' and proof['substitution'] == Z.policy(),
                  'normalization not proven')
        closure = json.loads(N.bound(r['include_closure']))
        N.require(closure['status'] == 'PASS' and closure['translation_units'] == policy['translation_units'] and
                  closure['equals_frozen_closure'], 'include closure incomplete')
        c = r['comfort_reemission']
        N.require(c['status'] == 'PASS: REPL-COMFORT RE-EMITTED FROM PUBLIC SOURCES' and
                  c['blob_bytes'] == policy['comfort_reemission']['blob_bytes'] and
                  c['package_bytes'] == policy['comfort_reemission']['package_bytes'], 'Comfort re-emission missing')
        N.require(set(r['artifacts']) == set(want), 'artifact population drift')
        for role, row in r['artifacts'].items():
            raw = N.bound(row)
            N.require(N.identity(raw) == want[role] and raw == N.bound(final_rows[role]), 'Final mismatch: ' + role)
    for role in want:
        N.require(N.bound(reps[0]['artifacts'][role]) == N.bound(reps[1]['artifacts'][role]),
                  'reproductions differ: ' + role)
    return dict(status='PASS', reproductions=2, artifacts=want, translation_units=policy['translation_units'],
                toolchain_files=files, toolchain_inputs_bound=used, normalization='identical repl preprocessor output',
                comfort_reemission='equal to the projected r6 package in both roots')


def write_exclusive(path, value):
    with path.open('xb') as f:
        f.write(N.canonical(value))


def record(roots):
    N.require(not RECEIPT.exists(), 'receipt exists; explicit successor required')
    policy = N.load(POLICY)
    N.require(policy == derive_policy(), 'policy stale; a producer or config changed since the policy was recorded')
    reps = []
    for i, root in enumerate(roots, 1):
        root = root.resolve()
        N.require(root != ROOT and not root.is_relative_to(ROOT), 'scratch root must be outside repository')
        out = root / OUT
        state = json.loads((out / 'reproduction.json').read_text())
        N.require(state['status'] == 'PASS: PUBLIC SOURCE NATIVE AND MEDIA BYTEIDENTICAL', 'nonqualifying build')
        dest = ROOT / (RETAIN % i)
        N.require(not dest.exists(), 'retained run exists')
        shutil.copytree(out, dest / 'public-result')
        shutil.copyfile(root / 'PUBLIC-SOURCE-MANIFEST.json', dest / 'PUBLIC-SOURCE-MANIFEST.json')
        artifacts = {}
        for role, row in {**state['native'], 'D81': state['media']}.items():
            source = root / row['path']
            N.require(N.identity(source.read_bytes()) == policy['artifacts'][role], 'reproduced artifact differs')
            target = dest / (role + source.suffix)
            shutil.copyfile(source, target)
            artifacts[role] = bind(target)
        manifest = json.loads((root / 'PUBLIC-SOURCE-MANIFEST.json').read_text())
        exported = {r['path']: r for r in manifest['files']}
        for row in policy['producer_bindings']:
            N.require(row['path'] in exported and N.identity((ROOT / row['path']).read_bytes()) ==
                      {k: exported[row['path']][k] for k in ('bytes', 'sha256')},
                      'producer changed since export: ' + row['path'])
        reps.append(dict(root=str(root), environment=state['environment'], commands_consumed=state['commands_consumed'],
                         product_links=state['product_links'], comfort_reemission=state['comfort_reemission'],
                         artifacts=artifacts, source_manifest=bind(dest / 'PUBLIC-SOURCE-MANIFEST.json'),
                         commands=bind(dest / 'public-result/commands.jsonl'),
                         normalization=bind(dest / 'public-result/normalization-proof.json'),
                         include_closure=bind(dest / 'public-result/include-closure.json'),
                         media_receipt=bind(dest / 'public-result/media/receipt.json')))
    result = dict(status='PASS', format=FORMAT, reproductions=reps, producer_bindings=policy['producer_bindings'],
                  toolchain_manifest=bind(ROOT / TOOLCHAIN))
    for path in Z.policy()['paths']:
        N.require(N.identity((ROOT / path).read_bytes()) == Z.policy()['before'], 'frozen source changed: ' + path)
    validate(result, policy)
    write_exclusive(RECEIPT, result)
    return validate(result, policy)


MUTATIONS = (
    ('one reproduction', lambda a: a['reproductions'].pop()),
    ('same root', lambda a: a['reproductions'][1].update(root=a['reproductions'][0]['root'])),
    ('ELF bytes', lambda a: a['reproductions'][0]['artifacts']['ELF'].update(sha256='0' * 64)),
    ('D81 bytes', lambda a: a['reproductions'][1]['artifacts']['D81'].update(sha256='0' * 64)),
    ('commands', lambda a: a['reproductions'][0].update(commands_consumed=74)),
    ('product links', lambda a: a['reproductions'][0].update(product_links=2)),
    ('same hash seed', lambda a: a['reproductions'][1]['environment'].update(
        PYTHONHASHSEED=a['reproductions'][0]['environment']['PYTHONHASHSEED'])),
    ('unset time zone', lambda a: a['reproductions'][1]['environment'].update(TZ=None)),
    ('producer omitted', lambda a: a['producer_bindings'].pop()),
    ('producer hash', lambda a: a['producer_bindings'][0].update(sha256='0' * 64)),
    ('comfort missing', lambda a: a['reproductions'][0].update(
        comfort_reemission=dict(a['reproductions'][0]['comfort_reemission'], package_bytes=1))),
    ('toolchain binding', lambda a: a['toolchain_manifest'].update(sha256='0' * 64)),
)


def selftest():
    policy = derive_policy()
    final = N.load(N.AUTHORITY)['raw_pair']
    base = Path(tempfile.mkdtemp(dir=ROOT / 'build', prefix='v252-reproduction-gate-selftest-'))
    try:
        import c2_v252_r1_toolchain as T
        recipe = N.load(N.RECIPE)
        files = [dict(path=r['materialized_path'][len('tools/llvm-mos/'):], kind='file', bytes=r['source']['bytes'],
                      sha256=r['source']['sha256'], mode=493)
                 for r in recipe['inputs'] if r['materialized_path'].startswith('tools/llvm-mos/')]
        tool = base / 'toolchain.json'
        tool.write_bytes(N.canonical(dict(format=policy['toolchain_format'], status='PASS', files=files,
                                          host_tools=T.host_tools())))
        rel = lambda p: str(p.relative_to(ROOT))
        reps = []
        for i in (1, 2):
            d = base / str(i)
            d.mkdir()
            rows = {}
            for name, body in (('source', b'{}'), ('commands', b'{}'), ('media_receipt', b'{}'),
                               ('normalization', N.canonical(dict(status='PASS', byteidentical=True,
                                                                   substitution=Z.policy()))),
                               ('closure', N.canonical(dict(status='PASS', translation_units=73,
                                                            equals_frozen_closure=True)))):
                (d / name).write_bytes(body)
                rows[name] = bind(d / name)
            same = {k: v for k, v in rows.items()}
            same['source'] = bind(base / '1/source') if i == 2 else rows['source']
            reps.append(dict(root='/synthetic/root-%d' % i,
                             environment=dict(PYTHONHASHSEED=str(i), LC_ALL='C' if i == 1 else 'C.UTF-8',
                                              TZ='UTC' if i == 1 else 'Europe/Busingen'),
                             commands_consumed=75, product_links=1,
                             comfort_reemission=dict(status='PASS: REPL-COMFORT RE-EMITTED FROM PUBLIC SOURCES',
                                                     blob_bytes=2095, package_bytes=3725),
                             artifacts={role: dict(row) for role, row in final.items()},
                             source_manifest=same['source'], commands=rows['commands'],
                             normalization=rows['normalization'], include_closure=rows['closure'],
                             media_receipt=rows['media_receipt']))
        valid = dict(status='PASS', format=FORMAT, reproductions=reps, producer_bindings=policy['producer_bindings'],
                     toolchain_manifest=bind(tool))
        validate(valid, policy)
        rejected = []
        for name, mutate in MUTATIONS:
            trial = copy.deepcopy(valid)
            mutate(trial)
            try:
                validate(trial, policy)
            except (ValueError, KeyError, IndexError):
                rejected.append(name)
            else:
                raise AssertionError('reproduction mutation survived: ' + name)
        bad_policy = copy.deepcopy(policy)
        bad_policy['helpers'] = bad_policy['helpers'][1:]
        try:
            validate(valid, bad_policy)
        except (ValueError, KeyError, IndexError):
            rejected.append('policy population')
        else:
            raise AssertionError('policy mutation survived')
        return dict(status='PASS', mutations_rejected=len(rejected), producers=len(policy['producers']),
                    helpers=len(policy['helpers']), configs=len(policy['configs']))
    finally:
        shutil.rmtree(base)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['policy', 'record', 'check', 'selftest'])
    p.add_argument('--roots', nargs=2, type=Path)
    a = p.parse_args()
    if a.mode == 'selftest':
        result = selftest()
    elif a.mode == 'policy':
        write_exclusive(POLICY, derive_policy())
        result = dict(status='PASS', policy=str(POLICY.relative_to(ROOT)))
    elif a.mode == 'record':
        N.require(a.roots is not None, 'two roots required')
        result = record(a.roots)
    else:
        pol = N.load(POLICY)
        N.require(pol == derive_policy(), 'reproduction policy stale')
        result = validate(N.load(RECEIPT), pol)
    print(json.dumps(result, indent=2))
