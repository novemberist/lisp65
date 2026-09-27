#!/usr/bin/env python3
"""comfort-library card: seal the card's evidence (model: the dirty-anchor and
nested-error recovery final seals).

Stages:
  pre-source  before the sealed full check-source: binds every card output
              (and copies the small JSON receipts) so the sealed run protects
              them read-only.
  final       after the green sealed run: verifies the run receipt (exit 0,
              exact HEAD, zero changed protected files), writes the card
              closure (identities, prices, gates, GC, lanes) and seals it with
              the run.

Read-only on product artifacts: no compiler, linker, pack or emulator.
Usage: comfort_library_seal.py pre-source|final [--source-head SHA]
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks'
COPY_LIMIT = 200_000
ROOTS = ['build/comfort-library-r1', 'build/comfort-library-medium-r1-attempt1-overstrict',
         'build/comfort-library-medium-r1', 'build/comfort-library-medium-r2',
         'build/comfort-library-rows-base-r1', 'build/comfort-library-rows-r1', 'build/comfort-library-rows-r2',
         'build/comfort-library-gc-equal-baseline-1', 'build/comfort-library-gc-equal-candidate-1',
         'build/comfort-library-gc-equal-comfort-1', 'build/comfort-library-gc-equal-comfort-2',
         'build/input-cost-natural-comfort-library-r1', 'build/comfort-library-boot-probe-r1']
LOOSE = ['build/comfort-library-rows-base-r1.log', 'build/comfort-library-rows-r1.log',
         'build/comfort-library-rows-r2.log', 'build/comfort-library-gc-baseline-1.log',
         'build/comfort-library-gc-candidate-1.log', 'build/comfort-library-gc-comfort-1.log',
         'build/comfort-library-gc-comfort-2.log', 'build/comfort-library-lanes-r1.log',
         'lib/repl-comfort-v240.lisp', 'lib/sexp-depth.lisp',
         'tests/bytecode/libs/p0-repl-comfort-v240.json', 'tests/bytecode/libs/p0-repl-comfort-v240-resident.json']
FINAL_ROOTS = ['build/comfort-library-check-source-r1', 'build/comfort-library-check-source-r2']
# r1: exit 2, one red (media-builder enumeration did not know the Comfort
# medium producer); converted in tools only (enumeration v31); r2 is the run
# the closure binds.
ELF = '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
BASE_D81 = '87cb0f6ea9b2dc690f66ee11d9c76d5138e11f28452254a9b5730c78cabc5f5d'
MEDIUM = 'bb9b8d56330c425f43792b4a8e6929db05fc8f6bbca52180d04176619f5ff43f'
TRACKED = ('tests/bytecode/libs/p0-repl-comfort-v240.json', 'lib/repl-comfort-v240.lisp',
           'tests/bytecode/libs/p0-repl-comfort-v240-resident.json')
HISTORICAL = {'f48460bb65ec4db9': 'build/comfort-library-r1/rows-driver-as-run-r1.py',
              'dd2c095088be36b2': 'build/comfort-library-r1/medium-tool-as-run-r1.py'}


def bind(path):
    path = Path(path).resolve()
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest)


def committed(path, digest):
    """True when `digest` equals the blob of `path` at one of its commits."""
    revs = subprocess.check_output(['git', 'rev-list', 'HEAD', '-n', '40', '--', path], cwd=ROOT, text=True).split()
    return any(hashlib.sha256(subprocess.check_output(['git', 'show', r + ':' + path], cwd=ROOT)).hexdigest() == digest
               for r in revs)


def load(path):
    return json.loads((ROOT / path).read_text())


def closure(source_head):
    """Card numbers, re-derived from the receipts (never typed in)."""
    medium = load('build/comfort-library-medium-r2/packed-receipt.json')
    assert medium['status'].startswith('PASS') and medium['medium']['sha256'] == MEDIUM
    assert medium['elf']['sha256'] == ELF and medium['base_medium']['sha256'] == BASE_D81
    role = load('build/comfort-library-r1/role-r2/repl-comfort.manifest.json')
    rows = load('build/comfort-library-rows-r2/receipt.json')
    assert rows['status'] == 'DONE' and not rows['failed']
    by = {r['id']: r for r in rows['rows']}
    d5 = by['c10-ide']['values']
    gc = {k: load(f'build/comfort-library-gc-equal-{k}/receipt.json')
          for k in ('baseline-1', 'candidate-1', 'comfort-2')}
    for v in gc.values():
        assert v['counter'] == 136 and v['forced_count'] == 1
    lat = load('build/comfort-library-r1/latency-qualification.json')
    boot = load('build/comfort-library-boot-probe-r1/receipt.json')
    depth = dict(comfort_deepest=15 if '15' in by['c11-comfort-15']['new_lines'] else None,
                 comfort_first_refused=16 if '*** VM: STACK OVERFLOW' in by['c11-comfort-16']['new_lines'] else None,
                 native_deepest=16 if '16' in by['c11-native-16']['new_lines'] else None,
                 native_first_refused=17 if '*** VM: STACK OVERFLOW' in by['c11-native-17']['new_lines'] else None)
    value = dict(
        card='comfort-library', binding='180cb993',
        budget=dict(seed=0, final=0, product_link=0, product_builds=0, device_contacts=0),
        identities=dict(elf=ELF, base_d81=BASE_D81, comfort_d81=MEDIUM,
                        files_unchanged=medium['files_unchanged_count'], changed_file='L65INDEX',
                        added_file='REPL-COMFORT', directory_records_changed=medium['directory_records_changed'],
                        changed_sectors=len(medium['changed_sectors'])),
        package=dict(name='repl-comfort', shelf='repl', code_bytes=role['code_bytes'], objects=role['objects'],
                     largest=role['cost']['largest_code_object_bytes'], blob=role['blob_sha256'],
                     artifact_bytes=medium['package']['artifact_bytes']),
        d5=dict(free_symbols=d5['free_symbols'], free_name_bytes=d5['free_name_bytes'],
                nsym=d5['nsym']['used'], npool=d5['npool']['used'], images=d5['images']['used']),
        depth=depth,
        rows=dict(passed=rows['passed'], observed=sum(r['result'] == 'OBSERVED' for r in rows['rows']),
                  failed=rows['failed'], total=len(rows['rows'])),
        gc={k: [(c['phase'], c['cycles'], c['marked']['count']) for c in v['collections']] for k, v in gc.items()},
        lanes=dict(status=lat['status'], ratios={k: v['ratio'] for k, v in lat['lanes'].items()},
                   collections={k: v['collections'] for k, v in lat['lanes'].items()}),
        boot=dict(equal=boot['equal'], gc_runs={k: v['gc_runs'] for k, v in boot['worlds'].items()}))
    assert value['package']['code_bytes'] <= 950
    assert d5['free_symbols'] >= 32 and d5['free_name_bytes'] >= 384
    assert depth['comfort_deepest'] and depth['comfort_deepest'] >= 14
    if source_head:
        red = load('build/comfort-library-check-source-r1/receipt.json')
        assert red['exit_code'] == 2 and red['changed_protected_files'] == 0
        source = load('build/comfort-library-check-source-r2/receipt.json')
        assert source['target'] == 'make -k check-source'
        assert source['exit_code'] == 0 and source['changed_protected_files'] == 0
        assert not source['changed_files'] and not source['changed_sealed_artifacts']
        assert source['head_before'] == source['head_after'] == source_head
        assert bind(ROOT / source['log']['path'])['sha256'] == source['log']['sha256']
        value.update(first_source_run=dict(head=red['head_before'], exit=2, red='c2-media-builder-closure-enumeration-selftest'),
                     source_head=source_head, source_exit=0, source_seconds=source['seconds'],
                     protected_files=source['protected_files'],
                     sealed_artifacts=source['sealed_artifacts_read_only'])
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['pre-source', 'final'])
    p.add_argument('--source-head')
    a = p.parse_args()
    assert (a.stage == 'final') == bool(a.source_head)
    stem = 'comfort-library-' + a.stage + '-20260924'
    target = ARCH / (stem + '.json')
    assert not target.exists()
    value = closure(a.source_head)
    status = 'PASS: COMFORT LIBRARY HOST CLOSURE' if a.stage == 'final' else 'PASS: COMFORT LIBRARY PRE-SOURCE EVIDENCE'
    value['status'] = status
    card_closure = ROOT / f'build/comfort-library-r1/closure-{a.stage}.json'
    assert not card_closure.exists()
    card_closure.write_text(json.dumps(value, indent=2) + '\n')
    selected, skipped = set(), 0
    for root in ROOTS + (FINAL_ROOTS if a.stage == 'final' else []):
        for f in (ROOT / root).rglob('*'):
            if f.is_file() and not f.is_symlink():
                parts = f.relative_to(ROOT).parts
                if f.name == 'system-sd.img' or any(x in parts for x in
                                                    ('generated-0', 'xdg-data', 'xdg-config', 'xdg-run', 'ssh')):
                    skipped += 1
                    continue
                selected.add(f.resolve())
    selected.update((ROOT / 'tools/host-lisp').glob('comfort_library_*.py'))
    selected.update(ROOT / x for x in LOOSE)
    rows, copies, superseded, at_commit = {}, [], [], []

    def verify(v):
        if isinstance(v, dict):
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str) \
                    and v['sha256'][:16] in HISTORICAL:
                # A driver edited after its run (retargeted r1 -> r2): the as-run
                # revision is reconstructed byte-exactly and bound instead.
                actual = bind(ROOT / HISTORICAL[v['sha256'][:16]])
                assert actual['sha256'] == v['sha256'], v['path']
                superseded.append(dict(bound=dict(v), reconstructed=actual))
                rows[actual['path']] = actual
                v = {k: x for k, x in v.items() if k not in ('path', 'sha256')}
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str):
                q = (ROOT / v['path']).resolve()
                if q.is_file() and q.is_relative_to(ROOT) and q.name != 'system-sd.img':
                    actual = bind(q)
                    if actual['sha256'] != v['sha256'] and actual['path'] in TRACKED:
                        # Tracked input bound at an earlier committed version.
                        assert committed(actual['path'], v['sha256']), v['path']
                        at_commit.append(dict(path=actual['path'], sha256=v['sha256']))
                        return
                    assert actual['sha256'] == v['sha256'], v['path']
                    rows[actual['path']] = actual
            for child in v.values():
                verify(child)
        elif isinstance(v, list):
            for child in v:
                verify(child)
    for f in sorted(selected):
        rel = f.relative_to(ROOT)
        if f.suffix == '.json' and rel.parts[0] == 'build':
            try:
                data = json.loads(f.read_text())
            except ValueError:
                data = None
            if data is not None and rel.parts[1] not in ('comfort-library-check-source-r1', 'comfort-library-check-source-r2'):
                verify(data)
            if f.stat().st_size <= COPY_LIMIT and not rel.parts[1].startswith('comfort-library-check-source-r'):
                dest = ARCH / stem / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                assert not dest.exists()
                shutil.copyfile(f, dest)
                copies.append(bind(dest))
        row = bind(f)
        rows[row['path']] = row
    result = dict(status=status, stage=a.stage, card='comfort-library', binding='180cb993',
                  sealed_at_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  closure=bind(card_closure), numbers=value,
                  inputs=sorted(rows.values(), key=lambda x: x['path']), receipt_copies=copies,
                  superseded_driver_bindings=superseded, bound_at_committed_version=at_commit,
                  excluded=dict(rule='mutable SD scratch (system-sd.img); sealed-run private generated/xdg/ssh trees',
                                count=skipped),
                  budget=value['budget'], device_contacts=0)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(status, len(rows), 'bindings;', len(copies), 'receipt copies ->', target.relative_to(ROOT))


if __name__ == '__main__':
    main()
