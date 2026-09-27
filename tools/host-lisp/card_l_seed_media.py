#!/usr/bin/env python3
"""Card L artifact-only media packing; dry-run uses the 2.4.0 world.

A Seed input is an already materialized world (no product compiler is called).
Controls authenticate delivery of intentionally bad marker content; guest
failure/ownership and timing remain reviewer gates.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import runtime_overlay_bank as B

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/card-l-r1'
BASE = ROOT / 'build/nested-error-recovery-seed-medium-r1'
SIZES = (1792, 1792, 1792, 1792, 1024)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def marker():
    raw = b''.join(hashlib.sha256(
        b'lisp65 card L late region marker 2026-09-25' + n.to_bytes(4, 'big')
    ).digest() for n in range(256))
    if len(raw) != 8192 or B.crc16_ccitt_false(raw) != 0x7B72:
        raise ValueError('marker seal drift')
    path = OUT / 'card-l-marker.bin'
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('existing marker differs from sealed expansion')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def boot_pack(world, out):
    m = json.loads((world / 'runtime-overlays-boot-final.json').read_text())
    raw = (world / m['storage']['file']).read_bytes()
    if digest(raw) != m['storage']['sha256'] or len(m['slices']) != 12:
        raise ValueError('Boot predecessor identity/population drift')
    items = []
    for r in m['slices']:
        spec = B.SliceSpec(r['id'], r['name'], r['section'], r['start_symbol'],
            r['end_symbol'], r['entry_symbol'] or '', r['flags'], r['abi_version'],
            r['capability_mask'], data_only=bool(r['flags'] & B.FLAG_DATA_ONLY), destination=r['vma'])
        items.append(B.ExtractedSlice(spec, r['vma'], r['end'],
            B.DATA_ENTRY_SENTINEL if spec.data_only else r['entry'],
            raw[r['file_offset']:r['file_offset'] + r['file_size']]))
    kw = dict(profile_build_id=m['profile_build_id'], expected_vma=m['policy']['common_vma'],
        max_slice_bytes=B.MAX_SLICE_BYTES, format_version=4,
        main_source_base=B.BOOT_FAMILY_SOURCE_BASE, payload_alignment=B.BOOT_FAMILY_PAYLOAD_ALIGNMENT)
    if B.build_region_images(items, **kw)[0] != raw:
        raise ValueError('predecessor does not repack byte-identically')
    data = marker()
    cursor = 0
    for i, size in enumerate(SIZES):
        spec = B.SliceSpec(12+i, f'card-l-marker-{i}', f'.lisp65_card_l_marker_{i}',
            f'card_l_marker_{i}_start', f'card_l_marker_{i}_end', '', B.FLAG_BOOT | B.FLAG_DATA_ONLY, 0, 0, data_only=True, destination=0x1800)
        items.append(B.ExtractedSlice(spec, 0x1800, 0x1800+size,
            B.DATA_ENTRY_SENTINEL, data[cursor:cursor+size]))
        cursor += size
    image, overflow, parsed = B.build_region_images(items, **kw)
    assert not overflow
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'boot.bin'
    path.write_bytes(image)
    header = B.render_header(profile_build_id=m['profile_build_id'], format_version=4)
    value = B._manifest(profile=m['profile'], abi_contract=Path(m['abi']['contract']),
        abi_sha256=m['abi']['sha256'], elf=world/m['elf']['file'], image_path=path,
        overflow_image_path=out/'boot-region1.bin', header_path=out/'boot.h', image=image,
        overflow_image=overflow, header=header, parsed=parsed, slices=items,
        expected_vma=kw['expected_vma'], max_slice_bytes=B.MAX_SLICE_BYTES,
        format_version=4, payload_alignment=256)
    B.validate_manifest(value, payload_alignment=256)
    (out/'boot.h').write_bytes(header)
    (out/'boot-region1.bin').write_bytes(overflow)
    write(out/'boot-manifest.json', value)
    placed = json.loads((out/'boot-manifest.json').read_text())['slices'][12:]
    sealed = json.loads((ROOT/'config/card-l-native/card-l-inputs.json').read_text())
    if placed[0]['source_address'] != sealed['attic']['address']:
        raise ValueError('Seed Boot placement differs from the compiled marker constant')
    start = placed[0]['file_offset']
    assert image[start:start+8192] == data
    assert all(b['file_offset'] == a['file_offset']+a['file_size'] for a,b in zip(placed, placed[1:]))
    write(out/'placement-proof.json', dict(predecessor_repacked_identically=True,
        old_directory=m['catalog']['payload_offset'], directory=parsed.payload_offset,
        contiguous=True, slices=placed, boot_count=17, image_sha256=digest(image)))
    return image, value


def controls(image, manifest):
    """All variants overwrite the full expected span, including absent bytes."""
    first = manifest['slices'][12]['file_offset']
    # Missing tail record: catalog count 16 still has a 768-byte directory.
    missing = bytearray(image)
    h = list(B.HEADER.unpack_from(missing)); h[4] = 16
    missing[:B.HEADER_SIZE] = B.HEADER.pack(*h)
    last = manifest['slices'][16]
    missing[B.HEADER_SIZE+16*B.ENTRY_SIZE:B.HEADER_SIZE+17*B.ENTRY_SIZE] = bytes(B.ENTRY_SIZE)
    missing[last['file_offset']:last['file_offset']+last['file_size']] = bytes(last['file_size'])
    B._refresh_catalog_crcs(missing)
    corrupt = bytearray(image); corrupt[first+100] ^= 1
    # Preserve the complete marker, moved one alignment step, and clear its old start.
    displaced = bytearray(image[:first] + bytes(256) + image[first:])
    for slot in range(12, 17):
        offset = B.HEADER_SIZE + slot*B.ENTRY_SIZE
        rec = bytearray(displaced[offset:offset+B.ENTRY_SIZE])
        address = manifest['slices'][slot]['source_address']+256
        struct.pack_into('<H', rec, 4, address & 0xffff)
        rec[25] = (address >> 16) & 15; rec[26] = (address >> 20) & 255
        struct.pack_into('<H', rec, 22, 0)
        struct.pack_into('<H', rec, 22, B.crc16_ccitt_false(rec))
        displaced[offset:offset+B.ENTRY_SIZE] = rec
    h = list(B.HEADER.unpack_from(displaced)); h[11] = len(displaced)
    displaced[:B.HEADER_SIZE] = B.HEADER.pack(*h)
    B._refresh_catalog_crcs(displaced)
    result = dict(missing_record=bytes(missing), corrupted_byte=bytes(corrupt), displaced_256=bytes(displaced))
    for raw in result.values():
        assert B.crc16_ccitt_false(raw[first:first+8192]) != 0x7B72
    return result


def pack_disk(base_medium, population, boot, out, world, boot_manifest, session=None, session_manifest=None):
    """Reuse the world's exact roles; rebuild only the cold delivery stager."""
    import d81_persistence_fault as D81
    import c2_lite_media_product as M
    files = D81.visible_files(base_medium.read_bytes())
    files[b'BOOT.BIN'] = boot
    if session is not None:
        files[b'SESSION.BIN'] = session
    from elf_truth import ElfTruth
    # Both family images and the verifier offsets are authenticated in the PRG.
    # Rebind each control to its actual family bytes so failure reaches Card L.
    original_boot = json.loads((world/'runtime-overlays-boot-final.json').read_text())
    original_session = json.loads((world/'runtime-overlays-session-final.json').read_text())
    def table(bm, sm, boot_bytes, session_bytes):
        words=[]
        for manifest in (bm,sm):
            for row in manifest['slices'][:2]:
                words.extend(row[k] for k in ('file_offset','file_size','entry_offset','crc16'))
        words.extend((len(boot_bytes),B.crc16_ccitt_false(boot_bytes),
                      len(session_bytes),B.crc16_ccitt_false(session_bytes)))
        return struct.pack('<20H',*words)
    truth=ElfTruth.read(world/original_boot['elf']['file'],
        llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    section=truth.section('.lisp65_runtime_overlay_verifier_bindings')
    assert section.bytes == 40
    prg=bytearray(files[b'LISP65.PRG'])
    pos=section.address-struct.unpack_from('<H',prg)[0]+2
    old=table(original_boot,original_session,
        (world/original_boot['storage']['file']).read_bytes(),
        (world/original_session['storage']['file']).read_bytes())
    if prg[pos:pos+40] != old:
        raise ValueError('base medium does not carry the selected materialized world bindings')
    prg[pos:pos+40]=table(boot_manifest,session_manifest or original_session,boot,files[b'SESSION.BIN'])
    files[b'LISP65.PRG']=bytes(prg)
    out.mkdir(parents=True, exist_ok=True)
    rows = copy.deepcopy(json.loads(population.read_text())['rows'])
    for row in rows:
        data = files[row['name'].upper().encode()]
        row.update(bytes=len(data), crc32=M.crc32(data))
    # Descriptor cardinality belongs to the selected world's delivery population.
    M.RECORDS = len(rows); M.DESCRIPTOR_BYTES = M.HEADER_BYTES + len(rows)*M.RECORD_BYTES
    profile = struct.unpack_from('<I', files[b'BOOT.ID'], 12)[0]
    descriptor, build_id = M.make_descriptor(rows, profile)
    M.parse_descriptor(descriptor, build_id, rows)
    files[b'BOOT.ID'] = descriptor
    compiler = ROOT/'tools/llvm-mos/bin/mos-mega65-clang'
    packed = population.parent
    source = packed/'delivery-stager-main.c'
    # Include the exact previously accepted delivery source and population header.
    command = [str(compiler), '-std=c99', '-Oz', '-Wall', '-Wextra', '-Werror',
        '-DLISP65_C2_LITE_MEDIA_STAGER', '-DLISP65_STARTUP_REQUIRE_EXPERIENCE', f'-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id:08x}UL',
        '-I', str(ROOT/'scripts'), '-include', str(packed/'delivery-roles.h'),
        '-c', str(source), '-o', str(out/'autoboot-main.o')]
    link = [str(compiler), '-Oz', str(out/'autoboot-main.o'), str(packed/'autoboot-chain.o'),
        str(packed/'autoboot-rom-write-enable.o'), '-o', str(out/'autoboot.c65')]
    for i, cmd in enumerate((command, link)):
        p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, 'TMPDIR':str(OUT/'tmp')})
        (out/f'stager-{i}.log').write_text(p.stdout)
        if p.returncode:
            raise RuntimeError(p.stdout)
    files[b'AUTOBOOT.C65'] = (out/'autoboot.c65').read_bytes()
    entries=[]
    for name, raw in files.items():
        path=out/name.decode().lower(); path.write_bytes(raw)
        entries.append((path, name.decode().lower()))
    medium=out/'card-l.d81'
    M.build_d81(medium, 'L65SYS,65', entries)
    M.D81.stamp_product_boot_marker(medium)
    import c2_require_resolver_gate as L
    disk = bytearray(medium.read_bytes())
    slots = {D81.entry_name(s.record): s.record for s in D81.directory_slots(disk) if s.record[2]}
    index = L.decode_index(files[b'L65INDEX'])
    for row in index:
        row['track'], row['sector'] = D81.file_chain(disk, slots[row['name'].upper().encode()])[0]
    located = L.encode_index(index)
    assert len(located) == len(files[b'L65INDEX'])
    chain = D81.file_chain(disk, slots[b'L65INDEX'])
    for i, (track, sector) in enumerate(chain):
        offset = D81.sector_offset(track, sector)
        disk[offset:offset+256] = D81.chain_sector(located, chain, i)
    medium.write_bytes(disk)
    files[b'L65INDEX'] = located
    (out/'l65index').write_bytes(located)
    assert D81.visible_files(medium.read_bytes()) == files
    write(out/'receipt.json', dict(medium=str(medium.relative_to(ROOT)), sha256=digest(medium.read_bytes()),
        descriptor_build_id=build_id, boot_sha256=digest(boot), product_links=0,
        cold_stager_links=1, rows=rows, guest_execution=False))
    return medium


