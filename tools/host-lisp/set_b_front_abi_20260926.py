"""Read-only joint caller/callee cost audit; no assembly, compiler or guest."""
from pathlib import Path
from dataclasses import asdict
import itertools
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from set_b_front_order_20260926 import old_accept
from elf_truth import ElfTruth

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-abi-r1'
NATIVE=ROOT/'build/set-b-front-fused-native-r1'
LIMIT=60758

def limb_accept(base,at,length,start):
    return (base>>16==0 and at>>16==0 and length!=0
        and base<=start and at==start-base
        and start<=LIMIT and length<=LIMIT-start)

def byte_max(cursor,end):
    lo,hi=cursor&255,cursor>>8
    elo,ehi=end&255,end>>8
    if hi<ehi or (hi==ehi and lo<elo):lo,hi=elo,ehi
    return lo+(hi<<8)

def read_instructions(path,section,truth):
    text=path.read_text().split('Disassembly of section '+section+':',1)[1]
    text=text.split('\nDisassembly of section ',1)[0]
    rows=[];raw=truth.section_bytes(section);offset=0
    for line in text.splitlines():
        m=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)([a-z][a-z0-9]*)\s*(.*)$',line)
        if not m:continue
        at=int(m[1],16);data=bytes.fromhex(m[2]);assert at==offset,(path,at,offset)
        assert raw[at:at+len(data)]==data
        rows.append(dict(offset=at,bytes=len(data),hex=data.hex(),mnemonic=m[3],operand=m[4].split(';')[0].strip(),
            relocations=[asdict(r) for r in truth.relocations if r.source_section==section and at<=r.offset<at+len(data)]))
        offset+=len(data)
    assert offset==len(raw)
    return rows

