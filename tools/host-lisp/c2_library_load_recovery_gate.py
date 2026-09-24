"""Execute consumed D1 and the native append driver before a product build.

Transport and later transaction phases are fault-injection seams, not a native
latency or hardware proof. Envelope validation and the resident driver's
branches are compiled verbatim from the product sources.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=ROOT / 'build/c2-library-load-recovery-gate')
OUT = parser.parse_args().out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
SRC = ROOT / 'src/c2_product_runtime.c'
GEN = ROOT / 'tools/host-lisp/c2_lite_v6_product_probe.py'

def function(text, name):
    starts = list(re.finditer(r'(?m)^.*\b' + name + r'\([^;]*?\)\s*\{', text))
    assert len(starts) == (2 if name == 'c2_append_begin' else 1), (name, len(starts))
    start = starts[-1].start(); brace = text.index('{', start); depth = 0
    if name == 'c2_append_begin':
        return text[start:text.index('\n#endif\n\nstatic uint8_t c2_append_rollback', start)]
    for end in range(brace, len(text)):
        depth += (text[end] == '{') - (text[end] == '}')
        if not depth:
            return text[start:end+1]
    raise AssertionError(name)

raw = SRC.read_text()
fold = function(raw, 'c2_library_name_fold')
generic = function(raw, 'c2_product_static_image_named')
generated = [n.args[2].value for n in ast.walk(ast.parse(GEN.read_text()))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'replace_c_function' and len(n.args) == 3
             and isinstance(n.args[1], ast.Constant)
             and n.args[1].value == 'c2_product_static_image_named']
assert len(generated) == 1
name_header = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef const char *obj;
#define IS_PTR(p) ((p)!=0)
#define T_STR 1
#define cell_type(p) 1
#define str_len(p) strlen(p)
#define str_byte(p,i) ((uint8_t)(p)[i])
static uint8_t c2_ready = 1;
static struct { uint8_t image_count; } c2_runtime = {6};
static const char *names[] = {"stdlib", "ide", "idex", "m65d", "buffer", "lcc"};
static int c2_stream_shelf_read(uint32_t at, void *p, uint16_t n) {
    memset(p,0,n); strcpy(p,names[(at-32)/32]); return 1;
}
'''
name_main = r'''
int main(void) {
    char text[32]; unsigned i,j,mode;
    for (i=0;i<256;i++) {
        unsigned expected=i & 127;
        if (expected>=97 && expected<=122) expected-=32;
        assert(c2_library_name_fold(i)==expected);
    }
    for(i=0;i<6;i++) for(mode=0;mode<4;mode++) {
        strcpy(text,names[i]);
        for(j=0;text[j];j++) {
            if((mode==1 || (mode==2 && !(j&1))) && text[j]>='a' && text[j]<='z') text[j]-=32;
            if(mode==3) text[j]=(uint8_t)text[j]|128;
        }
        assert(c2_product_static_image_named(text));
        strcat(text,"!"); assert(!c2_product_static_image_named(text));
    }
    assert(!c2_product_static_image_named(""));
    assert(!c2_product_static_image_named("missing"));
    c2_ready=0; assert(!c2_product_static_image_named("IDE"));
    return 0;
}
'''

begin = function(raw, 'c2_append_begin')
envelope = function(raw, 'c2_append_envelope_phase')
slots = sorted(set(re.findall(r'\bLISP65_C2_\w+_SLOT\b', begin + envelope)))
defines = ['LISP65_C2_NESTED_APPEND_V5', 'LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT',
           'LISP65_C2_LITE_V6_SEMANTIC_SPLITS', 'LISP65_C2_LITE_COLD_EVICTION',
           'LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT']
header = '\n'.join('#define '+x+' 1' for x in defines)
header += '\n' + '\n'.join('#define '+x+' '+str(i+1) for i,x in enumerate(slots))
capacity_defines = re.findall(
    r'^#define C2_APPEND_(?:BEGIN_CAPACITY|CAPACITY_CAUSE) .+$', raw, re.M)
assert len(capacity_defines) == 2, 'append capacity cause/result population drift'
header += '\n' + '\n'.join(capacity_defines)
header += r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#define C2_KERNAL_RESIDENT
#define C2_APPEND_SECTION(s)
#define C2_INSTALL_TRACE_STAMP_SLOT(s)
#define C2_FRAME_ATTRIBUTION_STAMP(s)
#define LISP65_C2_PHASE_OWNER_APPEND 1
#define LISP65_C2_PRODUCT_BUILD_ID 0x68ad02e6UL
#define C2_STREAM_OK 0
#define C2_STREAM_ERR_STATE 1
#define C2_STREAM_ERR_C2I 2
#define C2D_HANDLE_CAP 64
#define C2D_ENTRY_CAP 2048
#define C2D_ROOT_CAP 1536
#define NIL 0
#define C2_APPEND_FLAG_TRANSIENT 1
#define C2J_RESULT_NONE 0
#define C2_ROOTS_REQUEST_MARK 1
#define C2_FRONTS_REQUEST_MARK 2
#define C2_RESERVE_SCAN_REQUEST 3
#define C2_COMPLETION_PUBLISH_MARK 4
#define C2_CLEAR_REQUEST_MARK 5
typedef struct { uint16_t entry_first; uint8_t error; } c2_stream_context;
typedef struct {
 c2_stream_context *before, append; uint16_t *main_ordinal;
 uint16_t length,code_off,code_len,meta_off,meta_len,new_roots,new_entries,entries;
 uint8_t staged,committed,rollback_rebuild_header,record[32];
 uint8_t journal,completion,roots_fronts,reserve,publish_clear;
} c2_append_state;
#define C2AW_JOURNAL_RESULT(w) ((w)->journal)
#define C2AW_COMPLETION_MARK(w) ((w)->completion)
#define C2AW_ROOTS_FRONTS_MARK(w) ((w)->roots_fronts)
#define C2AW_RESERVE_MARK(w) ((w)->reserve)
#define C2AW_PUBLISH_CLEAR_MARK(w) ((w)->publish_clear)
static c2_append_state c2aw;
static c2_stream_context c2_runtime, *c2_decode_active;
static uint8_t c2_ready, c2_journal_count;
static uint16_t c2_pending_roots;
static uint8_t bytes[8192];
static int call_no,fail_at,rollback_calls,stage_calls,releases,world,capacity_fault;
static uint8_t ext_disk_get(uint16_t at) { assert(at>=256); return bytes[at-256]; }
static uint16_t c2_stage_u16(uint16_t at) { return bytes[at]|(uint16_t)bytes[at+1]<<8; }
static uint32_t c2_stage_u24(uint16_t at) { return c2_stage_u16(at)|(uint32_t)bytes[at+2]<<16; }
static uint32_t c2_stage_u32(uint16_t at) { return c2_stage_u24(at)|(uint32_t)bytes[at+3]<<24; }
static int c2_phase_scratch_acquire(int owner) { (void)owner; return 1; }
static int c2_phase_scratch_release(int owner) { (void)owner; releases++; return 1; }
'''
seams = r'''
static int check(void) {
 if (++call_no != fail_at) return 1;
 if (capacity_fault) c2aw.append.error=C2_APPEND_CAPACITY_CAUSE;
 return 0;
}
static int c2_overlay_call_range(int first,int last,void *p) {
 (void)last;
 if(first==LISP65_C2_APPEND_ENVELOPE_SLOT && c2_append_envelope_phase(p)!=C2_STREAM_OK) return 0;
 return check();
}
static int c2_overlay_call(int slot,void *p) { (void)slot;(void)p;return check(); }
static int c2_append_run_stage_plan(void *p) {
 (void)p; stage_calls++; world=17; return check();
}
static int c2_append_run_rollback_plan(void *p) {
 (void)p; rollback_calls++;
 /* Unprepared rollback must remain an error, never silently succeed. */
 if(!stage_calls) return 0;
 world=9; return 1;
}
static int c2_decode_from(void *p,int phase) { (void)p;(void)phase;return check(); }
static int c2_append_run_persistent_publish_plan(void *p) { (void)p;return check(); }
'''
main = r'''
static void put(uint16_t at,uint32_t v,int n) { while(n--) {bytes[at++]=v;v>>=8;} }
static void reset(void) {
 memset(&c2aw,0xa5,sizeof c2aw); memset(bytes,0,sizeof bytes);
 c2_ready=1; world=9; call_no=stage_calls=rollback_calls=releases=0; fail_at=capacity_fault=0;
 memcpy(bytes,"L65S",4); bytes[4]=4;bytes[5]=32;bytes[6]=32;bytes[7]=1;
 put(8,32,2);put(10,64,3);put(13,88,3);put(16,32,2);
 put(22,LISP65_C2_PRODUCT_BUILD_ID,4);put(26,1,2);
 memcpy(bytes+32,"SESS",4);bytes[62]=1;
 put(40,64,3);put(43,0,2); /* filled below: smallest envelope needs one code byte */
 put(43,1,2);put(45,65,3);put(48,24,2);put(13,89,3);
}
int main(void) {
 c2_stream_context before; uint16_t ordinal; unsigned i;
 const uint16_t invalid_lengths[]={0,87,8193,34723,65535};
 for(i=0;i<sizeof invalid_lengths/sizeof *invalid_lengths;i++) {
   reset();assert(!c2_append_begin(invalid_lengths[i],&before,&ordinal,0));
   assert(c2_ready && world==9 && !stage_calls && !rollback_calls && releases==1);
 }
 for(i=0;i<8;i++) {
   reset();bytes[i]^=1;
   assert(!c2_append_begin(89,&before,&ordinal,0));
   assert(c2_ready && world==9 && !stage_calls && !rollback_calls && releases==1);
 }
 /* Every pre-stage transport/validation rejection preserves the world. */
 for(i=1;i<=5;i++) {
   reset();fail_at=i; assert(!c2_append_begin(89,&before,&ordinal,0));
   assert(c2_ready && world==9 && !stage_calls && !rollback_calls && releases==1);
 }
 /* Once stage has started, the exact old rollback contract remains active. */
 for(i=6;i<=10;i++) {
   reset();fail_at=i; assert(!c2_append_begin(89,&before,&ordinal,0));
   assert(c2_ready && world==9 && stage_calls==1 && rollback_calls==1 && releases==1);
 }
 reset(); assert(c2_append_begin(89,&before,&ordinal,0));
 assert(c2_ready && world==17 && stage_calls==1 && !rollback_calls && releases==1);
 return 0;
}
'''

def run(name, code, passes=True):
    source = OUT / (name+'.c'); binary = OUT/name
    source.write_text(code)
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-function',
                    '-Wno-unused-variable','-O0',str(source),'-o',str(binary)],check=True)
    result = subprocess.run([str(binary)],capture_output=True)
    assert (result.returncode==0)==passes, (name,result.returncode,result.stderr.decode())
    return {'name':name,'exit_code':result.returncode,'expected_pass':passes,
            'source_sha256':hashlib.sha256(code.encode()).hexdigest()}

rows=[]
for name, body in [('generic',generic),('consumed',generated[0])]:
    rows.append(run('names-'+name,name_header+fold+body+name_main))
    old = body.replace('c2_library_name_fold(record[i])','record[i]').replace(
        'c2_library_name_fold((uint8_t)names[at + i])','(uint8_t)names[at + i]').replace(
        'c2_library_name_fold(str_byte(name, i))','str_byte(name, i)')
    assert old != body
    rows.append(run('names-'+name+'-case-sensitive',name_header+fold+old+name_main,False))
rows.append(run('append-reject',header+envelope+seams+begin+main))
capacity_main = main.replace(' return 0;\n}', '''
 reset();fail_at=5;capacity_fault=1;
 assert(c2_append_begin(89,&before,&ordinal,0)==C2_APPEND_BEGIN_CAPACITY);
 assert(c2_ready && world==9 && !stage_calls && !rollback_calls && releases==1);
 return 0;
}''')
assert capacity_main != main
rows.append(run('append-capacity',header+envelope+seams+begin+capacity_main))
old_capacity = begin.replace('? C2_APPEND_BEGIN_CAPACITY : 0u', '? 0u : 0u')
assert old_capacity != begin
rows.append(run('append-capacity-as-generic-reject',
                header+envelope+seams+old_capacity+capacity_main,False))
old=function(subprocess.check_output(['git','show','412454ec:src/c2_product_runtime.c'],
                                    cwd=ROOT,text=True),'c2_append_begin')
rows.append(run('append-old-rollback',header+envelope+seams+old+main,False))
(OUT/'host-proof.json').write_text(json.dumps({
    'authority':'412454ec','status':'PASS','rows':rows,
    'sources':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in (SRC,GEN,Path(__file__))],
    'claim_boundary':'Compiled source branch/domain proof with fault-injected transport; native world equality and timing remain seed obligations.',
    'budget':{'seed':0,'final':0,'link':0}},indent=2)+'\n')
print('PASS: D1 domains and D2 pre-stage rejection; both old forms fail')
