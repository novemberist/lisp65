#!/usr/bin/env python3
"""Card L isolated Final; native-card Seed/Final identity admission lineage.

--preflight is read-only. --allow-pending permits only missing source/Final
receipts and reports dirty-tree admission as pending. `final` never tolerates
these conditions. No medium is rebuilt. Commands are the Seed's exact command
list with only its output root rebound, as in the native Final drivers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / 'build/card-l-product-r1'
OUT = ROOT / 'build/card-l-final-r1'
SOURCE = 'build/card-l-check-source-r3/receipt.json'
STEM = 'card-l-final-20260925'
MANIFEST = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks' / (STEM + '.json')
ELF = '7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
MEDIUM = 'build/card-l-seed-medium-r2/media-seed/card-l.d81'
MEDIA_SHA = 'ac05fdea6e6fb00b2e10b31c2ac30a3bd5d7530908a88c0aaa388cf62a0c1cc7'
MEMBERS = ['resident-island-seed.prg', 'resident-island-seed.prg.elf', 'resident-island-seed.prg.lto.o']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def load(path):
    return json.loads((ROOT / path).read_text())


def bind(path):
    path = (ROOT / path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def verify(row):
    actual = bind(row['path'])
    require(actual['sha256'] == row['sha256'], 'hash mismatch: ' + row['path'])
    require('bytes' not in row or actual['bytes'] == row['bytes'], 'size mismatch: ' + row['path'])
    return actual


def write_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def source_binding(pending):
    if not (ROOT / SOURCE).exists():
        pending.append(SOURCE)
        return None
    value = load(SOURCE)
    require(value['exit_code'] == 0, 'sealed source exit is not zero')
    require(value['head_before'] == value['head_after'] == git('rev-parse', 'HEAD'), 'sealed source HEAD mismatch')
    require(value['target'] == 'make -k check-source', 'sealed source target mismatch')
    require(value['changed_protected_files'] == 0 and not value['changed_files']
            and not value['changed_sealed_artifacts'], 'sealed source changed protected inputs')
    verify(value['log'])
    return value


def preflight(allow_pending=False, need_final=True):
    manifest = load(MANIFEST)
    require(not manifest.get('unavailable_references'), 'unresolved historical receipt references')
    for resolution in manifest.get('historical_resolutions', []):
        require(verify(resolution['preserved'])['sha256'] == resolution['recorded']['sha256'], 'historical identity mismatch')
    for row in manifest['inputs']:
        verify(row)
    for short, full in manifest['authority_commits'].items():
        require(git('rev-parse', short + '^{commit}') == full, 'authority drift: ' + short)
        subprocess.run(['git', 'merge-base', '--is-ancestor', full, 'HEAD'], cwd=ROOT, check=True)
    import card_l_producer as producer
    producer.require_auth()
    pending = []
    dirty = git('status', '--porcelain', '--untracked-files=all')
    if dirty:
        pending.append('clean working tree (tracked changes and untracked files must be resolved)')
    source_binding(pending)
    require(bind(SEED / 'wplto' / MEMBERS[1])['sha256'] == ELF, 'Seed ELF mismatch')
    require(bind(MEDIUM)['sha256'] == MEDIA_SHA, 'r2 medium mismatch')
    commands = load(SEED / 'commands.json')
    require(sum('-c' not in c for c in commands) == 2, 'Seed command shape mismatch')
    require(Path(commands[-2][0]).name == 'llvm-link', 'missing LTO command')
    for command in commands:
        require('-o' in command, 'command has no output')
        output = (ROOT / command[command.index('-o') + 1]).resolve()
        require(output.is_relative_to(SEED), 'command output escapes Seed root')
        require(Path(command[0]).is_file(), 'tool missing: ' + command[0])
    receipt = OUT / 'final-identity.json'
    if need_final and not receipt.exists():
        pending.append(str(receipt.relative_to(ROOT)))
    elif receipt.exists():
        value = load(receipt)
        require(value['status'] == 'PASS' and value['head'] == git('rev-parse', 'HEAD'), 'Final status/HEAD mismatch')
        require(value['budget'] == dict(seed_rebuilds=0, final=1, link=1), 'Final budget mismatch')
        verify(value['source']); verify(value['medium']); verify(value['command_consumption'])
        consumed = load(OUT/'final-command-consumption.json')
        expected = [[a.replace(str(SEED.relative_to(ROOT)), str(OUT.relative_to(ROOT))) for a in c] for c in commands]
        require(consumed['status'] == 'PASS' and consumed['commands'] == expected
                and consumed['commands_consumed'] == len(expected)
                and consumed['seed_commands'] == bind(SEED/'commands.json'), 'Final command consumption mismatch')
        invocation = load(OUT/'final-invocation.json')
        require(invocation['head'] == value['head'] and invocation['commands'] == expected
                and invocation['source'] == bind(SOURCE), 'Final invocation mismatch')
        require(value['source'] == bind(SOURCE) and value['medium'] == bind(MEDIUM), 'Final binding mismatch')
        for name, old, new in zip(MEMBERS, value['seed'], value['final'], strict=True):
            require(old == bind(SEED/'wplto'/name) and new == bind(OUT/'wplto'/name), 'Final member mismatch')
            require(old['sha256'] == new['sha256'], 'Final identity differs: ' + name)
    require(allow_pending or not pending, 'pending bindings: ' + '; '.join(pending))
    return dict(status='PENDING' if pending else 'PASS', bindings=len(manifest['inputs']), pending=pending)


def final():
    preflight(need_final=False)
    require(not OUT.exists(), 'Final directory exists; no implicit retry')
    head = git('rev-parse', 'HEAD')
    OUT.mkdir()
    old, new = str(SEED.relative_to(ROOT)), str(OUT.relative_to(ROOT))
    commands = [[arg.replace(old, new) for arg in command] for command in load(SEED/'commands.json')]
    write_once(OUT/'final-invocation.json', dict(head=head, source=bind(SOURCE), commands=commands,
               seed_commands=bind(SEED/'commands.json'), budget=dict(seed_rebuilds=0, final=1, link=1)))
    # Reuse only the frozen consumed source/header/linker population, never objects.
    shutil.copytree(SEED/'wplto', OUT/'wplto',
                    ignore=shutil.ignore_patterns('*.o', '*.elf', '*.prg', '*.map', '*.json', '*.txt'))
    for index, command in enumerate(commands):
        (ROOT/command[command.index('-o')+1]).parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env={**os.environ, 'TMPDIR': str(ROOT/'build/card-l-r1/tmp')})
        (OUT/f'command-{index:03d}.log').write_bytes(result.stdout)
        require(result.returncode == 0, f'Final stopped at command {index}; no retry')
    consumed = OUT/'final-command-consumption.json'
    write_once(consumed, dict(status='PASS', commands_consumed=len(commands), commands=commands,
                             seed_commands=bind(SEED/'commands.json')))
    seed, linked = [], []
    for name in MEMBERS:
        a, b = SEED/'wplto'/name, OUT/'wplto'/name
        require(a.read_bytes() == b.read_bytes(), 'Final is not byte-identical: ' + name)
        seed.append(bind(a)); linked.append(bind(b))
    preflight(need_final=False)  # Check immutable inputs, source HEAD, and clean tree again.
    require(git('rev-parse', 'HEAD') == head, 'HEAD changed during Final')
    write_once(OUT/'final-identity.json', dict(status='PASS', head=head, source=bind(SOURCE),
        seed=seed, final=linked, ELF_byteidentical=True, medium=bind(MEDIUM), medium_adoption='identity; no repack',
        command_consumption=bind(consumed), budget=dict(seed_rebuilds=0, final=1, link=1)))
    print('PASS: Card L Final PRG, ELF and LTO byte-identical; r2 medium adopted without repack')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['final'])
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--allow-pending', action='store_true')
    args = parser.parse_args()
    require(args.preflight != (args.mode == 'final'), 'choose --preflight or final')
    if args.preflight:
        print(json.dumps(preflight(args.allow_pending), indent=2))
    else:
        require(not args.allow_pending, 'final cannot allow pending bindings')
        final()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: ' + str(error))
