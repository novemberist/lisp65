"""Artifact-only Card 2b media adapter, with an explicit third physical owner.

No product compiler/link is permitted. This is a measurement image only.
"""
from pathlib import Path
import copy
import hashlib
import json
import shutil
import struct
import sys
import inspect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import capacity_disk_window_product_card as CARD
import runtime_overlay_bank as BANK
import c2_v160_refill_boundary_witness_media_repair as FACADE
from elf_truth import ElfTruth

OUT = ROOT/'build/capacity/card2b-seed-medium-r1'
FINAL = OUT/'materialized'
SOURCE_STEM = 'resident-island-seed.prg'
ROLE = 'seed'
PLANE = CARD.PREFLIGHT/'setup-owned/static-plane/narrow-static'
P = CARD.PRODUCT
ORIGINAL_PACK = P.overlay_pack_family
ORIGINAL_VALIDATE = P._validate_family_artifact
ORIGINAL_NEGATIVE = P._family_identity_negative_selftest

def bind(p):
    return dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)

def write(p, value):
    p.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def select_final():
    global OUT, FINAL, SOURCE_STEM, ROLE
    OUT = ROOT/'build/capacity/card2b-final-medium-r1'
    FINAL = OUT/'materialized'
    SOURCE_STEM = 'lisp65-c2-substitution-linked.prg'
    ROLE = 'final-prefilter'

def frozen_sources():
    return [bind(CARD.BUILD/'wplto'/(SOURCE_STEM+s)) for s in ('','.elf','.lto.o','.map')]

def prepare_final_unbound():
    """Facade precedes both publish-last stages in the owned media copy.

    A fully published PRG is not a KERNAL-only continuation. Replaying from
    its bound unbound copy is artifact materialization, never a new link.
    Frozen producer artifacts and all publication-domain checks stay intact.
    """
    assert ROLE=='final-prefilter'
    marker=OUT/'facade-publication-order.json'
    assert not marker.exists()
    target=FINAL/'lisp65-c2-substitution-linked.prg';elf=Path(str(target)+'.elf')
    source=CARD.BUILD/'wplto'
    unbound=FINAL/'lisp65-c2-substitution-unbound.prg'
    assert unbound.read_bytes()==(source/unbound.name).read_bytes()
    raw=(source/target.name).read_bytes()
    address,facade=FACADE.facade_truth(elf)
    expected,offset=FACADE.prg_span(source/target.name,address,len(facade))
    assert expected[offset:offset+len(facade)]==bytes(len(facade))
    expected[offset:offset+len(facade)]=facade
    assert target.read_bytes()==bytes(expected), 'media copy changed outside facade'
    proof=FACADE.materialize_facade(unbound,elf,OUT/'unbound-facade-materialization.json')
    prior=bind(target)
    target.write_bytes(unbound.read_bytes())
    write(marker,dict(status='FACADE PRECEDES EXISTING PUBLISH-LAST STAGES',
        source_final=bind(source/target.name),source_unbound=bind(source/unbound.name),
        prior_materialized_final=prior,unbound_facade=proof,
        product_builds=0,product_links=0,extra_images=0))

def verify_final_materialization():
    if ROLE!='final-prefilter':return
    target=FINAL/'lisp65-c2-substitution-linked.prg';elf=Path(str(target)+'.elf')
    address,facade=FACADE.facade_truth(elf)
    expected,offset=FACADE.prg_span(CARD.BUILD/'wplto'/SOURCE_STEM,address,len(facade))
    expected[offset:offset+len(facade)]=facade
    assert target.read_bytes()==bytes(expected), 'final completion changed more than the ELF-owned facade'

def payload(elf):
    t = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN/'llvm-readobj', include_section_data=True)
    s = t.section(CARD.D.SECTION)
    a = t.symbol('__card2b_payload_load_start').value
    e = t.symbol('card2b_disk_entry').value
    owner = CARD.D.receipt('owner-projection.json')['owner']
    assert a == owner['payload']['start'] and a % 256 == 0
    assert s.bytes <= owner['payload']['capacity'] and s.address <= e < s.address+s.bytes
    return t.section_bytes(s.name), a, s.address, e, owner

