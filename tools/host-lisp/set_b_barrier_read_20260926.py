"""One isolated trailing-DMA completion form; ordered-delivery and lifetime gates."""
import argparse
import ctypes as C
import difflib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_integration_r2_20260926 as I
import set_b_front_ordering_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding

ROOT = P.ROOT
OUT = ROOT / 'build/set-b-barrier-read-r1'
HEAD = '0089c308'
OLD_READ = '''    reader_ok = c2_stream_c2d_read(
        mode == C2_COMPLETION_PUBLISH_MARK ? 0u : C2D_UNWIND_BASE,
        observed, attempt_length);'''
NEW_READ = '''    /* The transaction fence must share the writers' ordered DMA engine.
     * Ordinary C2D consumers keep their synchronous MAP/CPU reader. */
    c2_facade_c2_dma(
        (uint16_t)(LISP65_C2D_BASE
            + (mode == C2_COMPLETION_PUBLISH_MARK ? 0u : C2D_UNWIND_BASE)),
        LISP65_C2D_BANK, (uint16_t)(uintptr_t)observed, 0u, attempt_length);
    reader_ok = 1u; /* Submission has no status; only content proves delivery. */'''

MODEL_DECL = r'''
static uint8_t model_enabled;
static uint8_t model_write(uint16_t at, const void *src, uint16_t n);
static void model_tick(void);
static void model_submit(uint16_t at, uint8_t bank, uint16_t low,
                         uint8_t target_bank, uint16_t n, uint8_t *full);
/* Host ABI bridge: preserve/check the actual truncated target argument,
   carrying the lexical local pointer separately; never dereference low16. */
#define c2_facade_c2_dma(s,b,t,tb,n) model_submit((s),(b),(t),(tb),(n),observed)
#define LISP65_C2D_BANK 5u
#define LISP65_C2D_BASE 0u
'''

