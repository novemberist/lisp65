"""Read-only destination ownership and bounded-timeout worksheet; no compilation."""
import argparse
import gzip
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_barrier_read_close_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=ROOT/'build/set-b-barrier-owner-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-barrier-owner-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-barrier-owner-report.md'
HEAD='873730db'
CANDIDATE=ROOT/'build/set-b-barrier-read-r1/candidate'
SOURCES=[
    CANDIDATE/'src/c2_product_runtime.c',CANDIDATE/'src/vm.c',
    CANDIDATE/'src/optional/set_b_retire_control.c',
    ROOT/'src/optional/set_b_retire_common.h',ROOT/'src/optional/set_b_retire_reset.c',
    ROOT/'src/c2_phase_scratch.h',ROOT/'src/c2_phase_scratch.c',ROOT/'src/c2_session_emitter.c',
    ROOT/'src/c2_platform_dma.c',ROOT/'src/symbol.c',ROOT/'src/repl.c',ROOT/'src/mem.c',
    ROOT/'src/optional/c2_kernal_input_capture.s',ROOT/'src/optional/c2_kernal_input_consumer.s',
    ROOT/'src/c2_kernal_window_equates.inc',ROOT/'src/c2_kernal_window.s',
    ROOT/'src/c2_kernal_runtime.c',ROOT/'src/optional/card_l_stage.c',
    ROOT/'src/c2_product_runtime.h',ROOT/'src/c2_journal_prepare_select.s',
]
AUTHORITIES=[
    ROOT/'config/c2-cpu-chip-write-completion-contract.json',
    ROOT/'config/c2-state-ownership-contract.json',
    ROOT/'config/c2-v160-comfort-input-fidelity-implementation-contract.json',
    ROOT/'config/set-b-native/set-b-inputs.json',ROOT/'config/set-b-native/set-b-placement.h',
    ROOT/'docs/planning/set-b-carrier-plan.md',ROOT/'docs/planning/set-b-carrier-preflight.md',
    ROOT/'docs/planning/set-b-front-span-report.md',
    ROOT/'tools/host-lisp/set_b_front_span_capacity_20260926.py',
    ROOT/'tools/host-lisp/set_b_third_seed_inventory_halt_20260926.py',
    ROOT/'build/set-b-front-span-capacity-r1/receipt.json',
    ROOT/'build/set-b-front-span-capacity-r1/packing.json',
    ROOT/'build/set-b-product-r5/wplto/resident-island-seed.prg.map',
    ROOT/'build/set-b-product-r5/wplto/resident-island-seed.prg.elf',
]