def make_record(data, source, vma, entry, count, build_id):
    flags = BANK.FLAG_RUNTIME | BANK.FLAG_REUSABLE
    region_word = 2 | (((source >> 16) & 15) << 8) | (((source >> 20) & 255) << 16)
    raw = bytearray(BANK.ENTRY.pack(count, flags, source & 65535, len(data), vma,
        len(data), entry-vma, BANK.ENTRY_ABI, build_id, BANK.crc16_ccitt_false(data), 0, region_word, 0))
    crc = BANK.crc16_ccitt_false(raw)
    assert crc
    struct.pack_into('<H', raw, 22, crc)
    return bytes(raw)

def pack_family(out, target, contract, family, suffix):
    if family != 'session':
        return ORIGINAL_PACK(out, target, contract, family, suffix)
    specs = P.SESSION_SLICE_SPECS
    assert len(specs) == 53 and specs[-1].split(':')[2] == CARD.D.SECTION
    try:
        P.SESSION_SLICE_SPECS = specs[:-1]
        image, manifest = ORIGINAL_PACK(out, target, contract, family, suffix)
    finally:
        P.SESSION_SLICE_SPECS = specs
    value = json.loads(manifest.read_text())
    data, source, vma, entry, owner = payload(Path(str(target)+'.elf'))
    raw = bytearray(image.read_bytes())
    count = value['catalog']['slice_count']
    assert count == 52 and [r['id'] for r in value['slices']] == list(range(count))
    start = BANK.HEADER_SIZE + count*BANK.ENTRY_SIZE
    assert start+BANK.ENTRY_SIZE <= value['catalog']['payload_offset']
    assert not any(raw[start:start+BANK.ENTRY_SIZE])
    record = make_record(data, source, vma, entry, count, value['profile_build_id'])
    raw[start:start+len(record)] = record
    # Header's count is one byte in L65R v4; use the format struct, not an offset pin.
    header = list(BANK.HEADER.unpack(raw[:BANK.HEADER_SIZE])); header[4] = count+1
    raw[:BANK.HEADER_SIZE] = BANK.HEADER.pack(*header)
    BANK._refresh_catalog_crcs(raw)
    image.write_bytes(raw)
    blob = out/f'runtime-overlays-session-{suffix}-region2.bin'; blob.write_bytes(data)
    value['external_storage'] = dict(region_id=2, file=blob.name, source_address=source,
        bytes=len(data), sha256=bind(blob)['sha256'], crc16=BANK.crc16_ccitt_false(data), owner=owner)
    value['storage'].update(size=len(raw), crc16=BANK.crc16_ccitt_false(raw), sha256=bind(image)['sha256'])
    fields = BANK.HEADER.unpack(raw[:BANK.HEADER_SIZE])
    value['catalog'].update(slice_count=count+1, directory_crc16=fields[12], header_crc16=fields[13])
    value['slices'].append(dict(id=count, name='f011-write-member', section=CARD.D.SECTION,
        start_symbol='__lisp65_rt_card2b_disk_start', end_symbol='__lisp65_rt_card2b_disk_end',
        entry_symbol='__lisp65_rt_card2b_disk_entry', flags=BANK.FLAG_RUNTIME|BANK.FLAG_REUSABLE,
        roles=BANK._roles(BANK.FLAG_RUNTIME|BANK.FLAG_REUSABLE), file_offset=0, file_size=len(data),
        memory_size=len(data), vma=vma, end=vma+len(data), entry=entry, entry_offset=entry-vma,
        abi_version=BANK.ENTRY_ABI, slice_build_id=value['profile_build_id'], capability_mask=0,
        crc16=BANK.crc16_ccitt_false(data), record_crc16=struct.unpack_from('<H',record,22)[0],
        sha256=bind(blob)['sha256'], region_id=2, source_address=source))
    write(manifest,value)
    validate(image,value,'third-owner-pack')
    return image,manifest

