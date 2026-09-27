"""Publication root gate for the synchronous CLEAR candidate; explicit transport seam."""
import ctypes as C
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_clear_gc_gate_20260926 as OLD
from set_b_load_preflight_seal_20260926 import external_binding


def prepare(out,candidate):
    out.mkdir(exist_ok=False)
    prefix=OLD.PREFIX.replace('#define C2_EXPORT_PLAN_RECORD_BYTES 8u', '#define C2_EXPORT_PLAN_RECORD_BYTES 8u\n#define C2_EXPORT_PLAN_LIMIT 48384u')
    prefix=prefix.replace('static uint8_t bank5[65536],marked[HEAP_CELLS];', '''static uint8_t bank5[65536],marked[HEAP_CELLS];
static uint16_t logical_fn[8],symbols,duplicate,fail_alloc,fault_store,undo_calls,fail_undo;
uint16_t missing_new[8],sync_writes,failed_stores;
''')
    # Record logical publication separately from physical visibility. This is
    # the independent owner set that the GC must keep alive for pending stores.
    a=prefix.index('static void submit(');b=prefix.index('\n#define c2_facade_c2_dma',a)
    prefix=prefix[:b]+'''
static uint8_t c2_map_cpu_write(uint32_t at,const void *src,uint16_t n){
 if((at>>16)!=5u || (at&65535u)+n>65536u || (n!=2 && n!=4)){++bounds_errors;return 0;}
 if(n==4 && ++undo_calls==fail_undo){++failed_stores;return 0;}
 if(n==2)logical_fn[((uint16_t)at-SYMFN_EXT_OFF)/2]=c2_u16(src);
 if((fault_store==1) || (fault_store==2 && n==4) || (fault_store==3 && n==2)){
  submit((uint16_t)(uintptr_t)src,0u,(uint16_t)at,5u,n,src);return 1;
 }
 memcpy(bank5+(at&65535u),src,n);++sync_writes;return 1;
}
'''+prefix[b:]
    prefix=prefix.replace('i<count;++i','i<symbols;++i')
    prefix=prefix.replace(' uint16_t *r=gc_rows[gc_count];', ''' for(uint16_t i=0;i<symbols;++i){
  uint16_t o=logical_fn[i];
  if(o>=64 && o<64+2*(allocations-1) && !marked[o/2])++missing_new[gc_count];
 }
 uint16_t *r=gc_rows[gc_count];''')
    prefix=prefix.replace(' obj fresh=(obj)(64+2*(allocations-1));', ' if(allocations==fail_alloc){mem_oom=1;return NIL;}\n obj fresh=(obj)(64+2*(allocations-1));')
    suffix=OLD.SUFFIX.replace('void probe(uint16_t mode,uint16_t n){', '''void probe(uint16_t mode,uint16_t n,uint16_t dup,uint16_t fa,uint16_t fw,uint16_t mutation){
 duplicate=dup;symbols=dup?1:n;fail_alloc=fa;fail_undo=fw;fault_store=0;
 sync_writes=failed_stores=undo_calls=0;memset(missing_new,0,sizeof missing_new);memset(logical_fn,0,sizeof logical_fn);''')
    suffix=suffix.replace('obj old=(obj)(2*(i+1));', 'uint16_t si=duplicate?0:i;obj old=(obj)(2*(si+1));')
    suffix=suffix.replace('set_sym_function(MK_SYMI(i),old);','set_sym_function(MK_SYMI(si),old);')
    suffix=suffix.replace('uint16_t sym=(uint16_t)MK_SYMI(i),tagged=', 'uint16_t sym=(uint16_t)MK_SYMI(si),tagged=')
    suffix=suffix.replace('submits=job_head=0;memset(jobs,0,sizeof jobs);delivery_mode=mode;', 'submits=job_head=0;memset(jobs,0,sizeof jobs);delivery_mode=mode;fault_store=mutation;sync_writes=undo_calls=0;')
    runtime=(candidate/'src/c2_product_runtime.c').read_text();symbol=(P.ROOT/'src/symbol.c').read_text();dma=(candidate/'src/c2_platform_dma.c').read_text()
    specs=[('undo',runtime,'static C2_KERNAL_RESIDENT uint8_t c2_export_undo_store('),
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
        body=OLD.extract(text,signature);(out/(name+'.c')).write_text(body);bodies.append(body)
    (out/'fixture.c').write_text(prefix+'\n'.join(bodies)+suffix)
    shutil.copyfile(P.ROOT/'config/set-b-native/includes/c2-stream-decoder.h',out/'c2-stream-decoder.h')
    P.write(out/'binding.json',dict(functions=[P.bind(out/(n+'.c')) for n,_,_ in specs],fixture=P.bind(out/'fixture.c'),driver=P.bind(Path(__file__)),
        plan='All candidate rows must retain old before-images and latest logically published wrappers, with duplicates and allocation/store failures; transport mutation controls must fail.',
        limits='Host root reachability, no collector sweep. Synchronous writer is memcpy seam; target MAP body unexecuted. Actual target placement/ABI must be qualified separately.'))


def run(out):
    command=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror','-I'+str(out),'-I'+str(P.ROOT/'src'),str(out/'fixture.c'),'-o',str(out/'fixture.so')]
    assert not (out/'command.json').exists()
    P.write(out/'command.json',dict(command=command,status='host compile/link attempt1 charged before execution',compiler=external_binding(Path(shutil.which('cc')).resolve())))
    r=subprocess.run(command,cwd=P.ROOT,capture_output=True,text=True);(out/'compile.log').write_text(r.stdout+r.stderr)
    P.write(out/'command.json',dict(command=command,exit=r.returncode,log=P.bind(out/'compile.log'),compiler=external_binding(Path(shutil.which('cc')).resolve())))
    assert r.returncode==0,r.stderr
    lib=C.CDLL(str(out/'fixture.so'));lib.probe.argtypes=[C.c_uint16]*6
    rows=[]
    for mode in range(3):
        for n in range(1,9):
            for dup in (0,1):
                for fa,fw in ((0,0),(1,0),(n,0),(0,1),(0,n)):
                    lib.probe(mode,n,dup,fa,fw,0)
                    result=list((C.c_uint16*10).in_dll(lib,'result'));raw=(C.c_uint16*12*8).in_dll(lib,'gc_rows')
                    new=list((C.c_uint16*8).in_dll(lib,'missing_new'))[:result[7]]
                    obs=[list(raw[i]) for i in range(result[7])]
                    failures=fa or fw
                    passed=(result[0]!=0 if failures else result[0]==0) and result[2]==0 and result[5]==0 and all(o[2]==0 for o in obs) and not any(new) and result[3]==0
                    row=dict(mode=mode,n=n,duplicate=dup,allocation_fail=fa,undo_fail=fw,result=result,old_observations=obs,new_missing=new,pass_gate=passed)
                    rows.append(row);P.write(out/'rows.json',rows)
                    if not passed:
                        P.write(out/'halt.json',row);return False
    controls=[]
    for mutation,mode,n in ((1,2,4),(2,1,4),(3,1,2)):
        lib.probe(mode,n,0,0,0,mutation)
        result=list((C.c_uint16*10).in_dll(lib,'result'));raw=(C.c_uint16*12*8).in_dll(lib,'gc_rows')
        old=[raw[i][2] for i in range(result[7])];new=list((C.c_uint16*8).in_dll(lib,'missing_new'))[:result[7]]
        row=dict(mutation=mutation,mode=mode,n=n,result=result,old_missing=old,new_missing=new,caught=any(old) or any(new));controls.append(row)
        P.write(out/'falling-controls.json',controls)
        if not row['caught']:P.write(out/'halt.json',row);return False
    P.write(out/'result.json',dict(status='PASS root prerequisite',candidate_rows=len(rows),falling_controls=len(controls),root_observations=sum(len(r['old_observations']) for r in rows),
        scope='Old predecessor and latest logically published wrapper roots; no full GC/sweep, terminal controller or target MAP execution.'))
    return True
