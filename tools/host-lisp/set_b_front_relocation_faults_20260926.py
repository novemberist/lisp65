"""Execute exact phase04/05a/05b C before broader lifecycle qualification."""
from pathlib import Path
import ctypes as C
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_integration_r2_20260926 as I
import set_b_front_relocation_20260926 as R
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-relocation-faults-r1'
PRE=r'''
#include <stdint.h>
#include <string.h>
#define C2_STREAM_PRODUCT_V3 1
#include "c2-stream-decoder.h"
#define LISP65_C2_LITE_COLD_EVICTION 1
#define LISP65_C2_SESSION_BYTES 65536UL
#define LISP65_C2_BANK2_CODE_LIMIT 60758UL
#define C2_SLICE(n)
#define C2_INSTALL_DECODER_STAMP(n) ((void)0)
#define C2_FRAME_ATTRIBUTION_STAMP(n) ((void)0)
static uint16_t r16(const uint8_t*p){return p[0]|((uint16_t)p[1]<<8);}
static uint32_t r24(const uint8_t*p){return r16(p)|((uint32_t)p[2]<<16);}
static uint16_t c2_u16(const uint8_t*p){return r16(p);}
static uint8_t fail(c2_stream_context*c,uint8_t e){c->error=e;return e;}
static uint8_t magic4(const uint8_t*p,const char*s){return !memcmp(p,s,3)&&p[3]==s[3];}
static void w16(uint8_t*p,uint16_t x){p[0]=x;p[1]=x>>8;}
static void w24(uint8_t*p,uint32_t x){w16(p,x);p[2]=x>>16;}
/* Transaction scaffolding only; not a native scratch ABI layout. */
struct {c2_stream_context append;uint8_t record[32],staged;uint16_t length;uint32_t attic;} c2aw;
c2_stream_context c2_runtime,*c2_decode_active;
uint8_t c2_ready=1;
static uint8_t plane[8192],shelf[8192],im[20];
static uint16_t meta=256,raw_at=80,entry_at=2096;
static uint8_t fault,partial;
uint8_t result_stage,result_code;
uint16_t result_front;
uint32_t read_count;
uint8_t read_classes[64];
static uint8_t transfer(uint8_t cls,const uint8_t*src,void*dst,uint16_t n){
 if(read_count<64)read_classes[read_count]=cls;
 ++read_count;
 if(cls==fault){uint16_t copied=partial==2?n:partial==1?n/2:0;memcpy(dst,src,copied);return 0;}
 memcpy(dst,src,n);return 1;
}
uint8_t c2_stream_shelf_read(uint32_t at,void*dst,uint16_t n){
 if(at>8192 || n>8192-at)return 0;
 return transfer(at==meta?1:at==meta+24?2:3,shelf+at,dst,n);
}
uint8_t c2_stream_c2d_read(uint16_t at,void*dst,uint16_t n){
 if(at>8192 || n>8192-at)return 0;
 return transfer(n==3?4:n==32?5:at==entry_at?6:7,plane+at,dst,n);
}
static uint8_t c2_image_read(c2_stream_context*c,uint16_t image,uint8_t*out){
 if(image!=c->image_first)return 0;memcpy(out,im,20);return 1;
}
void setup(uint8_t mutation,uint8_t fail_class,uint8_t copy_mode,uint8_t boot){
 memset(&c2aw,0,sizeof c2aw);memset(&c2_runtime,0,sizeof c2_runtime);
 memset(plane,0,sizeof plane);memset(shelf,0,sizeof shelf);memset(im,0,sizeof im);
 memset(read_classes,0,sizeof read_classes);read_count=0;
 c2_ready=!boot;raw_at=48+(boot?0:32);fault=fail_class;partial=copy_mode;
 c2aw.staged=1;c2aw.length=64;c2aw.attic=256;c2_decode_active=&c2aw.append;
 c2aw.append.generation=1;c2aw.append.images_offset=48;c2aw.append.entries_offset=entry_at;
 c2aw.append.image_first=boot?0:1;c2aw.append.image_count=boot?1:2;
 c2aw.append.phase=4;c2aw.append.entry_cursor=boot?0:90;w16(c2aw.record+12,boot?0:90);
 w16(im+4,2);w16(im+16,14);w16(im+18,56);w24(im+13,meta);
 memcpy(shelf+meta,"C2I",3);shelf[meta+4]=2;shelf[meta+5]=24;shelf[meta+6]=16;shelf[meta+7]=8;
 w16(shelf+meta+10,2);w16(shelf+meta+14,24);w16(shelf+meta+16,56);w16(shelf+meta+18,56);
 w24(plane+raw_at+18,100);
 for(unsigned i=0;i<2;++i){
  uint8_t*e=shelf+meta+24+i*16;uint8_t*d=plane+entry_at+i*10;
  w24(e,i*7);w16(e+3,7);w16(e+8,0xffff);
  d[0]=boot?0:1;w16(d+2,100+i*7);w16(d+4,7);w16(d+8,1);
 }
 if(mutation==1)w16(plane+entry_at+10+8,2); /* generation */
 if(mutation==2)w16(plane+entry_at+2,101); /* binding */
 if(mutation==3)w16(shelf+meta+24+3,0); /* zero length */
 if(mutation==4){ /* source remains valid; corrupt execution coordinates */
  w24(plane+raw_at+18,60758);w16(plane+entry_at+2,60758);w16(plane+entry_at+12,60765);
 }
 if(mutation==5)plane[raw_at+23]=1;
 if(mutation==6)shelf[meta+24+11]=4;
 if(mutation==7){w16(im+4,0);w16(im+18,24);w16(shelf+meta+10,0);w16(shelf+meta+16,24);w16(shelf+meta+18,24);}
 if(mutation==8){w24(shelf+meta+24,7);w24(shelf+meta+40,0);w16(plane+entry_at+2,107);w16(plane+entry_at+12,100);}
 if(mutation==9){w24(plane+raw_at+18,60000);w16(plane+entry_at+2,60000);w16(plane+entry_at+12,60007);}
 if(mutation==10){w16(c2aw.record+12,500);c2aw.append.entry_cursor=500;}
 result_stage=result_code=0;result_front=0;
}
'''
SUFFIX=r'''
uint8_t run(uint8_t world){
 uint8_t e;
 uint8_t (*phases[3][3])(void*)={{b_phase04,b_phase05a,b_phase05b},{p_phase04,p_phase05a,p_phase05b},{n_phase04,n_phase05a,n_phase05b}};
 for(uint8_t i=0;i<3;++i){
  e=phases[world][i](&c2aw.append);
  if(e){result_stage=i;result_code=e;result_front=c2aw.append.entry_cursor;return e;}
 }
 result_stage=3;result_front=c2aw.append.entry_cursor;return 0;
}
uint8_t guard_probe(uint8_t mode){
 setup(0,0,0,0);c2aw.append.entry_cursor=29;
 if(mode==1)c2aw.staged=0;
 if(mode==2)c2aw.attic=65537;
 if(mode==3)c2_decode_active=&c2_runtime;
 uint8_t e=n_guard(&c2aw.append);result_front=c2aw.append.entry_cursor;return e;
}
'''

