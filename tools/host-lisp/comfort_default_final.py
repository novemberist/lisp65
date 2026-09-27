#!/usr/bin/env python3
"""Comfort default: budget-free probe or one write-once Final (Card L lineage).

A sealed-run directory must contain receipt.json in the Card L check-source
format. Probe only reads files and Git metadata. Selftest uses private copies,
never product commands. Final failures retain the output directory: no retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
SEED = Path('build/comfort-default-r2/seed')
PRODUCT = Path('build/comfort-default-product-r2')
OUT = Path('build/comfort-default-final-r1')
BINDINGS = Path('tools/host-lisp/comfort_default_final_inputs.json')
BINDINGS_SHA = 'aff5ff3eec08f8cd15166e2b12e2d4a5d2c96cde7abfad9e250ca711c602681d'
ELF_SHA = 'd555f01fbac51bb5fbc035b2b595e95e3c8e3bedc584c87112bca8b073e31444'
BUDGET = dict(seed_rebuilds=0, final=1, link=1)
ADMISSIONS = [
    'Final output directory absent (no implicit retry)',
    'sealed check-source exit zero, zero protected changes, exact current HEAD',
    'sealed log hash and receipt bound',
    'tracked working tree and index clean',
    'all 201 frozen bindings intact, including snapshot inputs and linker-comfort',
    'committed repl.c and linker files equal their Seed bindings',
    'Seed seed.json, d555f01f ELF, PRG and optional LTO bound',
    '75 frozen Seed commands; outputs rebased only to Final wplto',
    'media builder, inventory, explicit media inputs and all three Seed D81s bound',
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


class Driver:
    def __init__(self, root=ROOT):
        self.root = root

    def load(self, path):
        return json.loads((self.root / path).read_text())

    def bind(self, path):
        path = (self.root / path).resolve()
        raw = path.read_bytes()
        return dict(path=str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path),
                    bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def verify(self, row):
        actual = self.bind(row['path'])
        require(actual['sha256'] == row['sha256'] and
                ('bytes' not in row or actual['bytes'] == row['bytes']),
                'hash/size mismatch: ' + row['path'])
        return actual

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root,
                                       env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True).strip()

    def admit(self, sealed_run, *, claimed=False):
        require(claimed or not os.path.lexists(self.root / OUT), 'Final directory exists; no implicit retry')
        head = self.git('rev-parse', 'HEAD')
        require(not self.git('status', '--porcelain', '--untracked-files=no'), 'tracked tree dirty')
        receipt_path = sealed_run / 'receipt.json'
        receipt = self.load(receipt_path)
        require(receipt['target'] == 'make -k check-source', 'sealed target mismatch')
        require(receipt['exit_code'] == 0, 'sealed source exit is not zero')
        require(receipt['head_before'] == receipt['head_after'] == head, 'sealed HEAD mismatch')
        require(receipt['changed_protected_files'] == 0 and receipt['changed_files'] == []
                and receipt['changed_sealed_artifacts'] == [], 'sealed protected changes')
        log = self.verify(receipt['log'])
        require((self.root / log['path']).resolve().is_relative_to((self.root / sealed_run).resolve()),
                'sealed log outside run')
        require(self.bind(BINDINGS)['sha256'] == BINDINGS_SHA, 'frozen bindings drift')
        rows = self.load(BINDINGS)['inputs']
        for row in rows:
            self.verify(row)
        expected = {r['path'] for r in rows}
        for directory in (SEED / 'inputs', SEED / 'linker-comfort'):
            actual = {str(p.relative_to(self.root)) for p in (self.root / directory).rglob('*') if p.is_file()}
            require(actual == {p for p in expected if p.startswith(str(directory) + '/')},
                    'snapshot population drift: ' + str(directory))
        ready = self.load(SEED / 'command-ready.json')
        require(self.bind(SEED / 'repl.c')['sha256'] == ready['source']['sha256'], 'Seed repl mismatch')
        self.verify(ready['source'])
        for row in self.load('config/comfort-default-native/manifest.json')['linker']:
            self.verify(row)
            relative = Path(row['path']).relative_to('config/comfort-default-native/linker')
            require(self.bind(SEED / 'linker-comfort' / relative)['sha256'] == row['sha256'], 'linker mismatch')
        seed = self.load(PRODUCT / 'seed.json')
        require(seed['commands_consumed'] == 75 and seed['ELF']['sha256'] == ELF_SHA, 'Seed receipt mismatch')
        self.verify(seed['ELF'])
        proof = self.load(SEED / 'command-proof.json')
        for row in proof['authority']:
            self.verify(row)
        commands = proof['commands']
        require(len(commands) == 75 and all('-c' in c for c in commands[:73])
                and Path(commands[73][0]).name == 'llvm-link' and '-c' not in commands[74],
                'Seed command shape mismatch')
        old, new = str(PRODUCT / 'wplto'), str(OUT / 'wplto')
        rebased = [[a.replace(old + '/', new + '/') for a in c] for c in commands]
        for command in rebased:
            require('-o' in command, 'missing output')
            require((self.root / command[command.index('-o') + 1]).resolve().is_relative_to(self.root / OUT / 'wplto'),
                    'output outside Final')
            require(Path(command[0]).is_file(), 'missing tool: ' + command[0])
        members = [r for r in rows if r['path'].startswith(old + '/resident-island-seed.prg')]
        media = [r for r in rows if r['path'].endswith('.d81')]
        require(len(media) == 3, 'expected three Seed D81s')
        return dict(status='PASS', head=head, sealed_run=str(sealed_run), source=self.bind(receipt_path),
                    source_log=log, seed_receipt=self.bind(PRODUCT / 'seed.json'),
                    seed_commands=self.bind(SEED / 'command-proof.json'), input_bindings=self.bind(BINDINGS),
                    commands=rebased, seed=members, seed_media=media, admissions=ADMISSIONS)

    def probe(self, sealed_run):
        result = self.admit(sealed_run)
        return dict(status=result['status'], head=result['head'], admissions=ADMISSIONS,
                    commands=len(result['commands']), budget=dict(seed_rebuilds=0, final=0, link=0))

    def media(self):
        # The existing builder has fixed global paths, not an ELF CLI option.
        # Project only the inventory's identical ELF binding into the Final.
        import comfort_default_media as media
        media.ELF = self.root / OUT / 'wplto/resident-island-seed.prg.elf'
        media.OUT = self.root / OUT / 'media-inputs'
        media.OUT.mkdir()
        inventory = self.load(SEED / 'inventory.json')
        inventory['ELFs'][1] = self.bind(media.ELF)
        save(media.OUT / 'inventory.json', inventory)
        media.MED = self.root / OUT / 'media'
        media.ART = media.MED / 'artifacts'
        for name, expected in media.INPUT_SHA256.items():
            require(self.bind(name)['sha256'] == expected, 'media input drift: ' + name)
        media.prepare()
        media.stager()
        media.pack()

    def final(self, sealed_run):
        admission = self.admit(sealed_run)
        output = self.root / OUT
        output.mkdir()  # Atomic attempt claim before any product command.
        identity = dict(status='FAIL', head=admission['head'], source=admission['source'],
                        sealed_run=admission['sealed_run'], budget=BUDGET, artifacts=[], media=[])
        try:
            save(output / 'final-invocation.json', dict(admission, budget=BUDGET,
                 driver=self.bind(Path(__file__).resolve()), media_builder=self.bind('tools/host-lisp/comfort_default_media.py')))
            for index, command in enumerate(admission['commands']):
                (self.root / command[command.index('-o') + 1]).parent.mkdir(parents=True, exist_ok=True)
                with (output / f'command-{index:03d}.log').open('wb') as log:
                    result = subprocess.run(command, cwd=self.root, stdout=log, stderr=subprocess.STDOUT)
                require(result.returncode == 0, f'command {index} exit {result.returncode}; no retry')
                identity['commands_consumed'] = index + 1
            for seed in admission['seed']:
                final = self.bind(OUT / 'wplto' / Path(seed['path']).name)
                equal = (self.root / seed['path']).read_bytes() == (self.root / final['path']).read_bytes()
                identity['artifacts'].append(dict(seed=seed, final=final, byteidentical=equal))
                require(equal, 'Final identity mismatch: ' + seed['path'])
            self.media()
            for seed in admission['seed_media']:
                relative = Path(seed['path']).relative_to(SEED / 'media-r2')
                final = self.bind(OUT / 'media' / relative)
                equal = (self.root / seed['path']).read_bytes() == (self.root / final['path']).read_bytes()
                identity['media'].append(dict(seed=seed, final=final, byteidentical=equal))
                require(equal, 'Final D81 mismatch: ' + str(relative))
            require(self.admit(sealed_run, claimed=True) == admission, 'admissions changed during Final')
            identity['status'] = 'PASS'
        except BaseException as error:
            identity['error'] = str(error)
            raise
        finally:
            save(output / 'final-identity.json', identity)
        return identity


def _selftest_fixture():
    # Copy, never mutate, actual Seed inputs. Git is the only substituted reader.
    real = Driver()
    with tempfile.TemporaryDirectory(prefix='comfort-final-selftest-') as temp:
        root = Path(temp)
        for row in real.load(BINDINGS)['inputs'] + [real.bind(BINDINGS)]:
            target = root / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['path'], target)
        driver = Driver(root)
        head = '1' * 40
        driver.git = lambda *args: head if args == ('rev-parse', 'HEAD') else ''
        sealed = Path('fake-sealed-run')
        (root / sealed).mkdir()
        (root / sealed / 'check-source.log').write_text('FAKE SELFTEST ONLY\n')
        receipt = dict(target='make -k check-source', exit_code=0, head_before=head, head_after=head,
                       changed_protected_files=0, changed_files=[], changed_sealed_artifacts=[],
                       log=driver.bind(sealed / 'check-source.log'))
        def reset():
            (root / sealed / 'receipt.json').write_text(json.dumps(receipt))
        reset()
        require(driver.probe(sealed)['status'] == 'PASS', 'positive probe failed')
        require(not (root / OUT).exists(), 'positive probe created output')
        admitted = driver.admit(sealed)
        originals = driver.load(SEED / 'command-proof.json')['commands']
        for old, new in zip(originals, admitted['commands'], strict=True):
            require(old == [a.replace(str(OUT / 'wplto') + '/', str(PRODUCT / 'wplto') + '/')
                            for a in new], 'rebase changed a Seed input or flag')
        passed = ['positive fake-sealed probe']
        def rejected(label, expected):
            try:
                driver.probe(sealed)
            except ValueError as error:
                require(expected in str(error), label + ': wrong rejection: ' + str(error))
                passed.append(label)
            else:
                raise ValueError(label + ': mutation accepted')
        for label, changes, reason in [
            ('wrong sealed HEAD', dict(head_after='2' * 40), 'HEAD mismatch'),
            ('red receipt', dict(exit_code=1), 'exit is not zero'),
            ('protected change', dict(changed_protected_files=1), 'protected changes'),
        ]:
            (root / sealed / 'receipt.json').write_text(json.dumps(dict(receipt, **changes)))
            rejected(label, reason)
            reset()
        path = root / real.load(SEED / 'command-proof.json')['authority'][0]['path']
        original = path.read_bytes()
        path.write_bytes(original + b'drift')
        rejected('drifted input', 'hash/size mismatch')
        path.write_bytes(original)
        driver.git = lambda *args: head if args == ('rev-parse', 'HEAD') else ' M tracked.c'
        rejected('dirty tracked tree', 'tracked tree dirty')
        driver.git = lambda *args: head if args == ('rev-parse', 'HEAD') else ''
        (root / OUT).mkdir()
        rejected('existing output dir', 'Final directory exists')
        require(not list((root / OUT).iterdir()), 'probe wrote output')
        return dict(status='PASS', tests=passed, product_commands=0, final_links=0,
                    fixture='private temporary copies; fake sealed receipt; mocked Git')


def selftest():
    from unittest.mock import patch
    # Any accidental command execution in probe fails even in a synthetic tree.
    with patch.object(subprocess, 'run', side_effect=AssertionError('selftest ran a command')), \
         patch.object(subprocess, 'check_output', side_effect=AssertionError('selftest ran a command')):
        return _selftest_fixture()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['probe', 'final'])
    parser.add_argument('--sealed-run', type=Path)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        require(args.mode is None and args.sealed_run is None, '--selftest is standalone')
        result = selftest()
    else:
        require(args.mode is not None and args.sealed_run is not None, 'mode and --sealed-run required')
        result = getattr(Driver(), args.mode)(args.sealed_run)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, AssertionError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: ' + str(error))