MODEL = r'''
/* An explicit ordered job queue, NOT a hardware DMA emulator. Write sources
   remain pointers and are sampled on delivery; a separate snapshot detects
   source lifetime/mutation mistakes. DMA destination pointers are never used
   after the tested function returns. Only their outstanding count is kept. */
typedef struct {
 uint8_t bank; uint16_t at,n,done; const uint8_t *src; uint8_t snapshot[64];
} model_job;
static model_job jobs[8];
static uint8_t job_count,job_head,read_active,read_done,read_style,drop_data;
static uint16_t ticks,write_wait,read_wait,chunk,read_at,read_n,read_bytes;
static uint16_t submits,lifetime_errors,order_errors,escaped,read_low;
static uint8_t *read_pointer;
static uint8_t bank2[65536],payload2[16],payload5[16],expected_header[48];
uint16_t barrier_result[14],event_count,events[256][4];
static void event(uint16_t kind,uint16_t a,uint16_t b){
 if(event_count<256){events[event_count][0]=ticks;events[event_count][1]=kind;
 events[event_count][2]=a;events[event_count][3]=b;++event_count;}
}
static uint16_t pending_bytes(void){
 uint16_t n=0;for(uint8_t i=job_head;i<job_count;++i)n+=jobs[i].n-jobs[i].done;return n;
}
static uint8_t *memory(uint8_t bank){return bank==2?bank2:arena;}
static uint8_t enqueue(uint8_t bank,uint16_t at,const void *src,uint16_t n){
 if(job_count==8 || n>64 || (uint32_t)at+n>65536u){++bounds_errors;return 0;}
 model_job *j=&jobs[job_count++];j->bank=bank;j->at=at;j->n=n;j->done=0;j->src=src;
 memcpy(j->snapshot,src,n);event(1,bank,n);return 1;
}
static uint8_t model_write(uint16_t at,const void *src,uint16_t n){
 ++writes;return enqueue(5,at,src,n);
}
static void model_submit(uint16_t at,uint8_t bank,uint16_t low,
                         uint8_t target_bank,uint16_t n,uint8_t *full){
 ++submits;read_low=low;
 if(bank!=5 || target_bank || (n!=48 && n!=64) || low!=(uint16_t)(uintptr_t)full
    || read_active){++bounds_errors;return;}
 read_at=at;read_n=n;read_pointer=full;read_bytes=0;read_active=1;read_done=0;
 event(2,at,n);
}
static void model_tick(void){
 if(!model_enabled || !read_active || read_done)return;
 ++ticks;
 if(ticks<=write_wait)return;
 if(job_head<job_count){
   model_job *j=&jobs[job_head];uint16_t take=j->n-j->done;if(take>chunk)take=chunk;
   for(uint16_t k=0;k<take;++k){uint16_t i=j->done+k;
     if(j->src[i]!=j->snapshot[i])++lifetime_errors;
     if(!drop_data || (j->at!=2116 && j->bank!=2))memory(j->bank)[j->at+i]=j->src[i];
   }
   j->done+=take;event(3,j->bank,j->n-j->done);
   if(j->done==j->n)++job_head;
   if(job_head<job_count)return;
 }
 if(ticks<read_wait)return;
 if(pending_bytes())++order_errors;
 /* Completed-but-corrupt/absent/partial read controls. These are terminal
    fault injections, unlike the separately tested still-pending late job. */
 if(read_style){
   uint16_t take=read_style==1?0:read_style==2?read_n/2:read_n;
   memcpy(read_pointer,arena+read_at,take);
   if(read_style==3)read_pointer[0]^=1;
   read_bytes=take;read_done=1;read_active=0;event(4,take,read_style);return;
 }
 uint16_t take=read_n-read_bytes;if(take>chunk)take=chunk;
 memcpy(read_pointer+read_bytes,arena+read_at+read_bytes,take);read_bytes+=take;
 event(4,take,read_n-read_bytes);
 if(read_bytes==read_n){read_done=1;read_active=0;}
}
static void reset_model(void){
 model_enabled=0;job_count=job_head=read_active=read_done=read_style=drop_data=0;
 ticks=write_wait=read_wait=submits=lifetime_errors=order_errors=escaped=read_low=0;
 read_at=read_n=read_bytes=0;read_pointer=0;chunk=64;event_count=0;
 memset(jobs,0,sizeof jobs);memset(events,0,sizeof events);
 memset(bank2,0xa5,sizeof bank2);memset(payload2,0x37,sizeof payload2);
 memset(payload5,0,sizeof payload5);memset(barrier_result,0,sizeof barrier_result);
}
/* setup=0: content predicate; setup=1: pending data after ACTIVE;
   setup=2: actual journal producer itself remains queued. */
void barrier_test(uint8_t mode,uint8_t mutation,uint8_t style,uint16_t ww,
                  uint16_t rw,uint16_t part,uint8_t old,uint8_t drop,uint8_t setup){
 reset_model();writer_setup(0,0,0,0,0);work.length=64;work.attic=256;
 work.old_images=6;work.new_images=7;
 if(setup==2)model_enabled=1;
 uint8_t status=c2_append_journal_write_phase(&work);
 memcpy(expected_header,work.old_header,48);
 if(mode==C2_COMPLETION_PUBLISH_MARK)memcpy(arena,expected_header,48);
 if(mode==C2_COMPLETION_CLEAR_MARK)memset(arena+C2D_UNWIND_BASE,0,64);
 if(mutation==1)arena[mode==C2_COMPLETION_PUBLISH_MARK?0:C2D_UNWIND_BASE]^=1;
 if(mutation==2)C2AW_C2J_SEAL_BYTES(&work)[0]^=1;
 model_enabled=1;read_style=style;write_wait=ww;read_wait=rw;chunk=part;drop_data=drop;
 if(setup==1){enqueue(2,4096,payload2,16);c2_stream_c2d_write(2116,payload5,16);}
 reads=0;
 uint8_t ok=old?map_completion_poll(&work,mode,mode==C2_COMPLETION_PUBLISH_MARK?expected_header:0)
               :c2_completion_poll(&work,mode,mode==C2_COMPLETION_PUBLISH_MARK?expected_header:0);
 /* End of the actual poll's automatic-buffer lifetime. Do not execute a
    late write: retaining a live destination obligation already fails. */
 escaped=read_active && !read_done;
 event(5,ok,escaped);
 barrier_result[0]=status;barrier_result[1]=ok;barrier_result[2]=submits;
 barrier_result[3]=reads;barrier_result[4]=ticks;barrier_result[5]=pending_bytes();
 barrier_result[6]=read_active?read_n-read_bytes:0;barrier_result[7]=lifetime_errors;
 barrier_result[8]=order_errors;barrier_result[9]=escaped;
 barrier_result[10]=memcmp(bank2+4096,payload2,16)==0 && memcmp(arena+2116,payload5,16)==0;
 barrier_result[11]=work.committed;barrier_result[12]=bounds_errors;barrier_result[13]=read_low!=0;
 /* Diagnostic fixture teardown does not stand in for product cancellation. */
 read_pointer=0;model_enabled=0;
}
'''


