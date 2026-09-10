#!/usr/bin/env python3
"""A-only successor of Card 2b; corrected shared entry, no other freight.

Reuse the established producer and carrier reservation. Never re-use an old
card's source price or authorize a compiler merely by importing this module.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import capacity_disk_window_product_card as B

ROOT, C, F, A = B.ROOT, B.C, B.F, B.A
BUILD = ROOT/'build/capacity/lever-a-product-r1'
PREFLIGHT = ROOT/'build/capacity/lever-a-product-r1-preflight'
EVIDENCE = ROOT/'build/capacity/lever-a-r1'
BASE = ROOT/'build/capacity/card2b-product-r1'
BASE_PREFLIGHT = ROOT/'build/capacity/card2b-product-r1-preflight'
REF = '4a7087a9b9c536e57ad73cf76cdf3b5e724d1959'
AUTHORIZATION = 'a5a51f47'
ORIGINAL_CONFIGURE = B.configure
ORIGINAL_MATERIALIZE = B.materialize


def authority():
    raw = subprocess.check_output(['git','show',AUTHORIZATION+
        ':docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'4a7087a9' in raw and b'one seed WPLTO' in raw
    expected = {'ELF':'efe2585390e5583e6b7a49d810b9fabc8dc633680d98d60419341780ef74ffcf',
                'PRG':'5ed35f65e9c254ba5edaedd6fc9fe2051768f4aaae6ae6a12a1e119cffb75a72'}
    for key,digest in expected.items():
        assert C.bind(A.PREDECESSOR[key])['sha256']==digest
    return dict(commit=AUTHORIZATION,patch_commit=REF,
        plan_sha256=hashlib.sha256(raw).hexdigest(),
        predecessor={n:C.bind(A.PREDECESSOR[n]) for n in ('ELF','PRG','PROFILE')},
        budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1,host_images=2,device_contacts=0),
        acceptance='positive final ordinary-text gain, exact host trace identity, both responsiveness lanes')


def corrected_vm():
    old=(BASE/'wplto/generated-product-sources/vm.c').read_bytes()
    get=lambda ref:subprocess.check_output(['git','show',ref+':src/vm.c'],cwd=ROOT)
    anchor=(b'obj vm_run_inner(uint8_t bank, uint16_t off, uint16_t len,\n'
            b'                 const obj *args, uint8_t nargs_actual) {')
    prior,new=get('8b04f688^'),get(REF)
    assert all(x.count(anchor)==1 for x in (old,prior,new))
    assert old.split(anchor)[1]==prior.split(anchor)[1]
    value=old.split(anchor)[0]+anchor+new.split(anchor)[1]
    assert value.count(b'case 22: return card2b_disk_call(a,n);')==1
    assert value==(EVIDENCE/'corrected/vm.c').read_bytes()
    return value


def source_gate():
    path=EVIDENCE/'corrected/receipt.json';value=C.load(path)
    assert value['status']=='PASS: CORRECTED COMPOSITION AND REQUIRED HOST IDENTITY'
    assert value['authority']==REF
    for key in ('base','candidate','runner','observer','trace_receipt'):
        item=value[key]
        assert C.bind(ROOT/item['path'])['sha256']==item['sha256'],key
    traces=C.load(ROOT/value['trace_receipt']['path'])
    for item in traces['bindings']:
        assert C.bind(ROOT/item['path'])['sha256']==item['sha256'], item['path']
    for row in traces['rows']:
        assert row['trace_equal'] and row['output_equal']
        for item in row['traces']+row['outputs']:
            assert C.bind(ROOT/item['path'])['sha256']==item['sha256']
    assert hashlib.sha256(corrected_vm()).hexdigest()==value['candidate']['sha256']
    return dict(status='PASS',identity=C.bind(path),adapter=C.bind(Path(__file__)),
                unchanged_card2b_prefix=True,only_changed_product_root='vm.c')


def materialize(out):
    mapping=ORIGINAL_MATERIALIZE(out)
    target=mapping[(ROOT/'src/vm.c').resolve()]
    target.write_bytes(corrected_vm())
    return mapping


def profile(mapping=None):
    assert mapping
    by_name={p.name:p for p in mapping.values()}
    lines=A.PREDECESSOR['PROFILE'].read_text().splitlines()
    changes=[]; population=[]
    for i,line in enumerate(lines):
        if not line.startswith('input_sha256='): continue
        name,previous=line.split('=',1)[1].rsplit(':',1)
        before=(ROOT/name).resolve()
        assert C.bind(before)['sha256']==previous, 'stale predecessor input: '+name
        target=(by_name.get(before.name,before) if '/generated-product-sources/' in name
                else mapping.get(before,before))
        current=C.bind(target)['sha256']
        successor=((F.WPLTO/'generated-product-sources'/target.name).relative_to(ROOT).as_posix()
                   if target in mapping.values() else name)
        lines[i]=f'input_sha256={successor}:{current}'
        population.append(dict(before=name,after=successor,sha256=current))
        if current!=previous:
            changes.append(dict(predecessor=name,successor=successor,before=previous,after=current))
    assert len(changes)==1 and Path(changes[0]['predecessor']).name=='vm.c',changes
    assert len(population)==len({r['after'] for r in population})
    C.BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    assert A.features(C.BOUND_PROFILE)==A.features(A.PREDECESSOR['PROFILE'])
    return dict(predecessor=C.bind(A.PREDECESSOR['PROFILE']),successor=C.bind(C.BOUND_PROFILE),
                changes=changes,population=population,feature_authority=B.feature_authority())


def configure():
    B.BUILD,B.PREFLIGHT=BUILD,PREFLIGHT
    A.BASE_PREFLIGHT=BASE_PREFLIGHT
    A.PREDECESSOR=dict(BUILD=BASE,PREFLIGHT=BASE_PREFLIGHT,
        PLANE=BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',
        PLANE_RECEIPT=BASE_PREFLIGHT/'plane-receipt.json',
        ELF=BASE/'wplto/lisp65-c2-substitution-linked.prg.elf',
        PRG=BASE/'wplto/lisp65-c2-substitution-linked.prg',PROFILE=BASE/'wplto/resolved-profile.txt')
    B.authority,B.source_gate,B.profile,B.materialize=authority,source_gate,profile,materialize
    ORIGINAL_CONFIGURE()
    for module in (F,C,C.B):
        module.DRIVER=Path(__file__).resolve()
        module.AUTHORIZATION=AUTHORIZATION
        module.FORMAT='capacity-lever-a-r1'
        module.STATUS='PENDING: A QUALIFICATION'
        module.PLAN_HEADER='## BOUND — the "shared callee entry" card (lever A), ready for Codex — 2026-09-07'
        module.REPORT=ROOT/'docs/planning/capacity-lever-a-product-report.md'
    C.PLAN=C.B.PLAN=ROOT/'docs/planning/v2.0.0-pre-plan.md'


def main():
    B.configure=A.configure=configure
    if sys.argv[1:]==['preflight']:
        A.preflight()
        for path,role in ((F.PLANE_RECEIPT,'plane'),(F.PREFLIGHT_RECEIPT,'preflight')):
            value=C.load(path)
            assert value['authority']==authority()
            value['format']='capacity-lever-a-r1-'+role
            path.write_bytes(C.canonical(value))
        print('A preflight PASS; corrected entry on Card 2b, budget 0/0/0')
    elif sys.argv[1:]==['seed']:
        B.produce_seed()
    else:
        raise SystemExit('Choose preflight or seed; no implicit final build')


if __name__=='__main__': main()