def main():
    S.require_auth();gate=ROOT/'build/set-b-front-relocation-capacity-r2/receipt.json'
    assert P.load(gate)['status'].startswith('PASS');OUT.mkdir(exist_ok=False)
    before_runtime=(ROOT/'src/c2_product_runtime.c').read_text()
    before_decoder=(ROOT/'config/set-b-native/includes/c2-stream-decoder.c').read_text()
    worlds=[('b',before_runtime,before_decoder),
        ('p',(I.OUT/'candidate/src/c2_product_runtime.c').read_text(),(I.OUT/'candidate/config/set-b-native/includes/c2-stream-decoder.c').read_text()),
        ('n',(R.OUT/'candidate/src/c2_product_runtime.c').read_text(),(R.OUT/'candidate/config/set-b-native/includes/c2-stream-decoder.c').read_text())]
    pieces=[];extracted=[]
    for prefix,runtime,decoder in worlds:
        f=I.function(runtime,'c2_append_source_domain_guard')
        f=f.replace('c2_append_source_domain_guard',prefix+'_guard');pieces.append(f)
        for name in ('04','05a','05b'):
            f=I.function(decoder,'c2_stream_phase_'+name)
            f=f.replace('c2_stream_phase_'+name,prefix+'_phase'+name).replace('c2_append_source_domain_guard',prefix+'_guard')
            pieces.append(f)
        p=OUT/(prefix+'-extracted.c');p.write_text('\n'.join(pieces[-4:]));extracted.append(P.bind(p))
    (OUT/'c2-stream-decoder.h').write_bytes((ROOT/'config/set-b-native/includes/c2-stream-decoder.h').read_bytes())
    fixture=OUT/'fixture.c';fixture.write_text(PRE+'\n'+'\n'.join(pieces)+SUFFIX)
    lib=OUT/'fixture.so';cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror',
        '-Wno-misleading-indentation','-I'+str(OUT),str(fixture),'-o',str(lib)]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert r.returncode==0,r.stderr
    d=C.CDLL(str(lib));d.setup.argtypes=[C.c_uint8]*4;d.run.argtypes=[C.c_uint8];d.run.restype=C.c_uint8
    def execute(world,mutation=0,fault=0,partial=0,boot=0):
        d.setup(mutation,fault,partial,boot);status=d.run(world)
        return dict(status=status,phase=['04','05a','05b','completed05b'][C.c_uint8.in_dll(d,'result_stage').value],
            pending=C.c_uint16.in_dll(d,'result_front').value,
            reads=list((C.c_uint8*64).in_dll(d,'read_classes'))[:C.c_uint32.in_dll(d,'read_count').value])
    rows=[]
    for mode in range(4):
        result=d.guard_probe(mode);pending=C.c_uint16.in_dll(d,'result_front').value
        assert (result,pending)==((1,90) if mode==0 else (0,29))
        rows.append(dict(kind='actual-guard',mode=mode,result=result,pending=pending))
    for mutation in (0,7,8,9,10):
        for boot in (0,1):
            if mutation==10 and boot:continue
            a=execute(1,mutation,boot=boot);b=execute(2,mutation,boot=boot)
            assert a['status']==b['status']==0 and a['pending']==b['pending'],(mutation,boot,a,b)
            rows.append(dict(kind='valid-pending',mutation=mutation,boot=boot,previous=a,candidate=b))
    for mutation in (1,2,3,5,6):
        a=execute(0,mutation);b=execute(1,mutation);c=execute(2,mutation)
        assert a['status']==b['status']==c['status']==5
        rows.append(dict(kind='single-malformed',mutation=mutation,maintained=a,previous=b,candidate=c))
    for fault in (1,2,3,5,6,7):
        for partial in range(3):
            a=execute(0,fault=fault,partial=partial);b=execute(1,fault=fault,partial=partial);c=execute(2,fault=fault,partial=partial)
            assert a['status']==b['status']==c['status']==1
            rows.append(dict(kind='shared-read-fault',fault=fault,partial=partial,maintained=a,previous=b,candidate=c))
    for partial in range(3):
        c=execute(2,fault=4,partial=partial);assert c['status']==1 and c['phase']=='05a' and c['pending']==90
        rows.append(dict(kind='new-base-read-fault',partial=partial,candidate=c))
    # First combined-fault row: immutable entry1 read fails after entry0's
    # corrupted execution range. Semantic read-class injection, not call index.
    a=execute(0,mutation=4,fault=3);b=execute(1,mutation=4,fault=3);c=execute(2,mutation=4,fault=3)
    halt=dict(kind='range-plus-later-source-read-fault',mutation=4,fault=3,maintained=a,previous=b,candidate=c,
        domain='Synthetic execution-plane mutation after prior setup; not a claim that ordinary admitted append/boot produces this bad range.')
    assert a['status']==b['status']==1 and c['status']==5
    rows.append(halt);P.write(OUT/'rows.json',rows);P.write(OUT/'first-unbound-error.json',halt)
    P.write(OUT/'receipt.json',dict(status='HALT: UNBOUND ERROR-PRECEDENCE DIFFERENCE IN ACTUAL DECODER C',
        driver=P.bind(Path(__file__)),gate=P.bind(gate),execution_head='775c4083',
        extracted=extracted,fixture=P.bind(fixture),header=P.bind(OUT/'c2-stream-decoder.h'),library=P.bind(lib),
        compile=P.bind(OUT/'command.json'),rows=P.bind(OUT/'rows.json'),row_count=len(rows),passing_rows=len(rows)-1,
        halt=P.bind(OUT/'first-unbound-error.json'),host_c_compiles=1,host_c_links=1,
        scope='Exact extracted source guard and phases04/05a/05b execute under a common header. Image-read transport and transaction layout are explicit synthetic seams; readers support semantic-class partial failures. No publishing form, later decoder phase, full rollback, guest or product execution.',
        classification='Prototype fault-domain counterexample, not a new reproduced product defect or data corruption. Supported writer-domain reachability and exact-error acceptance remain unbound; halt rather than tolerate.',
        unexecuted=['Terminal publication/abort/recovery integrated fixtures','Whole-product BAD BYTECODE successor','Native cold/stack/GC/usage'],
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('HALT after',len(rows)-1,'passing C rows: old/previous IO1, candidate ENTRY5 at source-entry1 fault; no publication invoked')

if __name__=='__main__':main()
