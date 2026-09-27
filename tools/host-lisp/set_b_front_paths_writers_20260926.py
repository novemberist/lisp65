"""Actual entry/header/unpublish/wipe C against bounded memory transports."""
from pathlib import Path
import ctypes as C
import re,subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_integration_r2_20260926 as I
ROOT=P.ROOT;OUT=ROOT/'build/set-b-front-paths-writers-r3'
PRE=r'''
#include <stdint.h>
#include <string.h>
#include "c2-stream-decoder.h"
#include "c2d_v6_entry.h"
#define C2_APPEND_INLINE static
#define C2_APPEND_SECTION(x)
#define C2TR_BODY_USED
#define C2_INSTALL_TRACE_STAMP_SLOT(x) ((void)0)
#define C2_INSTALL_TRACE_LOCK_PRIMARY() ((void)0)
#define C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(x) ((void)0)
#define C2_FRAME_ATTRIBUTION_STAMP(x) ((void)0)
#define C2_C1_FREEZER_HOLD(x) ((void)0)
#define C2_C1_FREEZER_HOLD_STATE_PROVEN(x) ((void)0)
typedef int16_t obj;
static uint16_t c2_u16(const uint8_t*p){return p[0]|((uint16_t)p[1]<<8);}
static uint32_t c2_u24(const uint8_t*p){return c2_u16(p)|((uint32_t)p[2]<<16);}
static c2_stream_context c2_runtime,*c2_decode_active,before;
static uint16_t c2_journal_count,c2_pending_roots,c2_committed_roots;
uint8_t arena[65536],checkpoint[65536],source[1024];
uint16_t writes,reads,polls,bounds_errors,write_at[64],write_len[64];
static uint16_t fault_write,fault_read,fault_poll;
static uint8_t copy_mode;
uint8_t c2_stream_c2d_write(uint16_t at,const void*src,uint16_t n){
 if(n>65536u-(uint32_t)at){++bounds_errors;return 0;}
 if(writes<64){write_at[writes]=at;write_len[writes]=n;}++writes;
 if(writes==fault_write){memcpy(arena+at,src,copy_mode==2?n:copy_mode==1?n/2:0);return 0;}
 memcpy(arena+at,src,n);return 1;
}
uint8_t c2_stream_c2d_read(uint16_t at,void*dst,uint16_t n){
 if(n>65536u-(uint32_t)at){++bounds_errors;return 0;}++reads;
 if(reads==fault_read){memcpy(dst,arena+at,copy_mode==2?n:copy_mode==1?n/2:0);return 0;}
 memcpy(dst,arena+at,n);return 1;
}
static uint8_t ext_disk_get(uint16_t at){if(at>=1024){++bounds_errors;return 0;}return source[at];}
static void set_sym_function(obj a,obj b){(void)a;(void)b;++bounds_errors; /* no exports in this fixture */}
'''
SEAMS=r'''
static c2_append_state work;
static uint8_t c2_completion_poll(c2_append_state*w,uint8_t mode,const uint8_t*header){
 (void)w;(void)mode;(void)header;return ++polls!=fault_poll;
}
'''
TAIL=r'''
uint16_t writer_result[12];
void writer_setup(uint8_t transient,uint16_t fw,uint16_t fr,uint16_t fp,uint8_t partial){
 memset(arena,0xa5,sizeof arena);memset(source,0,sizeof source);memset(&work,0,sizeof work);
 memset(&c2_runtime,0,sizeof c2_runtime);writes=reads=polls=bounds_errors=0;
 memset(write_at,0,sizeof write_at);memset(write_len,0,sizeof write_len);
 fault_write=fw;fault_read=fr;fault_poll=fp;copy_mode=partial;
 c2_runtime.generation=1;c2_runtime.images_offset=48;c2_runtime.entries_offset=2096;
 c2_runtime.resolutions_offset=22576;c2_runtime.roots_offset=30768;
 c2_runtime.image_count=2;c2_runtime.entry_count=2;c2_runtime.resolution_count=2;c2_runtime.c2_root_count=2;
 c2_runtime.entry_first=C2D_HANDLE_CAP;c2_runtime.entry_cursor=114;before=c2_runtime;
 work.before=&before;work.staged=1;work.entries=2;work.literals=2;work.roots=2;
 work.old_images=2;work.old_entries=transient?2048:2;work.old_res=transient?4096:2;work.old_roots=transient?1536:2;
 work.new_images=transient?63:3;work.new_entries=transient?2046:4;
 work.new_res=transient?4094:4;work.new_roots=transient?1534:4;
 work.rollback_rebuild_header=transient?C2_APPEND_FLAG_TRANSIENT:0;
 c2_record_u16(work.record+28,transient?60000:114);c2_record_u16(work.record+12,114);
 memset(work.old_header,0,sizeof work.old_header);memcpy(work.old_header,"C2D",3);work.old_header[4]=6;
 c2_header_watermark(work.old_header,4096);c2_record_u16(work.old_header+10,1);
 c2_header_counts(work.old_header,2,2,2,2);memcpy(arena,work.old_header,48);
 c2_pending_roots=c2_committed_roots=2;c2_journal_count=0;
 for(uint8_t i=0;i<2;++i){uint8_t*e=source+256+24+i*16;c2_record_u16(e,i*7);c2_record_u16(e+3,7);c2_record_u16(e+5,i);e[7]=1;}
}
void writer_run(uint8_t op){
 uint8_t result=0;
 if(op==0){memcpy(checkpoint,arena,sizeof arena);result=c2_append_entries_phase(&work);}
 else{
   /* Reach the selected phase from a complete prepared append context. */
   work.append=c2_runtime;work.append.finished=1;work.append.entry_cursor=128;
   work.append.image_count=3;work.append.entry_count=4;work.append.resolution_count=4;work.append.c2_root_count=4;
   C2AW_JOURNAL_RESULT(&work)=C2J_RESULT_ACTIVE;C2AW_COMPLETION_MARK(&work)=C2_COMPLETION_PUBLISH_MARK;
   if(op==1){memcpy(checkpoint,arena,sizeof arena);result=c2_append_header_phase(&work);}
   else{
     work.committed=1;
     if(C2AW_TRANSIENT(&work)){c2_runtime.entry_first=4094;c2_header_watermark(arena,4094);}
     else{c2_runtime=work.append;c2_header_counts(arena,3,4,4,4);}
     memcpy(checkpoint,arena,sizeof arena);
     if(op==2)result=c2_append_rollback_unpublish_phase(&work);
     if(op==3)result=c2_append_rollback_wipe_plane_phase(&work);
     if(op==4)result=c2_append_rollback_finalize_phase(&work);
   }
 }
 writer_result[0]=result;writer_result[1]=c2_runtime.entry_cursor;writer_result[2]=c2_runtime.entry_count;
 writer_result[3]=c2_runtime.entry_first;writer_result[4]=work.committed;writer_result[5]=work.append.phase;
 writer_result[6]=work.append.entry_cursor;writer_result[7]=c2_pending_roots;writer_result[8]=c2_committed_roots;
 writer_result[9]=writes;writer_result[10]=reads;writer_result[11]=polls;
}
'''
def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text()
    native=P.load(ROOT/'build/set-b-front-span-native-r1/commands.json')
    defines=[x[2:] for x in native[0]['command'] if x.startswith('-D')]
    profile=''.join('#define '+x.replace('=',' ',1)+('' if '=' in x else ' 1')+'\n' for x in defines)
    struct=runtime[runtime.index('typedef struct __attribute__((may_alias)) {'):runtime.index('} c2_append_state;')+len('} c2_append_state;')]
    macro_names=['C2D_HANDLE_CAP','C2D_ENTRY_CAP','C2D_ROOT_CAP','C2_APPEND_FLAG_TRANSIENT','C2AW_TRANSIENT',
        'C2AW_CHIP_CODE_BASE','C2AW_JOURNAL_RESULT','C2AW_COMPLETION_MARK','C2AW_C2J_SEAL_BYTES',
        'C2J_RESULT_NONE','C2J_RESULT_PREPARED','C2J_RESULT_ACTIVE','C2_COMPLETION_ACTIVE_MARK',
        'C2_COMPLETION_PUBLISH_MARK','C2_COMPLETION_ROLLBACK_MARK','C2_COMPLETION_CLEAR_MARK','C2_EXPORT_JOURNAL_BASE','C2_EXPORT_JOURNAL_RECORD_BYTES']
    macros='\n'.join(re.search(r'^#define '+n+r'\b[^\n]*',runtime,re.M)[0] for n in macro_names)+'\n#define LISP65_C2D_BYTES 33840u\n'
    names=['c2_record_u16','c2_header_watermark','c2_header_counts','c2_append_entries_phase','c2_append_header_phase',
        'c2_append_restore_exports','c2_append_rollback_unpublish_phase','c2_append_rollback_zero_plane',
        'c2_append_rollback_wipe_plane_phase','c2_append_rollback_finalize_phase']
    def extract(s,n):
        if n=='c2_header_watermark':s=s[s.index('C2_APPEND_INLINE void c2_header_watermark'):]
        return I.function(s,n)
    functions=[extract(runtime,n) for n in names]
    for n,f in zip(names,functions):
        assert f==extract((ROOT/'src/c2_product_runtime.c').read_text(),n),n
        (OUT/(n+'.c')).write_text(f)
    fixture=OUT/'fixture.c';fixture.write_text(profile+PRE+struct+'\n'+macros+SEAMS+'\n'.join(functions)+TAIL)
    (OUT/'c2-stream-decoder.h').write_bytes((ROOT/'config/set-b-native/includes/c2-stream-decoder.h').read_bytes())
    cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I'+str(OUT),'-I'+str(ROOT/'src'),str(fixture),'-o',str(OUT/'fixture.so')]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert not r.returncode,r.stderr
    d=C.CDLL(str(OUT/'fixture.so'));d.writer_setup.argtypes=[C.c_uint8,C.c_uint16,C.c_uint16,C.c_uint16,C.c_uint8];d.writer_run.argtypes=[C.c_uint8]
    keys=['status','front','entry_count','watermark','committed','pending_phase','pending_front','pending_roots','committed_roots','writes','reads','polls']
    rows=[];halt=None
    def run(t,op,fw=0,fr=0,fp=0,partial=0):
        d.writer_setup(t,fw,fr,fp,partial);d.writer_run(op);before=bytes((C.c_uint8*65536).in_dll(d,'checkpoint'))
        after=bytes((C.c_uint8*65536).in_dll(d,'arena'));v=dict(zip(keys,list((C.c_uint16*12).in_dll(d,'writer_result'))))
        ats=list((C.c_uint16*64).in_dll(d,'write_at'));ns=list((C.c_uint16*64).in_dll(d,'write_len'))
        changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
        return dict(transient=t,op=op,fault_write=fw,fault_read=fr,fault_poll=fp,partial=partial,actual=v,
            writes=list(zip(ats[:v['writes']],ns[:v['writes']])),changed_bytes=changed,bounds_errors=C.c_uint16.in_dll(d,'bounds_errors').value),before,after
    for t in (0,1):
        for op in range(5):
            base,_,after=run(t,op);v=base['actual']
            spans=([(2096+(2046 if t else 2)*10,20)] if op==0 else [(0,48)] if op in (1,2,4) else
                [(48+(63 if t else 2)*32,32),(2096+(2046 if t else 2)*10,20),(22576+(4094 if t else 2)*2,4),(30768+(1534 if t else 2)*2,4)])
            ok=v['status']==0 and not base['bounds_errors'] and all(any(a<=i<a+n for a,n in spans) for i in base['changed_bytes'])
            if op==0:
                expected=b''.join(bytes([63 if t else 2,1])+int((60000 if t else 114)+i*7).to_bytes(2,'little')+b'\x07\x00'+int((4094 if t else 2)+i).to_bytes(2,'little')+b'\x01\x00' for i in range(2))
                ok=ok and after[spans[0][0]:spans[0][0]+20]==expected and v['pending_phase']==4
            if op==1:ok=ok and v['front']==(114 if t else 128) and v['entry_count']==(2 if t else 4) and v['watermark']==(4094 if t else 4096)
            if op==2:ok=ok and v['front']==114 and v['entry_count']==2 and v['watermark']==4096
            if op==3:ok=ok and all(after[a:a+n]==bytes(n) for a,n in spans)
            base['pass_gate']=ok;base['allowed_write_spans']=spans;rows.append(base)
            if not ok:halt=base;break
            for kind,count in (('write',v['writes']),('read',v['reads']),('poll',v['polls'])):
                for index in range(1,count+1):
                    for partial in (0,1,2):
                        kw={'f'+{'write':'w','read':'r','poll':'p'}[kind]:index,'partial':partial}
                        row,_,_=run(t,op,**kw);a=row['actual'];ok=a['status']==1 and not row['bounds_errors']
                        if op==1:ok=ok and a['front']==114 and a['entry_count']==2 and a['committed']==0
                        ok=ok and a[{'write':'writes','read':'reads','poll':'polls'}[kind]]==index
                        row['pass_gate']=ok;rows.append(row)
                        if not ok:halt=row;break
                    if halt:break
                if halt:break
            if halt:break
        if halt:break
    P.write(OUT/'rows.json',rows)
    if halt:P.write(OUT/'halt.json',halt)
    P.write(OUT/'receipt.json',dict(status='HALT REAL WRITER SUCCESSOR' if halt else 'PASS EXACT ENTRY HEADER UNPUBLISH AND PLANE-WIPE C',
        driver=P.bind(Path(__file__)),execution_head='9013c3fc',source=P.bind(F.OUT/'candidate/src/c2_product_runtime.c'),
        native_profile=P.bind(ROOT/'build/set-b-front-span-native-r1/commands.json'),fixture=P.bind(fixture),command=P.bind(OUT/'command.json'),
        library=P.bind(OUT/'fixture.so'),rows=P.bind(OUT/'rows.json'),row_count=len(rows),passing_rows=sum(x['pass_gate'] for x in rows),halt=P.bind(OUT/'halt.json') if halt else None,
        scope='Ten exact functions equal to maintained source. Real transaction struct fields under host ABI; real entry serializer. Bounded64KiB memory/read/write faults and completion-poll seam; no actual DMA or native scratch alias/layout.',
        limits='Prepared phase inputs; no full stage/journal/overlay chain, code/attic DMA wipe or native execution. Partial physical writes on failure remain rollback obligations.',
        host_c_compiles=1,host_c_links=1,product_builds=0,product_links=0,seeds=0,guest_runs=0,device_contacts=0))
    print('HALT' if halt else 'PASS',len(rows),'writer rows')
if __name__=='__main__':main()
