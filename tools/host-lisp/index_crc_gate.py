"""Private parser composition, actual native C CRC bridge and actual D81."""
from pathlib import Path
import json,sys,ctypes,copy,hashlib,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'build/index-crc-check'
HERE.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import bytecode_p0_stdlib as P
import resolver_owner_gate as OWNER
B,C=P.B,P.C
BASE='4cf5a2f9'
raw=subprocess.check_output(['git','show',BASE+':lib/stdlib-require.lisp'],cwd=ROOT,text=True)
baseline=HERE/'baseline-require.lisp';baseline.write_text(raw)
candidate=ROOT/'lib/stdlib-require.lisp'
removed={'%l65i-crc-bits','%l65i-crc-byte','%l65i-row-crc-byte'}
# Extract the actual product function; the C harness never keeps a second body.
vm_source=(ROOT/'src/vm.c').read_text()
first=vm_source.index('static __attribute__((noinline)) obj vm_index_crc_step(')
last=vm_source.index('\n}\n',first)+3
(HERE/'crc-bridge.h').write_text(vm_source[first:last])
cc=['cc','-O2','-I',str(ROOT/'src'),'-I',str(HERE),'-DHEAP_CELLS=48','-DLISP65_EXT_HEAP',
    str(ROOT/'tests/fixtures/index_crc_native.c')]
subprocess.run(cc+['-o',str(HERE/'native')],check=True)
subprocess.run([str(HERE/'native')],check=True)
subprocess.run(cc+['-shared','-fPIC','-o',str(HERE/'native.so')],check=True)
native=ctypes.CDLL(str(HERE/'native.so'))
native.crc_bridge_value.argtypes=[ctypes.c_uint16,ctypes.c_uint8]
native.crc_bridge_value.restype=ctypes.c_uint32
medium=ROOT/'build/storage-owner-final-medium-r2/packed/hardware-sp-seed.d81';d81=medium.read_bytes()
assert hashlib.sha256(d81).hexdigest()=='903f4a7ed783018b4c140c8c6198b1ca689b2cb6a8d58cf6b0f1e0fd3a8128cd'
disk={(t,s):d81[((t-1)*40+s)*256:((t-1)*40+s+1)*256] for t in range(1,81) for s in range(40)}
directory=(40,3);locator=None
while directory[0]:
    sector=disk[directory]
    for i in range(8):
        base=i*32
        if sector[base+5:base+21].rstrip(b'\xa0\0 ')==b'L65INDEX':
            locator=tuple(sector[base+3:base+5])
    directory=tuple(sector[:2])
assert locator
chain=[];ts=locator
while ts[0]:
    chain.append(ts);ts=tuple(disk[ts][:2])
assert len(chain)==2
# The live public entry now queries the native owner before parsing. Supply
# that product query, not the reference VM's two-argument-only seam. This
# fixture has no transient handles; malformed indexes must reach the parser.
owner=OWNER.build(HERE/'owner-bridge')
owner_header=bytearray(28)
owner_header[:8]=b'C2D\0\6\x30\x20\x0a'
def owner_word(at,value):owner_header[at:at+2]=value.to_bytes(2,'little')
owner_word(8,owner.expected_owner(6));owner_word(10,1);owner_word(12,6)
for field in range(1,5):owner_word(10+4*field,owner.expected_owner(field))
owner.set_header(ctypes.create_string_buffer(bytes(owner_header)))
assert owner.c2_resolver_owner_part(16)==1
class VM(B.P0VM):
    def _callprim(self,pid,argc,stack,pc=None,native_base=0,frame_slots=0):
        if pid==67:
            args=self._pop_args(argc,stack)
            if argc not in (1,2) or not all(B.is_fix(a) and 0<=B.fixval(a)<=255 for a in args):
                raise B.VMError('TypeError','product owner byte domain')
            if argc==1:
                value=owner.c2_resolver_owner_part(B.fixval(args[0]))
                return B.NIL if value==65535 else B.mkfix(value)
            at=B.fixval(args[0])+256*B.fixval(args[1])
            if at>=len(owner_header):raise AssertionError('unexpected resolver access in rejected parser row')
            return B.mkfix(owner_header[at])
        if pid==18 and argc==2:
            self.append_calls=getattr(self,'append_calls',0)+1
        if pid==16 and argc==2:
            state,value=self._pop_args(argc,stack)
            if not self.heap.consp(state) or not B.is_fix(value):raise B.VMError('TypeError','CRC domain')
            lo,hi=self.heap.car(state),self.heap.cdr(state)
            if not all(B.is_fix(x) and 0<=B.fixval(x)<=255 for x in (lo,hi,value)):raise B.VMError('TypeError','CRC byte domain')
            crc=native.crc_bridge_value(B.fixval(lo)|(B.fixval(hi)<<8),B.fixval(value));assert crc>>16==0
            self.heap.cell(state).a=B.mkfix(crc&255);self.heap.cell(state).b=B.mkfix(crc>>8)
            self.crc_updates.append(crc);return value
        return super()._callprim(pid,argc,stack,pc,native_base,frame_slots)
