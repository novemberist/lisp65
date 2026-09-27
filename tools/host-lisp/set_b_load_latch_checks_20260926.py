"""Actual parked reset/control C: post-INIT capture and refusal host rows."""
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-latch-checks-r1'
PROP=ROOT/'build/set-b-load-repair-proposal-r5/candidate/src/optional'
PREFIX=r'''
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#define C2_APPEND_SECTION(x)
#define C2_STREAM_OK 0
#define C2_STREAM_ERR_STATE 8
#define C2_STREAM_ERR_C2D 3
#define LISP65_C2_PHASE_OWNER_APPEND 2
#define LISP65_C2_PHASE_OWNER_EMITTER 1
#define C2D_HANDLE_CAP 4096
#define C2D_UNWIND_BASE 50752
#define RJ 56864
static uint8_t c2r_boot_count,c2_ready,gc_rootsp,c2_journal_count,c2r_gc_failed;
static uint16_t c2_pending_roots,c2_committed_roots;
static struct {uint16_t image_count,generation,entry_first;} c2_runtime;
typedef struct {uint8_t first,count;uint16_t generation;} c2r_ctx;
typedef struct {uint8_t next,mode,recovery,owned,auth;} c2r_dispatch;
static c2r_ctx scratch;
#define RX (&scratch)
static int owner,quiescent,read_ok,journal_byte,unwind_byte,gcs,fail_magic;
static void c2_facade_c2_dma(uint16_t a,uint8_t b,uint16_t c,uint8_t d,uint16_t e){
 (void)a;assert(b==0 && c==RJ && d==5 && e==1);journal_byte=fail_magic?166:0;
}
static uint8_t c2_map_cpu_read(uint32_t a,uint8_t *b,uint16_t c){assert(a==0x50000UL+RJ && c==1);*b=journal_byte;return read_ok;}
static uint8_t c2_phase_scratch_release(uint8_t x){if(owner!=x)return 0;owner=0;return 1;}
static uint8_t c2_phase_scratch_acquire(uint8_t x){if(owner)return 0;owner=x;return 1;}
static uint8_t vm_retire_prompt_quiescent(void){return quiescent;}
static uint8_t c2_stream_c2d_read(uint16_t a,uint8_t *b,uint8_t c){assert(a==C2D_UNWIND_BASE && c==64);memset(b,0,c);b[0]=unwind_byte;return read_ok;}
static void gc_collect(void){gcs++;assert((c2r_boot_count&127)>=6);}
'''
BODY=r'''
static void fresh(void){
 c2r_boot_count=c2_ready=gc_rootsp=c2_journal_count=c2r_gc_failed=0;
 owner=journal_byte=unwind_byte=gcs=fail_magic=0;quiescent=read_ok=1;
 c2_pending_roots=c2_committed_roots=376;
 c2_runtime.image_count=6;c2_runtime.generation=1;c2_runtime.entry_first=4096;
}
int main(void){
 const char *names[]={"post-init-eight","no-init-six","already-captured-stays-eight","max-prefix64","under-six-refused","over64-refused","quiescence-refused","unwind-refused","recovery-does-not-capture","reset-read-failure","reset-magic-failure","ready-reset-refused"};
 for(int i=0;i<12;i++){
  fresh();c2r_dispatch d={56,0,0,0,1};
  if(i>=9){
   if(i==9)read_ok=0;if(i==10)fail_magic=1;if(i==11)c2_ready=1;
   assert(c2_retire_reset(&c2_runtime)==(i==11?8:3));
   assert(c2r_boot_count==0 && c2_ready==(i==11));
  }else{
   assert(c2_retire_reset(&c2_runtime)==0 && c2r_boot_count==128 && !c2_ready);
   c2_ready=1;c2_runtime.image_count=i==1?6:i==3?64:i==4?5:i==5?65:8;
   if(i==6)quiescent=0;if(i==7)unwind_byte=1;if(i==8){d.mode=1;d.recovery=1;}
   int status=c2_retire_control(&d);
   if(i>=4 && i<=7)assert(status==8 && c2r_boot_count==128 && !gcs);
   else if(i==8){assert(status==0 && d.next==59 && c2r_boot_count==128 && !gcs);d.mode=4;assert(c2_retire_control(&d)==0 && !c2r_boot_count);}
   else{
    assert(status==0 && scratch.first==c2_runtime.image_count && gcs==1);
    if(i==2){d.mode=3;assert(c2_retire_control(&d)==0);d.mode=0;c2_runtime.image_count=9;assert(c2_retire_control(&d)==0 && scratch.first==8);}
   }
   assert(c2_ready==1);
  }
  printf("%s PASS latch=%u ready=%u gc=%d\n",names[i],c2r_boot_count,c2_ready,gcs);
 }
 return 0;
}
'''

def main():
    OUT.mkdir(exist_ok=False)
    inputs=[PROP/'set_b_retire_reset.c',PROP/'set_b_retire_control.c']
    source=OUT/'latch.c';source.write_text(PREFIX+''.join(p.read_text() for p in inputs)+BODY)
    binary=OUT/'latch';rows=[]
    commands=[[shutil.which('cc'),'-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-O0',str(source),'-o',str(binary)],[str(binary)]]
    for i,c in enumerate(commands):
        r=subprocess.run(c,cwd=ROOT,capture_output=True,text=True);log=OUT/f'command-{i}.txt';log.write_text(r.stdout+r.stderr)
        rows.append(dict(command=c,exit=r.returncode,log=P.bind(log)));P.write(OUT/'commands.json',rows);assert r.returncode==0,r.stdout+r.stderr
    P.write(OUT/'receipt.json',dict(status='PASS: 12 PARKED C LATCH/REFUSAL ROWS',driver=P.bind(Path(__file__)),candidate=[P.bind(p) for p in inputs],harness=P.bind(source),commands=P.bind(OUT/'commands.json'),host_test_compiles=1,host_test_links=1,product_builds=0,product_links=0,seeds=0,device_contacts=0,limits='Host C with transport/GC/scratch stubs. Resident replay and cold timing remain future native gates.'))
    print('PASS 12 post-INIT latch/refusal rows')

if __name__=='__main__':main()
