"""Seal the host-only Set B reader repair design and immutable-Seed trace."""
import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
ROOT=P.ROOT
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-read-path-repair-20260926'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-read-path-repair-proposal.md'


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    trace=P.load(ROOT/'build/set-b-read-path-trace-r2/receipt.json')
    assert trace['status']=='PASS: EXECUTED RESET REFUSAL ATTRIBUTION'
    price=P.load(ROOT/'build/set-b-read-path-proposal-r5/receipt.json')
    assert price['tenant_extent']==6752 and price['tenant_tail']==1440
    check=P.load(ROOT/'build/set-b-read-path-checks-r1/receipt.json')
    assert check['status']=='PASS: ABI, INPUT CLOSURE, GEOMETRY AND EXECUTED TRACE'
    roots=sorted((ROOT/'build').glob('set-b-read-path-*'))
    selected=set();excluded=[]
    for root in roots:
        for path in root.rglob('*'):
            if not path.is_file():continue
            if path.name=='system-sd.img':
                excluded.append(dict(path=str(path.relative_to(ROOT)),reason='Disposable 4 GiB SD copy; bound D81 and stopped/shutdown memory preserved'))
            else:selected.add(path)
    toolnames=['set_b_read_path_trace_20260926.py','set_b_read_path_proposal_20260926.py',
        'set_b_read_path_checks_20260926.py',Path(__file__).name,'set_b_producer.py','elf_truth.py',
        'native_cycle_stationary.py','dwx_retroactive_red_replay.py','dwx_mirrored_prefilter_rows.py',
        'dwx_comfort_resume.py','nested_error_recovery_gates.py','nested_error_recovery_lanes.py',
        'c2_product_substitution_link.py','set_b_qualification_halt_seal_20260926.py']
    selected.update(ROOT/'tools/host-lisp'/n for n in toolnames)
    selected.update(ROOT/p for p in P.authority_files())
    for row in check['dependency_rows']:
        selected.update(ROOT/r['binding']['path'] for r in row['inputs'])
    selected.update([REPORT,ROOT/'src/optional/c2_map_cpu_read.s',ROOT/'src/c2_platform_dma.h',
        ROOT/'src/c2_kernal_facade_reopen.s',ROOT/'scripts/xmega65-safe-run.sh',ROOT/'scripts/kill-xmega65-by-token.py',
        ROOT/'build/set-b-product-r3/commands.json',ROOT/trace['world']['ELF']['path'],
        ROOT/trace['world']['medium']['path'],ROOT/trace['world']['binary']['path'],
        ROOT/'build/set-b-product-r3/set-b-tenants.bin',ROOT/'build/card-l-r1/instrument-comfort.json',
        ROOT/'build/input-cost-attribution-r6/xemu/targets/mega65/mega65.c',
        ROOT/'build/input-cost-attribution-r6/xemu/targets/mega65/uart_monitor.c',
        ARCH/'set-b-seed-qualification-halt-20260926.json'])
    scope=ARCH/STEM/'owner-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner continuation: Alles klar. Bitte weitermachen\n\n'+
        subprocess.check_output(['git','show','f8d98e3d:docs/planning/post-2.4.0-plan.md'],cwd=ROOT,text=True))
    inputs=[];copies=[]
    for path in sorted(selected):
        bound=P.bind(path);inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'):continue
        data=path.read_bytes();compressed=len(data)>131072
        dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        dest.write_bytes(gzip.compress(data,compresslevel=9,mtime=0) if compressed else data)
        copies.append(dict(source=bound,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status='HOST REPAIR DESIGN COMPLETE; PRODUCT QUALIFICATION HALTED; REPLACEMENT BUDGET PROPOSED',
        authority=P.require_auth(),scope_authority='f8d98e3d plus owner continuation',owner_scope=P.bind(scope),
        accepted_world='Card L Final',public_release='2.4.0',seed=trace['world']['ELF'],
        report=P.bind(REPORT),patch=price['patch'],maintained_native_source_unchanged=True,
        consumed=dict(seed_attempts=3,finals=0,product_link_attempts=3),
        proposed_ceiling=dict(seed_attempts=4,finals=1,product_link_attempts=4),further_product_link_authorized=False,
        this_continuation=dict(object_compiles=2,dependency_only_calls=2,guest_launches=2,discarded_guest_traces=1,
            product_links=0,seeds=0,finals=0,observer_builds=0,device_contacts=0),
        inputs=inputs,receipt_copies=copies,excluded=excluded))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies')


def check():
    seal=P.load(SEAL)
    for row in seal['inputs']+[seal['owner_scope']]:assert P.bind(ROOT/row['path'])==row,row['path']
    for row in seal['receipt_copies']:
        source,copy=row['source'],row['copy'];assert P.bind(ROOT/copy['path'])==copy
        data=(ROOT/copy['path']).read_bytes()
        if row['encoding']=='gzip':data=gzip.decompress(data)
        assert len(data)==source['bytes'] and hashlib.sha256(data).hexdigest()==source['sha256']
    print('PASS repair seal; all source bindings and lossless copies')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['create','check'])
    args=ap.parse_args();create() if args.mode=='create' else check()
