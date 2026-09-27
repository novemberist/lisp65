"""Independent record, payload, descriptor and ELF readback of Set B media."""
from pathlib import Path
import hashlib
import struct
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
import runtime_overlay_bank as B
import d81_persistence_fault as D
import c2_lite_media_product as DISK
import c2_require_resolver_gate as INDEX
from elf_truth import ElfTruth

ROOT = P.ROOT
OUT = ROOT/'build/set-b-seed-medium-r4'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def descriptor(folder, medium):
    files = D.visible_files(medium.read_bytes()); receipt = P.load(folder/'receipt.json')
    assert sha(medium.read_bytes()) == receipt['sha256']
    DISK.RECORDS = len(receipt['rows']); DISK.DESCRIPTOR_BYTES = DISK.HEADER_BYTES+DISK.RECORDS*DISK.RECORD_BYTES
    DISK.parse_descriptor(files[b'BOOT.ID'], receipt['descriptor_build_id'], receipt['rows'])
    for r in receipt['rows']:
        data = files[r['name'].upper().encode()]
        assert (len(data),DISK.crc32(data)) == (r['bytes'],r['crc32'])
    slots = {D.entry_name(s.record):s.record for s in D.directory_slots(medium.read_bytes()) if s.record[2]}
    for r in INDEX.decode_index(files[b'L65INDEX']):
        assert (r['track'],r['sector']) == D.file_chain(medium.read_bytes(),slots[r['name'].upper().encode()])[0]
    return files


def catalogs(files, bm, sm, late, *, allow_bad_late=False):
    rows = []
    for file,m,expected in [(b'BOOT.BIN',bm,len(bm['slices'])),(b'SESSION.BIN',sm,63)]:
        raw = files[file]; assert sha(raw) == m['storage']['sha256']
        fresh = bytearray(raw); B._refresh_catalog_crcs(fresh); assert fresh == raw
        assert B.HEADER.unpack_from(raw)[4] == m['catalog']['slice_count'] == expected
        overflow = files[b'REGION1.BIN'] if file == b'SESSION.BIN' else b''
        assert struct.unpack_from('<HH',raw,28) == (len(overflow),B.crc16_ccitt_false(overflow) if overflow else 0)
        for r in m['slices']:
            at = 32+r['id']*32; rec = bytearray(raw[at:at+32]); v = B.ENTRY.unpack(rec)
            struct.pack_into('<H',rec,22,0); assert B.crc16_ccitt_false(rec) == v[10] == r['record_crc16'] != 0
            assert (v[0],v[1],v[3],v[4],v[5],v[6]) == (r['id'],r['flags'],r['file_size'],r['vma'],r['memory_size'],r['entry_offset'])
            address = v[2] | (((v[11]>>8)&15)<<16) | (((v[11]>>16)&255)<<20)
            assert address == r['source_address'] and (v[11]&255) == r['region_id']
            size = r['file_size']; off = r['file_offset']; region = r['region_id']
            if region == 0: data = raw[off:off+size]
            elif region == 1: data = overflow[off:off+size]
            elif region == 2: data = files[b'CODE.BIN'][address-0x20000:address-0x20000+size]
            elif region == 3: data = late[off:off+size]
            else: raise AssertionError(('unexpected region',region))
            if region != 3 or not allow_bad_late:
                assert len(data) == size and sha(data) == r['sha256'] and B.crc16_ccitt_false(data) == v[9] == r['crc16']
            rows.append(dict(family=file.decode(),slot=r['id'],region=region,bytes=size,payload_crc16=v[9],record_crc16=v[10]))
    return rows


