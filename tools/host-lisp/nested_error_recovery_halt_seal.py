"""Seal the nested-error recovery halt evidence. No emulator, compiler, linker or product execution.

Binds every file of the card's evidence roots (mutable SD scratch copies and
the copied Xemu observer source tree excepted; the observer binary and header
stay bound through its build receipt), verifies every SHA binding found in
the card's JSON receipts, and commits copies of the small receipts.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'nested-error-recovery-halt-20260923'
ROOTS = ['build/nested-error-recovery-r1', 'build/nested-error-recovery-link-preprobe-r1',
         'build/nested-error-recovery-e000-preprobe-r1', 'build/nested-error-recovery-capacity-r1',
         'build/nested-error-recovery-capacity-seed-r1', 'build/nested-error-recovery-seed-inventory-r1',
         'build/nested-error-recovery-product-r1', 'build/nested-error-recovery-product-r1-preflight',
         'build/nested-error-recovery-seed-medium-r1', 'build/nested-error-recovery-native-boot-r1',
         'build/nested-error-recovery-instrument-r1', 'build/input-cost-natural-nested-error-recovery-r1',
         'build/nested-error-recovery-ready-instrument-r1',
         'build/nested-error-recovery-gc-equal-baseline-1', 'build/nested-error-recovery-gc-equal-candidate-1',
         'build/nested-error-recovery-gates-nested-r1', 'build/nested-error-recovery-gates-depth2-r1']
LOOSE = ['build/nested-error-recovery-link-preprobe-r1.log', 'build/nested-error-recovery-e000-preprobe-r1.log',
         'build/nested-error-recovery-capacity-r1.log', 'build/nested-error-recovery-capacity-seed-r1.log',
         'build/nested-error-recovery-gc-pc-baseline-r1.txt', 'build/nested-error-recovery-gc-pc-candidate-r1.txt',
         'docs/planning/nested-error-recovery-halt-report.md', 'docs/planning/post-2.3.0-plan.md',
         'docs/planning/definitions-set-b-preflight.md', 'src/c2_product_runtime.c',
         'config/retained-callable-repair-r2-native/include-closure.json',
         'build/retained-callable-repair-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf',
         'build/retained-callable-repair-seed-medium-r2/packed/hardware-sp-seed.d81',
         'build/retained-callable-repair-r2/ready-instrument.json',
         'build/input-cost-natural-retained-callable-repair-r2/receipt.json',
         'build/anchor-cache-projection-r1/instrument.json']
COPY_LIMIT = 200_000
NO_COPY = ('generated-product-sources', 'objects', 'setup-owned', 'world-data-derivation')


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def excluded(path):
    parts = path.relative_to(ROOT).parts
    return path.name == 'system-sd.img' or 'observer' in parts[2:3] or \
        (len(parts) > 2 and parts[1] == 'nested-error-recovery-native-boot-r1' and parts[2] == 'observer') or \
        (len(parts) > 2 and parts[1] == 'nested-error-recovery-ready-instrument-r1' and parts[2] == 'xemu'
         and parts[-1] != 'xmega65.native')


def main():
    target = ARCH/(STEM+'.json')
    assert not target.exists()
    analysis = json.loads((ROOT/'build/nested-error-recovery-r1/halt-analysis.json').read_text())
    assert analysis['status'].startswith('HALT: GC PLACEMENT DELTA')
    assert analysis['budget_consumed'] == dict(seed=1, final=0, product_link=0, device=0, replacement_seed=0)
    selected, closure, copies, skipped = set(), {}, [], []
    for root in ROOTS:
        for p in (ROOT/root).rglob('*'):
            if p.is_file() and not p.is_symlink():
                if excluded(p.resolve()):
                    skipped.append(str(p.relative_to(ROOT)))
                else:
                    selected.add(p.resolve())
    selected.update((ROOT/'tools/host-lisp').glob('nested_error_recovery_*.py'))
    selected.update(ROOT/p for p in LOOSE)

    historical = {}
    superseded = []
    # Explicitly labelled intermediate states of the pack pipeline (the D81
    # before its boot stamp); recorded, not verified against the final file.
    INTERMEDIATE = ('medium_before_boot_stamp',)
    TRACKED_AT_HEAD = ('docs/planning/post-2.3.0-plan.md',)
    at_head = []
    intermediate = []

    def verify(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                key = (value['path'], value['sha256'])
                if key in historical:
                    actual = bind(ROOT/historical[key])
                    assert actual['sha256'] == value['sha256'] and actual['bytes'] == value.get('bytes', actual['bytes'])
                    superseded.append(dict(bound=value, reconstructed=actual))
                    value = {k: v for k, v in value.items() if k not in ('path', 'sha256')}
                p = (ROOT/value['path']).resolve() if 'path' in value else None
                if p is not None and p.is_file() and p.is_relative_to(ROOT) and not excluded(p):
                    actual = bind(p)
                    if actual['sha256'] != value['sha256'] and value['path'] in TRACKED_AT_HEAD:
                        # A tracked document bound before this card's own
                        # later edit: it must equal the committed HEAD version.
                        committed = subprocess.check_output(['git', 'show', 'HEAD:'+value['path']], cwd=ROOT)
                        assert hashlib.sha256(committed).hexdigest() == value['sha256'], value['path']
                        at_head.append(dict(value))
                        value = dict(value, sha256=actual['sha256'], bytes=actual['bytes'])
                    assert actual['sha256'] == value['sha256'], value['path']
                    if isinstance(value.get('bytes'), int):
                        assert actual['bytes'] == value['bytes'], value['path']
                    closure[actual['path']] = actual
            for key, child in value.items():
                if key in INTERMEDIATE:
                    intermediate.append({key: child})
                    continue
                verify(child)
        elif isinstance(value, list):
            for child in value:
                verify(child)
    for p in sorted(selected):
        rel = p.relative_to(ROOT)
        if p.suffix == '.json' and rel.parts[0] == 'build' and \
                any(p.is_relative_to(ROOT/r) for r in ROOTS):
            value = json.loads(p.read_text())
            verify(value)
            if p.stat().st_size <= COPY_LIMIT and not any(x in rel.parts for x in NO_COPY):
                dest = ARCH/STEM/rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                assert not dest.exists()
                shutil.copyfile(p, dest)
                copies.append(bind(dest))
        row = bind(p)
        closure[row['path']] = row
    seal = dict(status=analysis['status'], binding='44c021ee', source_authority='90b5f9f2',
                producer_commit='2fb8df5c',
                source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                seed=analysis['seed'], budget_consumed=analysis['budget_consumed'],
                executed=['projection', 'command probe', 'link and E000 pre-probes', 'capacity', 'Seed',
                          'price', 'linked-byte inventory (address drift)', 'medium', 'cold boot', 'natural lanes',
                          'matched GC with branch-page and IRQ attribution (halt)', 'hot-branch pages',
                          'post-halt diagnostics: nested, depth2 (not verdicts)'],
                not_executed=analysis['not_executed'],
                inputs=sorted(closure.values(), key=lambda x: x['path']), receipt_copies=copies,
                superseded_driver_bindings=superseded, intermediate_bindings=intermediate,
                bound_at_head_before_halt_entry=at_head,
                excluded=dict(rule='mutable system-sd.img scratch copies; copied Xemu observer source trees (binaries bound)',
                              count=len(skipped)),
                device_contacts=0, final=0, product_links=0)
    target.write_text(json.dumps(seal, indent=2)+'\n')
    print('PASS:', len(closure), 'verified bindings;', len(copies), 'committed receipt copies; HALT preserved')


if __name__ == '__main__':
    main()
