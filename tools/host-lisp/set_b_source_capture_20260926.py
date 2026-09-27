"""Read-only source-capture attribution; no compiler, simulation or device execution."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_clear_c_preflight_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding

ROOT=P.ROOT
OUT=ROOT/'build/set-b-source-capture-r1'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-source-capture-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-source-capture-report.md'
HEAD='d97b1a30'
CORE=ROOT/'build/upstream-verification/mega65-core'
REV='a9158930665763c592d004c895d52eff4a9eefc3'
RTL=CORE/'src/vhdl/gs4510.vhdl'
SOURCES=PREVIOUS.SOURCES+[RTL]
AUTHORITIES=PREVIOUS.AUTHORITIES+[ROOT/p for p in (
    'config/c2-runtime-overlay-dma-completion-contract.json',
    'config/c2-cpu-chip-write-completion-contract.json',
    'config/g6-hardware-profile.json',
    'docs/planning/c2.2-runtime-overlay-dma-completion-contract.md',
    'docs/planning/c2.2-symbol-read-completion-investigation.md',
    'docs/upstream-findings.md',
    'build/set-b-front-ordering-r1/chipset-page84.txt',
    'build/set-b-front-ordering-r1/pdf-extraction.json',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link59-C1-Freezer-cutpoint4-late-chip-write-hardware-first-red.json')]

# Attribution anchors, not an RTL simulator or a formal exhaustiveness proof.
SPANS=[
 ('source-and-waits',5326,5459,['memory_read_value := read_data;',"if proceed = '0' then",'case state is']),
 ('descriptor-entry',5762,5777,['state <= DMAgicReadList;','state <= DMAgicReadOptions;']),
 ('read-ahead',6359,6378,['when DMAgicCopyRead =>','1 byte buffer']),
 ('source-latch',6548,6595,['state <= DMAgicCopyWrite;','reg_t <= memory_read_value;','state <= DMAgicCopyRead;']),
 ('job-terminal',6767,6805,['if dmagic_count = 1 then',"if dmagic_cmd(2) = '0' then",'state <= normal_fetch_state;','state <= DMAgicTrigger;']),
 ('trigger',8926,8963,['x"FFD3700"','x"FFD3705"','state <= DMAgicTrigger;','reg_pc <= reg_pc;']),
 ('bus-read-write',9707,9760,['memory_access_address := dmagic_src_addr(35 downto 8);','memory_access_wdata := reg_t;']),
 ('monitor-exception',5578,5640,['when ProcessorHold =>',"if monitor_mem_setpc='1' then"]),
]


def audit():
    PREVIOUS.check();authority=S.require_auth()
    assert subprocess.check_output(['git','rev-parse','--short=8','HEAD'],cwd=ROOT,text=True).strip()==HEAD
    old=P.load(PREVIOUS.OUT/'receipt.json')
    for row in old['compiler_inputs']+old['candidate']:assert P.bind(ROOT/row['path'])==row
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=CORE,text=True).strip()==REV
    assert subprocess.check_output(['git','status','--porcelain'],cwd=CORE,text=True)==''
    blob=subprocess.check_output(['git','show',REV+':src/vhdl/gs4510.vhdl'],cwd=CORE)
    assert RTL.read_bytes()==blob
    documented=P.load(ROOT/'config/c2-runtime-overlay-dma-completion-contract.json')['documented_semantics']
    pdf=ROOT/documented['chipset_reference']['path']
    assert P.bind(pdf)['sha256']==documented['chipset_reference']['sha256']
    extraction=P.load(ROOT/'build/set-b-front-ordering-r1/pdf-extraction.json')
    assert P.bind(pdf)==extraction['source']
    assert P.bind(ROOT/extraction['result']['path'])==extraction['result']
    OUT.mkdir(exist_ok=False)
    shutil.copytree(ROOT/'build/set-b-source-capture-attempt1',OUT/'attempt-1')
    lines=blob.decode().splitlines();rows=[]
    for name,start,end,tokens in SPANS:
        raw='\n'.join(lines[start-1:end])+'\n'
        for token in tokens:assert token in raw,(name,token)
        path=OUT/(name+'.txt')
        path.write_text(''.join(f'{i}: {lines[i-1]}\n' for i in range(start,end+1)))
        rows.append(dict(id=name,start=start,end=end,required_tokens=tokens,excerpt=P.bind(path)))
    P.write(OUT/'rtl-attribution.json',dict(revision=REV,source=P.bind(RTL),git_blob_equal=True,
        git_blob_id=subprocess.check_output(['git','rev-parse',REV+':src/vhdl/gs4510.vhdl'],cwd=CORE,text=True).strip(),
        checkout_clean=True,spans=rows,proof_kind='Static normal-copy CPU/DMA state-path attribution, not simulation or full-core formal verification.',
        excludes=['Reset/watchdog, external debugger/monitor intervention, faulty bitstream or memory controller.',
                  'Physical identity of historical Link34/35/59 device; G6 profile covers a different commission.',
                  'Destination visibility, rollback ordering, permanent loss/truncation, current-device qualification.']))
    register=subprocess.check_output(['git','show',HEAD+':docs/reference/parked-items-register.md'],cwd=ROOT,text=True)
    attic=[r for r in register.splitlines() if r.startswith('| **Attic runtime refill')]
    assert len(attic)==1
    (OUT/'prior-register-attic-row.txt').write_text(attic[0]+'\n')
    late=P.load(AUTHORITIES[-1])
    assert late['captures']['bank2']['changed_bytes']==5
    assert len(late['captures']['bank5']['Freezer_delta']['export_journal_offsets'])==2
    P.write(OUT/'authority-table.json',dict(rows=[
        dict(id='manual',evidence='PDF84/printed70 promises CPU stall until DMA completion.',source_capture='Supports intended capture-before-reuse.',limit='Target convergence violated intended full completion historically.'),
        dict(id='pinned-rtl',evidence='D700/D705 enter DMA state; read data latched in reg_t, bus writes register; CPU resumes at terminal count.',source_capture='Normal-copy reference-source premise established.',limit='No device identity or memory-controller formal proof.'),
        dict(id='link35',evidence='Immutable source, target wrong at1ms, correct at691ms and2381ms.',source_capture='Cannot distinguish early from deferred source reads.',limit='Delayed target evidence remains.'),
        dict(id='link59',evidence='Five changed Bank2 bytes in nine-byte span; two export-journal bytes; ACTIVE otherwise unchanged.',source_capture='No source-reuse timing or source-fetch capture in receipt.',limit='Retain late-write protection; no current-world reproduction.'),
        dict(id='symbol-read-investigation',evidence='Single descriptor, fields filled before D700, memory clobber, no IRQ/NMI writer identified.',source_capture='Descriptor-reuse race not statically established.',limit='Missing hardware timing is not affirmative race evidence.'),
        dict(id='host-preflight',evidence='Four immediate/captured controls pass; deferred-source synthetic row sees two changed bytes.',source_capture='Keep policy3 as falling boundary control; use policy2 for reference-core qualification.',limit='Existing rows reused, no new host C run.'),
        dict(id='identity',evidence='Reference revision pinned; historical tested-core identity missing. G6 binding is media-only.',source_capture='Do not retroassign G6 or later TE0000B18447/git-03b24c6b to Link59.',limit='Exact hardware applicability remains a later qualification obligation.')]))
    P.write(OUT/'lookup-ledger.json',dict(local_checkout='Existing pinned checkout; no fetch or update.',
        web_issue='https://github.com/MEGA65/mega65-user-guide/issues/670',direct_fetch='Cache miss; no independently retrieved comment guarantee.',
        raw_rtl_fetch='Cache miss; exact local git blob used instead.',
        listing_only='Official issue listing names Enhanced Attic convergence issue; not source-capture evidence.',
        local_comment_authority=P.bind(OUT/'prior-register-attic-row.txt')))
    P.write(OUT/'receipt.json',dict(status='COMPLETE: reference-core source-capture premise attributed; no device admission',
        execution_head=HEAD,source_authority=authority,driver=P.bind(Path(__file__)),predecessor=P.bind(PREVIOUS.SEAL),
        compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],candidate=old['candidate'],
        verified_compiler_roots=74,rtl=P.bind(RTL),pdf=P.bind(pdf),
        artifacts=[P.bind(p) for p in sorted(OUT.rglob('*')) if p.is_file()],
        this_commission=dict(compiler_calls=0,host_link_attempts=0,dependency_calls=0,assembler_calls=0,native_object_calls=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,new_source_forms=0),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        next_recommendation='Resume the same CLEAR repair under explicit reference-core capture-before-return premise, retaining delayed-target/ordered-witness gates. Renew exhausted host budget before compile. Keep deferred-source row as a falling boundary control.',
        limit='Static source premise closes the conceptual source-ownership objection for host qualification only. No hardware proof, target-drain guarantee, lifetime of pending read destination, or product acceptance inferred.'))
    print('COMPLETE: pinned RTL capture-before-CPU-resume attribution; target/hardware gates unchanged; zero compiler/device')


def seal():
    PREVIOUS.check();S.require_auth()
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    receipt=P.load(OUT/'receipt.json')
    selected={p for p in OUT.rglob('*') if p.is_file()}
    selected.update(SOURCES+AUTHORITIES+[REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT])
    selected.update(local_import_closure([Path(__file__)]))
    external=[external_binding(Path(shutil.which(n)).resolve()) for n in ('python3','rg','git')]
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
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue d97b1a30 with the recommended read-only source-consumption authority audit. Zero compiler/dependency/assembler/native/product build/link/Seed/Final/guest/device. No renewed implementation budget inferred. Complete rollback remains selected.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-clear-c-preflight-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        row=P.bind(path);inputs.append(row)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072 or (path.is_relative_to(OUT) and path.suffix=='.txt');dest=ARCH/STEM/path.relative_to(ROOT)
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
    PREVIOUS.check();S.require_auth();print('PASS source-capture audit seal:74 roots, pinned RTL blob, authority boundaries and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('audit','seal','check'))
    {'audit':audit,'seal':seal,'check':check}[parser.parse_args().mode]()
