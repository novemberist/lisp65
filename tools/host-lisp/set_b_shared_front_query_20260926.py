"""Replay actual C rows with exact scan/entry and controlled transport seams."""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_front_prototype_query_20260926 as Q
import set_b_shared_front_20260926 as R1
import set_b_shared_front_r2_20260926 as R2

ROOT=P.ROOT
PRE=r'''
static unsigned char fixture_owner(void);
unsigned char allocation_owner_fault;
'''
SHARED=r'''
#include <stddef.h>
#include <setjmp.h>
#define LISP65_C2_LITE_V6_SEMANTIC_SPLITS 1
#define LISP65_C2D_V6_ENTRY_BYTES 10u
#define LISP65_C2_PHASE_OWNER_APPEND 2u
#define LISP65_C2_INSTALL_LAST_SLOT_OFFSET 302u
#define LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT 29u
#define C2_RESERVE_SCAN_REQUEST 0x62u
#define C2_RESERVE_SCAN_DONE 0x64u
#define C2_RESERVE_PERSISTENT_MARK 0x70u
#define C2_STREAM_OK 0u
#define C2_STREAM_ERR_STATE 8u
#define C2_STREAM_ERR_C2D 7u
#define C2_APPEND_CAPACITY_CAUSE 9u
#define C2_FRONT_SCAN_FN static
/* Only fields read on the SCAN branch have target offsets in this scaffold.
 * The non-SCAN branch remains exact source but is never selected here. */
typedef struct {uint8_t pad[182],record[32];uint16_t code_len;
 struct {uint8_t error;} append;uint8_t transient;} c2_append_state;
typedef c2_append_state c2_bank2_front_population;
_Static_assert(offsetof(c2_append_state,record)==182,"record ABI");
uint8_t lisp65_c2_phase_scratch[304]={[302]=77,[303]=129};
uint8_t phase_owner,transport_mode,transport_latch,abort_seen,cons_clobber;
uint32_t overlays,entries,release_calls;
static jmp_buf abort_env;
static uint8_t fixture_owner(void){return phase_owner;}
#define c2aw (*(c2_append_state *)(void *)lisp65_c2_phase_scratch)
#define C2AW_FRONT_ENTRIES(w) c2_u16((w)->record+2)
#define C2AW_RESERVE_MARK(w) ((w)->record[20])
#define C2AW_TRANSIENT(w) ((w)->transient)
#define C2_INSTALL_TRACE_STAMP_SLOT(slot) (lisp65_c2_phase_scratch[302]=(slot))
static uint32_t c2_u32(const uint8_t *p){return c2_u16(p)|((uint32_t)c2_u16(p+2)<<16);}
static void c2_record_u16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void c2_record_u32(uint8_t *p,uint32_t v){c2_record_u16(p,(uint16_t)v);c2_record_u16(p+2,(uint16_t)(v>>16));}
static uint8_t c2_bank2_code_range(uint32_t at,uint32_t n){return at<=60758UL && n<=60758UL-at;}
static uint8_t c2_phase_scratch_acquire(uint8_t owner){
 if((owner!=1u && owner!=2u) || phase_owner!=0u)return 0;
 phase_owner=owner;return 1;
}
static uint8_t c2_phase_scratch_release(uint8_t owner){
 release_calls++;
 if(transport_mode==7 || owner==0u || phase_owner!=owner)return 0;
 phase_owner=0u;return 1;
}
static uint8_t c2_overlay_call(uint8_t slot,void *context);
'''
SUFFIX=r'''
uint8_t state(void){return c2_front_certificate[2];}
static uint8_t c2_overlay_call(uint8_t slot,void *context){
 uint8_t status;
 overlays++;
 if(slot!=29u || phase_owner!=2u || context!=&c2aw)return 0;
 if(transport_latch)return 0;
 if(transport_mode==1)return 0; /* family/busy refusal, no latch */
 if(transport_mode==2){transport_latch=7;return 0;} /* pre-entry fault */
 if(transport_mode==5)longjmp(abort_env,1);
 if(transport_mode==8){
  if(c2_front_begin()!=0 || c2_front_publish(1)!=0 || c2_resolver_charged_front()!=NIL)
   allocation_owner_fault=1;
  c2_front_raw_write();
 }
 entries++;status=c2_append_reserve_persistent_code_phase(context);
 if(transport_mode==6)longjmp(abort_env,1);
 if(transport_mode==3){transport_latch=8;return 0;} /* final wipe failure */
 if(transport_mode==4)C2AW_RESERVE_MARK(&c2aw)=0; /* missing DONE control */
 return status==C2_STREAM_OK;
}
obj invoke(void){
 if(setjmp(abort_env)){
  abort_seen=1;
  /* Proposed hook ordering, not installed product recovery. These forced
   * releases mirror the existing recovery preamble after the new hook. */
  c2_front_abort();
  (void)c2_phase_scratch_release(2u);(void)c2_phase_scratch_release(1u);
  return NIL;
 }
 return c2_resolver_charged_front();
}
void fixture_reset(void){
 transport_mode=transport_latch=phase_owner=abort_seen=cons_clobber=allocation_owner_fault=0;
 overlays=entries=release_calls=0;
 memset(lisp65_c2_phase_scratch,0xa5,304);
 lisp65_c2_phase_scratch[302]=77;lisp65_c2_phase_scratch[303]=129;
 c2_front_boot_reset();
}
'''
EXTRA=r'''
    base_rows=len(rows);assert base_rows==4536
    gaps=[]
    def byte(name,v):C.c_uint8.in_dll(d,name).value=v
    def reset():d.fixture_reset();plane(base,True)
    def scratch():return bytes((C.c_uint8*304).in_dll(d,'lisp65_c2_phase_scratch'))
    reset();d.mismatch();query('shared-context-mismatch',None,1,0)
    reset();C.c_uint16.in_dll(d,'fixture_bad_offset').value=2097
    d.set_offset();query('shared-wrong-table-base',None,1,0)
    for owner in (1,2):
        reset();byte('phase_owner',owner);before=scratch()
        query('shared-owner-busy-'+str(owner),None,1,0)
        assert scratch()==before and field('phase_owner',C.c_uint8)==owner
        assert field('overlays')==0 and field('release_calls')==0
    for mode in (1,2,3,4):
        reset();byte('transport_mode',mode);before=scratch()
        query('shared-transport-'+str(mode),None,1 if mode<3 else count+1,0)
        assert scratch()[302:]==before[302:] and scratch()[202]==0
        assert field('phase_owner',C.c_uint8)==0
        assert field('entries')==int(mode>=3)
        if mode in (2,3):
            latch=field('transport_latch',C.c_uint8);assert latch
            byte('transport_mode',0);query('shared-latch-persists-'+str(mode),None,1,0)
            assert field('transport_latch',C.c_uint8)==latch
    reset();byte('transport_mode',7)
    query('shared-release-refusal',None,count+1,0)
    assert field('phase_owner',C.c_uint8)==2 and field('allocations')==0
    assert scratch()[302:]==bytes([77,129])
    reset();byte('cons_clobber',1)
    query('shared-result-survives-scratch-reuse-by-cons',front,count+1,1)
    assert scratch()[194:198]==b'\x5a'*4 and not field('allocation_owner_fault',C.c_uint8)
    for mode in (5,6):
        reset();byte('transport_mode',mode);d.configure(0,0,1)
        assert d.invoke()==0 and d.state()==0 and field('abort_seen',C.c_uint8)==1
        assert field('phase_owner',C.c_uint8)==0 and field('allocations')==0
        trace_ok=scratch()[302:]==bytes([77,129]);marker_ok=scratch()[202]==0
        row=dict(case='shared-nonlocal-'+str(mode),trace_restored=trace_ok,marker_cleared=marker_ok,
            owner_released=True,certificate_invalid=True,execution='Actual C setjmp/longjmp; proposed recovery-hook ordering seam')
        if REVISION==1:
            assert not marker_ok
            if mode==6:assert not trace_ok
            gaps.append(row)
        else:assert trace_ok and marker_ok
        rows.append(row)
        # Fixture resets transport mode but keeps recovered directory and certificate.
        byte('transport_mode',0);query('shared-refill-after-nonlocal-'+str(mode),front,count+1,1)
    if REVISION==2:
        reset();byte('transport_mode',8)
        query('shared-reentrant-refusal-and-raw-during-refill',front,count+1,4)
        assert field('allocation_owner_fault',C.c_uint8)==0 and scratch()[302:]==bytes([77,129])
    reset();query('shared-final-clean-refill',front,count+1,1)
    P.write(OUT/'integration-gap-controls.json',gaps)
'''

