"""Copy new card receipts and seal their immutable artifact closure, no producer."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from dirty_anchor_producer import ROOT

ARCH = ROOT / 'tests/bytecode/dialect-v2/evidence/architecture-blocks'

def binding(p):
    with p.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=digest)

def main():
    stage = sys.argv[1]
    assert stage in ('pre-final', 'final', 'halt')
    stem = 'dirty-anchor-' + stage + '-20260923'
    target = ARCH / (stem + '.json')
    assert not target.exists()
    roots = [ROOT / ('build/dirty-anchor-usage-' + r + '-r1') for r in ('baseline', 'candidate')]
    roots += sorted((ROOT/'build').glob('dirty-anchor-final-r*'))
    if stage != 'pre-final':
        roots += [ROOT/'build/dirty-anchor-check-source-r1', ROOT/'build/dirty-anchor-source-qualification-r1']
    files = set()
    # Keep writable SD scratch outside the seal; the actual mounted D81, screen,
    # memory snapshot and interpreter binary are bound by the original receipt.
    for root in roots:
        if root.exists():
            for p in root.rglob('*'):
                if p.is_file() and p.name != 'system-sd.img' and 'generated-0' not in p.parts:
                    files.add(p)
    for name in ('final-release-authority.md', 'gc-accepted.json', 'usage-baseline.log',
                 'usage-candidate.log', 'final-preflight.log', 'final-preflight-r2.log',
                 'final-preflight-r3.log', 'final-preflight-r4.log'):
        p = ROOT/'build/dirty-anchor-card-r1'/name
        if p.exists(): files.add(p)
    files.update((ROOT/'tools/host-lisp').glob('dirty_anchor_*.py'))
    config = ROOT/'config/dirty-anchor-seed.json'
    if config.exists(): files.add(config)
    copies = []
    copyroot = ARCH / stem
    for p in sorted(files):
        if p.suffix == '.json' and p.is_relative_to(ROOT/'build'):
            dest = copyroot / p.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            assert not dest.exists()
            shutil.copyfile(p, dest)
            copies.append(binding(dest))
    closure = {}
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and 'sha256' in value:
                p = (ROOT/value['path']).resolve()
                if p.is_file() and p.is_relative_to(ROOT):
                    actual = binding(p)
                    assert actual['sha256'] == value['sha256'], str(p)
                    if 'bytes' in value: assert actual['bytes'] == value['bytes'], str(p)
                    closure[actual['path']] = actual
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    for p in sorted(files):
        if p.suffix == '.json': visit(json.loads(p.read_text()))
        row = binding(p); closure[row['path']] = row
    receipt = dict(stage=stage, authority='e9ef6d57',
        evidence=list(sorted(closure.values(), key=lambda r:r['path'])), receipt_copies=copies,
        exclusions=['mutable system-sd.img scratch; full-check generated scratch tree'],
        budget='see Final invocation; this tool does not compile or link')
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(target.relative_to(ROOT), len(closure), 'files,',len(copies),'receipt copies')

if __name__ == '__main__': main()
