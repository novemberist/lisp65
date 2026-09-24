"""Execute extracted Set-A reservation and API bodies; no product build.

This proves C field semantics and typed API behavior, not native transport,
struct layout, whole append atomicity or device recovery.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def body(source, signature):
    start = source.index(signature)
    end = source.index('\n}', start) + 2
    return source[start:end]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    out = ap.parse_args().out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = (ROOT / 'src/c2_product_runtime.c').read_text()
    macros = []
    for line in source.splitlines():
        if re.match(r'#define (C2D_IMAGE_CAP |C2_APPEND_BEGIN_|C2_APPEND_CAPACITY_CAUSE |'
                    r'C2_APPEND_FLAG_TRANSIENT |C2AW_TRANSIENT\(|C2AW_FRONT_\w+\(|'
                    r'C2AW_RESERVE_MARK\(|C2_RESERVE_\w+ )', line):
            macros.append(line)
    bodies = '\n'.join(body(source, signature) for signature in (
        'uint8_t c2_append_reserve_persistent_bounds_phase(void *opaque)',
        'uint8_t c2_append_reserve_persistent_code_phase(void *opaque)',
        'uint8_t c2_product_append_staged(uint16_t length)',
        'obj c2_product_publish_staged(uint16_t length)'))
    prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "vm.h"
enum { C2_STREAM_OK=0, C2_STREAM_ERR_C2D=3, C2_STREAM_ERR_STATE=8 };
#define C2_INSTALL_TRACE_STAMP_SLOT(x) ((void)0)
typedef struct {
    struct { uint8_t error; } append;
    uint16_t length, code_len, entries, literals, roots;
    uint16_t old_images, old_entries, old_res, old_roots;
    uint16_t new_images, new_entries, new_res, new_roots;
    uint32_t attic;
    uint8_t record[32], rollback_rebuild_header;
} c2_append_state;
static struct {uint16_t image_count, entry_count, resolution_count, c2_root_count;} c2_runtime;
static uint32_t watermark;
static uint8_t scan_ok=1, append_result;
uint8_t vm_status;
obj lisp_t=2;
static uint16_t c2_u16(const uint8_t *p){return p[0]|(uint16_t)p[1]<<8;}
static uint32_t c2_u32(const uint8_t *p){return c2_u16(p)|(uint32_t)c2_u16(p+2)<<16;}
static void c2_record_u16(uint8_t *p,uint16_t v){p[0]=v;p[1]=v>>8;}
static void c2_record_u32(uint8_t *p,uint32_t v){c2_record_u16(p,v);c2_record_u16(p+2,v>>16);}
static uint32_t c2_attic_watermark(void){return watermark;}
static uint8_t c2_lite_bank2_scan(c2_append_state *w){(void)w;return scan_ok;}
static uint8_t c2_product_append_staged_result(uint16_t n){(void)n;return append_result;}
'''
    tests = r'''
static c2_append_state fresh(void) {
    c2_append_state w={0};
    c2_runtime.image_count=63;c2_runtime.entry_count=100;
    c2_runtime.resolution_count=50;c2_runtime.c2_root_count=20;
    w.entries=18;w.literals=10;w.roots=3;w.length=500;w.code_len=318;
    c2_record_u16(w.record+2,2048);c2_record_u16(w.record+4,4096);
    c2_record_u16(w.record+6,1536);c2_record_u32(w.record+8,8192);
    c2_record_u32(w.record+12,50000);c2_record_u32(w.record+16,60758);
    C2AW_RESERVE_MARK(&w)=C2_RESERVE_SCAN_DONE;watermark=0;scan_ok=1;
    return w;
}
static void capacity(c2_append_state *w) {
    assert(c2_append_reserve_persistent_bounds_phase(w)==C2_STREAM_ERR_C2D);
    assert(w->append.error==C2_APPEND_CAPACITY_CAUSE);
}
int main(void) {
    c2_append_state w=fresh();
    assert(c2_append_reserve_persistent_bounds_phase(&w)==C2_STREAM_OK);
    assert(w.new_images==64 && w.new_entries==118 && !w.append.error);
    assert(c2_append_reserve_persistent_code_phase(&w)==C2_STREAM_OK);
    assert(c2_u16(w.record+28)==50000);
    w=fresh();c2_runtime.image_count=64;capacity(&w);
    w=fresh();C2AW_FRONT_DEPTH(&w)=1;capacity(&w);
    w=fresh();c2_record_u16(w.record+2,117);capacity(&w);
    w=fresh();c2_record_u16(w.record+4,59);capacity(&w);
    w=fresh();c2_record_u16(w.record+6,22);capacity(&w);
    w=fresh();watermark=8192-499;capacity(&w);
    w=fresh();watermark=0xffffffffUL;
    assert(c2_append_reserve_persistent_bounds_phase(&w)==C2_STREAM_ERR_STATE);
    assert(!w.append.error);
    w=fresh();C2AW_RESERVE_MARK(&w)=0;
    assert(c2_append_reserve_persistent_bounds_phase(&w)==C2_STREAM_ERR_STATE);
    assert(!w.append.error);
    w=fresh();C2AW_RESERVE_MARK(&w)=C2_RESERVE_SCAN_REQUEST;scan_ok=0;
    assert(c2_append_reserve_persistent_code_phase(&w)==C2_STREAM_ERR_C2D);
    assert(!w.append.error);
    w=fresh();assert(c2_append_reserve_persistent_bounds_phase(&w)==C2_STREAM_OK);
    c2_record_u32(w.record+12,60758-318);
    assert(c2_append_reserve_persistent_code_phase(&w)==C2_STREAM_OK);
    w=fresh();assert(c2_append_reserve_persistent_bounds_phase(&w)==C2_STREAM_OK);
    c2_record_u32(w.record+12,60758-317);
    assert(c2_append_reserve_persistent_code_phase(&w)==C2_STREAM_ERR_C2D);
    assert(w.append.error==C2_APPEND_CAPACITY_CAUSE);
    for(append_result=0;append_result<=2;append_result++) {
        vm_status=VM_OK;
        assert(c2_product_append_staged(500)==(append_result==C2_APPEND_BEGIN_OK));
        assert(vm_status==VM_OK);
        obj got=c2_product_publish_staged(500);
        assert(got==(append_result==C2_APPEND_BEGIN_OK?lisp_t:NIL));
        assert(vm_status==(append_result==C2_APPEND_BEGIN_OK?VM_OK:
               append_result==C2_APPEND_BEGIN_CAPACITY?VM_HEAPOOM:VM_BADOPCODE));
    }
    puts("PASS: image/entry/resolution/root/source/code bounds; corrupt state distinct; bool and typed APIs");
}
'''
    text = prefix + '\n'.join(macros) + '\n' + bodies + tests
    cases = [('positive', text)]
    for name, old, new in (
        ('capacity-as-success', 'return c2_product_append_staged_result(length) == C2_APPEND_BEGIN_OK;',
         'return c2_product_append_staged_result(length);'),
        ('bad-bytecode-for-capacity', 'result == C2_APPEND_BEGIN_CAPACITY ? VM_HEAPOOM : VM_BADOPCODE',
         'VM_BADOPCODE'),
        ('ignore-transient-images', 'C2D_IMAGE_CAP - C2AW_FRONT_DEPTH(w)', 'C2D_IMAGE_CAP'),
    ):
        assert old in text, name
        cases.append((name, text.replace(old, new)))
    rows=[]
    for name, code in cases:
        path=out/(name+'.c');path.write_text(code)
        exe=out/name
        cmd=['cc','-std=c11','-Wall','-Wextra','-Isrc',str(path),'-o',str(exe)]
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        (out/(name+'-compile.log')).write_text(p.stdout+p.stderr)
        p.check_returncode()
        p=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        assert (p.returncode==0)==(name=='positive'), (name,p.stdout,p.stderr)
        rows.append(dict(name=name,exit=p.returncode,sha256=hashlib.sha256(code.encode()).hexdigest()))
    result=dict(status='PASS: EXTRACTED C MODEL, NOT NATIVE APPEND', rows=rows,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                budget=dict(seed=0,final=0,product_link=0))
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
