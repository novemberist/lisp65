"""Actual isolated C certificate protocol, refill and partial-read faults."""
from pathlib import Path
import ctypes as C
import hashlib
import shutil
import subprocess
import set_b_producer as P
import set_b_front_prototype_20260926 as K

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-prototype-query-r1'
PREFIX=r'''
#include <stdint.h>
#include <string.h>
typedef int16_t obj;
#define NIL 0
#define MKFIX(x) ((obj)(((uint16_t)(x)<<1)|1))
#define C2D_ENTRY_CAP 2048
#define LISP65_C2_BANK2_CODE_LIMIT 60758UL
uint8_t arena[65536],c2_ready=1,vm_status=93;
struct {uint16_t generation,entry_count;} c2_runtime;
uint32_t calls,byte_count,fail_at,partial,allocations;
uint16_t result_low,result_high;
static uint16_t c2_u16(const uint8_t *p){return p[0]|((uint16_t)p[1]<<8);}
static uint8_t c2_stream_c2d_read(uint16_t at,void *dest,uint16_t n){
 calls++;byte_count+=n;
 if((uint32_t)at+n>50816)return 0;
 if(calls==fail_at){memcpy(dest,arena+at,partial==2?n:partial?n/2:0);return 0;}
 memcpy(dest,arena+at,n);return 1;
}
static obj cons(obj a,obj b){allocations++;result_low=((uint16_t)a)>>1;result_high=((uint16_t)b)>>1;return 2;}
void plane(const uint8_t *p){memcpy(arena,p,65536);c2_runtime.generation=c2_u16(p+10);c2_runtime.entry_count=c2_u16(p+16);}
void configure(uint32_t fail,uint32_t part,uint8_t ready){calls=byte_count=allocations=0;fail_at=fail;partial=part;c2_ready=ready;result_low=result_high=65535;}
void mismatch(void){c2_runtime.entry_count++;}
'''
SUFFIX='\nuint8_t state(void){return c2_front_certificate[2];}\n'

