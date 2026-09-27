"""Seal the completion ownership halt without extending the fault qualification."""
from pathlib import Path
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_fence_20260926 as Q
import set_b_front_paths_seal_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding
ROOT=P.ROOT;OUT=ROOT/'build/set-b-front-fence-close-r2'

def main():
    PREVIOUS.check();authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    roots=[x['after'] for x in c['roots']]+c['sources'];assert c['root_count']==74
    for b in roots:assert P.bind(ROOT/b['path'])==b
    for b in P.load(F.OUT/'binding.json')['candidate']:assert P.bind(ROOT/b['path'])==b
    proof=Q.OUT/'receipt.json';q=P.load(proof);h=P.load(Q.OUT/'halt.json')
    assert q['passing_rows']==72 and q['row_count']==73
    assert h['kind']=='outstanding-earlier-write-boundary' and h['actual'][:6]==[0,1,1,1,0,8]
    assert h['actual'][6]==h['actual'][7] and h['actual'][8]==0
    assert h['before']=='a5'*16 and h['after']=='00'*8+'a5'*8 and h['expected']=='00'*16
    commands=ROOT/'build/set-b-front-span-native-r1/commands.json';cmds=P.load(commands)
    assert all('-DLISP65_C2_MAP_CPU_TRANSPORT' in x['command'] for x in cmds)
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text()
    read=F.R.I.function(runtime[runtime.index('C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_read'):],'c2_stream_c2d_read');write=F.R.I.function(runtime[runtime.index('C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write'):],'c2_stream_c2d_write')
    assert '#ifdef LISP65_C2_MAP_CPU_TRANSPORT' in read and 'c2_facade_map_cpu_read(' in read
    assert 'c2_facade_c2_dma(' in write and 'return 1;' in write
    contract=ROOT/'config/c2-cpu-chip-write-completion-contract.json';k=P.load(contract)
    assert 'same ordered DMA engine' in k['completion']['ordering_witness']
    map_source=ROOT/'src/optional/c2_map_cpu_read.s';assert 'no DMA submission and no completion signal' in map_source.read_text()
    sources=[F.OUT/'candidate/src/c2_product_runtime.c',ROOT/'src/c2_product_runtime.c',map_source,
        ROOT/'src/c2_completion_mode_length.s',ROOT/'src/rtov_crc_mem.s',ROOT/'src/c2_platform_dma.c',
        contract,ROOT/'docs/planning/c2.2-cpu-chip-write-completion-contract.md',
        ROOT/'docs/planning/2.1-cpu-transport-work-plan.md',ROOT/'config/c2-v21-cpu-transport-release-contract.json',commands]
    P.write(OUT/'ordering-attribution.json',dict(sources=[P.bind(p) for p in sources],
        contract=k['completion']['ordering_witness'],
        write='Bounded C2D DMA submission; result1 follows submission, no target verification in this facade.',
        read='Active MAP_CPU_TRANSPORT branch uses synchronous physical CPU read via the selector. Assembly explicitly has no DMA submission/completion signal.',
        predicate='Reads64-byte already-active C2J for rollback barrier; matches retained emission-bound CRC16. No touched transaction-data address is read by this predicate.',
        observed='Actual C predicate accepts unchanged journal while8 earlier-write bytes remain pending in synthetic memory.',
        missing='A bound transport/CPU ordering guarantee that excludes that visibility state under the active reader, or an explicit narrower admitted fault model. Selected authorities do not establish this bridge.',
        not_claimed=['hardware reachability of the schedule','a new defect introduced by the span candidate','full publication or rollback accepted','complete search of every historical decision'],
        halt='Do not proceed to replay or repair; retain exact predicate, CRCs and capacity.'))
    command=P.load(Q.OUT/'command.json')['command'].copy();at=command.index('-o');del command[at:at+2];command+=['-M','-MT','fixture']
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);log=OUT/'host-dependencies.log';log.write_text(r.stdout+r.stderr);assert not r.returncode,r.stderr
    internal=[];external=[]
    for word in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
        p=(ROOT/word).resolve()
        (internal if p.is_relative_to(ROOT) else external).append(P.bind(p) if p.is_relative_to(ROOT) else external_binding(p))
    P.write(OUT/'host-dependencies.json',dict(command=command,exit=0,log=P.bind(log),internal=internal,external=external))
    P.write(OUT/'receipt.json',dict(status='HALT: ACTIVE READER ORDERING BRIDGE UNBOUND; NO REPLAY QUALIFICATION',
        driver=P.bind(Path(__file__)),execution_head='5b401d68',source_authority=authority,compiler_authority=P.bind(cp),compiler_inputs=roots,verified_compiler_roots=74,
        predecessor=P.bind(PREVIOUS.SEAL),candidate=P.bind(F.OUT/'binding.json'),capacity=P.bind(ROOT/'build/set-b-front-span-capacity-r1/receipt.json'),
        C_proof=P.bind(proof),halt=P.bind(Q.OUT/'halt.json'),ordering_attribution=P.bind(OUT/'ordering-attribution.json'),
        host_dependencies=P.bind(OUT/'host-dependencies.json'),host_dependency_external=external,
        this_commission=dict(native_object_compiles=0,native_dependency_calls=0,host_c_compile_attempts=1,host_c_compile_successes=1,host_c_links=1,
            host_dependency_calls=1,product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),product_admitted=False,
        passing_content_rows=72,halt_rows=1,replay_rows=0,
        unchanged_air=dict(phase05b_free=5,ordinary_floor_margin=8,BSS_floor_margin=1,E000_floor_margin=25,capture_floor_margin=48),
        limits='Exact unchanged C predicate with host parity helpers and synthetic memory visibility. No asynchronous hardware model, native timing or shipped defect claim. Halt is a missing transport-ordering proof, not proof of accepted full partial publication.',
        next_proposal='Read-only transport-authority reconciliation before any new fixture/repair: establish whether the active MAP/CPU read is guaranteed to follow completion of prior F018 writes, bind the guarantee and its scope or record its absence, and define the admitted partial/stale fault domain explicitly. No source change, compiler/product build/link/Seed/guest/device.'))
    print('CLOSED HALT:72 content passes; predicate accepts with8 pending bytes in synthetic schedule; replay0; host1/1; product0')
if __name__=='__main__':main()
