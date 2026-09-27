"""Close the measured relocation at its first unbound C error successor."""
from pathlib import Path
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from set_b_load_preflight_seal_20260926 import external_binding
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-relocation-close-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    bindings=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    capacity=ROOT/'build/set-b-front-relocation-capacity-r2/receipt.json';cap=P.load(capacity)
    proof=ROOT/'build/set-b-front-relocation-faults-r2/receipt.json';q=P.load(proof)
    assert cap['status'].startswith('PASS') and q['status'].startswith('HALT')
    assert (q['row_count'],q['passing_rows'])==(40,39)
    h=P.load(ROOT/q['halt']['path']);assert [h[k]['status'] for k in ('maintained','previous','candidate')]==[1,1,5]
    failed=P.load(ROOT/'build/set-b-front-relocation-faults-r1/command.json')
    assert failed['exit']!=0 and P.load(ROOT/q['compile']['path'])['exit']==0
    for p in ('build/set-b-front-relocation-capacity-r1-execution.log','build/set-b-front-relocation-faults-r1-execution.log'):
        assert 'Traceback' in (ROOT/p).read_text()
    command=P.load(ROOT/q['compile']['path'])['command'].copy();at=command.index('-o');del command[at:at+2]
    command+=['-M','-MT','fixture']
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    log=OUT/'host-dependencies.log';log.write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    internal=[];external=[]
    for word in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
        p=(ROOT/word).resolve()
        if p.is_relative_to(ROOT):internal.append(P.bind(p))
        else:external.append(external_binding(p))
    P.write(OUT/'host-dependencies.json',dict(command=command,exit=0,log=P.bind(log),internal=internal,external=external))
    P.write(OUT/'receipt.json',dict(status='HALT AT ERROR-PRECEDENCE GATE; OBJECT AND PACKING PROJECTIONS PASS',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='775c4083',
        compiler_authority=P.bind(cp),verified_compiler_roots=74,compiler_inputs=bindings,
        source=P.bind(ROOT/'build/set-b-front-relocation-r1/binding.json'),capacity=P.bind(capacity),C_proof=P.bind(proof),
        host_dependencies=P.bind(OUT/'host-dependencies.json'),host_dependency_external=external,
        predecessor=P.bind(ROOT/'build/set-b-front-placement-r1/receipt.json'),
        elf=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        scope='39 passing selected C rows, then first mixed-fault row halts with IO1 versus ENTRY5. No further lifecycle qualification or product execution.',
        interpretation='Synthetic error-domain counterexample in candidate, not a shipped defect; ordinary admitted-world reachability and final VM error mapping not established. No tolerance or gate relaxation.',
        remaining=['Keep earlier decoder fault precedence or prove/bind its supported domain before another form',
            'Terminal publication/transient exclusion/rollback/nonlocal recovery fixtures',
            'Raw writer closure and whole-product exact BAD BYTECODE successors','Native cold, stack, GC and linked delivery identity'],
        product_admitted=False,consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=10,native_dependency_calls=10,host_c_compile_attempts=2,
            host_c_compile_successes=1,host_c_links=1,host_dependency_calls=1,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Non-LTO matched deltas and aligned projection; exact selected C functions with synthetic image/transaction seams. No complete product lifecycle, native time or error-mapping proof.',
        next_proposal='Read-only error-domain and phase-order analysis: preserve source-read precedence, separate provisional max computation from range refusal, price retaining the refusal at the existing05b binding point within its137-byte air. No compiler/product attempt until that contract is closed.'))
    print('CLOSED HALT: 39 C passes, IO1/ENTRY5 successor; native10/10 and packing pass; two host compile attempts, one success/link; zero product/Seed/device')

if __name__=='__main__':main()
