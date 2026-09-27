"""Seal the read-only certificate writer audit and conditional design model."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_load_batch_seal_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding
from set_b_fourth_halt_seal_20260926 import local_import_closure

ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-front-certificate-design-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-front-certificate-design.md'
CLOSURE=ROOT/'build/set-b-front-certificate-close-r1/receipt.json'

def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    PREVIOUS.check();authority=S.require_auth();closure=P.load(CLOSURE)
    assert closure['status']=='DESIGN COMPLETE; IMPLEMENTATION NOT ADMITTED UNTIL WRITER/REFILL/FAULT GATES ARE BOUND'
    assert not closure['new_product_budget_requested']
    selected=set()
    for root in sorted((ROOT/'build').glob('set-b-front-certificate-*')):
        selected.update(p for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file())
    def add_bindings(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                bound={k:value[k] for k in ('path','bytes','sha256')};path=ROOT/bound['path']
                assert P.bind(path)==bound,bound['path'];selected.add(path)
            else:
                for item in value.values():add_bindings(item)
        elif isinstance(value,list):
            for item in value:add_bindings(item)
    for path in sorted(selected):
        if path.name in ('receipt.json','binding.json','source-witnesses.json'):
            add_bindings(P.load(path))
    selected.update(ROOT/p for p in S.authority_files())
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_front_certificate*_20260926.py'))))
    selected.update([REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT,
        ROOT/'build/set-b-product-r5/commands.json',
        ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81',
        ROOT/'build/set-b-seed-medium-r6/base/init.l65',
        ROOT/'build/set-b-load-preflight-cost-r1/receipt.json',
        ROOT/'build/set-b-load-preflight-native-r2/receipt.json',
        ROOT/'build/set-b-load-batch-close-r1/receipt.json',
        ROOT/'src/optional/set_b_retire_common.h',ROOT/'src/c2_product_runtime.h',
        ROOT/'src/c2_kernal_facade.s',ROOT/'src/c2_kernal_runtime.c',
        ROOT/'src/attic_library_shelf.c',ROOT/'lib/stdlib-q.lisp'])
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Dann bitte gemäß deiner Empfehlung fortfahren. '
        'Continue the host-only validated-front design/writer audit proposed in 5f9309fb; '
        'no implementation, compiler, product build/link/Seed/device.\n\n'+
        subprocess.check_output(['git','show','5f9309fb:docs/planning/set-b-library-load-batch-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        bound=P.bind(path);inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ('llvm-objdump','llvm-readobj','mos-mega65.cfg')]
    P.write(SEAL,dict(status=closure['status'],source_authority=authority,execution_head='5f9309fb',
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(CLOSURE),predecessor_seal=P.bind(PREVIOUS.SEAL),
        accepted_world='Card L Final',public_release='2.4.0',consumed=closure['consumed'],authorized_ceiling=closure['authorized_ceiling'],
        implementation_or_further_product_attempt_authorized=False,
        this_commission=closure['this_commission'],audit_attempts=2,discarded_audit_attempts=1,
        inputs=inputs,receipt_copies=copies,toolchain=toolchain,
        external_toolchain=[external_binding(Path(shutil.which('python3')))],
        limits='Direct sink census and Python design model; raw-I/O writer mediation, warm failure successor, native barrier/refill costs and lifetime remain unproved. No new product defect claimed.'))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless archive copies')

def check():
    seal=P.load(SEAL)
    for row in seal['inputs']+seal['toolchain']+[seal['owner_scope']]:
        assert P.bind(ROOT/row['path'])==row,row['path']
    for row in seal['external_toolchain']:
        assert external_binding(Path(row['path']))==row,row['path']
    for row in seal['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy']
        raw=path.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes']
        assert hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    S.require_auth()
    print('PASS certificate-design seal: source authority, identities and lossless copies')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('create','check'))
    create() if parser.parse_args().mode=='create' else check()
