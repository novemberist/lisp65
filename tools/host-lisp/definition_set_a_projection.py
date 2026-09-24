"""Set-A isolated object pricing. No WPLTO, product link or artifact overwrite."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = '91cbb479'


def bind(path):
    path = path.resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tool = ROOT / 'tools/llvm-mos/bin'
    generated = ROOT / 'build/transient-retirement-final-medium-r1/materialized/generated-product-sources'
    base = json.loads((ROOT / 'build/append-name-pricing-r1/hash-index-command.json').read_text())
    if '-fno-lto' not in base or '-c' not in base:
        raise ValueError('not an isolated-object command')
    rows = []
    for name in ('c2_product_runtime', 'c2_session_emitter'):
        canonical = f'src/{name}.c'
        before = out / f'{name}-before.c'
        if name == 'c2_product_runtime':
            # Keep all consumed source adaptations. Apply only this card's
            # canonical diff, with zero fuzzy context matching.
            before.write_bytes((generated / f'{name}.c').read_bytes())
        else:
            before.write_bytes(subprocess.check_output(
                ['git', 'show', f'{BASE_COMMIT}:{canonical}'], cwd=ROOT))
        after = out / f'{name}-after.c'
        delta = subprocess.check_output(['git', 'diff', BASE_COMMIT, '--', canonical], cwd=ROOT)
        (out / f'{name}.patch').write_bytes(delta)
        patched = subprocess.run(['patch', '--batch', '--fuzz=0', str(before),
                                  '-o', str(after)], input=delta, capture_output=True)
        (out / f'{name}-patch.log').write_bytes(patched.stdout + patched.stderr)
        patched.check_returncode()
        objects = {}
        for world, source in [('before', before), ('after', after)]:
            obj = source.with_suffix('.o')
            dep = source.with_suffix('.d')
            cmd = list(base)
            cmd[cmd.index('build/append-name-pricing-r1/hash-index-projection.c')] = str(source)
            cmd[cmd.index('-o')+1] = str(obj)
            cmd[cmd.index('-MF')+1] = str(dep)
            cmd += ['-Isrc']
            compiled = subprocess.run(cmd, cwd=ROOT, capture_output=True)
            source.with_suffix('.log').write_bytes(compiled.stdout + compiled.stderr)
            compiled.check_returncode()
            truth = ElfTruth.read(obj, llvm_readobj=tool / 'llvm-readobj')
            objects[world] = {s.name: s.bytes for s in truth.sections
                              if s.name.startswith(('.text', '.rodata', '.bss', '.lisp65'))}
            rows.append(dict(unit=name, world=world, command=cmd,
                             source=bind(source), object=bind(obj), sections=objects[world]))
        changes = [dict(section=s, before=objects['before'].get(s, 0),
                        after=objects['after'].get(s, 0),
                        delta=objects['after'].get(s, 0)-objects['before'].get(s, 0))
                   for s in sorted(objects['before'].keys() | objects['after'].keys())
                   if objects['before'].get(s, 0) != objects['after'].get(s, 0)]
        rows.append(dict(unit=name, changes=changes))
    receipt = dict(status='ISOLATED PROJECTION; NOT SEED ADMISSION', rows=rows,
                   budget=dict(seed=0, final=0, product_link=0),
                   limits=['No native integrated group/capacity execution',
                           'No whole-product placement or LTO delta'],
                   inputs=[bind(ROOT / 'src/c2_product_runtime.c'),
                           bind(ROOT / 'src/c2_product_runtime.h'),
                           bind(ROOT / 'src/c2_session_emitter.c'),
                           bind(Path(__file__)), bind(tool / 'mos-mega65-clang')])
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps([r for r in rows if 'changes' in r], indent=2))


if __name__ == '__main__':
    main()
