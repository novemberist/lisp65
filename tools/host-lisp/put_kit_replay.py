"""Actual historical boot requests, actual candidate C, shared name scratch.

Historical requests test semantic parity, not current boot timing. Repeat
after simulated abort/rollback with an intervening linear intern. The
resident abort driver's unchanged invalidation is independently inspected.
"""
import argparse
import json
from pathlib import Path
import subprocess

import put_kit_host as H
import put_kit_objects as P


MAIN = r'''
static obj lookup(const char *name, uint16_t *indexed) {
    uint8_t row[8] = {0}; strcpy(query, name); row[3] = strlen(name);
    obj result = c2_publish_bnx_lookup(row, indexed);
    return result == NIL ? linear(name) : result;
}
int main(void) {
    obj expected[REQUESTS]; uint16_t counts[REQUESTS], indexed = 0;
    char expected_names[1008][34]; uint16_t expected_count;
    for (unsigned i = 0; i < REQUESTS; ++i) {
        expected[i] = linear(requests[i]); counts[i] = count;
    }
    expected_count = count; memcpy(expected_names, names, sizeof names);
    memset(names, 0, sizeof names); count = 0; creates = 0;
    for (unsigned i = 0; i < REQUESTS; ++i) {
        obj value = phases[i] >= 8 ? lookup(requests[i], &indexed) : linear(requests[i]);
        assert(value == expected[i] && count == counts[i]);
    }
    assert(count == expected_count && !memcmp(names, expected_names, sizeof names));
    /* Abort/rollback at many boundaries: the owner must die before retry.
     * Deliberately create a different spelling at the rolled-back index. */
    for (unsigned stop = 1; stop < REQUESTS; stop += 37) {
        memset(names, 0, sizeof names); memset(table, 0, sizeof table);
        count = 0; indexed = 0;
        for (unsigned i = 0; i < stop; ++i) (void)lookup(requests[i], &indexed);
        count = 0; memset(names, 0, sizeof names);
        (void)linear("%put-kit-abort-witness");
#ifndef OMIT_INVALIDATION
        memset(table, 0, sizeof table); indexed = 0;
#endif
        for (unsigned i = 0; i < REQUESTS; ++i) {
            obj value = lookup(requests[i], &indexed);
            assert(value == expected[i] + 1 && count == counts[i] + 1);
        }
    }
    printf("PASS %u recorded requests, %u canonical symbols, shared scratch, abort/retry boundaries\n",
           REQUESTS, expected_count);
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = P.ROOT / args.out
    out.mkdir(parents=True, exist_ok=False)
    census = P.ROOT / 'build/native-diet-intern-census-r1/capture-r1/intern.txt'
    rows = [line.split() for line in census.read_text().splitlines()]
    assert all(len(r) == 10 and r[0] == 'N' for r in rows)
    names = [r[9] for r in rows]
    assert all(len(n) <= 33 and n.isascii() for n in names)
    decoder = P.ROOT / 'config/put-kit-native/includes/c2-stream-v2-decoder.c'
    runtime = P.ROOT / 'src/c2_product_runtime.c'
    body = ''.join(H.function(decoder.read_text(), s) for s in
                   ('uint16_t v2_bnx_hash(', 'obj v2_bnx_find(', 'void v2_bnx_catch_up('))
    body += H.function(runtime.read_text(), 'static obj c2_publish_bnx_lookup(')
    preamble = H.PREAMBLE.replace(
        'static const char *symname(obj i) { assert(i < count); return names[i]; }',
        'static char scratch[34];\n'
        'static const char *symname(obj i) { assert(i < count);\n'
        '    memcpy(scratch, names[i], sizeof scratch); return scratch; }')
    header = '#define REQUESTS %du\n' % len(rows)
    header += 'static const char *requests[] = {' + ','.join(json.dumps(n) for n in names) + '};\n'
    header += 'static unsigned phases[] = {' + ','.join(r[1] for r in rows) + '};\n'
    results = []
    for variant in ('candidate', 'old-owner-after-abort'):
        source = out / (variant + '.c')
        source.write_text(('#define OMIT_INVALIDATION\n' if variant != 'candidate' else '')
                          + preamble + header + body + MAIN)
        binary = source.with_suffix('')
        subprocess.run(['cc', '-std=c99', '-O1', '-g', '-fsanitize=address,undefined',
                        '-fno-pie', '-no-pie', str(source), '-o', str(binary)], check=True)
        run = subprocess.run([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=30)
        (out / (variant + '.log')).write_text(run.stdout)
        assert (run.returncode == 0) == (variant == 'candidate'), run.stdout
        results.append(dict(variant=variant, returncode=run.returncode, output=run.stdout,
                            source_sha256=P.sha(source)))
    value = dict(claim='HISTORICAL REQUEST SEMANTIC REPLAY; NOT CURRENT TIMING OR NATIVE RECOVERY',
                 inputs=[dict(path=str(p.relative_to(P.ROOT)), sha256=P.sha(p))
                         for p in (census, decoder, runtime, Path(__file__), Path(H.__file__))],
                 requests=len(rows), names=len(set(names)), results=results)
    (out / 'receipt.json').write_text(json.dumps(value, indent=2) + '\n')
    print('put-kit-replay: PASS, shared scratch and abort mutation')


if __name__ == '__main__':
    main()
