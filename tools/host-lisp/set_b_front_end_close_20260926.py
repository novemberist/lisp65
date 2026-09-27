"""Close the single checked-end reuse attempt at its object-capacity halt."""
from pathlib import Path
from elf_truth import ElfTruth
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-end-close-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    capacity=ROOT/'build/set-b-front-end-capacity-r1/receipt.json';cap=P.load(capacity)
    native=ROOT/'build/set-b-front-end-native-r1/receipt.json';n=P.load(native)
    assert cap['status']=='HALT AT CAPACITY GATE; NO C EXECUTION'
    assert cap['text']==dict(new=764,air=52,floor=32,margin=20)
    row=next(x for x in cap['owners'] if x['section']=='.lisp65_rt_c2d_05b')
    assert row==dict(section='.lisp65_rt_c2d_05b',before=1655,delta=171,projected=1826,air=-34)
    helper=next(x for x in n['changes'] if x['section']=='.text.c2_front_pending_max')
    assert helper['after']==38
    disasm=ROOT/'build/set-b-front-end-native-r1/candidate/c2_product_runtime.c.disassembly.txt'
    text=disasm.read_text().split('Disassembly of section .text.c2_front_pending_max:',1)[1]
    text=text.split('\nDisassembly of section ',1)[0]
    excerpt=OUT/'pending-max.disassembly.txt';excerpt.write_text(text)
    # Compare every allocated section to the better parked limb candidate,
    # including byte contents and relocations, not merely section sizes.
    unchanged=[];changed=[]
    for unit in ('c2_product_runtime.c','vm.c','c2-stream-phase-04.c','c2-stream-phase-05a.c','c2-stream-phase-05b.c'):
        a=ElfTruth.read(ROOT/'build/set-b-front-limb-native-r1/candidate'/(unit+'.o'),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        b=ElfTruth.read(ROOT/'build/set-b-front-end-native-r1/candidate'/(unit+'.o'),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        aa={x.name:x for x in a.sections if 'SHF_ALLOC' in x.flags}
        bb={x.name:x for x in b.sections if 'SHF_ALLOC' in x.flags}
        def rel(t,n):return [(x.offset,x.relocation_type,x.target,x.addend) for x in t.relocations if x.source_section==n]
        for name in sorted(aa.keys()|bb.keys()):
            x,y=aa.get(name),bb.get(name)
            equal=x and y and x.bytes==y.bytes and rel(a,name)==rel(b,name)
            if equal and x.section_type!='SHT_NOBITS':equal=a.section_bytes(name)==b.section_bytes(name)
            (unchanged if equal else changed).append([unit,name])
    assert changed==[['c2-stream-phase-05b.c','.lisp65_rt_c2d_05b']],changed
    P.write(OUT/'limb-comparison.json',dict(unchanged=unchanged,changed=changed,
        predecessor_native=P.bind(ROOT/'build/set-b-front-limb-native-r1/receipt.json'),current_native=P.bind(native),
        interpretation='All allocated byte/relocation differences against best parked limb control are confined to05b; helper and every other owner match.'))
    P.write(OUT/'receipt.json',dict(status='HALT AT CAPACITY:05b SHORT34; END REUSE GROWS27; NO C EXECUTION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='3534895c',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        source=P.bind(ROOT/'build/set-b-front-end-r1/binding.json'),capacity=P.bind(capacity),native=P.bind(native),
        limb_comparison=P.bind(OUT/'limb-comparison.json'),
        helper_disassembly=P.bind(excerpt),helper_disassembly_source=P.bind(disasm),
        predecessor=P.bind(ROOT/'build/set-b-front-end-plan-r1/receipt.json'),
        elf=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        scope='One isolated source form, ten matched non-LTO objects and dependency closures; halt before host C or native execution.',
        interpretation='Capacity rejection, not a new semantic defect. Full error-order, lifecycle, exact BAD BYTECODE, stack, GC and cold gates remain unexecuted.',
        remaining=['Do not continue this larger form; retain the limb candidate with7-byte overrun as best parked control',
            'Actual C semantic-read/partial-copy controls and pending/terminal/recovery lifetime qualification',
            'Whole-product exact error, raw-writer closure, native cold/stack/GC and linked identity'],
        product_admitted=False,consumed=dict(seeds=5,finals=0,product_links=5),
        authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=10,native_dependency_calls=10,
            host_c_compiles=0,host_c_links=0,host_dependency_calls=0,product_builds=0,product_links=0,
            seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Non-LTO object deltas and all-record packing only. No alternative form, relaxed floor, C pass or product admission.',
        next_proposal='One isolated start/length helper-interface form based on the better limb candidate: retain its exact05b validation, pass context/start/length only after full acceptance, compute end inside the resident helper. Measure complete caller and callee owners directly; cap05b growth137, helper plus drift58. Halt on capacity before C fault/lifetime tests. No product attempt or Seed.'))
    print('CLOSED CAPACITY HALT:05b1826/1792,27 worse; ordinary764 leaves52/floor32; no C or product attempt')

if __name__=='__main__':main()
