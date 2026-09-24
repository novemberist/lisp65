"""Paired off-product projection of resolver header validation; no link."""
import json
import shlex
import argparse
from elf_truth import ElfTruth
from pathlib import Path
from native_diet_object_probe import ROOT, BASE, sha, put, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-diet-bounds-probe-r3')
    out = parser.parse_args().out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('experiment output must stay under build/')
    out.mkdir(parents=True, exist_ok=True)
    proof = json.loads((BASE / 'command-proof.json').read_text())
    command = next(c for c in proof['commands'] if '-c' in c
                   and c[c.index('-c') + 1].endswith('/c2_product_runtime.c'))
    source = ROOT / command[command.index('-c') + 1]
    original = source.read_text()
    begin = original.index('static uint8_t c2_resolver_header_capacities(void) {')
    end = original.index('\n}\n', begin) + 2
    before = original[begin:end]
    after = '''static uint8_t c2_resolver_header_capacities(void) {
    uint8_t h[28];
    uint8_t field;
    const uint16_t *owner = c2_resolver_owner_parts + 2;
    uint8_t *p = h + 12;
    if (!c2_stream_c2d_read(0u, h, sizeof h)) return 0u;
    for (field = 4u; field; --field, p += 4, owner += 2) {
        uint8_t lo = (uint8_t)owner[0], hi = (uint8_t)owner[1];
        if (p[2] != lo || p[3] != hi || p[1] > hi
            || (p[1] == hi && p[0] > lo)) return 0u;
    }
    return c2_u16(h + 10) != 0u
        && c2_u16(h + 12) >= 6u
        && c2_u16(h + 8) >= C2D_ENTRY_CAP
        && c2_u16(h + 8) <= C2D_HANDLE_CAP;
}'''
    candidate = original[:begin] + after + original[end:]
    # Explicit native owners, not copied capacity literals. This permits the
    # compiler to fold the immutable field capacities before generating code.
    unrolled_body = '''static uint8_t c2_resolver_header_capacities(void) {
    uint8_t h[28];
    if (!c2_stream_c2d_read(0u, h, sizeof h)) return 0u;
    if (c2_u16(h + 14) != C2D_IMAGE_CAP || c2_u16(h + 12) > C2D_IMAGE_CAP
        || c2_u16(h + 18) != C2D_ENTRY_CAP || c2_u16(h + 16) > C2D_ENTRY_CAP
        || c2_u16(h + 22) != C2D_RESOLUTION_CAP || c2_u16(h + 20) > C2D_RESOLUTION_CAP
        || c2_u16(h + 26) != C2D_ROOT_CAP || c2_u16(h + 24) > C2D_ROOT_CAP) return 0u;
    return c2_u16(h + 10) != 0u
        && c2_u16(h + 12) >= 6u
        && c2_u16(h + 8) >= C2D_ENTRY_CAP
        && c2_u16(h + 8) <= C2D_HANDLE_CAP;
}'''
    unrolled = original[:begin] + unrolled_body + original[end:]
    byte_table = candidate.replace('static const uint16_t c2_resolver_owner_parts[]',
                                   'static const uint8_t c2_resolver_owner_parts[]', 1)
    byte_table = byte_table.replace('const uint16_t *owner = c2_resolver_owner_parts + 2;',
                                   'const uint8_t *owner = c2_resolver_owner_parts + 2;', 1)
    byte_body = '''static uint8_t c2_resolver_header_capacities(void) {
    uint8_t h[28];
    if (!c2_stream_c2d_read(0u, h, sizeof h)) return 0u;
#define FIELD(at, cap) (h[(at)+2] == ((cap)&255u) && h[(at)+3] == ((cap)>>8) \\
    && (h[(at)+1] < ((cap)>>8) || (h[(at)+1] == ((cap)>>8) && h[at] <= ((cap)&255u))))
    if (!FIELD(12, C2D_IMAGE_CAP) || !FIELD(16, C2D_ENTRY_CAP)
        || !FIELD(20, C2D_RESOLUTION_CAP) || !FIELD(24, C2D_ROOT_CAP)) return 0u;
#undef FIELD
    return c2_u16(h + 10) != 0u
        && c2_u16(h + 12) >= 6u
        && c2_u16(h + 8) >= C2D_ENTRY_CAP
        && c2_u16(h + 8) <= C2D_HANDLE_CAP;
}'''
    byte_unrolled = (original[:begin] + byte_body + original[end:]).replace(
        'static const uint16_t c2_resolver_owner_parts[]',
        'static const uint8_t c2_resolver_owner_parts[]', 1)
    # Exhaust every count for the four actual owner capacities; header
    # equality is the identical low/high-byte equality in both expressions.
    capacities = (64, 2048, 4096, 1536)
    for cap in capacities:
        for count in range(65536):
            hi, lo = cap >> 8, cap & 255
            new = (count >> 8) < hi or ((count >> 8) == hi and (count & 255) <= lo)
            assert new == (count <= cap)
    closure_path = BASE / 'active-include-check/receipt.json'
    closure = json.loads(closure_path.read_text())
    allowed = {(ROOT / d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}
    flags = command[1:command.index('-c')]
    results = []
    for name, text in [('baseline', original), ('byte-cursor', candidate),
                       ('native-owner-fields', unrolled), ('byte-owner-table', byte_table),
                       ('byte-owner-fields', byte_unrolled)]:
        src, obj = out / (name + '.c'), out / (name + '.o')
        put(src, text)
        deps = run([command[0], *flags, '-M', '-MT', 'probe', str(src)])
        put(out / (name + '.d'), deps)
        headers = []
        for path in shlex.split(deps.replace('\\\n', ' ').split(':', 1)[1]):
            p = (ROOT / path).resolve()
            if p == src:
                continue
            if p not in allowed or sha(p) != allowed[p]:
                raise ValueError('include provenance mismatch: ' + str(p))
            headers.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p)})
        if obj.exists():
            raise ValueError('experiment object already exists')
        compile_command = [command[0], *flags, '-fno-lto', '-c', str(src), '-o', str(obj)]
        put(out / (name + '.compile.log'), run(compile_command))
        truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
        put(out / (name + '.symbols'), ''.join(
            '%08x %08x %s\n' % (row.value, row.bytes, row.name)
            for row in sorted(truth.symbols, key=lambda row: row.name)))
        selected = truth.symbol('c2_resolver_owner_part')
        table = truth.symbol('c2_resolver_owner_parts')
        put(out / (name + '.disassembly'), run([
            str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-dr',
            '--disassemble-symbols=c2_resolver_owner_part', str(obj)]))
        results.append(dict(variant=name, bytes=selected.bytes,
                            table_bytes=table.bytes,
                            source_sha256=sha(src), object_sha256=sha(obj),
                            headers=headers, command=compile_command))
    receipt = dict(claim='PAIRED NON-LTO OBJECT PROJECTION; NOT PRODUCT PRICE',
                   budget=dict(seed=0, final=0, link=0),
                   source_sha256=sha(source), compiler_sha256=sha(Path(command[0])),
                   include_closure_sha256=sha(closure_path),
                   count_comparisons_checked=4 * 65536, results=results,
                   projected_saving=results[0]['bytes'] - results[1]['bytes'])
    receipt['projected_native_owner_saving'] = results[0]['bytes'] - results[2]['bytes']
    for r in results:
        r['projected_total_saving'] = (results[0]['bytes'] + results[0]['table_bytes']
                                      - r['bytes'] - r['table_bytes'])
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    print([(r['variant'], r['bytes'], r['table_bytes'], r['projected_total_saving']) for r in results])
    print('Projected saving:', receipt['projected_saving'])
    print('Native owner projection:', receipt['projected_native_owner_saving'])


if __name__ == '__main__':
    main()
