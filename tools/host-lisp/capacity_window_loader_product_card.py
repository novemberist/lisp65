#!/usr/bin/env python3
"""Card 2a: explicit Renderer successor; one seed, one final C/LTO, one link.

The inherited producer owns materialization and world checks. This adapter
changes only the commissioned C/ASM roots and the derived cache feature.
It does not authorize hardware, member relocation or a completion retry.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import shutil
from evidence_era import stable_recorded_on

import renderer_branch_product_card as R

F = R.F
C = F.C
ROOT = R.ROOT
BUILD = ROOT / 'build/capacity/card2a-product-r1'
PREFLIGHT = ROOT / 'build/capacity/card2a-product-r1-preflight'
BASE = ROOT / 'build/v2.1/renderer-branch-product-r1'
BASE_PREFLIGHT = ROOT / 'build/v2.1/renderer-branch-product-r1-preflight'
EVIDENCE = ROOT / 'build/capacity/card2a-r1'
AUTHORIZATION = '3845fbc7'
FEATURE = 'LISP65_RTOV_SESSION_RECORD_CACHE'
AUTHORED = ('src/vm_runtime_overlay.c', 'src/rtov_crc_mem.s')
PREDECESSOR = dict(BUILD=BASE, PREFLIGHT=BASE_PREFLIGHT,
    PLANE=BASE_PREFLIGHT / 'setup-owned/static-plane/narrow-static',
    ELF=BASE / 'wplto/lisp65-c2-substitution-linked.prg.elf',
    PRG=BASE / 'wplto/lisp65-c2-substitution-linked.prg',
    PROFILE=BASE / 'wplto/resolved-profile.txt',
    PLANE_RECEIPT=BASE_PREFLIGHT / 'plane-receipt.json')
ORIGINAL_CONFIGURE = F.configure
ORIGINAL_PROFILE = F.ORIGINAL_PROFILE


def features(path):
    lines = [line.split('=', 1)[1] for line in path.read_text().splitlines()
             if line.startswith('feature_defines=')]
    assert len(lines) == 1 and lines[0], 'feature authority missing'
    result = tuple(lines[0].split(','))
    assert len(result) == len(set(result)), 'duplicate feature'
    return result


def expected_features():
    old = features(PREDECESSOR['PROFILE'])
    assert FEATURE not in old
    return old + (FEATURE,)


def bound_features():
    result = features(C.BOUND_PROFILE)
    assert result == expected_features(), 'empty/shortened/divergent feature population'
    return result


def feature_authority():
    result = bound_features()
    return dict(predecessor=C.bind(PREDECESSOR['PROFILE']),
                successor=C.bind(C.BOUND_PROFILE), added=[FEATURE],
                predecessor_feature_count=len(result)-1,
                successor_feature_count=len(result))


def authority():
    raw = subprocess.check_output(['git', 'show', AUTHORIZATION +
        ':docs/planning/capacity-block-work-plan.md'], cwd=ROOT)
    for phrase in (b'100 bytes', b'single check', b'0.5 frame'):
        assert phrase in raw, 'commission missing: '+repr(phrase)
    assert C.bind(PREDECESSOR['ELF'])['sha256'] == 'c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c'
    assert C.bind(PREDECESSOR['PRG'])['sha256'] == 'e05a242cfd81f2c72e00d695e682e8e5eb2f017baf50ec58f2933ebcfe2e2f23'
    return dict(commit=AUTHORIZATION, plan_sha256=hashlib.sha256(raw).hexdigest(),
        predecessor={n:C.bind(PREDECESSOR[n]) for n in ('ELF','PRG','PROFILE')},
        budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1,host_images=2,device_contacts=0),
        completion='Chip-RAM single CRC check, resident ERR_CRC, no retry')


def profile(mapping=None):
    # The C root is compiled through a generated TU, not an authored input
    # row. Its source identity is bound separately, never silently omitted.
    assert mapping is not None and ROOT/AUTHORED[0] in mapping
    original = C.DIRECT
    C.DIRECT = ('src/rtov_crc_mem.s',)
    old_reader = C.B.bound_features
    C.B.bound_features = expected_features
    try:
        result = ORIGINAL_PROFILE(mapping)
    finally:
        C.DIRECT = original
        C.B.bound_features = old_reader
    lines = C.BOUND_PROFILE.read_text().splitlines()
    indices = [i for i,line in enumerate(lines) if line.startswith('feature_defines=')]
    assert len(indices) == 1
    lines[indices[0]] = 'feature_defines='+','.join(expected_features())
    C.BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    result.update(successor=C.bind(C.BOUND_PROFILE),
                  authored_templates=[C.bind(ROOT/p) for p in AUTHORED],
                  feature_authority=feature_authority())
    return result


def source_gate():
    rows={}
    for name in ('integration-test.json','crc-integrated.json'):
        receipt=json.loads((EVIDENCE/name).read_text())
        source=receipt.get('authored',receipt['source'])
        assert source['sha256']==C.bind(ROOT/source['path'])['sha256']
        assert receipt['mutations'], 'mutation evidence absent'
        rows[name]=C.bind(EVIDENCE/name)
    return dict(evidence=rows, authored=[C.bind(ROOT/p) for p in AUTHORED],
                final_ELF_proofs_pending=True, completion_retry=False)


def source_population():
    leaf=C.B.PREV.CARD.CARD2.R2.CARD
    directory=Path(tempfile.mkdtemp(prefix='source-population-',dir=PREFLIGHT))
    mapping=leaf.BASE.CHAIN.LINK.materialize_candidate_sources(directory)
    selected=bound_features()
    sources=leaf.projected_source_list(mapping,selected)
    base_sources=C.PRODUCT.source_list(selected)
    # The profile's authored and generated source selection must agree with
    # every producer-selected TU. Do not retain the predecessor's 71/36 pins.
    expected=[str(mapping.get(Path(p),Path(p))) for p in base_sources]
    assert sources==expected, 'materialized source population differs from producer'
    assert str(C.PRODUCT.F011_COLD_SOURCE) in sources
    assert C.PRODUCT.F011_COLD_FEATURE in selected
    definitions=C.PRODUCT.scoped_probe_definitions(selected)
    count_rows=[v for v in definitions if v.startswith('LISP65_RTOV_SESSION_RECORD_COUNT=')]
    assert len(count_rows)==1
    n=int(count_rows[0].split('=')[1])
    catalog=json.loads((BASE/'wplto/runtime-overlays-session-final.json').read_text())
    assert [int(s.split(':',1)[0]) for s in C.PRODUCT.SESSION_SLICE_SPECS]==[s['id'] for s in catalog['slices']]
    assert n==len(catalog['slices'])-len(C.PRODUCT.VERIFIER_SPECS)
    rejected=[]
    for name,defs in [('duplicate-feature',selected+(FEATURE,)),
                      ('caller-supplied-count',selected+('LISP65_RTOV_SESSION_RECORD_COUNT=1',))]:
        try:C.PRODUCT.scoped_probe_definitions(defs)
        except RuntimeError:rejected.append(name)
        else:raise AssertionError(name+' survived')
    specs=C.PRODUCT.SESSION_SLICE_SPECS
    try:
        for name,rows in [('missing-catalog',[]),('catalog-hole',specs[:3]+specs[4:])]:
            C.PRODUCT.SESSION_SLICE_SPECS=rows
            try:C.PRODUCT.scoped_probe_definitions(selected)
            except RuntimeError:rejected.append(name)
            else:raise AssertionError(name+' survived')
    finally:C.PRODUCT.SESSION_SLICE_SPECS=specs
    input_features,projected=leaf.BASE.CHAIN.LINK.producer_input_features()
    assert leaf.BASE.CHAIN.LINK.project_single_link_features(input_features)==selected
    value=dict(status='PASS: PRODUCER-DERIVED SOURCE/FEATURE/CACHE POPULATION',
        recorded_on=stable_recorded_on(F.SOURCE_PREFLIGHT),
        compiler_sources=dict(total=len(sources),generated=len(mapping),
                              bindings=[C.bind(Path(p)) for p in sources]),
        producer_input_features=list(input_features),projected_features=list(projected),
        feature_authority=feature_authority(),
        feature_count=len(selected),cache_count=n,cache_table_bytes=2*n,
        scoped_definitions=list(definitions),mutations_rejected=rejected)
    F.SOURCE_PREFLIGHT.write_bytes(C.canonical(value))
    return value


def preflight():
    configure()
    if C.INVOCATION.exists() and not BUILD.exists():
        # Preserve, rather than overwrite, a stopped orchestration attempt.
        # Only a stop before compile_link was reached can reuse this budget.
        stopped=C.load(PREFLIGHT/'seed-attempt.json')
        assert stopped['entered']==[] and stopped['artifacts']==[] and not stopped['completed']
        archive=Path(tempfile.mkdtemp(prefix='no-compiler-attempt-',dir=PREFLIGHT))
        for path in (C.INVOCATION,PREFLIGHT/'seed-attempt.json',F.PREFLIGHT_RECEIPT):
            path.rename(archive/path.name)
        shutil.copyfile(EVIDENCE/'seed.log',archive/'traceback.log')
    assert not C.INVOCATION.exists() and not BUILD.exists(), 'product budget already entered'
    toolchain=C.B.toolchain_identity()
    if not C.PLANE.exists(): shutil.copytree(PREDECESSOR['PLANE'],C.PLANE)
    for name in ('projected-ownership-contract.json','projected-full-map-authority.json'):
        source=BASE_PREFLIGHT/name; target=PREFLIGHT/name
        if not target.exists(): shutil.copyfile(source,target)
        assert source.read_bytes()==target.read_bytes()
    configure()
    leaf=C.B.PREV.CARD.CARD2.R2.CARD
    path=Path(tempfile.mkdtemp(prefix='profile-sources-',dir=PREFLIGHT))
    mapping=leaf.BASE.CHAIN.LINK.materialize_candidate_sources(path)
    profile_value=profile(mapping)
    configure()
    world=leaf.product_world_identity()
    assert world['selected_plane_world']['product_build_id']=='0x4a1713ab'
    assert world['selected_plane_world']['banner']=='WORKBENCH 2.0.0'
    plane=C.load(PREDECESSOR['PLANE_RECEIPT'])
    plane.update(format='capacity-window-loader-r1-plane',
        recorded_on=stable_recorded_on(F.PLANE_RECEIPT),
        status='PASS: RENDERER PLANE BOUND UNCHANGED',authority=authority(),
        product=C.bind(C.PLANE/'product/substitution-artifacts.json'),
        profile=C.bind(C.PLANE/'candidate-profile.json'),
        contract=C.bind(C.PLANE/'c2-lite-execution-contract.json'),
        header=C.bind(C.PLANE/'c2_lite_static_plane.h'),
        bank2=C.bind(C.PLANE/'v6-semantics/bank2-static-code.bin'),
        product_world_identity=world,accounting=dict(seed_WPLTO=0,final_C_LTO=0,product_links=0))
    F.PLANE_RECEIPT.write_bytes(C.canonical(plane))
    configure()
    value=dict(format='capacity-window-loader-r1-preflight',
        recorded_on=stable_recorded_on(F.PREFLIGHT_RECEIPT),
        authority=authority(),world=world,toolchain=toolchain,profile=profile_value,
        configuration=leaf.configuration_gate(),source_population=source_population(),
        semantic=source_gate(),instrument_registry=C.PRODUCT.f011_status_inventory_registration(),
        accounting=dict(seed_WPLTO=0,final_C_LTO=0,product_links=0,host_images=0,device_contacts=0))
    F.PREFLIGHT_RECEIPT.write_bytes(C.canonical(value))
    print('Card 2a preflight PASS; budget 0/0/0, no medium')


def produce_seed():
    configure()
    assert not C.INVOCATION.exists() and not BUILD.exists(), 'seed budget already entered'
    pre=C.load(F.PREFLIGHT_RECEIPT)
    assert pre['authority']==authority() and pre['toolchain']==C.B.toolchain_identity()
    assert pre['semantic']==source_gate(), 'source proof changed after preflight'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    upstream=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT).decode().strip()
    assert head==upstream, 'seed source authority must be remote-visible'
    C.INVOCATION.write_bytes(C.canonical(dict(authority=authority(),commit=head,
        preflight=C.bind(F.PREFLIGHT_RECEIPT),status='SEED ATTEMPT ENTERED',
        final_C_LTO_invocations=0,product_links=0)))
    original=C.PRODUCT.compile_link
    entered=[]
    class SeedComplete(Exception):pass
    def only_seed(out,name,*args,**kwargs):
        assert out==F.WPLTO and name=='resident-island-seed.prg' and not entered
        entered.append(name)
        original(out,name,*args,**kwargs)
        raise SeedComplete()
    C.PRODUCT.compile_link=only_seed
    completed=False
    try:
        C.B.child('_produce')
        raise AssertionError('producer returned without seed')
    except SeedComplete:
        completed=True
    finally:
        C.PRODUCT.compile_link=original
        paths=[F.WPLTO/('resident-island-seed.prg'+suffix) for suffix in ('','.elf','.lto.o')]
        evidence=dict(entered=entered,completed=completed,authority=authority(),
            artifacts=[C.bind(p) for p in paths if p.exists()],
            final_C_LTO_invocations=0,product_links=0)
        (PREFLIGHT/'seed-attempt.json').write_bytes(C.canonical(evidence))
        if completed:
            frozen=[C.bind(p) for p in paths]
            (BUILD/'seed-read-only-inventory.json').write_bytes(C.canonical(dict(before=frozen,after=frozen,
                authority=authority(),status='SEED EMITTED; OWNER AND COST QUALIFICATION PENDING')))
    print('Seed emitted; final C/LTO and product link remain unused')


def configure():
    values=dict(BUILD=BUILD,PREFLIGHT=PREFLIGHT,
        PLANE=PREFLIGHT/'setup-owned/static-plane/narrow-static',WPLTO=BUILD/'wplto',
        ELF=BUILD/'wplto/lisp65-c2-substitution-linked.prg.elf',
        PRG=BUILD/'wplto/lisp65-c2-substitution-linked.prg',
        PROFILE=BUILD/'wplto/resolved-profile.txt',BOUND_PROFILE=PREFLIGHT/'bound-feature-profile.txt',
        INVOCATION=PREFLIGHT/'candidate-invocation.json',AUTHORIZATION=AUTHORIZATION,
        PLAN_HEADER='### Card 2a — completion contract: adopt the chip-RAM single check (2026-09-07)',
        FORMAT='capacity-window-loader-r1',STATUS='PENDING: CARD 2a QUALIFICATION',
        DRIVER=Path(__file__).resolve(),REPORT=ROOT/'docs/planning/capacity-window-loader-product-report.md')
    for name in ('PLANE_RECEIPT','PREFLIGHT_RECEIPT','SOURCE_PREFLIGHT','PRELINK_RED','DIFFERENCE','RECEIPT'):
        values[name]=PREFLIGHT/(name.lower().replace('_','-')+'.json')
    PREFLIGHT.mkdir(parents=True,exist_ok=True)
    for name,value in values.items(): setattr(F,name,value)
    F.OLD.update(PREDECESSOR)
    F.authority=authority; F.profile=profile; F.source_gate=source_gate
    C.B.bound_features=bound_features
    C.B.bound_feature_authority=feature_authority
    ORIGINAL_CONFIGURE()
    C.PRODUCT.SESSION_RECORD_CACHE_ENABLED=True
    C.PLAN=ROOT/'docs/planning/capacity-block-work-plan.md'
    C.B.PLAN=C.PLAN
    C.DIRECT=AUTHORED
    C.B.DIRECT_CARD6_SOURCES=AUTHORED
    C.B.HEADER_ROOTS=AUTHORED
    C.B.PREV.bound_features=bound_features
    C.B.PREV.CARD.CARD2.R2.CARD.materialize_bound_feature_profile=feature_authority
    C.B.PREV.CARD.CARD2.R2.source_preflight=source_population


if __name__=='__main__':
    F.configure=configure
    if sys.argv[1:]==['preflight']:preflight()
    elif sys.argv[1:]==['produce']:produce_seed()
    else:F.main()
