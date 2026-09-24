"""Off-product native-diet experiment; never links or overwrites sealed inputs.

Object prices are paired, non-LTO projections, not a Seed or final-link price.
Every header is checked against the accepted producer's include closure before
code generation. Product sources are not changed by this experiment.
"""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import argparse
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/definition-set-a-product-r2/wplto'
OUT = ROOT / 'build/native-diet-object-probe-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, data):
    raw = data.encode() if isinstance(data, str) else data
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('refusing to overwrite experiment: ' + str(path))
    if not path.exists():
        path.write_bytes(raw)


def run(command):
    return subprocess.check_output(command, cwd=ROOT, text=True,
                                   stderr=subprocess.STDOUT)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    OUT = parser.parse_args().out.resolve()
    if not OUT.is_relative_to(ROOT / 'build'):
        raise ValueError('experiment outputs must stay under build/')
    OUT.mkdir(parents=True, exist_ok=True)
    proof = json.loads((BASE / 'command-proof.json').read_text())
    command = next(c for c in proof['commands']
                   if '-c' in c and c[c.index('-c') + 1].endswith('/vm.c'))
    source = ROOT / command[command.index('-c') + 1]
    original = source.read_text()
    candidate = original
    # For a 16-bit tagged fixnum, the byte domain is exactly the odd
    # representations 1..511. Check the domain before unsigned decoding.
    replacements = {
        '!IS_FIX(value)\n        || (uint16_t)FIXVAL(value) > 255u':
        '!IS_FIX(value)\n        || (uint16_t)value > 511u',
        '!IS_FIX(lo) || !IS_FIX(hi) || (uint16_t)FIXVAL(lo) > 255u\n        || (uint16_t)FIXVAL(hi) > 255u':
        '!IS_FIX(lo) || !IS_FIX(hi) || (uint16_t)lo > 511u\n        || (uint16_t)hi > 511u',
        'crc = (uint16_t)FIXVAL(lo) | ((uint16_t)FIXVAL(hi) << 8);\n    crc ^= (uint16_t)FIXVAL(value) << 8;':
        'crc = ((uint16_t)lo >> 1) | (((uint16_t)hi >> 1) << 8);\n    crc ^= ((uint16_t)value >> 1) << 8;',
    }
    for before, after in replacements.items():
        if candidate.count(before) != 1:
            raise ValueError('CRC source population drift: ' + before)
        candidate = candidate.replace(before, after, 1)
    masked = candidate.replace(
        '!IS_FIX(value)\n        || (uint16_t)value > 511u',
        '((uint16_t)value & 0xfe01u) != 1u', 1).replace(
        '!IS_FIX(lo) || !IS_FIX(hi) || (uint16_t)lo > 511u\n        || (uint16_t)hi > 511u',
        '((uint16_t)lo & 0xfe01u) != 1u\n        || ((uint16_t)hi & 0xfe01u) != 1u', 1)
    for encoded in range(65536):
        signed = encoded if encoded < 32768 else encoded - 65536
        old = bool(encoded & 1) and ((signed >> 1) & 65535) <= 255
        new = bool(encoded & 1) and encoded <= 511
        assert old == new
        assert old == ((encoded & 0xfe01) == 1)
        if new:
            assert (signed >> 1) == (encoded >> 1)

    closure_path = BASE / 'active-include-check/receipt.json'
    closure = json.loads(closure_path.read_text())
    allowed = {}
    for row in closure['rows']:
        for dep in row['dependencies']:
            p = (ROOT / dep['path']).resolve()
            if p in allowed and allowed[p] != dep['sha256']:
                raise ValueError('ambiguous include provenance: ' + str(p))
            allowed[p] = dep['sha256']
    flags = command[1:command.index('-c')]
    compiler = command[0]
    results = []
    for name, text in [('baseline', original), ('encoded-byte-domain', candidate),
                       ('masked-byte-domain', masked)]:
        src = OUT / (name + '.c')
        obj = OUT / (name + '.o')
        put(src, text)
        dependencies = run([compiler, *flags, '-M', '-MT', 'probe', str(src)])
        put(OUT / (name + '.d'), dependencies)
        paths = shlex.split(dependencies.replace('\\\n', ' ').split(':', 1)[1])
        headers = []
        for path in paths:
            p = (ROOT / path).resolve()
            if p == src.resolve():
                continue
            if p not in allowed or sha(p) != allowed[p]:
                raise ValueError('include outside accepted path/SHA closure: ' + str(p))
            headers.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p)})
        if obj.exists():
            raise ValueError('choose a fresh experiment directory before compiling')
        compile_command = [compiler, *flags, '-fno-lto', '-c', str(src), '-o', str(obj)]
        put(OUT / (name + '.compile.log'), run(compile_command))
        truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
        put(OUT / (name + '.symbols'), ''.join(
            '%08x %08x %s\n' % (row.value, row.bytes, row.name)
            for row in sorted(truth.symbols, key=lambda row: (row.bytes, row.name))))
        helper = truth.symbol('vm_index_crc_step')
        disassembly = run([str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'),
                          '-dr', '--disassemble-symbols=vm_index_crc_step', str(obj)])
        put(OUT / (name + '.disassembly'), disassembly)
        results.append({'variant': name, 'helper_bytes': helper.bytes,
                        'object_sha256': sha(obj), 'source_sha256': sha(src),
                        'headers': headers, 'command': compile_command})
    receipt = {'claim': 'PAIRED NON-LTO OBJECT PROJECTION ONLY; NOT PRODUCT PRICE',
               'seed_consumption': 0, 'final_consumption': 0, 'link_consumption': 0,
               'compiler_sha256': sha(Path(compiler)),
               'command_proof_sha256': sha(BASE / 'command-proof.json'),
               'include_closure_sha256': sha(closure_path),
               'byte_domain_encodings_checked': 65536, 'results': results,
               'projected_helper_saving': results[0]['helper_bytes'] - results[1]['helper_bytes']}
    receipt['projected_masked_helper_saving'] = results[0]['helper_bytes'] - results[2]['helper_bytes']
    put(OUT / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'results'}, indent=2))
    print([(r['variant'], r['helper_bytes']) for r in results])


if __name__ == '__main__':
    main()
