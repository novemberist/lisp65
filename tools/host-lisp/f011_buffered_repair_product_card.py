#!/usr/bin/env python3
"""One-shot buffered F011 repair, explicit 566c2e23 authority."""
import argparse
import hashlib
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from pathlib import Path

import f011_status_product_card as C
import f011_buffered_repair_preflight as H
import block_26_f011_replacement_product_card as PACKED
from elf_truth import ElfTruth
import c2_v160_r1_stored_world_conversions as STORED

ROOT=C.ROOT
OLD={n:getattr(C,n) for n in ('BUILD','PREFLIGHT','PLANE','ELF','PRG','PROFILE','PLANE_RECEIPT')}
ORIGINAL_CONFIGURE=C.configure
ORIGINAL_PROFILE=C.materialize_bound_profile
ORIGINAL_PACKED_CHECKS=PACKED.source_checks
ORIGINAL_INVENTORY=C.PRODUCT.f011_status_inventory_registration
ORIGINAL_FINAL_CHECK=C.PRODUCT.final_section_inventory_check
ORIGINAL_ADDITIVE_CLOSURE=STORED._additive_section_closure
BUILD=ROOT/'build/v2.1/f011-buffered-repair-r1'
PREFLIGHT=ROOT/'build/v2.1/f011-buffered-repair-r1-preflight-r2'
PLANE=PREFLIGHT/'setup-owned/static-plane/narrow-static'
WPLTO=BUILD/'wplto'
ELF=WPLTO/'lisp65-c2-substitution-linked.prg.elf'
PRG=WPLTO/'lisp65-c2-substitution-linked.prg'
PROFILE=WPLTO/'resolved-profile.txt'
BOUND_PROFILE=PREFLIGHT/'bound-feature-profile.txt'
INVOCATION=PREFLIGHT/'candidate-invocation.json'
AUTHORIZATION='566c2e23'
PLAN_HEADER='## DECISION'
FORMAT='f011-buffered-repair-r1'
STATUS='PENDING: BUFFERED REPAIR QUALIFICATION'
DRIVER=Path(__file__).resolve()
REPORT=ROOT/'docs/planning/v2.1-f011-buffered-repair-product-report.md'
for n in ('PLANE_RECEIPT','PREFLIGHT_RECEIPT','SOURCE_PREFLIGHT','PRELINK_RED','DIFFERENCE','RECEIPT'):
    globals()[n]=C.ARCH/(FORMAT+'-'+n.lower().replace('_','-')+'.json')

