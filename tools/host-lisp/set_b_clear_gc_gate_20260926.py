"""Exact-C publication root-lifetime gate with coupled ordered journal/function writes."""
import argparse
import ctypes as C
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_source_capture_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=ROOT/'build/set-b-clear-gc-gate-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-clear-gc-gate-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-clear-gc-gate-report.md'
HEAD='0815dce5'
CANDIDATE=ROOT/'build/set-b-barrier-read-r1/candidate'
SOURCES=PREVIOUS.SOURCES+[ROOT/'src/symbol.c',ROOT/'src/mem.c']
AUTHORITIES=PREVIOUS.AUTHORITIES+[PREVIOUS.REPORT,ROOT/'docs/planning/set-b-clear-protocol-report.md',ROOT/'build/set-b-r1/step4-r6/command-preview/receipt.json']

PREFIX=r'''
#include <stdint.h>
#include <string.h>
#include "obj.h"
#include "c2-stream-decoder.h"
#define LISP65_SET_B 1
#define LISP65_SYMFN_EXT 1
#define LISP65_CODE_WINDOW_CONVERGENCE 1
#define LISP65_C2_MUTABLE_CPU_READS 1
#define LISP65_C2_MAPPED_FACADE_FN
#define SYMFN_EXT_BANK 5u
#define SYMFN_EXT_OFF 54848u
#define SYMVAL_EXT_BANK 5u
#define LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT 61u
#define lisp_abort_static(code,text) (++bounds_errors)
#define C2_KERNAL_RESIDENT
#define LISP65_C2D_REGION_BYTES 50816u
#define LISP65_C2D_BASE 0u
#define LISP65_C2D_BANK 5u
#define C2_EXPORT_JOURNAL_BASE 33840u
#define C2_EXPORT_JOURNAL_RECORD_BYTES 4u
#define C2_EXPORT_PLAN_RECORD_BYTES 8u
#define C2_EXPORT_PUBLISH_MARK 0x51u
#define C2D_ENTRY_CAP 2048u
#define C2AW_PLAN_MARK(w) ((w)->record[22])
#define C2_C1_FREEZER_HOLD(n) ((void)(n))
#define C2_C1_FREEZER_ABORT_REQUESTED() 0
/* Exact accessed fields; no target sizeof/stack claim. */
typedef struct { uint8_t committed,record[32],meta[24];uint16_t *main_ordinal,new_entries; } c2_append_state;
static struct {uint16_t roots_offset;} c2_runtime;
static uint16_t c2_journal_count,c2_committed_roots,c2_pending_roots;
static uint8_t c2r_gc_failed,mem_oom;
Cell heap[HEAP_CELLS];
obj symfn_ext_get(uint16_t);
void symfn_ext_set(uint16_t,obj);
static uint8_t symfnptr[1];
static const uint8_t bndbit[8]={1,2,4,8,16,32,64,128};
static uint16_t sidx(obj s){return SYMI_IDX(s);}
static obj symfn_get(uint16_t i){return symfn_ext_get(i);}
static void symfn_set(uint16_t i,obj o){symfn_ext_set(i,o);}
static uint16_t c2_u16(const uint8_t *p){return (uint16_t)(p[0]|(uint16_t)p[1]<<8);}
static uint8_t bank5[65536],marked[HEAP_CELLS];
static uint16_t count,allocations,bounds_errors,submits,mark_count,delivery_mode,job_head;
static uint16_t mark_trace[16],read_trace[8][4],read_count;
/* Captured payload only: no pointer survives the facade call. */
typedef struct {uint16_t at,n;uint8_t bytes[4];} job;
static job jobs[16];
static void drain(void){
 while(job_head<submits){job *p=&jobs[job_head++];memcpy(bank5+p->at,p->bytes,p->n);}
}
static uint8_t c2_map_cpu_read(uint32_t at,uint8_t *dst,uint16_t n){
 if((at>>16)!=5u || (at&65535u)+n>65536u){++bounds_errors;return 0;}
 memcpy(dst,bank5+(at&65535u),n);return 1;
}
uint16_t gc_rows[8][12],root_marks[8][16],root_reads[8][8][4],gc_count;
uint8_t pending_journal[32],physical_journal[32],plan_before[64];
uint16_t result[10];
static void c2_facade_gc_mark(obj o){
 if(mark_count<16)mark_trace[mark_count++]=(uint16_t)o;
 if(IS_PTR(o) && ((uint16_t)o>>1)<HEAP_CELLS)marked[(uint16_t)o>>1]=1;
}
uint8_t c2_stream_c2d_read(uint16_t at,void *dst,uint16_t n){
 if((uint32_t)at+n>65536u){++bounds_errors;return 0;}
 memcpy(dst,bank5+at,n);
 if(n==32 && read_count<8){
  read_trace[read_count][0]=at;read_trace[read_count][1]=n;
  read_trace[read_count][2]=c2_u16(bank5+at);read_trace[read_count][3]=c2_u16(bank5+at+2);++read_count;
 }
 return 1;
}
static void submit(uint16_t low,uint8_t sb,uint16_t target,uint8_t tb,uint16_t n,const void *full){
 if(sb || tb!=5 || (n!=4 && n!=2) || low!=(uint16_t)(uintptr_t)full || submits>=16 || (uint32_t)target+n>65536u){++bounds_errors;return;}
 job *p=&jobs[submits++];p->at=target;p->n=n;memcpy(p->bytes,full,n);
 if(delivery_mode==0)drain();
}
#define c2_facade_c2_dma(s,sb,t,tb,n) submit((s),(sb),(t),(tb),(n),src)
void c2_product_gc_mark_roots(void);
void set_sym_function(obj,obj);
obj sym_function(obj);
uint8_t sym_function_ptrp(obj);
static obj alloc(uint8_t type){
 ++allocations;memset(marked,0,sizeof marked);mark_count=read_count=0;
 memset(mark_trace,0,sizeof mark_trace);memset(read_trace,0,sizeof read_trace);
 /* Observe the necessary root closure at the actual allocation seam.
    No collector, sweep, or fabricated reclamation is executed. */
 c2_product_gc_mark_roots();
 /* All prior jobs drain strictly FIFO between the collector's two root
    populations. No function-cell write overtakes its undo write. */
 if(delivery_mode==2 && allocations==count)drain();
 for(uint16_t i=0;i<count;++i)if(sym_function_ptrp(MK_SYMI(i)))
   c2_facade_gc_mark(sym_function(MK_SYMI(i)));
 /* Complete reachability for this fixture: old/new macros contain only
    immediate BCODE and NIL, hence no transitive edges to an old macro. */
 uint16_t missing=0,first=0,mask=0;
 for(uint16_t i=0;i<count;++i)if(!marked[i+1]){++missing;if(!first)first=(uint16_t)(2*(i+1));}
 for(uint16_t i=0;i<count;++i)if(marked[i+1])mask|=(uint16_t)(1u<<i);
 uint16_t *r=gc_rows[gc_count];r[0]=allocations;r[1]=c2_journal_count;
 r[2]=missing;r[3]=first;r[4]=mask;r[5]=c2r_gc_failed;r[6]=submits;
 r[7]=read_count;r[8]=mark_count;r[9]=symfnptr[0];
 if(first){uint16_t i=(uint16_t)(first/2-1);r[10]=(uint16_t)symfn_get(i);r[11]=(uint16_t)(C2_EXPORT_JOURNAL_BASE+4*i+2);}
 memcpy(root_marks[gc_count],mark_trace,sizeof mark_trace);
 memcpy(root_reads[gc_count],read_trace,sizeof read_trace);++gc_count;
 obj fresh=(obj)(64+2*(allocations-1));CELL(fresh).type=type;return fresh;
}
'''

