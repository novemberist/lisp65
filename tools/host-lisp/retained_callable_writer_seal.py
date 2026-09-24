"""ca9af627: seal the writer-attribution evidence.  No emulator, compiler, linker
or product execution.

  python3 -B retained_callable_writer_seal.py          write the seal (once)
  python3 -B retained_callable_writer_seal.py check    re-verify every binding
"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'retained-callable-writer-attribution-20260923'
TARGET = ARCH / (STEM + '.json')
ANALYSIS = ROOT / 'build/retained-callable-writer-analysis-r1'
RUNS = [ROOT / f'build/retained-callable-writer-r{i}' for i in (1, 2, 3, 4, 6)]
STATUS = 'WRITER ATTRIBUTED; 2.3.0 AFFECTED IN BOTH CLASSES; PARTIAL r2/r3 RECEIPTS AFTER HOST CRASH'
V230 = ROOT / 'build/retained-callable-writer-r1/v230/lisp65-2.3.0'
FIXED = [
    'docs/planning/retained-callable-writer-attribution.md',
    'build/dirty-anchor-final-r3/wplto/lisp65-c2-substitution-linked.prg.elf',
    'build/dirty-anchor-seed-medium-r1/packed/hardware-sp-seed.d81',
    'build/retained-callable-writer-r1/v230/lisp65-2.3.0/product/lisp65-c2-substitution-linked.prg.elf',
    'build/retained-callable-writer-r1/v230/lisp65-2.3.0/media/lisp65-product.d81',
    'build/release-v2.3.0/review-assets-r2/lisp65-2.3.0.tar.gz',
    'build/input-cost-attribution-r6/xemu/build/bin/xmega65.native',
    'build/input-cost-attribution-r6/xemu/targets/mega65/uart_monitor.c',
    'build/input-cost-attribution-r6/xemu/targets/mega65/mega65.c',
    'build/anchor-cache-projection-r1/instrument.json',
    'build/dirty-anchor-product-r1/wplto/command-proof.json',
    'build/retained-callable-attribution-r4/receipt.json',
    'tools/host-lisp/native_cycle_stationary.py', 'tools/host-lisp/dwx_retroactive_red_replay.py',
    'tools/host-lisp/dwx_comfort_resume.py', 'tools/host-lisp/dwx_mirrored_prefilter_rows.py',
    'tools/host-lisp/elf_truth.py', 'scripts/xmega65-safe-run.sh',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/retained-callable-attribution-halt-20260923.json',
] + [f'build/dirty-anchor-product-r1/wplto/generated-product-sources/{n}' for n in
     ['c2-stream-v2-decoder.c', 'c2-stream-decoder.h', 'c2_product_runtime.c', 'c2-stream-v2-phase-12.c',
      'c2_platform_dma.c']]
TOOLS = ['retained_callable_writer_probe_r1.py', 'retained_callable_writer_probe_r2.py',
         'retained_callable_writer_probe_r3.py', 'retained_callable_writer_probe_r4.py',
         'retained_callable_writer_probe_r6.py', 'retained_callable_writer_analysis.py',
         'retained_callable_writer_decoder_projection.py',
         'retained_callable_writer_partial_receipts.py', 'retained_callable_writer_seal.py']
LIMITATIONS = [
    'watch run r1 was driven by the previous worker\'s script; its receipts were re-verified and '
    're-analysed, not regenerated; its watchpoint was armed after (require "defstruct"), before the '
    'triggering form, not at boot',
    'no instruction trace of the rollback driver; the phase sequence is inferred from the resident '
    'overlay and the append-state fields',
    'the missing code_len / chip-code-base assignment in c2_append_rollback_prepare_phase is a source '
    'and disassembly attribution; the stale values themselves are measured bytes',
    'why a bare top-level (eval (quote (defun ...))) escapes (front depth zero) is a hypothesis',
    'r2 and r3 were killed by a host session crash inside their N = 54 loops; their receipts are '
    'partial, without shutdown memory, shutdown framebuffer or end-of-run medium check; medium copies '
    're-hashed unchanged afterwards',
    'the anchor N = 54 sweep row is the halt card\'s retained-callable-attribution-r4 run, not r2',
    'the phase-12 air figure is a non-LTO single-translation-unit projection, not product text; no '
    'projection was taken for the retirement-wipe repair',
    'no reset or persistence cycle; remaining setq/setf, function-in-data and returned-closure matrix '
    'not executed; no repair compiled into a product, linked, Seeded or executed; no budget claimed',
]


def bind(path):
    path = Path(path).resolve()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def selected_files():
    selected = set()
    for root in RUNS + [ANALYSIS]:
        for p in root.rglob('*'):
            if not p.is_file() or p.name == 'system-sd.img':
                continue
            if p.is_relative_to(V230):
                continue      # the release tree is bound through its archive, D81 and ELF only
            selected.add(p.resolve())
    for run in RUNS:
        log = ROOT / (str(run.relative_to(ROOT)) + '.log')
        if log.is_file():
            selected.add(log.resolve())
    selected.update((ROOT / 'tools/host-lisp' / n).resolve() for n in TOOLS)
    selected.update((ROOT / p).resolve() for p in FIXED)
    return selected


def receipt_jsons():
    rows = []
    for root in RUNS + [ANALYSIS]:
        for p in sorted(root.rglob('*.json')):
            if p.is_relative_to(V230) or '-sources' in str(p.relative_to(root)):
                continue
            rows.append(p.resolve())
    return rows


def verify_nested(value, closure):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and 'sha256' in value:
            p = Path(value['path'])
            p = (p if p.is_absolute() else ROOT / p).resolve()
            if p.is_file() and p.is_relative_to(ROOT) and p.name != 'system-sd.img':
                actual = bind(p)
                assert actual['sha256'] == value['sha256'], value['path']
                if 'bytes' in value:
                    assert actual['bytes'] == value['bytes'], value['path']
                closure[actual['path']] = actual
        for child in value.values():
            verify_nested(child, closure)
    elif isinstance(value, list):
        for child in value:
            verify_nested(child, closure)


def seal():
    assert not TARGET.exists(), 'seal is immutable; use check'
    assert not subprocess.check_output(['git', 'diff', 'HEAD', '--', 'src', 'lib', 'scripts'], cwd=ROOT)
    result = json.loads((ANALYSIS / 'attribution.json').read_text())
    assert result['status'].startswith('ATTRIBUTED')
    assert all(result[k] == 0 for k in ('product_builds', 'observer_builds', 'links', 'seeds', 'device_contacts'))
    projection = json.loads((ANALYSIS / 'projection/projection.json').read_text())
    assert projection['delta'].get('.lisp65_rt_c2d_12') == -21
    authority = ANALYSIS / 'authority-at-start.md'
    authority_bytes = subprocess.check_output(['git', 'show', 'ca9af627:docs/planning/post-2.3.0-plan.md'], cwd=ROOT)
    if authority.exists():
        assert authority.read_bytes() == authority_bytes
    else:
        authority.write_bytes(authority_bytes)
    closure, copies = {}, []
    for p in receipt_jsons():
        verify_nested(json.loads(p.read_text()), closure)
        dest = ARCH / STEM / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        assert not dest.exists()
        shutil.copyfile(p, dest)
        copies.append(dict(copy=bind(dest), source=bind(p)))
    for p in selected_files():
        row = bind(p)
        closure[row['path']] = row
    seal_row = dict(
        status=STATUS, authority='ca9af627', accepted_world='1e210f3f',
        source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        writer=result['writer'],
        minimal_failing_n=1, largest_passing_n=None,
        affected_population='exactly one object per triggering top-level form: the last persistent publication',
        release_2_3_0=dict(lambda_class='affected', capfill_class='affected'),
        phase12_projection=dict(ordinary_text=-21, e000=0, bank2=0, c2d=0, kind='non-LTO TU projection'),
        partial_receipts=['build/retained-callable-writer-r2/receipt.json',
                          'build/retained-callable-writer-r3/receipt.json'],
        inputs=sorted(closure.values(), key=lambda x: x['path']), receipt_copies=copies,
        product_builds=0, observer_builds=0, links=0, seeds=0, device_contacts=0,
        translation_unit_projections=1,
        excluded=['mutable system-sd.img scratch copies',
                  'extracted 2.3.0 release tree other than its D81 and ELF (bound via the archive)'],
        limitations=LIMITATIONS, repair_card_started=False, budget_claimed=False)
    TARGET.write_text(json.dumps(seal_row, indent=2) + '\n')
    print('SEALED:', TARGET.relative_to(ROOT), len(closure), 'bindings;', len(copies), 'receipt copies')


def check():
    data = json.loads(TARGET.read_text())
    assert data['status'] == STATUS
    bad = []
    for row in data['inputs']:
        p = ROOT / row['path']
        if not p.is_file() or bind(p)['sha256'] != row['sha256'] or p.stat().st_size != row['bytes']:
            bad.append(row['path'])
    for row in data['receipt_copies']:
        for side in ('copy', 'source'):
            p = ROOT / row[side]['path']
            if not p.is_file() or bind(p)['sha256'] != row[side]['sha256']:
                bad.append(row[side]['path'])
        if row['copy']['sha256'] != row['source']['sha256']:
            bad.append('copy differs: ' + row['copy']['path'])
    bound = {row['path'] for row in data['inputs']}
    for p in selected_files():
        if str(p.relative_to(ROOT)) not in bound and p.name != 'retained_callable_writer_seal.py':
            bad.append('unbound: ' + str(p.relative_to(ROOT)))
    if bad:
        print('FAIL:', len(bad), 'bindings'); [print('  ', b) for b in bad[:40]]
        raise SystemExit(1)
    print('PASS:', len(data['inputs']), 'bindings and', len(data['receipt_copies']), 'receipt copies re-verified')


if __name__ == '__main__':
    check() if sys.argv[1:] == ['check'] else seal()