def audit():
    PREVIOUS.check();authority=S.require_auth()
    for p in SOURCES+AUTHORITIES:assert p.is_file(),str(p)
    OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    c=P.load(cp);roots=[r['after'] for r in c['roots']]+c['sources']
    assert c['root_count']==74
    for row in roots:assert P.bind(ROOT/row['path'])==row
    binding=P.load(ROOT/'build/set-b-barrier-read-r1/binding.json')
    for row in binding['candidate']+binding['before']:assert P.bind(ROOT/row['path'])==row
    runtime=SOURCES[0].read_text();scratch=(ROOT/'src/c2_phase_scratch.h').read_text()
    emitter=(ROOT/'src/c2_session_emitter.c').read_text()
    assert 'offsetof(c2_append_state, record) + 31u == 213u' in runtime
    assert 'uint8_t record[32];\n    uint8_t meta[24];\n    uint8_t staged;\n    uint8_t committed;\n    uint8_t rollback_rebuild_header;' in runtime
    assert '#define LISP65_C2_PHASE_SCRATCH_BYTES 304u' in scratch
    assert '#define LISP65_C2_INSTALL_TRACE_BYTES 2u' in scratch
    assert 'sizeof(c2e_work_state) == LISP65_C2_INSTALL_TRACE_OFFSET' in emitter
    record=213-31;end_lower_bound=record+32+24+3
    tail_upper_bound=304-2-end_lower_bound
    assert (record,end_lower_bound,tail_upper_bound)==(182,241,61)
    map_path=ROOT/'build/set-b-product-r5/wplto/resident-island-seed.prg.map'
    maptext=map_path.read_text()
    def section(name):
        m=re.search(r'^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+ '+re.escape(name)+r'$',maptext,re.M)
        assert m,name
        return dict(address=int(m[1],16),bytes=int(m[2],16))
    layout={n:section(n) for n in ('.bss','.lisp65_vm_soft_frames_bss','.lisp65_c2_input_raw_owner',
        '.lisp65_c2_symbol_metadata_bss','.lisp65_c2_convergence_state','.noinit.card_l_gap','.noinit.card_l_late')}
    frames=layout['.lisp65_vm_soft_frames_bss'];input_ring=layout['.lisp65_c2_input_raw_owner']
    low_margin=input_ring['address']-(frames['address']+frames['bytes'])-5
    assert low_margin==8
    m=re.search(r'^\s*([0-9a-f]+)\s+[0-9a-f]+\s+0\s+1\s+__bss_end =',maptext,re.M);assert m
    high_margin=0xc000-int(m[1],16)-5;assert high_margin==5
    packing=P.load(ROOT/'build/set-b-front-span-capacity-r1/packing.json')
    late=next(r for r in packing['regions'] if r['region']==3)
    assert late['projected_used']==6784 and late['air']==1408
    config=P.load(ROOT/'config/set-b-native/set-b-inputs.json')
    assert config['owners'][0]['tenant']['unassigned']==24
    assert config['bank5_tail_floor']==374 and config['header']==dict(address=0x5fe80,bytes=10)
    assert 0x60000-(0x5fe80+10)==374
    footprint=dict(required_destination_bytes=64,record_offset=record,append_end_lower_bound=end_lower_bound,
        scratch_bytes=304,trace_bytes=2,tail_upper_bound=tail_upper_bound,tail_shortfall_at_least=64-tail_upper_bound,
        note='ABI record-offset assertion plus source field widths; no host sizeof substituted for target layout. Padding can only reduce the upper bound.',
        native_map=layout,seed_low_margin_after_floor=low_margin,seed_high_margin_after_floor=high_margin,
        span_certificate_bytes=4,low_margin_if_ordinary_certificate_charge=low_margin-4,
        inherited_conservative_BSS_margin=1,
        bss_limit='Prior price charges the4-byte ordinary certificate delta to high-BSS headroom. This worksheet does not amend that accepted projection. In the current map the low gap is occupied by146-byte soft frames; even its8-byte pre-charge margin is less than64.',
        journal_gap_unused=24,bank5_tail_floor=374,bank5_tail_spendable=0,
        late_projected_padding=dict(start=0x5de80+6784,end_exclusive=0x5fe80,bytes=1408,
            disposition='Sealed tenant-image padding, not an admitted mutable destination. Any split needs a new owner/identity/write-watch contract.'))
    P.write(OUT/'capacity-worksheet.json',footprint)
    owners=[
        ('automatic observed[64]',64,'CALL LOCAL','Expired on return; prior C halt binds64 pending bytes.'),
        ('append scratch tail',61,'AT MOST61','At least3 short before two trace bytes; full emitter overlaps on reuse.'),
        ('journal_snapshot/header union',96,'ALIASES REQUIRED SOURCE','Producer snapshot and old/new48-byte headers, not disjoint. Abort reconstruction and publication reuse it.'),
        ('full phase scratch',304,'SHARED MUTEX OWNER','Emitter fills302 bytes; append and retirement overlap; recovery forcibly releases/reacquires. No quarantine state.'),
        ('sym_name_scratch',34,'TOO SMALL AND LIVE','Symbol lookup/rendering/interning can use it after return.'),
        ('vm_codebuf',56,'TOO SMALL AND LIVE','VM reload/execution owner; retaining it excludes normal evaluator use.'),
        ('VM soft-frame arena',146,'LIVE FRAME OWNER','Low gap is already occupied; cannot borrow suspended frames or active stack.'),
        ('input ring',112,'RAW IRQ/REPL OWNER','Absolute assembly accesses atBC90 despite no C symbol inside the NOLOAD reservation; live prompt can reuse it.'),
        ('DMA convergence arena',66,'DESCRIPTORS AND WITNESSES','25-byte D700 and41-byte D705 owners retained by sources/map; no proof permitting removal or independent timeout retention.'),
        ('ordinary/high BSS slack',8,'BELOW REQUIRED SIZE','Low margin8 before span certificate; high margin5 before conservative certificate charge. Floors are not allocation.'),
        ('retirement-journal gap remainder',24,'TOO SMALL','Other72 bytes are durable retirement before-images; cannot overwrite recovery data.'),
        ('Bank5 tail beyond live header',374,'FLOOR ONLY','Spendable0 above the374-byte floor.'),
        ('Bank5 late-region padding',1408,'SEALED PAYLOAD; NEW OWNER NEEDED','Enough physical space under span projection; not a currently authorized mutable64-byte destination, nor Bank0 storage. Different DMA/CPU sampling and admission required.'),
    ]
    P.write(OUT/'owner-table.json',dict(rows=[dict(owner=n,bytes=b,verdict=v,conflict=c) for n,b,v,c in owners],
        sources=[P.bind(p) for p in SOURCES+AUTHORITIES],
        scope='Named direct destinations and nearest existing stable arenas. Bounded source/ownership inventory, not a proof that no redesign elsewhere in RAM is possible.',
        decision='No admitted disjoint64-byte destination with timeout retention and safe reuse identified under current ownership contracts.'))
    queries=[r'lisp65_c2_phase_scratch|c2_phase_scratch_(acquire|release)|c2_phase_owner|\b(c2aw|c2ew|RX|JJ)\b',
             r'journal_snapshot|old_header|new_header|C2AW_C2J_SEAL|v5_fail:|c2_ready = 0|abort_recover',
             r'c2_dma_verify|c2_edma_probe|sym_name_scratch|vm_codebuf|vm_soft_stack|C2K_INPUT_RING']
    searches=[]
    for i,pattern in enumerate(queries):
        command=['rg','-n',pattern]+[str(p.relative_to(ROOT)) for p in SOURCES]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        assert result.returncode in (0,1),result.stderr
        path=OUT/f'access-edges-{i+1}.txt';path.write_text(result.stdout)
        searches.append(dict(command=command,exit=result.returncode,result=P.bind(path)))
    P.write(OUT/'access-ledger.json',dict(searches=searches,
        coverage='All textual matches in20 named sources including selected candidate, phase APIs, emitter, retirement, VM, symbols, raw input assembly. Includes inactive branches conservatively; not a preprocessed call graph.',
        aliases=dict(append='c2aw => phase scratch',emitter='c2ew => phase scratch',retirement_scan='RX => phase scratch',retirement_readback='JJ => phase scratch+16'),
        critical_reuse_edges=[
            'c2_session_emit_reset: release EMITTER, acquire EMITTER, then initialize shared work state.',
            'c2_session_emit_finalize: release emitter on both success/failure.',
            'c2_append_begin v5_fail: run rollback, clear READY on rollback failure, then release APPEND at v5_reject.',
            'c2_append_publish_staged: failed publication invokes rollback and releases APPEND.',
            'c2_abort_driver: release both owners, reacquire APPEND, validate/reconstruct/restore, release; clear READY on failure.',
            'c2_abort_empty_journal_derived: release both owners, acquire APPEND, overwrite journal_snapshot, release.',
            'c2_retire_control recovery: release both owners then acquire APPEND; RX/JJ reuse follows.',
            'REPL setjmp landing: c2_product_abort_recover precedes rendering/new evaluation; new emitter work precedes next append.',
            'Input IRQ producer/consumer use absolute BC90 ring; no symbol-table emptiness exemption.',
        ]))
    assert 'v5_fail:\n    if (!c2_append_run_rollback_plan(&c2aw)) {\n        c2_ready = 0;' in runtime
    assert '(void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);' in runtime
    phase=(ROOT/'src/c2_phase_scratch.c').read_text()
    assert 'c2_phase_owner = LISP65_C2_PHASE_OWNER_NONE;' in phase
    P.write(OUT/'timeout-disposition.json',dict(status='REQUIRED STATE MACHINE; BLOCKED AT OWNER AND EXISTING REENTRY EDGES',
        states=[
            dict(state='IDLE',requirement='No pending DMA to destination; allocation/poison legal only after exclusive acquisition.'),
            dict(state='WAIT',requirement='One read submitted; destination, mode, expected bytes/seal and transaction recovery facts retained; no resubmit/repoison.'),
            dict(state='QUARANTINED',requirement='At deadline return exact IO without clearing READY; no destination/source/transaction reuse or cleanup writes while completion is unproven.'),
            dict(state='REENTRY',requirement='Bounded observation of the same pending result; no new submission. If unresolved keep ownership and refuse unsafe work without recursive recovery.'),
            dict(state='RECOVER',requirement='Only proven read retirement opens rollback/CLEAR; scratch and destination release only after those obligations close.'),
        ],
        blocked_edges=[
            'No existing admitted disjoint destination64 with retention established.',
            'Normal failure takes v5_fail rollback/release, not quarantine; this cannot be fixed by changing destination address alone.',
            'Abort/retirement recovery forcibly releases both scratch owners; acquire guard alone cannot preserve quarantine.',
            'Mode/seal/header expectations and recovery context must also survive; a stable destination alone is insufficient.',
            'Unresolved forward writes may still affect transaction data; a live prompt is not permission for unrestricted evaluation/publication.',
        ],
        not_authorized=['new storage owner','changed comparator','READY clear','boot abort','unbounded wait','assumed cancellation','assumed delivery by deadline','second repair form'],
        claim_limit='Design requirements derived from current source edges; no executed state-machine or Lisp reentry proof.'))
    old=P.load(ROOT/'build/set-b-barrier-read-r1/close-r1/receipt.json')
    P.write(OUT/'receipt.json',dict(status='WORKSHEET COMPLETE; HALT AT EXISTING-OWNER AND TIMEOUT-REENTRY CONFLICT',
        execution_head=HEAD,driver=P.bind(Path(__file__)),source_authority=authority,
        predecessor=P.bind(PREVIOUS.SEAL),compiler_authority=P.bind(cp),compiler_inputs=roots,verified_compiler_roots=74,
        candidate_binding=P.bind(ROOT/'build/set-b-barrier-read-r1/binding.json'),candidate=binding['candidate'],
        owner_table=P.bind(OUT/'owner-table.json'),capacity=P.bind(OUT/'capacity-worksheet.json'),
        access_ledger=P.bind(OUT/'access-ledger.json'),timeout_disposition=P.bind(OUT/'timeout-disposition.json'),
        this_commission=dict(compiler_calls=0,dependency_calls=0,assembler_calls=0,host_c_runs=0,product_builds=0,
            product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,new_source_forms=0),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        next_recommendation='Review one coherent storage-and-recovery scope: price a mutable subowner inside existing late-region padding plus durable quarantine/rollback admission, preserving floors and boot. Do not continue local-buffer substitutions. First bind layout/write-watch and exact timeout/reentry behavior in a host-only design; no source/build/Seed until that binding closes.',
        limits='Current sources/map and inherited non-LTO projection only. No new target layout or permission to consume sealed padding. No exhaustive whole-RAM impossibility or new hardware-defect claim.'))
    print('WORKSHEET HALT: scratch tail at most61/64; low BSS pre-charge8; Bank5 tail spendable0; quarantine/reentry unbound;74 roots unchanged')


