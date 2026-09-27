"""Close the single directory-difference/byte-max attempt at its object-capacity halt."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-limb-close-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    capacity=ROOT/'build/set-b-front-limb-capacity-r1/receipt.json';cap=P.load(capacity)
    native=ROOT/'build/set-b-front-limb-native-r1/receipt.json';n=P.load(native)
    assert cap['status']=='HALT AT CAPACITY GATE; NO C EXECUTION'
    assert cap['text']==dict(new=764,air=52,floor=32,margin=20)
    row=next(x for x in cap['owners'] if x['section']=='.lisp65_rt_c2d_05b')
    assert row==dict(section='.lisp65_rt_c2d_05b',before=1655,delta=144,projected=1799,air=-7)
    helper=next(x for x in n['changes'] if x['section']=='.text.c2_front_pending_max')
    assert helper['after']==38
    disasm=ROOT/'build/set-b-front-limb-native-r1/candidate/c2_product_runtime.c.disassembly.txt'
    text=disasm.read_text().split('Disassembly of section .text.c2_front_pending_max:',1)[1]
    text=text.split('\nDisassembly of section ',1)[0]
    excerpt=OUT/'pending-max.disassembly.txt';excerpt.write_text(text)
    P.write(OUT/'receipt.json',dict(status='HALT AT CAPACITY:05b SHORT7; ORDINARY FLOOR PASSES WITH20 MARGIN; NO C EXECUTION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='d2865265',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        source=P.bind(ROOT/'build/set-b-front-limb-r1/binding.json'),capacity=P.bind(capacity),native=P.bind(native),
        helper_disassembly=P.bind(excerpt),helper_disassembly_source=P.bind(disasm),
        predecessor=P.bind(ROOT/'build/set-b-front-abi-r1/receipt.json'),
        elf=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        scope='One isolated source form, ten matched non-LTO objects and dependency closures; halt before host C or native execution.',
        interpretation='Capacity rejection, not a new semantic defect. Full error-order, lifecycle, exact BAD BYTECODE, stack, GC and cold gates remain unexecuted.',
        remaining=['Remove at least7 bytes from05b without changing read/error order; ordinary text has20 bytes above its floor',
            'Actual C semantic-read/partial-copy controls and pending/terminal/recovery lifetime qualification',
            'Whole-product exact error, raw-writer closure, native cold/stack/GC and linked identity'],
        product_admitted=False,consumed=dict(seeds=5,finals=0,product_links=5),
        authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=10,native_dependency_calls=10,
            host_c_compiles=0,host_c_links=0,host_dependency_calls=0,product_builds=0,product_links=0,
            seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Non-LTO object deltas and all-record packing only. No alternative form, relaxed floor, C pass or product admission.',
        next_proposal='Read-only audit of the remaining7-byte05b overrun, including call/setup costs and the now measured20-byte resident margin. Bind one exact reduction/transfer form preserving error/read order before another compilation; no floor waiver or product attempt.'))
    print('CLOSED CAPACITY HALT:05b1799/1792; ordinary764 leaves52/floor32; no C or product attempt')

if __name__=='__main__':main()
