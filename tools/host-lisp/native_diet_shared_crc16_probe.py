"""Price reuse of the consumed CRC16 leaf; no new assembly implementation."""
import json
import shlex
from native_diet_object_probe import ROOT, BASE, sha, put, run
from elf_truth import ElfTruth
import c2_product_substitution_link as PRODUCT


def replace_body(text, signature, replacement):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[:opening] + '{\n' + replacement + '\n}' + text[end:]


def main():
    out = ROOT / 'build/native-diet-shared-crc16-probe-r2'
    out.mkdir(parents=True, exist_ok=True)
    proof = json.loads((BASE / 'command-proof.json').read_text())
    closure_path = BASE / 'active-include-check/receipt.json'
    closure = json.loads(closure_path.read_text())
    allowed = {(ROOT / d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}
    kernel_owner = (BASE / 'c2-kernal-window.generated.h').resolve()
    kernel_input = out / kernel_owner.name
    put(kernel_input, PRODUCT.kernal_header_values(PRODUCT.KERNAL_CRC_BINDING_SENTINEL, '0' * 64))
    if sha(kernel_input) != allowed[kernel_owner]:
        raise ValueError('materialized compiler sentinel differs from accepted input')
    allowed[kernel_input] = allowed[kernel_owner]
    results = []
    for name, helper, arguments in [
        ('vm_boot_overlay.c', 'ov_crc16', 'p, n'),
        ('c2_kernal_runtime.c', 'c2k_crc16', '(const uint8_t *)source, length'),
    ]:
        command = next(c for c in proof['commands'] if '-c' in c
                       and c[c.index('-c') + 1].endswith('/' + name))
        source = ROOT / command[command.index('-c') + 1]
        if source.resolve() not in allowed or sha(source) != allowed[source.resolve()]:
            raise ValueError('accepted source SHA drift: ' + name)
        original = source.read_text()
        candidate = replace_body(original, 'uint16_t ' + helper + '(',
            '    extern uint16_t rtov_crc_mem(const uint8_t *, uint16_t);\n'
            '    return rtov_crc_mem(' + arguments + ');')
        flags = command[1:command.index('-c')]
        for variant, text in [('baseline', original), ('shared-leaf', candidate)]:
            stem = name.removesuffix('.c') + '-' + variant
            src, obj = out / (stem + '.c'), out / (stem + '.o')
            put(src, text)
            deps = run([command[0], *flags, '-M', '-MT', 'probe', str(src)])
            put(out / (stem + '.d'), deps)
            inputs = []
            for path in shlex.split(deps.replace('\\\n', ' ').split(':', 1)[1]):
                p = (ROOT / path).resolve()
                if p != src and (p not in allowed or sha(p) != allowed[p]):
                    raise ValueError('unbound include: ' + str(p))
                inputs.append(dict(path=str(p.relative_to(ROOT)), sha256=sha(p)))
            if obj.exists():
                raise ValueError('experiment object already exists')
            cc = [command[0], *flags, '-fno-lto', '-c', str(src), '-o', str(obj)]
            put(out / (stem + '.log'), run(cc))
            truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
            sym = truth.symbol(helper)
            put(out / (stem + '.disassembly'), run([
                str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-dr',
                '--disassemble-symbols=' + helper, str(obj)]))
            results.append(dict(source=name, variant=variant, helper=helper,
                                helper_bytes=sym.bytes, inputs=inputs, command=cc,
                                object_sha256=sha(obj)))
    receipt = dict(claim='PAIRED CRC16 CALL-SEAM PROJECTION; NOT FULL ABI ACCEPTANCE',
                   budget=dict(seed=0, finale=0, link=0), results=results,
                   materialized_compiler_input=dict(path=str(kernel_input.relative_to(ROOT)),
                       sha256=sha(kernel_input), authority_path=str(kernel_owner.relative_to(ROOT))),
                   projected_saving=sum(r['helper_bytes'] * (1 if r['variant'] == 'baseline' else -1)
                                        for r in results),
                   required=['polynomial/init parity', 'exact consumed assembly leaf',
                             'native call ABI and zero-length/full-span cases',
                             'pre-ownership call closure', 'unchanged fail-closed gates'])
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    print([(r['helper'], r['variant'], r['helper_bytes']) for r in results])
    print('Paired helper saving:', receipt['projected_saving'])


if __name__ == '__main__':
    main()
