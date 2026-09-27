"""Artifact-only Card L Seed delivery. Never compiles or links the runtime.

Refresh inherited fixed-size records directly from the immutable Seed ELF,
retain their placement, publish the established CRC binding domains in a
PRG copy, and invoke the committed Card L adapter for slot 55 and markers.
Only that adapter compiles/links cold delivery stagers.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import card_l_producer as P
import card_l_seed_media as MEDIA
import runtime_overlay_bank as B
from elf_truth import ElfTruth

ROOT=P.ROOT
OUT=ROOT/'build/card-l-seed-medium-r2'
WORLD=OUT/'materialized'
BASE=ROOT/'build/nested-error-recovery-seed-medium-r1'
SEED=ROOT/'build/card-l-product-r1/wplto'

def sha(data):return hashlib.sha256(data).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def bind(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))

def refresh_family(family,before,after):
    m=json.loads((BASE/'materialized'/f'runtime-overlays-{family}-final.json').read_text())
    main=m['storage']; overflow=m['overflow_storage'];ext=m.get('external_storage')
    paths={0:main['file'],1:overflow['file']}
    if ext:paths[2]=ext['file']
    regions={k:bytearray((BASE/'materialized'/p).read_bytes()) for k,p in paths.items()}
    assert sha(regions[0])==main['sha256'] and sha(regions[1])==overflow['sha256']
    if ext:assert sha(regions[2])==ext['sha256']
    proof=[]
    for row in m['slices']:
        old=before.section_bytes(row['section']);new=after.section_bytes(row['section'])
        offset=row['file_offset'];region=row['region_id'];size=row['file_size']
        assert len(old)==len(new)==size
        assert regions[region][offset:offset+size]==old,(family,row['id'],'baseline extraction mismatch')
        assert after.section(row['section']).address==row['vma']
        regions[region][offset:offset+size]=new
        row.update(crc16=B.crc16_ccitt_false(new),sha256=sha(new))
        at=B.HEADER_SIZE+row['id']*B.ENTRY_SIZE
        record=bytearray(regions[0][at:at+B.ENTRY_SIZE])
        struct.pack_into('<H',record,20,row['crc16']);struct.pack_into('<H',record,22,0)
        row['record_crc16']=B.crc16_ccitt_false(record);assert row['record_crc16']
        struct.pack_into('<H',record,22,row['record_crc16'])
        regions[0][at:at+B.ENTRY_SIZE]=record
        proof.append(dict(id=row['id'],section=row['section'],before_sha256=sha(old),after_sha256=sha(new),region=region,offset=offset,bytes=size))
    # V4 authenticates the overflow tenant in header bytes 28..31, in
    # addition to each record's payload CRC. Re-extraction changes both.
    struct.pack_into('<HH', regions[0], 28, len(regions[1]),
        B.crc16_ccitt_false(regions[1]) if regions[1] else 0)
    B._refresh_catalog_crcs(regions[0])
    h=B.HEADER.unpack_from(regions[0]);m['catalog'].update(directory_crc16=h[12],header_crc16=h[13])
    for k,path in paths.items():(WORLD/path).write_bytes(regions[k])
    for key,k in [('storage',0),('overflow_storage',1)]+([('external_storage',2)] if ext else []):
        m[key].update(sha256=sha(regions[k]),crc16=B.crc16_ccitt_false(regions[k]))
    m['elf'].update(file='lisp65-c2-substitution-linked.prg.elf',sha256=sha((WORLD/'lisp65-c2-substitution-linked.prg.elf').read_bytes()))
    write(WORLD/f'runtime-overlays-{family}-final.json',m)
    return m,proof


def main():
    inventory=json.loads((P.HERE/'inventory-r4/inventory.json').read_text())
    assert inventory['status']=='PASS' and inventory['unclassified_bytes']==0
    assert json.loads((P.HERE/'inventory-r4/serialization-proof.json').read_text())['status']=='PASS'
    P.require_auth()
    assert not OUT.exists(),'No implicit materialization retry'
    OUT.mkdir();WORLD.mkdir();(OUT/'tmp').mkdir()
    frozen=[bind(SEED/('resident-island-seed.prg'+suffix)) for suffix in ('','.elf','.lto.o','.map')]
    assert frozen[1]['sha256']=='7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
    write(OUT/'frozen.json',frozen)
    target=WORLD/'lisp65-c2-substitution-linked.prg'
    for suffix in ('','.elf','.lto.o','.map'):shutil.copyfile(SEED/('resident-island-seed.prg'+suffix),Path(str(target)+suffix))
    for name in ('resolved-profile.txt','c2-kernal-window.generated.h'):
        source=SEED/name if (SEED/name).exists() else P.BASE/'wplto'/name
        shutil.copyfile(source,WORLD/name)
    elf=Path(str(target)+'.elf')
    before=ElfTruth.read(P.FINAL,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    after=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    boot,bootproof=refresh_family('boot',before,after)
    session,sessionproof=refresh_family('session',before,after)
    write(OUT/'family-extraction.json',dict(boot=bootproof,session=sessionproof))
    import c2_product_substitution_link as LINK
    P.configure(LINK)
    def forbidden(*a,**kw):raise RuntimeError('Runtime compile/link forbidden; reuse immutable Seed')
    LINK.compile_link=forbidden
    import c2_v160_refill_boundary_witness_media_repair as FACADE
    facade=FACADE.materialize_facade(target,elf,WORLD/'facade-materialization.json')
    window=LINK.publish_kernal_window_binding(WORLD,target)
    address=after.section('.lisp65_runtime_overlay_verifier_bindings').address
    overlay=LINK.patch_verifier_binding_table(WORLD,target,WORLD/'runtime-overlays-boot-final.json',WORLD/'runtime-overlays-session-final.json',expected_base=address)
    publication=LINK.total_publish_last_gate(WORLD,target,window,overlay,expected_verifier_base=address)
    import boot_only_carrier_prg as CARRIER
    extended=CARRIER.from_elf(elf,target.read_bytes(),publication_dir=WORLD)
    (OUT/'extended-resident.prg').write_bytes(extended)
    import c2_lite_canonical_product as CAN
    CAN.ARTIFACTS=OUT/'bootstage';CAN.ARTIFACTS.mkdir()
    stage,geometry=CAN.build_boot_stage(elf,WORLD/'resolved-profile.txt')
    import d81_persistence_fault as D81
    import c2_lite_media_product as DISK
    files=D81.visible_files((BASE/'packed/hardware-sp-seed.d81').read_bytes())
    # Verify the inherited disk is bound to the selected predecessor world.
    for name,path in [('BOOT.BIN',boot['storage']['file']),('SESSION.BIN',session['storage']['file']),('REGION1.BIN',session['overflow_storage']['file'])]:
        assert files[name.encode()]==(BASE/'materialized'/path).read_bytes()
    # All mapped Bank-2 native owners and the private record are unchanged.
    bank2=[]
    for sec in after.sections:
        if sec.name.startswith('.lisp65_c2_mapped_') or sec.name=='.lisp65_rt_card2b_disk':
            if sec.section_type=='SHT_NOBITS':continue
            assert before.section_bytes(sec.name)==after.section_bytes(sec.name),sec.name
            bank2.append(sec.name)
    files.update({b'LISP65.PRG':extended,b'BOOTSTAGE.BIN':stage.read_bytes(),
        b'WINDOW.BIN':(WORLD/'c2-product-kernal-window.bin').read_bytes(),
        b'BOOT.BIN':(WORLD/boot['storage']['file']).read_bytes(),
        b'SESSION.BIN':(WORLD/session['storage']['file']).read_bytes(),
        b'REGION1.BIN':(WORLD/session['overflow_storage']['file']).read_bytes()})
    # Every changed allocated section has a delivery owner; none can silently
    # retain a predecessor payload outside the channels refreshed above.
    covered={x['section'] for x in bootproof+sessionproof}|{'.text','.rodata','.lisp65_c2_host_facade','.lisp65_boot_bank3_stage','.lisp65_workbench_overlay','.lisp65_boot_carrier','.lisp65_rt_card_l_stage'}
    changed=[]
    for sec in after.sections:
        if 'SHF_ALLOC' not in sec.flags or sec.section_type=='SHT_NOBITS':continue
        if sec.name in before.sections_by_name and before.section_bytes(sec.name)==after.section_bytes(sec.name):continue
        assert sec.name in covered or sec.name.startswith('.lisp65_c2_kernal_window.'),sec.name
        changed.append(sec.name)
    base=OUT/'base';base.mkdir();entries=[]
    for name,raw in files.items():
        path=base/name.decode().lower();path.write_bytes(raw);entries.append((path,name.decode().lower()))
    medium=base/'base.d81';DISK.build_d81(medium,'L65SYS,65',entries);DISK.D81.stamp_product_boot_marker(medium)
    assert D81.visible_files(medium.read_bytes())==files
    population=OUT/'population';population.mkdir()
    for name in ('delivery-population.json','delivery-stager-main.c','delivery-roles.h','autoboot-chain.o','autoboot-rom-write-enable.o'):
        shutil.copyfile(BASE/'packed'/name,population/name)
    write(OUT/'materialization.json',dict(status='PASS: EXISTING SEED ARTIFACTS ONLY',frozen=frozen,facade=facade,
        window=window,publication=publication,changed_sections_delivered=changed,bank2_unchanged_sections=bank2,
        bank2_sha256=sha(files[b'CODE.BIN']),bootstage=geometry,product_compiles=0,product_links=0))
    MEDIA.OUT=OUT
    MEDIA.run(WORLD,medium,population/'delivery-population.json',False)
    assert frozen==[bind(SEED/('resident-island-seed.prg'+suffix)) for suffix in ('','.elf','.lto.o','.map')]
    write(OUT/'completion.json',dict(status='PASS',seed_unchanged=True,product_compiles=0,product_links=0))
    print('PASS: Card L positive and three negative-control media built; no runtime link')


if __name__=='__main__':
    import traceback
    try:main()
    except Exception as e:
        if OUT.exists():write(OUT/'failure.json',dict(error=str(e),traceback=traceback.format_exc()))
        raise
