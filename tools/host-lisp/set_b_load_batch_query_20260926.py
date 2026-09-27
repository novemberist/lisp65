"""Differential/fault proof for the exact bounded batch helper, without a guest."""
import ctypes
import hashlib
from pathlib import Path
import random
import shutil
import subprocess
import set_b_producer as P
import set_b_load_batch_native_20260926 as N
import set_b_load_preflight_native_r2_20260926 as OLD

ROOT = P.ROOT
OUT = ROOT/'build/set-b-load-batch-query-r1'
PREFIX = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef int16_t obj;
#define NIL 0
#define MKFIX(x) ((obj)(((uint16_t)(x)<<1)|1))
#define C2D_ENTRY_CAP 2048
#define LISP65_C2_BANK2_CODE_LIMIT 60758UL
uint8_t arena[65536],c2_ready;
uint32_t calls,byte_count,fail_at,partial,cons_calls,max_read;
uint16_t result_low,result_high,read_at[2050],read_size[2050];
static uint16_t c2_u16(const uint8_t *p){return p[0]|((uint16_t)p[1]<<8);}
static uint8_t c2_stream_c2d_read(uint16_t at,void *dest,uint16_t n){
 assert(n>0 && n<=60 && (uint32_t)at+n<=33840 && calls<2050);
 read_at[calls]=at;read_size[calls]=n;calls++;byte_count+=n;
 if(n>max_read)max_read=n;
 if(calls==fail_at){
  uint16_t copied=partial==1 ? n/2 : partial==2 ? n : 0;
  memcpy(dest,arena+at,copied);return 0;
 }
 memcpy(dest,arena+at,n);return 1;
}
static obj cons(obj a,obj b){cons_calls++;result_low=((uint16_t)a)>>1;result_high=((uint16_t)b)>>1;return 2;}
void prepare(const uint8_t *p,uint32_t fail,uint8_t ready,uint32_t part){
 memcpy(arena,p,65536);calls=byte_count=cons_calls=max_read=0;
 fail_at=fail;c2_ready=ready;partial=part;result_low=result_high=65535;
}
'''


def main():
    OUT.mkdir(exist_ok=False)
    candidate = N.OUT/'candidate/src/c2_product_runtime.c'
    assert N.HELPER in candidate.read_text()
    old_candidate = OLD.OUT/'candidate/src/c2_product_runtime.c'
    assert OLD.HELPER in old_candidate.read_text()
    src = OUT/'query.c'
    src.write_text(PREFIX + N.HELPER + OLD.HELPER.replace(
        'c2_resolver_charged_front(void)', 'original_charged_front(void)'))
    lib = OUT/'query.so'
    command = [shutil.which('cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
               '-O2', '-shared', '-fPIC', str(src), '-o', str(lib)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (OUT/'compile.txt').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    dll = ctypes.CDLL(str(lib))
    dll.prepare.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32,
                           ctypes.c_uint8, ctypes.c_uint32]
    for name in ('c2_resolver_charged_front', 'original_charged_front'):
        getattr(dll, name).restype = ctypes.c_int16
    base_path = ROOT/'build/set-b-load-attribution-r1/definitions-2/before-load-c2d.bin'
    base = base_path.read_bytes()
    rows, traces = [], []
    def u(raw, at):
        return int.from_bytes(raw[at:at+2], 'little')
    def oracle(raw):
        count, generation = u(raw, 16), u(raw, 10)
        if count > 2048:
            return None
        ends = []
        for i in range(count):
            p = 2096 + i*10; start, length = u(raw, p+2), u(raw, p+4)
            if u(raw, p+8) != generation or length == 0 or start+length > 60758:
                return None
            ends.append(start+length)
        return max(ends, default=0)
    def value(name):
        return ctypes.c_uint32.in_dll(dll, name).value
    def invoke(name, raw, fail=0, ready=1, partial=0):
        dll.prepare((ctypes.c_uint8*65536).from_buffer_copy(raw), fail, ready, partial)
        result = getattr(dll, name)()
        got = None if result == 0 else (
            ctypes.c_uint16.in_dll(dll, 'result_low').value +
            256*ctypes.c_uint16.in_dll(dll, 'result_high').value)
        assert bytes((ctypes.c_uint8*65536).in_dll(dll, 'arena')) == raw
        assert value('cons_calls') == (0 if got is None else 1)
        return got
    def run(label, raw, fail=0, ready=1, partial=0, save_trace=False):
        expected = None if fail or not ready else oracle(raw)
        if not fail:
            assert invoke('original_charged_front', raw, ready=ready) == expected
        got = invoke('c2_resolver_charged_front', raw, fail, ready, partial)
        assert got == expected, (label, got, expected)
        calls = value('calls')
        ats = (ctypes.c_uint16*2050).in_dll(dll, 'read_at')
        sizes = (ctypes.c_uint16*2050).in_dll(dll, 'read_size')
        trace = [[ats[i], sizes[i]] for i in range(calls)]
        if ready:
            assert trace[0] == [10, 8]
            offset = 2096
            for at, size in trace[1:]:
                assert at == offset and size%10 == 0 and 10 <= size <= 60
                offset += size
            assert offset <= 2096 + min(u(raw, 16), 2048)*10
        else:
            assert calls == 0
        if got is not None:
            count = u(raw, 16)
            assert calls == 1+(count+5)//6
            assert value('byte_count') == 8+10*count
        if fail:
            assert calls == fail
        row = dict(case=label, result=got, read_calls=calls,
                   read_bytes=value('byte_count'), maximum_read=value('max_read'),
                   failure=fail, partial_mode=partial, ready=ready,
                   raw_sha256=hashlib.sha256(raw).hexdigest())
        rows.append(row)
        if save_trace:
            traces.append(dict(case=label, reads=trace))
    run('captured-first-replacement', base, save_trace=True)
    run('not-ready', base, ready=0)
    for failure in range(1, 1+(806+5)//6+1):
        for partial in range(3):
            run(f'read-failure-{failure}-partial-{partial}', base, fail=failure, partial=partial)
    # Every legal count, including every six-row residue, empty and full.
    for count in range(2049):
        raw = bytearray(base); raw[16:18] = count.to_bytes(2, 'little')
        for i in range(count):
            p = 2096+i*10
            raw[p:p+10] = bytes([255, 0]) + ((count-i)*10).to_bytes(2, 'little') + b'\x0a\0\0\0\x01\0'
        run(f'reversed-retired-count-{count}', raw, save_trace=count in (0,1,5,6,7,785,801,804,806,2048))
    for slot in (0,1,4,5,6,7,799,800,801,802,803,804,805):
        for field, offset, data in (
                ('generation', 8, b'\x02\0'), ('zero-size', 4, b'\0\0'),
                ('past-owner', 2, (60758).to_bytes(2,'little')),
                ('wrap', 2, b'\xff\xff'), ('oversize', 4, b'\xff\xff')):
            raw = bytearray(base); p = 2096+slot*10+offset; raw[p:p+2] = data
            run(f'{field}-slot-{slot}', raw)
    raw = bytearray(base); raw[16:18] = (2049).to_bytes(2,'little'); run('count-overflow',raw)
    rng = random.Random(8719)
    for i in range(200):
        raw = bytearray(base); p = 2096+10*rng.randrange(806)
        for offset in (0,2,3,4,5,8,9):
            raw[p+offset] = rng.randrange(256)
        run(f'mutation-{i}',raw)
    P.write(OUT/'rows.json',rows); P.write(OUT/'traces.json',traces)
    P.write(OUT/'receipt.json',dict(status='PASS: EXACT BATCH C DIFFERENTIAL AND PARTIAL-READ FAILURE PROOF',
        driver=P.bind(Path(__file__)), candidate=P.bind(candidate), scalar_candidate=P.bind(old_candidate),
        base=P.bind(base_path), harness=P.bind(src), library=P.bind(lib), command=command,
        rows=P.bind(OUT/'rows.json'), traces=P.bind(OUT/'traces.json'), row_count=len(rows),
        all_legal_counts=2049, partial_failure_rows=408, native_read_limit=64, batch_maximum=60,
        source_unchanged_every_row=True, host_c_compiles=1, host_c_links=1,
        product_builds=0, product_links=0, seeds=0, device_contacts=0,
        limits='Actual helper C, target-width values. Reader and cons stubs; no target stack, collector or timing qualification.'))
    print('PASS',len(rows),'batch rows; every legal count, partial failure and unchanged 64K source')


if __name__ == '__main__':
    main()