def validate(image,value,label):
    if 'external_storage' not in value:
        return ORIGINAL_VALIDATE(image,value,label)
    ext = value['external_storage']; data=(image.parent/ext['file']).read_bytes()
    r=value['slices'][-1]; raw=image.read_bytes()
    elf=image.parent/value['elf']['file']
    assert bind(elf)['sha256']==value['elf']['sha256']
    expected_data,expected_source,expected_vma,expected_entry,expected_owner=payload(elf)
    assert (data,r['source_address'],r['vma'],r['entry'],ext['owner']) == \
        (expected_data,expected_source,expected_vma,expected_entry,expected_owner)
    assert ext['region_id']==r['region_id']==2 and r['id']==len(value['slices'])-1==52
    assert ext['source_address']==r['source_address']==ext['owner']['payload']['start']
    assert ext['bytes']==r['file_size']==len(data)<=ext['owner']['payload']['capacity']
    assert hashlib.sha256(data).hexdigest()==ext['sha256']==r['sha256']
    assert BANK.crc16_ccitt_false(data)==ext['crc16']==r['crc16']
    expected=make_record(data,r['source_address'],r['vma'],r['entry'],r['id'],value['profile_build_id'])
    start=BANK.HEADER_SIZE+r['id']*BANK.ENTRY_SIZE
    assert raw[start:start+BANK.ENTRY_SIZE]==expected
    projected=bytearray(raw); projected[start:start+BANK.ENTRY_SIZE]=bytes(BANK.ENTRY_SIZE)
    header=list(BANK.HEADER.unpack(projected[:BANK.HEADER_SIZE])); assert header[4]==53
    header[4]-=1; projected[:BANK.HEADER_SIZE]=BANK.HEADER.pack(*header); BANK._refresh_catalog_crcs(projected)
    overflow=(image.parent/value['overflow_storage']['file']).read_bytes()
    main_bases={row['source_address']-row['file_offset'] for row in value['slices'] if row['region_id']==0}
    assert len(main_bases)==1
    overflow_base=(value['overflow_storage']['bank']<<16)+value['overflow_storage']['address']
    parsed=BANK.validate_region_images(bytes(projected),overflow,expected_build_id=value['profile_build_id'],
        expected_vma=value['policy']['common_vma'],max_slice_bytes=value['policy']['max_slice_bytes'],
        format_version=4,main_source_base=main_bases.pop(),overflow_source_base=overflow_base)
    assert len(parsed.slices)==52
    # Verify the actual enlarged catalog checksums too, not just its projection.
    refreshed=bytearray(raw);BANK._refresh_catalog_crcs(refreshed);assert bytes(refreshed)==raw
    ordinary=copy.deepcopy(value);ordinary['slices']=ordinary['slices'][:-1]
    ORIGINAL_VALIDATE(image,ordinary,label)