rows=[]
for variant in ('baseline','candidate'):
    suite=P._read_suite(str(ROOT/'tests/bytecode/libs/p0-stdlib-require-resolver.json'))
    suite['cases']=[dict(name='parse',expr='(%l65i-parse)',expect='nil')]
    suite['sources']=[str(candidate if variant=='candidate' else baseline)
        if Path(p).name=='stdlib-require.lisp' else p for p in suite['sources']]
    if variant=='baseline':
        # The old parser must consume its own function population, not names
        # introduced by a later resolver card. Its source is already era-bound.
        historical=json.loads(subprocess.check_output(
            ['git','show',BASE+':tests/bytecode/libs/p0-stdlib-require-resolver.json'],
            cwd=ROOT,text=True))
        current=json.loads((ROOT/'tests/bytecode/libs/p0-stdlib-require-resolver.json').read_text())
        new_names=set(current['functions'])-set(historical['functions'])
        suite['functions']=[n for n in suite['functions'] if n not in new_names]
        suite['functions']+=sorted(set(historical['functions'])-set(suite['functions']))
        assert removed<=set(suite['functions'])
    else:
        # The obsolete retaining parser must fail the new lifetime oracle,
        # even though its successful index value is identical.
        old=subprocess.check_output(['git','show','89c2cc48:lib/stdlib-require.lisp'],
                                    cwd=ROOT,text=True)
        start=old.index('(defun %l65i-parse ()')
        end=old.index('\n(defun ',start+1)
        control=HERE/'retaining-parser-control.lisp'
        control.write_text(old[start:end].replace('(defun %l65i-parse ()',
                          '(defun %l65i-parse-retaining-control ()',1))
        suite['sources'].append(str(control))
        suite['functions'].append('%l65i-parse-retaining-control')
    heap,_,_,_,_,_,directory,_,_,_=P._compile_suite(suite)
    abi,ledger=P._suite_abi(suite)
    vm=VM(heap=heap,directory=directory,abi_profile=abi,abi_ledger=ledger,
        disk_raw_sectors=disk,max_steps=10000000);vm.crc_updates=[]
    _,code,helpers=C.compile_top_form_with_helpers(C.parse_one('(lambda () (%l65i-parse))'),heap,strict_arity=True,abi_profile=abi,abi_ledger=ledger)
    assert not helpers
    initial_heap=heap.clone()
    value=vm.run(code,[]);text=heap.obj_to_text(value)
    if variant=='candidate':
        assert all(heap.symbol_value(heap.intern(name))==B.NIL
                   for name in ('*l65i-crc-hi*','*l65i-row-hi*'))
    row=dict(variant=variant,result=text,crc_updates=len(vm.crc_updates),
        functions=len(directory),code_bytes=sum(len(x.encode()) for x in directory.values()))
    rows.append(row);print(variant,text[:120],row['crc_updates'])
    if variant=='candidate':
        h=initial_heap.clone()
        stale=VM(heap=h,directory=dict(directory),abi_profile=abi,abi_ledger=ledger,
                 disk_raw_sectors=disk,max_steps=10000000)
        stale.crc_updates=[]
        _,old_code,helpers=C.compile_top_form_with_helpers(
            C.parse_one('(lambda () (%l65i-parse-retaining-control))'),h,
            strict_arity=True,abi_profile=abi,abi_ledger=ledger)
        assert not helpers and h.obj_to_text(stale.run(old_code,[]))==text
        assert any(h.symbol_value(h.intern(root))!=B.NIL
                   for root in ('*l65i-crc-hi*','*l65i-row-hi*'))
        row['old_retaining_parser_rejected']=True
    controls={}
    for name in ('flipped-row','wrong-lock','truncated-one-byte','truncated-sector-boundary',
                 'short-header-0','short-header-4','short-header-17','short-header-18','short-header-31'):
        changed=dict(disk)
        target=chain[-1] if name=='truncated-one-byte' else chain[0]
        sector=bytearray(changed[target])
        if name=='truncated-one-byte':
            assert sector[0]==0 and sector[1]>1
            # Remove the final payload byte, and clear newly unused storage.
            sector[sector[1]]=0;sector[1]-=1
        elif name=='truncated-sector-boundary':
            # The first 254 payload bytes remain intact; continuation is gone.
            sector[0]=0;sector[1]=255
        elif name.startswith('short-header-'):
            length=int(name.rsplit('-',1)[1])
            sector[0]=0;sector[1]=length+1
        else:sector[34 if name=='flipped-row' else 13]^=1
        changed[target]=bytes(sector)
        h=initial_heap.clone();test=VM(heap=h,directory=dict(directory),abi_profile=abi,abi_ledger=ledger,disk_raw_sectors=changed,max_steps=10000000);test.crc_updates=[]
        try:answer=h.obj_to_text(test.run(code,[]))
        except B.VMError as exc:answer='ERROR:'+str(exc)
        controls[name]=dict(rejected=answer=='nil' or answer.startswith('ERROR:'),answer=answer)
        if variant=='candidate':
            assert all(h.symbol_value(h.intern(root))==B.NIL
                       for root in ('*l65i-crc-hi*','*l65i-row-hi*'))
            _,load_code,helpers=C.compile_top_form_with_helpers(
                C.parse_one('(lambda () (require "inspect"))'),h,
                strict_arity=True,abi_profile=abi,abi_ledger=ledger)
            assert not helpers
            loaded=h.obj_to_text(test.run(load_code,[]))
            assert loaded=='nil' and getattr(test,'append_calls',0)==0, (name,loaded)
            _,recover,helpers=C.compile_top_form_with_helpers(
                C.parse_one('(lambda () (+ 4 5))'),h,
                strict_arity=True,abi_profile=abi,abi_ledger=ledger)
            assert not helpers and h.obj_to_text(test.run(recover,[]))=='9'
            controls[name].update(require_result=loaded,append_calls=0,recovery='9',
                                  scope='Host VM, not native prompt or bank identity')
    row['controls']=controls
assert rows[0]['result']==rows[1]['result'] and rows[1]['result']!='nil'
assert rows[1]['crc_updates']==482
assert rows[0]['controls']['truncated-one-byte']['answer']==rows[0]['result']
assert all(c['answer']=='nil' for c in rows[1]['controls'].values()), rows[1]['controls']
from check_result_receipt import report
report(HERE/'receipt.json', dict(status='PASS: native CRC parser projection and exact nil truncation controls',rows=rows,
    last_sector=list(chain[-1]),last_sector_count_before=disk[chain[-1]][1],last_sector_count_after=disk[chain[-1]][1]-1,
    limits=['Host model, not native latency; full product-domain suite remains owed.']))
print([(x['variant'],x['code_bytes'],{n:c['rejected'] for n,c in x['controls'].items()}) for x in rows])
