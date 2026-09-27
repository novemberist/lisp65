"""Exact-C producer lifetime gate before authoring the CLEAR implementation."""
import argparse
import ctypes as C
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_clear_protocol_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=ROOT/'build/set-b-clear-c-preflight-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-clear-c-preflight-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-clear-c-preflight-report.md'
HEAD='b95ba185'
CANDIDATE=ROOT/'build/set-b-barrier-read-r1/candidate'
SOURCES=PREVIOUS.SOURCES+[ROOT/'src/obj.h',ROOT/'src/c2_kernal_facade.h',ROOT/'src/c2_platform_dma.c']
AUTHORITIES=PREVIOUS.AUTHORITIES+[ROOT/'build/set-b-clear-protocol-r1/receipt.json',
    ROOT/'docs/planning/set-b-front-ordering-report.md',ROOT/'build/set-b-barrier-read-r1/host-r1/harness-binding.json']

PREFIX=r'''
#include <stdint.h>
#include <string.h>
#include "obj.h"
#include "c2-stream-decoder.h"
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
/* Only named accessed fields supplied; no claim this host struct is target ABI. */
typedef struct { uint8_t committed,record[32],meta[24];uint16_t *main_ordinal,new_entries; } c2_append_state;
static uint16_t c2_journal_count;
Cell heap[HEAP_CELLS];
static uint8_t mem_oom;
static obj functions[4];
static obj alloc(uint8_t type){heap[1].type=type;return (obj)2;}
static void set_sym_function(obj s,obj v){functions[SYMI_IDX(s)]=v;}
static uint16_t c2_u16(const uint8_t *p){return (uint16_t)(p[0]|(uint16_t)p[1]<<8);}
static uint8_t bank5[65536];
static uint8_t delivery_mode;
static uint16_t bounds_errors,submit_count,changed_bytes,first_submit,live_alias;
static uint8_t first_expected[4],first_observed[4];
/* A queue entry records the full pointer only for comparisons while the
 * producer is executing. It is explicitly discarded at function return. */
typedef struct { const uint8_t *source;uint8_t captured[4];uint16_t target,n; } job;
static job jobs[4];
uint8_t c2_stream_c2d_read(uint16_t at,void *dst,uint16_t n){
 if((uint32_t)at+n>65536u){++bounds_errors;return 0;}
 memcpy(dst,bank5+at,n);return 1;
}
static void submit(uint16_t low,uint8_t sb,uint16_t target,uint8_t tb,uint16_t n,const void *full){
 if(sb || tb!=5 || n!=4 || low!=(uint16_t)(uintptr_t)full || submit_count>=4){++bounds_errors;return;}
 /* At this hook both previous and current journal referents are still in
    the active producer frame. No post-return pointer dereference occurs. */
 if(delivery_mode==2){
  for(uint16_t j=0;j<submit_count;++j){
   job *p=&jobs[j];
   for(uint16_t i=0;i<p->n;++i){
    if(p->source[i]!=p->captured[i]){
     if(!changed_bytes){first_submit=submit_count+1;memcpy(first_expected,p->captured,4);
       memcpy(first_observed,p->source,4);live_alias=(p->source==full);}
     ++changed_bytes;
    }
   }
  }
 }
 job *p=&jobs[submit_count++];p->source=full;p->target=target;p->n=n;
 memcpy(p->captured,full,n);
 if(delivery_mode==0)memcpy(bank5+target,full,n);
}
/* Exact low16 ABI arguments are checked; the full host pointer is an explicit
   fixture seam, not an extra product parameter. */
#define c2_facade_c2_dma(s,sb,t,tb,n) submit((s),(sb),(t),(tb),(n),src)
'''
SUFFIX=r'''
uint16_t result[12];
uint8_t expected_bytes[4],observed_bytes[4],final_undo[8];
void probe(uint8_t mode,uint16_t count){
 memset(bank5,0,sizeof bank5);memset(heap,0,sizeof heap);memset(functions,0,sizeof functions);
 memset(jobs,0,sizeof jobs);memset(result,0,sizeof result);memset(first_expected,0,4);memset(first_observed,0,4);
 delivery_mode=mode;bounds_errors=submit_count=changed_bytes=first_submit=live_alias=c2_journal_count=mem_oom=0;
 c2_append_state w;memset(&w,0,sizeof w);w.committed=1;w.new_entries=22;
 w.meta[22]=(uint8_t)count;w.meta[23]=(uint8_t)(count>>8);
 for(uint16_t i=0;i<count;++i){
  uint8_t *row=bank5+C2_EXPORT_JOURNAL_BASE+8*i;
  uint16_t sym=(uint16_t)MK_SYMI(i),old=(uint16_t)MK_BCODE(10+i),next=20+i;
  row[0]=(uint8_t)sym;row[1]=(uint8_t)(sym>>8);row[2]=(uint8_t)old;row[3]=(uint8_t)(old>>8);
  row[4]=(uint8_t)next;row[5]=(uint8_t)(next>>8);functions[i]=(obj)old;
 }
 uint8_t status=c2_append_publish_exports_phase(&w);
 /* End of automatic storage lifetime. Clear every saved source pointer
    before executing anything after return. Snapshot controls own their bytes. */
 for(uint16_t i=0;i<submit_count;++i)jobs[i].source=0;
 if(mode==1)for(uint16_t i=0;i<submit_count;++i)memcpy(bank5+jobs[i].target,jobs[i].captured,jobs[i].n);
 result[0]=status;result[1]=submit_count;result[2]=changed_bytes;result[3]=first_submit;
 result[4]=live_alias;result[5]=bounds_errors;result[6]=c2_journal_count;
 result[7]=mode==2?submit_count:0;result[8]=(uint16_t)functions[0];result[9]=(uint16_t)functions[1];
 result[10]=w.record[22];result[11]=mode==2?1:0;
 memcpy(expected_bytes,first_expected,4);memcpy(observed_bytes,first_observed,4);
 memcpy(final_undo,bank5+C2_EXPORT_JOURNAL_BASE,8);
}
'''