SUFFIX=r'''
void probe(uint16_t mode,uint16_t n){
 memset(bank5,0,sizeof bank5);memset(heap,0,sizeof heap);
 memset(jobs,0,sizeof jobs);memset(gc_rows,0,sizeof gc_rows);memset(root_marks,0,sizeof root_marks);
 memset(root_reads,0,sizeof root_reads);memset(result,0,sizeof result);memset(symfnptr,0,sizeof symfnptr);
 memset(pending_journal,0,sizeof pending_journal);memset(physical_journal,0,sizeof physical_journal);
 count=n;delivery_mode=0;allocations=bounds_errors=submits=gc_count=c2_journal_count=job_head=0;
 c2_committed_roots=c2_pending_roots=c2r_gc_failed=mem_oom=0;
 c2_runtime.roots_offset=26000u;
 c2_append_state w;memset(&w,0,sizeof w);w.committed=1;w.new_entries=(uint16_t)(20+n);
 w.meta[22]=(uint8_t)n;w.meta[23]=(uint8_t)(n>>8);
 for(uint16_t i=0;i<n;++i){
  obj old=(obj)(2*(i+1));CELL(old).type=T_MACRO;cell_set_a(old,MK_BCODE(100+i));cell_set_b(old,NIL);
  set_sym_function(MK_SYMI(i),old);
  uint8_t *r=bank5+C2_EXPORT_JOURNAL_BASE+8*i;
  uint16_t sym=(uint16_t)MK_SYMI(i),tagged=(uint16_t)(0x8000u+20+i);
  r[0]=(uint8_t)sym;r[1]=(uint8_t)(sym>>8);r[2]=(uint8_t)old;r[3]=(uint8_t)((uint16_t)old>>8);
  r[4]=(uint8_t)tagged;r[5]=(uint8_t)(tagged>>8);
 }
 submits=job_head=0;memset(jobs,0,sizeof jobs);delivery_mode=mode;
 memcpy(plan_before,bank5+C2_EXPORT_JOURNAL_BASE,64);
 uint8_t status=c2_append_publish_exports_phase(&w);
 memcpy(physical_journal,bank5+C2_EXPORT_JOURNAL_BASE,32);
 for(uint16_t i=0;i<submits;++i)if(jobs[i].n==4){
   uint16_t at=(uint16_t)(jobs[i].at-C2_EXPORT_JOURNAL_BASE);
   if(at<32)memcpy(pending_journal+at,jobs[i].bytes,4);
 }
 result[0]=status;result[1]=allocations;result[2]=bounds_errors;result[3]=submits;
 result[4]=c2_journal_count;result[5]=c2r_gc_failed;result[6]=mem_oom;
 result[7]=gc_count;result[8]=symfnptr[0];result[9]=w.record[22];
 /* Immutable queued sources remain diagnostic data. No late writes, GC
    sweeping or controller execution are performed after the failed gate. */
}
'''


