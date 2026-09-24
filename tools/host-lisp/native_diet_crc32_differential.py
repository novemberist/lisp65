"""Execute extracted baseline/candidate CRC C, including read failures (host only)."""
import ctypes as C
import json
from pathlib import Path
import random
import zlib
from native_diet_object_probe import ROOT, BASE, put, run, sha

OUT = ROOT / 'build/native-diet-crc32-differential-r1'
PRE = '''#include <stdint.h>
#include <string.h>
#define C2_LOCAL static
#define C2_SLICE(n)
#define C2_STREAM_PHASE 1
#define LISP65_C2_MAP_CPU_TRANSPORT 1
static uint32_t calls, fail_at, trace;
static uint8_t data_byte(uint32_t a) { return (a * 37u + (a >> 8) * 13u + 17u); }
static uint8_t c2_stream_shelf_read(uint32_t at, uint8_t *p, uint16_t n) {
    ++calls; trace = trace * 16777619u ^ at; trace = trace * 16777619u ^ n;
    if (calls == fail_at) return 0;
    while (n--) *p++ = data_byte(at++);
    return 1;
}
'''
POST = '''
uint32_t update(uint32_t c, uint8_t b) { return crc32_update(c, &b, 1); }
uint8_t test(uint32_t a, uint16_t n, uint32_t b, uint16_t m,
             uint32_t fail, uint8_t pair, uint32_t *out) {
    calls = 0; trace = 0; fail_at = fail;
    return pair ? shelf_crc32_pair(a,n,b,m,out) : shelf_crc32(a,n,out);
}
uint32_t count(void) { return calls; }
uint32_t reads(void) { return trace; }
'''


def extract(path, candidate=False):
    text = path.read_text()
    start = text.index('/* Exactly one owner' if candidate else 'C2_LOCAL uint32_t crc32_update(')
    return text[start:text.index('#ifdef LISP65_C2_LITE_BANK2_STAGING', start)]


def build(name, body):
    source = OUT / (name + '.c')
    library = OUT / (name + '.so')
    if library.exists():
        raise RuntimeError('refusing to replace experiment')
    put(source, PRE + body + POST)
    run(['cc', '-std=c99', '-O2', '-shared', '-fPIC', str(source), '-o', str(library)])
    lib = C.CDLL(str(library))
    lib.update.argtypes = [C.c_uint32, C.c_uint8]
    lib.update.restype = C.c_uint32
    lib.test.argtypes = [C.c_uint32, C.c_uint16, C.c_uint32, C.c_uint16,
                         C.c_uint32, C.c_uint8, C.POINTER(C.c_uint32)]
    lib.test.restype = C.c_uint8
    lib.count.restype = lib.reads.restype = C.c_uint32
    return lib


def payload(at, n):
    return bytes((a * 37 + (a >> 8) * 13 + 17) & 255 for a in range(at, at+n))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = BASE / 'generated-product-sources/c2-stream-decoder.c'
    candidate = ROOT / 'build/native-diet-boot-crc-probe-r3/compact-phase-local/c2-stream-decoder.c'
    old, new = build('baseline', extract(baseline)), build('candidate', extract(candidate, True))
    rng = random.Random(0)
    inputs = [(0, 0)] + [(1 << i, 0) for i in range(32)] + [(0, 1 << i) for i in range(8)]
    inputs += [(rng.getrandbits(32), rng.randrange(256)) for _ in range(10000)]
    for state, byte in inputs:
        assert old.update(state, byte) == new.update(state, byte)
    tests = 0
    for pair in (0, 1):
        for n in (0, 1, 31, 32, 33, 255, 256, 65535):
            for m in ((0, 1, 33, 65535) if pair else (0,)):
                total_reads = (n+31)//32 + (m+31)//32
                failures = [0] + (list(range(1, total_reads+1)) if total_reads < 25 else [1, total_reads//2, total_reads])
                for fail in failures:
                    results = []
                    for lib in (old, new):
                        out = C.c_uint32(0x12345678)
                        ok = lib.test(19, n, 90001, m, fail, pair, C.byref(out))
                        results.append((ok, out.value, lib.count(), lib.reads()))
                    assert results[0] == results[1], (pair,n,m,fail,results)
                    if fail:
                        assert results[0][0:2] == (0, 0x12345678)
                    else:
                        assert results[0][0:2] == (1, zlib.crc32(payload(19,n) + (payload(90001,m) if pair else b'')))
                    tests += 1
    mutant = build('wrong-table', extract(candidate, True).replace('0x1db71064UL', '0x1db71065UL', 1))
    assert any(old.update(s,b) != mutant.update(s,b) for s,b in inputs)
    receipt = dict(claim='HOST C DIFFERENTIAL ONLY; NOT NATIVE OR LINK ACCEPTANCE',
                   source_sha256=sha(baseline), candidate_sha256=sha(candidate),
                   update_cases=len(inputs), range_failure_cases=tests,
                   wrong_table_mutation='rejected', budget=dict(seed=0,finale=0,link=0))
    put(OUT / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
