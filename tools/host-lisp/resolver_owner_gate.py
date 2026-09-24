"""Execute the product owner query and resolver fronts; no native product build.

The host transport supplies bytes only. All owner values and the capacity
predicate come from the product source and its selected manifest definitions.
"""
from pathlib import Path
import ctypes
import hashlib
import json
import re
import subprocess
import sys

import bytecode_p0_stdlib as P
import symbol_layout_manifest as L

ROOT=L.ROOT
B,C=P.B,P.C
FIELDS=('LISP65_C2_BANK2_CODE_LIMIT','C2D_IMAGE_CAP','C2D_ENTRY_CAP',
        'C2D_RESOLUTION_CAP','C2D_ROOT_CAP','C2D_MAX_TRANSIENT_DEPTH',
        'C2D_HANDLE_CAP','C2_EXPORT_PLAN_LIMIT - C2_EXPORT_JOURNAL_BASE')

def function(source,declaration):
    start=source.index(declaration)
    at=source.index('{',start)+1;end=at;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

def bind(path):
    raw=path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def build(output, *, limit=None, stale=False):
    output.mkdir(parents=True,exist_ok=True)
    runtime=ROOT/'src/c2_product_runtime.c'
    header=ROOT/'src/c2_product_runtime.h'
    text=runtime.read_text()
    manifest=L.load();authority=ROOT/manifest['predecessor_manifest']['path']
    definitions=L.replace_definitions(json.loads(authority.read_text())['definitions'])
    names={d.split('=',1)[0] for d in definitions}
    assert {'LISP65_C2_NESTED_APPEND_V5','LISP65_C2_TWO_REGION_SESSION_STORE'}<=names
    if limit is not None:
        definitions=[d for d in definitions if not d.startswith('LISP65_C2_BANK2_CODE_LIMIT=')]
        definitions.append('LISP65_C2_BANK2_CODE_LIMIT='+str(limit))
    # Extract the actual conditional definition block, including query/table.
    start=text.index('#define C2_MAX_HOT_LITERALS')
    end=text.index('static inline void c2_header_watermark',start)
    body=text[start:end]+'\n#endif\n'
    if stale:
        old='C2_OWNER_PARTS(LISP65_C2_BANK2_CODE_LIMIT)'
        assert body.count(old)==1
        body=body.replace(old,'C2_OWNER_PARTS(65536UL)')
    extent=re.findall(r'^#define LISP65_C2D_BYTES .+$',header.read_text(),re.M)
    assert len(extent)==1
    code='''#include <stdint.h>
#include <string.h>
static uint8_t header_bytes[28], readable=1;
void set_header(const void *p) { memcpy(header_bytes,p,28); }
void set_readable(uint8_t value) { readable=value; }
static uint8_t c2_stream_c2d_read(uint16_t at,void *dst,uint16_t n) {
    if (!readable || at || n!=sizeof header_bytes) return 0;
    memcpy(dst,header_bytes,n);return 1;
}
'''+extent[0]+'\n'+body+'\n'
    code+=function(text,'static uint16_t c2_u16(')+'\n'
    code+=function(text,'static uint8_t c2_resolver_header_capacities(void) {')+'\n'
    code+='uint32_t expected_owner(unsigned i) {\n const uint32_t owners[] = {'+','.join(FIELDS)+'};\n return owners[i];\n}\n'
    source=output/'bridge.c';source.write_text(code)
    library=output/'bridge.so'
    command=['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC']
    # Only preprocessing of this isolated host bridge; no MOS/LTO/link budget.
    command+=['-D'+d for d in definitions]+[str(source),'-o',str(library)]
    subprocess.run(command,check=True,capture_output=True)
    native=ctypes.CDLL(str(library))
    native.c2_resolver_owner_part.argtypes=[ctypes.c_uint8]
    native.c2_resolver_owner_part.restype=ctypes.c_uint16
    native.expected_owner.argtypes=[ctypes.c_uint]
    native.expected_owner.restype=ctypes.c_uint32
    native.set_header.argtypes=[ctypes.c_void_p]
    native.set_readable.argtypes=[ctypes.c_uint8]
    native.inputs=[bind(p) for p in (runtime,header,authority,L.MANIFEST)]
    return native

