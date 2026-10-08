#!/usr/bin/env python3
"""2.5.5 public Final r1 replay; no private build or evidence inputs.

Runs only in a fresh exported public root (no build/ directory). It
materializes the 235 frozen native inputs, proves the one comment
normalization token-neutral, re-derives every compiler dependency, executes
the 75 frozen commands (73 compiles, llvm-link, ONE product link) and requires
the Final ELF/PRG/LTO bytes; then the standalone media packer must produce
the Final D81 byte for byte.
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

import c2_v255_r1_public_native as N
import c2_v255_r1_public_normalization as Z

ROOT = N.ROOT
OUT = ROOT / 'build/public-v2.5.5'
STATUS = 'PASS: PUBLIC SOURCE NATIVE AND MEDIA BYTEIDENTICAL'


def save(path, value):
    Path(path).write_bytes(N.canonical(value))


def environment(recipe):
    env = dict(recipe['environment'], PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(OUT / 'tmp'))
    return env


def run(cmd, env):
    r = subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    N.require(r.returncode == 0, 'command failed: ' + shlex.join(cmd) + '\n' + r.stdout.decode(errors='replace'))
    return r.stdout


def materialize(recipe):
    for path in recipe['absent_paths']:
        N.require(not N.local(path).exists(), 'recipe-absent include path exists: ' + path)
    for row in recipe['inputs']:
        raw = N.bound(row['source'])
        if row['materialized_path'].startswith('tools/llvm-mos/'):
            N.require(N.local(row['materialized_path']).read_bytes() == raw, 'toolchain input drift')
            continue
        if row['source']['path'] in Z.policy()['paths']:
            raw = Z.normalize(raw)
        target = N.local(row['materialized_path'])
        N.require(not target.exists(), 'replay destination exists: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for path in recipe['absent_paths']:
        N.require(not N.local(path).exists(), 'materialization created a recipe-absent path: ' + path)


def preprocess_command(command):
    cmd = list(command)
    at = cmd.index('-o')
    del cmd[at:at + 2]
    cmd.remove('-c')
    return cmd


def include_check(recipe, env):
    allowed = {}
    for r in recipe['inputs']:
        p = N.local(r['materialized_path'])
        allowed[str(p.resolve())] = N.identity(p.read_bytes())
    rows = []
    for c in recipe['commands'][:73]:
        src = c[c.index('-c') + 1]
        if src.endswith('.s'):
            dirs = [ROOT] + [N.local(c[j + 1]) for j, x in enumerate(c) if x == '-I']
            pending, deps = [N.local(src)], set()
            while pending:
                p = pending.pop().resolve()
                if str(p) in deps:
                    continue
                deps.add(str(p))
                for name in re.findall(r'^\s*\.include\s+"([^"]+)"', p.read_text(), re.M):
                    found = next((d / name for d in dirs if (d / name).is_file()), None)
                    N.require(found is not None, 'assembler include absent: ' + name)
                    pending.append(found)
        else:
            output = run(preprocess_command(c) + ['-E', '-M', '-MT', 'public-input'], env)
            deps = {str((ROOT / p).resolve()) for p in
                    shlex.split(output.decode().replace('\\\n', ' ').split(':', 1)[1])}
        for p in deps:
            N.require(p in allowed, 'unbound compiler dependency: ' + p)
            N.require(N.identity(Path(p).read_bytes()) == allowed[p], 'compiler input drift: ' + p)
        rows.append(dict(source=src, dependencies=sorted(str(Path(p).relative_to(ROOT)) for p in deps)))
    frozen = N.load(N.ROOT / ('config/%s-include-closure.json' % N.PREFIX))['rows']
    N.require(rows == frozen, 'fresh include closure differs from the frozen 2.5.5 Final closure')
    result = dict(status='PASS', translation_units=len(rows), rows=rows, equals_frozen_closure=True)
    save(OUT / 'include-closure.json', result)
    return result


def normalization_proof(recipe, env):
    """Preprocess one consuming TU with normalized and original comment bytes."""
    p = Z.policy()
    targets = [N.local(r['materialized_path']) for r in recipe['inputs'] if r['source']['path'] in p['paths']]
    N.require(len(targets) == len(p['paths']), 'normalized compiler input absent')
    closure = N.load(N.ROOT / ('config/%s-include-closure.json' % N.PREFIX))
    wanted = {str(t.relative_to(ROOT)) for t in targets}
    index = next(i for i, row in enumerate(closure['rows']) if wanted & set(row['dependencies']))
    command = preprocess_command(recipe['commands'][index]) + ['-E', '-P']
    normalized = run(command, env)
    saved = {t: t.read_bytes() for t in targets}
    try:
        for t, raw in saved.items():
            t.write_bytes(Z.denormalize(raw, p))
        original = run(command, env)
    finally:
        for t, raw in saved.items():
            t.write_bytes(raw)
    N.require(original == normalized, 'normalization changes preprocessor tokens')
    result = dict(status='PASS', substitution=p, command=command, preprocessed=N.identity(normalized),
                  byteidentical=True, targets=sorted(wanted))
    save(OUT / 'normalization-proof.json', result)
    return result


def build():
    N.require(not (ROOT / 'build').exists(), 'public reproduction requires no build directory')
    N.require((ROOT / 'PUBLIC-SOURCE-MANIFEST.json').is_file(), 'exported public source required')
    OUT.mkdir(parents=True)
    (OUT / 'tmp').mkdir()

    def audit(event, args):
        if event == 'subprocess.Popen':
            with (OUT / 'commands.jsonl').open('a') as f:
                f.write(json.dumps(dict(executable=str(args[0]), argv=[str(x) for x in args[1]],
                                        cwd=str(args[2] or Path.cwd()))) + '\n')
    sys.addaudithook(audit)
    state = dict(status='STARTED', source_manifest=N.identity((ROOT / 'PUBLIC-SOURCE-MANIFEST.json').read_bytes()),
                 environment={k: os.environ.get(k) for k in ('PYTHONHASHSEED', 'LC_ALL', 'TZ')},
                 commands_consumed=0, product_links=0)
    try:
        state['authority'] = N.check()
        import c2_v255_r1_public_plane as plane
        import c2_v255_r1_public_includes as includes
        state['plane'] = plane.check()
        state['includes_authority'] = includes.check()
        import c2_v255_r1_public_libraries as libraries
        state['comfort_reemission'] = libraries.comfort_reemission(int(state['plane']['product_build_id'], 16))
        state['defstruct_reemission'] = libraries.defstruct_reemission(int(state['plane']['product_build_id'], 16))
        recipe = N.load(N.RECIPE)
        env = environment(recipe)
        state['native_environment'] = env
        materialize(recipe)
        state['normalization'] = normalization_proof(recipe, env)
        state['include_closure'] = dict(translation_units=include_check(recipe, env)['translation_units'])
        for i, cmd in enumerate(recipe['commands']):
            N.local(cmd[cmd.index('-o') + 1]).parent.mkdir(parents=True, exist_ok=True)
            if i == 74:
                state['product_links'] = 1
            (OUT / f'command-{i:03d}.log').write_bytes(run(cmd, env))
            state['commands_consumed'] = i + 1
            if i == 73:
                # Intermediate (merged bitcode of /usr/bin/llvm-link), not an artifact: recorded here; the Final's
                # value (same host in 2.5.5) is in the recipe's host_qualification record.  Equality with it is
                # recorded by the reproduction gate and is not a pass condition.
                merged = N.local(cmd[cmd.index('-o') + 1])
                state['host_dependent_intermediate'] = dict(
                    path=str(merged.relative_to(ROOT)), **N.identity(merged.read_bytes()),
                    final_host=recipe['host_qualification']['host_dependent_intermediate']['final_host'],
                    host_tools=recipe['host_tools'])
        wplto = ROOT / N.FINAL_DIR / 'wplto'
        paths = {'ELF': wplto / 'resident-island-seed.prg.elf', 'PRG': wplto / 'resident-island-seed.prg',
                 'LTO': wplto / 'resident-island-seed.prg.lto.o'}
        state['native'] = {}
        for role, p in paths.items():
            got = N.identity(p.read_bytes())
            N.require(got == {k: recipe['raw_pair'][role][k] for k in ('bytes', 'sha256')}, 'HALT native mismatch: ' + role)
            state['native'][role] = dict(path=str(p.relative_to(ROOT)), **got)
        save(OUT / 'reproduction.json', state)
        import c2_v255_r1_public_media_reproduction as MR
        media = MR.pack(paths['ELF'], paths['PRG'], OUT / 'media')
        N.require(media['status'] == 'PASS: PUBLIC MEDIA BYTEIDENTICAL', 'media not reproduced')
        state['media'] = media['medium']
        state['media_receipt'] = MR.bind(OUT / 'media/receipt.json')
        state['status'] = STATUS
    except BaseException as error:
        state.update(status='HALT', error=str(error))
        raise
    finally:
        save(OUT / 'reproduction.json', state)
    return state


def check():
    state = N.load(OUT / 'reproduction.json')
    N.require(state['status'] == STATUS and state['commands_consumed'] == 75 and state['product_links'] == 1,
              'reproduction not passed')
    for r in [*state['native'].values(), state['media'], state['media_receipt']]:
        N.bound(r)
    N.require(state['media']['sha256'] == N.FINAL_SHA['D81'], 'wrong reproduced D81')
    return state


if __name__ == '__main__':
    print(json.dumps(build() if sys.argv[1:] == ['build'] else check(), indent=2, default=str))
