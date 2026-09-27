"""Seal fourth Seed tools and receipts after the positive activation halt."""
import argparse
import ast
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
ROOT = P.ROOT
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'set-b-fourth-seed-activation-halt-20260926'
SEAL = ARCH/(STEM+'.json')
REPORT = ROOT/'docs/planning/set-b-fourth-seed-activation-halt-report.md'


def local_import_closure(paths):
    seen = set()
    while paths:
        path = paths.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
            for name in names:
                if name:
                    candidate = ROOT/'tools/host-lisp'/(name.split('.')[0]+'.py')
                    if candidate.is_file() and candidate not in seen:
                        paths.append(candidate)
    return seen


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    authority = S.require_auth()
    boot = P.load(ROOT/'build/set-b-fourth-boot-r1/receipt.json')
    assert boot['status'] == 'HALT' and not boot['steps']
    closure = P.load(S.OUT/'closure-r1/receipt.json')
    assert closure['complete_inventory'] and closure['unclassified_bytes'] == closure['unclassified_relocations'] == 0
    assert P.load(ROOT/'build/set-b-seed-medium-r5/readback.json')['status'] == 'PASS: INDEPENDENT MEDIA READBACK'
    assert P.load(S.OUT/'halt-attribution-r1/receipt.json')['first_executed_failure'].startswith('UNKNOWN')
    roots = [S.OUT, S.PRODUCT, ROOT/'build/set-b-seed-medium-r5', ROOT/'build/set-b-fourth-boot-r1']
    selected = set()
    excluded = []
    for root in roots:
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            if path.name == 'system-sd.img':
                excluded.append(dict(path=str(path.relative_to(ROOT)), reason='Disposable 4 GiB SD copy; medium and stopped memory preserved'))
            else:
                selected.add(path)
    selected.update(ROOT/p for p in S.authority_files())
    newtools = sorted((ROOT/'tools/host-lisp').glob('set_b_fourth*_20260926.py')) + [ROOT/'tools/host-lisp/set_b_read_repair_final_20260926.py']
    selected.update(local_import_closure(newtools))
    selected.update([REPORT, ROOT/'src/optional/c2_map_cpu_read.s', ROOT/'src/vm_runtime_overlay.c',
        ROOT/'scripts/xmega65-safe-run.sh', ROOT/'scripts/kill-xmega65-by-token.py',
        ARCH/'set-b-read-path-repair-20260926.json', ARCH/'set-b-seed-qualification-halt-20260926.json',
        ROOT/boot['world']['binary']['path'], ROOT/'build/card-l-r1/instrument-comfort.json',
        ROOT/'build/input-cost-attribution-r6/xemu/targets/mega65/mega65.c',
        ROOT/'build/input-cost-attribution-r6/xemu/targets/mega65/uart_monitor.c'])
    # Compiler input closure binds external generated sources as well as files
    # inside the four output roots. Preserve those external build inputs too.
    def add_bindings(value):
        if isinstance(value, dict):
            if {'path', 'sha256', 'bytes'} <= value.keys():
                path = ROOT/value['path']
                assert P.bind(path) == value, value['path']
                selected.add(path)
            else:
                for item in value.values():
                    add_bindings(item)
        elif isinstance(value, list):
            for item in value:
                add_bindings(item)
    add_bindings(P.load(S.OUT/'closure-r1/compiler-inputs.json'))
    toolchain = [P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ['mos-mega65-clang', 'llvm-objdump', 'llvm-readobj']]
    aggregator = Path('/usr/bin/llvm-link')
    raw = aggregator.read_bytes()
    external_toolchain = [dict(path=str(aggregator), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())]
    scope = ARCH/STEM/'owner-scope.txt'
    scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Freigabe erteilt; fourth attempt, no implicit retry.\n\n' +
        subprocess.check_output(['git', 'show', '8c0f3289:docs/planning/post-2.4.0-plan.md'], cwd=ROOT, text=True))
    inputs, copies = [], []
    for path in sorted(selected):
        bound = P.bind(path)
        inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):
            continue
        data = path.read_bytes()
        compressed = len(data) > 131072
        dest = ARCH/STEM/path.relative_to(ROOT)
        if compressed:
            dest = dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True, exist_ok=True)
        assert not dest.exists()
        dest.write_bytes(gzip.compress(data, compresslevel=9, mtime=0) if compressed else data)
        copies.append(dict(source=bound, copy=P.bind(dest), encoding='gzip' if compressed else 'identity'))
    P.write(SEAL, dict(status='FOURTH SEED INVENTORY CLOSED; POSITIVE ACTIVATION HALT',
        source_authority=authority, execution_head='8c0f3289', owner_scope=P.bind(scope),
        accepted_world='Card L Final', public_release='2.4.0', report=P.bind(REPORT),
        seed=boot['world']['ELF'], medium=boot['world']['medium'],
        consumed=dict(seed_attempts=4, finals=0, product_link_attempts=4),
        authorized_ceiling=dict(seed_attempts=4, finals=1, product_link_attempts=4),
        further_product_link_authorized=False,
        this_continuation=dict(admission_object_compiles=148, seed_compile_roots=74,
            llvm_aggregations=1, product_links=1, cold_stager_links=4,
            dependency_only_calls=2, guest_launches=1, observer_builds=0, device_contacts=0, finals=0),
        first_executed_failure='UNKNOWN; static busy conflict does not supply an executed boundary trace',
        inputs=inputs, toolchain=toolchain, external_toolchain=external_toolchain, receipt_copies=copies, excluded=excluded))
    print('SEALED', len(inputs), 'inputs;', len(copies), 'lossless copies')


def check():
    seal = P.load(SEAL)
    for row in seal['inputs'] + seal['toolchain'] + [seal['owner_scope']]:
        assert P.bind(ROOT/row['path']) == row, row['path']
    for row in seal['external_toolchain']:
        raw = Path(row['path']).read_bytes()
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    for row in seal['receipt_copies']:
        source, copy = row['source'], row['copy']
        assert P.bind(ROOT/copy['path']) == copy
        data = (ROOT/copy['path']).read_bytes()
        if row['encoding'] == 'gzip':
            data = gzip.decompress(data)
        assert len(data) == source['bytes'] and hashlib.sha256(data).hexdigest() == source['sha256']
    print('PASS fourth halt seal; all input bindings and lossless copies')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['create', 'check'])
    args = ap.parse_args()
    create() if args.mode == 'create' else check()
