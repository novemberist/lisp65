"""Owner-selected CLEAR rollback protocol and bounded reuse model; no compilation."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_barrier_design_20260926 as PREVIOUS
import set_b_clear_protocol_model_20260926 as MODEL
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=ROOT/'build/set-b-clear-protocol-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-clear-protocol-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-clear-protocol-report.md'
HEAD='fe469f02'
CANDIDATE=ROOT/'build/set-b-barrier-read-r1/candidate'
SOURCES=PREVIOUS.SOURCES+[
    ROOT/'src/optional/c2_map_cpu_read.s', ROOT/'src/error_codes.h', ROOT/'src/interrupt.c', ROOT/'src/symbol.c',
    ROOT/'tools/host-lisp/set_b_producer.py',
]
AUTHORITIES=PREVIOUS.AUTHORITIES+[
    ROOT/'build/set-b-barrier-owner-r1/receipt.json',
    ROOT/'build/set-b-barrier-owner-r1/access-addendum.json',
    ROOT/'build/set-b-barrier-owner-r1/capacity-worksheet.json',
]


def audit():
    PREVIOUS.check();authority=S.require_auth()
    old=P.load(PREVIOUS.OUT/'receipt.json')
    for row in old['compiler_inputs']+old['candidate']:
        assert P.bind(ROOT/row['path'])==row
    assert not SEAL.exists()
    OUT.mkdir(exist_ok=True)
    runtime=(CANDIDATE/'src/c2_product_runtime.c').read_text()
    api=(ROOT/'src/c2_product_runtime.h').read_text()
    assert '#define LISP65_C2D_BYTES 33840u' in api
    assert '#define C2_EXPORT_PLAN_LIMIT 48384u' in runtime
    assert '#define C2_EXPORT_PLAN_RECORD_BYTES 8u' in runtime
    assert '#define C2_EXPORT_JOURNAL_RECORD_BYTES 4u' in runtime
    assert 'static uint16_t c2_journal_count;' in runtime
    assert 'count == (uint16_t)((C2_EXPORT_PLAN_LIMIT' in runtime
    assert 'while (c2_journal_count)' in runtime
    assert 'c2_facade_gc_mark((obj)((uint16_t)b[2]' in runtime
    cp=P.load(ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json')
    # Inspect recorded arguments without executing preprocessor or compiler.
    encoded=(ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json').read_text()
    for flag in ('-DLISP65_C2_TWO_REGION_SESSION_STORE','-DLISP65_C2_LITE_V6_CORESIDENT_DIET'):
        assert flag in encoded
    producer=(ROOT/'tools/host-lisp/set_b_producer.py').read_text()
    assert 'image[extent:]=bytes([0xa5])*(8192-extent)' in producer
    result=MODEL.run()
    P.write(OUT/'model-rows.json',result)
    base=MODEL.BASE;limit=MODEL.LIMIT;n=MODEL.MAX_COUNT
    assert (n,base+4*n,base+8*n)==(1818,41112,48384)
    layout=dict(export_base=base,export_limit=limit,max_count=n,scan_capacity_bytes=limit-base,
        primary_formula='[B,B+4N)',backup_formula='[B+4N,B+8N)',copy_bytes='4K, 0 <= K <= N',
        max_primary=[base,base+4*n],max_backup=[base+4*n,limit],new_export_bytes=0,
        capsule_start=0x5f900,capsule_end_exclusive=0x5fa20,capsule_bytes=288,
        fields=[dict(start=0x5f900,bytes=64,owner='observed'),dict(start=0x5f940,bytes=64,owner='expected'),
            dict(start=0x5f980,bytes=64,owner='retained C2J'),dict(start=0x5f9c0,bytes=48,owner='predecessor header'),
            dict(start=0x5f9f0,bytes=32,owner='control'),dict(start=0x5fa10,bytes=16,owner='reserved guard')],
        control={'state':1,'mode':1,'disposition':1,'pending':1,'generation':2,'seal':2,'start_frame':2,
            'plan_N':2,'published_K':2,'replay_cursor':2,'error':1,'flags':1,'direction':1,'cleanup':1,'root_authority':1,'reserved':11},
        remaining_late_padding=1120,tail_floor=374,tail_spendable=0,additional_BSS=0,
        initial_padding='Producer uses A5 after aligned extent; full-image CRC before runtime initialization. Corrects previous report zero-padding wording.',
        scope='All N 0..1818 checked arithmetically; not a claim every N is reachable under other product caps.')
    assert sum(layout['control'].values())==32
    assert sum(f['bytes'] for f in layout['fields'])==288
    P.write(OUT/'layout.json',layout)
    P.write(OUT/'binding.json',dict(owner_answer='Vollständige Rücknahme (empfohlen)',
        semantic_rule='Timed-out publishing transaction is rolled back after its ordered witness retires; no successful callable publication survives that recovery.',
        critical_order=['latch N/K and durable recovery facts; prohibit allocation/GC/retirement and ordinary unwind',
            'ordered DMA copy compacted 4K-byte primary undo into upper half after prior producers',
            'ordered clear lower 4N bytes, then C2J, then one disjoint trailing read',
            'timeout latches ABORT irrevocably; bounded native reentry observes same witness only',
            'after witness enter READY_TO_FINISH; retain backup through caller transaction_end and all fallible finalizers; ABORT restores from immutable backup',
            'rollback CLEAR never recopies primary; retain backup through any repeated timeout',
            'after rollback witness, synchronous scrub entire owned 8N span, then release and ordinary unwind'],
        error=dict(install_publish=43,internal='C2_STREAM_ERR_IO',load='existing false/nil',capacity='existing OOM',stop='preserve original STOPPED/error authority'),
        execution_limit='Conceptual ordered-job model only. Target code, CRC implementation, root guard, reset, nested callers, timing and code size remain qualification gates.',
        implementation_budget=dict(compiler=0,dependency=0,assembler=0,build=0,link=0,seed=0,final=0,guest=0,device=0)))
    P.write(OUT/'receipt.json',dict(status='TERMINAL CONTRACT AND ABSTRACT MODEL COMPLETE; PRODUCT IMPLEMENTATION NOT ADMITTED',
        execution_head=HEAD,source_authority=authority,driver=P.bind(Path(__file__)),model=P.bind(Path(MODEL.__file__)),
        predecessor=P.bind(PREVIOUS.SEAL),compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],
        candidate=old['candidate'],verified_compiler_roots=74,
        sources=[P.bind(p) for p in SOURCES],artifacts=[P.bind(p) for p in sorted(OUT.glob('*.json')) if p.name!='receipt.json'],
        model_summary=dict(geometry_counts=result['geometry_counts'],passing_rows=result['passing_rows'],falling_controls=len(result['falling_controls'])),
        this_commission=dict(compiler_calls=0,dependency_calls=0,assembler_calls=0,host_c_runs=0,product_builds=0,
            product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,new_source_forms=0),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        next_recommendation='One isolated host implementation card for the terminal protocol and synchronous writer, exact-C tests plus matched-object pricing under an explicitly bound budget; no product link or Seed.',
        limits='Owner-selected semantic contract, arithmetic capacity and abstract schedules only; unchanged product and 74 roots, inherited code margins not a new executable price.'))
    print('COMPLETE:',result['geometry_counts'],'count bounds;',result['passing_rows'],'abstract rows;3 falling controls;0 new export bytes;288 capsule bytes')

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
    scope=ARCH/STEM/'design-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Clarification: Vollständige Rücknahme (empfohlen). Continuefe469f02: bind undo retention, forward/rollback CLEAR and bounded quarantine. Host-only contract/model, zero compiler/dependency/assembler/build/link/Seed/Final/guest/device; no product source form.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-barrier-design-report.md'],cwd=ROOT,text=True))
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
    PREVIOUS.check();S.require_auth();print('PASS CLEAR protocol seal:74 roots, owner choice, source bounds, abstract schedules, lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('audit','seal','check'))
    {'audit':audit,'seal':seal,'check':check}[parser.parse_args().mode]()
