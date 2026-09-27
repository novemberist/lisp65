"""Execute exact append/terminal/recovery callers with declared transport seams."""
from pathlib import Path
import ctypes as C
import re
import subprocess
import set_b_producer as P
import set_b_front_span_20260926 as F
import set_b_front_span_faults_20260926 as D
import set_b_front_integration_r2_20260926 as I
import set_b_shared_front_r2_20260926 as K
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-span-lifetime-r2'

SEAMS=r'''
#define C2_KERNAL_RESIDENT
#define VM_RUNTIME_OVERLAY_OK 0
#define LISP65_RUNTIME_OVERLAY_FAMILY_SESSION 2u
uint8_t lisp65_c2_phase_scratch[LISP65_C2_PHASE_SCRATCH_BYTES],c2_phase_owner;
static uint16_t c2_journal_count,c2_pending_roots;
static uint8_t mode,steps,rollbacks,ended_state,trace_ok,recovery_calls,bad_valid;
static uint8_t seen_state[64];
static uint16_t seen_pending[64],seen_world[64];
static jmp_buf jump;
static uint8_t c2_overlay_call(uint8_t,void*);
static uint8_t c2_overlay_call_range(uint8_t,uint8_t,void*);
static uint8_t c2_append_run_stage_plan(void*);
static uint8_t c2_append_run_persistent_publish_plan(void*);
static uint8_t c2_append_run_rollback_plan(void*);
static uint8_t c2_decode_from(c2_stream_context*,uint8_t);
static uint8_t vm_runtime_overlay_transaction_begin(uint8_t,uint16_t);
static uint8_t vm_runtime_overlay_transaction_end(void);
static uint8_t vm_runtime_overlay_abort_cleanup(void);
void c2_boot_name_index_invalidate(void);
uint8_t c2_retire_run(uint8_t);
static uint8_t c2_abort_empty_journal_derived(void);
'''
IMPL=r'''
/* Controlled seams: no real stage/publication/journal/transport writes. */
static void sample(void){
 if(steps<64){seen_state[steps]=c2_front_certificate[2];seen_pending[steps]=c2aw.append.entry_cursor;
 seen_world[steps]=c2_runtime.entry_cursor;}
 ++steps;if(c2_front_certificate[2]&FC_VALID)++bad_valid;
}
static uint8_t c2_overlay_call(uint8_t slot,void*w){
 (void)w;sample();
 if(mode==1 && slot==LISP65_C2_APPEND_ROOTS_FRONTS_SLOT)return 0;
 if(mode==2 && slot==LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT){c2aw.append.error=C2_APPEND_CAPACITY_CAUSE;return 0;}
 if(slot==LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT)C2AW_JOURNAL_RESULT(&c2aw)=C2J_RESULT_PREPARED;
 if(slot==LISP65_C2_APPEND_HEADER_SLOT)c2_runtime=c2aw.append;
 if(mode==6 && slot==LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT)return 0;
 return 1;
}
static uint8_t c2_overlay_call_range(uint8_t a,uint8_t b,void*w){
 sample();if(a==LISP65_C2_APPEND_ENVELOPE_SLOT)*c2aw.before=c2_runtime;
 if(a==LISP65_C2_APPEND_ENVELOPE_SLOT && mode==3)return 0;
 for(uint8_t i=a;i<=b;++i)if(!c2_overlay_call(i,w))return 0;
 return 1;
}
static uint8_t c2_append_run_stage_plan(void*w){
 (void)w;sample();c2aw.staged=1;c2aw.entries=2;
 if(mode==4)return 0;
 if(mode==10){c2_front_raw_write();}
 if(mode==11){c2_product_abort_cleanup(47);longjmp(jump,1);}
 return 1;
}
static uint8_t c2_decode_from(c2_stream_context*c,uint8_t phase){
 (void)phase;sample();
 if(n_phase04(c)||n_phase05a(c)||n_phase05b(c))return 0;
 sample();if(mode==5)return 0; /* seam for later decoder refusal */
 return 1;
}
static uint8_t c2_append_run_persistent_publish_plan(void*w){
 (void)w;sample();if(mode==7)return 0;c2_runtime=c2aw.append;return 1;
}
static uint8_t c2_append_run_rollback_plan(void*w){
 (void)w;sample();++rollbacks;c2_runtime=*c2aw.before;return 1;
}
static uint8_t vm_runtime_overlay_transaction_begin(uint8_t family,uint16_t generation){
 (void)family;(void)generation;return mode==8?1:0;
}
static uint8_t vm_runtime_overlay_transaction_end(void){
 ended_state=c2_front_certificate[2];return mode==9?1:0;
}
void c2_rtov_retire_continuations_facade(uint8_t slot){(void)slot;}
static uint8_t vm_runtime_overlay_abort_cleanup(void){
 trace_ok=(uint8_t)(!(c2_front_certificate[2]&(FC_VALID|FC_BUSY|FC_REFILL))
   && (!(mode==20)||(!c2_phase_owner && !C2AW_RESERVE_MARK(&c2aw)
     && lisp65_c2_phase_scratch[LISP65_C2_INSTALL_LAST_SLOT_OFFSET]==73)));
 return 0;
}
void c2_boot_name_index_invalidate(void){++recovery_calls;}
uint8_t c2_retire_run(uint8_t x){(void)x;++recovery_calls;return 1;}
static uint8_t c2_abort_empty_journal_derived(void){
 ++recovery_calls;(void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
 (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER);return mode!=21;
}
uint8_t c2_abort_driver_facade(void){++recovery_calls;return 1;}

/* Results are plain integers for ctypes, no host-layout serialization. */
uint16_t lifetime_result[14];
void lifetime_run(uint8_t kind,uint8_t m,uint8_t mutation,uint8_t f,uint8_t part){
 setup(mutation,f,part,0);mode=m;steps=rollbacks=ended_state=recovery_calls=bad_valid=0;trace_ok=1;
 memset(seen_state,0,sizeof seen_state);memset(seen_pending,0,sizeof seen_pending);memset(seen_world,0,sizeof seen_world);
 memset(lisp65_c2_phase_scratch,0xa5,sizeof lisp65_c2_phase_scratch);c2_phase_owner=0;
 memset(c2_front_certificate,0,sizeof c2_front_certificate);c2_front_begin();c2_front_publish(90);
 c2_runtime.entry_cursor=90;c2_runtime.generation=1;
 c2_stream_context before=c2_runtime;uint16_t ordinal=0;uint8_t ok=0;
 if(kind==0){if(!setjmp(jump))ok=c2_product_append_staged_result(64);else ok=c2_product_abort_recover();}
 if(kind==1){ok=c2_append_begin(64,&before,&ordinal,1);ended_state=c2_front_certificate[2];
   if(ok)c2_front_publish(c2_runtime.entry_cursor);}
 if(kind==2){c2aw.before=&before;ok=c2_append_rollback(&before);}
 if(kind==3){
   c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND);c2_front_certificate[2]=FC_BUSY|FC_REFILL|(m==22?FC_TAINTED:0);
   c2_front_certificate[3]=73;C2AW_RESERVE_MARK(&c2aw)=C2_RESERVE_SCAN_REQUEST;
   ok=c2_product_abort_cleanup(47);ok&=c2_product_abort_recover();
 }
 if(kind==4){c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_EMITTER);ok=c2_product_append_staged_result(64);}
 if(kind==5){c2_front_begin();ok=c2_product_append_staged_result(64);}
 if(kind==6){c2_front_certificate[2]=FC_TAINTED|FC_BUSY;c2_front_boot_reset();ok=1;}
 lifetime_result[0]=ok;lifetime_result[1]=c2_front_certificate[2];lifetime_result[2]=c2_u16(c2_front_certificate);
 lifetime_result[3]=c2_runtime.entry_cursor;lifetime_result[4]=c2aw.append.entry_cursor;lifetime_result[5]=c2_phase_owner;
 lifetime_result[6]=c2_ready;lifetime_result[7]=rollbacks;lifetime_result[8]=ended_state;lifetime_result[9]=trace_ok;
 lifetime_result[10]=recovery_calls;lifetime_result[11]=bad_valid;lifetime_result[12]=steps;lifetime_result[13]=ordinal;
}
uint16_t boundary(uint8_t i,uint8_t col){return col==0?seen_state[i]:col==1?seen_pending[i]:seen_world[i];}
'''

