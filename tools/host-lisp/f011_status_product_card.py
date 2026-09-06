#!/usr/bin/env python3
"""One-shot F011 follow-up, explicit predecessor and temporary record owner."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from copy import deepcopy
from elf_truth import ElfTruth

import block_26_small_hardening_dma_tuple_repair_product_card as PREVIOUS
import c2_product_substitution_link as PRODUCT
from evidence_era import stable_recorded_on

ROOT=Path(__file__).resolve().parents[2]
B=PREVIOUS.BASE
OLD_BUILD=PREVIOUS.BUILD
OLD_PREFLIGHT=PREVIOUS.PREFLIGHT
OLD_PLANE=PREVIOUS.PLANE
OLD_ELF=PREVIOUS.ELF
OLD_PRG=PREVIOUS.PRG
OLD_PROFILE=PREVIOUS.PROFILE
OLD_PLANE_RECEIPT=PREVIOUS.PLANE_RECEIPT
BUILD=ROOT/'build/v2.1/f011-status-product-r1'
PREFLIGHT=ROOT/'build/v2.1/f011-status-product-r1-preflight'
PLANE=PREFLIGHT/'setup-owned/static-plane/narrow-static'
WPLTO=BUILD/'wplto'
ELF=WPLTO/'lisp65-c2-substitution-linked.prg.elf'
PRG=WPLTO/'lisp65-c2-substitution-linked.prg'
PROFILE=WPLTO/'resolved-profile.txt'
BOUND_PROFILE=PREFLIGHT/'bound-feature-profile.txt'
INVOCATION=PREFLIGHT/'candidate-invocation.json'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
AUTHORIZATION='5b59fca5'
PLAN=ROOT/'docs/planning/v2.0.0-pre-plan.md'
PLAN_HEADER='## v2.1 — F011 instrument + propagation follow-up: product card authorized — 2026-09-05'
DRIVER=Path(__file__).resolve()
FORMAT='lisp65-v21-f011-status-product-r1-v1'
STATUS='PENDING: F011 FINAL PRODUCT QUALIFICATION'
for _name in ['PLANE_RECEIPT','PREFLIGHT_RECEIPT','SOURCE_PREFLIGHT','PRELINK_RED','DIFFERENCE','RECEIPT']:
    globals()[_name]=ARCH/('v2.1-f011-status-product-r1-'+_name.lower().replace('_','-')+'.json')
REPORT=ROOT/'docs/planning/v2.1-f011-status-product-report.md'
bind=B.bind
require=B.require
load=B.load
canonical=B.canonical
DIRECT=('src/io.c','src/main.c','src/vm.c')

def authority():
    raw=subprocess.check_output(['git','show',f'{AUTHORIZATION}:{PLAN.relative_to(ROOT)}'],cwd=ROOT).decode()
    require(raw.count(PLAN_HEADER)==1,'F011 commission missing')
    section=(PLAN_HEADER+raw.split(PLAN_HEADER,1)[1]).split('\n## ',1)[0]
    for word in ['One WPLTO','one product link','Abort survival','LOAD_OPEN']:
        require(word in section,'commission condition missing: '+word)
    require(bind(OLD_ELF)['sha256']=='f02d6997e33ae6c1059be1a9f81711d219f430c26e3144772124fd9a979366cf','Comfort predecessor ELF drift')
    require(bind(OLD_PRG)['sha256']=='3f00922419c808ca96dbe7a6b24d24abe3c4c3c3cb00ae591b44be20aab7b238','Comfort predecessor PRG drift')
    return {'commit':AUTHORIZATION,'section_sha256':hashlib.sha256(section.encode()).hexdigest(),
            'predecessor':{'ELF':bind(OLD_ELF),'PRG':bind(OLD_PRG)},
            'budget':{'WPLTO':1,'product_links':1,'device_contacts':0}}

def materialize_bound_profile(mapping=None):
    require(mapping is not None,'source projection must be producer-owned')
    generated={p.name:p for p in mapping.values()}
    old=B.profile_inputs(OLD_PROFILE)
    lines=OLD_PROFILE.read_text().splitlines(); authored=[]; derived=[]
    for i,line in enumerate(lines):
        if not line.startswith('input_sha256='): continue
        name=line.split('=',1)[1].split(':',1)[0]
        p=ROOT/name
        if '/generated-product-sources/' in name:
            p=generated.get(Path(name).name,OLD_BUILD/'wplto/generated-product-sources'/Path(name).name)
            successor=(WPLTO/'generated-product-sources'/p.name).relative_to(ROOT).as_posix()
            family=derived
        else:
            successor=name; family=authored
        digest=bind(p)['sha256']
        lines[i]=f'input_sha256={successor}:{digest}'
        if digest!=old[name]: family.append(name)
    require(sorted(authored)==sorted(DIRECT),'uncommissioned authored source population: '+str(authored))
    # Derived objects remain compiler-owned and are rebound with their actual
    # bytes. The final compiler-consumption proof must confirm this projection.
    BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    return {'predecessor':bind(OLD_PROFILE),'successor':bind(BOUND_PROFILE),
            'changed_authored_roots':sorted(authored),'changed_generated_roots':sorted(derived),
            'header_roots':[bind(ROOT/'src/f011_status_witness.h')],
            'feature_count':len(B.bound_features())}

def configure():
    PREVIOUS.configure(); PREVIOUS.R2.configure()
    names=('AUTHORIZATION PLAN_HEADER BUILD PREFLIGHT PLANE WPLTO ELF PRG PROFILE BOUND_PROFILE INVOCATION '
           'PLANE_RECEIPT PREFLIGHT_RECEIPT SOURCE_PREFLIGHT PRELINK_RED DIFFERENCE RECEIPT REPORT DRIVER FORMAT STATUS').split()
    for n in names: setattr(B,n,globals()[n])
    B.PLAN=PLAN
    B.PREDECESSOR_BUILD=OLD_BUILD; B.PREDECESSOR_PREFLIGHT=OLD_PREFLIGHT
    B.PREDECESSOR_PLANE=OLD_PLANE; B.PREDECESSOR_ELF=OLD_ELF
    B.PREDECESSOR_PRG=OLD_PRG; B.PREDECESSOR_PROFILE=OLD_PROFILE
    B.PREDECESSOR_PLANE_RECEIPT=OLD_PLANE_RECEIPT
    B.DIRECT_CARD6_SOURCES=DIRECT
    B.HEADER_ROOTS=('src/f011_status_witness.h',)
    B.authority=authority; B.git_section=authority
    B.materialize_bound_profile=materialize_bound_profile
    B.configure_stack()
    PRODUCT.F011_STATUS_WITNESS_ENABLED=True
    # Card 6 already moved the descriptor to BSS. Its sealed relocation
    # evidence must not be re-run with this card's predecessor as Card 3.
    PREVIOUS.R2.descriptor_emission_gate=unchanged_descriptor_successor
    B.PREV.CARD.CARD2.R2.CARD.configure()

def unchanged_descriptor_successor():
    old=ElfTruth.read(OLD_ELF,llvm_readobj=B.READOBJ,include_section_data=True)
    new=ElfTruth.read(ELF,llvm_readobj=B.READOBJ,include_section_data=True)
    def normalized(t,name):
        symbol=t.symbol(name); section=t.section(symbol.section)
        raw=bytearray(t.section_bytes(section.name)[symbol.value-section.address:symbol.value-section.address+symbol.bytes])
        for r in t.relocations:
            if r.source_section!=symbol.section or not symbol.value<=r.offset<symbol.value+symbol.bytes:continue
            width=2 if r.relocation_type=='R_MOS_ADDR16' else 1
            i=r.offset-symbol.value;raw[i:i+width]=bytes(width)
        return bytes(raw)
    name='vm_runtime_overlay_exec_family'
    require(normalized(old,name)==normalized(new,name),'DMA materializer changed outside relocations')
    before,after=old.symbol('rtov_edma_job'),new.symbol('rtov_edma_job')
    require((before.section,before.bytes)==(after.section,after.bytes)
            and after.section=='.bss' and after.bytes==20,'qualified DMA job owner changed')
    relocation_proof=None
    if before.value!=after.value:
        def tail_owner(t,s):
            bss=t.section('.bss')
            return bss.address<=s.value and s.value+s.bytes==bss.address+bss.bytes
        require(tail_owner(old,before) and tail_owner(new,after),
                'moved DMA descriptor is not the same derived BSS-tail owner')
        def edges(t):
            s=t.symbol(name)
            result=[]
            for r in t.relocations:
                if r.source_section!=s.section or not s.value<=r.offset<s.value+s.bytes:continue
                target=(r.target,r.addend)
                if r.target in ('.bss','.zp.bss'):
                    address=t.section(r.target).address+r.addend
                    owners=sorted((o.name,address-o.value) for o in t.symbols
                        if o.section==r.target and o.symbol_type=='Object'
                        and o.value<=address<o.value+o.bytes)
                    require(bool(owners),'DMA relocation has no named state owner')
                    target=tuple(owners)
                result.append((r.offset-s.value,r.relocation_type,repr(target)))
            return sorted(result)
        require(edges(old)==edges(new),'DMA materializer relocation targets changed')
        from dataclasses import replace
        require(not tail_owner(new,replace(after,value=after.value+1)),
                'unexplained descriptor displacement mutation survived')
        relocation_proof={'before':before.value,'after':after.value,
            'relation':'20-byte owner ends at final ordinary BSS end',
            'relocation_targets_equal':True,'shift_mutation_rejected':True}
    sealed=ARCH/'block-2.6-card6-small-hardening-dma-tuple-repair-r3-receipt.json'
    value=deepcopy(load(sealed)['final_product']['small_hardening']['descriptor_emission'])
    value['successor_neutrality']={'sealed_evidence':bind(sealed),'predecessor':bind(OLD_ELF),
        'candidate':bind(ELF),'method':'same BSS owner and relocation-normalized final DMA materializer bytes',
        'normalized_materializer_sha256':hashlib.sha256(normalized(new,name)).hexdigest()}
    if relocation_proof is not None:
        value['successor_neutrality']['derived_BSS_relocation']=relocation_proof
    return value

def source_gate():
    import f011_status_instrument_semantics as S
    S.main()
    # Run the independent ordinary-caller mutation through its public command.
    subprocess.run([sys.executable,str(ROOT/'tools/host-lisp/f011_read_error_propagation_gate.py')],cwd=ROOT,check=True)
    text=(ROOT/'src/f011_status_witness.h').read_text()
    require('lisp_abort' not in text and 'map_enter' not in text and 'map_leave' not in text,'cold observer calls forbidden service')
    script=PRODUCT.full_map_platform_c_ld()
    def owner_contract(s):
        for token in ['.noinit.lisp65_f011_status (ADDR(.bss) + SIZEOF(.bss)) (NOLOAD)',
                      'KEEP(*(.noinit.lisp65_f011_status))',
                      'SIZEOF(.noinit.lisp65_f011_status) + 5 <=',
                      'ADDR(.lisp65_c2_input_raw_owner)']:
            require(token in s,'F011 NOLOAD contract missing: '+token)
    owner_contract(script)
    mutations=[]
    for token in ['KEEP(*(.noinit.lisp65_f011_status))','(NOLOAD)']:
        try: owner_contract(script.replace(token,''))
        except B.CardError: mutations.append(token)
    require(len(mutations)==2,'NOLOAD-owner mutation survived')
    return {'host_semantics':bind(S.OUT/'semantics-receipt.json'),
            'error_transfer':bind(ROOT/'build/v2.1/f011-followup-host-preflight/primitive15-receipt.json'),
            'header':bind(ROOT/'src/f011_status_witness.h'),
            'owner_script_sha256':hashlib.sha256(script.encode()).hexdigest(),
            'owner_mutations_rejected':mutations,
            'final_elf_proof':False}

def preflight():
    require(not INVOCATION.exists() and not BUILD.exists(),'product budget already invoked')
    configure(); toolchain=B.toolchain_identity()
    if not PLANE.exists(): shutil.copytree(OLD_PLANE,PLANE)
    for n in ['projected-ownership-contract.json','projected-full-map-authority.json']:
        dest=PREFLIGHT/n
        if not dest.exists(): shutil.copyfile(OLD_PREFLIGHT/n,dest)
    configure()
    leaf=B.PREV.CARD.CARD2.R2.CARD
    mapping=leaf.BASE.CHAIN.LINK.materialize_candidate_sources(PREFLIGHT/'profile-generated-sources')
    profile=materialize_bound_profile(mapping)
    configure(); world=leaf.product_world_identity()
    require(world['selected_plane_world']['product_build_id']=='0x4a1713ab' and world['selected_plane_world']['banner']=='WORKBENCH 2.0.0','wrong product world')
    plane=load(OLD_PLANE_RECEIPT)
    plane.update({'format':FORMAT+'-plane','recorded_on':stable_recorded_on(PLANE_RECEIPT),
        'status':'PASS: F011 FOLLOW-UP PLANE BOUND','authority':authority(),
        'product':bind(PLANE/'product/substitution-artifacts.json'),
        'profile':bind(PLANE/'candidate-profile.json'),'contract':bind(PLANE/'c2-lite-execution-contract.json'),
        'header':bind(PLANE/'c2_lite_static_plane.h'),'bank2':bind(PLANE/'v6-semantics/bank2-static-code.bin'),
        'product_world_identity':world,'accounting':{'WPLTO_runs':0,'product_links':0}})
    PLANE_RECEIPT.write_bytes(canonical(plane))
    configure(); config=leaf.configuration_gate()
    sources=B.PREV.CARD.CARD2.R2.source_preflight()
    semantic=source_gate()
    result={'format':FORMAT+'-preflight','recorded_on':stable_recorded_on(PREFLIGHT_RECEIPT),
            'status':'PASS: F011 FOLLOW-UP ARMED 0/1','authority':authority(),
            'world':world,'toolchain':toolchain,'profile':profile,'configuration':config,
            'source_population':sources,'semantic':semantic,
            'instrument_registry':PRODUCT.f011_status_inventory_registration(),
            'accounting':{'WPLTO_runs':0,'product_links':0,'device_contacts':0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(result))
    print('F011 product preflight PASS, budget 0/1 + 0/1')

def produce():
    configure()
    require(not INVOCATION.exists() and not BUILD.exists(),'one-shot product budget exhausted')
    pre=load(PREFLIGHT_RECEIPT)
    require(pre['authority']==authority() and pre['toolchain']==B.toolchain_identity(),'preflight authority drift')
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT),'commit-bound producer requires clean tree')
    INVOCATION.write_bytes(canonical({'status':'INVOKED','authority':authority(),'preflight':bind(PREFLIGHT_RECEIPT),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()}))
    B.child('_produce')

def refresh_host_checks():
    """Recheck the existing preflight without rerunning its one-shot producer."""
    configure()
    require(not INVOCATION.exists() and not BUILD.exists(),'pre-build refresh only')
    value=load(PREFLIGHT_RECEIPT)
    require(value['authority']==authority() and value['toolchain']==B.toolchain_identity(),'bound preflight changed')
    for name,digest in B.profile_inputs(BOUND_PROFILE).items():
        if '/generated-product-sources/' not in name:
            require(bind(ROOT/name)['sha256']==digest,'source changed after preflight: '+name)
    require(value['profile']['header_roots']==[bind(ROOT/'src/f011_status_witness.h')],'header changed after preflight')
    value['semantic']=source_gate()
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print('F011 existing preflight rechecked, no producer replay')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','refresh-host-checks','produce'])
    args=parser.parse_args()
    {'preflight':preflight,'refresh-host-checks':refresh_host_checks,'produce':produce}[args.action]()
