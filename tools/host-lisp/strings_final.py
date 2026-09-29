#!/usr/bin/env python3
"""Comfort multi-line strings: budget-free probe or one write-once Final (Card L lineage).

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
PREP = ROOT / 'build/strings-r9'
PRIORITY = ['nice', '-n', '18', 'ionice', '-c3']
SEED = Path('build/strings-r7/seed')
PRODUCT = Path('build/strings-product-r3')
OUT = Path('build/strings-final-r1')
SOURCE_RUN = 'build/strings-check-source-r4'
RECEIPTS = {
    "build/strings-r7/seed/baseline-command-proof.json": "123528d1ea28c1b8a0acdcf57678f5aa0602eb1886414a729ef4670ba46dde1c",
    "build/strings-r7/seed/command-proof.json": "bae017dc334ada76703d18a41bdec6cb7e6c9bf79a5115236d6b71b38799015e",
    "build/strings-r7/seed/command-ready.json": "94f20f9494f4b115ee611387dcf6abd1f2b4acef106cff033b8fd4bbeaf11d86",
    "build/strings-r7/seed/derived-inputs.json": "fe68d0789dabdb0d888ccf06dc96183e61085d2716f18775e61e75a589003253",
    "build/strings-r7/seed/include-closure.json": "3d52949e9c889c47285a8273759dc8a9d15cff04ecf4fb31b1cd83530768cee3",
    "build/strings-r7/seed/inventory.json": "f1fc8b905315b9c6efb8131a95429ad15549d9f43323ac80d4b210d1434e860f",
    "build/strings-r7/seed/media.json": "3caa8cda25048986f92eaa43aff2a096b5e7537621fefabab332bbf9f6222ce2",
    "build/strings-r7/seed/plane-price.json": "061b8642eb5ac37b587b03516fb6dc28f14b7656d9b106d24d9e11b8db9754b0",
    "build/strings-r7/seed/price.json": "63994086a3682cdd1237aa0404945e323a5289ac27143d2c6081c23cfec671b6",
    "build/strings-product-r3/seed.json": "e343f4ff4818d2391d2de6959b9418f6de38bf709f5d27b94e1bb4ba25318298"
}
PRODUCER = "tools/host-lisp/strings_seed_producer.py"
HISTORICAL_DRIVER = "dca61b4aae3e663bd583245b7589c49039ab4d9b"
MEDIA_SHA = "9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441"
# Reviewer-approved non-consumed changes only: two omission declarations and
# the runtime harness media repin. None is read by the 75 commands or media emission.
NON_PRODUCT_DELTAS = {
    "tests/bytecode/libs/p0-v160-comfort-device-delta.json": {
        "seed_sha256": "03010a684f21ee131b9a14976b47ccafbb626a102dd5b37df97c99b0eae8669c",
        "seed_bytes": 5158,
        "current_sha256": "43cdca749b0c0be86ca9e2609c43f9081148a0880e7f152f77e25108970ea126",
        "current_bytes": 5273,
        "proof": "build/strings-r12/final-admission-report.md#exhaustive-binding-audit"
    },
    "tests/bytecode/stdlib/p0-stdlib-core-subset.json": {
        "seed_sha256": "3580145111fe0a4390847c1b9ae74b399a29973bfd9e23142526637aac29066b",
        "seed_bytes": 3125,
        "current_sha256": "1007f0a45632a96a70b752f313ed5d73734d1f43fdc729d732f49fc4adaab129",
        "current_bytes": 3240,
        "proof": "build/strings-r12/final-admission-report.md#exhaustive-binding-audit"
    },
    "tools/host-lisp/comfort_default_rows.py": {
        "seed_sha256": "6bb128bfc6d86e4ec2c80fb75891058404decf1a0c50d53bd4d73ecaf67736fa",
        "seed_bytes": 14730,
        "current_sha256": "9c6c080926dc15958aa5883f904c5e86a8df141b0a47f13aa3cb847bdf285810",
        "current_bytes": 14730,
        "proof": "build/strings-r12/final-admission-report.md#exhaustive-binding-audit"
    }
}
# Acceptance-stage producer authority, distinct from the pre-link Seed driver.
ACCEPTED_PRODUCER_COMMIT = '7cbd2b2d2654d8ccf2bbc7f188698a098a7ab281'
ACCEPTED_PRODUCER_SHA = 'abb91b0e653ac6f0dddd6c54960d141c4ee05ce83febfeac1a9760506b9b9b0e'
ACCEPTED_MEDIA_RECEIPTS = {
    'build/strings-r7/seed/media.json': RECEIPTS['build/strings-r7/seed/media.json'],
    'build/strings-product-r3/media-r1/runtime-receipt.json':
        '86ccf711510d2ca61246d9745da02270be1c1541f869b2aee097d081b3fba74f',
}
BUDGET = dict(seed_rebuilds=0, final=1, link=1)
ADMISSIONS = [
    'Final directory absent; one attempt only',
    'sealed check-source green, no protected changes, exact current HEAD and bound log',
    'tracked tree and index clean',
    'frozen Seed receipts and all input bindings verified without restoration writes',
    'historical Seed producer verified; media producer equals accepted 7cbd2b2d bytes',
    'accepted media receipt hashes verified and mtimes post-date producer commit',
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
        require(sealed_run == Path(SOURCE_RUN), 'selected source run mismatch')
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
        require(ready['media_authority']['builder'] == ready['driver'],
                'historical media builder differs from producer')
        # git() strips text output; use a dedicated byte reader for provenance.
        raw = self.historical_driver()
        require(len(raw) == ready['driver']['bytes'] and
                hashlib.sha256(raw).hexdigest() == ready['driver']['sha256'],
                'historical producer mismatch')
        producer_provenance = self.verify_media_producer()
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
        require(proof['frozen'] == ready['commands'], 'Seed command lineage mismatch')
        commands = proof['commands']
        require(len(commands) == 75 and all('-c' in c for c in commands[:73])
                and Path(commands[73][0]).name == 'llvm-link' and '-c' not in commands[74],
                'Seed command shape mismatch')
        old, new = str(PRODUCT / 'wplto'), str(OUT / 'wplto')
        rebased = [[a.replace(old + '/', new + '/') for a in c] for c in commands]
        require(commands == [[a.replace(new + '/', old + '/') for a in c] for c in rebased],
                'Final replay changed a Seed input or flag')
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
                    producer_provenance=producer_provenance, non_product_deltas=NON_PRODUCT_DELTAS,
                    commands=rebased, seed=members, seed_media=[media['medium']], admissions=ADMISSIONS)

    def historical_driver(self):
        return subprocess.check_output(['git', 'show', HISTORICAL_DRIVER + ':' + PRODUCER],
            cwd=self.root, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})

    def historical_file(self, path):
        return subprocess.check_output(['git', 'show', HISTORICAL_DRIVER + ':' + path],
            cwd=self.root, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})

    def accepted_driver(self):
        return subprocess.check_output(['git', 'show', ACCEPTED_PRODUCER_COMMIT + ':' + PRODUCER],
            cwd=self.root, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})

    def verify_media_producer(self):
        raw = self.accepted_driver()
        require(hashlib.sha256(raw).hexdigest() == ACCEPTED_PRODUCER_SHA,
                'accepted producer provenance mismatch')
        require((self.root / PRODUCER).read_bytes() == raw, 'wrong accepted producer version')
        require(self.git('merge-base', ACCEPTED_PRODUCER_COMMIT, 'HEAD') == ACCEPTED_PRODUCER_COMMIT,
                'accepted producer commit not in HEAD ancestry')
        committed = int(self.git('show', '-s', '--format=%ct', ACCEPTED_PRODUCER_COMMIT))
        receipts = []
        for path, expected in ACCEPTED_MEDIA_RECEIPTS.items():
            row = self.verify(dict(path=path, sha256=expected))
            # These local receipts have no embedded creation timestamp. Preserve
            # their mtimes when copying; hashes independently bind their content.
            mtime_ns = (self.root / path).stat().st_mtime_ns
            require(mtime_ns > committed * 1_000_000_000,
                    'accepted media receipt predates producer commit: ' + path)
            receipts.append(dict(row, mtime_ns=mtime_ns))
        return dict(commit=ACCEPTED_PRODUCER_COMMIT, commit_time=committed,
                    sha256=ACCEPTED_PRODUCER_SHA, receipts=receipts)

    def seed_bindings(self):
        rows = {}
        for path, expected in RECEIPTS.items():
            row = self.bind(path)
            require(row['sha256'] == expected, 'frozen receipt drift: ' + path)
            rows[path] = row
            value = self.load(path)
            if path.endswith('/command-ready.json'):
                value.pop('driver')  # historical provenance, checked separately
                value['media_authority'].pop('builder')
            for row in bindings(value):
                if row['path'] in NON_PRODUCT_DELTAS:
                    delta = NON_PRODUCT_DELTAS[row['path']]
                    require(row['sha256'] == delta['seed_sha256'] and
                            row['bytes'] == delta['seed_bytes'],
                            'unapproved Seed delta binding: ' + row['path'])
                    raw = self.historical_file(row['path'])
                    require(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
                            'historical delta mismatch: ' + row['path'])
                    row = self.verify(dict(path=row['path'], sha256=delta['current_sha256'],
                                           bytes=delta['current_bytes']))
                require(row['path'] not in rows or rows[row['path']]['sha256'] == row['sha256'],
                        'conflicting input binding: ' + row['path'])
                rows[row['path']] = row
        for path, expected in ACCEPTED_MEDIA_RECEIPTS.items():
            rows[path] = self.verify(dict(path=path, sha256=expected))
        return [rows[p] for p in sorted(rows)]

    def probe(self, sealed_run):
        result = self.admit(sealed_run)
        return dict(status=result['status'], head=result['head'], admissions=ADMISSIONS,
                    commands=len(result['commands']), budget=dict(seed_rebuilds=0, final=0, link=0))

    def media(self):
        # Keep producer BUILD on Seed for its accepted plane and seed.json.
        # HERE is private so producer.media cannot rewrite Seed media.json.
        sys.path.insert(0, str(self.root / 'tools/host-lisp'))
        import strings_seed_producer as producer
        from unittest.mock import patch
        private = self.root / OUT / 'media-inputs'
        private.mkdir()
        for name in ('command-ready', 'price', 'plane-price', 'derived-inputs'):
            save(private / (name + '.json'), self.load(SEED / (name + '.json')))
        # The strings producer reads prepared plane bytes relative to HERE.
        # Copy them privately; its only receipt write is private media.json.
        shutil.copytree(self.root / SEED / 'plane', private / 'plane')
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
        require(Path(__file__).resolve() == self.root / 'tools/host-lisp/strings_final.py',
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
                relative = Path(seed['path']).relative_to(PRODUCT / 'media-r1')
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
    with tempfile.TemporaryDirectory(prefix='strings-final-selftest-', dir=PREP) as temp:
        root = Path(temp)
        for row in real.seed_bindings() + [real.bind(PRODUCER)]:
            require(not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts,
                    'unsafe fixture input path')
            target = root / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / row['path'], target)
        driver = Driver(root)
        driver.historical_driver = lambda: historical
        head = '1' * 40
        def fixture_git(*args):
            if args == ('rev-parse', 'HEAD'):
                return head
            if args == ('merge-base', ACCEPTED_PRODUCER_COMMIT, 'HEAD'):
                return ACCEPTED_PRODUCER_COMMIT
            if args == ('show', '-s', '--format=%ct', ACCEPTED_PRODUCER_COMMIT):
                return '1790634955'
            return ''
        driver.git = fixture_git
        sealed = Path(SOURCE_RUN)
        (root / sealed).mkdir(parents=True)
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
        try:
            driver.probe(Path('wrong-source-run'))
        except ValueError as error:
            require('selected source run mismatch' in str(error), 'wrong source rejection')
            passed.append('wrong selected source run')
        else:
            raise ValueError('wrong selected source accepted')
        for delta_path in NON_PRODUCT_DELTAS:
            path = root / delta_path
            original = path.read_bytes()
            path.write_bytes(original + b'drift')
            rejected('unapproved successor bytes: ' + delta_path, 'hash/size mismatch')
            path.write_bytes(original)
        saved_reader = driver.historical_file
        driver.historical_file = lambda path: b'wrong historical delta'
        rejected('historical delta drift', 'historical delta mismatch')
        driver.historical_file = saved_reader
        path = root / PRODUCER
        original = path.read_bytes()
        path.write_bytes(historical)
        rejected('wrong producer version (Seed-time producer)', 'wrong accepted producer version')
        path.write_bytes(original)
        for receipt_path in ACCEPTED_MEDIA_RECEIPTS:
            path = root / receipt_path
            times = (path.stat().st_atime_ns, path.stat().st_mtime_ns)
            os.utime(path, ns=(times[0], 1790634955 * 1_000_000_000))
            rejected('media receipt before acceptance: ' + receipt_path, 'predates producer commit')
            os.utime(path, ns=times)
        path = root / SEED / 'command-proof.json'
        original = path.read_bytes()
        proof = driver.load(SEED / 'command-proof.json')
        proof['commands'][0].append('-DUNREVIEWED=1')
        path.write_text(json.dumps(proof))
        rejected('changed frozen command proof', 'frozen receipt drift')
        path.write_bytes(original)
        path = root / real.load(SEED / 'derived-inputs.json')['generated']['path']
        original = path.read_bytes()
        path.write_bytes(original + b'drift')
        rejected('unlisted input delta', 'hash/size mismatch')
        path.write_bytes(original)
        driver.git = lambda *args: head if args == ('rev-parse', 'HEAD') else ' M tracked.c'
        rejected('dirty tracked tree', 'tracked tree dirty')
        driver.git = fixture_git
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
            for source in (root / SEED / 'plane').rglob('*'):
                if source.is_file():
                    copied_plane = fake.HERE / 'plane' / source.relative_to(root / SEED / 'plane')
                    require(copied_plane.read_bytes() == source.read_bytes(), 'private plane drift')
            require(driver.load(fake.HERE / 'derived-inputs.json') ==
                    driver.load(SEED / 'derived-inputs.json'), 'private derivation drift')
            require(driver.load(fake.HERE / 'inventory.json')['ELFs'][1] == driver.bind(target),
                    'Final inventory projection mismatch')
            require(fake.verify_ready(acceptance=True) == driver.load(SEED / 'command-ready.json'),
                    'media admission mismatch')
            result = dict(status='PASS', every_file_read_back=True, unclassified_bytes=0)
            save(fake.HERE / 'media.json', result)
            return result
        fake.media = fake_media
        driver._sealed_run = sealed
        with patch.dict(sys.modules, {'strings_seed_producer': fake}):
            driver.media()
        require((root / SEED / 'media.json').read_bytes() == original_media, 'Seed media receipt overwritten')
        passed.append('private media handoff and Final ELF projection (synthetic producer)')
        return dict(status='PASS', tests=passed, product_commands=0, final_links=0,
                    fixture='private temporary copies; fake sealed receipt; mocked Git')


def selftest():
    from unittest.mock import patch
    historical = Driver().historical_driver()
    deltas = {p: Driver().historical_file(p) for p in NON_PRODUCT_DELTAS}
    accepted = Driver().accepted_driver()
    Driver().verify_media_producer()
    # Any accidental command execution in probe fails even in a synthetic tree.
    with patch.object(Driver, 'historical_file', side_effect=lambda p: deltas[p]), \
         patch.object(Driver, 'accepted_driver', return_value=accepted), \
         patch.object(subprocess, 'run', side_effect=AssertionError('selftest ran a command')), \
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
