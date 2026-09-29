#!/usr/bin/env python3
"""Public runtime-family packing for the third Chip-RAM owner (2.4.0 catalog).

The record codec and validation are the established Card-2b algorithm; the
55-record catalog with the disk record at slot 52 and the two pinned
boot-name-index records at 53/54 is the accepted 2.4.0 session shape.
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

# 2.4.0 session catalog: 55 dense records. The private f011-write-member
# record keeps slot 52; the two boot-name-index records are pinned at 53/54.
# The shape is the accepted nested-error recovery medium's, derived from the
# configured SESSION_SLICE_SPECS, never from a card receipt.
DISK_SLOT = 52
PIN_10A = 53
PIN_10B = 54
PIN_SECTIONS = ('.lisp65_rt_c2d_10a', '.lisp65_rt_c2d_10b')
SESSION_SLICES = 55


def _record(raw, slot):
    start = BANK.HEADER_SIZE + slot*BANK.ENTRY_SIZE
    return bytes(raw[start:start+BANK.ENTRY_SIZE])


def _reslot(record, slot):
    """Return the catalog record carrying `slot` as its id, CRC refreshed."""
    raw = bytearray(record)
    struct.pack_into('<H', raw, 0, slot)
    struct.pack_into('<H', raw, 22, 0)
    crc = BANK.crc16_ccitt_false(bytes(raw))
    assert crc
    struct.pack_into('<H', raw, 22, crc)
    return bytes(raw)


def _catalog_ids(raw, count):
    return [BANK.ENTRY.unpack_from(bytes(raw), BANK.HEADER_SIZE+index*BANK.ENTRY_SIZE)[0]
            for index in range(count)]


def _set_count(raw, count):
    header = list(BANK.HEADER.unpack(bytes(raw[:BANK.HEADER_SIZE])))
    header[4] = count
    raw[:BANK.HEADER_SIZE] = BANK.HEADER.pack(*header)
    BANK._refresh_catalog_crcs(raw)


def pack_family(out, target, contract, family, suffix):
    if family != 'session':
        return ORIGINAL_PACK(out, target, contract, family, suffix)
    specs = list(P.SESSION_SLICE_SPECS)
    assert len(specs) == SESSION_SLICES
    assert [int(spec.split(':')[0]) for spec in specs] == list(range(SESSION_SLICES))
    assert specs[DISK_SLOT].split(':')[2] == SECTION
    tail = specs[DISK_SLOT+1:]
    assert [spec.split(':')[2] for spec in tail] == list(PIN_SECTIONS)
    lowered = [f"{int(spec.split(':', 1)[0])-1}:{spec.split(':', 1)[1]}" for spec in tail]
    try:
        P.SESSION_SLICE_SPECS = specs[:DISK_SLOT] + lowered
        image, manifest = ORIGINAL_PACK(out, target, contract, family, suffix)
    finally:
        P.SESSION_SLICE_SPECS = specs
    value = json.loads(manifest.read_text())
    data, source, vma, entry, owner = payload(Path(str(target)+'.elf'))
    raw = bytearray(image.read_bytes())
    count = value['catalog']['slice_count']
    assert count == SESSION_SLICES-1
    assert [r['id'] for r in value['slices']] == list(range(count))
    assert [r['section'] for r in value['slices'][DISK_SLOT:]] == list(PIN_SECTIONS)
    assert _catalog_ids(raw, count) == list(range(count))
    start = BANK.HEADER_SIZE + DISK_SLOT*BANK.ENTRY_SIZE
    assert BANK.HEADER_SIZE + (count+1)*BANK.ENTRY_SIZE <= value['catalog']['payload_offset']
    assert not any(raw[start+2*BANK.ENTRY_SIZE:start+3*BANK.ENTRY_SIZE])
    record = make_record(data, source, vma, entry, DISK_SLOT, value['profile_build_id'])
    pinned = [_reslot(_record(raw, DISK_SLOT+index), PIN_10A+index) for index in (0, 1)]
    raw[start:start+3*BANK.ENTRY_SIZE] = record + pinned[0] + pinned[1]
    _set_count(raw, count+1)
    image.write_bytes(bytes(raw))
    blob = out/f'runtime-overlays-session-{suffix}-region2.bin'; blob.write_bytes(data)
    rows = value['slices'][DISK_SLOT:]
    for index, row in enumerate(rows):
        row['id'] = PIN_10A+index
        row['record_crc16'] = struct.unpack_from('<H', pinned[index], 22)[0]
    value['external_storage'] = dict(region_id=2, file=blob.name, source_address=source,
        bytes=len(data), sha256=bind(blob)['sha256'], crc16=BANK.crc16_ccitt_false(data), owner=owner)
    value['storage'].update(size=len(raw), crc16=BANK.crc16_ccitt_false(bytes(raw)),
                            sha256=bind(image)['sha256'])
    fields = BANK.HEADER.unpack(bytes(raw[:BANK.HEADER_SIZE]))
    value['catalog'].update(slice_count=count+1, directory_crc16=fields[12], header_crc16=fields[13])
    value['slices'] = value['slices'][:DISK_SLOT] + [dict(id=DISK_SLOT,
        name='f011-write-member', section=SECTION,
        start_symbol='__lisp65_rt_card2b_disk_start', end_symbol='__lisp65_rt_card2b_disk_end',
        entry_symbol='__lisp65_rt_card2b_disk_entry', flags=BANK.FLAG_RUNTIME|BANK.FLAG_REUSABLE,
        roles=BANK._roles(BANK.FLAG_RUNTIME|BANK.FLAG_REUSABLE), file_offset=0, file_size=len(data),
        memory_size=len(data), vma=vma, end=vma+len(data), entry=entry, entry_offset=entry-vma,
        abi_version=BANK.ENTRY_ABI, slice_build_id=value['profile_build_id'], capability_mask=0,
        crc16=BANK.crc16_ccitt_false(data), record_crc16=struct.unpack_from('<H', record, 22)[0],
        sha256=bind(blob)['sha256'], region_id=2, source_address=source)] + rows
    write(manifest, value)
    validate(image, value, 'public-session-pack')
    selftest(image, value)
    return image, manifest


def validate(image, value, label):
    if 'external_storage' not in value:
        return ORIGINAL_VALIDATE(image, value, label)
    ext = value['external_storage']; data = (image.parent/ext['file']).read_bytes()
    rows = value['slices']; r = rows[DISK_SLOT]; raw = image.read_bytes()
    elf = image.parent/value['elf']['file']
    assert bind(elf)['sha256'] == value['elf']['sha256']
    expected_data, expected_source, expected_vma, expected_entry, expected_owner = payload(elf)
    assert (data, r['source_address'], r['vma'], r['entry'], ext['owner']) == \
        (expected_data, expected_source, expected_vma, expected_entry, expected_owner)
    assert len(rows) == value['catalog']['slice_count'] == SESSION_SLICES
    assert [row['id'] for row in rows] == list(range(SESSION_SLICES))
    assert r['id'] == DISK_SLOT and r['section'] == SECTION
    assert [row['section'] for row in rows[PIN_10A:]] == list(PIN_SECTIONS)
    assert _catalog_ids(raw, SESSION_SLICES) == list(range(SESSION_SLICES))
    assert ext['region_id'] == r['region_id'] == 2
    assert ext['source_address'] == r['source_address'] == ext['owner']['payload']['start']
    assert ext['bytes'] == r['file_size'] == len(data) <= ext['owner']['payload']['capacity']
    assert hashlib.sha256(data).hexdigest() == ext['sha256'] == r['sha256']
    assert BANK.crc16_ccitt_false(data) == ext['crc16'] == r['crc16']
    expected = make_record(data, r['source_address'], r['vma'], r['entry'], r['id'],
                           value['profile_build_id'])
    start = BANK.HEADER_SIZE + r['id']*BANK.ENTRY_SIZE
    assert raw[start:start+BANK.ENTRY_SIZE] == expected
    assert BANK.HEADER.unpack(raw[:BANK.HEADER_SIZE])[4] == SESSION_SLICES
    projected = bytearray(raw)
    projected[start:start+2*BANK.ENTRY_SIZE] = b''.join(
        _reslot(_record(raw, PIN_10A+index), DISK_SLOT+index) for index in (0, 1))
    projected[start+2*BANK.ENTRY_SIZE:start+3*BANK.ENTRY_SIZE] = bytes(BANK.ENTRY_SIZE)
    _set_count(projected, SESSION_SLICES-1)
    overflow = (image.parent/value['overflow_storage']['file']).read_bytes()
    main_bases = {row['source_address']-row['file_offset'] for row in rows if row['region_id'] == 0}
    assert len(main_bases) == 1
    overflow_base = (value['overflow_storage']['bank'] << 16)+value['overflow_storage']['address']
    parsed = BANK.validate_region_images(bytes(projected), overflow,
        expected_build_id=value['profile_build_id'], expected_vma=value['policy']['common_vma'],
        max_slice_bytes=value['policy']['max_slice_bytes'], format_version=4,
        main_source_base=main_bases.pop(), overflow_source_base=overflow_base)
    assert len(parsed.slices) == SESSION_SLICES-1
    refreshed = bytearray(raw); BANK._refresh_catalog_crcs(refreshed); assert bytes(refreshed) == raw
    ordinary = copy.deepcopy(value)
    ordinary['slices'] = [dict(row, id=row['id']-(row['id'] > DISK_SLOT))
                          for row in ordinary['slices'] if row['id'] != DISK_SLOT]
    ORIGINAL_VALIDATE(image, ordinary, label)


def negative(image, manifest):
    value = json.loads(manifest.read_text())
    if 'external_storage' not in value:
        return ORIGINAL_NEGATIVE(image, manifest)
    source = image.parent/value['external_storage']['file']; p = source.with_suffix('.negative')
    raw = bytearray(source.read_bytes()); raw[len(raw)//2] ^= 1; p.write_bytes(bytes(raw))
    value['external_storage']['file'] = p.name
    try:
        validate(image, value, 'public-session-mutation')
    except (AssertionError, RuntimeError):
        return 'rejected'
    finally:
        p.unlink()
    raise AssertionError('corrupted third-owner payload survived')


def selftest(image, value):
    """Fail-closed control over the three pinned catalog slots."""
    results = {}
    raw = bytearray(image.read_bytes())
    start = BANK.HEADER_SIZE + PIN_10A*BANK.ENTRY_SIZE
    raw[start:start+2*BANK.ENTRY_SIZE] = (_reslot(_record(raw, PIN_10B), PIN_10A)
                                         + _reslot(_record(raw, PIN_10A), PIN_10B))
    _set_count(raw, SESSION_SLICES)
    mutated = image.with_suffix('.pin-mutation')
    mutated.write_bytes(bytes(raw))
    swapped = copy.deepcopy(value)
    rows = swapped['slices']
    rows[PIN_10A], rows[PIN_10B] = (dict(rows[PIN_10B], id=PIN_10A),
                                    dict(rows[PIN_10A], id=PIN_10B))
    swapped['storage'].update(size=len(raw), crc16=BANK.crc16_ccitt_false(bytes(raw)),
                              sha256=hashlib.sha256(bytes(raw)).hexdigest())
    fields = BANK.HEADER.unpack(bytes(raw[:BANK.HEADER_SIZE]))
    swapped['catalog'].update(directory_crc16=fields[12], header_crc16=fields[13])
    relabelled = copy.deepcopy(value)
    relabelled['slices'][DISK_SLOT]['id'] = PIN_10B
    try:
        for name, candidate, target in (('10a/10b-ids-swapped', swapped, mutated),
                                        ('disk-record-relabelled-54', relabelled, image)):
            try:
                validate(target, candidate, 'public-session-pin-mutation')
            except (AssertionError, RuntimeError):
                results[name] = 'rejected'
            else:
                raise AssertionError('public session pin mutation survived: '+name)
    finally:
        mutated.unlink()
    return results


def check():
    """Bind the inherited catalog geometry to the selected Comfort Final ELF."""
    import c2_v251_public_native as N
    import d81_persistence_fault as D81
    authority=json.loads(N.AUTHORITY.read_text())
    elf=N.local(authority['raw_pair']['ELF']['path']);N.bound(authority['raw_pair']['ELF'])
    data,source,vma,entry,owner=payload(elf)
    media=json.loads((N.ROOT/'config/c2-v251-public-media.json').read_text())
    files=D81.visible_files(N.bound(media['medium']))
    assert files[b'CODE.BIN'][source-0x20000:source-0x20000+len(data)]==data
    assert files[b'SESSION.BIN'][7]==SESSION_SLICES
    return dict(status='PASS: COMFORT FINAL OVERLAY PAYLOAD',bytes=len(data),source=source,owner=owner)

if __name__=='__main__':
    print(json.dumps(check(),indent=2))
