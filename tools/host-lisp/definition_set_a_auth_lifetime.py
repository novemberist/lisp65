"""Execute product control/transaction/abort bodies with model transport.

This is a lifetime preflight, not a native timing or DMA proof.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from definition_group_capacity_probe import body

ROOT = Path(__file__).resolve().parents[2]


def bind(p):
    data=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    out=ap.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=False)
    emitter=(ROOT/'src/c2_session_emitter.c').read_text()
    runtime=(ROOT/'src/c2_product_runtime.c').read_text()
    overlay=(ROOT/'src/vm_runtime_overlay.c').read_text()
    start=overlay.index('#define RTOV_TRANSACTION_INACTIVE')
    macros=overlay[start:overlay.index('\n#else',start)]
    owner='\n'.join(body(overlay,s) for s in (
        'static void rtov_transaction_invalidate(void)',
        'vm_runtime_overlay_status vm_runtime_overlay_transaction_begin(',
        'vm_runtime_overlay_status vm_runtime_overlay_transaction_end(void)'))
    abort=body(overlay,'vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(void)')
    helper=body(runtime,'uint8_t c2_product_emitter_auth_begin(void)')
    control=body(emitter,'obj c2_session_emit_control(obj operation, obj payload)')
    prefix=r'''
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include "vm.h"
#include "c2_session_emitter.h"
#include "vm_runtime_overlay.h"
#define LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH 1
#define LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND 1
#define LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES 1
#define LISP65_C2_TRANSACTION_AUTH 1
#define RTOV_SESSION_INVALIDATE() ((void)0)
static uint8_t rtov_repeat,rtov_busy,rtov_fault,rtov_batch_slot_id;
static uint16_t rtov_batch_entry,rtov_batch_crc;
static uint8_t rtov_family=LISP65_RUNTIME_OVERLAY_FAMILY_SESSION;
static uint16_t rtov_family_generation=71;
static struct {uint16_t generation;} c2_runtime={71};
uint8_t vm_status;
static int fail_status,abort_at,catalogs,steps,wipe_ok=1;
static jmp_buf landing;
static uint8_t rtov_wipe(void){return wipe_ok;}
static obj car(obj x){return x==2?10:x==4?12:MKFIX(0);}
static obj cdr(obj x){return x==2?4:x==4?6:NIL;}
static uint8_t c2e_cons(obj x){return x==2||x==4||x==6;}
'''
    transport=r'''
obj intern(const char *s){(void)s;assert(!RTOV_TRANSACTION_ACTIVE());return 20;}
obj vm_buffer_from_stage(uint16_t n){assert(n==42);assert(!RTOV_TRANSACTION_ACTIVE());return 22;}
obj c2_product_publish_staged(uint16_t n){assert(n==42);assert(!RTOV_TRANSACTION_ACTIVE());return 20;}
c2_emit_status c2_session_emit_reset(void){assert(!RTOV_TRANSACTION_ACTIVE());return C2_EMIT_OK;}
static c2_emit_status work(void){
 for(int i=0;i<4;i++){
  if(++steps==abort_at){rtov_busy=1;longjmp(landing,1);}
  if(!RTOV_TRANSACTION_TRUSTED()){
   catalogs++;
   if(RTOV_TRANSACTION_ACTIVE())rtov_transaction_count=53;
  }
 }
 return fail_status?C2_EMIT_STATE:C2_EMIT_OK;
}
c2_emit_status c2_session_emit_add(obj x,obj n,uint8_t f){assert(x==10&&n==12&&f==0);return work();}
c2_emit_status c2_session_emit_finalize(uint16_t *n){*n=42;return work();}
'''
    tests=r'''
static void reset(void){rtov_transaction_invalidate();rtov_repeat=rtov_busy=rtov_fault=0;vm_status=VM_OK;fail_status=abort_at=catalogs=steps=0;wipe_ok=1;}
int main(void){
 for(int op=1;op<=3;op++){
  reset();assert(c2_session_emit_control(MKFIX(op),op==1?2:NIL)==(op==2?22:20));
  assert(catalogs==1);assert(!RTOV_TRANSACTION_ACTIVE());assert(vm_status==VM_OK);
  reset();fail_status=1;assert(c2_session_emit_control(MKFIX(op),op==1?2:NIL)==NIL);
  assert(!RTOV_TRANSACTION_ACTIVE());assert(vm_status==VM_BADOPCODE);
  for(int point=1;point<=4;point++){
   reset();abort_at=point;
   if(!setjmp(landing)){c2_session_emit_control(MKFIX(op),op==1?2:NIL);assert(0);}
   assert(RTOV_TRANSACTION_ACTIVE());
   assert(vm_runtime_overlay_abort_cleanup()==VM_RUNTIME_OVERLAY_ERR_ABORTED);
   assert(!RTOV_TRANSACTION_ACTIVE());assert(!rtov_busy);
   abort_at=steps=catalogs=0;
   assert(c2_session_emit_control(MKFIX(op),op==1?2:NIL)==(op==2?22:20));
   assert(catalogs==1);assert(!RTOV_TRANSACTION_ACTIVE());
  }
 }
 reset();assert(c2_session_emit_control(MKFIX(0),NIL)==20);assert(!catalogs);
 reset();assert(c2_session_emit_control(MKFIX(4),NIL)==NIL);assert(vm_status==VM_TYPEERROR&&!RTOV_TRANSACTION_ACTIVE());
 reset();assert(c2_session_emit_control(MKFIX(1),NIL)==NIL);assert(vm_status==VM_TYPEERROR&&!RTOV_TRANSACTION_ACTIVE());
 reset();rtov_family_generation=72;assert(c2_session_emit_control(MKFIX(1),2)==NIL);assert(!RTOV_TRANSACTION_ACTIVE());rtov_family_generation=71;
 reset();abort_at=1;if(!setjmp(landing)){c2_session_emit_control(MKFIX(1),2);assert(0);}
 wipe_ok=0;assert(vm_runtime_overlay_abort_cleanup()==VM_RUNTIME_OVERLAY_ERR_WIPE);assert(!RTOV_TRANSACTION_ACTIVE());
 puts("PASS: bounded return, status-error, abort/reentry, generation and wipe failure");
}
'''
    old=body(subprocess.check_output(['git','show','20e4aa49:src/c2_session_emitter.c'],cwd=ROOT,text=True),
             'obj c2_session_emit_control(obj operation, obj payload)')
    end=body(overlay,'vm_runtime_overlay_status vm_runtime_overlay_transaction_end(void)')
    mutants={
        'candidate':(owner,abort,control),
        'open-return':(owner.replace(end,end.replace('    rtov_transaction_invalidate();','    /* mutation: left open */')),abort,control),
        'open-abort':(owner,abort.replace('    rtov_transaction_invalidate();','    /* mutation: left open */'),control),
        'old-repeated-verification':(owner,abort,old),
    }
    rows=[]
    for name,(o,a,c) in mutants.items():
        source=out/(name+'.c');source.write_text(prefix+macros+'\n'+o+'\n'+a+'\n'+helper+'\n'+transport+'\n'+c+'\n'+tests)
        binary=out/name
        cmd=['cc','-std=c11','-O0','-g','-Isrc',str(source),'-o',str(binary)]
        compiled=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        (out/(name+'.compile.log')).write_text(compiled.stdout+compiled.stderr);compiled.check_returncode()
        run=subprocess.run([str(binary)],cwd=ROOT,capture_output=True,text=True)
        (out/(name+'.run.log')).write_text(run.stdout+run.stderr)
        assert (run.returncode==0)==(name=='candidate'),(name,run.returncode,run.stderr)
        rows.append(dict(name=name,exit=run.returncode,source=bind(source),binary=bind(binary)))
    result=dict(status='PASS: EXTRACTED PRODUCT LIFETIME WITH MODEL TRANSPORT',rows=rows,
                mutations=3,native_seed=0,limits=['Transport costs and native non-local landing still require the replacement Seed.'],
                inputs=[bind(ROOT/p) for p in ('src/c2_product_runtime.c','src/c2_product_runtime.h','src/c2_session_emitter.c','src/vm_runtime_overlay.c','src/vm_runtime_overlay.h','src/obj.h','src/vm.h')]+[bind(Path(__file__))])
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],'mutations=3')


if __name__=='__main__':main()
