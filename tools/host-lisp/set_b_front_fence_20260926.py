"""Actual completion predicate: content checks and ordered-write ownership boundary."""
from pathlib import Path
import ctypes as C
import re,subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_integration_r2_20260926 as I
ROOT=P.ROOT;OUT=ROOT/'build/set-b-front-fence-r1'
TAIL=r'''
uint16_t fence_result[9];
uint8_t data_before[16],data_expected[16],data_after[16];
void fence_test(uint8_t mode,uint8_t mutation,uint8_t read_failure,uint8_t partial){
 writer_setup(0,0,0,0,0);work.length=64;work.attic=256;
 /* Valid persistent C2J envelope; only the tested predicate consumes it. */
 work.old_images=6;work.new_images=7;
 uint8_t status=c2_append_journal_write_phase(&work);
 uint8_t expected[48];memcpy(expected,work.old_header,48);
 if(mode==C2_COMPLETION_PUBLISH_MARK)memcpy(arena,expected,48);
 if(mode==C2_COMPLETION_CLEAR_MARK)memset(arena+C2D_UNWIND_BASE,0,64);
 uint16_t target=mode==C2_COMPLETION_PUBLISH_MARK?0:C2D_UNWIND_BASE;
 if(mutation==1)arena[target]^=1;
 if(mutation==2)C2AW_C2J_SEAL_BYTES(&work)[0]^=1;
 reads=0;fault_read=read_failure;copy_mode=partial;
 uint8_t ok=c2_completion_poll(&work,mode,mode==C2_COMPLETION_PUBLISH_MARK?expected:0);
 fence_result[0]=status;fence_result[1]=ok;fence_result[2]=reads;
 fence_result[3]=work.committed;fence_result[4]=bounds_errors;fence_result[5]=C2AW_JOURNAL_RESULT(&work);
 fence_result[6]=rtov_crc_mem(arena+C2D_UNWIND_BASE,64);fence_result[7]=C2AW_C2J_SEAL(&work);fence_result[8]=c2_runtime.entry_cursor;
}
void pending_write_test(void){
 writer_setup(0,0,0,0,0);work.length=64;work.attic=256;work.old_images=6;work.new_images=7;
 uint8_t status=c2_append_journal_write_phase(&work);
 uint8_t active=c2_completion_poll(&work,C2_COMPLETION_ACTIVE_MARK,0);
 /* Abstract outstanding earlier job. The selected CPU-read seam observes
    current memory and does not itself submit/drain a DMA queue. No real DMA. */
 memcpy(data_before,arena+2116,16);memset(data_expected,0,16);
 /* Half of the intended zero write is visible; the rest is still pending. */
 memset(arena+2116,0,8);reads=0;
 uint8_t barrier=c2_completion_poll(&work,C2_COMPLETION_ROLLBACK_MARK,0);
 memcpy(data_after,arena+2116,16);
 fence_result[0]=status;fence_result[1]=active;fence_result[2]=barrier;fence_result[3]=reads;
 fence_result[4]=memcmp(data_after,data_expected,16)==0;fence_result[5]=8;
 fence_result[6]=rtov_crc_mem(arena+C2D_UNWIND_BASE,64);fence_result[7]=C2AW_C2J_SEAL(&work);fence_result[8]=work.committed;
}
'''
def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text();maintained=(ROOT/'src/c2_product_runtime.c').read_text()
    base=ROOT/'build/set-b-front-paths-writers-r3/fixture.c';s=base.read_text()
    stub=I.function(s,'c2_completion_poll');s=s.replace(stub,'static uint8_t c2_completion_poll(c2_append_state*,uint8_t,const uint8_t*);\n')
    names=['C2D_UNWIND_BASE','C2D_UNWIND_BYTES','C2_APPEND_FLAG_TRANSIENT','C2AW_C2J_SEAL','C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES']
    macros='\n#define c2aw work\n#define C2_JOURNAL_WRITE_ENTRY\n#define C2_C1_COMPLETION_WITNESS8(a,b) ((void)0)\n'
    for name in names:
        if re.search(r'^#define '+name+r'\b',s,re.M):continue
        macros+=re.search(r'^#define '+name+r'\b[^\n]*',runtime,re.M)[0]+'\n'
    vh=(ROOT/'src/vm_runtime_overlay.h').read_text()
    for name in ('LISP65_RUNTIME_OVERLAY_CRC16_INIT','LISP65_RUNTIME_OVERLAY_CRC16_POLY'):
        macros+=re.search(r'^#define '+name+r'\b[^\n]*',vh,re.M)[0]+'\n'
    def extract(src,name):
        if name=='rtov_crc_mem':src=src[src.index('C2_APPEND_INLINE uint16_t rtov_crc_mem'):]
        if name=='c2_completion_mode_length':src=src[src.index('C2_APPEND_INLINE uint8_t c2_completion_mode_length'):]
        return I.function(src,name)
    names=['rtov_crc_mem','c2_record_u32','c2j_crc32','c2_completion_bytes_equal','c2_completion_c2j_matches','c2_completion_mode_length','c2_completion_poll','c2_append_journal_write_phase']
    functions=[]
    for name in names:
        f=extract(runtime,name);assert f==extract(maintained,name),name
        functions.append(f);(OUT/(name+'.c')).write_text(f)
    fixture=OUT/'fixture.c';fixture.write_text(s+macros+'\n'.join(functions)+TAIL)
    (OUT/'c2-stream-decoder.h').write_bytes((base.parent/'c2-stream-decoder.h').read_bytes())
    cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(fixture),'-o',str(OUT/'fixture.so')]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert not r.returncode,r.stderr
    d=C.CDLL(str(OUT/'fixture.so'));d.fence_test.argtypes=[C.c_uint8]*4
    rows=[];halt=None
    for mode in (0xa1,0xa2,0xa3,0xa4,0,0xa5):
        for mutation in (0,1,2):
            for fail in (0,1):
                for part in ((0,) if not fail else (0,1,2)):
                    d.fence_test(mode,mutation,fail,part);got=list((C.c_uint16*9).in_dll(d,'fence_result'))
                    valid=0xa1<=mode<=0xa4
                    expect=int(valid and not fail and mutation!=1 and (mutation!=2 or mode in (0xa2,0xa4)))
                    ok=got[0]==0 and got[1]==expect and got[2]==int(valid) and got[3:5]==[0,0]
                    row=dict(kind='content-predicate',mode=mode,mutation=mutation,read_failure=fail,partial=part,actual=got,expected_accept=expect,pass_gate=ok);rows.append(row)
                    if not ok:halt=row;break
                if halt:break
            if halt:break
        if halt:break
    if not halt:
        d.pending_write_test();got=list((C.c_uint16*9).in_dll(d,'fence_result'))
        row=dict(kind='outstanding-earlier-write-boundary',actual=got,
            before=bytes((C.c_uint8*16).in_dll(d,'data_before')).hex(),expected=bytes((C.c_uint8*16).in_dll(d,'data_expected')).hex(),
            after=bytes((C.c_uint8*16).in_dll(d,'data_after')).hex(),
            predicate_accepts=got[2]==1,prior_write_complete=got[4]==1,
            contract_requires='An independently bound ordering guarantee must exclude this state; the predicate alone cannot prove prior-write completion.',
            scope='Synthetic pending-write/CPU-read visibility schedule, not a hardware-faithful DMA engine or executed full publication.',pass_gate=False)
        assert got[:6]==[0,1,1,1,0,8] and got[6]==got[7] and got[8]==0
        rows.append(row);halt=row
    P.write(OUT/'rows.json',rows);P.write(OUT/'halt.json',halt)
    P.write(OUT/'receipt.json',dict(status='HALT: PRIOR-WRITE ORDERING NOT ESTABLISHED BY CONTENT PREDICATE',
        driver=P.bind(Path(__file__)),execution_head='5b401d68',source=P.bind(F.OUT/'candidate/src/c2_product_runtime.c'),maintained=P.bind(ROOT/'src/c2_product_runtime.c'),
        base_fixture=P.bind(base),fixture=P.bind(fixture),command=P.bind(OUT/'command.json'),library=P.bind(OUT/'fixture.so'),rows=P.bind(OUT/'rows.json'),
        halt=P.bind(OUT/'halt.json'),row_count=len(rows),passing_rows=sum(x['pass_gate'] for x in rows),
        scope='Eight exact unchanged completion/journal helpers; host parity CRC/length/timeout bodies. Real predicate over bounded memory; selected reader semantics synchronous snapshot.',
        interpretation='A matching already-active journal cannot by its own bytes establish completion of another address. The older contract obtains ordering from a trailing same-engine DMA read; active profile instead selects MAP/CPU. Missing transport proof, not a demonstrated shipped data-corruption defect.',
        stopped_before=['full replay-driver integration','full publication/rollback successor','any repair or native/product attempt'],
        host_c_compiles=1,host_c_links=1,product_builds=0,product_links=0,seeds=0,guest_runs=0,device_contacts=0))
    print('HALT prior-write ordering;',len(rows)-1,'content rows pass; actual predicate accepts with8 pending bytes; no full publication claimed')
if __name__=='__main__':main()
