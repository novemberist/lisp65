"""Seal all fifth-Seed evidence at the library-load qualification halt."""
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
STEM='set-b-fifth-seed-workload-halt-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-fifth-seed-workload-halt-report.md'


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    authority=S.require_auth()
    closure=P.load(S.OUT/'closure-r1/receipt.json')
    assert closure['complete_inventory'] and closure['unclassified_bytes']==closure['unclassified_relocations']==0
    medium=ROOT/'build/set-b-seed-medium-r6'
    assert P.load(medium/'readback.json')['status']=='PASS: INDEPENDENT MEDIA READBACK'
    halt=P.load(ROOT/'build/set-b-fifth-functional-reuse-r3/qualification-halt.json')
    assert halt['actual']=='NIL' and halt['expected']=='T' and halt['ready']==1 and halt['arm']==134 and halt['tenant_intact']
    analysis=P.load(S.OUT/'workload-halt-analysis-r2/receipt.json')
    assert analysis['completed_prefix']['forms']==53 and analysis['halt']['c2d_64k_unchanged'] and analysis['halt']['bank2_64k_unchanged']
    cold=P.load(ROOT/'build/set-b-fifth-cold-boot-r4/receipt.json')
    assert cold['status'].startswith('PASS') and cold['delta_cycles']==19972299
    roots=[S.OUT,S.PRODUCT,medium]+sorted((ROOT/'build').glob('set-b-fifth-*'))
    selected=set();excluded=[];guest_logs=[];observer_builds=[]
    for root in roots:
        for p in root.rglob('*'):
            if not p.is_file():continue
            rel=p.relative_to(ROOT)
            if p.name=='system-sd.img':
                excluded.append(dict(path=str(rel),reason='Disposable sparse SD clone; delivered medium, launch and final memory preserved'));continue
            if 'observer' in p.parts:
                sub=p.parts[p.parts.index('observer')+1:]
                if '.git' in sub or (sub and sub[0]=='build' and sub!=('build','bin','xmega65.native')) or p.suffix in ('.o','.d'):
                    excluded.append(dict(path=str(rel),reason='Reconstructible observer object/cache or VCS metadata; complete source/configuration and final binary preserved'));continue
            selected.add(p)
            if p.name=='xemu.log':guest_logs.append(P.bind(p))
            if p.name=='build.json' and 'cold-boot-' in str(p):observer_builds.append(P.bind(p))
    assert len(guest_logs)==15,len(guest_logs)
    assert len(observer_builds)==6,len(observer_builds)
    selected.update(ROOT/p for p in S.authority_files())
    newtools=sorted((ROOT/'tools/host-lisp').glob('set_b_fifth*_20260926.py'))
    newtools += [ROOT/'tools/host-lisp/set_b_transaction_final_20260926.py']
    selected.update(local_import_closure(newtools))
    selected.update([REPORT,ARCH/'set-b-transaction-boundary-repair-20260926.json',ARCH/'set-b-fourth-seed-activation-halt-20260926.json',
        ROOT/'scripts/xmega65-safe-run.sh',ROOT/'scripts/kill-xmega65-by-token.py',ROOT/'build/card-l-r1/instrument-comfort.json',
        ROOT/'build/card-l-boot-instrument-r2/configuration.json'])
    for name in ['xemu/cpu65.c','xemu/cpu65_mega65_timings.h','targets/mega65/mega65.c','targets/mega65/uart_monitor.c','build/bin/xmega65.native']:
        selected.add(ROOT/'build/input-cost-attribution-r6/xemu'/name)
    # The cold observer's inherited source tree is separately pinned too.
    parent=ROOT/'build/card-l-boot-instrument-r2/candidate/observer'
    for name in ['xemu/cpu65.c','xemu/boot_observer.h','xemu/boot_boundaries.h','targets/mega65/mega65.c','targets/mega65/uart_monitor.c']:
        selected.add(parent/name)
    def bindings(v):
        if isinstance(v,dict):
            if {'path','sha256','bytes'}<=v.keys():
                p=(ROOT/v['path']).resolve();actual=P.bind(p)
                assert all(actual[k]==v[k] for k in ('sha256','bytes')),v['path']
                selected.add(p)
            else:
                for x in v.values():bindings(x)
        elif isinstance(v,list):
            for x in v:bindings(x)
    bindings(P.load(S.OUT/'closure-r1/compiler-inputs.json'))
    for role in ('baseline','candidate'):
        bindings(P.load(ROOT/f'build/set-b-fifth-cold-boot-r4/{role}/configuration.json'))
    toolchain=[P.bind(ROOT/'tools/llvm-mos/bin'/n) for n in ['mos-mega65-clang','llvm-objdump','llvm-readobj']]
    external=[]
    for n in ['/usr/bin/llvm-link','/usr/bin/gcc','/usr/bin/make']:
        p=Path(n);raw=p.read_bytes();external.append(dict(path=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner word: Freigabe erteilt; fifth attempt, ceiling5/1/5, no implicit retry.\n\n'+subprocess.check_output(['git','show','1f9fda66:docs/planning/post-2.4.0-plan.md'],cwd=ROOT,text=True))
    inputs=[];copies=[]
    for p in sorted(selected):
        bound=P.bind(p);inputs.append(bound)
        if not p.is_relative_to(ROOT/'build'):continue
        raw=p.read_bytes();compressed=len(raw)>131072;dest=ARCH/STEM/p.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status='FIFTH SEED INVENTORY/ACTIVATION/REUSE CLOSED; LIBRARY-LOAD QUALIFICATION HALT',
        source_authority=authority,execution_head='1f9fda66',owner_scope=P.bind(scope),report=P.bind(REPORT),
        accepted_world='Card L Final',public_release='2.4.0',seed=closure['seed'],medium=P.bind(medium/'media-seed/set-b-comfort.d81'),
        consumed=dict(seed_attempts=5,finals=0,product_link_attempts=5),authorized_ceiling=dict(seed_attempts=5,finals=1,product_link_attempts=5),
        further_product_link_authorized=False,
        this_continuation=dict(admission_object_compiles=148,seed_compile_roots=74,llvm_aggregations=1,product_links=1,dependency_only_calls=2,cold_stager_links=4,observer_builds=len(observer_builds),guest_launches=len(guest_logs),finals=0,device_contacts=0),
        first_unexpected_product_result=halt,offline_closure=P.bind(S.OUT/'workload-halt-analysis-r2/receipt.json'),
        guest_logs=guest_logs,observer_build_receipts=observer_builds,
        inputs=inputs,receipt_copies=copies,excluded=excluded,toolchain=toolchain,external_toolchain=external))
    print('SEALED',len(inputs),'inputs;',len(copies),'copies;',len(excluded),'excluded cache/SD files')


def check():
    seal=P.load(SEAL)
    for row in seal['inputs']+seal['toolchain']+[seal['owner_scope']]:
        assert P.bind(ROOT/row['path'])==row,row['path']
    for row in seal['external_toolchain']:
        raw=Path(row['path']).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
    for r in seal['receipt_copies']:
        assert P.bind(ROOT/r['copy']['path'])==r['copy']
        raw=(ROOT/r['copy']['path']).read_bytes()
        if r['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==r['source']['bytes'] and hashlib.sha256(raw).hexdigest()==r['source']['sha256']
    print('PASS fifth halt seal: all input identities and lossless archive copies')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['create','check']);a=ap.parse_args();create() if a.mode=='create' else check()
