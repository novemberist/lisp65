"""Full installer callers and exact error mapping on the unchanged span candidate."""
from pathlib import Path
import ctypes as C
import re, subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_integration_r2_20260926 as I
ROOT=P.ROOT;OUT=ROOT/'build/set-b-front-paths-r1'
EXTRA=r'''
static uint8_t install_inner_status,install_calls,begin_calls,end_calls;
obj lisp_t=2;uint8_t vm_status;
c2_emit_status c2_session_emit_reset(void){return mode==30?C2_EMIT_STATE:C2_EMIT_OK;}
c2_emit_status c2_session_emit_add(obj f,obj n,uint8_t flags){(void)f;(void)n;(void)flags;return mode==31?C2_EMIT_SHAPE:C2_EMIT_OK;}
c2_emit_status c2_session_emit_finalize(uint16_t *n){*n=64;return mode==32?C2_EMIT_OUTPUT:C2_EMIT_OK;}
obj vm_run_dir(int dir,int argc,obj *args){(void)dir;(void)argc;(void)args;++install_calls;vm_status=install_inner_status;return MKFIX(7);}
'''
TAIL=r'''
uint16_t install_result[11];
void install_test(uint8_t old,uint8_t transient,uint8_t m,uint8_t status){
 setup(0,0,0,0);mode=m;steps=rollbacks=ended_state=recovery_calls=bad_valid=0;
 install_calls=begin_calls=end_calls=0;install_inner_status=status;vm_status=VM_OK;c2_phase_owner=0;
 memset(c2_front_certificate,0,sizeof c2_front_certificate);c2_front_begin();c2_front_publish(90);
 c2_runtime.entry_cursor=90;c2_runtime.generation=1;
 obj result=old?old_install(NIL,transient?lisp_t:MKFIX(13)):c2_product_install(NIL,transient?lisp_t:MKFIX(13));
 install_result[0]=(uint16_t)result;install_result[1]=vm_status;install_result[2]=vm_status_error_code(vm_status);
 install_result[3]=install_calls;install_result[4]=c2_runtime.entry_cursor;install_result[5]=c2_front_certificate[2];
 install_result[6]=c2_phase_owner;install_result[7]=c2_ready;install_result[8]=rollbacks;install_result[9]=begin_calls;install_result[10]=end_calls;
}
uint16_t publish_result[3];
void publish_test(uint8_t m,uint8_t loader){
 setup(0,0,0,0);mode=m;steps=rollbacks=0;begin_calls=end_calls=0;vm_status=VM_OK;c2_phase_owner=0;
 memset(c2_front_certificate,0,sizeof c2_front_certificate);c2_runtime.entry_cursor=90;c2_runtime.generation=1;
 obj result=loader?c2_product_append_staged(64):c2_product_publish_staged(64);
 publish_result[0]=(uint16_t)result;publish_result[1]=vm_status;publish_result[2]=vm_status_error_code(vm_status);
}
'''
def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    base=ROOT/'build/set-b-front-span-lifetime-r2/fixture.c';s=base.read_text()
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text();vm=(F.OUT/'candidate/src/vm.c').read_text()
    vh=(ROOT/'src/vm.h').read_text();enum=re.search(r'enum \{\n    VM_OK=0,.*?\};',vh,re.S)[0]
    extra='#include "c2_session_emitter.h"\n#include "error_codes.h"\n'+enum+'\n'+EXTRA
    s=s.replace('/* Controlled seams: no real stage/publication/journal/transport writes. */',extra+'\n/* Controlled seams retained from the previous fixture. */')
    s=s.replace('(void)family;(void)generation;return mode==8?1:0;',
        '(void)family;(void)generation;++begin_calls;return (mode==8 || (mode==33 && begin_calls==2))?1:0;')
    s=s.replace('ended_state=c2_front_certificate[2];return mode==9?1:0;',
        '++end_calls;ended_state=c2_front_certificate[2];return (mode==9 || (mode==34 && end_calls==2))?1:0;')
    s=s.replace('(void)w;sample();++rollbacks;c2_runtime=*c2aw.before;return 1;',
        '(void)w;sample();++rollbacks;if(mode==35)return 0;c2_runtime=*c2aw.before;return 1;')
    names=['c2_product_install','c2_product_append_staged','c2_product_publish_staged']
    functions=[I.function(runtime,n) for n in names]
    functions += [I.function((ROOT/'src/c2_product_runtime.c').read_text(),'c2_product_install').replace('c2_product_install','old_install'),I.function(vm,'vm_status_error_code')]
    for i,f in enumerate(functions):(OUT/f'extracted-{i}.c').write_text(f)
    fixture=OUT/'fixture.c';fixture.write_text(s+'\n'+'\n'.join(functions)+TAIL)
    (OUT/'c2-stream-decoder.h').write_bytes((base.parent/'c2-stream-decoder.h').read_bytes())
    cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(fixture),'-o',str(OUT/'fixture.so')]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert not r.returncode,r.stderr
    d=C.CDLL(str(OUT/'fixture.so'));d.install_test.argtypes=[C.c_uint8]*4;d.publish_test.argtypes=[C.c_uint8]*2
    keys=['result','vm_status','error_code','inner_calls','front','state','owner','ready','rollbacks','begins','ends']
    rows=[];halt=None
    for transient in (0,1):
        for mode in (0,1,2,3,4,5,6,7,8,9,10,30,31,32,33,34,35):
            for status in (0,2,3,5):
                pair=[]
                for old in (1,0):
                    d.install_test(old,transient,mode,status);pair.append(dict(zip(keys,list((C.c_uint16*11).in_dll(d,'install_result')))))
                a,b=pair;ok=all(a[k]==b[k] for k in keys if k!='state')
                # Exact inherited error mapping: never tolerance or a generic non-OK match.
                expected={0:43,2:43,3:38,5:40}[b['vm_status']]
                ok=ok and b['error_code']==expected
                row=dict(kind='installer',transient=transient,mode=mode,inner_status=status,previous=a,candidate=b,pass_gate=ok)
                rows.append(row)
                if not ok:halt=row;break
            if halt:break
        if halt:break
    if not halt:
        for mode in (0,1,2,3,4,5,6,7,8,9):
            for loader in (0,1):
                d.publish_test(mode,loader);got=list((C.c_uint16*3).in_dll(d,'publish_result'))
                expected=[1 if loader else 2,0,43] if mode==0 else ([0,0,43] if loader else [0,5,40] if mode==2 else [0,2,43])
                row=dict(kind='loader-vs-publisher',mode=mode,loader=loader,actual=got,expected=expected,pass_gate=got==expected);rows.append(row)
                if got!=expected:halt=row;break
            if halt:break
    P.write(OUT/'rows.json',rows)
    if halt:P.write(OUT/'halt.json',halt)
    P.write(OUT/'receipt.json',dict(status='HALT EXACT CALLER SUCCESSOR' if halt else 'PASS FULL INSTALLER AND EXACT STATUS MAPPING AT DECLARED SEAMS',
        driver=P.bind(Path(__file__)),execution_head='9013c3fc',base_fixture=P.bind(base),candidate=P.bind(F.OUT/'candidate/src/c2_product_runtime.c'),
        previous=P.bind(ROOT/'src/c2_product_runtime.c'),vm=P.bind(F.OUT/'candidate/src/vm.c'),vm_header=P.bind(ROOT/'src/vm.h'),
        fixture=P.bind(fixture),command=P.bind(OUT/'command.json'),library=P.bind(OUT/'fixture.so'),rows=P.bind(OUT/'rows.json'),
        row_count=len(rows),passing_rows=sum(x['pass_gate'] for x in rows),halt=P.bind(OUT/'halt.json') if halt else None,
        scope='Exact full current and maintained install callers, file/publisher wrappers, status-to-error mapping; emitter/VM/stage/transport seams remain controlled. VM_OK mapping default43 is not an emitted error because callers bypass mapping on OK.',
        limits='No Lisp form execution, evaluator abort presentation, native VM or exact whole-product BAD BYTECODE successor claim.',
        host_c_compiles=1,host_c_links=1,product_builds=0,product_links=0,seeds=0,guest_runs=0,device_contacts=0))
    print('HALT' if halt else 'PASS',len(rows),'caller rows')
if __name__=='__main__':main()
