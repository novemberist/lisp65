"""Retained-callable repair: budget-free non-LTO object probe of both members.

Compiles the two affected translation units of the accepted dirty-anchor Seed
(the generated sources the anchor Final consumed) twice, with the product's
own recorded compiler commands, into a scratch directory:

  baseline  the consumed generated tree, unchanged;
  repaired  the same tree with the successor v2 decoder of
            config/retained-callable-repair-native/ and the commissioned
            src/c2_product_runtime.c hunk (git diff DIFF_BASE) projected with
            exact context onto the consumed generated runtime.

Codegen is forced with -fno-lto, so every number is a NON-LTO PROJECTION, not
the product's linked price.  No link, no Seed, no product artefact; nothing in
build/dirty-anchor-product-r1 is written.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-repair-object-probe-r2'
# r1 priced the first drafted form (c2_record_u16/c2_u16: +69 non-LTO bytes);
# it is kept.  r2 prices the committed byte-copy form.
PROOF = ROOT / 'build/dirty-anchor-product-r1/wplto/command-proof.json'
GENERATED = ROOT / 'build/dirty-anchor-product-r1/wplto/generated-product-sources'
DECODER = ROOT / 'config/retained-callable-repair-native/includes/c2-stream-v2-decoder.c'
PREDECESSOR_DECODER = ROOT / 'config/put-kit-native/includes/c2-stream-v2-decoder.c'
DIFF_BASE = 'd3d5044b'
UNITS = ('c2-stream-v2-phase-12.c', 'c2_product_runtime.c')


def bind(path):
    path = Path(path).resolve()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def sizes(obj):
    text = subprocess.run([str(ROOT / 'tools/llvm-mos/bin/llvm-readobj'),
                           '--elf-output-style=JSON', '--sections', str(obj)],
                          check=True, text=True, stdout=subprocess.PIPE).stdout
    data = json.loads(text)
    rows = {}
    for item in data[0]['Sections'] if isinstance(data, list) else data['Sections']:
        section = item['Section']
        rows[section['Name']['Name']] = section['Size']
    return rows


def project(text, diff, name):
    parts = re.split(r'(^@@[^\n]*\n)', diff, flags=re.M)
    if len(parts) < 3:
        raise ValueError('commissioned hunk absent: ' + name)
    for i in range(2, len(parts), 2):
        lines = parts[i].splitlines(keepends=True)
        before = ''.join(l[1:] for l in lines if l[:1] in (' ', '-'))
        after = ''.join(l[1:] for l in lines if l[:1] in (' ', '+'))
        if text.count(before) != 1:
            raise ValueError('source projection hunk mismatch: ' + name)
        text = text.replace(before, after, 1)
    return text


def compile_once(command, label, unit):
    out = OUT / f'{label}-{unit.name}.o'
    argv = list(command) + ['-fno-lto']
    argv[argv.index('-o') + 1] = str(out)
    argv[argv.index('-c') + 1] = str(unit)
    log = OUT / f'{label}-{unit.name}.log'
    completed = subprocess.run(argv, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(f'$ {" ".join(argv)}\n{completed.stdout}')
    assert completed.returncode == 0, log.read_text()[-2000:]
    return dict(label=label, object=bind(out), sections=sizes(out), log=bind(log),
                warnings=completed.stdout.count('warning:'))


def main():
    if OUT.exists():
        raise SystemExit('fresh output required: ' + str(OUT))
    OUT.mkdir(parents=True)
    proof = json.loads(PROOF.read_text())
    base_dir, patched_dir = OUT / 'baseline-sources', OUT / 'repaired-sources'
    shutil.copytree(GENERATED, base_dir)
    shutil.copytree(GENERATED, patched_dir)
    assert (GENERATED / 'c2-stream-v2-decoder.c').read_bytes() == PREDECESSOR_DECODER.read_bytes()
    (patched_dir / 'c2-stream-v2-decoder.c').write_bytes(DECODER.read_bytes())
    diff = subprocess.check_output(['git', 'diff', DIFF_BASE, '--', 'src/c2_product_runtime.c'],
                                   cwd=ROOT, text=True)
    (OUT / 'c2_product_runtime.c.patch').write_text(diff)
    runtime = patched_dir / 'c2_product_runtime.c'
    runtime.write_text(project(runtime.read_text(), diff, 'c2_product_runtime.c'))
    rows = []
    for name in UNITS:
        commands = [c for c in proof['commands']
                    if '-c' in c and Path(c[c.index('-c') + 1]).name == name]
        assert len(commands) == 1, name
        base = compile_once(commands[0], 'baseline', base_dir / name)
        fix = compile_once(commands[0], 'repaired', patched_dir / name)
        delta = {k: fix['sections'].get(k, 0) - v for k, v in base['sections'].items()
                 if fix['sections'].get(k, 0) != v}
        delta.update({k: v for k, v in fix['sections'].items() if k not in base['sections']})
        rows.append(dict(unit=name, command_ordinal=proof['commands'].index(commands[0]),
                         baseline=base, repaired=fix, delta=delta))
    result = dict(
        status='PROJECTION ONLY: TWO TRANSLATION UNITS, NO LINK, NO SEED, NO PRODUCT ARTEFACT',
        binding='d3d5044b', diff_base=DIFF_BASE, command_proof=bind(PROOF),
        decoder=dict(predecessor=bind(PREDECESSOR_DECODER), successor=bind(DECODER)),
        runtime=dict(consumed=bind(GENERATED / 'c2_product_runtime.c'), projected=bind(runtime),
                     patch=bind(OUT / 'c2_product_runtime.c.patch')),
        rows=rows, driver=bind(Path(__file__)),
        product_builds=0, links=0, seeds=0, device_contacts=0)
    (OUT / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    for row in rows:
        print(row['unit'], 'delta', row['delta'], 'warnings', row['baseline']['warnings'],
              '->', row['repaired']['warnings'])


if __name__ == '__main__':
    sys.exit(main())
