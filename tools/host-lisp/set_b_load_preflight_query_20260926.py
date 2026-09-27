"""Execute the parked native query C, including every transport-failure row."""
from pathlib import Path
import ctypes
import hashlib
import random
import shutil
import subprocess
import set_b_producer as P
import set_b_load_preflight_native_r2_20260926 as N
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-query-r1'
PREFIX=r'''
#include <stdint.h>
#include <string.h>
typedef int16_t obj;
#define NIL 0
#define MKFIX(x) ((obj)(((uint16_t)(x)<<1)|1))
#define C2D_ENTRY_CAP 2048
#define LISP65_C2_BANK2_CODE_LIMIT 60758UL
uint8_t arena[65536],c2_ready=1;
uint32_t calls,byte_count,fail_at;
uint16_t result_low,result_high;
static uint16_t c2_u16(const uint8_t *p){return p[0]|((uint16_t)p[1]<<8);}
static uint8_t c2_stream_c2d_read(uint16_t at,void *dest,uint16_t n){
 calls++;byte_count+=n;if(calls==fail_at)return 0;
 if((uint32_t)at+n>33840)return 0;memcpy(dest,arena+at,n);return 1;
}
static obj cons(obj a,obj b){result_low=((uint16_t)a)>>1;result_high=((uint16_t)b)>>1;return 2;}
void prepare(const uint8_t *p,uint32_t fail,uint8_t ready){memcpy(arena,p,65536);calls=byte_count=0;fail_at=fail;c2_ready=ready;result_low=result_high=65535;}
'''

def main():
    OUT.mkdir(exist_ok=False);candidate=N.OUT/'candidate/src/c2_product_runtime.c';assert N.HELPER in candidate.read_text()
    src=OUT/'query.c';src.write_text(PREFIX+N.HELPER);lib=OUT/'query.so'
    cmd=[shutil.which('cc'),'-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-O2','-shared','-fPIC',str(src),'-o',str(lib)]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);(OUT/'compile.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    dll=ctypes.CDLL(str(lib));dll.prepare.argtypes=[ctypes.POINTER(ctypes.c_uint8),ctypes.c_uint32,ctypes.c_uint8];dll.c2_resolver_charged_front.restype=ctypes.c_int16
    base=(ROOT/'build/set-b-load-attribution-r1/definitions-2/before-load-c2d.bin').read_bytes();rows=[]
    u=lambda b,a:int.from_bytes(b[a:a+2],'little')
    def reference(raw):
        n=u(raw,16);gen=u(raw,10);low=0
        if n>2048:return None
        for i in range(n):
            at=2096+10*i;start=u(raw,at+2);length=u(raw,at+4)
            if u(raw,at+8)!=gen or not length or start>60758 or length>60758-start:return None
            low=max(low,start+length)
        return low
    def run(label,raw,fail=0,ready=1):
        a=(ctypes.c_uint8*65536).from_buffer_copy(raw);dll.prepare(a,fail,ready)
        result=dll.c2_resolver_charged_front();calls=ctypes.c_uint32.in_dll(dll,'calls').value
        got=None if result==0 else ctypes.c_uint16.in_dll(dll,'result_low').value+256*ctypes.c_uint16.in_dll(dll,'result_high').value
        want=None if fail or not ready else reference(raw)
        assert got==want,(label,got,want)
        after=bytes((ctypes.c_uint8*65536).in_dll(dll,'arena'));assert after==raw
        rows.append(dict(case=label,result=got,read_calls=calls,read_bytes=ctypes.c_uint32.in_dll(dll,'byte_count').value,transport_failure=fail,ready=ready,raw_sha256=hashlib.sha256(raw).hexdigest()))
    run('minimal-reuse',base);run('not-ready',base,ready=0)
    for i in range(1,808):run('transport-'+str(i),base,fail=i)
    for label,at,data in [('generation',2096+8,b'\x02\x00'),('zero-length',2096+4,b'\0\0'),('count-overflow',16,(2049).to_bytes(2,'little')),('past-owner',2096+2,(60758).to_bytes(2,'little')),('u16-overflow',2096+2,b'\xff\xff')]:
        b=bytearray(base);b[at:at+2]=data;run(label,b)
    for count in (0,1,785,806,2048):
        b=bytearray(base);b[16:18]=count.to_bytes(2,'little')
        for i in range(count):
            at=2096+10*i;b[at:at+10]=bytes([255,0])+((count-i)*10).to_bytes(2,'little')+b'\x0a\0\0\0\x01\0'
        run('reverse-order-all-retired-'+str(count),b)
    rng=random.Random(519)
    for i in range(200):
        b=bytearray(base);slot=rng.randrange(806);at=2096+10*slot
        for off in (0,2,3,4,5,8,9):b[at+off]=rng.randrange(256)
        run('mutation-'+str(i),b)
    P.write(OUT/'rows.json',rows)
    P.write(OUT/'receipt.json',dict(status='PASS: ACTUAL NATIVE QUERY C HOST DIFFERENTIAL/FAULT ROWS',driver=P.bind(Path(__file__)),candidate=P.bind(candidate),harness=P.bind(src),library=P.bind(lib),command=cmd,rows=P.bind(OUT/'rows.json'),row_count=len(rows),transport_failure_rows=807,product_builds=0,product_links=0,seeds=0,device_contacts=0,host_c_compiles=1,host_c_links=1,
        limits='Host C target-width arithmetic and actual query body. Transport/cons are stubs; no 45GS02 time, product collector or linked placement claim.'))
    print('PASS',len(rows),'query/fault rows; every 64K source unchanged')
if __name__=='__main__':main()
