"""Independent ELF/medium readback verification for the existing Card L Seed."""
import hashlib,json,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
import card_l_producer as P
import runtime_overlay_bank as B
import d81_persistence_fault as D81
import c2_lite_media_product as DISK
import c2_require_resolver_gate as INDEX
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/card-l-seed-medium-r2'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
    elf=ROOT/'build/card-l-product-r1/wplto/resident-island-seed.prg.elf'
    assert digest(elf.read_bytes())=='7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    positive=OUT/'media-seed'; medium=positive/'card-l.d81'
    files=D81.visible_files(medium.read_bytes())
    bm=json.loads((positive/'boot-manifest.json').read_text());sm=json.loads((positive/'session-manifest.json').read_text())
    checked=[]
    for name,m,count in [('BOOT.BIN',bm,17),('SESSION.BIN',sm,56)]:
        raw=files[name.encode()];assert digest(raw)==m['storage']['sha256']
        assert B.HEADER.unpack_from(raw)[4]==m['catalog']['slice_count']==len(m['slices'])==count
        fresh=bytearray(raw);B._refresh_catalog_crcs(fresh);assert fresh==raw
        overflow=files[b'REGION1.BIN'] if name=='SESSION.BIN' else b''
        assert struct.unpack_from('<HH',raw,28)==(len(overflow),B.crc16_ccitt_false(overflow) if overflow else 0), 'stale overflow tenant binding'
        for row in m['slices']:
            at=B.HEADER_SIZE+row['id']*B.ENTRY_SIZE
            record=bytearray(raw[at:at+B.ENTRY_SIZE]);v=B.ENTRY.unpack(record)
            expected=v[10];struct.pack_into('<H',record,22,0)
            assert expected==B.crc16_ccitt_false(record)==row['record_crc16']
            assert (v[0],v[1],v[3],v[4],v[5],v[6])==(row['id'],row['flags'],row['file_size'],row['vma'],row['memory_size'],row['entry_offset'])
            address=v[2] | (((v[11]>>8)&15)<<16) | (((v[11]>>16)&255)<<20)
            assert address==row['source_address'] and (v[11]&255)==row['region_id']
            region=row['region_id'];start=row['file_offset'];n=row['file_size']
            if region==0:payload=raw[start:start+n]
            elif region==1:payload=files[b'REGION1.BIN'][start:start+n]
            else:payload=files[b'CODE.BIN'][address-0x20000:address-0x20000+n]
            assert len(payload)==n and digest(payload)==row['sha256'] and B.crc16_ccitt_false(payload)==v[9]==row['crc16']
            checked.append(dict(family=name,slot=row['id'],record_crc16=expected,payload_crc16=v[9],bytes=n))
    marker=(P.HERE/'card-l-marker.bin').read_bytes();assert len(marker)==8192 and B.crc16_ccitt_false(marker)==0x7b72
    placements=bm['slices'][12:];expected=[0x4e00,0x5500,0x5c00,0x6300,0x6a00]
    dry=json.loads((P.HERE/'media-dryrun/boot-manifest.json').read_text())['slices'][12:]
    assert [x['file_offset'] for x in placements]==expected==[x['file_offset'] for x in dry]
    assert [x['file_size'] for x in placements]==[1792]*4+[1024]
    assert files[b'BOOT.BIN'][expected[0]:expected[0]+8192]==marker
    assert b''.join(files[b'BOOT.BIN'][x['file_offset']:x['file_offset']+x['file_size']] for x in placements)==marker
    section=truth.section('.lisp65_rt_card_l_stage');symbol=truth.symbol('rtov_late_stage_binding')
    offset=symbol.value-section.address;assert symbol.section==section.name and symbol.bytes==4 and offset==593
    linked=truth.section_bytes(section.name);assert linked[offset:offset+4]==bytes(4)
    slot=sm['slices'][55];payload=files[b'SESSION.BIN'][slot['file_offset']:slot['file_offset']+slot['file_size']]
    assert payload[:offset]==linked[:offset] and payload[offset+4:]==linked[offset+4:]
    assert struct.unpack_from('<HH',payload,offset)==(8192,0x7b72)
    assert payload==(ROOT/'build/card-l-product-r1/slot55-bound-payload.bin').read_bytes()
    # Straight-line linked instruction witness for the four source argument
    # bytes (A, X, __rc2, __rc3), immediately before physical-copy JSR.
    start=0xc3f1;end=0xc418;witness=linked[start-section.address:end-section.address]
    expected_witness=bytes.fromhex('a920a080a2de8504a908850584068607a20586086409a00bb102850aa61e860ba24ea90020')+truth.symbol('c2_product_physical_copy').value.to_bytes(2,'little')
    assert witness==expected_witness
    source=0x00|(0x4e<<8)|(0x20<<16)|(0x08<<24)
    assert source==placements[0]['source_address']==0x08204e00
    controls=[]
    for name in ('missing_record','corrupted_byte','displaced_256'):
        folder=OUT/'media-controls'/name;p=folder/'card-l.d81';data=p.read_bytes();f=D81.visible_files(data)
        receipt=json.loads((folder/'receipt.json').read_text());assert digest(data)==receipt['sha256']
        DISK.RECORDS=len(receipt['rows']);DISK.DESCRIPTOR_BYTES=DISK.HEADER_BYTES+len(receipt['rows'])*DISK.RECORD_BYTES
        DISK.parse_descriptor(f[b'BOOT.ID'],receipt['descriptor_build_id'],receipt['rows'])
        for row in receipt['rows']:
            content=f[row['name'].upper().encode()];assert row['bytes']==len(content) and DISK.crc32(content)==row['crc32']
        span=f[b'BOOT.BIN'][expected[0]:expected[0]+8192];assert span!=marker and B.crc16_ccitt_false(span)!=0x7b72
        if name=='missing_record':assert B.HEADER.unpack_from(f[b'BOOT.BIN'])[4]==16 and span[-1024:]==bytes(1024)
        elif name=='corrupted_byte':assert sum(x!=y for x,y in zip(span,marker))==1
        else:assert f[b'BOOT.BIN'][expected[0]+256:expected[0]+256+8192]==marker
        controls.append(dict(name=name,medium=str(p.relative_to(ROOT)),sha256=digest(data),expected_span_crc16=B.crc16_ccitt_false(span),transport_descriptor_valid=True,guest_boot_not_run=True))
    slots={D81.entry_name(s.record):s.record for s in D81.directory_slots(medium.read_bytes()) if s.record[2]}
    locators=INDEX.decode_index(files[b'L65INDEX'])
    for row in locators:assert (row['track'],row['sector'])==D81.file_chain(medium.read_bytes(),slots[row['name'].upper().encode()])[0]
    old=D81.visible_files((P.ROOT/'build/nested-error-recovery-seed-medium-r1/packed/hardware-sp-seed.d81').read_bytes())
    assert files[b'CODE.BIN']==old[b'CODE.BIN']
    region0=max(x['source_address']%65536+x['file_size'] for x in sm['slices'] if x['region_id']==0)
    regions=dict(region0_used=region0,region0_free=65536-region0,region1_used=sm['overflow_storage']['used'],region1_free=sm['overflow_storage']['capacity']-sm['overflow_storage']['used'],region2_used=sm['external_storage']['bytes'],region2_free=sm['external_storage']['owner']['payload']['capacity']-sm['external_storage']['bytes'])
    assert regions==dict(region0_used=65045,region0_free=491,region1_used=1892,region1_free=140,region2_used=750,region2_free=872)
    # Header remains the live Bank-5 endpoint: all old Bank-5 NOBITS owners
    # are unchanged in the content/geometry inventory; new late payload ends
    # at the header start and cannot reduce the 374-byte tail.
    assert truth.section('.noinit.card_l_late').address+truth.section('.noinit.card_l_late').bytes==0x5fe80
    tail=0x60000-(0x5fe80+10);assert tail==374
    result=dict(status='PASS',elf_sha256=digest(elf.read_bytes()),medium=dict(path=str(medium.relative_to(ROOT)),sha256=digest(medium.read_bytes())),
        catalogs=dict(session=56,boot=17,capacity_each=64),records_checked=checked,placements=placements,marker_sha256=digest(marker),
        marker_readback_equal=True,tuple=dict(symbol_address=symbol.value,section_address=section.address,payload_offset=offset,size=8192,crc16=0x7b72,slot55_payload_crc16=slot['crc16'],slot55_record_crc16=slot['record_crc16'],record_crc_valid=True),
        compiled_source=dict(address=source,register_bytes=dict(A=0,X=0x4e,rc2=0x20,rc3=8),witness_start=start,witness_hex=witness.hex()),
        controls=controls,locator_count=len(locators),session_regions=regions,bank5_tail_floor=tail,bank2_plane_sha256=digest(files[b'CODE.BIN']),bank2_plane_unchanged=True)
    (OUT/'seed-media-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',medium=result['medium'],tuple=result['tuple'],regions=regions,controls=controls),indent=2))

if __name__=='__main__':main()