def extract(text,signature):
    start=text.index(signature);end=text.index('\n}\n',start)+3
    return text[start:end]


def prepare():
    PREVIOUS.check();authority=S.require_auth();OUT.mkdir(exist_ok=False)
    old=P.load(PREVIOUS.OUT/'receipt.json')
    for row in old['compiler_inputs']+old['candidate']:assert P.bind(ROOT/row['path'])==row
    runtime=(CANDIDATE/'src/c2_product_runtime.c').read_text()
    names=[('writer','C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write('),
           ('publisher','uint8_t c2_append_publish_exports_phase(')]
    bodies=[]
    for name,signature in names:
        body=extract(runtime,signature);bodies.append(body);(OUT/(name+'.c')).write_text(body)
    fixture=OUT/'fixture.c';fixture.write_text(PREFIX+'\n'.join(bodies)+SUFFIX)
    header=ROOT/'config/set-b-native/includes/c2-stream-decoder.h'
    shutil.copyfile(header,OUT/'c2-stream-decoder.h')
    P.write(OUT/'binding.json',dict(execution_head=HEAD,source_authority=authority,driver=P.bind(Path(__file__)),
        predecessor=P.bind(PREVIOUS.SEAL),source=P.bind(CANDIDATE/'src/c2_product_runtime.c'),
        compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],candidate=old['candidate'],
        functions=[P.bind(OUT/(n+'.c')) for n,_ in names],fixture=P.bind(fixture),header=P.bind(header),
        target_layout=False,product_source_changes=0,
        seams=['Exact unedited publisher and region-write bodies; object macros from src/obj.h.',
            'Context supplies only accessed named fields; no sizeof/target-stack-size assertion.',
            'Bank5 plan reads and symbol/allocator effects are bounded host seams; no actual GC.',
            'Facade checks original low16 arguments and carries full host source pointer separately.',
            'Mode0 immediate; mode1 source captured at submit with later target commit; mode2 source fetch deferred while CPU proceeds.',
            'Live-frame source comparisons only. All saved pointers cleared at producer return; no expired pointer read.',
            'Mode2 is a source-lifetime obligation, not a claimed hardware schedule; late visibility alone does not imply late source fetch.'],
        budget=dict(source_forms=1,host_compile_attempts=2,host_links=2,host_dependencies=1,native_object_calls=16,
            native_dependencies=8,assembler_calls=2,product_builds=0,product_links=0,seeds=0,finals=0,guest=0,device=0)))
    P.write(OUT/'gate-order.json',dict(first='Exact producer source lifetime under both capture policies, before authoring the terminal implementation.',
        next=['All four completion modes with retained destination; partial publication/duplicate symbols/macro roots.',
            'No GC/allocation/root drop or restoration while unretired; late64-frame and repeated reentry.',
            'RUN/STOP before/after terminal decision; transaction-end failure and empty-C2J bypass.',
            'Nested transients, exact status/file nil and bytewise header/code/C2D/exports rollback.',
            'Three falling protocol controls; matched native object and placement prices.'],
        stop='First unclosed lifetime/semantic/capacity gate; no native pricing or source workaround after red.'))
    print('PREPARED exact publisher/writer source-lifetime preflight; no product source form yet')


