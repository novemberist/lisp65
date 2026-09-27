"""Seal the isolated certificate C rows and native object admission halt."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_certificate_seal_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding
from set_b_fourth_halt_seal_20260926 import local_import_closure

ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-front-prototype-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-front-prototype-report.md'
CLOSURE=ROOT/'build/set-b-front-prototype-close-r1/receipt.json'

def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    PREVIOUS.check();authority=S.require_auth();closure=P.load(CLOSURE)
    assert closure['status']=='HALT: ISOLATED CERTIFICATE KERNEL EXCEEDS ORDINARY-TEXT OBJECT ENVELOPE'
    assert not closure['new_product_budget_requested']
    selected=set()
    for root in sorted((ROOT/'build').glob('set-b-front-prototype-*')):
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
        if path.name in ('receipt.json','binding.json','commands.json'):add_bindings(P.load(path))
    selected.update(ROOT/p for p in S.authority_files())
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_front_prototype*_20260926.py'))))
    selected.update([REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT,ROOT/'build/set-b-product-r5/commands.json',
        ROOT/'build/set-b-load-repair-proposal-r5/candidate/lib/stdlib-require.lisp',
        ROOT/'build/set-b-load-repair-proposal-r5/candidate/src/optional/set_b_retire_reset.c',
        ROOT/'build/set-b-load-repair-proposal-r5/candidate/src/optional/set_b_retire_control.c',
        ROOT/'config/set-b-native/linker/c2-substitution.ld'])
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Bitte fortfahren. Continue the isolated host-only C prototype and object pricing recommended in 117e925b. '
        'No product build/link/Seed/guest/device. Stop on admission failure.\n\n'+
        subprocess.check_output(['git','show','117e925b:docs/planning/set-b-front-certificate-design.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        bound=P.bind(path);inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    commands=P.load(ROOT/'build/set-b-front-prototype-native-r1/commands.json')
    native_compiler=(ROOT/commands[0]['command'][0]).resolve()
    toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ('llvm-objdump','llvm-readobj','mos-mega65.cfg')]
    P.write(SEAL,dict(status=closure['status'],source_authority=authority,execution_head='117e925b',
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(CLOSURE),predecessor_seal=P.bind(PREVIOUS.SEAL),
        accepted_world='Card L Final',public_release='2.4.0',consumed=closure['consumed'],authorized_ceiling=closure['authorized_ceiling'],
        product_integration_or_further_product_attempt_authorized=False,
        this_commission=closure['this_commission'],inputs=inputs,receipt_copies=copies,toolchain=toolchain,
        external_toolchain=[external_binding(p) for p in (Path(shutil.which('python3')),Path(shutil.which('cc')),native_compiler)],
        limits=closure['limits']))
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
    print('PASS prototype seal: authority, toolchain, object dependencies and lossless copies')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('create','check'))
    create() if parser.parse_args().mode=='create' else check()
