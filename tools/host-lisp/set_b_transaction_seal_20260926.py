"""Seal existing-Seed transaction trace and parked, object-priced repair."""
import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
from set_b_fourth_halt_seal_20260926 import local_import_closure
ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-transaction-boundary-repair-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-transaction-boundary-repair-proposal.md'


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    authority=S.require_auth()
    trace=P.load(ROOT/'build/set-b-transaction-trace-r1/receipt.json')
    assert trace['status']=='PASS: EXECUTED FOURTH SEED BOUNDARY ATTRIBUTION'
    proposal=P.load(ROOT/'build/set-b-transaction-proposal-r1/receipt.json')
    assert proposal['resident_delta']==193 and proposal['text_free_projection']==816
    checks=P.load(ROOT/'build/set-b-transaction-checks-r1/receipt.json')
    assert checks['host_c_rows']==11 and checks['status'].startswith('PASS')
    selected=set();excluded=[]
    for root in sorted((ROOT/'build').glob('set-b-transaction-*')):
        for p in root.rglob('*'):
            if not p.is_file():continue
            if p.name=='system-sd.img':excluded.append(dict(path=str(p.relative_to(ROOT)),reason='Disposable private 4 GiB SD copy; consumed D81 and memory preserved'))
            else:selected.add(p)
    selected.update(ROOT/p for p in S.authority_files())
    selected.update(local_import_closure(sorted((ROOT/'tools/host-lisp').glob('set_b_transaction_*_20260926.py'))))
    for row in P.load(ROOT/'build/set-b-transaction-proposal-r1/dependencies.json'):
        for bound in row['inputs']:
            b=bound['binding'];assert P.bind(ROOT/b['path'])==b;selected.add(ROOT/b['path'])
    selected.update([REPORT,ROOT/'src/vm_runtime_overlay.c',ROOT/'src/optional/c2_map_cpu_read.s',
        ROOT/'scripts/xmega65-safe-run.sh',ROOT/'scripts/kill-xmega65-by-token.py',
        ROOT/'build/set-b-product-r4/commands.json',ROOT/'build/set-b-product-r4/set-b-tenants.bin',
        ROOT/'build/card-l-r1/instrument-comfort.json',
        ROOT/'build/input-cost-attribution-r6/xemu/targets/mega65/mega65.c',
        ROOT/'build/input-cost-attribution-r6/xemu/targets/mega65/uart_monitor.c',
        ARCH/'set-b-fourth-seed-activation-halt-20260926.json'])
    for key in ['ELF','medium','binary']:selected.add(ROOT/trace['world'][key]['path'])
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Bitte genau damit fortfahren. Existing-Seed trace and repair design only.\n\n'+
        subprocess.check_output(['git','show','38f882d6:docs/planning/post-2.4.0-plan.md'],cwd=ROOT,text=True))
    inputs=[];copies=[]
    for p in sorted(selected):
        b=P.bind(p);inputs.append(b)
        if not p.is_relative_to(ROOT/'build'):continue
        raw=p.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/p.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=b,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    compiler=Path(P.load(ROOT/'build/set-b-transaction-checks-r1/commands.json')[0]['command'][0])
    raw=compiler.read_bytes();host_compiler=dict(path=str(compiler),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    P.write(SEAL,dict(status='HOST ATTRIBUTION AND REPAIR DESIGN COMPLETE; PRODUCT QUALIFICATION HALTED',
        authority=authority,scope_authority='38f882d6 plus owner continuation',owner_scope=P.bind(scope),
        report=P.bind(REPORT),seed=trace['world']['ELF'],medium=trace['world']['medium'],patch=proposal['patch'],
        maintained_native_source_unchanged=True,accepted_world='Card L Final',public_release='2.4.0',
        consumed=dict(seed_attempts=4,finals=0,product_link_attempts=4),
        proposed_ceiling=dict(seed_attempts=5,finals=1,product_link_attempts=5),
        proposed_resident_admission=439,further_product_link_authorized=False,
        this_continuation=dict(guest_launches=1,native_object_compiles=2,dependency_only_calls=2,host_test_compiles=1,host_test_links=1,product_links=0,seeds=0,finals=0,observer_builds=0,device_contacts=0),
        inputs=inputs,receipt_copies=copies,excluded=excluded,host_compiler=host_compiler))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies')


def check():
    s=P.load(SEAL)
    for b in s['inputs']+[s['owner_scope']]:assert P.bind(ROOT/b['path'])==b,b['path']
    b=s['host_compiler'];raw=Path(b['path']).read_bytes();assert len(raw)==b['bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256']
    for row in s['receipt_copies']:
        a,b=row['source'],row['copy'];assert P.bind(ROOT/b['path'])==b
        raw=(ROOT/b['path']).read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==a['bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
    print('PASS transaction repair seal; all bindings and lossless copies')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['create','check']);a=ap.parse_args()
    create() if a.mode=='create' else check()