def seal():
    PREVIOUS.check();S.require_auth()
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    receipt=P.load(OUT/'receipt.json')
    selected={p for p in OUT.rglob('*') if p.is_file()}
    selected.update(SOURCES+AUTHORITIES+[REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT])
    selected.update(local_import_closure([Path(__file__)]))
    external=[external_binding(Path(shutil.which(n)).resolve()) for n in ('python3','rg')]
    def bindings(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                row={k:value[k] for k in ('path','bytes','sha256')};path=ROOT/row['path']
                if path.is_relative_to(ROOT):assert P.bind(path)==row,row['path'];selected.add(path)
                else:assert external_binding(path)==row;external.append(row)
            else:
                for item in value.values():bindings(item)
        elif isinstance(value,list):
            for item in value:bindings(item)
    for path in OUT.glob('*.json'):bindings(P.load(path))
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue873730db: host-only lifetime/ownership and capacity worksheet. Existing disjoint destination, access/reuse edges, bounded timeout/reentry; stop at precise owner/capacity conflict. Zero compiler/dependency/assembler/build/link/Seed/guest/device, no second source form.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-barrier-read-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        row=P.bind(path);inputs.append(row)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=row,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status=receipt['status'],execution_head=HEAD,source_authority=receipt['source_authority'],
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(OUT/'receipt.json'),predecessor=P.bind(PREVIOUS.SEAL),
        inputs=inputs,receipt_copies=copies,external_tools=external,this_commission=receipt['this_commission'],
        consumed=receipt['consumed'],authorized_ceiling=receipt['authorized_ceiling'],accepted_world='Card L Final',public_release='2.4.0',product_admitted=False))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies')


def check():
    value=P.load(SEAL)
    for row in value['inputs']+[value['owner_scope']]:assert P.bind(ROOT/row['path'])==row,row['path']
    for row in value['external_tools']:assert external_binding(Path(row['path']))==row
    for row in value['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy'];raw=path.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes'] and hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    PREVIOUS.check();S.require_auth();print('PASS barrier-owner seal:74 roots, candidate, arithmetic worksheet, source edges and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('audit','seal','check'))
    {'audit':audit,'seal':seal,'check':check}[parser.parse_args().mode]()