def host():
    assert not (OUT/'command.json').exists()
    attempt=1+len(list(OUT.glob('attempt-*')))
    assert attempt<=2,'Host compile attempt budget exhausted'
    binding=P.load(OUT/'binding.json')
    for row in binding['functions']+[binding['fixture']]:assert P.bind(ROOT/row['path'])==row
    command=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(OUT/'fixture.c'),'-o',str(OUT/'fixture.so')]
    P.write(OUT/'command.json',dict(command=command,status='attempt charged before execution'))
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    (OUT/'compile.log').write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=command,exit=r.returncode,log=P.bind(OUT/'compile.log')))
    assert r.returncode==0,r.stderr
    dep=command[:];at=dep.index('-o');del dep[at:at+2];dep+=['-M','-MT','fixture']
    r=subprocess.run(dep,cwd=ROOT,capture_output=True,text=True)
    (OUT/'dependencies.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0,r.stderr
    internal,external=[],[]
    for name in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
        p=(ROOT/name).resolve()
        (internal if p.is_relative_to(ROOT) else external).append(P.bind(p) if p.is_relative_to(ROOT) else external_binding(p))
    P.write(OUT/'dependencies.json',dict(command=dep,exit=r.returncode,internal=internal,external=external,
        compiler=external_binding(Path(shutil.which('cc')).resolve())))
    lib=C.CDLL(str(OUT/'fixture.so'));lib.probe.argtypes=[C.c_uint8,C.c_uint16]
    rows=[];keys=['producer_status','submissions','changed_source_bytes','first_changed_at_submit','same_live_pointer',
        'bounds_errors','journal_count','unconsumed_sources_at_return','function0','function1','plan_mark','expired_reads_avoided']
    for mode,count in ((0,1),(0,2),(1,1),(1,2),(2,2)):
        lib.probe(mode,count)
        got=dict(zip(keys,list((C.c_uint16*12).in_dll(lib,'result'))))
        expected=list((C.c_uint8*4).in_dll(lib,'expected_bytes'));observed=list((C.c_uint8*4).in_dll(lib,'observed_bytes'))
        undo=list((C.c_uint8*8).in_dll(lib,'final_undo'))
        expected_undo=[]
        for i in range(count):expected_undo+=list((0xe000+2*i).to_bytes(2,'little')+(0xc014+2*i).to_bytes(2,'little'))
        ok=got['producer_status']==0 and got['bounds_errors']==0 and got['changed_source_bytes']==0
        if mode!=2:ok=ok and undo[:count*4]==expected_undo
        row=dict(mode=mode,count=count,actual=got,first_expected=expected,first_observed=observed,undo=undo,pass_gate=ok)
        rows.append(row);P.write(OUT/'rows.json',rows)
        if not ok:
            P.write(OUT/'halt.json',row);break
    assert len(rows)==5 and all(r['pass_gate'] for r in rows[:4])
    halt=rows[-1];assert not halt['pass_gate']
    assert halt['actual']['changed_source_bytes']==2 and halt['actual']['first_changed_at_submit']==2
    assert halt['actual']['same_live_pointer']==1 and halt['actual']['producer_status']==0
    old=P.load(PREVIOUS.OUT/'receipt.json')
    P.write(OUT/'receipt.json',dict(status='HALT: deferred-source ownership fails; capture-before-reuse bridge unbound',
        execution_head=HEAD,source_authority=binding['source_authority'],driver=P.bind(Path(__file__)),
        predecessor=P.bind(PREVIOUS.SEAL),compiler_authority=binding['compiler_authority'],compiler_inputs=binding['compiler_inputs'],
        candidate=binding['candidate'],verified_compiler_roots=74,
        artifacts=[P.bind(p) for p in sorted(OUT.glob('*')) if p.is_file()],
        this_commission=dict(compiler_calls=attempt,host_link_attempts=attempt,host_links=1,dependency_calls=1,assembler_calls=0,native_object_calls=0,
            native_dependencies=0,host_c_rows=len(rows),product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,new_source_forms=0),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        next_recommendation='Bind source capture separately from late destination visibility using existing evidence; if capture is not provable, include stable producer storage or synchronous stores in the same repair scope before native pricing.',
        limit='Host source-policy differential only; no claim hardware defers source fetch, no out-of-lifetime dereference, no current product-corruption/third-defect-class assertion. The new CLEAR controller was not authored after this preflight halt.'))
    print('HALT:4 capture controls pass; second deferred-source submission sees2 changed bytes in the same live journal[4]; no expired read')

def seal():
    PREVIOUS.check();S.require_auth()
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    receipt=P.load(OUT/'receipt.json')
    selected={p for p in OUT.rglob('*') if p.is_file()}
    selected.update(SOURCES+AUTHORITIES+[REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT])
    selected.update(local_import_closure([Path(__file__)]))
    external=[external_binding(Path(shutil.which(n)).resolve()) for n in ('python3','rg')]
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
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continueb95ba185: one isolated CLEAR implementation with host compile/link attempts2, host dependency1, native object calls16/dependencies8, assembler2;0 product build/link/Seed/Final/guest/device. Prepare exact-C lifetime successors first and stop at first unresolved gate. Full rollback remains selected.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-clear-protocol-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        row=P.bind(path);inputs.append(row)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/path.relative_to(ROOT)
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
    PREVIOUS.check();S.require_auth();print('PASS CLEAR C preflight seal:74 roots, exact bodies, policy controls, live-frame halt and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','host','seal','check'))
    {'prepare':prepare,'host':host,'seal':seal,'check':check}[parser.parse_args().mode]()