def main():
    output=ROOT/'build/resolver-owner-check'
    native=build(output/'actual');query=native.c2_resolver_owner_part
    values=[native.expected_owner(i) for i in range(8)]
    assert [query(2*i)+256*query(2*i+1) for i in range(8)]==values
    assert all(query(i)==65535 for i in range(17,256))
    changed=build(output/'changed-owner',limit=values[0]-1)
    assert changed.c2_resolver_owner_part(0)+256*changed.c2_resolver_owner_part(1)==values[0]-1
    stale=build(output/'stale-owner',stale=True)
    assert stale.c2_resolver_owner_part(0)+256*stale.c2_resolver_owner_part(1)!=values[0]
    whole=build(output/'exclusive-bank-end',limit=65536)
    assert (whole.c2_resolver_owner_part(0),whole.c2_resolver_owner_part(1))==(0,256)
    raw=bytearray(33840)
    raw[:8]=b'C2D\0\6\x30\x20\x0a'
    def word(at,value):raw[at:at+2]=value.to_bytes(2,'little')
    word(8,values[6]);word(10,1);word(12,6)
    for i in range(1,5):word(10+4*i,values[i])
    for at,value in zip((28,30,32,34,36,38),(48,2096,22576,30768,33840,6)):word(at,value)
    native.set_header(ctypes.create_string_buffer(bytes(raw[:28])))
    assert query(16)==1
    controls=['owner-change-propagated','stale-bank-end','exclusive-bank-end']
    for field in (8,10,12,14,16,18,20,22,24,26):
        bad=bytearray(raw[:28])
        value=(0 if field in (8,10,12) else 65535)
        bad[field:field+2]=value.to_bytes(2,'little')
        native.set_header(ctypes.create_string_buffer(bytes(bad)))
        assert query(16)==0,field
        controls.append('invalid-header-field-'+str(field))
    native.set_readable(0);assert query(16)==0;native.set_readable(1)
    controls.append('unreadable-header')
    suite=P._read_suite(str(ROOT/'tests/bytecode/libs/p0-stdlib-require-resolver.json'))
    suite['cases']=[dict(name='owners',expr='nil',expect='nil')]
    heap,_,_,_,_,_,directory,_,_,_=P._compile_suite(suite)
    abi,ledger=P._suite_abi(suite)
    class VM(B.P0VM):
        def _callprim(self,pid,argc,stack,pc=None,native_base=0,frame_slots=0):
            if pid!=67:return super()._callprim(pid,argc,stack,pc,native_base,frame_slots)
            args=self._pop_args(argc,stack)
            if argc not in (1,2) or not all(B.is_fix(a) and 0<=B.fixval(a)<=255 for a in args):
                raise B.VMError('TypeError','product byte argument domain')
            if argc==2:return B.mkfix(raw[B.fixval(args[0])+256*B.fixval(args[1])])
            native.set_header(ctypes.create_string_buffer(bytes(raw[:28])))
            value=query(B.fixval(args[0]))
            return B.NIL if value==65535 else B.mkfix(value)
    def call(expression):
        h=heap.clone();vm=VM(heap=h,directory=dict(directory),abi_profile=abi,abi_ledger=ledger,max_steps=1000000)
        _,code,helpers=C.compile_top_form_with_helpers(C.parse_one('(lambda () '+expression+')'),h,strict_arity=True,abi_profile=abi,abi_ledger=ledger)
        assert not helpers
        return h.obj_to_text(vm.run(code,[]))
    assert call('(%require-owner-pair 0)')==f'({values[0]&255} . {values[0]>>8})'
    # Empty transient population starts at the actual code owner, not bank end.
    fronts=call('(%require-transient-fronts (%require-c2d-state))')
    assert fronts==f'(0 {values[2]} {values[3]} {values[4]} ({values[0]&255} . {values[0]>>8}))',fronts
    assert call('(%require-state-advance-p (list 6 8 9 10 4096) (list 7 9 10 11 4096) 4)')=='t'
    assert call('(%require-state-advance-p (list 6 8 9 10 4096) (list 7 7 10 11 4096) 4)')=='nil'
    assert call('(%require-state-advance-p (list 6 8 9 10 4096) (list 7 9 10 11 4095) 4)')=='nil'
    receipt=dict(status='PASS',owners=dict(zip(FIELDS,values)),fronts=fronts,controls=controls,
                 inputs=native.inputs+[bind(ROOT/'lib/stdlib-require.lisp'),bind(Path(__file__))],
                 claim='Actual C query/capacity predicate and product-domain Lisp; not native transport or timing.')
    from check_result_receipt import report
    report(output/'receipt.json', receipt)
    print('PASS: resolver owner query, capacity predicate, transient fronts and monotonic state',len(controls))

if __name__=='__main__':main()
