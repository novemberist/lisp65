"""Execute product reader bodies on a recording host transport (not native timing)."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import symbol_layout_manifest as layout

ROOT = layout.ROOT

def body(source, name):
    start = source.index('{', source.index(name+'('))
    end, depth = start+1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

def run(output):
    source = (ROOT/'src/c2_platform_dma.c').read_text()
    values = layout.values()
    code = '\n'.join('#define '+key+' '+str(value) for key,value in values.items())
    code += r'''
#include <stdint.h>
#include <assert.h>
#include <setjmp.h>
#include <string.h>
typedef uint16_t obj;
#define LISP65_CODE_WINDOW_CONVERGENCE
#define LISP65_C2_MUTABLE_CPU_READS
#define LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT 61
#define DMA_COUNT(x) ((void)0)
static uint32_t physical;
static uint16_t length;
static unsigned calls, aborts;
static int success = 1;
static jmp_buf landing;
static int c2_map_cpu_read(uint32_t p, uint8_t *d, uint16_t n) {
    physical=p; length=n; calls++;
    if (!success) return 0;
    memset(d, 0x12, n); return 1;
}
static void lisp_abort_static(unsigned code, const char *message) {
    assert(code==61 && message); aborts++; longjmp(landing,1);
}
'''
    functions = {
        'c2_dma_read_or_abort':'static void c2_dma_read_or_abort(uint8_t bank, uint16_t offset, uint16_t length, uint8_t *destination)',
        'c2_sympool_read_or_abort':'static void c2_sympool_read_or_abort(uint16_t offset, uint16_t length, uint8_t *destination)',
        'sympool_read':'void sympool_read(uint16_t offset, char *destination, uint16_t length)',
        'symval_get':'obj symval_get(uint16_t index)',
        'nameoff_get':'uint16_t nameoff_get(uint16_t index)',
        'symfn_ext_get':'obj symfn_ext_get(uint16_t index)',
    }
    for name, declaration in functions.items():
        if name=='c2_sympool_read_or_abort': code += '\n#if SYMPOOL_EXT_BANK != 5\n'
        code += '\n'+declaration+' '+body(source,name)+'\n'
        if name=='c2_sympool_read_or_abort': code += '\n#endif\n'
    # Expected addresses are from the independently loaded manifest, not the
    # macros in the generated unit which the wrong-bank mutation changes.
    main = r'''
int main(void) {
    char buffer[34];
    for (unsigned i=0; i<16351; i++) {
        sympool_read(i,buffer,34);
        assert(physical==0x1c000u+i && length==34);
        assert(physical+length<=0x20000u);
    }
    for (unsigned i=0; i<1008; i++) {
        assert(symval_get(i)==0x1212); assert(physical==0x5c680u+2*i && length==2);
        assert(nameoff_get(i)==0x1212); assert(physical==0x5ce60u+2*i && length==2);
        assert(symfn_ext_get(i)==0x1212); assert(physical==0x5d640u+2*i && length==2);
    }
    assert(calls==16351+3*1008 && aborts==0);
    success=0;
    if (!setjmp(landing)) { sympool_read(0,buffer,1); assert(!"name read failure returned"); }
    if (!setjmp(landing)) { symval_get(0); assert(!"table read failure returned"); }
    assert(aborts==2); return 0;
}
'''
    assert values['MAX_SYM']==1008 and values['NAMEPOOL']==16351
    assert [values[k] for k in ('SYMPOOL_EXT_OFF','SYMVAL_EXT_OFF','NAMEOFF_EXT_OFF','SYMFN_EXT_OFF')]==[49152,50816,52832,54848]
    variants={'candidate':code,
        'wrong-name-bank':code.replace('#define SYMPOOL_EXT_BANK 1','#define SYMPOOL_EXT_BANK 5'),
        'wrong-function-offset':code.replace('#define SYMFN_EXT_OFF 54848','#define SYMFN_EXT_OFF 54846'),
        'swallowed-read-error':code.replace('if (c2_map_cpu_read(physical, destination, length)) return;',
                                          'if (!c2_map_cpu_read(physical, destination, length)) return;')}
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,unit in variants.items():
        if name!='candidate' and unit==code: raise ValueError('empty mutation: '+name)
        c=output/(name+'.c');exe=output/name
        c.write_text(unit+main)
        subprocess.run(['cc','-std=c11','-O1','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
        result=subprocess.run([str(exe)],capture_output=True,text=True)
        if (result.returncode==0)!=(name=='candidate'): raise ValueError('reader check: '+name)
        rows.append(dict(name=name,returncode=result.returncode,stderr=result.stderr,
                         source_sha256=hashlib.sha256(c.read_bytes()).hexdigest()))
    receipt=dict(status='PASS',source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                 manifest_sha256=hashlib.sha256(layout.MANIFEST.read_bytes()).hexdigest(),rows=rows,
                 claim='Extracted product reader bodies with recording host transport; no native timing or hardware proof.',
                 product_budget=dict(seed=0,final=0,link=0))
    from check_result_receipt import report
    report(output/'receipt.json', receipt)
    print('PASS: 16351 name offsets, 3024 table reads, two abort paths, three falling controls')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
