"""Seal host-only load preflight, including the cold-cost halt and failed tools."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from set_b_fourth_halt_seal_20260926 import local_import_closure

ROOT = P.ROOT
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'set-b-library-load-preflight-20260926'
SEAL = ARCH/(STEM+'.json')
REPORT = ROOT/'docs/planning/set-b-library-load-preflight-report.md'
CLOSURE = ROOT/'build/set-b-load-preflight-close-r1/receipt.json'


def external_binding(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    authority = S.require_auth()
    closure = P.load(CLOSURE)
    assert closure['status'] == 'HOST PREFLIGHT CLOSED; NATIVE COLD COST REMAINS AN ADMISSION HALT'
    assert closure['gross_object_instruction_floor'] == 478650
    assert closure['additional_product_budget_requested'] is False
    selected = set()
    for root in sorted((ROOT/'build').glob('set-b-load-preflight-*')):
        selected.update(p for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file())

    # All bound inputs of successful receipts and native dependency closures.
    # Failed harness files are copied verbatim, never promoted to passing rows.
    def add_bindings(value):
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= value.keys():
                bound = {k: value[k] for k in ('path', 'bytes', 'sha256')}
                path = ROOT/bound['path']
                assert P.bind(path) == bound, bound['path']
                selected.add(path)
            else:
                for item in value.values():
                    add_bindings(item)
        elif isinstance(value, list):
            for item in value:
                add_bindings(item)

    for path in sorted(selected):
        if path.name in ('receipt.json', 'commands.json', 'binding.json'):
            add_bindings(P.load(path))
    for attempt in ('native-r1', 'native-r2'):
        for row in P.load(ROOT/f'build/set-b-load-preflight-{attempt}/commands.json'):
            assert row['exit'] == row['dependencies']['exit'] == 0
    selected.update(ROOT/p for p in S.authority_files())
    newtools = sorted((ROOT/'tools/host-lisp').glob('set_b_load_preflight*_20260926.py'))
    newtools += sorted((ROOT/'tools/host-lisp').glob('set_b_host_snapshot_heap*_20260926.py'))
    selected.update(local_import_closure(newtools))
    selected.update([
        REPORT, ARCH/'set-b-library-load-attribution-20260926.json',
        ROOT/'lib/stdlib-require.lisp', ROOT/'lib/stdlib-load.lisp',
        ROOT/'config/bytecode-abi-ledger.json', ROOT/'src/c2_bank2_code_domain.h',
        ROOT/'build/set-b-r1/step2/b-boundary.md',
        ROOT/'build/set-b-load-repair-proposal-r5/authored.patch',
        ROOT/'build/set-b-load-analysis-r2/receipt.json',
        ROOT/'build/nested-error-recovery-product-r1-preflight/setup-owned/static-plane/narrow-static/product/substitution-artifacts.json',
        S.PRODUCT/'wplto/resident-island-seed.prg.elf',
        ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81',
        ROOT/'build/set-b-seed-medium-r6/base/init.l65',
        ROOT/'build/input-cost-attribution-r6/xemu/xemu/cpu65.c',
        ROOT/'build/input-cost-attribution-r6/xemu/xemu/cpu65_mega65_timings.h',
    ])
    # Include all planes consumed by the discarded reference-VM instruments.
    for count in range(3):
        folder = ROOT/f'build/set-b-load-attribution-r1/definitions-{count}'
        selected.update(folder.glob('*-c2d.bin'))
        selected.update(folder.glob('*-bank2.bin'))
        selected.update(folder.glob('*-bank0.bin'))
    scope = ARCH/STEM/'owner-scope.txt'
    scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Dann bitte gemäß deiner Empfehlung fortfahren. '
                     'Continue host-only cost/packing/consumer preflight proposed in 519a1be2; '
                     'zero product builds/links/Seeds/device. No sixth Seed.\n\n' +
                     subprocess.check_output(['git', 'show',
                         '519a1be2:docs/planning/set-b-library-load-attribution-report.md'],
                         cwd=ROOT, text=True))
    inputs, copies = [], []
    for path in sorted(selected):
        bound = P.bind(path)
        inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):
            continue
        raw = path.read_bytes()
        compressed = len(raw) > 131072
        dest = ARCH/STEM/path.relative_to(ROOT)
        if compressed:
            dest = dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True, exist_ok=True)
        assert not dest.exists()
        dest.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0) if compressed else raw)
        copies.append(dict(source=bound, copy=P.bind(dest), encoding='gzip' if compressed else 'identity'))
    toolchain = [P.bind(ROOT/'tools/llvm-mos/bin'/n)
                 for n in ('mos-mega65-clang', 'llvm-objdump', 'llvm-readobj')]
    external = [external_binding(Path(shutil.which(n))) for n in ('cc', 'sbcl', 'python3')]
    sbcl_core = Path('/usr/lib/sbcl/sbcl.core')
    if sbcl_core.exists():
        external.append(external_binding(sbcl_core))
    P.write(SEAL, dict(
        status=closure['status'], source_authority=authority, execution_head='519a1be2',
        owner_scope=P.bind(scope), report=P.bind(REPORT), closure=P.bind(CLOSURE),
        accepted_world='Card L Final', public_release='2.4.0',
        consumed=closure['consumed'], authorized_ceiling=dict(seeds=5, finals=1, product_links=5),
        further_seed_or_product_link_authorized=False,
        this_commission=closure['this_commission'], inputs=inputs, receipt_copies=copies,
        toolchain=toolchain, external_toolchain=external,
        limits='Non-LTO native cost projection, SBCL publication replay and scalar query seam; '
               'actual C tested separately. Three failed reference-VM attempts discarded. '
               'No product consumer/native qualification or full source run claimed.'))
    print('SEALED', len(inputs), 'inputs;', len(copies), 'lossless archive copies')


def check():
    seal = P.load(SEAL)
    for row in seal['inputs'] + seal['toolchain'] + [seal['owner_scope']]:
        assert P.bind(ROOT/row['path']) == row, row['path']
    for row in seal['external_toolchain']:
        assert external_binding(Path(row['path'])) == row, row['path']
    for row in seal['receipt_copies']:
        path = ROOT/row['copy']['path']
        assert P.bind(path) == row['copy']
        raw = path.read_bytes()
        if row['encoding'] == 'gzip':
            raw = gzip.decompress(raw)
        assert len(raw) == row['source']['bytes']
        assert hashlib.sha256(raw).hexdigest() == row['source']['sha256']
    S.require_auth()
    print('PASS preflight seal: immutable source authority, identities and lossless copies')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('create', 'check'))
    create() if parser.parse_args().mode == 'create' else check()
