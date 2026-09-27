"""Host-only barrier storage/recovery design; arithmetic and abstract model, no compilation."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_barrier_owner_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=ROOT/'build/set-b-barrier-design-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-barrier-design-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-barrier-design-report.md'
HEAD='220415d1'
CANDIDATE=ROOT/'build/set-b-barrier-read-r1/candidate'
SOURCES=PREVIOUS.SOURCES+[
    ROOT/'src/optional/c2_map_cpu_read.s', ROOT/'src/error_codes.h',
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
    assert old['verified_compiler_roots']==74
    OUT.mkdir(exist_ok=False)
    runtime=(CANDIDATE/'src/c2_product_runtime.c').read_text()
    anchors={
        'clear_zeros_export_undo':'C2_EXPORT_JOURNAL_BASE\n                    + i * C2_EXPORT_SCRATCH_RECORD_BYTES',
        'compact_undo_width':'#define C2_EXPORT_JOURNAL_RECORD_BYTES 4u',
        'undo_old_function':'c2_record_u16(row + 2, (uint16_t)sym_function((obj)symbol));',
        'publish_requires_commit':'if (!w || !w->committed || C2AW_PLAN_MARK(w))',
        'timeout_is_stream_io':'if (!c2_completion_poll(w, mode, 0))\n            return C2_STREAM_ERR_IO;',
        'failure_rollback':'v5_fail:\n    if (!c2_append_run_rollback_plan(&c2aw)) {\n        c2_ready = 0;',
        'caller_public_error':'vm_status = append_ok == C2_APPEND_BEGIN_CAPACITY ? VM_HEAPOOM : VM_BADOPCODE;',
        'caller_frame_pointer':'c2aw.before = before; c2aw.main_ordinal = main_ordinal;',
    }
    for name,fragment in anchors.items(): assert fragment in runtime,name
    assert 'LISP65_ERR_VM_BAD_BYTECODE = 43' in (ROOT/'src/error_codes.h').read_text()
    lines=runtime.splitlines()
    P.write(OUT/'source-anchors.json',dict(source=P.bind(CANDIDATE/'src/c2_product_runtime.c'),
        anchors=[dict(name=k,fragment=v,line=runtime[:runtime.index(v)].count('\n')+1) for k,v in anchors.items()],
        note='Source attribution, not executed product behavior; same active consumer families as predecessor.'))
    packing=P.load(ROOT/'build/set-b-front-span-capacity-r1/packing.json')
    late=next(r for r in packing['regions'] if r['region']==3)
    base=0x5de80+late['projected_used'];end=0x5de80+late['limit']
    assert (base,end,end-base)==(0x5f900,0x5fe80,1408)
    spans=[]
    cursor=base
    for name,size in [('observed',64),('expected_header_or_seal_domain',64),
                      ('retained_C2J',64),('predecessor_header',48),('control',16)]:
        spans.append(dict(name=name,start=cursor,end_exclusive=cursor+size,bytes=size));cursor+=size
    assert cursor-base==256 and end-cursor==1152
    assert 0x60000-(end+10)==374
    P.write(OUT/'layout.json',dict(status='PROPOSED PARTITION ONLY; NOT ADMITTED',packing=P.bind(ROOT/'build/set-b-front-span-capacity-r1/packing.json'),
        spans=spans,base=base,end_exclusive=cursor,bytes=256,remaining_padding=1152,
        separate_header=dict(start=end,bytes=10),tail_floor=374,tail_spendable=0,
        control_fields=[['state',1],['mode',1],['disposition',1],['pending',1],['generation',2],
            ['seal',2],['start_frame',2],['export_count',2],['error_code',1],['flags',1],['reserved_zero',2]],
        missing='Variable export before-images and full nested recovery/root closure; no pointer survives unwind.'))
    # Two explicit abstract histories: exactly the information retained by this
    # proposed capsule, not emulated C or a reachability claim about hardware.
    histories=[]
    for old_function in (0x1234,0x5678):
        undo=bytes([0x21,0x80,old_function&255,old_function>>8])
        retained=dict(mode='CLEAR',error_code=43,header='same',journal='same',
            published_function=0x6789,observed='poison; read pending',export_undo=[0,0,0,0])
        histories.append(dict(before_function=old_function,undo_before=list(undo),after_clear=retained))
    assert histories[0]['after_clear']==histories[1]['after_clear']
    assert histories[0]['before_function']!=histories[1]['before_function']
    P.write(OUT/'clear-counterexample.json',dict(status='DESIGN COUNTEREXAMPLE: selected capsule cannot determine original function value',
        histories=histories,scope='Python data construction and equality only; no C, target, guest, device or new product-defect class claim.',
        schedule=['Header proven and export cells published; undo rows contain old functions.',
            'CLEAR writes zero the export scratch then C2J; ordered trailing read remains pending at deadline.',
            'Selected capsule retains C2J/header/control but no export old-function words.',
            'After eventual read delivery, generic rollback lacks original function identity.'],
        limit='Does not prove all storage/recovery designs impossible. Retain undo elsewhere or define a distinct terminal commit outcome; neither is admitted here.'))
    price=P.load(ROOT/'build/set-b-front-span-capacity-r1/receipt.json')
    P.write(OUT/'price.json',dict(status='DATA PRICE EXACT; EXECUTABLE PRICE UNMEASURED AND NOT BOUND',
        data_bytes=256,extra_BSS_requested=0,remaining_internal_padding=1152,
        inherited=dict(ordinary_margin=8,E000_margin=25,capture_margin=48,conservative_BSS_margin=1,
            session_region0_used=65205,session_region0_spendable=0,phase05b_margin=5),
        code_obligations=[
            dict(owner='ordinary MAP transport',change='new synchronous physical CPU writer; reuse existing direct c2_map_cpu_read for samples',bytes=None),
            dict(owner='resident E000/ordinary transaction callers and REPL abort',change='quarantine dispatch before scratch release, retirement, rendering, compilation and restaging',bytes=None),
            dict(owner='cold slot39 header, slot40 publish/clear',change='durable prepare, one Bank5 DMA read, CPU sampling, mode-specific terminal recovery',bytes=None),
            dict(owner='late tenants control/reset',change='preserve pending capsule and gate late image restaging',bytes=None)],
        constraint='1152 remaining Bank5 data bytes are not automatically executable ordinary/E000 air. No target compiler run, no invented byte estimate, no executable capacity pass.',
        predecessor=P.bind(ROOT/'build/set-b-front-span-capacity-r1/receipt.json')))
    P.write(OUT/'receipt.json',dict(status='DESIGN HALT: CLEAR terminal recovery and live-session/code closure unresolved',
        execution_head=HEAD,driver=P.bind(Path(__file__)),source_authority=authority,
        predecessor=P.bind(PREVIOUS.SEAL),compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],
        verified_compiler_roots=74,candidate=old['candidate'],
        artifacts=[P.bind(p) for p in sorted(OUT.glob('*.json'))],
        this_commission=dict(compiler_calls=0,dependency_calls=0,assembler_calls=0,host_c_runs=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,new_source_forms=0),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        next_recommendation='Reviewer disposition of CLEAR commit/undo retention and restricted native quarantine before any implementation/pricing commission; no further local buffer substitution.',
        limits='Source-backed design and abstract counterexample only; layout uses consumed span projection, not a newly linked target. No hardware defect or universal impossibility claim.'))
    print('DESIGN HALT:256 data bytes fit; CLEAR undo absent; code/live-session closure unbound;74 roots unchanged')

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
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue220415d1: one host-only storage-and-recovery design, zero compiler/dependency/assembler/build/link/Seed/guest/device; no source form before closure; halt if bounds/live-session contract cannot close.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-barrier-owner-report.md'],cwd=ROOT,text=True))
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
    PREVIOUS.check();S.require_auth();print('PASS barrier-design seal:74 roots, unchanged candidate, layout and CLEAR design counterexample, lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('audit','seal','check'))
    {'audit':audit,'seal':seal,'check':check}[parser.parse_args().mode]()