def extract(text,signature):
    start=text.index(signature);brace=text.index('{',start);level=0
    for i in range(brace,len(text)):
        if text[i]=='{':level+=1
        if text[i]=='}':
            level-=1
            if not level:return text[start:i+1]+'\n'
    raise AssertionError(signature)


def prepare():
    PREVIOUS.check();authority=S.require_auth();OUT.mkdir(exist_ok=False)
    assert subprocess.check_output(['git','rev-parse','--short=8','HEAD'],cwd=ROOT,text=True).strip()==HEAD
    old=P.load(PREVIOUS.OUT/'receipt.json')
    for row in old['compiler_inputs']+old['candidate']:assert P.bind(ROOT/row['path'])==row
    runtime=(CANDIDATE/'src/c2_product_runtime.c').read_text();symbol=(ROOT/'src/symbol.c').read_text()
    dma=(ROOT/'src/c2_platform_dma.c').read_text()
    specs=[('writer',runtime,'C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write('),
        ('gc-roots',runtime,'C2_KERNAL_RESIDENT void c2_product_gc_mark_roots('),
        ('function-setter',symbol,'void set_sym_function('),
        ('function-getter',symbol,'obj  sym_function('),
        ('function-ptrp',symbol,'uint8_t sym_function_ptrp('),
        ('publisher',runtime,'uint8_t c2_append_publish_exports_phase('),
        ('mutable-reader',dma,'void c2_dma_read_or_abort('),
        ('physical-function-getter',dma,'obj symfn_ext_get('),
        ('physical-function-setter',dma,'void symfn_ext_set(')]
    bodies=[]
    for name,text,signature in specs:
        body=extract(text,signature);(OUT/(name+'.c')).write_text(body)
        if name=='physical-function-setter':
            bodies.append('#undef c2_facade_c2_dma\n#define c2_facade_c2_dma(s,sb,t,tb,n) submit((s),(sb),(t),(tb),(n),&word)\n')
        bodies.append(body)
    fixture=OUT/'fixture.c';fixture.write_text(PREFIX+'\n'.join(bodies)+SUFFIX)
    shutil.copyfile(ROOT/'config/set-b-native/includes/c2-stream-decoder.h',OUT/'c2-stream-decoder.h')
    P.write(OUT/'binding.json',dict(execution_head=HEAD,source_authority=authority,driver=P.bind(Path(__file__)),
        predecessor=P.bind(PREVIOUS.SEAL),compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],
        candidate=old['candidate'],functions=[P.bind(OUT/(n+'.c')) for n,_,_ in specs],fixture=P.bind(fixture),
        source=[P.bind(CANDIDATE/'src/c2_product_runtime.c'),P.bind(ROOT/'src/symbol.c'),P.bind(ROOT/'src/mem.c')],
        budget=dict(source_forms=1,host_compile_attempts=2,host_links=2,host_dependencies=1,
            native_object_calls=16,native_dependencies=8,assembler_calls=2,product_builds=0,product_links=0,seeds=0,finals=0,guest=0,device=0),
        seam='Exact publisher, region writer, C2 root walker, function setter/getter/ptr bitmap; read and mark transport seams; allocation hook observes root closure without sweeping. All queued write sources are captured. Context layout is host-only.',
        schedule='Immediate controls N1..4 then captured-source/delayed-destination N1..4, root observation at each macro allocation; stop first failing row. No counterexample schedule inferred as physical timing.'))
    P.write(OUT/'gate-order.json',dict(first='Macro before-image root closure at real publisher allocation sites, before authoring terminal controller.',
        next=['Exact C four-mode terminal implementation and full rollback/GC rejection/caller-finalizer/empty-C2J/nested-transient rows.',
              'Matched native prices only after all lifetime and semantic rows pass.'],
        unchanged='Source-capture premise from0815dce5. No deferred source fetch, expired pointer, sweep or device execution.',
        stop='First failed root/lifetime/semantic/capacity gate; no speculative alternative source form.'))
    print('PREPARED nine exact C bodies; shared-FIFO macro root closure before terminal controller')


