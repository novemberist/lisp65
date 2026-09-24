"""Price Boot CRC sharing/placement off product, with closed input provenance."""
import argparse
import json
from pathlib import Path
import shlex
from native_diet_object_probe import ROOT, BASE, sha, put, run
from elf_truth import ElfTruth


def nibble_table():
    result = []
    for n in range(16):
        crc = n
        for _ in range(4):
            crc = (crc >> 1) ^ (0xedb88320 if crc & 1 else 0)
        result.append(crc)
    return result


def replacement():
    table = ', '.join('0x%08xUL' % n for n in nibble_table())
    return '''/* Exactly one owner for the 64-byte table, in ordinary text. */
#if C2_STREAM_PHASE == 1
const uint32_t c2_crc32_nibbles[16]
    __attribute__((section(".text.c2_crc32_nibbles"), used)) = { TABLE };
#else
extern const uint32_t c2_crc32_nibbles[16];
#endif
C2_LOCAL __attribute__((noinline)) uint32_t crc32_update(uint32_t crc, const uint8_t *p, uint16_t n) {
    while (n--) {
        crc ^= *p++;
        crc = (crc >> 4) ^ c2_crc32_nibbles[crc & 15u];
        crc = (crc >> 4) ^ c2_crc32_nibbles[crc & 15u];
    }
    return crc;
}
#if C2_STREAM_PHASE == 1
#define C2_CRC_HELPER C2_SLICE(01)
#elif C2_STREAM_PHASE == 3
#define C2_CRC_HELPER C2_SLICE(03)
#else
#define C2_CRC_HELPER __attribute__((noinline))
#endif
/* Same reads, lengths and failure ordering; share the accumulator loop
 * between the single-range and two-range checks inside the loaded phase. */
C2_LOCAL C2_CRC_HELPER uint8_t shelf_crc32_extend(uint32_t at, uint32_t bytes, uint32_t *crc) {
    uint8_t block[32];
    while (bytes) {
        uint16_t n = bytes > sizeof(block) ? sizeof(block) : (uint16_t)bytes;
        if (!c2_stream_shelf_read(at, block, n)) return 0;
        *crc = crc32_update(*crc, block, n);
        at += n; bytes -= n;
    }
    return 1;
}
C2_LOCAL uint8_t shelf_crc32(uint32_t at, uint32_t bytes, uint32_t *result) {
    uint32_t crc = 0xffffffffUL;
    if (!shelf_crc32_extend(at, bytes, &crc)) return 0;
    *result = ~crc;
    return 1;
}
C2_LOCAL uint8_t shelf_crc32_pair(uint32_t first_at, uint16_t first_bytes,
                                uint32_t second_at, uint16_t second_bytes,
                                uint32_t *result) {
    uint32_t crc = 0xffffffffUL;
    if (!shelf_crc32_extend(first_at, first_bytes, &crc)
        || !shelf_crc32_extend(second_at, second_bytes, &crc)) return 0;
    *result = ~crc;
    return 1;
}
'''.replace('TABLE', table)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-diet-boot-crc-probe-r3')
    out = parser.parse_args().out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('outputs must be fresh experiment artifacts')
    out.mkdir(parents=True, exist_ok=True)
    generated = BASE / 'generated-product-sources'
    source = generated / 'c2-stream-decoder.c'
    original = source.read_text()
    start = original.index('C2_LOCAL uint32_t crc32_update(')
    stop = original.index('#ifdef LISP65_C2_LITE_BANK2_STAGING', start)
    candidate = original[:start] + replacement() + original[stop:]
    compact = candidate.replace('uint32_t at, uint32_t bytes, uint32_t *',
                                'uint32_t at, uint16_t bytes, uint32_t *')
    compact = compact.replace('''        crc = (crc >> 4) ^ c2_crc32_nibbles[crc & 15u];
        crc = (crc >> 4) ^ c2_crc32_nibbles[crc & 15u];''', '''        uint8_t part = 2;
        do { crc = (crc >> 4) ^ c2_crc32_nibbles[crc & 15u]; } while (--part);''', 1)
    carried = compact.replace('C2_LOCAL uint8_t shelf_crc32(uint32_t',
                              'C2_LOCAL C2_CRC_HELPER uint8_t shelf_crc32(uint32_t', 1)
    phase_local = compact.replace('C2_LOCAL uint8_t shelf_crc32(uint32_t', '''
#if C2_STREAM_PHASE == 3
#define C2_CRC_RANGE C2_SLICE(03)
#else
#define C2_CRC_RANGE
#endif
C2_LOCAL C2_CRC_RANGE uint8_t shelf_crc32(uint32_t''', 1)
    # Preserve the exact resolved progress-header identity at the new path.
    progress = (generated / '../src/boot_progress.h').resolve()
    if not progress.exists():
        progress = (ROOT / 'src/boot_progress.h').resolve()
    proof = json.loads((BASE / 'command-proof.json').read_text())
    closure_path = BASE / 'active-include-check/receipt.json'
    closure = json.loads(closure_path.read_text())
    allowed = {(ROOT / d['path']).resolve(): d['sha256']
               for row in closure['rows'] for d in row['dependencies']}
    results = []
    for variant, text in [('baseline', original), ('shared-nibble-carrier', candidate),
                          ('compact-round-loop', compact), ('compact-all-carrier', carried),
                          ('compact-phase-local', phase_local)]:
        directory = out / variant
        directory.mkdir(exist_ok=True)
        decoder = directory / 'c2-stream-decoder.c'
        text = text.replace('#include "../src/boot_progress.h"',
                            '#include "' + str(progress) + '"', 1)
        put(decoder, text)
        for phase in ('01', '03', '03b'):
            name = 'c2-stream-phase-' + phase + '.c'
            command = next(c for c in proof['commands'] if '-c' in c
                           and c[c.index('-c') + 1].endswith('/' + name))
            wrapper = directory / name
            put(wrapper, (generated / name).read_bytes())
            flags = command[1:command.index('-c')]
            deps = run([command[0], *flags, '-M', '-MT', 'probe', str(wrapper)])
            put(directory / (phase + '.d'), deps)
            inputs = []
            for path in shlex.split(deps.replace('\\\n', ' ').split(':', 1)[1]):
                p = (ROOT / path).resolve()
                if p not in (decoder, wrapper):
                    if p not in allowed or sha(p) != allowed[p]:
                        raise ValueError('unbound include: ' + str(p))
                inputs.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p)})
            obj = directory / (phase + '.o')
            if obj.exists():
                raise ValueError('experiment artifact already exists')
            cc = [command[0], *flags, '-fno-lto', '-c', str(wrapper), '-o', str(obj)]
            put(directory / (phase + '.log'), run(cc))
            truth = ElfTruth.read(obj, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
            sections = {s.name: s.bytes for s in truth.sections
                        if s.name.startswith(('.text', '.rodata', '.lisp65_rt_'))}
            results.append(dict(variant=variant, phase=phase, sections=sections,
                                inputs=inputs, command=cc, object_sha256=sha(obj)))
    receipt = dict(claim='NON-LTO OBJECT PLACEMENT PROJECTION ONLY',
                   budget=dict(seed=0, finale=0, link=0),
                   source_sha256=sha(source), include_closure_sha256=sha(closure_path),
                   table=nibble_table(), table_bytes=64, results=results)
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    for row in results:
        print(row['variant'], row['phase'], row['sections'])


if __name__ == '__main__':
    main()
