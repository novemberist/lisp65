"""Read-only seven-byte audit: reuse a checked16-bit end, no compiler."""
from pathlib import Path
import itertools
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from set_b_front_abi_20260926 import read_instructions, schedule
from set_b_front_order_20260926 import old_accept
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-end-plan-r1'
NATIVE=ROOT/'build/set-b-front-limb-native-r1'
LIMIT=60758

def end_accept(base,at,length,start):
    end=(start+length)&65535
    return (base>>16==0 and at>>16==0 and length!=0
        and base<=start and at==start-base and end>=start and end<=LIMIT)

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    objects=[];instructions={}
    for unit,section,key in (
        ('c2-stream-phase-05b.c','.lisp65_rt_c2d_05b','caller'),
        ('c2_product_runtime.c','.text.c2_front_pending_max','helper')):
        obj=NATIVE/'candidate'/(unit+'.o');dis=NATIVE/'candidate'/(unit+'.disassembly.txt')
        t=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        instructions[key]=read_instructions(dis,section,t);objects.extend((P.bind(obj),P.bind(dis)))
    assert sum(r['bytes'] for r in instructions['caller'])==1796
    assert sum(r['bytes'] for r in instructions['helper'])==38
    bounds=[('start limit',0x51b,0x531),('room subtraction and first length comparison',0x531,0x549),
        ('length comparison tail',0x553,0x55a),('end addition before call',0x66a,0x687)]
    windows=[]
    for label,a,b in bounds:
        rows=[r for r in instructions['caller'] if a<=r['offset']<b]
        assert rows[0]['offset']==a and rows[-1]['offset']+rows[-1]['bytes']==b
        windows.append(dict(label=label,start=a,end_exclusive=b,bytes=sum(r['bytes'] for r in rows)))
    assert [w['bytes'] for w in windows]==[22,24,7,29]
    assert sum(w['bytes'] for w in windows)==82
    for r in instructions['caller']:
        r['cost_class']='replacement pool' if any(a<=r['offset']<b for _,a,b in bounds) else 'retained'
    P.write(OUT/'inventory.json',dict(objects=objects,instructions=instructions,target_windows=windows,
        caller_target_bytes=82,caller_retained_bytes=1714,helper_unchanged_bytes=38,
        zero_length_tail_retained=dict(start=0x549,end_exclusive=0x553,bytes=10),
        call_setup_jsr_reload_retained=dict(start=0x687,end_exclusive=0x6aa,bytes=35),unclassified_bytes=0,
        limits='Complete instruction byte comparison to existing ELF sections. Object-offset attribution, not a patch or a prediction of future register allocation.'))
    core=schedule('compute checked end once and reuse; same helper ABI',[
        ('16-bit addition',[('CLC',1),('LDA start.low',2),('ADC length.low',2),('STA end.low',2),
            ('LDA start.high',2),('ADC length.high',2),('STA end.high',2)]),
        ('reject end less than start',[('LDA end.low',2),('CMP start.low',2),('LDA end.high',2),
            ('SBC start.high',2),('BCS next',2),('JMP entry-fail',3)]),
        ('reject end above limit',[('LDA #limit.low',2),('CMP end.low',2),('LDA #limit.high',2),
            ('SBC end.high',2),('BCS next',2),('JMP entry-fail',3)])])
    assert core['bytes']==39
    P.write(OUT/'worksheet.json',core)
    cases=0
    for start in range(65536):
        candidates={0,1,7,32768,65535}
        for boundary in (LIMIT-start,65536-start):
            candidates.update(n for n in (boundary-1,boundary,boundary+1) if 0<=n<=65535)
        for length in candidates:
            old=bool(length) and start<=LIMIT and length<=LIMIT-start
            end=(start+length)&65535;new=bool(length) and end>=start and end<=LIMIT
            assert old==new,(start,length)
            if new:assert end==start+length
            cases+=1
    count=0
    for base in itertools.chain(range(65536),(65536,65537,0xffffff)):
        for at in sorted({0,1,7,max(0,LIMIT-base),max(0,LIMIT-base+1),65535,65536,0xffffff}):
            for length in (0,1,7,65535):
                for start in {(base+at)&65535,((base+at)&65535)^1}:
                    assert old_accept(base,at,length,start)==end_accept(base,at,length,start)
                    count+=1
    # Falling specification control: dropping wrap refusal would accept 65535+1.
    assert ((65535+1)&65535)<=LIMIT and not end_accept(65535,0,1,65535)
    P.write(OUT/'models.json',dict(range_boundary_cases=cases,full_predicate_boundary_cases=count,
        falling_control=dict(start=65535,length=1,wrapped_end=0,without_wrap_guard=True,with_wrap_guard=False),
        limits='Python arithmetic only. Not an actual C, ISA, transport, fault-order or lifetime execution.'))
    budget=dict(existing05b_object=1796,existing05b_linked_projection=1799,target_pool=82,
        symbolic_core=39,spill_bridge_liveness_allowance=24,replacement_target=63,target_saving=19,
        other05b_drift_allowance=12,projected05b_target=1780,hard05b_ceiling=1792,
        hard05b_growth_cap=137,helper_unchanged=38,ordinary_target=764,other_resident_drift_cap=20,
        hard_ordinary_ceiling=784,region0_ceiling=65205,E000_remaining=25,BSS_remaining=1,capture_remaining=48,
        measured_successor_bytes=None)
    assert 1799-(82-(39+24))+12==1792
    P.write(OUT/'budget.json',budget)
    P.write(OUT/'receipt.json',dict(status='READ-ONLY CHECKED-END REUSE PLAN COMPLETE; SUCCESSOR FIT UNMEASURED',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='724860a3',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        predecessor=P.bind(ROOT/'build/set-b-front-limb-close-r1/receipt.json'),objects=objects,
        inventory=P.bind(OUT/'inventory.json'),worksheet=P.bind(OUT/'worksheet.json'),
        models=P.bind(OUT/'models.json'),budget=P.bind(OUT/'budget.json'),
        product_admitted=False,consumed=dict(seeds=5,finals=0,product_links=5),
        authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=0,dependency_calls=0,host_c_compiles=0,host_c_links=0,
            assembly_calls=0,product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Existing object audit, source algebra and symbolic widths only; no emitted successor, compiler-size guarantee or semantic C pass.',
        next_proposal='One isolated05b-only checked-end reuse form over limb candidate; keep byte helper and its ABI exact. Compute uint16 end once after existing reads, refuse end<start or end>limit at same row decision, pass end after all bindings. Objects/packing before actual C fault/lifetime tests; halt on cap/floor failure or unbound successor. No product attempt.'))
    print('PLAN:82-byte pool ->63 target,19 saving plus12 drift; helper38 unchanged; models',cases,count,'; zero compilers')

if __name__=='__main__':main()
