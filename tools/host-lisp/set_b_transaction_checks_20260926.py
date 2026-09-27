"""Execute candidate resident C and control C with explicit host fault stubs.

This exercises ownership/error ordering; it is not a product emulator gate.
"""
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
ROOT=P.ROOT
OUT=ROOT/'build/set-b-transaction-checks-r1'
PROP=ROOT/'build/set-b-transaction-proposal-r1'
PREFIX=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <setjmp.h>
#define C2_APPEND_SECTION(x)
#define VM_RUNTIME_OVERLAY_OK 0
#define LISP65_RUNTIME_OVERLAY_FAMILY_SESSION 2
#define LISP65_C2_PHASE_OWNER_APPEND 2
#define LISP65_C2_PHASE_OWNER_EMITTER 1
#define C2_STREAM_OK 0
#define C2_STREAM_ERR_STATE 8
#define C2_STREAM_ERR_C2D 3
#define C2D_HANDLE_CAP 4096
#define C2D_UNWIND_BASE 50752
static uint8_t c2r_boot_count, gc_rootsp, c2_journal_count, c2r_gc_failed;
static uint16_t c2_pending_roots=376, c2_committed_roots=376;
static struct {uint16_t generation,entry_first;uint8_t image_count;} c2_runtime;
typedef struct {uint8_t first,count;uint16_t generation;} c2r_ctx;
typedef struct {uint8_t next,mode,recovery,owned,auth;} c2r_dispatch;
static c2r_ctx scratch;
#define RX (&scratch)
static int scenario,busy,active,owner,journal,begin_count,end_count,replays,victims,fired,fatal;
static char events[256];static unsigned used;
static jmp_buf fatal_target;
static void event(char c){assert(used+1<sizeof(events));events[used++]=c;events[used]=0;}
static uint8_t vm_runtime_overlay_transaction_begin(uint8_t family,uint16_t generation){
 event('B');begin_count++;assert(!busy && !active);assert(family==2 && generation==1);
 if(scenario==3)return 3;
 active=1;return 0;
}
static uint8_t vm_runtime_overlay_transaction_end(void){
 event('E');end_count++;assert(!busy && active);active=0;
 return scenario==6?3:0;
}
static uint8_t c2_phase_scratch_release(uint8_t expected){if(owner!=expected)return 0;owner=0;event('R');return 1;}
static uint8_t c2_phase_scratch_acquire(uint8_t expected){if(owner)return 0;owner=expected;event('A');return 1;}
static uint8_t vm_retire_prompt_quiescent(void){event('Q');return !gc_rootsp;}
static uint8_t c2_stream_c2d_read(uint16_t at,uint8_t *dest,uint8_t length){assert(at==C2D_UNWIND_BASE && length==64);memset(dest,0,length);return 1;}
static void gc_collect(void){event('G');assert(busy && active);}
__attribute__((noreturn)) void c2_kernal_fail_closed(void){event('F');fatal=1;longjmp(fatal_target,1);}
static uint8_t c2_overlay_call(uint8_t slot,void *opaque);
'''
MOCK=r'''
static uint8_t c2_overlay_call(uint8_t slot,void *opaque){
 c2r_dispatch *d=opaque;uint8_t status=0;
 assert(!busy);busy=1;event((char)('a'+slot-56));
 if(scenario==8 && slot==56 && d->mode==4){busy=0;return 0;}
 if(slot==56){status=c2_retire_control(d);}
 else if(slot==57){
  if((scenario==4 || scenario==7) && !fired){fired=1;busy=0;return 0;}
  d->next=58;
 }else if(slot==58){d->next=59;}
 else if(slot==59){
  if(d->recovery){replays++;event('P');if(scenario==7){busy=0;return 0;}}
  if(scenario==5 && !fired && !d->recovery){journal=1;fired=1;busy=0;return 0;}
  if(journal){d->next=60;}
  else if(scenario==2 && !victims && !d->recovery){journal=1;d->next=60;}
  else {d->mode=d->recovery?4:3;d->next=d->recovery?0:56;}
 }else if(slot==60){assert(journal);d->next=61;}
 else if(slot==61){assert(journal);journal=0;victims++;c2_runtime.image_count--;d->mode=d->recovery?4:2;d->next=d->recovery?0:56;}
 else assert(0);
 busy=0;return status==0;
}
int main(void){
 const char *names[]={"disarmed","normal-empty","normal-victim-repeat","begin-refusal","tenant-refusal-before-journal","tenant-refusal-after-journal","end-refusal","replay-failure-fatal","cleanup-fetch-failure","quiescence-refusal","explicit-abort-replay"};
 for(scenario=0;scenario<11;scenario++){
  busy=active=owner=journal=begin_count=end_count=replays=victims=fired=fatal=0;used=0;events[0]=0;
  c2r_boot_count=scenario?134:0;gc_rootsp=scenario==9;gc_rootsp=!!gc_rootsp;
  c2_runtime.generation=1;c2_runtime.entry_first=4096;c2_runtime.image_count=8;
  if(scenario==8 || scenario==10)journal=1;
  if(!setjmp(fatal_target))assert(c2_retire_run((scenario==8 || scenario==10)?1:0)==1);
  assert(!busy);
  if(scenario==7){assert(fatal && replays==1 && c2r_boot_count==134);}
  else {
   assert(!fatal && !active && !journal);
   if(scenario!=8)assert(!owner);
   if(scenario==1 || scenario==2)assert(c2r_boot_count==134 && begin_count==1 && end_count==1 && !replays);
   else assert(c2r_boot_count==0);
   if(scenario>=3 && scenario<=6)assert(replays==1);
   if(scenario==5)assert(victims==1 && end_count==1);
   if(scenario==6){assert(end_count==1);assert(strstr(events,"EaR") && strstr(events,"EaR")<strchr(events,'P'));}
   if(scenario==8 || scenario==10)assert(begin_count==0 && end_count==0 && victims==1 && replays==1);
   if(scenario==9)assert(!strchr(events,'G') && replays==1 && end_count==1);
  }
  printf("%s PASS events=%s begin=%d end=%d replay=%d fatal=%d arm=%u owner=%d\n",names[scenario],events,begin_count,end_count,replays,fatal,c2r_boot_count,owner);
 }
 return 0;
}
'''


def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    runtime=(PROP/'candidate/src/c2_product_runtime.c').read_text()
    start=runtime.index('/* Transaction ownership belongs to the resident caller')
    code=runtime[start:];assert code.endswith('\n#endif\n');code=code[:-len('\n#endif\n')]
    control=PROP/'candidate/src/optional/set_b_retire_control.c'
    harness=OUT/'ownership.c';harness.write_text(PREFIX+control.read_text()+code+MOCK)
    compiler=Path(shutil.which('cc'));binary=OUT/'ownership'
    commands=[[str(compiler),'-std=c11','-Wall','-Wextra','-Werror','-O0',str(harness),'-o',str(binary)],[str(binary)]]
    rows=[]
    for i,c in enumerate(commands):
        run=subprocess.run(c,cwd=ROOT,capture_output=True,text=True);log=OUT/f'command-{i}.txt';log.write_text(run.stdout+run.stderr)
        rows.append(dict(command=c,exit=run.returncode,log=P.bind(log)))
        P.write(OUT/'commands.json',rows)
        assert run.returncode==0,run.stdout+run.stderr
    trace=P.load(ROOT/'build/set-b-transaction-trace-r1/receipt.json');r=trace['result']
    assert trace['status']=='PASS: EXECUTED FOURTH SEED BOUNDARY ATTRIBUTION'
    assert (r['destination_before'],r['destination_after'],r['reader_return'],r['reset_status'])==(255,0,1,0)
    assert (r['first_mode'],r['busy_read'],r['begin_status'],r['control_status'])==(0,1,3,8)
    assert r['ready_at_prompt']==1 and r['arm_at_prompt']==0 and r['tenants_intact']
    walk=P.load(ROOT/'build/set-b-transaction-trace-r1/control-walk.json')['rows']
    begin=next(x for x in walk if x['pc']==0xc4a8)
    assert begin['roots']==0 and begin['busy']==1 and begin['dispatch']=='3800000100'
    P.write(OUT/'receipt.json',dict(status='PASS: EXECUTED ATTRIBUTION AND 11 HOST C OWNERSHIP ROWS',
        driver=P.bind(Path(__file__)),harness=P.bind(harness),candidate=[P.bind(PROP/'candidate/src/c2_product_runtime.c'),P.bind(control)],
        trace=P.bind(ROOT/'build/set-b-transaction-trace-r1/receipt.json'),commands=P.bind(OUT/'commands.json'),
        host_c_rows=11,host_test_compiles=1,host_test_links=1,product_links=0,seeds=0,device_contacts=0,
        limit='Actual proposed resident/control C; mocked transaction, overlay, GC, journal and fatal sink. No repaired native/emulator execution claimed.'))
    print('PASS 11 host C ownership/fault rows and executed trace assertions')


if __name__=='__main__':main()