def main():
    F.S.require_auth();assert P.load(D.OUT/'receipt.json')['halt'] is None
    OUT.mkdir(exist_ok=False)
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text()
    commands=P.load(ROOT/'build/set-b-front-span-native-r1/commands.json')
    defines=[x[2:] for x in commands[0]['command'] if x.startswith('-D')]
    profile=''.join('#define '+x.replace('=',' ',1)+('' if '=' in x else ' 1')+'\n' for x in defines)
    # obj.h keeps the host ABI; only the runtime callers select their MOS branch.
    profile+='#include "obj.h"\n#define __mos__ 1\n#include "c2_product_runtime.h"\n#include "c2_phase_scratch.h"\n#include <setjmp.h>\n'
    pre=(D.OUT/'fixture.c').read_text()
    for line in ('#define C2_FRAME_ATTRIBUTION_STAMP(n) ((void)0)\n','#define C2_STREAM_PRODUCT_V3 1\n','#define LISP65_C2_LITE_COLD_EVICTION 1\n',
                 '#define LISP65_C2_SESSION_BYTES 65536UL\n','#define LISP65_C2_BANK2_CODE_LIMIT 60758UL\n'):
        pre=pre.replace(line,'')
    pre=pre.replace('uint32_t attic;} c2aw;', 'uint32_t attic;c2_stream_context *before;uint16_t *main_ordinal;uint8_t committed,rollback_rebuild_header;uint16_t new_roots,new_entries,entries;} c2aw;')
    macros=['C2D_ENTRY_CAP','C2D_ROOT_CAP','C2D_HANDLE_CAP','C2J_RESULT_NONE','C2J_RESULT_PREPARED',
        'C2_APPEND_FLAG_TRANSIENT','C2_APPEND_BEGIN_OK','C2_APPEND_BEGIN_CAPACITY','C2_APPEND_CAPACITY_CAUSE',
        'C2AW_JOURNAL_RESULT','C2AW_COMPLETION_MARK','C2AW_RESERVE_MARK','C2AW_FUSED_PHASE_MARK',
        'C2AW_ROOTS_FRONTS_MARK','C2AW_PUBLISH_CLEAR_MARK','C2_ROOTS_REQUEST_MARK','C2_FRONTS_REQUEST_MARK',
        'C2_CLEAR_REQUEST_MARK','C2_COMPLETION_PUBLISH_MARK','C2_RESERVE_SCAN_REQUEST']
    constants='\n'.join(re.search(r'^#define '+n+r'\b[^\n]*',runtime,re.M)[0] for n in macros)+'\n'
    kernel=K.HELPER.split('FC_FN obj c2_resolver_charged_front',1)[0];assert kernel in runtime
    scratch=(ROOT/'src/c2_phase_scratch.c').read_text()
    functions=[I.function(scratch,n) for n in ('c2_phase_scratch_acquire','c2_phase_scratch_release')]
    tail=runtime[runtime.index('uint8_t c2_append_entries_phase'):]
    functions += [I.function(tail,'c2_append_begin'),I.function(runtime,'c2_append_rollback')]
    functions += ['#if defined(__mos__) && defined(LISP65_C2_RTOV_CONTINUATION_LIVENESS)\n'+I.function(runtime,'c2_product_abort_cleanup'),
        I.function(runtime,'c2_product_abort_recover'),I.function(runtime,'c2_product_append_staged_result')]
    for i,f in enumerate(functions):(OUT/f'extracted-{i}.c').write_text(f)
    fixture=OUT/'fixture.c';fixture.write_text(profile+pre+constants+SEAMS+kernel+'\n'+'\n'.join(functions)+IMPL)
    (OUT/'c2-stream-decoder.h').write_bytes((D.OUT/'c2-stream-decoder.h').read_bytes())
    lib=OUT/'fixture.so';cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(fixture),'-o',str(lib)]
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert not r.returncode,r.stderr
    d=C.CDLL(str(lib));d.lifetime_run.argtypes=[C.c_uint8]*5;d.boundary.argtypes=[C.c_uint8]*2;d.boundary.restype=C.c_uint16
    keys=['result','state','certificate_front','world_front','pending','owner','ready','rollbacks','terminal_state','trace_ok','recovery_calls','premature_valid','boundaries','ordinal']
    rows=[];halt=None
    def run(kind=0,mode=0,mutation=0,fault=0,partial=0):
        d.lifetime_run(kind,mode,mutation,fault,partial)
        got=dict(zip(keys,list((C.c_uint16*14).in_dll(d,'lifetime_result'))))
        boundaries=[[d.boundary(i,j) for j in range(3)] for i in range(got['boundaries'])]
        return dict(kind=kind,mode=mode,mutation=mutation,fault=fault,partial=partial,actual=got,boundaries=boundaries)
    def add(row,expected):
        nonlocal halt
        row['expected']=expected;row['pass']=all(row['actual'][k]==v for k,v in expected.items())
        rows.append(row)
        if not row['pass']:halt=row;return False
        return True
    # Terminal wrapper: failures before writes, decoder failures after writes,
    # later-phase/publication/clear failures, terminal refusal, sticky raw taint.
    for mode in range(12):
        expected=dict(result=1 if mode in (0,10,11) else 2 if mode==2 else 0,
            state=1 if mode==0 else 4 if mode==10 else 0,owner=0,ready=1,premature_valid=0)
        if mode==8:expected['state']=1 # transaction not entered; no invalidation is required
        expected['world_front']=114 if mode in (0,9,10) else 90
        expected['rollbacks']=1 if mode in (4,5,6,7) else 0
        if mode==0:expected.update(certificate_front=114,terminal_state=2)
        if mode==11:expected.update(trace_ok=1,recovery_calls=3)
        if not add(run(mode=mode),expected):break
    if not halt:
        for mutation in range(16):
            # setup only supports0..10 here; later mutations already qualified by decoder fixture.
            if mutation>10:continue
            for fault in (0,1,2,3,5,6,7):
                for partial in ((0,) if not fault else (0,1,2)):
                    ref=next(r for r in P.load(D.OUT/'rows.json') if r['kind']=='decoder-matrix' and
                        (r['mutation'],r['boot'],r['fault'],r['partial'])==(mutation,0,fault,partial))['candidate']
                    passed=ref['status']==0
                    expected=dict(result=int(passed),state=int(passed),owner=0,ready=1,premature_valid=0,
                        world_front=ref['pending'] if passed else 90,rollbacks=int(not passed))
                    if not add(run(mutation=mutation,fault=fault,partial=partial),expected):break
                if halt:break
            if halt:break
    if not halt:
        for kind,mode,mut,expected in [
            (1,0,9,dict(result=1,state=1,certificate_front=90,world_front=90,pending=60014,owner=0,terminal_state=2)),
            (2,0,0,dict(result=1,state=0,world_front=90,owner=0,rollbacks=1)),
            (3,20,0,dict(result=1,state=0,owner=0,trace_ok=1,recovery_calls=3)),
            (3,21,0,dict(result=1,state=0,owner=0,trace_ok=1,recovery_calls=4)),
            (3,22,0,dict(result=1,state=4,owner=0,trace_ok=1,recovery_calls=3)),
            (4,0,0,dict(result=0,state=0,owner=1,world_front=90)),
            (5,0,0,dict(result=0,state=0,owner=0,world_front=90)),
            (6,0,0,dict(result=1,state=0,owner=0,world_front=90))]:
            expected.update(ready=1,premature_valid=0)
            if not add(run(kind,mode,mut),expected):break
    P.write(OUT/'rows.json',rows)
    if halt:P.write(OUT/'first-unbound-error.json',halt)
    status='HALT: LIFETIME SUCCESSOR REQUIRES ATTRIBUTION' if halt else 'PASS EXTRACTED C CALLER LIFETIME WITH DECLARED SEAMS'
    P.write(OUT/'receipt.json',dict(status=status,driver=P.bind(Path(__file__)),execution_head='09c7c983',
        source=P.bind(F.OUT/'candidate/src/c2_product_runtime.c'),decoder_fixture=P.bind(D.OUT/'receipt.json'),
        profile=P.bind(ROOT/'build/set-b-front-span-native-r1/commands.json'),scratch_source=P.bind(ROOT/'src/c2_phase_scratch.c'),
        fixture=P.bind(fixture),command=P.bind(OUT/'command.json'),library=P.bind(lib),rows=P.bind(OUT/'rows.json'),
        row_count=len(rows),passing_rows=sum(r['pass'] for r in rows),halt=P.bind(OUT/'first-unbound-error.json') if halt else None,
        host_c_compiles=1,host_c_links=1,
        scope='Exact seven caller/scratch functions, certificate kernel and decoder04/05a/05b. Native conditional paths with host object ABI. Synthetic transaction struct; controlled stage, overlay, later decoder, publication, rollback and recovery transport seams.',
        limits='Not real C2D/journal writers, resolver query or raw-writer closure, whole-product exact BAD BYTECODE, native ABI/code/stack/GC/transport proof.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print(status,len(rows),'rows;',sum(r['pass'] for r in rows),'pass')

if __name__=='__main__':main()