def main(revision):
    k=R1 if revision==1 else R2
    out=ROOT/f'build/set-b-shared-front-query-r{revision}'
    driver=ROOT/f'build/set-b-shared-front-query-driver-r{revision}';driver.mkdir(exist_ok=False)
    prefix=PRE+Q.PREFIX
    prefix=prefix.replace('generation,entry_count;}','generation,entry_count,entries_offset;}')
    prefix=prefix.replace('allocations++;','if(fixture_owner())allocation_owner_fault=1;allocations++;')
    prefix=prefix.replace('c2_runtime.entry_count=c2_u16(p+16);','c2_runtime.entry_count=c2_u16(p+16);c2_runtime.entries_offset=2096;')
    prefix+=SHARED+(k.OUT/'existing-scan.inc').read_text()+(k.OUT/'existing-entry.inc').read_text()
    suffix=SUFFIX+'\nuint16_t fixture_bad_offset;void set_offset(void){c2_runtime.entries_offset=fixture_bad_offset;}\n'
    # Simulated allocator reuses scratch only after ownership has been released.
    prefix=prefix.replace('static obj cons(obj a,obj b){', 'void fixture_cons_hook(void);\nstatic obj cons(obj a,obj b){fixture_cons_hook();')
    suffix+='void fixture_cons_hook(void){if(cons_clobber)memset(lisp65_c2_phase_scratch+194,0x5a,4);}\n'
    source=inspect.getsource(Q.main)
    source=source.replace("    base=(", "    base=(")
    source=source.replace("    d.c2_resolver_charged_front.restype=C.c_int16", "    d.c2_resolver_charged_front.restype=C.c_int16\n    d.invoke.restype=C.c_int16;d.fixture_reset()")
    source=source.replace('result=d.c2_resolver_charged_front()', 'result=d.invoke()')
    source=source.replace("        rows.append(dict(case=label,result=got,", "        assert field('allocation_owner_fault',C.c_uint8)==0,label\n        rows.append(dict(case=label,result=got,")
    source=source.replace("    P.write(OUT/'rows.json',rows)",EXTRA+"\n    P.write(OUT/'rows.json',rows)")
    source=source.replace("status='PASS ISOLATED C PROTOCOL AND REFILL; INTEGRATION UNPROVED'", "status=('NORMAL ROWS PASS; NONLOCAL CLEANUP GAP CONTROL' if REVISION==1 else 'PASS SHARED C QUERY AND PROPOSED ABORT CLEANUP; PRODUCT INTEGRATION UNPROVED')")
    source=source.replace("negative_control='Unnotified plane mutation", "revision=REVISION,integration_gaps=P.bind(OUT/'integration-gap-controls.json'),entry=P.bind(K.OUT/'existing-entry.inc'),scan=P.bind(K.OUT/'existing-scan.inc'),negative_control='Unnotified plane mutation")
    source=source.replace("limits='Transport, cons, runtime context and publication callers are fixture stubs. No product lifecycle hooks, actual INIT, collector, native timing or linked placement proof.'", "limits='Exact scanner and entry source execute with scaffold context and stubbed overlay transport/cons. Nonlocal abort executes C longjmp and proposed hook ordering before existing forced releases; no real product abort/transport, hooks, INIT, collector, time or linked placement proof.'")
    executed=driver/'executed-main.py';executed.write_text(source)
    P.write(driver/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(Q.__file__)),
        executed=P.bind(executed),kernel=P.bind(k.OUT/'certificate.inc'),revision=revision))
    ns=dict(vars(Q),K=k,OUT=out,PREFIX=prefix,SUFFIX=suffix,REVISION=revision,__file__=__file__)
    exec(compile(source,str(executed),'exec'),ns);ns['main']()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('revision',type=int,choices=(1,2))
    main(p.parse_args().revision)