def correct():
    assert (OUT/'attempt-1/executed-driver.py').exists()
    prior=P.load(OUT/'attempt-1/binding.json')
    runtime=(CANDIDATE/'src/c2_product_runtime.c').read_text();symbol=(ROOT/'src/symbol.c').read_text()
    dma=(ROOT/'src/c2_platform_dma.c').read_text()
    specs=[('writer',runtime,'C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write('),
        ('gc-roots',runtime,'C2_KERNAL_RESIDENT void c2_product_gc_mark_roots('),
        ('function-setter',symbol,'void set_sym_function('),
        ('function-getter',symbol,'obj  sym_function('),
        ('function-ptrp',symbol,'uint8_t sym_function_ptrp('),
        ('publisher',runtime,'uint8_t c2_append_publish_exports_phase('),
        ('mutable-reader',dma,'void c2_dma_read_or_abort('),
        ('physical-function-getter',dma,'obj symfn_ext_get('),
        ('physical-function-setter',dma,'void symfn_ext_set(')]
    bodies=[]
    for name,text,signature in specs:
        body=extract(text,signature);(OUT/(name+'.c')).write_text(body)
        if name=='physical-function-setter':
            bodies.append('#undef c2_facade_c2_dma\n#define c2_facade_c2_dma(s,sb,t,tb,n) submit((s),(sb),(t),(tb),(n),&word)\n')
        bodies.append(body)
    fixture=OUT/'fixture.c';fixture.write_text(PREFIX+'\n'.join(bodies)+SUFFIX)
    # Same includes and command as attempt1: reuse the dependency closure,
    # explicitly replacing only the source binding. No second dependency call.
    oldfixture=(OUT/'attempt-1/fixture.c').read_text()
    includes=lambda t:[x for x in t.splitlines() if x.startswith('#include')]
    assert includes(oldfixture)==includes(fixture.read_text())
    deps=P.load(OUT/'attempt-1/dependencies.json')
    internal=[]
    for row in deps['internal']:
        if row['path']==str(fixture.relative_to(ROOT)):internal.append(P.bind(fixture))
        else:assert P.bind(ROOT/row['path'])==row;internal.append(row)
    P.write(OUT/'dependencies.json',dict(status='REUSED: identical include directives and headers; fixture binding updated, no new dependency command',
        original=P.bind(OUT/'attempt-1/dependencies.json'),internal=internal,external=deps['external']))
    P.write(OUT/'correction.json',dict(disposition='Attempt1 diagnostic excluded: independent immediate function-store seam did not preserve same-engine ordering.',
        original_driver=P.bind(OUT/'attempt-1/executed-driver.py'),corrected_driver=P.bind(Path(__file__)),
        source_bodies='Nine exact unedited C functions. New bodies are actual physical function get/set and mutable CPU-read wrapper.',
        queue='Capture every source, one FIFO for 4-byte undo and 2-byte function writes; no overtaking.',
        schedules=['0 immediate drain per submission','1 no queue progress during any root observation','2 at final allocation: drain queued prefix between C2-root walk and symbol-function scan'],
        dependency_reuse='Only source body/defines/seams change; include directives and all header bytes identical.',
        device_claim=False))
    prior.update(driver=P.bind(Path(__file__)),fixture=P.bind(fixture),functions=[P.bind(OUT/(n+'.c')) for n,_,_ in specs],
        seam='Exact journal writer/publisher/root walker/function bitmap plus physical function writer/getter and CPU-read wrapper. One FIFO owns both write classes; mark/allocation hook is not a collector or sweep.',
        schedule='Immediate N1..4; stalled FIFO N1..4; FIFO drains at last allocation between root populations N1..4; stop first red.')
    P.write(OUT/'binding.json',prior)
    for name in ('receipt.json','rows.json','halt.json'):
        (OUT/name).unlink()
    print('CORRECTED shared FIFO; first diagnostic excluded; no new product source or dependency call')


