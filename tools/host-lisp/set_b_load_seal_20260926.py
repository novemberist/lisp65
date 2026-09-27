"""Seal the existing-Seed load attribution and parked host/object proposal."""
import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from set_b_fourth_halt_seal_20260926 import local_import_closure
ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-library-load-attribution-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-library-load-attribution-report.md'

def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    authority=S.require_auth()
    closure=ROOT/'build/set-b-load-analysis-r2/receipt.json';r=P.load(closure)
    assert r['status']=='PASS: MINIMAL REPRO AND FIRST REFUSING PREDICATE ATTRIBUTED'
    assert r['first_refusal']['gap']==10 and r['price']['reset_record_unchanged']==256
    for key in ['proposal','host_world','host_latch']:
        q=ROOT/r[key]['path'];assert P.bind(q)==r[key] and P.load(q)['status'].startswith('PASS:')
    selected=set();excluded=[];guests=[]
    for root in sorted((ROOT/'build').glob('set-b-load-*')):
        for p in ([root] if root.is_file() else root.rglob('*')):
            if not p.is_file():continue
            if p.name=='system-sd.img':
                excluded.append(dict(path=str(p.relative_to(ROOT)),reason='Disposable sparse private SD clone; exact medium, launch and stopped planes preserved'));continue
            selected.add(p)
            if p.name=='xemu.log':guests.append(P.bind(p))
    assert len(guests)==6,len(guests)
    selected.update(ROOT/p for p in S.authority_files())
    newtools=sorted((ROOT/'tools/host-lisp').glob('set_b_load*_20260926.py'))
    selected.update(local_import_closure(newtools))
    selected.update([REPORT,ARCH/'set-b-fifth-seed-workload-halt-20260926.json',
        ROOT/'lib/stdlib-require.lisp',ROOT/'lib/lcc.lisp',ROOT/'lib/prelude-m1.lisp',
        ROOT/'config/bytecode-abi-ledger.json',ROOT/'src/c2_bank2_code_domain.h',
        ROOT/'build/set-b-r1/step2/b-boundary.md',S.PRODUCT/'wplto/resident-island-seed.prg.elf',
        S.PRODUCT/'set-b-tenants.bin',ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81',
        ROOT/'scripts/xmega65-safe-run.sh',ROOT/'scripts/kill-xmega65-by-token.py'])
    for name in ['xemu/cpu65.c','xemu/cpu65_mega65_timings.h','targets/mega65/mega65.c','targets/mega65/uart_monitor.c','build/bin/xmega65.native']:
        selected.add(ROOT/'build/input-cost-attribution-r6/xemu'/name)
    # Bound compiler input closure for the two non-LTO object projections.
    for row in P.load(ROOT/'build/set-b-load-repair-proposal-r5/compiles.json'):
        assert row['exit']==0 and row['dependencies']['exit']==0
        for dep in row['dependencies']['inputs']:
            q=ROOT/dep['binding']['path'];assert P.bind(q)==dep['binding'];selected.add(q)
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Freigabe erteilt after 19738af1. Existing fifth Seed attribution; zero product builds/links/Seeds/device.\n\n'+subprocess.check_output(['git','show','19738af1:docs/planning/set-b-fifth-seed-workload-halt-report.md'],cwd=ROOT,text=True))
    inputs=[];copies=[]
    for p in sorted(selected):
        bound=P.bind(p);inputs.append(bound)
        if not p.is_relative_to(ROOT/'build'):continue
        raw=p.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/p.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ['mos-mega65-clang','llvm-objdump','llvm-readobj']]
    raw=Path('/usr/bin/gcc').read_bytes()
    P.write(SEAL,dict(status='COMPLETE: LOAD ATTRIBUTION; REPAIR PARKED BEFORE TIMING/PACKING PREFLIGHT',
        source_authority=authority,execution_head='19738af1',owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(closure),
        accepted_world='Card L Final',public_release='2.4.0',consumed=dict(seed_attempts=5,finals=0,product_link_attempts=5),
        further_seed_or_product_link_authorized=False,
        this_commission=dict(product_builds=0,product_links=0,seeds=0,finals=0,device_contacts=0,observer_builds=0,guest_launches=6,native_object_compiles=2,dependency_only_calls=2,host_c_test_compiles=1,host_c_test_links=1,complete_lisp_object_populations=8,full_world_fixture_populations=2,partial_lisp_serialization_attempts=1),
        guest_logs=guests,inputs=inputs,receipt_copies=copies,excluded=excluded,toolchain=toolchain,
        host_compiler=dict(path='/usr/bin/gcc',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
    print('SEALED',len(inputs),'inputs;',len(copies),'archive copies;',len(excluded),'SD clones excluded')

def check():
    s=P.load(SEAL)
    for r in s['inputs']+s['toolchain']+[s['owner_scope']]:assert P.bind(ROOT/r['path'])==r,r['path']
    for row in s['receipt_copies']:
        p=ROOT/row['copy']['path'];assert P.bind(p)==row['copy']
        raw=p.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes'] and hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    r=s['host_compiler'];raw=Path(r['path']).read_bytes();assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
    S.require_auth()
    print('PASS attribution seal: immutable authority, all identities and lossless archive copies')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['create','check']);a=ap.parse_args();create() if a.mode=='create' else check()
