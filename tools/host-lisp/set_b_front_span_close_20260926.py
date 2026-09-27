"""Close capacity and bounded actual-C qualification of the scalar-span form."""
from pathlib import Path
import subprocess
from elf_truth import ElfTruth
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from set_b_load_preflight_seal_20260926 import external_binding
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-span-close-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    capacity=ROOT/'build/set-b-front-span-capacity-r1/receipt.json';cap=P.load(capacity)
    native=ROOT/'build/set-b-front-span-native-r1/receipt.json';n=P.load(native)
    assert cap['status'].startswith('PASS') and cap['text']==dict(new=776,air=40,floor=32,margin=8)
    row=next(x for x in cap['owners'] if x['section']=='.lisp65_rt_c2d_05b')
    assert row==dict(section='.lisp65_rt_c2d_05b',before=1655,delta=132,projected=1787,air=5)
    assert next(x for x in n['changes'] if x['section']=='.text.c2_front_pending_max')['after']==50
    proofs=[];dependencies=[];external=[]
    for name,count,command_key in (('faults-r1',941,'compile'),('lifetime-r2',229,'command')):
        path=ROOT/f'build/set-b-front-span-{name}/receipt.json';q=P.load(path);proofs.append(P.bind(path))
        assert q['status'].startswith('PASS') and q['halt'] is None
        assert q['row_count']==q['passing_rows']==count
        rows=P.load(ROOT/q['rows']['path']);assert len(rows)==count
        command=P.load(ROOT/q[command_key]['path'])['command'].copy();at=command.index('-o');del command[at:at+2]
        command+=['-M','-MT','fixture']
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        folder=OUT/name;folder.mkdir();log=folder/'host-dependencies.log';log.write_text(r.stdout+r.stderr)
        assert r.returncode==0,r.stderr
        internal=[];deps=[]
        for word in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
            p=(ROOT/word).resolve()
            if p.is_relative_to(ROOT):internal.append(P.bind(p))
            else:deps.append(external_binding(p))
        external.extend(deps)
        path=folder/'host-dependencies.json'
        P.write(path,dict(command=command,exit=0,log=P.bind(log),internal=internal,external=deps));dependencies.append(P.bind(path))
    failed=P.load(ROOT/'build/set-b-front-span-lifetime-r1/command.json');assert failed['exit']!=0
    assert 'Traceback' in (ROOT/'build/set-b-front-span-lifetime-r1-execution.log').read_text()
    # Compare every allocated section to the better parked limb candidate,
    # including byte contents and relocations, not merely section sizes.
    unchanged=[];changed=[]
    for unit in ('c2_product_runtime.c','vm.c','c2-stream-phase-04.c','c2-stream-phase-05a.c','c2-stream-phase-05b.c'):
        a=ElfTruth.read(ROOT/'build/set-b-front-limb-native-r1/candidate'/(unit+'.o'),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        b=ElfTruth.read(ROOT/'build/set-b-front-span-native-r1/candidate'/(unit+'.o'),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        aa={x.name:x for x in a.sections if 'SHF_ALLOC' in x.flags}
        bb={x.name:x for x in b.sections if 'SHF_ALLOC' in x.flags}
        def rel(t,n):return [(x.offset,x.relocation_type,x.target,x.addend) for x in t.relocations if x.source_section==n]
        for name in sorted(aa.keys()|bb.keys()):
            x,y=aa.get(name),bb.get(name)
            equal=x and y and x.bytes==y.bytes and rel(a,name)==rel(b,name)
            if equal and x.section_type!='SHT_NOBITS':equal=a.section_bytes(name)==b.section_bytes(name)
            (unchanged if equal else changed).append([unit,name])
    assert changed==[['c2_product_runtime.c','.text.c2_front_pending_max'],['c2-stream-phase-05b.c','.lisp65_rt_c2d_05b']],changed
    P.write(OUT/'limb-comparison.json',dict(unchanged=unchanged,changed=changed,
        predecessor_native=P.bind(ROOT/'build/set-b-front-limb-native-r1/receipt.json'),current_native=P.bind(native),
        interpretation='All allocated byte/relocation differences against best parked limb control are confined to05b and its pending-max helper; every other owner matches.'))
    P.write(OUT/'receipt.json',dict(status='COMPLETE: OBJECT CAPACITY AND BOUNDED C ERROR/LIFETIME GATES PASS; NO PRODUCT ADMISSION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='09c7c983',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        source=P.bind(ROOT/'build/set-b-front-span-r1/binding.json'),capacity=P.bind(capacity),native=P.bind(native),
        limb_comparison=P.bind(OUT/'limb-comparison.json'),C_proofs=proofs,C_passing_rows=1170,
        host_dependencies=dependencies,host_dependency_external=list({x['path']:x for x in external}.values()),
        failed_harness_command=P.bind(ROOT/'build/set-b-front-span-lifetime-r1/command.json'),
        predecessor=P.bind(ROOT/'build/set-b-front-end-close-r1/receipt.json'),
        elf=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        scope='One isolated product source form; ten matched native non-LTO objects, complete packing, 941 decoder/helper and229 caller/scratch C rows.',
        interpretation='Capacity fit is a projection with5 overlay bytes and8 ordinary floor margin. C tests qualify extracted code at declared synthetic seams, not real journal/world writers or a linked native product.',
        remaining=['Close raw-writer invalidation and every real publication/recovery caller before adoption',
            'Replace synthetic stage/publication/rollback seams with real C paths where feasible; bind whole-product exact errors including BAD BYTECODE',
            'Native cold/stack/GC and linked identity remain later gates under separate product authority'],
        product_admitted=False,consumed=dict(seeds=5,finals=0,product_links=5),
        authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=10,native_dependency_calls=10,
            host_c_compile_attempts=3,host_c_compile_successes=2,host_c_links=2,host_dependency_calls=2,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Non-LTO deltas, unchanged linked baseline and all-record packing projection; extracted C under host ABI with synthetic transaction/image/transport seams. No product adoption, exact VM error, native time, stack or GC claim.',
        next_proposal='Host-only closure of the remaining real writer/caller paths on this exact isolated source: inventory every certificate invalidation and pending/terminal use, connect real stage/publication/rollback code to a bounded memory fixture where feasible, price any missing hook before mutation. Keep05b1787/1792, ordinary776/784 and all floors; halt on missing ownership, new semantic successor or capacity failure. No product build/link/Seed/guest/device.'))
    print('COMPLETE:05b1787/1792; ordinary776,8 floor margin;1170 C rows; host3 attempts/2 successes; no product attempt')

if __name__=='__main__':main()
