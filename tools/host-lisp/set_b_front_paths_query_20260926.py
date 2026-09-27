"""Join real plane writers, scanner, certificate and retirement owner mutation."""
from pathlib import Path
import ctypes as C
import re,subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_integration_r2_20260926 as I
import set_b_shared_front_r2_20260926 as K
ROOT=P.ROOT;OUT=ROOT/'build/set-b-front-paths-query-r1'
PRE=r'''
#include "c2_bank2_code_domain.h"
#define NIL 0
#define MKFIX(n) ((obj)(((uint16_t)(n)<<1)|1u))
#define c2aw work
#define C2_FRONT_SCAN_FN static
#define RCOMMIT
#define LISP65_C2_PHASE_OWNER_NONE 0u
#define LISP65_C2_PHASE_OWNER_EMITTER 1u
#define LISP65_C2_PHASE_OWNER_APPEND 2u
#define LISP65_C2_INSTALL_LAST_SLOT_OFFSET 302u
#define LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT 29u
uint8_t c2_ready=1,c2_phase_owner,lisp65_c2_phase_scratch[304];
typedef c2_append_state c2_bank2_population;
typedef c2_append_state c2_bank2_front_population;
static uint32_t c2_u32(const uint8_t*p){return c2_u16(p)|((uint32_t)c2_u16(p+2)<<16);}
static uint16_t query_value,allocations,allocation_owner_error;
static obj cons(obj a,obj b){++allocations;if(c2_phase_owner)++allocation_owner_error;query_value=((uint16_t)a>>1)+(((uint16_t)b>>1)<<8);return 2;}
static uint8_t c2_overlay_call(uint8_t slot,void*ctx);
static uint8_t rm_write(uint16_t at,const uint8_t*p,uint8_t n){return c2_stream_c2d_write(at,p,n);}
'''
TAIL=r'''
static uint8_t c2_overlay_call(uint8_t slot,void*ctx){
 if(slot!=29 || ctx!=&work || c2_phase_owner!=2)return 0;
 lisp65_c2_phase_scratch[302]=slot;
 return c2_append_reserve_persistent_code_phase(ctx)==C2_STREAM_OK;
}
uint16_t query_result[10];
void query_test(uint8_t mode,uint16_t fail,uint8_t partial){
 writer_setup(0,0,0,0,0);c2_phase_owner=0;c2_ready=1;allocations=allocation_owner_error=0;
 memset(c2_front_certificate,0,4);lisp65_c2_phase_scratch[302]=73;
 /* One valid published population, constructed with the product serializer. */
 for(uint8_t i=0;i<2;++i)c2d_v6_emit_entry_row(arena+2096+i*10,1,0,100+i*7,7,0,1);
 obj first=c2_resolver_charged_front();(void)first;reads=0;allocations=0;query_value=65535;
 if(mode==1){uint8_t image[32]={0};c2_record_u16(image+6,0);c2_record_u16(image+8,2);(void)rm_own(image,255);}
 if(mode>=2 && mode<=5){
  if(mode!=2)c2_front_raw_write();
  if(mode==4)c2_record_u16(arena+2096+4,0);else c2_record_u16(arena+2096+2,200);
  if(mode!=2)c2_front_raw_write();
 }
 if(mode==5)c2_front_abort();
 if(mode==6)c2_front_abort();
 fault_read=fail;copy_mode=partial;
 obj result=c2_resolver_charged_front();
 query_result[0]=result!=NIL;query_result[1]=query_value;query_result[2]=c2_front_certificate[2];
 query_result[3]=reads;query_result[4]=c2_phase_owner;query_result[5]=lisp65_c2_phase_scratch[302];
 query_result[6]=allocations;query_result[7]=allocation_owner_error;query_result[8]=bounds_errors;query_result[9]=C2AW_RESERVE_MARK(&work);
}
uint16_t stage_result[7];
void stage_test(uint8_t t,uint16_t fw,uint16_t fr,uint8_t partial,uint8_t mark){
 writer_setup(t,fw,fr,0,partial);work.staged=0;C2AW_STAGE_MARK(&work)=mark;
 memcpy(checkpoint,arena,sizeof arena);uint8_t status=c2_append_stage_plane_phase(&work);
 stage_result[0]=status;stage_result[1]=work.staged;stage_result[2]=C2AW_STAGE_MARK(&work);
 stage_result[3]=writes;stage_result[4]=reads;stage_result[5]=bounds_errors;stage_result[6]=c2_runtime.entry_cursor;
}
'''
def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    base=ROOT/'build/set-b-front-paths-writers-r3/fixture.c';s=base.read_text()
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text();assert K.HELPER in runtime
    names=['C2AW_FRONT_ENTRIES','C2AW_RESERVE_MARK','C2_RESERVE_SCAN_REQUEST','C2_RESERVE_SCAN_DONE','C2_RESERVE_PERSISTENT_MARK','C2_APPEND_CAPACITY_CAUSE','C2AW_STAGE_MARK','C2_STAGE_COPY_MARK']
    macros='\n'.join(re.search(r'^#define '+n+r'\b[^\n]*',runtime,re.M)[0] for n in names)+'\n'
    scratch=(ROOT/'src/c2_phase_scratch.c').read_text();retire=(ROOT/'src/optional/set_b_retire_commit_b.c').read_text()
    functions=[I.function(runtime,n) for n in ('c2_record_u32','c2_lite_bank2_scan','c2_append_reserve_persistent_code_phase','c2_append_stage_plane_zero','c2_append_stage_plane_phase')]
    functions += [I.function(scratch,n) for n in ('c2_phase_scratch_acquire','c2_phase_scratch_release')]+[I.function(retire,'rm_own')]
    # rm_own uses same-line closing braces, so the generic extractor includes rm_finish: isolate exact text by next declaration.
    functions[-1]=retire[retire.index('RCOMMIT static uint8_t rm_own'):retire.index('RCOMMIT static uint8_t rm_finish')]
    for i,f in enumerate(functions):(OUT/f'extracted-{i}.c').write_text(f)
    fixture=OUT/'fixture.c';fixture.write_text(s+macros+PRE+'\n'.join(functions)+K.HELPER+TAIL)
    (OUT/'c2-stream-decoder.h').write_bytes((base.parent/'c2-stream-decoder.h').read_bytes())
    cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(fixture),'-o',str(OUT/'fixture.so')]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert not r.returncode,r.stderr
    d=C.CDLL(str(OUT/'fixture.so'));d.query_test.argtypes=[C.c_uint8,C.c_uint16,C.c_uint8];d.stage_test.argtypes=[C.c_uint8,C.c_uint16,C.c_uint16,C.c_uint8,C.c_uint8]
    rows=[];halt=None
    for mode in range(7):
        for fail in range(4):
            for partial in (0,1,2):
                d.query_test(mode,fail,partial);got=list((C.c_uint16*10).in_dll(d,'query_result'))
                expected_value=114 if mode in (0,1,2,6) else 207
                expected_reads=1 if mode in (0,1,2) else 3
                bad=mode==4 or (fail>0 and fail<=expected_reads)
                expected_state=(4 if mode in (3,4,5) else 0) if bad else (4 if mode in (3,5) else 1)
                ok=got[0]==int(not bad) and got[1]==(65535 if bad else expected_value) and got[2]==expected_state and got[4:]==[0,73,int(not bad),0,0,0]
                row=dict(kind='query',mode=mode,fail_read=fail,partial=partial,actual=got,expected_value=None if bad else expected_value,expected_state=expected_state,pass_gate=ok)
                rows.append(row)
                if not ok:halt=row;break
            if halt:break
        if halt:break
    if not halt:
        for t in (0,1):
            for fw,fr,mark in [(0,0,0),(0,0,0x53),(0,1,0x53)]+[(i,0,0x53) for i in range(1,7)]:
                for partial in (0,1,2):
                    d.stage_test(t,fw,fr,partial,mark);got=list((C.c_uint16*7).in_dll(d,'stage_result'))
                    # Existing void-write contract: zero submissions are checked by later completion fences.
                    expected=[8,0,0,0,0,0,114] if not mark else [1,0,0x53,0,1,0,114] if fr else [0,1,0,6,1,0,114]
                    row=dict(kind='stage-plane',transient=t,fail_write=fw,fail_read=fr,partial=partial,mark=mark,actual=got,expected=expected,pass_gate=got==expected);rows.append(row)
                    if got!=expected:halt=row;break
                if halt:break
            if halt:break
    P.write(OUT/'rows.json',rows)
    if halt:P.write(OUT/'halt.json',halt)
    P.write(OUT/'receipt.json',dict(status='HALT QUERY OR STAGE SUCCESSOR' if halt else 'PASS REAL SCANNER CERTIFICATE RETIREMENT-OWNER AND STAGE-PLANE C',
        driver=P.bind(Path(__file__)),execution_head='9013c3fc',source=P.bind(F.OUT/'candidate/src/c2_product_runtime.c'),base_fixture=P.bind(base),
        retirement=P.bind(ROOT/'src/optional/set_b_retire_commit_b.c'),scratch=P.bind(ROOT/'src/c2_phase_scratch.c'),
        fixture=P.bind(fixture),command=P.bind(OUT/'command.json'),library=P.bind(OUT/'fixture.so'),rows=P.bind(OUT/'rows.json'),
        row_count=len(rows),passing_rows=sum(x['pass_gate'] for x in rows),halt=P.bind(OUT/'halt.json') if halt else None,
        scope='Exact scan/reserve entry/certificate, scratch ownership, retirement owner loop and stage-plane functions joined to real writer fixture. Unnotified address mutation is an intentional stale-cache falling control; notified mutation forces scans.',
        limits='CPU poke physical store, DMA/map transport, full retirement and journal completion fence not executed. Stage zero-write returns intentionally ignored in maintained source; later fence obligation retained.',
        host_c_compiles=1,host_c_links=1,product_builds=0,product_links=0,seeds=0,guest_runs=0,device_contacts=0))
    print('HALT' if halt else 'PASS',len(rows),'query/stage rows')
if __name__=='__main__':main()
