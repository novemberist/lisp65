"""Seal the retained-callable repair halt evidence. No emulator, compiler, linker or product execution.

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
STEM = 'retained-callable-repair-halt-20260923'
ROOTS = ['build/retained-callable-repair-r1', 'build/retained-callable-repair-object-probe-r1',
         'build/retained-callable-repair-object-probe-r2', 'build/retained-callable-repair-link-preprobe-r1',
         'build/retained-callable-repair-e000-preprobe-r1', 'build/retained-callable-repair-capacity-r1',
         'build/retained-callable-repair-capacity-seed-r1', 'build/retained-callable-repair-seed-inventory-r1',
         'build/retained-callable-repair-product-r1', 'build/retained-callable-repair-product-r1-preflight',
         'build/retained-callable-repair-seed-medium-r1', 'build/retained-callable-repair-native-boot-r1',
         'build/retained-callable-repair-instrument-r1', 'build/input-cost-natural-retained-callable-repair-r1',
         'build/retained-callable-repair-gc-equal-baseline-1', 'build/retained-callable-repair-gc-equal-candidate-1',
         'build/retained-callable-repair-usage-baseline-r1', 'build/retained-callable-repair-usage-candidate-r1',
         'build/retained-callable-repair-gates-lambda-r1']
LOOSE = ['build/retained-callable-repair-link-preprobe-r1.log', 'build/retained-callable-repair-e000-preprobe-r1.log',
         'build/retained-callable-repair-capacity-r1.log', 'build/retained-callable-repair-capacity-seed-r1.log',
         'build/retained-callable-repair-gc-pc-baseline-r1.txt', 'build/retained-callable-repair-gc-pc-candidate-r1.txt',
         'docs/planning/retained-callable-repair-halt-report.md', 'docs/planning/post-2.3.0-plan.md',
         'config/retained-callable-repair-native/include-closure.json',
         'config/retained-callable-repair-native/includes/c2-stream-v2-decoder.c', 'src/c2_product_runtime.c',
         'build/dirty-anchor-final-r3/wplto/lisp65-c2-substitution-linked.prg.elf',
         'build/dirty-anchor-seed-medium-r1/packed/hardware-sp-seed.d81',
         'build/anchor-cache-projection-r1/instrument.json',
         'build/input-cost-natural-anchor-final-r1/receipt.json',
         'build/dirty-anchor-card-r1/ready-instrument.json']
COPY_LIMIT = 200_000
NO_COPY = ('generated-product-sources', 'objects', 'setup-owned', 'world-data-derivation')


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def excluded(path):
    parts = path.relative_to(ROOT).parts
    return path.name == 'system-sd.img' or 'observer' in parts[2:3] or \
        (len(parts) > 2 and parts[1] == 'retained-callable-repair-native-boot-r1' and parts[2] == 'observer')


def main():
    target = ARCH/(STEM+'.json')
    assert not target.exists()
    analysis = json.loads((ROOT/'build/retained-callable-repair-r1/halt-analysis.json').read_text())
    assert analysis['status'].startswith('HALT: GATE 3 RED')
    assert analysis['budget_consumed'] == dict(seed=1, final=0, product_link=0, device=0)
    selected, closure, copies, skipped = set(), {}, [], []
    for root in ROOTS:
        for p in (ROOT/root).rglob('*'):
            if p.is_file() and not p.is_symlink():
                if excluded(p.resolve()):
                    skipped.append(str(p.relative_to(ROOT)))
                else:
                    selected.add(p.resolve())
    selected.update((ROOT/'tools/host-lisp').glob('retained_callable_repair_*.py'))
    selected.update(ROOT/p for p in LOOSE)

    # The r1 object probe ran an uncommitted earlier revision of its driver
    # (output directory r1 instead of r2, no comment).  That revision is
    # reconstructed byte-exactly as driver-as-run.py and bound instead.
    historical = {('tools/host-lisp/retained_callable_repair_object_probe.py',
                   '95fe9cd29c3078d5220262c14c33d263455238756e583054b52866f822eca3ce'):
                  'build/retained-callable-repair-object-probe-r1/driver-as-run.py'}
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
    seal = dict(status=analysis['status'], binding='d3d5044b', source_authority='e0be22c1',
                producer_commit='7f65ed14',
                source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                seed=analysis['seed'], budget_consumed=analysis['budget_consumed'],
                executed=['command probe', 'link and E000 pre-probes', 'capacity', 'Seed', 'linked-byte inventory',
                          'price', 'medium', 'cold boot', 'natural lanes', 'matched GC', 'usage (2 x 23 rows)',
                          'gate 3 lambda row (red)'],
                not_executed=analysis['not_executed'],
                inputs=sorted(closure.values(), key=lambda x: x['path']), receipt_copies=copies,
                superseded_driver_bindings=superseded, intermediate_bindings=intermediate,
                bound_at_head_before_halt_entry=at_head,
                excluded=dict(rule='mutable system-sd.img scratch copies; copied Xemu observer source tree',
                              count=len(skipped)),
                device_contacts=0, final=0, product_links=0)
    target.write_text(json.dumps(seal, indent=2)+'\n')
    print('PASS:', len(closure), 'verified bindings;', len(copies), 'committed receipt copies; HALT preserved')


if __name__ == '__main__':
    main()
