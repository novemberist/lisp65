"""Close and seal the isolated barrier's destination-lifetime halt."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_ordering_20260926 as PREVIOUS
import set_b_barrier_read_20260926 as Q
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=Q.OUT/'close-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-barrier-read-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-barrier-read-report.md'


def close():
    PREVIOUS.check();authority=S.require_auth();OUT.mkdir(exist_ok=False)
    binding=P.load(Q.OUT/'binding.json')
    for row in binding['before']+binding['candidate']:
        assert P.bind(ROOT/row['path'])==row
    assert binding['changed']==['src/c2_product_runtime.c']
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    c=P.load(cp);roots=[x['after'] for x in c['roots']]+c['sources']
    assert c['root_count']==74
    for row in roots:assert P.bind(ROOT/row['path'])==row
    r1=P.load(Q.OUT/'host-r1/receipt.json');r2=P.load(Q.OUT/'host-replay-r2/receipt.json')
    halt=P.load(Q.OUT/'host-replay-r2/halt.json');got=halt['actual']
    assert r1['row_count']==80 and r1['passing_rows']==79
    assert r2['row_count']==161 and r2['passing_rows']==160
    assert halt['kind']=='late-read-destination-lifetime'
    assert got['accept']==got['committed']==got['pending_write_bytes']==0
    assert got['ticks']==64 and got['pending_read_bytes']==64 and got['escaped_destination']==1
    assert got['data_complete']==1 and got['source_lifetime_errors']==got['order_errors']==got['bounds_errors']==0
    rows=P.load(Q.OUT/'host-replay-r2/rows.json')
    edge=next(r for r in rows if r['kind']=='last-attempt-delivery')
    assert edge['pass_gate'] and edge['actual']['ticks']==64 and edge['actual']['accept']==1
    poll=(Q.OUT/'host-r1/c2_completion_poll.c').read_text()
    assert 'uint8_t observed[64]' in poll and '(uint16_t)(uintptr_t)observed' in poll
    assert poll.count('c2_facade_c2_dma(')==1 and poll.count('c2_completion_mode_length(')==4
    assert 'return 0u;' in poll and 'C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES' in poll
    runtime=(Q.OUT/'candidate/src/c2_product_runtime.c').read_text()
    old=(ROOT/'build/set-b-front-span-r1/candidate/src/c2_product_runtime.c').read_text()
    assert runtime==old.replace(Q.OLD_READ,Q.NEW_READ)
    P.write(OUT/'lifetime-attribution.json',dict(
        sources=[P.bind(Q.OUT/'candidate/src/c2_product_runtime.c'),P.bind(Q.OUT/'host-r1/c2_completion_poll.c'),
                 P.bind(ROOT/'src/c2_kernal_facade.h'),P.bind(ROOT/'src/c2_platform_dma.c'),
                 P.bind(ROOT/'src/c2_completion_mode_length.s'),P.bind(ROOT/'src/optional/c2_map_cpu_read.s')],
        submitted_target='Function-local observed[64], full host pointer carried by checked low16 facade bridge.',
        actual_timeout='Exact candidate poll returns0 after64 host attempts, committed0, ordered data already complete, trailing read still pending64 bytes.',
        missing_owner='No cancellation, completion acknowledgement or retained-destination ownership before returning. Native physical placement/reuse is not established by this host run.',
        safety_of_fixture='The model records the pending obligation and clears its own pointer without dereferencing it after return. Teardown is not product cancellation.',
        hardware_limit='65th-attempt delivery is an explicit contract-model schedule, not a measured device delay. No native-frame or target stack-corruption claim.',
        stop='One form halted before all native object/dependency calls, capacity, full publication/rollback and device gates.'))
    previous=P.load(ROOT/'build/set-b-front-ordering-r1/receipt.json')
    P.write(OUT/'receipt.json',dict(status='HALT: TRAILING READ DESTINATION OUTLIVES PROVEN OWNERSHIP ON TIMEOUT',
        driver=P.bind(Path(__file__)),execution_head=Q.HEAD,source_authority=authority,
        predecessor=P.bind(PREVIOUS.SEAL),binding=P.bind(Q.OUT/'binding.json'),
        compiler_authority=P.bind(cp),compiler_inputs=roots,verified_compiler_roots=74,
        initial_host=P.bind(Q.OUT/'host-r1/receipt.json'),replay=P.bind(Q.OUT/'host-replay-r2/receipt.json'),
        attribution=P.bind(OUT/'lifetime-attribution.json'),product_admitted=False,
        this_commission=dict(isolated_forms=1,host_compile_attempts=1,host_compile_successes=1,host_links=1,
            host_dependencies=1,extra_host_replay_compiles=0,native_object_compiles=0,native_dependencies=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        consumed=previous['consumed'],authorized_ceiling=previous['authorized_ceiling'],
        inherited_span_air=previous['inherited_air'],candidate_capacity='UNMEASURED: stopped before native pricing',
        outcomes=dict(original_MAP_content=72,DMA_content=72,ordered_data=12,queued_producer=1,
            last_attempt=1,falling_MAP_control=1,permanent_drop_limit=1,lifetime_halt=1),
        next_proposal='One host-only lifetime/ownership design and capacity worksheet before any second form: name a disjoint existing stable destination, all use/reuse owners, and a bounded safe timeout/reentry disposition. No assumed cancellation, BSS expansion, READY clear, boot abort or deadline guarantee; no compile/link/Seed/guest/device.',
        limits='Bounded exact C at named host seams, not linked/native/device acceptance. Retain the ordering requirement and permanent-drop limit. Halt does not authorize a second repair form.'))
    print('CLOSED lifetime HALT:158 content/order rows +2 expected controls; 1 host compile/link/dependency; native0')


def seal():
    PREVIOUS.check();S.require_auth()
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    receipt=P.load(OUT/'receipt.json')
    selected={p for p in Q.OUT.rglob('*') if p.is_file()}
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_barrier_read*_20260926.py'))))
    selected.update([REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT])
    external=[external_binding(Path(shutil.which('python3')).resolve()),external_binding(Path(shutil.which('cc')).resolve())]
    def bindings(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                row={k:value[k] for k in ('path','bytes','sha256')};path=ROOT/row['path']
                if path.is_relative_to(ROOT):
                    assert P.bind(path)==row,row['path'];selected.add(path)
                else:
                    assert external_binding(path)==row;external.append(row)
            else:
                for x in value.values():bindings(x)
        elif isinstance(value,list):
            for x in value:bindings(x)
    for path in sorted(Q.OUT.rglob('*.json')):bindings(P.load(path))
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue0089c308: one isolated completion-reader repair form, bounded host C then matched objects; stop on first semantic/lifetime/capacity failure. No product build/link/Seed/Final/guest/device.\n\n'+
        subprocess.check_output(['git','show',Q.HEAD+':docs/planning/set-b-front-ordering-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        bound=P.bind(path);inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status=receipt['status'],execution_head=Q.HEAD,source_authority=receipt['source_authority'],
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(OUT/'receipt.json'),predecessor=P.bind(PREVIOUS.SEAL),
        inputs=inputs,receipt_copies=copies,external_tools=list({r['path']:r for r in external}.values()),
        this_commission=receipt['this_commission'],consumed=receipt['consumed'],authorized_ceiling=receipt['authorized_ceiling'],
        product_admitted=False,accepted_world='Card L Final',public_release='2.4.0',candidate_capacity=receipt['candidate_capacity']))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless build copies')


def check():
    value=P.load(SEAL)
    for row in value['inputs']+[value['owner_scope']]:assert P.bind(ROOT/row['path'])==row,row['path']
    for row in value['external_tools']:assert external_binding(Path(row['path']))==row
    for row in value['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy'];raw=path.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes'] and hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    PREVIOUS.check();S.require_auth()
    print('PASS barrier-read seal: isolated form, unchanged74 roots, C receipts, oracle attribution and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('close','seal','check'))
    {'close':close,'seal':seal,'check':check}[parser.parse_args().mode]()
