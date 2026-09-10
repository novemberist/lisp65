#!/usr/bin/env python3
"""Artifact-only seed materialization. Never invokes the product compiler."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

import hardware_sp_fallback_card as H
import c2_v160_refill_boundary_witness_media_repair as FACADE
import c2_lite_canonical_product as CAN
import c2_lite_media_product as MEDIA
import c2_v200_block3_return_device_media as COMPOSE
import c2_v200_tier2_delivery_device_media as DELIVERY
import d81_persistence_fault as D81
from elf_truth import ElfTruth

ROOT=H.ROOT
SOURCE=ROOT/'build/v2.1/hardware-sp-fallback-r1-evidence'
PRODUCER=(ROOT.parent / 'lisp65-comfort-stack-seed-r1')
SEED=PRODUCER/'build/v2.1/hardware-sp-fallback-r1'
PLANE=PRODUCER/'build/v2.1/hardware-sp-fallback-r1-preflight/setup-owned/static-plane/narrow-static'
OUT=ROOT/'build/v2.1/hardware-sp-seed-medium-r1'
FINAL=OUT/'materialized'
AUTH='44f48798'

def bind(p):
    p=Path(p);raw=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def authority():
    raw=subprocess.check_output(['git','show',AUTH+':docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'additional host-only image for the seed measurement' in raw
    assert bind(SEED/'wplto/resident-island-seed.prg.elf')['sha256']=='e188f201de545201ceff60cd20393949af5554c61c149124a113411c0aa4b730'
    return dict(commit=AUTH,plan_sha256=hashlib.sha256(raw).hexdigest(),measurement_only=True,
                seed_rebuilds=0,product_links=0,additional_host_images=1,device_contacts=0)

def setup():
    H.configure()
    H.P.F.C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.setup_link_world()
    p=H.P.F.C.PRODUCT
    def forbidden(*a,**kw):
        raise RuntimeError('product compiler/link forbidden in seed media')
    p.compile_link=forbidden
    p.PRODUCT_ARTIFACTS_MANIFEST=PLANE/'product/substitution-artifacts.json'
    p.INITIAL_C2D=PLANE/'product/initial.c2d-v3.bin'
    p.PRODUCT_SHELF=PLANE/'product/product-shelf-v4-direct.bin'
    t=ElfTruth.read(SOURCE/'resident-island-seed.prg.elf',llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    p.VERIFIER_BINDING_BASE=p.LINK60_VERIFIER_BINDING_BASE=t.section(p.VERIFIER_BINDING_SECTION).address
    return p

def materialize():
    auth=authority();assert not OUT.exists(),'one-shot materialization; inspect any prior stop'
    OUT.mkdir(parents=True)
    frozen=[bind(SEED/'wplto'/('resident-island-seed.prg'+s)) for s in ('','.elf','.lto.o','.map')]
    p=setup()
    shutil.copytree(SEED/'wplto',FINAL)
    target=FINAL/'lisp65-c2-substitution-linked.prg'
    for s in ('','.elf','.map','.lto.o'):
        shutil.copyfile(FINAL/('resident-island-seed.prg'+s),Path(str(target)+s))
    shutil.copytree(PLANE,FINAL/'fresh-c2-lite-prelink-gates')
    # The seed is immutable; only the artifact copy receives the normal
    # facade and publish-last transformations.
    facade=FACADE.materialize_facade(target,Path(str(target)+'.elf'),FINAL/'facade-materialization.json')
    p.finish_single_link(FINAL,target,FINAL/'resolved-profile.txt')
    assert frozen==[bind(SEED/'wplto'/('resident-island-seed.prg'+s)) for s in ('','.elf','.lto.o','.map')]
    result=dict(status='SEED MATERIALIZED; NOT PRODUCT QUALIFICATION',authority=auth,
        frozen=frozen,materialized_prg=bind(target),elf=bind(Path(str(target)+'.elf')),
        facade=facade,compiler_calls=0,product_links=0,host_images=0)
    (OUT/'materialization.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])

def pack():
    auth=authority();p=setup()
    source_plane=PLANE
    plane=FINAL/'fresh-c2-lite-prelink-gates'
    for path in source_plane.rglob('*'):
        if path.is_file():
            assert path.read_bytes()==(plane/path.relative_to(source_plane)).read_bytes()
    record=json.loads((OUT/'materialization.json').read_text())
    target=FINAL/'lisp65-c2-substitution-linked.prg';elf=Path(str(target)+'.elf')
    assert record['materialized_prg']==bind(target) and record['elf']==bind(elf)
    frozen=[bind(SEED/'wplto'/('resident-island-seed.prg'+s)) for s in ('','.elf','.lto.o','.map')]
    assert frozen==record['frozen']
    packed=OUT/'packed';assert not packed.exists(),'one additional image; no implicit retry'
    packed.mkdir()
    CAN.ARTIFACTS=packed/'artifacts';CAN.ARTIFACTS.mkdir()
    bootstage,bootgeometry=CAN.build_boot_stage(elf,FINAL/'resolved-profile.txt')
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    names=[s.name for s in truth.sections if s.name.startswith('.lisp65_c2_mapped_')
           and truth.symbols_by_name.get('__'+s.name.removeprefix('.')+'_load_start')
           and truth.symbol('__'+s.name.removeprefix('.')+'_load_start').value<0x30000]
    mapped=COMPOSE.mapped_section_rows(truth,names)
    prefix=(plane/'v6-semantics/bank2-static-code.bin').read_bytes()
    assert len(prefix)==47795
    base=0x20000;end=max(start+len(raw) for start,raw,_ in mapped)
    image=bytearray(end-base);image[:len(prefix)]=prefix;cursor=base+len(prefix)
    for start,raw,name in mapped:
        assert start>=cursor;image[start-base:start-base+len(raw)]=raw;cursor=start+len(raw)
    code=CAN.ARTIFACTS/'bank2-static-code.bin';code.write_bytes(image)
    reference=ROOT/'build/v2.1/f011-buffered-repair-r1/packed-prefilter/product/media/canonical-product/canonical-product-manifest.json'
    old={r['role']:r for r in json.loads(reference.read_text())['artifacts']}
    roles={'linked-product-elf':elf,'c2-resident-prg':target,
        'c2-bank2-static-code-plane':code,
        'c2d-v6-code-plane':plane/'v6-semantics/initial.c2d-v6.bin',
        'c2-two-record-boot-stage':bootstage,
        'c2-session-family-region-0':FINAL/'runtime-overlays-session-final.bin',
        'c2-product-shelf':plane/'product/product-shelf-v4-direct.bin',
        'c2-boot-family':FINAL/'runtime-overlays-boot-final.bin',
        'c2-session-family-region-1':FINAL/'runtime-overlays-session-final-region1.bin',
        'c2-kernal-window':FINAL/'c2-product-kernal-window.bin',
        'resolved-profile':FINAL/'resolved-profile.txt'}
    for role in ('library-ide','library-idex','library-m65d'):
        path=ROOT/old[role]['path'];assert bind(path)['sha256']==old[role]['sha256'];roles[role]=path
    assert set(roles)==set(old)
    MEDIA.BUILD=packed
    contract=MEDIA.load(MEDIA.CONTRACT)
    staged,reset=MEDIA.stage_artifact_map(contract,roles,write=True)
    rows=MEDIA.media_rows(contract,staged)
    descriptor,build_id=MEDIA.make_descriptor(rows,int(MEDIA.sha(roles['resolved-profile'])[:8],16))
    desc=packed/'boot.id';desc.write_bytes(descriptor)
    parsed=MEDIA.parse_descriptor(descriptor,build_id,rows)
    mutations=MEDIA.mutation_gate(descriptor,build_id,rows)
    domains=MEDIA.stage_domain_gate(rows)
    stager=packed/'autoboot.c65'
    opt=COMPOSE.BASE.MEDIA.PREP.LIVENESS.OPT_IN
    stager_gate=MEDIA.compile_stager(build_id,rows,build_dir=packed,stager=stager,
        stager_map=Path(str(stager)+'.map'),compile_defines=(opt,))
    medium=packed/'hardware-sp-seed.d81'
    entries=[(stager,'autoboot.c65'),(desc,'boot.id'),*[(r['path'],r['name']) for r in rows]]
    MEDIA.build_d81(medium,'L65SYS,65',entries);MEDIA.D81.stamp_product_boot_marker(medium)
    actual=D81.visible_files(medium.read_bytes())
    expected={name.upper().encode():path.read_bytes() for path,name in entries}
    assert actual==expected,'packed role bytes differ'
    assert not any(b'COMFORT' in name or b'V16CORE' in name for name in actual)
    assert actual[b'CODE.BIN']==bytes(image)
    # Run the established closure and generation consumers over the readback
    # prefix; do not substitute the pre-pack source population.
    projection=packed/'readback-product';shutil.copytree(plane/'product',projection)
    manifest=json.loads((projection/'substitution-artifacts.json').read_text())
    keys=H.P.F.C.B.PREV.CARD.CARD2.R2.CARD.BASE.PRODUCT_KEYS
    offset=0
    for key in keys:
        source=projection/(key+'.code.bin');n=source.stat().st_size
        source.write_bytes(actual[b'CODE.BIN'][offset:offset+n]);offset+=n
    assert offset==len(prefix)
    closure=DELIVERY.CLOSURE.derive(projection/'substitution-artifacts.json');DELIVERY.CLOSURE.require_closed(closure)
    stdlib=(projection/'stdlib-p0.code.bin').read_bytes()
    coherence=DELIVERY.COHERENCE.derive(plane/'stdlib-p0.manifest.json',plane/'product/stdlib-p0.code.bin',
        DELIVERY.PRICE.STDLIB_SUITE,stdlib)
    DELIVERY.COHERENCE.require_coherent(coherence)
    assert frozen==[bind(SEED/'wplto'/('resident-island-seed.prg'+s)) for s in ('','.elf','.lto.o','.map')]
    value=dict(status='PACKED SEED MEASUREMENT IMAGE; NOT PRODUCT OR DEVICE ACCEPTANCE',
        authority=auth,medium=bind(medium),elf=bind(elf),frozen=frozen,boot_geometry=bootgeometry,
        artifacts={k:bind(v) for k,v in roles.items()},stager=stager_gate,
        descriptor=parsed,descriptor_mutations=mutations,domains=domains,reset=reset,
        closure=closure,coherence=coherence,product_compiler_calls=0,product_links=0,
        cold_stager_builds=1,seed_measurement_images=1,final_prefilter_images=0,device_contacts=0)
    (OUT/'packed-receipt.json').write_text(json.dumps(value,indent=2)+'\n')
    print(value['status'],bind(medium)['sha256'])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['materialize','pack']);a=ap.parse_args()
    {'materialize':materialize,'pack':pack}[a.action]()