def host():
    S.require_auth();binding=P.load(OUT/'binding.json')
    for r in binding['functions']+[binding['fixture']]:assert P.bind(ROOT/r['path'])==r
    attempts=list(OUT.glob('compile-attempt-*.json'));attempt=len(attempts)+1
    assert attempt<=2
    command=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(OUT/'fixture.c'),'-o',str(OUT/'fixture.so')]
    record=OUT/f'compile-attempt-{attempt}.json'
    P.write(record,dict(command=command,status='charged before execution'))
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    log=OUT/f'compile-attempt-{attempt}.log';log.write_text(r.stdout+r.stderr)
    P.write(record,dict(command=command,exit=r.returncode,log=P.bind(log),compiler=external_binding(Path(shutil.which('cc')).resolve())))
    assert r.returncode==0,r.stderr
    if not (OUT/'dependencies.json').exists():
        dep=command[:];at=dep.index('-o');del dep[at:at+2];dep+=['-M','-MT','fixture']
        P.write(OUT/'dependencies.json',dict(command=dep,status='charged before execution'))
        r=subprocess.run(dep,cwd=ROOT,capture_output=True,text=True)
        (OUT/'dependencies.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
        internal,external=[],[]
        for name in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
            p=(ROOT/name).resolve()
            (internal if p.is_relative_to(ROOT) else external).append(P.bind(p) if p.is_relative_to(ROOT) else external_binding(p))
        P.write(OUT/'dependencies.json',dict(command=dep,exit=r.returncode,internal=internal,external=external,log=P.bind(OUT/'dependencies.log')))
    lib=C.CDLL(str(OUT/'fixture.so'));lib.probe.argtypes=[C.c_uint16,C.c_uint16]
    rows=[];keys=['allocation','journal_K','missing_before_images','first_missing_object','old_mark_mask','root_read_error',
                  'write_submissions','root_reads','mark_calls','function_ptr_bitmap','missing_object_current_function','missing_object_undo_word_at']
    for mode,n in [(mode,n) for mode in range(3) for n in range(1,5)]:
        lib.probe(mode,n)
        result=list((C.c_uint16*10).in_dll(lib,'result'))
        raw=(C.c_uint16*12*8).in_dll(lib,'gc_rows');marks=(C.c_uint16*16*8).in_dll(lib,'root_marks')
        reads=(C.c_uint16*4*8*8).in_dll(lib,'root_reads')
        observations=[dict(zip(keys,list(raw[i])),marks=list(marks[i])[:raw[i][8]],reads=[list(x) for x in reads[i][:raw[i][7]]]) for i in range(result[7])]
        row=dict(mode=mode,exports=n,result=result,observations=observations,
            expected_captured_undo=list((C.c_uint8*32).in_dll(lib,'pending_journal'))[:4*n],
            physical_bytes=list((C.c_uint8*32).in_dll(lib,'physical_journal'))[:4*n],
            plan_before=list((C.c_uint8*64).in_dll(lib,'plan_before'))[:8*n],
            pass_gate=result[0]==0 and result[2]==0 and result[5]==0 and all(x['missing_before_images']==0 for x in observations))
        rows.append(row);P.write(OUT/'rows.json',rows)
        if not row['pass_gate']:
            P.write(OUT/'halt.json',row);break
    failed=[r for r in rows if not r['pass_gate']]
    old=P.load(PREVIOUS.OUT/'receipt.json')
    P.write(OUT/'receipt.json',dict(status='HALT: publication before-image root not retained' if failed else 'PASS initial macro root gate; implementation still required',
        execution_head=HEAD,source_authority=binding['source_authority'],driver=P.bind(Path(__file__)),predecessor=P.bind(PREVIOUS.SEAL),
        compiler_authority=binding['compiler_authority'],compiler_inputs=binding['compiler_inputs'],candidate=binding['candidate'],verified_compiler_roots=74,
        artifacts=[P.bind(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p!=OUT/'receipt.json'],
        this_commission=dict(compiler_calls=attempt,host_link_attempts=attempt,host_links=attempt,dependency_calls=1,native_object_calls=0,native_dependencies=0,assembler_calls=0,
            qualified_c_rows=len(rows),qualified_root_observations=sum(len(r['observations']) for r in rows),product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,new_source_forms=0),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        remaining_host_attempts=2-attempt,
        limit='Root-closure differential at exact C allocation seam, not full collector/sweep, native layout, complete append, device reproduction or new observed hardware corruption. No deferred source fetch.',
        next_recommendation='Include publication root protection before the first replacement, not only at CLEAR PREPARE. Price a durable CPU-written undo plane/root path or preallocated rooted macro wrappers with a non-allocating critical publisher; preserve complete rollback and no-GC pending interval. No new product attempt.'))
    print(P.load(OUT/'receipt.json')['status'],len(rows),'rows')


def close():
    receipt=P.load(OUT/'receipt.json')
    rows=P.load(OUT/'rows.json');excluded=P.load(OUT/'attempt-1/rows.json')
    assert len(rows)==12 and sum(bool(r['pass_gate']) for r in rows)==11
    final=rows[-1]['observations'][-1]
    assert final['first_missing_object']==6 and final['missing_object_current_function']==68
    assert final['old_mark_mask']==11 and final['write_submissions']==7
    assert rows[-1]['physical_bytes']==rows[-1]['expected_captured_undo']
    flags=(ROOT/'build/set-b-r1/step4-r6/command-preview/receipt.json').read_text()
    for flag in ('-DSYMFN_EXT_BANK=5','-DSYMFN_EXT_OFF=54848','-DLISP65_C2_MUTABLE_CPU_READS'):
        assert '"'+flag+'"' in flags
    budget=receipt['this_commission']
    budget.update(excluded_c_rows=len(excluded),host_c_rows=len(rows)+len(excluded),
        excluded_root_observations=sum(len(r['observations']) for r in excluded),
        root_observations=sum(len(r['observations']) for r in rows+excluded))
    receipt['driver']=P.bind(Path(__file__))
    receipt['artifacts']=[P.bind(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p!=OUT/'receipt.json']
    receipt['next_recommendation']='Extend the single full-rollback repair with synchronous CPU stores for compacted undo and canonical function-cell publication, sharing the primitive required by final scrub. Qualify both old and newly allocated macro roots and all existing CLEAR gates. No product build/link/Seed/device; current host attempts2/2 exhausted.'
    P.write(OUT/'receipt.json',receipt)
    print('CLOSED:12 qualified rows/30 root observations;8 excluded diagnostic rows/20 observations;2 host attempts,1 dependency')


def seal():
    PREVIOUS.check();S.require_auth()
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    receipt=P.load(OUT/'receipt.json')
    selected={p for p in OUT.rglob('*') if p.is_file()}
    selected.update(SOURCES+AUTHORITIES+[REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT])
    selected.update(local_import_closure([Path(__file__)]))
    external=[external_binding(Path(shutil.which(n)).resolve()) for n in ('python3','rg','git')]
    def bindings(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                row={k:value[k] for k in ('path','bytes','sha256')};path=ROOT/row['path']
                if path.is_relative_to(ROOT):assert P.bind(path)==row,row['path'];selected.add(path)
                else:assert external_binding(path)==row;external.append(row)
            else:
                for item in value.values():bindings(item)
        elif isinstance(value,list):
            for item in value:bindings(item)
    for path in OUT.glob('*.json'):bindings(P.load(path))
    scope=ARCH/STEM/'design-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue0815dce5: one isolated full-rollback source form, renewed host compile/link attempts2 and dependency1; native objects16/dependencies8/assembler2 only after host gates;0 product build/link/Seed/Final/guest/device. Mandatory producer/root lifetime and macro-GC gates precede the first controller qualification. Stop at first unresolved semantic/lifetime/capacity gate.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-source-capture-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        row=P.bind(path);inputs.append(row)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072 or (path.is_relative_to(OUT) and path.suffix=='.txt');dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=row,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status=receipt['status'],execution_head=HEAD,source_authority=receipt['source_authority'],
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(OUT/'receipt.json'),predecessor=P.bind(PREVIOUS.SEAL),
        inputs=inputs,receipt_copies=copies,external_tools=external,this_commission=receipt['this_commission'],
        consumed=receipt['consumed'],authorized_ceiling=receipt['authorized_ceiling'],accepted_world='Card L Final',public_release='2.4.0',product_admitted=False))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies')


def check():
    value=P.load(SEAL)
    for row in value['inputs']+[value['owner_scope']]:assert P.bind(ROOT/row['path'])==row,row['path']
    for row in value['external_tools']:assert external_binding(Path(row['path']))==row
    for row in value['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy'];raw=path.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes'] and hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    PREVIOUS.check();S.require_auth();print('PASS CLEAR GC gate seal:74 roots, exact C bodies, captured-source queue, root observations and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','correct','host','close','seal','check'))
    {'prepare':prepare,'correct':correct,'host':host,'close':close,'seal':seal,'check':check}[parser.parse_args().mode]()