def schedule(name,groups):
    # Symbolic operations are a cost worksheet, not assembled code or a
    # prediction that C will produce this register assignment.
    out=[]
    for label,ops in groups:
        out.append(dict(label=label,operations=[dict(operation=op,bytes=n) for op,n in ops],bytes=sum(n for _,n in ops)))
    return dict(name=name,groups=out,bytes=sum(g['bytes'] for g in out),
        limits='Symbolic instruction-width worksheet only. No candidate emitted, register allocation/bridges proven or execution performed.')

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    inputs=[];instructions={}
    for unit,section,key in (
        ('c2-stream-phase-05b.c','.lisp65_rt_c2d_05b','caller'),
        ('c2_product_runtime.c','.text.c2_front_pending_max','helper')):
        obj=NATIVE/'candidate'/(unit+'.o');dis=NATIVE/'candidate'/(unit+'.disassembly.txt')
        truth=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        instructions[key]=read_instructions(dis,section,truth)
        inputs.extend((P.bind(obj),P.bind(dis)))
    assert sum(x['bytes'] for x in instructions['caller'])==1828
    assert sum(x['bytes'] for x in instructions['helper'])==66
    windows=[('prefix',0,0x45a),('length/base materialization and first range branches',0x45a,0x492),
        ('interleaved completion/loop/IO blocks retained',0x492,0x4cc),
        ('base-guard tails',0x4cc,0x4da),('wide addition/subtraction/comparison',0x4da,0x53c),
        ('directory address materialization and equality',0x53c,0x584),
        ('other row bindings retained',0x584,0x68a),('end calculation and argument setup',0x68a,0x6bf),
        ('helper call',0x6bf,0x6c2),('context register reload',0x6c2,0x6ca),('loop and error tail',0x6ca,1828)]
    mapped=[]
    for label,a,b in windows:
        rows=[r for r in instructions['caller'] if a<=r['offset']<b]
        assert rows[0]['offset']==a and rows[-1]['offset']+rows[-1]['bytes']==b
        assert sum(r['bytes'] for r in rows)==b-a
        mapped.append(dict(label=label,start=a,end_exclusive=b,bytes=b-a))
    assert sum(r['bytes'] for r in mapped)==1828
    target=sum(mapped[i]['bytes'] for i in (1,3,4,5));assert target==240
    assert sum(mapped[i]['bytes'] for i in (7,8,9))==64
    P.write(OUT/'inventory.json',dict(inputs=inputs,instructions=instructions,caller_windows=mapped,
        target_pool_bytes=target,retained_caller_call_window=64,unclassified_bytes=0,
        limits='Object offsets, not linked addresses or execution cycles. Source attribution groups include local materialization; not byte-for-byte compiler successor blocks.'))
    # Use an identical context/end interface; the current object passes c in
    # rc2/rc3, low end in A and high end in X. All proposed helper scratch is
    # already clobbered by that existing callee. Do not transfer pointer work
    # to the caller or credit its existing eight-byte reload as removable.
    helper=schedule('same-interface byte-indexed pending max',[
        ('save end bytes',[('STA rc7',2),('STX rc4',2)]),
        ('compare cursor high',[('LDY #29',2),('LDA (rc2),Y',2),('CMP rc4',2),('BCC store',2),('BNE done',2)]),
        ('compare cursor low',[('DEY',1),('LDA (rc2),Y',2),('CMP rc7',2),('BCS done',2)]),
        ('write low then high',[('LDY #28',2),('LDA rc7',2),('STA (rc2),Y',2),('INY',1),('LDA rc4',2),('STA (rc2),Y',2)]),
        ('return',[('RTS',1)])])
    assert helper['bytes']==33
    fetch=lambda offset:[('LDY #'+str(offset),2),('LDA (buffer),Y',2),('STA low',2),('INY',1),('LDA (buffer),Y',2),('STA high',2)]
    compare=[('LDA difference',2),('CMP source offset',2),('BEQ next',2),('JMP entry-fail',3)]
    caller=schedule('16-bit directory-anchored range and address checks',[
        ('reject nonzero base/offset upper bytes',[('LDY #20',2),('LDA (raw),Y',2),('LDY #2',2),('ORA (e),Y',2),('BEQ next',2),('JMP entry-fail',3)]),
        ('fetch base',fetch(18)),('fetch directory start',fetch(2)),('fetch source offset',fetch(0)),
        ('reject zero length',[('LDA length.low',2),('ORA length.high',2),('BNE next',2),('JMP entry-fail',3)]),
        ('start minus base; reject borrow',[('SEC',1),('LDA start.low',2),('SBC base.low',2),('STA diff.low',2),('LDA start.high',2),('SBC base.high',2),('STA diff.high',2),('BCS next',2),('JMP entry-fail',3)]),
        ('bind both offset bytes',compare+compare),
        ('limit minus start; reject borrow',[('SEC',1),('LDA #limit.low',2),('SBC start.low',2),('STA room.low',2),('LDA #limit.high',2),('SBC start.high',2),('STA room.high',2),('BCS next',2),('JMP entry-fail',3)]),
        ('length at most room',[('LDA room.low',2),('CMP length.low',2),('LDA room.high',2),('SBC length.high',2),('BCS next',2),('JMP entry-fail',3)])])
    assert caller['bytes']==122
    P.write(OUT/'worksheets.json',dict(caller=caller,helper=helper,
        no_assembly=True,limits='Separate local symbolic schedules. Buffer pointer materialization, spills, layout and compiler choices are additional costs, explicitly budgeted; no compiler-size guarantee.'))
    count=0
    for base in itertools.chain(range(65536),(65536,65537,0xffffff)):
        for at in sorted({0,1,7,max(0,LIMIT-base),max(0,LIMIT-base+1),65535,65536,0xffffff}):
            for length in (0,1,7,65535):
                for start in {(base+at)&65535,((base+at)&65535)^1}:
                    assert old_accept(base,at,length,start)==limb_accept(base,at,length,start)
                    count+=1
    max_count=0
    for cursor in range(65536):
        for end in {0,1,255,256,LIMIT,65535,max(0,cursor-1),cursor,min(65535,cursor+1)}:
            assert byte_max(cursor,end)==max(cursor,end);max_count+=1
    P.write(OUT/'models.json',dict(predicate_boundary_cases=count,byte_max_cases=max_count,
        limits='Python arithmetic models only; not actual C, machine-instruction execution or a full fault/transport/lifecycle test.',
        domain='Unsigned24-bit base/offset,16-bit directory start/length; complete algebraic equivalence additionally described in report.'))
    budget=dict(caller_target_pool_before=240,caller_symbolic_core=122,caller_bridge_and_spill_allowance=63,
        caller_replacement_target=185,caller_target_saving=55,caller_other_drift_allowance=16,
        helper_before=66,helper_symbolic_core=33,helper_codegen_allowance=17,helper_target=50,
        other_resident_drift_allowance=8,hard_helper_plus_drift_cap=58,
        projected05b_target=1831-55,hard05b_ceiling=1792,hard05b_growth_cap=137,
        ordinary_target=726+50,hard_ordinary_ceiling=784,region0_ceiling=65205,
        E000_remaining=25,BSS_remaining=1,capture_remaining=48,
        measured_new_caller_bytes=None,measured_new_helper_bytes=None)
    assert budget['projected05b_target']+budget['caller_other_drift_allowance']==1792
    assert budget['ordinary_target']+budget['other_resident_drift_allowance']==784
    P.write(OUT/'budget.json',budget)
    P.write(OUT/'receipt.json',dict(status='READ-ONLY JOINT ABI COST PLAN COMPLETE; COMPILER FIT UNMEASURED',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='82434b68',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        predecessor=P.bind(ROOT/'build/set-b-front-fused-close-r1/receipt.json'),
        native_receipt=P.bind(NATIVE/'receipt.json'),object_inputs=inputs,
        inventory=P.bind(OUT/'inventory.json'),worksheets=P.bind(OUT/'worksheets.json'),
        models=P.bind(OUT/'models.json'),budget=P.bind(OUT/'budget.json'),
        product_admitted=False,consumed=dict(seeds=5,finals=0,product_links=5),
        authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=0,dependency_calls=0,host_c_compiles=0,host_c_links=0,
            assembly_calls=0,product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Existing object/disassembly audit, mathematical models and instruction-width design worksheets only. No measured successor size, ABI execution, C fault/lifecycle or cycle proof.',
        next_proposal='One isolated C form: directory-anchored16-bit checks with upper-byte refusal, same-interface byte-indexed helper using offsetof. Matched objects and all-record packing first; actual C error/lifetime gates only if every existing cap/floor passes. No product attempt.'))
    print('PLAN:',target,'caller bytes targeted; worksheet122+63, helper33+17; hard caps unchanged; models',count,max_count,'; zero compilers')

if __name__=='__main__':main()
