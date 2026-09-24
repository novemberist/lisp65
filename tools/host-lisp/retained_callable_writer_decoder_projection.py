"""ca9af627: object size projection for the phase-12 predicate repair.

Compiles the bound phase-12 translation unit alone, twice, into a scratch
directory with the product's own recorded flags.  This is a PROJECTION, not a
product build: there is no link, no Seed, no product artifact, and nothing in
build/dirty-anchor-product-r1 is written.
"""
import hashlib, json, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-writer-analysis-r1/projection'
PROOF = ROOT / 'build/dirty-anchor-product-r1/wplto/command-proof.json'
GENERATED = ROOT / 'build/dirty-anchor-product-r1/wplto/generated-product-sources'
DECODER = 'c2-stream-v2-decoder.c'
OLD = """                if (word != expected || !IS_BCODE((obj)word)
                    || BCODE_IDX((obj)word) != (uint16_t)(directory_base + local))
                    return v2_fail(c, C2_STREAM_ERR_RESOLUTION);"""
NEW = """                if (word != expected || !IS_BCODE((obj)word))
                    return v2_fail(c, C2_STREAM_ERR_RESOLUTION);"""


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


def compile_once(command, label, unit):
    out = OUT / f'{label}.o'
    # The product compiles this unit to LTO bitcode; a size projection needs
    # real target code, so codegen is forced here.  That makes every number
    # below a NON-LTO PROJECTION, not the product's own text cost.
    argv = list(command) + ['-fno-lto']
    argv[argv.index('-o') + 1] = str(out)
    argv[argv.index('-c') + 1] = str(unit)
    log = OUT / f'{label}.log'
    completed = subprocess.run(argv, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(f'$ {" ".join(argv)}\n{completed.stdout}')
    assert completed.returncode == 0, log.read_text()[-2000:]
    return dict(label=label, object=bind(out), sections=sizes(out), log=bind(log))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    proof = json.loads(PROOF.read_text())
    commands = [c for c in proof['commands'] if any('c2-stream-v2-phase-12.c' == Path(str(x)).name for x in c)]
    assert len(commands) == 1, 'phase 12 translation unit command not unique'
    command = commands[0]
    # Both arms compile a private copy of the generated source tree, so the only
    # difference between them is the one predicate.  The original tree is never
    # written to.
    base_dir = OUT / 'baseline-sources'
    patched_dir = OUT / 'patched-sources'
    for target in (base_dir, patched_dir):
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(GENERATED, target)
    source = (GENERATED / DECODER).read_text()
    assert source.count(OLD) == 1, 'phase 12 predicate text not found exactly once'
    (patched_dir / DECODER).write_text(source.replace(OLD, NEW))
    unit = 'c2-stream-v2-phase-12.c'
    result = dict(
        status='PROJECTION ONLY: ONE TRANSLATION UNIT, NO LINK, NO SEED, NO PRODUCT ARTEFACT',
        authority='ca9af627', translation_unit='c2-stream-v2-phase-12.c',
        decoder=bind(GENERATED / DECODER), patched=bind(patched_dir / DECODER),
        command_proof=bind(PROOF),
        baseline=compile_once(command, 'baseline', base_dir / unit),
        repaired=compile_once(command, 'repaired', patched_dir / unit),
        driver=bind(Path(__file__)), product_builds=0, links=0, seeds=0, device_contacts=0)
    base = result['baseline']['sections']
    fix = result['repaired']['sections']
    result['delta'] = {name: fix.get(name, 0) - size for name, size in base.items()
                       if fix.get(name, 0) != size}
    (OUT / 'projection.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    print('baseline', {k: v for k, v in base.items() if v})
    print('repaired', {k: v for k, v in fix.items() if v})
    print('delta', result['delta'])


if __name__ == '__main__':
    main()