def run(world, base_medium, population, dry_run):
    if not dry_run:
        import card_l_producer as P
        P.require_auth()
    out = OUT/('media-dryrun' if dry_run else 'media-seed')
    image, manifest = boot_pack(world, out)
    session = None
    if not dry_run:
        session = P.bind_session(world, out)
    sm = json.loads((out/'session-manifest.json').read_text()) if session is not None else None
    medium = pack_disk(base_medium, population, image, out, world, manifest, session, sm)
    for name, raw in controls(image, manifest).items():
        target = OUT/'media-controls'/('dryrun-'+name if dry_run else name)
        pack_disk(base_medium, population, raw, target, world, manifest, session, sm)
    write(out/'status.json', dict(dry_run=dry_run, boot_count=17, session_count=55 if dry_run else 56,
        medium=str(medium.relative_to(ROOT)), stage_executable=not dry_run,
        qualification='HOST PACK/READBACK ONLY; guest gates pending'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['dry-run','seed'])
    p.add_argument('--world', type=Path)
    p.add_argument('--base-medium', type=Path)
    p.add_argument('--population', type=Path)
    a=p.parse_args()
    if a.mode == 'seed' and not all((a.world,a.base_medium,a.population)):
        p.error('Seed requires --world (materialized), --base-medium and --population from that Seed')
    run(a.world or BASE/'materialized', a.base_medium or BASE/'packed/hardware-sp-seed.d81',
        a.population or BASE/'packed/delivery-population.json', a.mode=='dry-run')

if __name__ == '__main__':
    main()
