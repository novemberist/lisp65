#!/usr/bin/env python3
"""Derive 2.5.4 Final runtime families, CODE.BIN and WINDOW.BIN from a fresh ELF.

The committed family templates hold only the catalog header and slice
records (all CRC fields zero). Every payload byte comes from the ELF being
qualified; CRCs and manifest digests are recomputed exactly as the Seed
rebind did, then the inherited family validator checks the result.
"""
import copy
import hashlib
import json
import struct
import c2_v254_r1_public_native as N

POLICY = N.ROOT / ('config/%s-media-reproduction.json' % N.PREFIX)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def policy():
    return N.load(POLICY)


def truth(elf):
    from elf_truth import ElfTruth
    return ElfTruth.read(elf, llvm_readobj=N.ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)


def template_is_geometry(fam, t):
    header = bytes.fromhex(t['header_records'])
    v = t['manifest']
    N.require(len(header) == 32 + 32 * v['catalog']['slice_count'] == 32 + 32 * len(v['slices']), 'template extent')
    N.require(header[24:32] == bytes(8), 'template catalog CRCs not cleared')
    for s in v['slices']:
        at = 32 + 32 * s['id']
        N.require(header[at + 20:at + 24] == bytes(4), 'template record CRC not cleared')
        N.require(s['region_id'] != 0 or s['file_offset'] >= len(header), 'slice overlaps template header')
        N.require(not {'sha256', 'crc16', 'record_crc16'} & set(s), 'template carries slice digests')
    N.require('elf' not in v, 'template binds an ELF')


def families(B, out, elf_row):
    """Return {fam: (manifest, regions)}; write family manifests into out."""
    import runtime_overlay_bank as BANK
    import comfort_default_media as C
    result, paths = {}, []
    for fam in ('boot', 'session'):
        t = policy()['families'][fam]
        template_is_geometry(fam, t)
        v = copy.deepcopy(t['manifest'])
        header = bytes.fromhex(t['header_records'])
        regions = {0: bytearray(header) + bytearray(t['region0_bytes'] - len(header)),
                   1: bytearray(t['region1_bytes'])}
        if fam == 'session':
            regions[2] = bytearray(B.section_bytes(policy()['code']['card2b_section']))
        for s in v['slices']:
            new = B.section_bytes(s['section'])
            at, rid = s['file_offset'], s['region_id']
            N.require(len(new) == s['file_size'] == s['memory_size'], 'slice size drift: ' + s['name'])
            N.require(at + len(new) <= len(regions[rid]), 'slice escapes region: ' + s['name'])
            regions[rid][at:at + len(new)] = new
            s['sha256'], s['crc16'] = sha(new), BANK.crc16_ccitt_false(new)
            r = 32 + 32 * s['id']
            struct.pack_into('<H', regions[0], r + 20, s['crc16'])
            regions[0][r + 22:r + 24] = bytes(2)
            s['record_crc16'] = BANK.crc16_ccitt_false(regions[0][r:r + 32])
            struct.pack_into('<H', regions[0], r + 22, s['record_crc16'])
        crc = BANK.crc16_ccitt_false(regions[1])
        struct.pack_into('<I', regions[0], 28, len(regions[1]) | ((crc if regions[1] else 0) << 16))
        BANK._refresh_catalog_crcs(regions[0])
        v['overflow_storage'].update(crc16=crc, sha256=sha(regions[1]))
        v['storage'].update(crc16=BANK.crc16_ccitt_false(regions[0]), sha256=sha(regions[0]))
        v['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26], 'little'),
                            header_crc16=int.from_bytes(regions[0][26:28], 'little'))
        if fam == 'session':
            v['external_storage'].update(crc16=BANK.crc16_ccitt_false(regions[2]), sha256=sha(regions[2]))
        v['elf'] = dict(elf_row, file=elf_row['path'])
        # Inherited validator: payloads == ELF, record CRCs, bank region images.
        C.validate_family(fam, v, regions, None, B)
        path = out / ('runtime-overlays-%s-final.json' % fam)
        path.write_text(json.dumps(v, indent=2) + '\n')
        (out / v['overflow_storage']['file']).write_bytes(regions[1])
        paths.append(path)
        result[fam] = (v, regions)
    return result, paths


def code(B, plane_code, card2b):
    c = policy()['code']
    image = bytearray(c['bytes'])
    image[:len(plane_code)] = plane_code
    N.require(not any(image[len(plane_code):c['card2b_offset']]), 'plane overlaps card2b')
    image[c['card2b_offset']:c['card2b_offset'] + len(card2b)] = card2b
    covered = [(c['card2b_offset'], len(card2b))]
    for s in B.sections:
        marker = '__' + s.name.removeprefix('.') + '_load_start'
        if s.name.startswith(c['mapped_prefix']) and s.section_type != 'SHT_NOBITS' and B.symbols_by_name.get(marker):
            start = B.symbol(marker).value
            if c['bank_base'] <= start < c['bank_base'] + 0x10000:
                raw = B.section_bytes(s.name)
                at = start - c['bank_base']
                N.require(at + len(raw) <= len(image) and not any(image[at:at + len(raw)]), 'mapped owner overlap: ' + s.name)
                image[at:at + len(raw)] = raw
                covered.append((at, len(raw)))
    N.require(max(a + n for a, n in covered) == len(image), 'CODE.BIN extent not ELF-derived')
    return bytes(image)


def window(B):
    w = policy()['window']
    image = bytearray(w['bytes'])
    seen = set()
    for s in B.sections:
        if s.section_type == 'SHT_NOBITS' or not s.bytes:
            continue
        if s.name.startswith('.lisp65_c2_kernal_window.') or s.name == '.lisp65_c2_vectors':
            raw = B.section_bytes(s.name)
            at = s.address - w['base']
            N.require(0 <= at and at + len(raw) <= len(image), 'window section escapes: ' + s.name)
            N.require(not seen & set(range(at, at + len(raw))), 'window overlap: ' + s.name)
            seen |= set(range(at, at + len(raw)))
            image[at:at + len(raw)] = raw
        elif s.name.startswith('.lisp65_c2_kernal_window'):
            raise ValueError('unclassified kernal-window section: ' + s.name)
    return bytes(image)


if __name__ == '__main__':
    p = policy()
    for fam, t in p['families'].items():
        template_is_geometry(fam, t)
    print(json.dumps(dict(status='PASS: FAMILY TEMPLATES CARRY GEOMETRY ONLY',
                          families={f: len(t['manifest']['slices']) for f, t in p['families'].items()}), indent=2))
