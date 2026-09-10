#!/usr/bin/env python3
"""Pack the unchanged qualified renderer world; no product compiler or linker."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
import hardware_sp_seed_media as COMMON
from hardware_sp_seed_media import CAN,MEDIA,COMPOSE,DELIVERY,D81,ElfTruth,H,bind
ROOT=COMMON.ROOT
PRODUCT=ROOT/'build/v2.1/renderer-branch-product-r1'
FINAL=PRODUCT/'wplto'
PLANE=ROOT/'build/v2.1/renderer-branch-product-r1-preflight/setup-owned/static-plane/narrow-static'
OUT=ROOT/'build/v2.1/renderer-native-session-r3'
PAIR={'elf':'c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c',
      'prg':'e05a242cfd81f2c72e00d695e682e8e5eb2f017baf50ec58f2933ebcfe2e2f23'}
def pair():
    p=FINAL/'lisp65-c2-substitution-linked.prg'
    result={'elf':bind(Path(str(p)+'.elf')),'prg':bind(p)}
    assert all(result[k]['sha256']==v for k,v in PAIR.items())
    return result
def qualification():
    frozen=pair()
    receipt=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/v2.1-renderer-branch-product-r1-receipt.json'
    record=json.loads(receipt.read_text())
    assert [r['sha256'] for r in record['pair']]==[PAIR['elf'],PAIR['prg']]
    for p in (FINAL/'owner-scope-result.json',PRODUCT/'artifact-acceptance.json'):
        assert json.loads(p.read_text())['status']=='PASS'
    log=PRODUCT/'check-source-after-cadc26ea.log'
    assert bind(log)['sha256']=='c38cc05172531fcbb8ec02bf079e0753c89890e792823ef19d501ed885c48b73'
    plan=subprocess.check_output(['git','show','831a48eb:docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'OWNER RATIFICATION' in plan and b'No new product build or link is authorized' in plan
    return dict(pair=frozen,product_receipt=bind(receipt),full_source_log=bind(log),
                exception='c2-v110-persistent-performance-check Carrier pin only',
                authority='831a48eb',product_builds=0)
def pack():
    q=qualification();frozen=pair()
    OUT.mkdir(parents=True,exist_ok=True)
    packed=OUT/'packed';assert not packed.exists(),'one-shot pack; inspect stop before retry'
    packed.mkdir()
    target,completion=complete()
    elf=Path(str(target)+'.elf');plane=PLANE
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
        'c2-session-family-region-0':target.parent/'runtime-overlays-session-final.bin',
        'c2-product-shelf':plane/'product/product-shelf-v4-direct.bin',
        'c2-boot-family':target.parent/'runtime-overlays-boot-final.bin',
        'c2-session-family-region-1':target.parent/'runtime-overlays-session-final-region1.bin',
        'c2-kernal-window':target.parent/'c2-product-kernal-window.bin',
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
    medium=packed/'v21-renderer.d81'
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
    assert pair()==frozen
    value=dict(status='PACKED RENDERER WORLD; PREFILTER PENDING',qualification=q,
        medium=bind(medium),pair=frozen,completion=completion,boot_geometry=bootgeometry,
        artifacts={k:bind(v) for k,v in roles.items()},stager=stager_gate,
        descriptor=parsed,descriptor_mutations=mutations,domains=domains,reset=reset,
        closure=closure,coherence=coherence,product_compiler_calls=0,product_links=0,
        cold_stager_builds=1,device_contacts=0)
    (OUT/'packed-receipt.json').write_text(json.dumps(value,indent=2)+'\n')
    print(value['status'],bind(medium)['sha256'])
def complete():
    import c2_v160_nested_map_swap_media as NESTED
    destination=OUT/'completion';assert not destination.exists(),'inspect previous completion stop'
    shutil.copytree(FINAL,destination)
    target=destination/'lisp65-c2-substitution-linked.prg';elf=Path(str(target)+'.elf')
    predecessors=NESTED.materialize_candidate_publish_predecessors(destination,target,elf)
    # This is already a fully published final product, not a seed. Re-running
    # finish_single_link would re-enter the earlier KERNAL-only publish stage
    # with the later verifier domain present. Materialize all three existing
    # predecessors together; their declared domains are checked by NESTED.
    before=Path(pair()['prg']['path']).read_bytes();after=target.read_bytes()
    address,expected=COMMON.FACADE.facade_truth(elf)
    raw,offset=COMMON.FACADE.prg_span(target,address,len(expected))
    assert len(before)==len(after)
    assert before[:offset]==after[:offset] and before[offset+len(expected):]==after[offset+len(expected):]
    assert after[offset:offset+len(expected)]==expected
    for name in ('c2-product-kernal-window.bin','runtime-overlays-boot-final.bin',
                 'runtime-overlays-session-final.bin','runtime-overlays-session-final-region1.bin'):
        assert (destination/name).read_bytes()==(FINAL/name).read_bytes()
    facade=COMMON.FACADE.packed_facade_gate(target,elf)
    assert bind(elf)['sha256']==PAIR['elf']
    result=dict(before=pair(),after_prg=bind(target),elf=bind(elf),facade=facade,
                predecessors=predecessors,product_compilers=0,product_links=0)
    (OUT/'completion-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return target,result
def check():
    value=json.loads((OUT/'packed-receipt.json').read_text())
    assert value['pair']==pair()
    for record in [value['medium'],*value['artifacts'].values()]:
        assert bind(record['path'])==record
    qualification()
    print('PACKED PAIR AND ARTIFACT IDENTITIES PASS')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['pack','check']);a=ap.parse_args()
    {'pack':pack,'check':check}[a.action]()