def main():
    OUT.mkdir(exist_ok=False)
    kernel=K.OUT/'certificate.inc';assert kernel.read_text()==K.HELPER
    src=OUT/'fixture.c';src.write_text(PREFIX+kernel.read_text()+SUFFIX)
    lib=OUT/'fixture.so';cmd=[shutil.which('cc'),'-std=c11','-Wall','-Wextra','-Werror','-O2','-shared','-fPIC',str(src),'-o',str(lib)]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (OUT/'compile.txt').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr
    d=C.CDLL(str(lib));d.plane.argtypes=[C.POINTER(C.c_uint8)]
    d.configure.argtypes=[C.c_uint32,C.c_uint32,C.c_uint8]
    d.c2_front_publish.argtypes=[C.c_uint16]
    for name in ('state','c2_front_begin','c2_front_publish'):getattr(d,name).restype=C.c_uint8
    d.c2_resolver_charged_front.restype=C.c_int16
    basepath=ROOT/'build/set-b-load-attribution-r1/definitions-2/before-load-c2d.bin'
    base=basepath.read_bytes();rows=[];current=base
    u=lambda b,a:int.from_bytes(b[a:a+2],'little')
    def reference(b):
        count=u(b,16);generation=u(b,10);front=0
        if count>2048:return None
        for i in range(count):
            a=2096+10*i;at=u(b,a+2);length=u(b,a+4)
            if u(b,a+8)!=generation or not length or at>60758 or length>60758-at:return None
            front=max(front,at+length)
        return front
    def plane(raw,reset=False):
        nonlocal current
        current=bytes(raw);d.plane((C.c_uint8*65536).from_buffer_copy(current))
        if reset:d.c2_front_boot_reset()
    def field(name,typ=C.c_uint32):return typ.in_dll(d,name).value
    def query(label,want,reads=None,state=None,fail=0,partial=0,ready=1):
        d.configure(fail,partial,ready);before=d.state()
        result=d.c2_resolver_charged_front()
        got=None if result==0 else field('result_low',C.c_uint16)+256*field('result_high',C.c_uint16)
        assert got==want,(label,got,want)
        assert bytes((C.c_uint8*65536).in_dll(d,'arena'))==current,label
        assert field('c2_ready',C.c_uint8)==ready and field('vm_status',C.c_uint8)==93
        assert field('allocations')==int(got is not None)
        if reads is not None:assert field('calls')==reads,(label,field('calls'),reads)
        if state is not None:assert d.state()==state,(label,d.state(),state)
        rows.append(dict(case=label,result=got,reads=field('calls'),bytes=field('byte_count'),state_before=before,state_after=d.state(),fail_at=fail,partial=partial,sha256=hashlib.sha256(current).hexdigest()))
    def action(label,name,want=None,arg=None,state=None):
        before=d.state();result=getattr(d,name)(*(() if arg is None else (arg,)))
        if want is not None:assert result==want,(label,result,want)
        if state is not None:assert d.state()==state,(label,d.state(),state)
        rows.append(dict(case=label,action=name,argument=arg,result=result if want is not None else None,state_before=before,state_after=d.state()))
    count=u(base,16);front=reference(base)
    plane(base,True);query('cold-refill',front,count+1,1);query('warm-header-only',front,1,1)
    query('eliminated-row-fault-not-executed',front,1,1,fail=2)
    query('warm-header-failure',None,1,0,fail=1)
    query('refill-after-header-failure',front,count+1,1)
    query('not-ready',None,0,1,ready=0)
    d.mismatch();query('runtime-header-mismatch',None,1,0)
    for fault in range(1,count+2):
        for part in (0,1,2):
            plane(base,True);query(f'cold-fault-{fault}-partial-{part}',None,fault,0,fail=fault,partial=part)
    for n in range(2049):
        b=bytearray(base);b[16:18]=n.to_bytes(2,'little')
        for i in range(n):
            a=2096+10*i;b[a:a+10]=bytes([255,0])+((n-i)*10).to_bytes(2,'little')+b'\x0a\0\0\0'+b[10:12]
        plane(b,True);query(f'unordered-retired-population-{n}',reference(b),n+1,1)
    for slot in (0,5,6,784,800,805):
        for label,off,data in (('generation',8,b'\xff\xff'),('zero',4,b'\0\0'),('range',2,b'\xff\xff')):
            b=bytearray(base);a=2096+10*slot;b[a+off:a+off+2]=data
            plane(b,True);query(f'malformed-{label}-{slot}',None,slot+2,0)
    b=bytearray(base);b[16:18]=(2049).to_bytes(2,'little');plane(b,True);query('count-overflow',None,1,0)
    plane(base,True);query('protocol-initial',front,count+1,1)
    action('begin-invalidates','c2_front_begin',1,state=2)
    action('nested-begin-refused','c2_front_begin',0,state=2)
    query('busy-refuses-without-read',None,0,2)
    action('abort-invalidates','c2_front_abort',state=0)
    action('stale-publish-refused','c2_front_publish',0,front,0)
    query('abort-refill',front,count+1,1)
    action('begin-for-range','c2_front_begin',1,state=2)
    action('invalid-front-refused','c2_front_publish',0,60759,0)
    action('begin-for-publish','c2_front_begin',1,state=2)
    action('caller-validated-publish','c2_front_publish',1,front,1)
    query('published-warm',front,1,1)
    # Raw notifications conservatively disable every later reuse until trusted boot.
    action('raw-invalidates','c2_front_raw_write',state=4)
    b=bytearray(base);b[2100:2102]=b'\0\0';plane(b)
    query('raw-malformed-refused',None,2,4)
    plane(base);query('raw-repaired-full-refill',front,count+1,4)
    query('raw-taint-still-full-refill',front,count+1,4)
    action('tainted-begin','c2_front_begin',1,state=6)
    action('raw-during-busy','c2_front_raw_write',state=6)
    action('tainted-publication-no-reuse','c2_front_publish',1,front,4)
    action('tainted-abort','c2_front_abort',state=4)
    action('trusted-boot-only-reset','c2_front_boot_reset',state=0)
    query('boot-restores-refill',front,count+1,1)
    # Same generation/count but different charged front: never restore a pending cursor.
    b=bytearray(base);a=2096+10*(count-1);b[a+2:a+4]=(front+10).to_bytes(2,'little')
    changed=reference(b);assert changed!=front
    action('rollback-begin','c2_front_begin',1,state=2);plane(b)
    action('rollback-abort','c2_front_abort',state=0)
    query('rollback-refill-current-truth',changed,count+1,1)
    # Deliberately omit notification: a failing integration control, not a product defect.
    plane(base);query('missing-hook-falling-control-stale-answer',changed,1,1)
    assert changed!=reference(base)
    action('notify-after-control','c2_front_raw_write',state=4)
    query('notified-control-restores-truth',front,count+1,4)
    # Protocol-only trace; callers supply oracle-proven fronts, no actual INIT execution.
    plane(base,True)
    for step,n in enumerate((785,801,801,804)):
        b=bytearray(base);b[16:18]=n.to_bytes(2,'little');plane(b)
        action(f'prefix-{step}-begin','c2_front_begin',1,state=2)
        action(f'prefix-{step}-caller-proven-publish','c2_front_publish',1,reference(b),1)
        query(f'prefix-{step}-query',reference(b),1,1)
    P.write(OUT/'rows.json',rows)
    P.write(OUT/'receipt.json',dict(status='PASS ISOLATED C PROTOCOL AND REFILL; INTEGRATION UNPROVED',
        driver=P.bind(Path(__file__)),kernel=P.bind(kernel),harness=P.bind(src),library=P.bind(lib),input=P.bind(basepath),command=cmd,
        rows=P.bind(OUT/'rows.json'),row_count=len(rows),partial_transport_rows=(count+1)*3,legal_population_rows=2049,
        negative_control='Unnotified plane mutation returns stale warm front as expected; all actual writer hooks remain required.',
        limits='Transport, cons, runtime context and publication callers are fixture stubs. No product lifecycle hooks, actual INIT, collector, native timing or linked placement proof.',
        host_c_compiles=1,host_c_links=1,product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PASS',len(rows),'isolated C rows')

if __name__=='__main__':main()
