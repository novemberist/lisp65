#!/usr/bin/env python3
"""Comfort-default evidence seal, following comfort-library/Card L.

Install in tools/host-lisp after review. draft freezes available reports and
receipts; seal promotes that DRAFT once; check only reads. Missing closing
files may be pending, but present invalid files always fail. No product commands.
Selftest writes synthetic evidence ONLY below this script's seal-prep directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.git').exists())
PREP = ROOT / 'build/comfort-default-r2/seal-prep'
SOURCE_RUN = 'build/comfort-default-check-source-r4'  # sole selected-run constant
SOURCE = SOURCE_RUN + '/receipt.json'
STEM = 'comfort-default-final-20260927'
ARCH = 'tests/bytecode/dialect-v2/evidence/architecture-blocks'
MANIFEST = ARCH + '/' + STEM + '.json'
COPIES = ARCH + '/' + STEM
REPORT = 'docs/planning/comfort-default-final-report.md'
OUT = 'build/comfort-default-final-r1'
SEED = 'build/comfort-default-r2/seed'
PRODUCT = 'build/comfort-default-product-r2'
MEDIA = SEED + '/media-r2'
IDENTITY = OUT + '/final-identity.json'
INVOCATION = OUT + '/final-invocation.json'
FROZEN = 'tools/host-lisp/comfort_default_final_inputs.json'
COMMANDS = SEED + '/command-proof.json'
DRIVER = 'tools/host-lisp/comfort_default_final.py'
BUILDER = 'tools/host-lisp/comfort_default_media.py'
BUDGET = dict(seed_rebuilds=0, final=1, link=1)
PASS = 'PASS: COMFORT DEFAULT FINAL'
ATTEMPTS = [f'build/comfort-default-check-source-r{n}/receipt.json' for n in (1, 3)]
ROWS = [f'build/comfort-default-rows-{n}/receipt.json' for n in
        ('product-r2', 'v240-init-r2', 'no-comfort-r1', 'base-r2')]
GC = [f'build/comfort-default-gc-equal-{n}/receipt.json' for n in
      ('baseline-2', 'candidate-3', 'comfort-2', 'product-2')]
READBACKS = [f'{MEDIA}/{n}/readback.json' for n in
             ('comfort-default', 'control-v240-init', 'control-no-comfort')]
OPTIONAL = [SEED + '/' + n for n in ('seed-report.md', 'inventory.json',
            'allocated-byte-classification.json', 'repl-codegen-proof.json')]
REQUIRED = ATTEMPTS + ROWS + GC + READBACKS + [
    PRODUCT + '/seed.json', MEDIA + '/byte-diff.json',
    'build/input-cost-natural-comfort-default-native-rv4/receipt.json',
    'build/input-cost-natural-comfort-default-native-product-rv1/receipt.json',
    'build/comfort-default-gc-boot-rv2/receipt.json',
    'build/comfort-default-r2/keypath/keypath-report.md',
    'build/comfort-default-r2/gates/reviewer-gates.md',
    'build/comfort-default-r2/consumers/consumers-report.md',
    COMMANDS, FROZEN, DRIVER, BUILDER]
CLOSING = [REPORT, SOURCE, IDENTITY, INVOCATION]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


class Seal:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()

    def path(self, name):
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts, 'unsafe path: ' + str(name))
        result = self.root / p
        require(result.resolve().is_relative_to(self.root), 'path escapes root: ' + str(name))
        return result

    def load(self, name):
        return json.loads(self.path(name).read_text())

    def bind(self, name):
        raw = self.path(name).read_bytes()
        return dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def verify(self, row):
        actual = self.bind(row['path'])
        require(actual['sha256'] == row['sha256'] and
                ('bytes' not in row or actual['bytes'] == row['bytes']), 'binding drift: ' + row['path'])
        return actual

    def head(self):
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root,
                    env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True).strip()

    def write_once(self, name, raw):
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(raw)

    def evidence(self, closing=False):
        selected = set(REQUIRED)
        selected.update(p for p in OPTIONAL if self.path(p).exists())
        pending = [p for p in CLOSING if not self.path(p).exists()]
        if closing:
            selected.update(p for p in CLOSING if p not in pending)
        # Explicit dependency capture only: never crawl build or planning docs.
        for path in ATTEMPTS + ([SOURCE] if self.path(SOURCE).exists() else []):
            value = self.load(path)
            require(value['target'] == 'make -k check-source', 'source target mismatch')
            require(value['changed_protected_files'] == 0 and value['changed_files'] == []
                    and value['changed_sealed_artifacts'] == [], 'source protected changes')
            require(value['head_before'] == value['head_after'], 'source HEAD changed')
            if path == SOURCE:
                require(value['exit_code'] == 0, 'source exit is not zero')
                require(value['head_before'] == self.head(), 'source HEAD mismatch')
            else:
                require(value['exit_code'] == 2, 'red attempt exit mismatch')
            log = self.verify(value['log'])
            require(Path(log['path']).parent == Path(path).parent, 'source log outside run')
            if path != SOURCE or closing:
                selected.add(log['path'])
        for path in ROWS:
            v = self.load(path)
            require(v['status'] == 'DONE' and v['failed'] == [] and v['error'] is None,
                    'rows not green: ' + path)
        for path in GC:
            v = self.load(path)
            require(v['counter'] == 136 and v['forced_count'] == 1, 'GC receipt mismatch: ' + path)
        for path in READBACKS:
            v = self.load(path)
            require(v['status'] == 'PASS: every file read back', 'readback not PASS')
            for key in ('medium', 'index', 'init'):
                selected.add(self.verify(v[key])['path'])
        require(self.load(MEDIA + '/byte-diff.json')['status'] == 'PASS', 'byte-diff not PASS')
        seed = self.load(PRODUCT + '/seed.json')
        require(seed['commands_consumed'] == 75, 'Seed command count mismatch')
        selected.add(self.verify(seed['ELF'])['path'])
        if self.path(IDENTITY).exists():
            v = self.load(IDENTITY)
            require(v['status'] == 'PASS', 'Final not PASS')
            require(v['head'] == self.head(), 'Final HEAD mismatch')
            require(v['sealed_run'] == SOURCE_RUN and v['source'] == self.bind(SOURCE),
                    'Final source mismatch')
            require(v['budget'] == BUDGET and v['commands_consumed'] == 75, 'Final budget/count mismatch')
            # Match populations to the frozen Seed list, not just nonempty arrays.
            frozen = self.load(FROZEN)['inputs']
            frozen_by_path = {r['path']: r for r in frozen}
            for key, expected in (
                ('artifacts', {r['path'] for r in frozen if r['path'].startswith(PRODUCT + '/wplto/resident-island-seed.prg')}),
                ('media', {r['path'] for r in frozen if r['path'].endswith('.d81')})):
                require(len(expected) >= (2 if key == 'artifacts' else 3), 'empty frozen population')
                pairs = v[key]
                require(len(pairs) == len(expected) and {r['seed']['path'] for r in pairs} == expected,
                        'Final population mismatch: ' + key)
                for pair in pairs:
                    old, new = self.verify(pair['seed']), self.verify(pair['final'])
                    require(old == frozen_by_path[old['path']], 'Final Seed differs from frozen binding')
                    relative = (Path(old['path']).name if key == 'artifacts' else
                                str(Path(old['path']).relative_to(MEDIA)))
                    destination = OUT + ('/wplto/' if key == 'artifacts' else '/media/') + relative
                    require(new['path'] == destination and pair['byteidentical'] is True
                            and old['sha256'] == new['sha256'] and old['bytes'] == new['bytes'],
                            'Final identity mismatch')
                    if closing:
                        selected.update((old['path'], new['path']))
        if self.path(INVOCATION).exists():
            v = self.load(INVOCATION)
            require(v['status'] == 'PASS' and v['head'] == self.head(), 'invocation status/HEAD mismatch')
            require(v['sealed_run'] == SOURCE_RUN and v['source'] == self.bind(SOURCE)
                    and v['source_log'] == self.verify(self.load(SOURCE)['log']), 'invocation source mismatch')
            require(v['budget'] == BUDGET, 'invocation budget mismatch')
            for key, path in [('seed_receipt', PRODUCT + '/seed.json'), ('seed_commands', COMMANDS),
                              ('input_bindings', FROZEN), ('driver', DRIVER), ('media_builder', BUILDER)]:
                require(v[key] == self.bind(path), 'invocation binding mismatch: ' + key)
            commands = self.load(COMMANDS)['commands']
            expected = [[a.replace(PRODUCT + '/wplto/', OUT + '/wplto/') for a in c] for c in commands]
            require(len(expected) == 75 and v['commands'] == expected, 'invocation commands mismatch')
            frozen = self.load(FROZEN)['inputs']
            require(v['seed'] == [r for r in frozen if r['path'].startswith(PRODUCT + '/wplto/resident-island-seed.prg')]
                    and v['seed_media'] == [r for r in frozen if r['path'].endswith('.d81')],
                    'invocation Seed population mismatch')
        return [self.bind(p) for p in sorted(selected)], pending

    def copy_receipts(self, rows):
        copies = []
        # Copy all selected JSON receipts, including the large byte-diff; no size skip.
        for row in rows:
            if row['path'].endswith('.json'):
                dest = COPIES + '/' + row['path']
                raw = self.path(row['path']).read_bytes()
                require(hashlib.sha256(raw).hexdigest() == row['sha256'], 'copy source changed')
                self.write_once(dest, raw)
                copies.append(dict(source=row, copy=self.bind(dest)))
        return copies

    def draft(self):
        require(not self.path(MANIFEST).exists() and not self.path(COPIES).exists(), 'draft already exists')
        rows, pending = self.evidence()
        value = dict(format='comfort-default-seal-v1', card='comfort-default', status='DRAFT',
                     stage='draft', sealed_at_head=self.head(), inputs=rows, closing_inputs=[],
                     optional_absent=[p for p in OPTIONAL if not self.path(p).exists()],
                     pending=pending, receipt_copies=self.copy_receipts(rows),
                     budget=dict(seed_rebuilds=0, final=0, link=0), device_contacts=0)
        self.write_once(MANIFEST, encoded(value))
        return dict(status='DRAFT', bindings=len(rows), pending=pending)

    def check(self, allow_pending=False):
        v = self.load(MANIFEST)
        require(v['format'] == 'comfort-default-seal-v1' and v['card'] == 'comfort-default', 'seal format mismatch')
        require(v['status'] in ('DRAFT', PASS), 'unknown seal status')
        sealed = v['status'] == PASS
        rows, pending = self.evidence(closing=sealed)
        stored = v['inputs'] + v['closing_inputs']
        require(len(stored) == len({r['path'] for r in stored}), 'duplicate binding')
        for row in stored:
            self.verify(row)
        require(sorted(stored, key=lambda r: r['path']) == rows, 'binding population mismatch')
        require(v['optional_absent'] == [p for p in OPTIONAL if not self.path(p).exists()], 'optional population drift')
        expected = {r['path']: r for r in stored if r['path'].endswith('.json')}
        require(len(v['receipt_copies']) == len(expected), 'receipt copy population mismatch')
        seen = set()
        for pair in v['receipt_copies']:
            source, copy = pair['source'], pair['copy']
            require(source == expected.get(source['path']) and source['path'] not in seen, 'copy source mismatch')
            seen.add(source['path'])
            require(copy['path'] == COPIES + '/' + source['path'], 'copy destination mismatch')
            self.verify(copy)
            require(self.path(source['path']).read_bytes() == self.path(copy['path']).read_bytes(), 'receipt copy differs')
        if sealed:
            require(v['source_head'] == self.head() and v['pending'] == [] and v['stage'] == 'seal', 'seal HEAD/stage mismatch')
            require(v['final'] == self.load(IDENTITY) and v['budget'] == BUDGET, 'seal Final summary mismatch')
        else:
            require(v['closing_inputs'] == [] and v['stage'] == 'draft', 'invalid draft')
            pending.append('immutable Final seal (draft evidence snapshot only)')
        require(allow_pending or not pending, 'pending bindings: ' + '; '.join(pending))
        return dict(status='PENDING' if pending else 'PASS', pending=pending, bindings=len(stored),
                    receipt_copies=len(v['receipt_copies']))

    def seal(self):
        v = self.load(MANIFEST)
        require(v['status'] == 'DRAFT', 'immutable seal already exists')
        result = self.check(True)
        require(result['pending'] == ['immutable Final seal (draft evidence snapshot only)'], 'incomplete closure')
        rows, pending = self.evidence(closing=True)
        require(not pending, 'incomplete closure')
        old = {r['path'] for r in v['inputs']}
        closing = [r for r in rows if r['path'] not in old]
        v['receipt_copies'] += self.copy_receipts(closing)
        v.update(status=PASS, stage='seal', source_head=self.head(), pending=[],
                 closing_inputs=closing, final=self.load(IDENTITY), budget=BUDGET)
        # Only an explicit draft is replaced; an existing PASS is immutable.
        tmp = MANIFEST + '.tmp'
        self.write_once(tmp, encoded(v))
        self.path(tmp).replace(self.path(MANIFEST))
        return self.check()


def selftest():
    """Synthetic fixtures; no real evidence changes, subprocesses, or product work."""
    PREP.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='selftest-', dir=PREP) as temp:
        s = Seal(temp)
        s.head = lambda: '1' * 40
        def put(path, value):
            p = s.path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(encoded(value) if not isinstance(value, bytes) else value)
        for path in REQUIRED + OPTIONAL:
            put(path, {} if path.endswith('.json') else b'fixture\n')
        for path in ATTEMPTS + [SOURCE]:
            log = str(Path(path).with_name('check-source.log'))
            put(log, b'synthetic source log\n')
            put(path, dict(target='make -k check-source', exit_code=0 if path == SOURCE else 2,
                           head_before=s.head(), head_after=s.head(), changed_protected_files=0,
                           changed_files=[], changed_sealed_artifacts=[], log=s.bind(log)))
        for path in ROWS:
            put(path, dict(status='DONE', failed=[], error=None))
        for path in GC:
            put(path, dict(counter=136, forced_count=1))
        media = []
        for path in READBACKS:
            medium = str(Path(path).with_name(Path(path).parent.name + '.d81'))
            put(medium, b'medium')
            index, init = str(Path(path).with_name('l65index')), MEDIA + '/artifacts/init.l65'
            put(index, b'index'); put(init, b'init')
            put(path, dict(status='PASS: every file read back', medium=s.bind(medium), index=s.bind(index), init=s.bind(init)))
            media.append(s.bind(medium))
        put(MEDIA + '/byte-diff.json', dict(status='PASS'))
        artifacts = []
        for suffix in ('', '.elf', '.lto.o'):
            p = PRODUCT + '/wplto/resident-island-seed.prg' + suffix
            put(p, b'product' + suffix.encode()); artifacts.append(s.bind(p))
        put(PRODUCT + '/seed.json', dict(commands_consumed=75, ELF=artifacts[1]))
        put(FROZEN, dict(inputs=artifacts + media))
        put(COMMANDS, dict(commands=[['compiler', '-o', PRODUCT + '/wplto/test']] * 75))
        final = dict(status='PASS', head=s.head(), sealed_run=SOURCE_RUN, source=s.bind(SOURCE),
                     budget=BUDGET, commands_consumed=75, artifacts=[], media=[])
        for key, members in [('artifacts', artifacts), ('media', media)]:
            for old in members:
                relative = Path(old['path']).name if key == 'artifacts' else str(Path(old['path']).relative_to(MEDIA))
                new = OUT + ('/wplto/' if key == 'artifacts' else '/media/') + relative
                put(new, s.path(old['path']).read_bytes())
                final[key].append(dict(seed=old, final=s.bind(new), byteidentical=True))
        invocation = dict(status='PASS', head=s.head(), sealed_run=SOURCE_RUN, source=s.bind(SOURCE),
            source_log=s.verify(s.load(SOURCE)['log']), budget=BUDGET,
            seed=artifacts, seed_media=media,
            commands=[['compiler', '-o', OUT + '/wplto/test']] * 75)
        for key, path in [('seed_receipt', PRODUCT + '/seed.json'), ('seed_commands', COMMANDS),
                          ('input_bindings', FROZEN), ('driver', DRIVER), ('media_builder', BUILDER)]:
            invocation[key] = s.bind(path)
        # Draft with all four closing files absent, then complete closure.
        source_raw = s.path(SOURCE).read_bytes()
        s.path(SOURCE).unlink()
        s.draft()
        require(len(s.check(True)['pending']) == 5, 'pending fixture failed')
        tests = ['draft permits only missing closing evidence']
        def reject(label, action):
            try:
                action()
            except (ValueError, OSError, KeyError):
                tests.append(label)
            else:
                raise AssertionError('mutation accepted: ' + label)
        reject('strict draft check', s.check)
        reject('premature seal', s.seal)
        put(SOURCE, source_raw); put(REPORT, b'final card report\n')
        put(IDENTITY, final); put(INVOCATION, invocation)
        for path, key, bad in [(SOURCE, 'exit_code', 2), (SOURCE, 'head_after', '2' * 40),
                (SOURCE, 'changed_protected_files', 1), (SOURCE, 'changed_files', ['drift']),
                (SOURCE, 'changed_sealed_artifacts', ['drift']), (SOURCE, 'target', 'wrong'),
                (IDENTITY, 'status', 'FAIL'), (IDENTITY, 'artifacts', []),
                (IDENTITY, 'media', []), (IDENTITY, 'commands_consumed', 74),
                (INVOCATION, 'commands', []), (INVOCATION, 'sealed_run', 'wrong'),
                (INVOCATION, 'seed', []), (INVOCATION, 'seed_media', [])]:
            original = s.path(path).read_bytes()
            value = s.load(path); value[key] = bad; put(path, value)
            reject(path + ':' + key, lambda: s.check(True))
            put(path, original)
        s.seal(); require(s.check()['status'] == 'PASS', 'positive seal failed')
        tests.append('positive draft/seal/check')
        for path in [REPORT, SOURCE, IDENTITY, INVOCATION, REQUIRED[0],
                     SOURCE_RUN + '/check-source.log', final['media'][0]['final']['path'],
                     s.load(MANIFEST)['receipt_copies'][0]['copy']['path']]:
            raw = s.path(path).read_bytes(); put(path, raw + b' ')
            reject('drift: ' + path, s.check); put(path, raw)
        raw = s.path(MANIFEST).read_bytes()
        v = s.load(MANIFEST); v['inputs'].pop(); put(MANIFEST, v)
        reject('missing manifest binding', s.check); put(MANIFEST, raw)
        v = s.load(MANIFEST); v['receipt_copies'].pop(); put(MANIFEST, v)
        reject('missing receipt copy', s.check); put(MANIFEST, raw)
        reject('immutable reseal', s.seal); reject('immutable redraft', s.draft)
        s.head = lambda: '2' * 40
        reject('current HEAD drift', s.check)
        return dict(status='PASS', tests=tests, product_commands=0, device_contacts=0,
                    fixture='synthetic files exclusively inside seal-prep; subprocesses forbidden')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', nargs='?', choices=['draft', 'seal', 'check'])
    p.add_argument('--allow-pending', action='store_true')
    p.add_argument('--selftest', action='store_true')
    a = p.parse_args()
    if a.selftest:
        require(a.mode is None and not a.allow_pending, 'selftest is standalone')
        with patch.object(subprocess, 'run', side_effect=AssertionError('subprocess forbidden')), \
             patch.object(subprocess, 'check_output', side_effect=AssertionError('subprocess forbidden')):
            result = selftest()
    else:
        require(a.mode is not None, 'mode required')
        require(not a.allow_pending or a.mode == 'check', '--allow-pending is check-only')
        if a.mode in ('draft', 'seal'):
            require(Path(__file__).resolve() == ROOT / 'tools/host-lisp/comfort_default_seal.py',
                    'install reviewed tool before writing production seal')
        s = Seal()
        result = s.check(a.allow_pending) if a.mode == 'check' else getattr(s, a.mode)()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, AssertionError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: ' + str(error))
