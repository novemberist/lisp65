"""Seal the read-only phase04/05a placement and aggregate-capacity plan."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_integration_seal_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding
from set_b_fourth_halt_seal_20260926 import local_import_closure

ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-front-placement-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-front-placement-report.md'
CLOSURE=ROOT/'build/set-b-front-placement-r1/receipt.json'

def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    PREVIOUS.check();authority=S.require_auth();closure=P.load(CLOSURE)
    assert closure['status'].startswith('READ-ONLY PLACEMENT') and not closure['product_admitted']
    selected=set()
    for root in sorted((ROOT/'build').glob('set-b-front-placement-*')):
        selected.update(p for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file())
    def bindings(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                bound={k:value[k] for k in ('path','bytes','sha256')};path=ROOT/bound['path']
                assert P.bind(path)==bound,bound['path'];selected.add(path)
            else:
                for item in value.values():bindings(item)
        elif isinstance(value,list):
            for item in value:bindings(item)
    for path in sorted(selected):
        if path.name in ('receipt.json','binding.json','commands.json'):bindings(P.load(path))
    selected.update(ROOT/p for p in S.authority_files())
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_front_placement*_20260926.py'))))
    selected.update([REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT,ROOT/'build/set-b-product-r5/commands.json',
        ROOT/'build/set-b-load-repair-proposal-r5/candidate/lib/stdlib-require.lisp',
        ROOT/'build/set-b-load-repair-proposal-r5/candidate/src/optional/set_b_retire_reset.c',
        ROOT/'build/set-b-load-repair-proposal-r5/candidate/src/optional/set_b_retire_control.c'])
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue the read-only ownership/lifetime and aggregate-capacity recommendation after 9a9789b1. No candidate C or compiler/product build/link/Seed/guest/device.\n\n'+
        subprocess.check_output(['git','show','9a9789b1:docs/planning/set-b-front-integration-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        bound=P.bind(path);inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status=closure['status'],source_authority=authority,execution_head='9a9789b1',
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(CLOSURE),predecessor=P.bind(PREVIOUS.SEAL),
        accepted_world='Card L Final',public_release='2.4.0',consumed=closure['consumed'],authorized_ceiling=closure['authorized_ceiling'],
        product_integration_or_further_product_attempt_authorized=False,selected_revision=None,
        this_commission=closure['this_commission'],inputs=inputs,receipt_copies=copies,
        toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ('llvm-readobj',)],
        external_toolchain=[external_binding(p) for p in (Path(shutil.which('python3')),)],
        limits=closure['limits']))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies; placement, arithmetic and capacity bounds retained')

def check():
    seal=P.load(SEAL)
    for row in seal['inputs']+seal['toolchain']+[seal['owner_scope']]:assert P.bind(ROOT/row['path'])==row,row['path']
    for row in seal['external_toolchain']:assert external_binding(Path(row['path']))==row
    for row in seal['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy'];raw=path.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes'] and hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    S.require_auth();print('PASS front-placement seal: authority, toolchain, dependency closure and lossless copies')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('create','check'))
    create() if p.parse_args().mode=='create' else check()