def negative(image,manifest):
    value=json.loads(manifest.read_text())
    if 'external_storage' not in value:return ORIGINAL_NEGATIVE(image,manifest)
    source=image.parent/value['external_storage']['file'];p=source.with_suffix('.negative')
    raw=bytearray(source.read_bytes());raw[len(raw)//2]^=1;p.write_bytes(raw)
    value['external_storage']['file']=p.name
    try:
        validate(image,value,'third-owner-mutation')
    except (AssertionError,RuntimeError):return 'rejected'
    finally:p.unlink()
    raise AssertionError('corrupted third-owner payload survived')

def setup():
    CARD.configure()
    CARD.C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.setup_link_world()
    CARD.bind_member()
    def forbidden(*args,**kwargs):raise RuntimeError('product compiler/link forbidden in seed measurement')
    P.compile_link=forbidden
    P.PRODUCT_ARTIFACTS_MANIFEST=PLANE/'product/substitution-artifacts.json'
    P.INITIAL_C2D=PLANE/'product/initial.c2d-v3.bin'
    P.PRODUCT_SHELF=PLANE/'product/product-shelf-v4-direct.bin'
    P.overlay_pack_family=pack_family
    P._validate_family_artifact=validate
    P._family_identity_negative_selftest=negative
    t=ElfTruth.read(CARD.BUILD/'wplto'/(SOURCE_STEM+'.elf'),llvm_readobj=P.TOOLCHAIN/'llvm-readobj')
    P.VERIFIER_BINDING_BASE=P.LINK60_VERIFIER_BINDING_BASE=t.section(P.VERIFIER_BINDING_SECTION).address

def materialize():
    assert not OUT.exists(),'one artifact-only seed copy; resume explicitly after any stop'
    frozen=frozen_sources()
    setup();OUT.mkdir(parents=True)
    shutil.copytree(CARD.BUILD/'wplto',FINAL)
    target=FINAL/'lisp65-c2-substitution-linked.prg'
    if ROLE == 'seed':
        for s in ('','.elf','.lto.o','.map'):shutil.copyfile(FINAL/(SOURCE_STEM+s),Path(str(target)+s))
    plane_copy=FINAL/'fresh-c2-lite-prelink-gates'
    if plane_copy.exists():
        for path in PLANE.rglob('*'):
            if path.is_file(): assert path.read_bytes()==(plane_copy/path.relative_to(PLANE)).read_bytes()
    else: shutil.copytree(PLANE,plane_copy)
    write(OUT/'frozen.json',frozen)
    facade=FACADE.materialize_facade(target,Path(str(target)+'.elf'),FINAL/'facade-materialization.json')
    if ROLE=='final-prefilter':prepare_final_unbound()
    P.finish_single_link(FINAL,target,FINAL/'resolved-profile.txt')
    verify_final_materialization()
    assert frozen==frozen_sources()
    write(OUT/'materialization.json',dict(status=ROLE.upper()+' HOST IMAGE ONLY',frozen=frozen,facade=facade,
        prg=bind(target),elf=bind(Path(str(target)+'.elf')),product_builds=0,host_images=0,contacts=0))

def resume():
    frozen=json.loads((OUT/'frozen.json').read_text())
    assert frozen==frozen_sources()
    assert not (OUT/'materialization.json').exists()
    setup()
    target=FINAL/'lisp65-c2-substitution-linked.prg'
    if ROLE=='final-prefilter' and not (OUT/'facade-publication-order.json').exists():
        prepare_final_unbound()
    P.finish_single_link(FINAL,target,FINAL/'resolved-profile.txt')
    verify_final_materialization()
    assert frozen==frozen_sources()
    write(OUT/'materialization.json',dict(status=ROLE.upper()+' HOST IMAGE ONLY',frozen=frozen,
        prg=bind(target),elf=bind(Path(str(target)+'.elf')),product_builds=0,host_images=0,contacts=0))

def pack():
    import hardware_sp_seed_media as BASE
    record=json.loads((OUT/'materialization.json').read_text())
    record['materialized_prg']=record['prg']
    write(OUT/'materialization.json',record)
    BASE.OUT,BASE.FINAL,BASE.PLANE,BASE.SEED=OUT,FINAL,PLANE,CARD.BUILD
    BASE.setup=setup
    BASE.bind=bind
    BASE.authority=lambda:dict(commit='e0957b82',data_conversion='23bd3aeb',cost_disposition='df7cd1fe',
        role=ROLE,measurement_only=True,product_builds=0,host_images=1,device_contacts=0)
    original=BASE.COMPOSE.mapped_section_rows
    def composed(truth,names):
        rows=original(truth,names)
        data,source,_,_,owner=payload(FINAL/'lisp65-c2-substitution-linked.prg.elf')
        assert all(source+len(data)<=start or source>=start+len(raw) for start,raw,_ in rows)
        rows.append((source,data,CARD.D.SECTION))
        return sorted(rows)
    BASE.COMPOSE.mapped_section_rows=composed
    code=inspect.getsource(BASE.pack)
    assert code.count("'hardware-sp-seed.d81'")==1
    code=code.replace("'hardware-sp-seed.d81'",repr('card2b-'+ROLE+'.d81'))
    assert code.count("'resident-island-seed.prg'")==2
    code=code.replace("'resident-island-seed.prg'",repr(SOURCE_STEM))
    # All staging, facade, packed readback and both pack gates remain the
    # established path. Only the selected world and its explicit owner differ.
    namespace=dict(BASE.__dict__)
    exec(compile(code,str(Path(BASE.__file__)),'exec'),namespace)
    namespace['pack']()
    value=json.loads((OUT/'packed-receipt.json').read_text())
    value['inherited_media_adapter']=bind(Path(BASE.__file__))
    value['card_adapter']=bind(Path(__file__))
    value['external_owner']=json.loads((FINAL/'runtime-overlays-session-final.json').read_text())['external_storage']
    value['status']=ROLE.upper()+' HOST IMAGE; NOT DEVICE ACCEPTANCE'
    value['seed_measurement_images']=int(ROLE=='seed')
    value['final_prefilter_images']=int(ROLE=='final-prefilter')
    write(OUT/'packed-receipt.json',value)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--final':
        select_final();sys.argv.pop(1)
    if sys.argv[1:]==['materialize']:materialize()
    elif sys.argv[1:]==['resume']:resume()
    elif sys.argv[1:]==['pack']:pack()
    else:raise SystemExit('artifact-only materialize/resume')
