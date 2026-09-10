#!/usr/bin/env python3
"""Public runtime-family packing for the third Chip-RAM owner.

The record codec and validation are the established Card-2b algorithm.
Placement is derived exclusively from the consumed ELF, not a card receipt.
No private card driver, compiler, or device connection is imported.
"""
from pathlib import Path
import copy
import hashlib
import json
import struct

import c2_product_substitution_link as P
import runtime_overlay_bank as BANK
from elf_truth import ElfTruth

SECTION = '.lisp65_rt_card2b_disk'
ORIGINAL_PACK = P.overlay_pack_family
ORIGINAL_VALIDATE = P._validate_family_artifact
ORIGINAL_NEGATIVE = P._family_identity_negative_selftest


def bind(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def payload(elf):
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN/'llvm-readobj',
                          include_section_data=True)
    section = truth.section(SECTION)
    start = truth.symbol('__card2b_carrier_start').value
    end = truth.symbol('__card2b_carrier_end').value
    source = truth.symbol('__card2b_payload_load_start').value
    loaded_end = truth.symbol('__card2b_payload_load_end').value
    entry = truth.symbol('card2b_disk_entry').value
    prefix = truth.section('.noinit.card2b_carrier_prefix')
    tail = truth.section('.noinit.card2b_carrier_tail')
    assert start == prefix.address and source == start + prefix.bytes
    assert source % 256 == 0 and start <= source < loaded_end <= end
    assert loaded_end == source + section.bytes == tail.address
    assert tail.address + tail.bytes == end
    assert start >> 16 == (end-1) >> 16 == 2
    assert section.address <= entry < section.address + section.bytes
    owner = dict(
        bank=start >> 16, bytes=end-start, start=start, end=end,
        owner='card2b-session-slice-store', window_vma=section.address,
        map_offset=start-section.address,
        edma_tuple=dict(source_high=source >> 16, source_low=source & 65535),
        prefix=dict(start=start, end=source, bytes=source-start,
                    role='reserved-alignment-prefix'),
        payload=dict(start=source, end=end, capacity=end-source,
                     loadaddr_binding='candidate payload subsection LOADADDR; not carrier base'))
    return truth.section_bytes(SECTION), source, section.address, entry, owner


def install():
    P.overlay_pack_family = pack_family
    P._validate_family_artifact = validate
    P._family_identity_negative_selftest = negative


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
    assert len(specs) == 53 and specs[-1].split(':')[2] == SECTION
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
    value['slices'].append(dict(id=count, name='f011-write-member', section=SECTION,
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


