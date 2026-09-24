"""Execute fallback admission before every public require route.

The C owner query is compiled from product source. Stopping at loader intent
is deliberate: this gate proves exclusion, not native rollback or package use.
"""
from pathlib import Path
import ctypes,json,subprocess,sys
from pathlib import Path
import resolver_owner_gate as G
P=G.P;B=G.B;C=G.C;ROOT=G.ROOT

def main():
    out=ROOT/'build/transient-retirement-guard-check';out.mkdir(exist_ok=True)
    native=G.build(out/'owners');query=native.c2_resolver_owner_part
    values=[native.expected_owner(i) for i in range(8)]
    raw=bytearray(33840);raw[:8]=b'C2D\0\6\x30\x20\x0a'
    def word(at,value):raw[at:at+2]=value.to_bytes(2,'little')
    word(8,values[6]);word(10,1);word(12,6)
    for i in range(1,5):word(10+4*i,values[i])
    for at,value in zip((28,30,32,34,36,38),(48,2096,22576,30768,33840,6)):word(at,value)
    class EnteredLoader(Exception):pass
    class VM(B.P0VM):
        def _callprim(self,pid,argc,stack,pc=None,native_base=0,frame_slots=0):
            if pid==18:raise EnteredLoader()
            if pid!=67:return super()._callprim(pid,argc,stack,pc,native_base,frame_slots)
            args=self._pop_args(argc,stack)
            if argc==2:return B.mkfix(raw[B.fixval(args[0])+256*B.fixval(args[1])])
            assert argc==1
            native.set_header(ctypes.create_string_buffer(bytes(raw[:28])))
            value=query(B.fixval(args[0]))
            return B.NIL if value==65535 else B.mkfix(value)
    suite=P._read_suite(str(ROOT/'tests/bytecode/libs/p0-stdlib-require-resolver.json'))
    suite['cases']=[dict(name='guard',expr='nil',expect='nil')]
    abi,ledger=P._suite_abi(suite)
    def compiled(s):return P._compile_suite(s)
    actual=compiled(suite)
    def call(product,expr):
        heap=product[0].clone();directory=dict(product[6])
        vm=VM(heap=heap,directory=directory,abi_profile=abi,abi_ledger=ledger,max_steps=1000000)
        _,code,helpers=C.compile_top_form_with_helpers(C.parse_one('(lambda () '+expr+')'),heap,strict_arity=True,abi_profile=abi,abi_ledger=ledger)
        assert not helpers
        before=bytes(raw)
        try:result=heap.obj_to_text(vm.run(code,[]))
        except EnteredLoader:result='ENTERED_LOADER'
        assert bytes(raw)==before
        return result
    cases=[]
    # One or more live transient handles, including nested/high population.
    for handles in (1,2,21,100,values[2]-1):
        word(8,values[6]-handles)
        for expression in ('(require "defstruct")','(require "place")',"(require 'inspect)"):
            result=call(actual,expression);assert result=='nil',(handles,expression,result)
            cases.append(dict(handles=handles,expression=expression,result=result))
    word(8,values[6]);assert call(actual,'(require "defstruct")')=='ENTERED_LOADER'
    for bad in (0,values[6]+1):
        word(8,bad);assert call(actual,'(require "defstruct")')=='nil'
    word(8,values[6]);native.set_readable(0)
    assert call(actual,'(require "defstruct")')=='nil'
    native.set_readable(1)
    # Actual predecessor public require is the falling mutation, not a stub.
    old=out/'unguarded.lisp'
    old.write_bytes(subprocess.check_output(['git','show','0822d651:lib/stdlib-require.lisp'],cwd=ROOT))
    stale=dict(suite);stale['sources']=[str(old.relative_to(ROOT)) if p=='lib/stdlib-require.lisp' else p for p in suite['sources']]
    mutation=compiled(stale);word(8,values[6]-1)
    assert call(mutation,'(require "defstruct")')=='ENTERED_LOADER'
    receipt=dict(status='PASS: PRODUCT OWNER + PUBLIC REQUIRE ADMISSION',cases=cases,
        controls=['live-transient','cached-package-before-fast-path','invalid-watermark','unreadable-owner','unguarded-predecessor'],
        inputs=native.inputs+[G.bind(ROOT/'lib/stdlib-require.lisp'),G.bind(Path(__file__))],
        boundary='Host entry exclusion only; native normal/abort package-use and code-byte identity remain mandatory on Seed.')
    from check_result_receipt import report
    report(out/'receipt.json', receipt)
    print(receipt['status'],len(cases),'rows')
if __name__=='__main__':main()