def prepare():
    PREVIOUS.check()
    authority = S.require_auth()
    OUT.mkdir(exist_ok=False)
    base = F.OUT / 'candidate'
    shutil.copytree(base, OUT / 'candidate')
    path = OUT / 'candidate/src/c2_product_runtime.c'
    before = path.read_text()
    assert before.count(OLD_READ) == 1
    after = before.replace(OLD_READ, NEW_READ)
    path.write_text(after)
    patch = OUT / 'authored.patch'
    patch.write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
        fromfile='a/src/c2_product_runtime.c', tofile='b/src/c2_product_runtime.c')))
    files = sorted(p for p in base.rglob('*') if p.is_file())
    changed = [str(p.relative_to(base)) for p in files
               if p.read_bytes() != (OUT / 'candidate' / p.relative_to(base)).read_bytes()]
    assert changed == ['src/c2_product_runtime.c']
    oldpoll = I.function(before[before.index('static uint8_t c2_completion_poll'):], 'c2_completion_poll')
    newpoll = I.function(after[after.index('static uint8_t c2_completion_poll'):], 'c2_completion_poll')
    assert newpoll == oldpoll.replace(OLD_READ, NEW_READ)
    P.write(OUT / 'binding.json', dict(source_authority=authority, execution_head=HEAD,
        predecessor=P.bind(PREVIOUS.SEAL), driver=P.bind(Path(__file__)), patch=P.bind(patch),
        before=[P.bind(p) for p in files], candidate=[P.bind(OUT / 'candidate' / p.relative_to(base)) for p in files],
        changed=changed, budget=dict(forms=1,host_compile_attempts=2,host_links=2,host_dependencies=1,
            native_object_compiles=10,native_dependencies=10,product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        scope='Isolated candidate only; direct ordered DMA at common completion boundary; no maintained product source edit.'))
    print('PREPARED one isolated completion-reader form')


def host():
    S.require_auth()
    out = OUT / 'host-r1'
    out.mkdir(exist_ok=False)
    base = ROOT / 'build/set-b-front-fence-r1/fixture.c'
    text = base.read_text()
    oldpoll = I.function(text[text.index('static uint8_t c2_completion_poll(c2_append_state *w'):], 'c2_completion_poll')
    runtime = (OUT / 'candidate/src/c2_product_runtime.c').read_text()
    newpoll = I.function(runtime[runtime.index('static uint8_t c2_completion_poll'):], 'c2_completion_poll')
    assert oldpoll.replace(OLD_READ, NEW_READ) == newpoll
    assert text.count(oldpoll) == 1
    text = text.replace(oldpoll, oldpoll.replace('c2_completion_poll(', 'map_completion_poll(', 1) + '\n' + newpoll)
    original_test = I.function(text, 'fence_test')
    text = text.replace(original_test, original_test.replace('c2_completion_poll(', 'map_completion_poll('))
    write = I.function(text, 'c2_stream_c2d_write')
    text = text.replace(write, MODEL_DECL + write.replace('{', '{\n if(model_enabled)return model_write(at,src,n);', 1))
    length = I.function(text[text.index('uint8_t c2_completion_mode_length(uint8_t mode) {'):], 'c2_completion_mode_length')
    text = text.replace(length, length.replace('c2_completion_mode_length(', 'unhooked_mode_length(', 1) +
        '\nstatic uint8_t c2_completion_mode_length(uint8_t mode) {\n model_tick();return unhooked_mode_length(mode);\n}\n')
    fixture = out / 'fixture.c'
    fixture.write_text(text + MODEL)
    shutil.copyfile(base.parent / 'c2-stream-decoder.h', out / 'c2-stream-decoder.h')
    for name in ('rtov_crc_mem','c2j_crc32','c2_completion_bytes_equal','c2_completion_c2j_matches',
                 'c2_append_journal_write_phase'):
        source = runtime[runtime.index('C2_APPEND_INLINE uint16_t rtov_crc_mem'):] if name == 'rtov_crc_mem' else runtime
        body = I.function(source, name)
        assert body in text, name
        (out / (name + '.c')).write_text(body)
    (out / 'c2_completion_poll.c').write_text(newpoll)
    P.write(out / 'harness-binding.json', dict(base=P.bind(base), fixture=P.bind(fixture),
        source=P.bind(OUT / 'candidate/src/c2_product_runtime.c'),
        preserved='Exact poll/CRC/seal/journal function text; unchanged original72 rows execute MAP control.',
        seams=['Bounded memory; queued writes hold source pointers plus mutation-detection snapshots.',
               'Facade macro carries full host destination pointer alongside checked low16 ABI argument.',
               'Host mode-length wrapper ticks queue before calling unchanged host parity body.',
               'Host64 attempts, not native64 frames; no hardware reachability proof.',
               'Raw void DMA has no read-error return. Original zero/half/full-copy-with-failure cases retained on MAP control; candidate uses terminal absent/partial/corrupt delivery plus delayed pending-job cases.'],
        lifetime='Pending destination on poll return is a failure; fixture never dereferences escaped local storage or calls teardown a product cancellation.'))
    command = ['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror',
               '-Wno-misleading-indentation','-I'+str(out),'-I'+str(ROOT / 'src'),str(fixture),'-o',str(out / 'fixture.so')]
    result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    (out / 'compile.log').write_text(result.stdout + result.stderr)
    P.write(out / 'command.json',dict(command=command,exit=result.returncode,log=P.bind(out / 'compile.log')))
    assert result.returncode == 0, result.stderr
    dep = command.copy();at=dep.index('-o');del dep[at:at+2];dep+=['-M','-MT','fixture']
    result = subprocess.run(dep,cwd=ROOT,capture_output=True,text=True)
    (out / 'dependencies.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    internal,external=[],[]
    for name in result.stdout.replace('\\\n',' ').split(':',1)[1].split():
        p=(ROOT/name).resolve()
        (internal if p.is_relative_to(ROOT) else external).append(P.bind(p) if p.is_relative_to(ROOT) else external_binding(p))
    P.write(out / 'dependencies.json',dict(command=dep,exit=result.returncode,internal=internal,external=external,log=P.bind(out / 'dependencies.log')))
    library = C.CDLL(str(out / 'fixture.so'))
    library.fence_test.argtypes=[C.c_uint8]*4
    library.barrier_test.argtypes=[C.c_uint8]*3+[C.c_uint16]*3+[C.c_uint8]*3
    keys=['producer_status','accept','dma_reads','map_reads','ticks','pending_write_bytes','pending_read_bytes',
          'source_lifetime_errors','order_errors','escaped_destination','data_complete','committed','bounds_errors','has_target_address']
    rows=[]
    def record(row):
        rows.append(row)
        P.write(out / 'rows.json', rows)
        if not row['pass_gate']:
            P.write(out / 'halt.json',row)
            return False
        return True
    def run(kind,args,expected,check):
        library.barrier_test(*args)
        got=dict(zip(keys,list((C.c_uint16*14).in_dll(library,'barrier_result'))))
        count=C.c_uint16.in_dll(library,'event_count').value
        trace=[list(x) for x in ((C.c_uint16*4)*256).in_dll(library,'events')][:count]
        return record(dict(kind=kind,args=args,actual=got,expected=expected,trace=trace,
            pass_gate=check(got) and got['producer_status']==0 and got['bounds_errors']==0))
    stopped=False
    for mode in (0xa1,0xa2,0xa3,0xa4,0,0xa5):
        for mutation in (0,1,2):
            for fail in (0,1):
                for part in ((0,) if not fail else (0,1,2)):
                    library.fence_test(mode,mutation,fail,part)
                    got=list((C.c_uint16*9).in_dll(library,'fence_result'))
                    valid=0xa1<=mode<=0xa4
                    expected=int(valid and not fail and mutation!=1 and (mutation!=2 or mode in (0xa2,0xa4)))
                    if not record(dict(kind='original-MAP-content',mode=mode,mutation=mutation,read_failure=fail,partial=part,
                        actual=got,expected_accept=expected,pass_gate=got[0]==0 and got[1]==expected and got[2]==int(valid) and got[3:5]==[0,0])):
                        stopped=True;break
                if stopped:break
            if stopped:break
        if stopped:break
    if not stopped:
        for mode in (0xa1,0xa2,0xa3,0xa4,0,0xa5):
            for mutation in (0,1,2):
                for style in (0,1,2,3):
                    valid=0xa1<=mode<=0xa4
                    expected=int(valid and style==0 and mutation!=1 and (mutation!=2 or mode in (0xa2,0xa4)))
                    ok=run('DMA-content',[mode,mutation,style,0,0,64,0,0,0],dict(accept=expected,dma_reads=int(valid)),
                        lambda x: x['accept']==expected and x['dma_reads']==int(valid) and x['map_reads']==0
                        and x['escaped_destination']==0 and x['committed']==0)
                    if not ok:stopped=True;break
                if stopped:break
            if stopped:break
    if not stopped:
        for mode in (0xa1,0xa2,0xa3,0xa4):
            for delay,part in ((0,64),(3,8),(32,4)):
                if not run('ordered-data-and-read',[mode,0,0,delay,0,part,0,0,1],
                    'Accept only after both data jobs and complete read; live source and local destination.',
                    lambda x: x['accept']==1 and x['data_complete']==1 and x['dma_reads']==1 and x['map_reads']==0
                    and all(x[k]==0 for k in ('pending_write_bytes','pending_read_bytes','source_lifetime_errors','order_errors','escaped_destination','committed'))):
                    stopped=True;break
            if stopped:break
    if not stopped:
        stopped=not run('queued-real-journal-producer',[0xa1,0,0,3,0,8,0,0,2],
            'Actual producer source stays valid until ACTIVE delivery.',lambda x:x['accept']==1 and x['source_lifetime_errors']==0 and x['escaped_destination']==0 and x['pending_write_bytes']==0)
    if not stopped:
        stopped=not run('falling-MAP-control',[0xa3,0,0,0,0,8,1,0,1],
            'Old CPU reader accepts while32 data bytes stay pending; expected falling control.',
            lambda x:x['accept']==1 and x['pending_write_bytes']==32 and x['data_complete']==0 and x['dma_reads']==0 and x['map_reads']==1)
    if not stopped:
        stopped=not run('permanent-drop-known-limit',[0xa3,0,0,0,0,64,0,1,1],
            'Accepted matching journal cannot detect dropped unrelated data; this is a demonstrated limit, NOT robustness qualification.',
            lambda x:x['accept']==1 and x['data_complete']==0 and x['pending_write_bytes']==0 and x['escaped_destination']==0)
    if not stopped:
        stopped=not run('last-attempt-delivery',[0xa3,0,0,0,64,64,0,0,1],
            'Complete read on attempt64 succeeds with no remaining destination obligation.',
            lambda x:x['accept']==1 and x['ticks']==64 and x['data_complete']==1 and x['escaped_destination']==0)
    if not stopped:
        stopped=not run('late-read-destination-lifetime',[0xa3,0,0,0,65,64,0,0,1],
            'Timeout must refuse without leaving any future DMA write into the expired local buffer.',
            lambda x:x['accept']==0 and x['committed']==0 and x['escaped_destination']==0 and x['pending_read_bytes']==0)
    P.write(out / 'receipt.json',dict(status='HALT AT FIRST C OR LIFETIME GATE' if stopped else 'PASS BOUNDED HOST GATES; NATIVE PRICING NEXT',
        execution_head=HEAD,driver=P.bind(Path(__file__)),binding=P.bind(OUT / 'binding.json'),harness=P.bind(out / 'harness-binding.json'),
        fixture=P.bind(fixture),command=P.bind(out / 'command.json'),library=P.bind(out / 'fixture.so'),dependencies=P.bind(out / 'dependencies.json'),
        rows=P.bind(out / 'rows.json'),halt=P.bind(out / 'halt.json') if stopped else None,
        row_count=len(rows),passing_rows=sum(r['pass_gate'] for r in rows),
        host_compile_attempts=1,host_links=1,host_dependencies=1,native_object_compiles=0,native_dependencies=0,
        product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,
        limits='Exact C function bodies at explicit host memory/ABI/tick seams. Ordered queue is a contract model, not hardware timing. No post-return buffer dereference, no full publication/replay claim. Stop before native pricing on any failed gate.'))
    print('HALT' if stopped else 'PASS',len(rows),'rows;',sum(r['pass_gate'] for r in rows),'expected outcomes; native pricing not run')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','host'))
    {'prepare':prepare,'host':host}[parser.parse_args().mode]()
