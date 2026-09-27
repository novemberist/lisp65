"""Read-only error-domain audit and predicate/order model; no compiler or C run."""
from pathlib import Path
import itertools
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-order-r1'
LIMIT=60758

def old_accept(base,at,length,directory):
    return (base<=65535 and at<=65535-base and directory==base+at
        and bool(length) and directory<=LIMIT and length<=LIMIT-directory)

def fused_accept(base,at,length,directory):
    return (bool(length) and base<=LIMIT and at+length<=LIMIT-base
        and directory==base+at)

def model(mode,base=100,length=7,bad_source=None,fault=None,bad_binding=None):
    trace=[];pending=90
    def read(label):
        trace.append(label);return label!=fault
    def done(status,phase):return dict(status=status,phase=phase,reads=trace,pending=pending)
    # Common-image helpers are represented as single read events. These are
    # order models, not an execution of those helpers or real transport.
    for event in ('04.image','04.header','05a.image','05a.header'):
        if not read(event):return done(1,event.split('.')[0])
    if mode=='early' and not read('05a.extra-base'):return done(1,'05a')
    for i in range(2):
        if not read(f'05a.entry{i}'):return done(1,'05a')
        if bad_source==i or (i==0 and not length):return done(5,'05a')
        if mode=='early':
            end=base+i*7+(length if i==0 else 7)
            if end>LIMIT:return done(5,'05a')
            pending=max(pending,end)
    for event in ('05b.image','05b.raw','05b.header'):
        if not read(event):return done(1,'05b')
    for i in range(2):
        for event in (f'05b.entry{i}',f'05b.directory{i}'):
            if not read(event):return done(1,'05b')
        at=i*7;n=length if i==0 else 7;directory=(base+at)&65535
        accepted=(fused_accept if mode=='fused' else old_accept)(base,at,n,directory)
        if bad_binding==i or not accepted:return done(5,'05b')
        if mode!='early':pending=max(pending,directory+n)
    return done(0,'completed05b')

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    commands=P.load(ROOT/'build/set-b-front-relocation-native-r1/commands.json')
    command=next(r for r in commands if r['world']=='before' and r['unit']=='c2-stream-phase-05b.c')
    pin=next(d['binding'] for d in command['dependencies']['inputs'] if d['logical']=='config/set-b-native/includes/static-plane/c2_lite_static_plane.h')
    assert P.bind(ROOT/pin['path'])==pin and 'STATIC_CODE_BYTES 49758UL' in (ROOT/pin['path']).read_text()
    assert '-DLISP65_C2_BANK2_CODE_LIMIT=60758' in command['command']
    assert 49758<LIMIT
    rules={
        'config/set-b-native/includes/c2-stream-decoder.c':r'code_target|STATIC_CODE_BYTES|next \+ length|c2_stream_phase_05|r16\(de|r24\(raw \+ 18\)|return fail\(c, C2_STREAM_ERR_(IO|ENTRY)\)',
        'src/c2_product_runtime.c':r'code_low|code_high|bank2_code_range|c2_facade_target_overlay_call_family|status == C2_STREAM_OK|C2_APPEND_CAPACITY_CAUSE|v5_fail:|v5_reject:|vm_status =|entry_cursor|c2_append_source_domain_guard',
        'src/c2_bank2_code_domain.h':r'.',
        'src/vm_runtime_overlay.c':r'\*entry_result = RTOV_CALL|rtov_wipe\(\)|rtov_fail\(|rtov_fault =|rtov_busy = 0',
        'src/vm.c':r'vm_status_error_code|LISP65_ERR_VM_BAD_BYTECODE|VM_TYPEERROR|VM_STEPLIMIT',
        'src/eval.c':r'vm_check_status|vm_status = VM_OK|vm_status_error_code|lisp_abort_code',
        'src/error_codes.h':r'LISP65_ERR_VM_BAD_BYTECODE',
        'config/error-texts.json':r'vm-bad-bytecode',
        pin['path']:r'.'}
    witnesses=[]
    for name,pattern in rules.items():
        p=ROOT/name;ls=p.read_text().splitlines()
        witnesses.append(dict(source=P.bind(p),hits=[dict(line=i+1,text=x,context=ls[max(0,i-2):i+3]) for i,x in enumerate(ls) if re.search(pattern,x)]))
    P.write(OUT/'source-witnesses.json',witnesses)
    count=0
    for base in itertools.chain(range(65536),(65536,65537,0xffffff)):
        for at in sorted({0,1,7,max(0,LIMIT-base),max(0,LIMIT-base+1),65535,65536,0xffffff}):
            for length in (0,1,7,65535):
                for directory in {(base+at)&65535,((base+at)&65535)^1}:
                    assert old_accept(base,at,length,directory)==fused_accept(base,at,length,directory)
                    count+=1
    assert 0xffffff+65535<2**32
    events=['04.image','04.header','05a.image','05a.header','05a.entry0','05a.entry1',
        '05b.image','05b.raw','05b.header','05b.entry0','05b.directory0','05b.entry1','05b.directory1']
    rows=[]
    for base,length,bad_source,fault,bad_binding in itertools.product(
            (100,LIMIT-7,LIMIT,LIMIT+1,65536,0xffffff),(0,7,65535),(None,0,1),(None,*events),(None,0,1)):
        a=model('old',base,length,bad_source,fault,bad_binding)
        b=model('fused',base,length,bad_source,fault,bad_binding)
        assert a==b,(base,length,bad_source,fault,bad_binding,a,b)
        rows.append(dict(base=base,length=length,bad_source=bad_source,fault=fault,bad_binding=bad_binding,result=a))
    P.write(OUT/'order-model.json',dict(rows=rows,scope='Specification model of source/entry read order and pure predicates; not candidate C or a real transport trace.'))
    old=model('old',LIMIT,7,None,'05a.entry1');early=model('early',LIMIT,7,None,'05a.entry1');new=model('fused',LIMIT,7,None,'05a.entry1')
    assert old['status']==new['status']==1 and early['status']==5
    new_read_old=model('old',bad_source=0,fault='05a.extra-base')
    new_read_early=model('early',bad_source=0,fault='05a.extra-base')
    assert new_read_old['status']==5 and new_read_early['status']==1
    controls=[dict(name='bound prior C halt',old=old,early=early,proposed=new,
        C_authority=P.bind(ROOT/'build/set-b-front-relocation-faults-r2/first-unbound-error.json')),
        dict(name='extra early base read also changes precedence',old=new_read_old,early=new_read_early,
            proof='Source-order model only; no additional actual C row run.')]
    P.write(OUT/'controls.json',controls)
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    assert t.section('.lisp65_rt_c2d_05b').bytes==1655
    align=lambda n:(n+31)//32*32
    packing_growth=align(1404+15)-align(1404)+align(1655+137)-align(1655)
    assert packing_growth==160 and 65536-(65045+packing_growth)==331
    budget=dict(ordinary_helper_and_any_resident_drift_cap=58,total_ordinary_cap=784,
        phase05b_delta_cap=137,phase04_retained_measured_delta=15,phase05a_delta_cap=0,
        phase05b_max=1792,region0_max=65205,region0_min_air=331,
        E000_remaining=25,BSS_remaining=1,capture_remaining=48,
        old_monolithic05b_increment=270,required_05b_reduction=133,
        required_total_net_reduction_if_all58_bytes_used=75,
        measured_new_helper_bytes=None,measured_new_05b_bytes=None)
    P.write(OUT/'budget.json',budget)
    P.write(OUT/'receipt.json',dict(status='READ-ONLY ERROR-ORDER CONTRACT COMPLETE; RESTORE05a AND REFUSE/ACCUMULATE AT05b',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='39af7c16',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        consumed_static_pin=pin,prior_commands=P.bind(ROOT/'build/set-b-front-relocation-native-r1/commands.json'),
        witnesses=P.bind(OUT/'source-witnesses.json'),predicate_boundary_cases=count,order_model_rows=len(rows),
        model=P.bind(OUT/'order-model.json'),controls=P.bind(OUT/'controls.json'),budget=P.bind(OUT/'budget.json'),
        predecessor=P.bind(ROOT/'build/set-b-front-relocation-close-r1/receipt.json'),elf=P.bind(elf),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        proposal=dict(phase05a='Restore maintained body, including all reads, validations and handoff; no execution-base read.',
            phase05b='Same reads and same row failure point. Fold domain into existing pure address predicate: length !=0, base<=60758, at+length<=60758-base; retain every other binding check.',
            update='After complete row acceptance, call a noinline ordinary-text leaf that only max-updates context.entry_cursor with the validated uint16 end. No I/O, allocation, certificate publication or error return.',
            phase04='Retain measured+15 initialization after the existing source guard; do not return pending storage to Entries.',
            status='Design only; semantic equivalence is to prior parked05b validator, not arbitrary extra acceptance of corrupted maintained inputs.'),
        source_error_mapping='With successful transport/wipe and rollback, decoder IO1/ENTRY5 are nonzero entry results, both facade false; neither equals capacityFE. Publish/install map noncapacity rejection to VM_BADOPCODE and code43. File-load bool stays false. No full runtime execution or diagnostic-state equality claimed.',
        cold=dict(new05a_reads=0,new_overlay_calls=0,new_resident_max_calls_in_prior_conditional_model=804,
            retained_query_header_calls=4,retained_query_header_bytes=32,
            margin_cycles=277701,exact_new_cycles=None,exact_new_stack=None),
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=0,dependency_calls=0,host_c_compiles=0,host_c_links=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,model_runs=1),
        product_admitted=False,limits='Read-only source and ELF audit plus arithmetic/order specification models. No new C, compile, link or candidate execution. No gate relaxed or fault-domain narrowing accepted.',
        next_proposal='One isolated05b fused-check/resident-max form, object and packing gates first (helper/resident<=58,05b delta<=137, every floor). Then actual C error-order replay including both controls and full lifecycle rows. No product build/link/Seed/device.'))
    print('CONTRACT:',count,'predicate cases;',len(rows),'order-model rows;05a restored; helper+drift cap58,05b cap137,region0 max65205; zero compilers')

if __name__=='__main__':main()
