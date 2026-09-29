#!/usr/bin/env python3
"""IDE key exit: budget-free probe or one write-once Final (Card L lineage).

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
ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.git').exists())
PREP = ROOT / 'build/ide-exit-r9'
PRIORITY = ['nice', '-n', '18', 'ionice', '-c3']
SEED = Path('build/ide-exit-r5/seed')
PRODUCT = Path('build/ide-exit-product-r2')
OUT = Path('build/ide-exit-final-r1')
RECEIPTS = {
    "build/ide-exit-r5/seed/command-ready.json": "82de727eab34f363b9b822b7dc1c00fcd1931de1523719f5e617098a3c45c79f",
    "build/ide-exit-r5/seed/baseline-command-proof.json": "ca268fec2783f53ea26d82dc28cb2ffe40a9c4b571ea27610cb1eab3cca32fbb",
    "build/ide-exit-r5/seed/command-proof.json": "c9280630fdd22e57a5e51386b03e4bed6dc9f18030ec1912219d958e2eb0c0e0",
    "build/ide-exit-r5/seed/include-closure.json": "4f7d7c2caf9f720de5a5a1af64b3fdc661b1f2c1289109ce9e3c08612e1c7842",
    "build/ide-exit-r5/seed/derived-inputs.json": "1136e49b69882dcf268610e7264cb305039d296404d3eaf45226c2a251f22406",
    "build/ide-exit-r5/seed/plane-price.json": "cac60f32d0514aa3285e52edf3440889745a37a9e1eb646a7a2193407d949c3d",
    "build/ide-exit-r5/seed/price.json": "7f3605f57cf626dc9e51b4f862290666b47e254f16e4382841f023d7918d5367",
    "build/ide-exit-r5/seed/inventory.json": "3eb8fb4b0c8eb237211f8b6817fd1f1a398321e0a1e42424c3612ec35c7bc3e5",
    "build/ide-exit-r5/seed/media.json": "565677d619b5ee0c48b50bb70f550c2d7c3b27e3e42ca05337e8567e73d00780",
    "build/ide-exit-product-r2/seed.json": "4526860c6e89357826f3b76a12d802f0b6284a579fd26616f6fe8a31b4fe8db6"
}
PRODUCER = "tools/host-lisp/ide_exit_seed_producer.py"
HISTORICAL_DRIVER = "712450b78c75eac82da190f698068875154d8e5f"
MEDIA_SHA = "8901407117b87814009a77751a78c0a70096813574300300ef4f8f5c5ad9f8f5"
BUDGET = dict(seed_rebuilds=0, final=1, link=1)
ADMISSIONS = [
    'Final directory absent; one attempt only',
    'sealed check-source green, no protected changes, exact current HEAD and bound log',
    'tracked tree and index clean',
    'frozen Seed receipts and all input bindings verified without restoration writes',
    'historical producer verified at Seed commit; current producer bound separately',
    '75 Seed commands with only wplto output references rebased',
    'ELF, PRG, LTO and accepted D81 byte identity required',
]


def bindings(value):
    if isinstance(value, dict):
        if {'path', 'sha256'} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from bindings(child)
    elif isinstance(value, list):
        for child in value:
            yield from bindings(child)


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
        rows = self.seed_bindings()
        for row in rows:
            self.verify(row)
        ready = self.load(SEED / 'command-ready.json')
        # git() strips text output; use a dedicated byte reader for provenance.
        raw = self.historical_driver()
        require(len(raw) == ready['driver']['bytes'] and
                hashlib.sha256(raw).hexdigest() == ready['driver']['sha256'],
                'historical producer mismatch')
        seed = self.load(PRODUCT / 'seed.json')
        require(seed['commands_consumed'] == 75 and seed['product_link_attempts'] == 1
                and set(seed['native']) == {'ELF', 'PRG', 'LTO'}, 'Seed receipt mismatch')
        for name in ('price', 'inventory', 'plane-price', 'media'):
            require(self.load(SEED / (name + '.json'))['status'] == 'PASS', name + ' not PASS')
        require(self.load(SEED / 'inventory.json')['unclassified_bytes'] == 0, 'inventory drift')
        media = self.load(SEED / 'media.json')
        require(media['every_file_read_back'] is True and media['unclassified_bytes'] == 0
                and media['medium']['sha256'] == MEDIA_SHA, 'media readback mismatch')
        proof = self.load(SEED / 'command-proof.json')
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
        members = list(seed['native'].values())
        return dict(status='PASS', head=head, sealed_run=str(sealed_run), source=self.bind(receipt_path),
                    source_log=log, seed_receipt=self.bind(PRODUCT / 'seed.json'),
                    seed_commands=self.bind(SEED / 'command-proof.json'),
                    input_bindings=rows, media_builder=self.bind(PRODUCER),
                    commands=rebased, seed=members, seed_media=[media['medium']], admissions=ADMISSIONS)

    def historical_driver(self):
        return subprocess.check_output(['git', 'show', HISTORICAL_DRIVER + ':' + PRODUCER],
            cwd=self.root, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})

    def seed_bindings(self):
        rows = {}
        for path, expected in RECEIPTS.items():
            row = self.bind(path)
            require(row['sha256'] == expected, 'frozen receipt drift: ' + path)
            rows[path] = row
            value = self.load(path)
            if path.endswith('/command-ready.json'):
                value.pop('driver')  # historical provenance, checked separately
            for row in bindings(value):
                require(row['path'] not in rows or rows[row['path']]['sha256'] == row['sha256'],
                        'conflicting input binding: ' + row['path'])
                rows[row['path']] = row
        return [rows[p] for p in sorted(rows)]

    def probe(self, sealed_run):
        result = self.admit(sealed_run)
        return dict(status=result['status'], head=result['head'], admissions=ADMISSIONS,
                    commands=len(result['commands']), budget=dict(seed_rebuilds=0, final=0, link=0))

    def media(self):
        # Keep producer BUILD on Seed for its accepted plane and seed.json.
        # HERE is private so producer.media cannot rewrite Seed media.json.
        sys.path.insert(0, str(self.root / 'tools/host-lisp'))
        import ide_exit_seed_producer as producer
        from unittest.mock import patch
        private = self.root / OUT / 'media-inputs'
        private.mkdir()
        for name in ('command-ready', 'price', 'plane-price'):
            save(private / (name + '.json'), self.load(SEED / (name + '.json')))
        inv = self.load(SEED / 'inventory.json')
        inv['ELFs'][1] = self.bind(OUT / 'wplto/resident-island-seed.prg.elf')
        save(private / 'inventory.json', inv)
        def ready(**kwargs):
            # Re-run full Final admission; old producer authority allowlist
            # predates installation of the Final and seal drivers.
            self.admit(self._sealed_run, claimed=True)
            return self.load(SEED / 'command-ready.json')
        with patch.object(producer, 'HERE', private), patch.object(producer, 'verify_ready', ready):
            result = producer.media(self.root / OUT / 'media')
        require(result['status'] == 'PASS' and result['every_file_read_back'] is True
                and result['unclassified_bytes'] == 0, 'Final media readback failed')

    def final(self, sealed_run):
        require(Path(__file__).resolve() == self.root / 'tools/host-lisp/ide_exit_final.py',
                'install reviewed driver before Final')
        self._sealed_run = sealed_run
        admission = self.admit(sealed_run)
        output = self.root / OUT
        output.mkdir()  # Atomic attempt claim before any product command.
        identity = dict(status='FAIL', head=admission['head'], source=admission['source'],
                        sealed_run=admission['sealed_run'], budget=BUDGET, artifacts=[], media=[])
        try:
            save(output / 'final-invocation.json', dict(admission, budget=BUDGET,
                 driver=self.bind(Path(__file__).resolve()), media_builder=self.bind(PRODUCER)))
            for index, command in enumerate(admission['commands']):
                (self.root / command[command.index('-o') + 1]).parent.mkdir(parents=True, exist_ok=True)
                with (output / f'command-{index:03d}.log').open('wb') as log:
                    result = subprocess.run(PRIORITY + command, cwd=self.root, stdout=log, stderr=subprocess.STDOUT)
                require(result.returncode == 0, f'command {index} exit {result.returncode}; no retry')
                identity['commands_consumed'] = index + 1
            for seed in admission['seed']:
                final = self.bind(OUT / 'wplto' / Path(seed['path']).name)
                equal = (self.root / seed['path']).read_bytes() == (self.root / final['path']).read_bytes()
                identity['artifacts'].append(dict(seed=seed, final=final, byteidentical=equal))
                require(equal, 'Final identity mismatch: ' + seed['path'])
            self.media()
            for seed in admission['seed_media']:
                relative = Path(seed['path']).relative_to(PRODUCT / 'media-r2')
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


def _selftest_fixture(historical):
    # Copy, never mutate, actual Seed inputs. Git is the only substituted reader.
    real = Driver()
    PREP.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ide-exit-final-selftest-', dir=PREP) as temp:
        root = Path(temp)
        for row in real.seed_bindings() + [real.bind(PRODUCER)]:
            target = root / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['path'], target)
        driver = Driver(root)
        driver.historical_driver = lambda: historical
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
        path = root / real.load(SEED / 'derived-inputs.json')['generated']['path']
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
        # Exercise the producer handoff without importing/running product code.
        from types import SimpleNamespace
        from unittest.mock import patch
        import sys
        copied = driver.load(SEED / 'inventory.json')
        target = root / OUT / 'wplto/resident-island-seed.prg.elf'
        target.parent.mkdir()
        shutil.copyfile(root / copied['ELFs'][1]['path'], target)
        original_media = (root / SEED / 'media.json').read_bytes()
        fake = SimpleNamespace(HERE=root / SEED, verify_ready=None)
        def fake_media(destination):
            require(destination == root / OUT / 'media', 'media destination mismatch')
            require(fake.HERE == root / OUT / 'media-inputs', 'media receipt root mismatch')
            require(driver.load(fake.HERE / 'inventory.json')['ELFs'][1] == driver.bind(target),
                    'Final inventory projection mismatch')
            require(fake.verify_ready(acceptance=True) == driver.load(SEED / 'command-ready.json'),
                    'media admission mismatch')
            result = dict(status='PASS', every_file_read_back=True, unclassified_bytes=0)
            save(fake.HERE / 'media.json', result)
            return result
        fake.media = fake_media
        driver._sealed_run = sealed
        with patch.dict(sys.modules, {'ide_exit_seed_producer': fake}):
            driver.media()
        require((root / SEED / 'media.json').read_bytes() == original_media, 'Seed media receipt overwritten')
        passed.append('private media handoff and Final ELF projection (synthetic producer)')
        return dict(status='PASS', tests=passed, product_commands=0, final_links=0,
                    fixture='private temporary copies; fake sealed receipt; mocked Git')


def selftest():
    from unittest.mock import patch
    historical = Driver().historical_driver()
    # Any accidental command execution in probe fails even in a synthetic tree.
    with patch.object(subprocess, 'run', side_effect=AssertionError('selftest ran a command')), \
         patch.object(subprocess, 'check_output', side_effect=AssertionError('selftest ran a command')):
        return _selftest_fixture(historical)


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
