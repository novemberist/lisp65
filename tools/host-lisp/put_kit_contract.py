"""Live Put-Kit C contract, with isolated outputs and no product build."""
from pathlib import Path
import subprocess
import tempfile

import put_kit_host as H
import put_kit_objects as P
import put_kit_preflight as F


def main():
    decoder = (P.ROOT / 'config/put-kit-native/includes/c2-stream-v2-decoder.c').read_text()
    runtime = (P.ROOT / 'src/c2_product_runtime.c').read_text()
    F.lifetime(runtime)
    body = ''.join(H.function(decoder, signature) for signature in
                   ('uint16_t v2_bnx_hash(', 'obj v2_bnx_find(', 'void v2_bnx_catch_up('))
    body += H.function(runtime, 'static obj c2_publish_bnx_lookup(')
    preamble = H.PREAMBLE.replace(
        'static const char *symname(obj i) { assert(i < count); return names[i]; }',
        'static char scratch[34];\n'
        'static const char *symname(obj i) { assert(i < count);\n'
        '    memcpy(scratch, names[i], sizeof scratch); return scratch; }')
    source = preamble + body + H.TESTS
    cases = {'candidate': source,
             'hash-is-equality': source.replace('if (known[i] == name[i]) return MK_SYMI(idx);',
                                                'return MK_SYMI(idx);'),
             'omit-catch-up': source.replace('    v2_bnx_catch_up(indexed);', ''),
             'unbounded-probe': source.replace('while (left--) {', 'while (1) {')}
    with tempfile.TemporaryDirectory(prefix='lisp65-put-kit-contract-') as directory:
        out = Path(directory)
        for name, text in cases.items():
            assert name == 'candidate' or text != source
            path = out / (name + '.c')
            binary = path.with_suffix('')
            path.write_text(text)
            subprocess.run(['cc', '-std=c99', '-O1', '-fsanitize=address,undefined',
                            '-fno-pie', '-no-pie', str(path), '-o', str(binary)],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=out)
            try:
                run = subprocess.run([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=10, cwd=out)
                code = run.returncode
            except subprocess.TimeoutExpired:
                code = 124
            assert (code == 0) == (name == 'candidate'), name
    print('put-kit-contract: PASS live canonical equality, catch-up, bounded fallback; 3 mutations; isolated outputs')


if __name__ == '__main__':
    main()
