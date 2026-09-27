"""Seal read-only scanner-sharing source and exact linked-byte evidence."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_prototype_seal_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding
from set_b_fourth_halt_seal_20260926 import local_import_closure

ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-scanner-reuse-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-scanner-reuse-report.md'
RECEIPT=ROOT/'build/set-b-scanner-reuse-audit-r1/receipt.json'

def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    PREVIOUS.check();authority=S.require_auth();r=P.load(RECEIPT)
    assert r['this_commission']['compiler_calls']==0
    selected={REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT}
    for root in (ROOT/'build').glob('set-b-scanner-reuse-*'):
        selected.update(p for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file())
    def bind(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                row={k:value[k] for k in ('path','bytes','sha256')};p=ROOT/row['path']
                assert P.bind(p)==row;selected.add(p)
            else:
                for v in value.values():bind(v)
        elif isinstance(value,list):
            for v in value:bind(v)
    for p in sorted(selected):
        if p.name in ('receipt.json','source-witnesses.json'):bind(P.load(p))
    selected.update(ROOT/p for p in S.authority_files())
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_scanner_reuse*_20260926.py'))))
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue the read-only scanner sharing and lifetime audit recommended by 5960ef83. No compiler, product change, build, link, Seed, guest or device.\n\n'+
        subprocess.check_output(['git','show','5960ef83:docs/planning/set-b-front-prototype-report.md'],cwd=ROOT,text=True))
    inputs=[];copies=[]
    for p in sorted(selected):
        b=P.bind(p);inputs.append(b)
        if not p.is_relative_to(ROOT/'build'):continue
        raw=p.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/p.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=b,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status=r['status'],execution_head='5960ef83',source_authority=authority,
        owner_scope=P.bind(scope),report=P.bind(REPORT),receipt=P.bind(RECEIPT),predecessor=P.bind(PREVIOUS.SEAL),
        accepted_world='Card L Final',public_release='2.4.0',consumed=r['consumed'],authorized_ceiling=r['authorized_ceiling'],
        this_commission=r['this_commission'],inputs=inputs,receipt_copies=copies,
        toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ('llvm-objdump','llvm-readobj')],
        external_toolchain=[external_binding(Path(shutil.which('python3')))],limits=r['limits']))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies')

def check():
    r=P.load(SEAL)
    for b in r['inputs']+r['toolchain']+[r['owner_scope']]:assert P.bind(ROOT/b['path'])==b,b['path']
    for b in r['external_toolchain']:assert external_binding(Path(b['path']))==b
    for b in r['receipt_copies']:
        p=ROOT/b['copy']['path'];assert P.bind(p)==b['copy'];raw=p.read_bytes()
        if b['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==b['source']['bytes'] and hashlib.sha256(raw).hexdigest()==b['source']['sha256']
    S.require_auth();print('PASS scanner-sharing seal: authority, linked inputs and lossless copies')

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('mode',choices=('create','check'))
    create() if a.parse_args().mode=='create' else check()