def authority():
    raw=subprocess.check_output(['git','show',f'{AUTHORIZATION}:docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'(status & $D8) == $40' in raw and b'03b24c6b' in raw
    assert C.bind(OLD['ELF'])['sha256']=='29d3ff462afc9c59ad9769fac8098ed0f02900d3c7cf5a37c89855b0444d9cc6'
    return dict(commit=AUTHORIZATION,plan_sha256=hashlib.sha256(raw).hexdigest(),
                predecessor=dict(ELF=C.bind(OLD['ELF']),PRG=C.bind(OLD['PRG'])),
                device_core=H.CORE,budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1,device_contacts=0))

def profile(mapping=None):
    result=ORIGINAL_PROFILE(mapping)
    result['header_roots']=[C.bind(H.HEADER)]
    return result

def source_gate():
    H.main()
    return dict(host_prerequisites=C.bind(H.OUT/'receipt.json'),header=C.bind(H.HEADER),
                diagnostic_record_removed=True,final_elf_proof=False)

def successor_packed_checks(source,wrappers):
    """Retain packed-state checks; replace only the two superseded wait pins."""
    value=ORIGINAL_PACKED_CHECKS(source,wrappers)
    receipt=C.load(H.OUT/'receipt.json')
    assert receipt['header']==C.bind(H.HEADER)
    assert receipt['ordinary_sources']==[C.bind(ROOT/'src/io.c'),C.bind(ROOT/'src/main.c')]
    assert receipt['mutations']['control']==0
    assert all(v!=0 for k,v in receipt['mutations'].items() if k!='control')
    value['busy-bounded']=('if (!f011_wait_complete(start))' in source
        and '#include "f011_buffered_wait.h"' in source)
    value['completion-bits-evaluated']=value['busy-bounded']
    return value

def empty_witness_inventory():
    value=ORIGINAL_INVENTORY()
    assert not value['selected']
    # The unchanged linker script emits an empty output-section shell.
    # Naming that shell must not activate instrument storage or its owner.
    value.update(names=['.noinit.lisp65_f011_status'],record_bytes=0,
                 authority='unmodified linker declaration; final ELF must prove empty')
    return value

def witness_absent(truth):
    section=truth.section('.noinit.lisp65_f011_status')
    assert section.bytes==0, 'disabled witness allocated bytes'
    assert not any(s.name=='lisp65_f011_status_state' or
                   (s.section==section.name and s.symbol_type=='Object')
                   for s in truth.symbols), 'disabled witness has a state symbol'
    assert not any(r.source_section==section.name or r.target=='lisp65_f011_status_state'
                   for r in truth.relocations), 'disabled witness has relocations'

def final_inventory_check(target):
    truth=ElfTruth.read(Path(str(target)+'.elf'),llvm_readobj=C.B.READOBJ)
    witness_absent(truth)
    return ORIGINAL_FINAL_CHECK(target)

def empty_witness_mutations(target):
    truth=ElfTruth.read(Path(str(target)+'.elf'),llvm_readobj=C.B.READOBJ)
    section=truth.section('.noinit.lisp65_f011_status')
    witness_absent(truth)
    cases={
        'empty-shell-gains-byte':SimpleNamespace(section=lambda name:replace(section,bytes=1),
            symbols=truth.symbols,relocations=truth.relocations),
        'state-symbol-returns':SimpleNamespace(section=lambda name:section,
            symbols=[SimpleNamespace(name='lisp65_f011_status_state',section=section.name,
                                     symbol_type='Object')],relocations=[]),
        'state-relocation-returns':SimpleNamespace(section=lambda name:section,
            symbols=[],relocations=[SimpleNamespace(source_section='.text',target='lisp65_f011_status_state')]),
    }
    rejected=[]
    for name,mutant in cases.items():
        try: witness_absent(mutant)
        except AssertionError: rejected.append(name)
    assert rejected==list(cases)
    return rejected

def project_empty_witness(layout):
    result=deepcopy(layout)
    rows=[r for r in result['allocatable_sections'] if r['name']=='.noinit.lisp65_f011_status']
    assert len(rows)==1 and rows[0]['bytes']==0 and rows[0]['section_type']=='SHT_NOBITS', \
        'disabled witness projection requires exactly one empty NOLOAD shell'
    result['allocatable_sections'].remove(rows[0])
    return result

def successor_additive_closure(layout,golden,registered,proof_rows):
    # A declared zero-byte shell is not additive allocated freight. Prove
    # emitted absence first; never normalize a live owner or its references.
    witness_absent(ElfTruth.read(ELF,llvm_readobj=C.B.READOBJ))
    projected=project_empty_witness(layout)
    bad=deepcopy(layout)
    next(r for r in bad['allocatable_sections'] if r['name']=='.noinit.lisp65_f011_status')['bytes']=1
    try: project_empty_witness(bad)
    except AssertionError: pass
    else: raise AssertionError('allocated-witness projection mutation survived')
    value=ORIGINAL_ADDITIVE_CLOSURE(projected,golden,registered,proof_rows)
    value['empty_disabled_witness']={'bytes':0,'state_and_relocations_absent':True,
        'allocated_shell_mutation_rejected':True}
    return value

def configure():
    for n in ('BUILD','PREFLIGHT','PLANE','WPLTO','ELF','PRG','PROFILE','BOUND_PROFILE','INVOCATION',
              'AUTHORIZATION','PLAN_HEADER','FORMAT','STATUS','DRIVER','REPORT',
              'PLANE_RECEIPT','PREFLIGHT_RECEIPT','SOURCE_PREFLIGHT','PRELINK_RED','DIFFERENCE','RECEIPT'):
        setattr(C,n,globals()[n])
    for n,v in OLD.items(): setattr(C,'OLD_'+n,v)
    C.DIRECT=('src/io.c','src/main.c')
    C.authority=authority
    C.materialize_bound_profile=profile
    C.source_gate=source_gate
    ORIGINAL_CONFIGURE()
    C.B.HEADER_ROOTS=('src/f011_buffered_wait.h',)
    C.PRODUCT.F011_STATUS_WITNESS_ENABLED=False
    PACKED.source_checks=successor_packed_checks
    C.PRODUCT.f011_status_inventory_registration=empty_witness_inventory
    C.PRODUCT.final_section_inventory_check=final_inventory_check
    STORED._additive_section_closure=successor_additive_closure

def final_product():
    """Standard finish: reuse one seed; exactly one final C/LTO + product link."""
    stamp=BUILD/'final-product-invocation.json'
    assert not stamp.exists() and not ELF.exists() and not PRG.exists()
    assert not (WPLTO/'.canonical-objects-lisp65-c2-substitution-linked').exists()
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    upstream=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT).decode().strip()
    assert head==upstream, 'producer commit must be remote-visible'
    seed=WPLTO/'resident-island-seed.prg'
    paths=[seed,Path(str(seed)+'.elf'),Path(str(seed)+'.lto.o'),Path(str(seed)+'.map')]
    frozen=[C.bind(p) for p in paths]
    assert frozen[:3]==C.load(BUILD/'seed-read-only-inventory.json')['after']
    stamp.write_bytes(C.canonical(dict(authority=authority(),
        completion_authorization='Alex: final C/LTO and authorized product link, reuse seed, no seed rebuild',
        commit=head,upstream=upstream,seed=frozen,
        budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1),seed_WPLTO_already_consumed=1)))
    link=C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    materializer=link.materialize_candidate_sources
    original=C.PRODUCT.compile_link
    existing=WPLTO/'generated-product-sources'
    calls=[]
    def reuse(out):
        with tempfile.TemporaryDirectory(dir=BUILD,prefix='final-source-check-') as tmp:
            mapping=materializer(Path(tmp))
            assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in existing.iterdir() if p.is_file()}=={
                p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (Path(tmp)/'generated-product-sources').iterdir() if p.is_file()}
            return {s:existing/p.name for s,p in mapping.items()}
    def finish(out,name,headers,artifacts,**kwargs):
        assert out==WPLTO and frozen==[C.bind(p) for p in paths]
        calls.append(name)
        if name==seed.name:
            assert calls==[seed.name]
            C.PRODUCT.final_section_inventory_gate(out,seed)
            C.PRODUCT.lto_partition_metadata_gate(out,seed)
            return seed
        assert calls==[seed.name,PRG.name], 'extra compiler/link invocation forbidden'
        return original(out,name,headers,artifacts,**kwargs)
    link.materialize_candidate_sources=reuse
    C.PRODUCT.compile_link=finish
    try:
        try: C.B.child('_produce')
        except SystemExit as stop: assert stop.code==0
    finally:
        C.PRODUCT.compile_link=original
        link.materialize_candidate_sources=materializer
        after=[C.bind(p) for p in paths]
        (BUILD/'final-product-attempt.json').write_bytes(C.canonical(dict(
            calls=calls,seed_before=frozen,seed_after=after,
            ELF_present=ELF.exists(),PRG_present=PRG.exists(),
            seed_rebuilds=0,final_C_LTO_invocations=int(PRG.name in calls))))
        assert frozen==after

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('action',choices=['preflight','produce','check-seed','final-product','_produce','_scope','_accept'])
    action=ap.parse_args().action
    configure(); C.configure=configure
    if action=='preflight': C.preflight()
    elif action=='produce': C.produce()
    elif action=='final-product': final_product()
    elif action=='check-seed':
        target=WPLTO/'resident-island-seed.prg'
        paths=[target,Path(str(target)+'.elf'),Path(str(target)+'.lto.o')]
        before=[C.bind(p) for p in paths]
        link=C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
        materializer=link.materialize_candidate_sources
        existing=WPLTO/'generated-product-sources'
        def reuse(out):
            with tempfile.TemporaryDirectory(dir=BUILD,prefix='read-only-source-check-') as tmp:
                mapping=materializer(Path(tmp))
                for p in mapping.values():
                    assert p.read_bytes()==(existing/p.name).read_bytes()
                return {s:existing/p.name for s,p in mapping.items()}
        entered=[]
        def inspect(out,name,*args,**kwargs):
            assert name==target.name and not entered
            entered.append(name)
            final_inventory_check(target)
            raise SystemExit(0)
        original=C.PRODUCT.compile_link
        link.materialize_candidate_sources=reuse
        C.PRODUCT.compile_link=inspect
        try:
            try: C.B.child('_produce')
            except SystemExit as stop: assert stop.code==0
        finally:
            C.PRODUCT.compile_link=original
            link.materialize_candidate_sources=materializer
        assert entered==[target.name]
        assert before==[C.bind(p) for p in paths]
        receipt=dict(status='READ-ONLY SEED INVENTORY PASS; FINAL PRODUCT NOT BUILT',
            authority=authority(),before=before,after=[C.bind(p) for p in paths],
            empty_shell_mutations_rejected=empty_witness_mutations(target),
            accounting=dict(new_WPLTO=0,new_product_links=0),
            boundary='one seed WPLTO already used; standard final C/LTO invocation requires explicit budget disposition')
        (BUILD/'seed-read-only-inventory.json').write_bytes(C.canonical(receipt))
        print('READ-ONLY SEED INVENTORY PASS; unchanged PRG/ELF/LTO; no final product')
    else: C.B.child(action)

if __name__=='__main__': main()