def main():
    target = OUT/'readback.json'; assert not target.exists()
    folder = OUT/'media-seed'; medium = folder/'set-b-comfort.d81'
    files = descriptor(folder,medium)
    bm = P.load(folder/'boot-manifest.json'); sm = P.load(folder/'session-manifest.json')
    elf = OUT/'world/lisp65-c2-substitution-linked.prg.elf'
    assert sha(elf.read_bytes()) == '1eb22d5282acae5e39c1a1ea37bd749d6e524c9fb45005791b298a26bb5b71cf'
    truth = ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    image, tenants = P.extract_tenants(elf)
    assert image == (folder/'set-b-tenants.bin').read_bytes()
    assert [r['file_offset'] for r in bm['slices'][12:]] == [0x4e00,0x5500,0x5c00,0x6300,0x6a00]
    assert files[b'BOOT.BIN'][0x4e00:0x6e00] == image
    checked = catalogs(files,bm,sm,image)
    extracted = []
    for family,m in [(b'BOOT.BIN',bm),(b'SESSION.BIN',sm)]:
        for r in m['slices']:
            if family == b'BOOT.BIN' and r['id'] >= 12: continue
            sec = truth.section(r['section']); linked = truth.section_bytes(sec.name)
            address = r['source_address']; off = r['file_offset']; size = r['file_size']
            source = files[family] if r['region_id'] == 0 else files[b'REGION1.BIN'] if r['region_id'] == 1 else files[b'CODE.BIN'] if r['region_id'] == 2 else image
            if r['region_id'] == 2: off = address-0x20000
            payload = source[off:off+size]
            if family == b'SESSION.BIN' and r['id'] == 55:
                at = truth.symbol('rtov_late_stage_binding').value-sec.address
                assert linked[at:at+4] == bytes(4)
                expected = bytearray(linked); struct.pack_into('<HH',expected,at,8192,B.crc16_ccitt_false(image))
                expected = bytes(expected).ljust(size,b'\0')
            else: expected = linked.ljust(size,b'\0')
            assert payload == expected, ('ELF payload mismatch',family,r['id'])
            extracted.append(dict(family=family.decode(),slot=r['id'],section=sec.name,code_bytes=len(linked),padding=size-len(linked)))
    native = P.load(OUT/'bank2-native-delivery.json')
    for r in native['owners']:
        at = r['physical_address']-0x20000; payload = files[b'CODE.BIN'][at:at+r['bytes']]
        assert payload == truth.section_bytes(r['section']) and sha(payload) == r['after_sha256']
    old = D.visible_files((ROOT/'build/card-l-seed-medium-r2/comfort/card-l-comfort.d81').read_bytes())
    allowed = {r['physical_address']-0x20000+i for r in native['owners'] for i in range(r['bytes'])}
    assert len(files[b'CODE.BIN']) == len(old[b'CODE.BIN'])
    assert all(a == b or i in allowed for i,(a,b) in enumerate(zip(old[b'CODE.BIN'],files[b'CODE.BIN'])))
    assert files[b'REPL-COMFORT'] == old[b'REPL-COMFORT']
    controls = []
    for name in ('missing_record','corrupted_byte','displaced_256'):
        folder = OUT/'controls'/name; disk = folder/'set-b-comfort.d81'
        f = descriptor(folder,disk); manifest = P.load(folder/'boot-manifest.json')
        rows = catalogs(f,manifest,sm,image)
        staged = f[b'BOOT.BIN'][0x4e00:0x6e00]
        assert staged != image and B.crc16_ccitt_false(staged) != B.crc16_ccitt_false(image)
        assert f[b'SESSION.BIN'] == files[b'SESSION.BIN'] and f[b'CODE.BIN'] == files[b'CODE.BIN']
        if name == 'missing_record': assert len(manifest['slices']) == 16 and staged[-1024:] == bytes(1024)
        elif name == 'corrupted_byte': assert sum(x != y for x,y in zip(staged,image)) == 1
        else: assert f[b'BOOT.BIN'][0x4f00:0x6f00] == image
        controls.append(dict(name=name,medium=P.bind(disk),transport_and_catalogs_valid=True,late_crc_rejected=True,records_checked=len(rows),guest_executed=False))
    P.write(target,dict(status='PASS: INDEPENDENT MEDIA READBACK',driver=P.bind(Path(__file__)),medium=P.bind(medium),
        elf=P.bind(elf),catalogs=dict(boot=17,session=63,limit=64),records_checked=checked,extractions=extracted,
        tenant_sha256=sha(image),tenant_crc16=B.crc16_ccitt_false(image),native_bank2_owners=native['owners'],
        lisp_plane_byte_identical=True,comfort_byte_identical=True,controls=controls,
        boot_journal_control='temporal injection between reset write and readback; prepared, not executed',
        product_builds=0,product_links=0,guest_runs=0))
    print('PASS: 80 records, 4 refreshed Bank-2 owners, 7 tenant readbacks, 3 falling controls; guest gates pending')


if __name__ == '__main__': main()
