#!/usr/bin/env python3
"""2.5.5 Seed producer library (successor of c254_product.py; derived by
build/card-255-seed-prep-r1/drafts/derive_c255_product.py).

2.5.5 = 2.5.4 Final r1 + a Lisp-only change of the IDE editor.  Baseline = the 2.5.4 Seed in its two directories
(c255_config.BASE = receipts r1b, c255_config.BASE_LINK = the link attempt r1) and the sealed Final r1.
preflight: baseline replay of the 2.5.4 static plane and of all six L65S packages, projection of the
2.5.4 -> 2.5.5 lib change onto the 2.5.4 product IDE world (three files; lib/ide-ui.lisp with the two reviewed
L2 product seams), emission of six static images (CHANGED ide, byte-EXACT stdlib-p0 / idex / m65d / buffer / lcc),
all six packages FROZEN (envelopes rebound, L65INDEX exact), computed constants, capacity.  The static plane
SHRINKS.  Only the canonical MK_BCODE host ABI probe may compile/run; no product compiler/link/media action.
rehearse: every pre-link step and the post-link logic with the 2.5.4 ELF as stand-in, plus the
immediate-shape prediction for the new constants.  No compile, no link.
e3: the exhaustive product-world E3 abort sweep (c255_e3_product.py: independent references, control must fail
in both shapes) on the preflight's projected IDE world, write-once directory CFG.E3; the preflight itself runs
the reduced sweep.  rehearse and seed refuse without a PASS receipt bound to the same preflight, tool bytes,
host and ide image.
seed: one attempt, one native link.  Native rule: no function changes except those forced by generated
constants; `.text` stays exactly CFG.BASE_TEXT_BYTES; the reviewed commuting-pair class of the 2.5.4
continuation is NOT carried (any instruction difference halts the inventory); full classified D81 transaction.
Host: the pinned Fedora 45 tools (CFG.HOST_TOOLS); every step records the host and refuses a changed one.
Historical worlds are read-only.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import re
import struct
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import bytecode_p0_stdlib as P
import c2_defstruct_foundations_gate as PK
import c2_full_emission as F
import c2_lite_v6_product_probe as V6
import c2_require_resolver_gate as L
import c2_session_extension_probe as EXT
import c2_substitution_artifacts as SUB
import d81_persistence_fault as D
import runtime_overlay_bank as BANK
import strings_seed_producer as S
import v2_workbench_codemod as CODEMOD
import v2_workbench_codemod_disk_r8_20261001 as CODEMOD_R8

import c254_e3_product as E3BASE     # base of the E3 harness (worlds, VM, cases); bound as tool `e3_base`
import c255_config as CFG
import c255_e3_product as E3P
ROOT = CFG.ROOT
BASE = ROOT / CFG.BASE                       # 2.5.4 Seed receipts r1b (frozen predecessor, byte-identical Final r1)
BASE_LINK = ROOT / CFG.BASE_LINK             # 2.5.4 link attempt r1: the paths of the frozen commands / native inputs
BUILD = ROOT / CFG.SEED                      # write-once Seed
PREFLIGHT = ROOT / CFG.PREFLIGHT             # write-once host-only Chunk A
SELFTEST = ROOT / CFG.SELFTEST               # write-once selftest
FROZEN_PLANE = ROOT / CFG.BASE_PLANE         # 2.5.4 candidate plane = the delivered baseline
FROZEN_NATIVE = ROOT / CFG.BASE_NATIVE       # 2.5.4 75-command recipe (substitutions already applied), in BASE_LINK
FROZEN_MEDIA = BASE / CFG.BASE_MEDIA_DIR     # 2.5.4 rebound overlay families / receipts
MEDIA = CFG.MEDIA_DIR
HERE = BUILD / 'native'
KEYS = CFG.KEYS
STATIC = ('CODE.BIN', 'C2D.BIN', 'SHELF.BIN')
NATIVE_FILES = ('AUTOBOOT.C65', 'BOOT.BIN', 'BOOT.ID', 'BOOTSTAGE.BIN',
                'LISP65.PRG', 'PROFILE', 'REGION1.BIN', 'SESSION.BIN', 'WINDOW.BIN')
BASE_MEDIUM_SHA, BASE_ELF_SHA = CFG.BASE_MEDIUM_SHA, CFG.BASE_ELF_SHA
sha, bind, checked, load, run = S.sha, S.bind, S.checked, S.load, S.run

def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw.encode() if isinstance(raw,str) else raw)

def save(path, value):
    once(path,json.dumps(value,indent=2,sort_keys=True)+'\n')
HOST_HELPER_COMMANDS = []
REHEARSAL_COMMANDS = []
CHUNK_C = ('env PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 python3 -B '
           'tools/host-lisp/c255_seed_producer.py seed')


def image_equal(a, b):
    assert a.code == b.code and a.metadata == b.metadata, 'foreign image content'


def symbols(m):
    return {e['name'] for e in m['entries']} | {
        x['symbol'] for e in m['entries'] for x in e['literals']
        if isinstance(x, dict) and 'symbol' in x}


def image_budget(image):
    m=image.manifest
    assert max(e['length'] for e in m['entries'])<=255, '256-byte object'
    assert m['code_bytes']==len(image.code), 'stale byte price'
    offset=0
    for row in m['entries']:
        assert row['blob_offset']==offset, 'noncontiguous object directory'
        assert int(row['ext_addr'],16)==offset, 'stale external address'
        offset+=row['length']
    assert offset==len(image.code), 'object population/extent drift'


def load_entry_emitter(out):
    """Reuse the frozen host ABI helper; no compiler or linker in preflight."""
    import ctypes
    # 2.5.5: the frozen SNAPSHOT of the baseline preflight, not the gate-rebuilt file under build/c2-lite/
    # (rebuilt by the Fedora 45 compiler on 2026-10-06 with other bytes; a pin on it is a host-made halt).
    source=ROOT/CFG.ENTRY_EMITTER
    assert source.is_relative_to(ROOT/CFG.BASE_PREFLIGHT), 'host ABI helper is not the frozen baseline snapshot'
    pins={source:CFG.ENTRY_EMITTER_SHA,
          ROOT/'scripts/c2d-v6-entry-host.c':'3b924b1c0b30bfb4719b66135e8384dedc91b350d11c2ed9573fd8cfe805b8f7',
          ROOT/'src/c2d_v6_entry.h':'35596f16869c35c5d50c86138b911d59a5969e7920560118d246c590103f8406'}
    for path,digest in pins.items():
        assert sha(path.read_bytes())==digest, 'host entry emitter drift'
    so=out/'host/c2d-v6-entry-emitter-host.so'
    once(so,source.read_bytes())
    library=ctypes.CDLL(str(so))
    fn=library.lisp65_c2d_v6_emit_entry_row
    fn.argtypes=[ctypes.POINTER(ctypes.c_uint8),ctypes.c_uint8,ctypes.c_uint8,
                 ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint16]
    fn.restype=ctypes.c_uint8
    V6._ENTRY_EMITTER,V6._ENTRY_EMITTER_PATH=fn,so
    save(out/'host/entry-emitter.json',dict(status='PASS',inputs=[bind(p) for p in pins],snapshot=bind(so),
        compilers_invoked=0,proof='Frozen shared target routine (snapshot of the 2.5.4 preflight); baseline rows checked byte for byte'))


def plane(out, manifests):
    assert not out.exists()
    specs = tuple((key, 'stdlib' if key == 'stdlib-p0' else key, path)
                  for key, path in zip(KEYS, manifests, strict=True))
    old = SUB.BUILD, SUB.SPECS, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.OUT
    try:
        SUB.BUILD, SUB.SPECS = out / 'product', specs
        product = SUB.build()
        V6.PRODUCT_IDENTITY = SUB.BUILD / 'substitution-artifacts.json'
        V6.OUT = out / 'v6'
        images = [F.emit_image(*spec) for spec in specs]
        V6.STATIC_CODE_BYTES = sum(len(i.code) for i in images)
        result, geometry = V6.static_plane(images)
        V6.validate_plane(result)
        for name, raw in [('CODE.BIN', bytes(result.code[:result.code_low])),
                          ('C2D.BIN', bytes(result.c2d)),
                          ('SHELF.BIN', (SUB.BUILD/'product-shelf-v4-direct.bin').read_bytes())]:
            once(out / name, raw)
        return product, geometry, images
    finally:
        SUB.BUILD, SUB.SPECS, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.OUT = old


def envelope_control(old, new, image, old_id, new_id):
    a = EXT.decode_extension(old, image, expected_build_id=old_id)
    b = EXT.decode_extension(new, image, expected_build_id=new_id)
    assert old[:22] == new[:22] and old[26:] == new[26:], 'package content drift'
    assert len(old) == len(new) and a.combined_crc == b.combined_crc


def emit_package(out, name, product_resident):
    """One L65S package image from its sources (disk-lib role, base 0): the recipe of the 2.4.0 / 2.5.1
    deliveries.  Inside base_era() the lib sources and the suite JSON are the BASE_AUTHORITY bytes.
    The resident is always a FROZEN world: the product resident of the same side (baseline: the 2.5.3 r8
    projected resident, candidate: the 2.5.4 projected resident) or a tracked config resident -- never the
    suite's own live resident chain, whose sources can live in the gate-rebuilt build/bytecode tree."""
    suite_path = str(ROOT / CFG.PACKAGE_SUITE[name])
    suite = P._read_suite(suite_path)
    suite['sources'] = [str(ROOT / s) for s in CFG.PACKAGE_SOURCES[name]]
    suite['cases'] = [dict(name='emission-only', expr='nil', expect='nil')]
    resident = CFG.PACKAGE_RESIDENT[name]
    suite.pop('resident_suites', None)
    suite['resident_suite'] = str(product_resident if resident == CFG.PRODUCT_RESIDENT else ROOT / resident)
    assert Path(suite['resident_suite']).is_file(), ('package resident', name)
    out.mkdir(parents=True)
    if name in CFG.PACKAGE_LIST_DOMAIN_WAIVER:
        # The live list-domain pre-check and the frozen r4 resident disagree on `nth` (same waiver as
        # c2_v253_r2_public_libraries.comfort_reemission); the payload comparison is the check.
        import editor_product_list_domain as DOMAIN
        from unittest.mock import patch
        with patch.object(DOMAIN, 'check_suite', lambda suite: None):
            P.emit_artifacts(suite_path, suite, str(out / name), base_addr=0, artifact_role='disk-lib')
    else:
        P.emit_artifacts(suite_path, suite, str(out / name), base_addr=0, artifact_role='disk-lib')
    return out / (name + '.manifest.json')


def index_row_control(old, new):
    """A re-emitted package may move only the measured fields of its L65INDEX row."""
    assert old.keys() == new.keys(), 'index row shape'
    foreign = sorted(k for k in old if old[k] != new[k] and k not in CFG.PACKAGE_INDEX_FIELDS)
    assert not foreign, ('foreign index mutation', old['name'], foreign)
    return sorted(k for k in old if old[k] != new[k])


def package_price(name, base, cand):
    """Price of one re-emitted package against its 2.5.3 baseline emission (manifests); fail closed."""
    delta = cand['code_bytes'] - base['code_bytes']
    lo, hi = CFG.PACKAGE_DELTA_WINDOW[name]
    assert lo <= delta <= hi, ('package growth outside the card window', name, delta)
    assert cand['code_bytes'] <= CFG.PACKAGE_LIBRARY_BOUND.get(name, 1 << 16), ('library bound', name)
    old = {e['name']: e['length'] for e in base['entries']}
    new = {e['name']: e['length'] for e in cand['entries']}
    assert max(new.values()) <= CFG.PACKAGE_MAX_OBJECT, ('256-byte object', name)
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    assert added == sorted(CFG.PACKAGE_NEW_SYMBOLS[name]) and not removed, ('package object population', name, added, removed)
    return dict(name=name, before=base['code_bytes'], after=cand['code_bytes'], delta=delta, objects_added=added,
                objects_changed={k: [old[k], new[k]] for k in sorted(new.keys() & old.keys()) if old[k] != new[k]},
                max_object=max(new.values()), entries=len(new))


def packages(out, files, old_id, new_id, reemit=True, residents=(None, None)):
    """Six L65S packages -> (records, index receipt).
    FROZEN: the delivered manifest, envelope rebound old_id -> new_id, content and index row exact (2.5.3 rule).
    REEMIT (CFG.PACKAGES_REEMIT, when `reemit`): baseline control = the recipe inside the BASE_AUTHORITY era
    reproduces the delivered payload and row byte for byte; candidate = the same recipe on the authority tree.
    residents = (2.5.3 product resident suite, 2.5.4 product resident suite) for CFG.PRODUCT_RESIDENT packages."""
    old_rows = L.decode_index(files[b'L65INDEX'])
    assert [r['name'] for r in old_rows] == list(CFG.PACKAGE_NAMES)
    rows, records, payloads, prices = [], [], {}, []
    for spec in package_specs():
        name = spec['name']
        print('reproducing/rebinding package '+name,flush=True)
        old = next(r for r in old_rows if r['name'] == name)
        frozen_manifest = ROOT/spec['manifest']['path']

        def measure(manifest, build_id):
            return PK.measured_row(name, name, spec['shelf'], manifest, tuple(spec['dependencies']),
                                   old['track'], old['sector'], product_build_id=build_id)
        row, baseline = measure(frozen_manifest, old_id)
        assert row == old and baseline == files[name.upper().encode()], ('baseline package', name)
        manifest, mode = frozen_manifest, 'FROZEN'
        if reemit and name in CFG.PACKAGES_REEMIT:
            mode = 'REEMIT'
            with base_era():
                base_manifest = emit_package(out/'emission-baseline'/name, name, residents[0])
            brow, bpayload = measure(base_manifest, old_id)
            assert brow == old and bpayload == baseline, ('baseline re-emission differs from the delivered 2.5.3 package', name)
            print('baseline re-emission EXACT: '+name,flush=True)
            manifest = emit_package(out/'emission'/name, name, residents[1])
            prices.append(package_price(name, load(base_manifest), load(manifest)))
        newrow, candidate = measure(manifest, new_id)
        image = F.emit_image(name, spec['shelf'], manifest)
        if mode == 'FROZEN':
            assert newrow == old, 'index row drift'
            envelope_control(baseline, candidate, image, old_id, new_id)
            moved = []
        else:
            moved = index_row_control(old, newrow)
            assert moved, ('re-emitted package did not change', name)
            EXT.decode_extension(candidate, image, expected_build_id=new_id)
        for side, data in [('baseline',baseline),('candidate',candidate)]:
            once(out/side/(name+'.l65s'), data)
        once(out/'loader'/(name+'.code.bin'), image.code)
        once(out/'loader'/(name+'.c2i.bin'), image.metadata)
        rows.append(newrow); payloads[name] = candidate
        records.append(dict(dict(spec, manifest=bind(manifest)), mode=mode, moved_index_fields=moved,
                            baseline=bind(out/'baseline'/(name+'.l65s')),
                            candidate=bind(out/'candidate'/(name+'.l65s')),
                            code=bind(out/'loader'/(name+'.code.bin')),
                            metadata=bind(out/'loader'/(name+'.c2i.bin')),row=newrow))
    index = L.encode_index(rows)
    changed = [r['name'] for r, o in zip(rows, old_rows, strict=True) if r != o]
    assert changed == [n for n in CFG.PACKAGE_NAMES if reemit and n in CFG.PACKAGES_REEMIT], ('index rows moved', changed)
    assert (index == files[b'L65INDEX']) == (not changed) and len(index) == len(files[b'L65INDEX'])
    assert L.decode_index(index, payloads, artifact_build_id=new_id) == rows
    once(out/'candidate'/'L65INDEX', index)
    return records, dict(index=bind(out/'candidate'/'L65INDEX'), changed_rows=changed, prices=prices,
                         baseline_index_sha256=sha(files[b'L65INDEX']), rows=rows)

def constants(out, before, after, old_geometry, geometry):
    tables = []
    for name, filename, offset in [('shelf','SHELF.BIN',32),('c2d','C2D.BIN',None)]:
        raw = [(out/side/filename).read_bytes() for side in ('baseline','candidate')]
        if offset is None:
            offset = struct.unpack_from('<H',raw[0],28)[0]
            assert offset == struct.unpack_from('<H',raw[1],28)[0]
        tables.append(dict(table=name, before=[BANK.crc16_ccitt_false(raw[0][offset+i*32:offset+(i+1)*32]) for i in range(6)],
                           after=[BANK.crc16_ccitt_false(raw[1][offset+i*32:offset+(i+1)*32]) for i in range(6)]))
    return dict(LISP65_C2_PRODUCT_BUILD_ID=after['product_build_id_hex'],
                LISP65_C2_PRODUCT_SHELF_BYTES=after['artifacts']['shelf']['bytes'],
                LISP65_C2_LITE_STATIC_CODE_BYTES=geometry['code_bytes'],crc_tables=tables,
                before_product=before,after_product=after,before_geometry=old_geometry,after_geometry=geometry)


def verify_preflight():
    r = load(PREFLIGHT/'receipt.json')
    assert r['status'] == 'PASS' and r['baseline_reproduction'] == 'PASS'
    attempt = load(PREFLIGHT/'attempt.json')
    assert attempt['tools'] == tool_identity(), 'tool bytes changed since preflight'
    assert attempt['host'] == host_identity(), 'host tools changed since preflight'
    checked(r['inputs'])
    for row in load(PREFLIGHT/'inputs.json') + r['artifacts']:
        checked(row)
    predecessor()
    return r


def classified(before, after, domains):
    result = S.classify_bytes(before,after,domains)
    assert result['unclassified_bytes'] == 0, 'unclassified media change'
    return result


def native_inputs():
    """Read and verify the exact recipe that produced the baseline (2.5.4) ELF: the receipts of the link attempt
    CFG.BASE_LINK.  Host tool rows of that recipe (Fedora 44 hashes) are NOT read: the live tools are bound."""
    recipe = load(FROZEN_NATIVE/'command-proof.json')
    derivation = load(FROZEN_NATIVE/'derived-inputs.json')
    ready = load(FROZEN_NATIVE/'command-ready.json')
    # r7c's own derived-inputs.json lists the CRC table source both as `generated` and inside
    # `all_generated` (Seed r5 HALT: the same derived file was materialised twice).  One row per
    # path; a repeated path must be the identical binding.
    rows, seen_rows = [], {}
    for row in derivation['all_generated'] + [derivation['generated']]:
        if row['path'] in seen_rows:
            assert seen_rows[row['path']] == row, ('conflicting native input rows', row['path'])
            continue
        seen_rows[row['path']] = row
        rows.append(row)
    assert derivation['generated']['path'] in seen_rows
    for row in rows:
        checked(row)
    # Include in-place toolchain dependencies in the consumed-input authority.
    tools = [row['source'] for row in ready['native'] if row['source']['path'].startswith('tools/llvm-mos/')]
    tools += [bind(ROOT/'tools/llvm-mos/bin'/name) for name in
              ('mos-mega65-clang','llvm-readobj','llvm-objdump','llvm-objcopy')]
    tools += [bind(Path(recipe['commands'][73][0])),bind(Path('/usr/bin/setarch')),bind(ROOT/'tools/llvm-mos/bin/ld.lld')]
    for platform in ('mega65','commodore','common'):
        folder=ROOT/'tools/llvm-mos/mos-platform'/platform
        tools += [bind(p) for p in sorted(folder.rglob('*')) if p.is_file()]
    for row in tools:
        checked(row)
    commands = recipe['commands']
    assert len(commands) == 75 and all('-c' in c for c in commands[:73])
    assert 'llvm-link' in commands[73][0] and '-c' not in commands[74]
    assert '-Wl,--emit-relocs' in commands[74]
    # 2.5.5: the two host executables of the recipe are exactly the pinned ones (CFG.HOST_TOOLS, checked live).
    assert commands[73][0] == '/usr/bin/llvm-link' and commands[74][:3] == ['/usr/bin/setarch', 'x86_64', '-R'], \
        'recipe does not use the pinned host tools'
    pinned = {row['path']: row['sha256'] for row in CFG.host_tools()}
    assert all(row['sha256'] == pinned[row['path']] for row in tools if row['path'] in pinned), 'host tool is not the pinned binary'
    return commands, rows, tools


def rebind_family(C,fam,value,regions,a,b,elf):
    """Rebind exact existing slots after successful native byte attribution."""
    for row in value['slices']:
        old,new = a.section_bytes(row['section']),b.section_bytes(row['section'])
        assert len(old)==len(new)==row['file_size']==row['memory_size']
        at,rid = row['file_offset'],row['region_id']
        assert regions[rid][at:at+len(old)] == old
        regions[rid][at:at+len(new)] = new
        row.update(sha256=sha(new),crc16=BANK.crc16_ccitt_false(new))
        at=32+32*row['id']
        struct.pack_into('<H',regions[0],at+20,row['crc16'])
        regions[0][at+22:at+24]=bytes(2)
        row['record_crc16']=BANK.crc16_ccitt_false(regions[0][at:at+32])
        struct.pack_into('<H',regions[0],at+22,row['record_crc16'])
    crc=BANK.crc16_ccitt_false(regions[1])
    struct.pack_into('<I',regions[0],28,len(regions[1])|((crc if regions[1] else 0)<<16))
    BANK._refresh_catalog_crcs(regions[0])
    value['overflow_storage'].update(crc16=crc,sha256=sha(regions[1]))
    value['storage'].update(crc16=BANK.crc16_ccitt_false(regions[0]),sha256=sha(regions[0]))
    value['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26],'little'),header_crc16=int.from_bytes(regions[0][26:28],'little'))
    if fam=='session':
        value['external_storage'].update(crc16=BANK.crc16_ccitt_false(regions[2]),sha256=sha(regions[2]))
    value['elf']=dict(bind(elf),file=str(elf))
    return C.validate_family(fam,value,regions,a,b)


def _chains(raw):
    return {D.entry_name(s.record).decode(): D.file_chain(raw, s.record) for s in D.directory_slots(raw) if s.record[2]}


def zero_residue(before_raw, packed, files, changed, domains):
    """Explicit media step of 2.5.5 (reviewer decision 2026-10-06), run AFTER the packer.  A file that gets shorter
    frees sectors; the packer (strings_seed_producer.replace_file, unchanged) marks them free in the BAM and leaves
    their bytes, and it keeps the old bytes behind the new end of data in the file's new last sector.  Those are
    bytes of the PREVIOUS medium.  Rule: for every file whose chain got SHORTER, every freed sector (256 B) and the
    slack of its new last sector (the bytes behind the stored length: byte 1 of that sector = data bytes + 1; the
    cold stager copies `byte 1 - 1` bytes and the runtime reads the shelf only below its byte count, so no reader
    sees them) are set to ZERO.  Files that keep their sector count are not touched (as in every release before).
    Fail closed: freed sectors are free in the BAM and still hold the previous medium's bytes when the step
    starts; no byte outside the named ranges changes; every file read through its directory chain is unchanged.
    Each cleared byte enters the classified ledger (`domains`).  Returns (medium, record)."""
    old, new = _chains(before_raw), _chains(packed)
    state, rows, touched = bytearray(packed), [], set()
    for name in changed:
        a, b, payload = old[name], new[name], files[name.encode()]
        keep = min(len(a), len(b))
        assert len(b) == (len(payload) + 253) // 254 and b[:keep] == a[:keep], ('chain plan', name)
        if len(b) >= len(a):
            continue
        ranges = []
        for ts in a[len(b):]:
            at = D.sector_offset(*ts)
            assert D.sector_is_free(packed, *ts), ('freed sector still allocated', name, ts)
            assert packed[at:at + 256] == before_raw[at:at + 256], ('freed sector was rewritten by the packer', name, ts)
            ranges.append(('freed-sector', ts, at, 256))
        used = 2 + len(payload) - 254 * (len(b) - 1)
        at = D.sector_offset(*b[-1])
        assert packed[at] == 0 and packed[at + 1] == used - 1, ('final-sector length byte', name, packed[at + 1], used)
        assert packed[at + 2:at + used] == payload[254 * (len(b) - 1):], ('final-sector data', name)
        ranges.append(('slack', b[-1], at + used, 256 - used))
        cleared = 0
        for kind, _ts, start, count in ranges:
            for i in range(start, start + count):
                touched.add(i)
                if state[i]:
                    assert i not in domains and packed[i] == before_raw[i], ('residue byte is not a byte of the previous medium', name, i)
                    domains[i] = (before_raw[i], 0, name + ': ' + kind)
                    state[i] = 0
                    cleared += 1
        rows.append(dict(file=name, bytes=len(payload), sectors_before=len(a), sectors_after=len(b), length_byte=used - 1,
                         ranges=[dict(kind=kind, track=ts[0], sector=ts[1], offset=start, bytes=count) for kind, ts, start, count in ranges],
                         bytes_in_ranges=sum(r[3] for r in ranges), nonzero_bytes_cleared=cleared))
    state = bytes(state)
    D.validate_bam(state)
    assert D.visible_files(state) == D.visible_files(packed), 'zeroing changed a file'
    assert len(state) == len(packed) and all(x == y or (i in touched and y == 0) for i, (x, y) in enumerate(zip(packed, state))), \
        'zeroing changed a byte outside the named ranges'
    return state, dict(rule='for every file whose sector chain got shorter: each freed sector and the slack behind the stored '
                            'length of its new last sector are zero; nothing else is touched',
                       unzeroed_medium_sha256=sha(packed), zeroed_medium_sha256=sha(state), files=rows,
                       bytes_in_ranges=sum(r['bytes_in_ranges'] for r in rows),
                       nonzero_bytes_cleared=sum(r['nonzero_bytes_cleared'] for r in rows))


def residue_record(before_raw, final, files, changed):
    """Read-back assertion on the FINAL medium: residue 0.  Every sector freed against the predecessor chain is free
    in the BAM and all zero; the slack of the new last sector of every shortened file is all zero; and -- the rule a
    reproduction can apply to the medium alone -- EVERY sector the BAM marks free is all zero."""
    old, new, rows = _chains(before_raw), _chains(final), []
    for name in changed:
        a, b, payload = old[name], new[name], files[name.encode()]
        if len(b) >= len(a):
            continue
        for ts in a[len(b):]:
            at = D.sector_offset(*ts)
            assert D.sector_is_free(final, *ts), ('freed sector still allocated', name, ts)
            assert not any(final[at:at + 256]), ('non-zero byte left in a freed sector', name, ts)
        used = 2 + len(payload) - 254 * (len(b) - 1)
        at = D.sector_offset(*b[-1])
        assert final[at + 1] == used - 1 and not any(final[at + used:at + 256]), ('non-zero slack behind a shortened file', name)
        rows.append(dict(file=name, freed=[list(ts) for ts in a[len(b):]], last_sector=list(b[-1]), used_bytes=used, slack_bytes=256 - used))
    free = [(t, s) for t in range(1, 81) for s in range(40) if D.sector_is_free(final, t, s)]
    dirty = [list(ts) for ts in free if any(final[D.sector_offset(*ts):D.sector_offset(*ts) + 256])]
    assert not dirty, ('a sector the BAM marks free is not zero', dirty[:8])
    return dict(status='PASS', residue_bytes=0, shortened_files=rows, free_sectors=len(free), free_sectors_nonzero=0,
                medium_sha256=sha(final), previous_medium_sha256=sha(before_raw))


def pack_media(med,artifacts,before_raw,records,build_id,derived):
    """One complete 2.5.4 -> 2.5.5 transaction; every change has an exact byte pair."""
    before = D.visible_files(before_raw)
    expected = {name:(artifacts/name.decode().lower()).read_bytes() for name in before}
    assert len(expected)==20
    assert expected[b'INIT.L65']==before[b'INIT.L65']
    index=(PREFLIGHT/'packages/candidate/L65INDEX').read_bytes()
    assert expected[b'L65INDEX']==index and (index!=before[b'L65INDEX'])==bool(CFG.PACKAGES_REEMIT)
    assert set(derived) <= {n.encode() for n in NATIVE_FILES}
    assert derived == {n:expected[n] for n in derived} and all(derived[n]!=before[n] for n in derived)
    baseline=(PREFLIGHT/'planes/baseline/CODE.BIN').read_bytes()
    candidate=(PREFLIGHT/'planes/candidate/CODE.BIN').read_bytes()
    assert expected[b'CODE.BIN']==project_delivery_code((med/'code-native-rebound.bin').read_bytes(),baseline,candidate)
    assert expected[b'SHELF.BIN']==(PREFLIGHT/'planes/candidate/SHELF.BIN').read_bytes()
    initial=(PREFLIGHT/'planes/candidate/C2D.BIN').read_bytes()
    assert expected[b'C2D.BIN']==initial+bytes(50816-len(initial))
    permitted = {n.encode() for n in STATIC}|set(derived)|{r['name'].upper().encode() for r in records}|{b'L65INDEX'}
    assert all(before[n]==expected[n] for n in before if n not in permitted), 'foreign media file'
    for spec in records:
        name=spec['name'].upper().encode()
        assert expected[name]==checked(spec['candidate'])
    raw,domains=before_raw,{}
    changed=[]
    for name,payload in expected.items():
        if payload != before[name]:
            changed.append(name.decode())
            raw = S.replace_file(raw,name.decode(),payload,domains)
    locators={D.entry_name(slot.record).decode().lower():D.file_chain(raw,slot.record)[0]
              for slot in D.directory_slots(raw) if slot.record[2]}
    rows=[];payloads={}
    for spec in records:
        name=spec['name']
        entry,payload=PK.measured_row(name,name,spec['shelf'],ROOT/spec['manifest']['path'],
            tuple(spec['dependencies']),*locators[name],product_build_id=build_id)
        assert payload==expected[name.upper().encode()]
        rows.append(entry);payloads[name]=payload
    # replace_file preserves first-sector locators: the measured rows are the preflight rows, and the rows
    # of the frozen packages are the delivered 2.5.4 rows.
    assert L.encode_index(rows)==index, 'unexpected index locator/content drift'
    old_rows=L.decode_index(before[b'L65INDEX'])
    assert [r['name'] for r,o in zip(rows,old_rows,strict=True) if r!=o]==[n for n in CFG.PACKAGE_NAMES if n in CFG.PACKAGES_REEMIT]
    assert L.decode_index(expected[b'L65INDEX'],payloads,artifact_build_id=build_id)==rows
    # 2.5.5: explicit, asserted zeroing of what a shorter file leaves behind (never a silent packer change).
    raw,zeroing=zero_residue(before_raw,raw,expected,changed,domains)
    final=med/CFG.MEDIA_NAME;once(final,raw)
    persisted=final.read_bytes();D.validate_bam(persisted)
    actual=D.visible_files(persisted)
    assert actual==expected
    assert struct.unpack_from('<I',actual[b'SHELF.BIN'],22)[0]==build_id
    assert struct.unpack_from('<I',actual[b'C2D.BIN'],44)[0]==build_id
    product=load(PREFLIGHT/'planes/candidate/product/substitution-artifacts.json')
    images=[F.emit_image(key,'stdlib' if key=='stdlib-p0' else key,ROOT/row['path'])
            for key,row in zip(KEYS,product['manifests'],strict=True)]
    F.verify_shelf(actual[b'SHELF.BIN'],images,F.declared_exports(images))
    assert len(D.visible_files(persisted))==20 and len(persisted)==819200
    # Read every chain independently, including those beyond directory entry 0.
    occupied=set()
    for slot in D.directory_slots(persisted):
        if not slot.record[2]:continue
        chain=D.file_chain(persisted,slot.record)
        assert not occupied.intersection(chain), 'crosslinked delivery file'
        occupied.update(chain)
        assert all(not D.sector_is_free(persisted,*ts) for ts in chain)
        assert D.read_record_payload(persisted,slot.record)==expected[D.entry_name(slot.record)]
    assert L.decode_index(D.visible_files(persisted)[b'L65INDEX'],payloads,artifact_build_id=build_id)==rows
    mutations=L.mutation_gate(expected[b'L65INDEX'],payloads,artifact_build_id=build_id)
    diff=classified(before_raw,persisted,domains)
    assert {r['owner'] for r in diff['rows']} <= {name+': '+kind for name in changed
                                                   for kind in ('file-chain','directory','BAM','freed-sector','slack')}
    residue=residue_record(before_raw,persisted,expected,changed)
    assert residue['medium_sha256']==zeroing['zeroed_medium_sha256']==sha(persisted)
    save(med/'residue-zeroing.json',dict(status='PASS',residue_bytes=0,zeroing=zeroing,read_back=residue))
    save(med/'classified-byte-ledger.json',dict(entries=[dict(offset=i,before=x,after=y,owner=owner) for i,(x,y,owner) in sorted(domains.items())]))
    save(med/'d81-byte-diff.json',diff)
    return dict(status='PASS',medium=bind(final),predecessor_medium=bind(ROOT/load(BASE/'complete.json')['medium']['path']),
        files={n.decode():dict(bytes=len(v),sha256=sha(v)) for n,v in expected.items()},
        changed_files=changed,every_file_read_back=True,index_exact=index==before[b'L65INDEX'],
        index_changed_rows=[n for n in CFG.PACKAGE_NAMES if n in CFG.PACKAGES_REEMIT],INIT_exact=True,
        index_rows=rows,unclassified_bytes=0,diff=bind(med/'d81-byte-diff.json'),
        ledger=bind(med/'classified-byte-ledger.json'),mutations=mutations,
        residue_zeroing=bind(med/'residue-zeroing.json'),residue_bytes=0,
        zeroed=dict(files=[r['file'] for r in zeroing['files']],bytes_in_ranges=zeroing['bytes_in_ranges'],
                    nonzero_bytes_cleared=zeroing['nonzero_bytes_cleared'],unzeroed_medium_sha256=zeroing['unzeroed_medium_sha256']))


def derive_profile(med,artifacts,pre):
    """The overlay ABI profile is independent of the static shelf build ID.

    Revalidate its exact bytes against both family contracts and every consumed
    native ABI header before deriving boot/stager descriptors. Changing this ABI
    ID would require a separately reviewed native source change, not repinning
    a historical profile's static-artifact provenance field.
    """
    raw=(artifacts/'profile').read_bytes()
    digest=sha(raw);profile_id=int(digest[:8],16)
    for fam in ('boot','session'):
        value=load(med/('runtime-overlays-'+fam+'-final.json'))
        assert value['abi']['sha256']==digest and value['profile_build_id']==profile_id
    headers=[]
    for row in load(HERE/'derived-inputs.json')['all_generated']:
        path=ROOT/row['path']
        if path.name in ('stage-config.h','runtime-overlay.prepare.h'):
            source=checked(row).decode()
            ids=re.findall(r'#define LISP65_(?:BOOT_OVERLAY|RUNTIME_OVERLAY)_PROFILE_BUILD_ID (0x[0-9a-f]+)UL',source)
            assert len(ids)==1 and int(ids[0],16)==profile_id
            headers.append(row)
    assert len(headers)>=2
    save(med/'profile-bindings.json',dict(status='PASS',profile=bind(artifacts/'profile'),
        ABI_profile_build_id=f'0x{profile_id:08x}',consumed_native_headers=headers,
        static_product_build_id=pre['constants']['LISP65_C2_PRODUCT_BUILD_ID'],
        ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf'),
        treatment='Unchanged ABI contract, freshly checked against compiled header closure and both overlay families'))


def media(stager=True):
    import comfort_default_media as C
    pre = verify_preflight()
    inv = load(HERE/'inventory.json')
    assert inv['status']=='PASS' and inv['unclassified_bytes']==0
    for row in inv['ELFs']:
        checked(row)
    previous,before_raw=predecessor()
    before=D.visible_files(before_raw)
    delivery_control(PREFLIGHT/'planes/baseline',before)
    med = BUILD/MEDIA
    med.mkdir()
    artifacts=med/'artifacts';artifacts.mkdir()
    for name,data in before.items():
        once(artifacts/name.decode().lower(),data)
    elf = ROOT / inv['ELFs'][1]['path']
    a, b = [C.ElfTruth.read(ROOT / r['path'], llvm_readobj=C.READOBJ, include_section_data=True) for r in inv['ELFs']]
    families, manifests = {}, []
    for fam in ('boot', 'session'):
        value = load(FROZEN_MEDIA / ('runtime-overlays-'+fam+'-final.json'))
        regions = {0: bytearray(before[(fam+'.bin').upper().encode()]),
                   1: bytearray((FROZEN_MEDIA / value['overflow_storage']['file']).read_bytes())}
        if fam == 'session':
            regions[2] = bytearray(a.section_bytes('.lisp65_rt_card2b_disk'))
        families[fam] = rebind_family(C, fam, value, regions, a, b, elf)
        (artifacts / (fam+'.bin')).write_bytes(regions[0])
        once(med / value['overflow_storage']['file'], regions[1])
        if fam == 'session':
            (artifacts / 'region1.bin').write_bytes(regions[1])
            code = bytearray(before[b'CODE.BIN'])
            assert code[0xee00:0xee00+len(regions[2])] == a.section_bytes('.lisp65_rt_card2b_disk')
            code[0xee00:0xee00+len(regions[2])] = regions[2]
            (artifacts / 'code.bin').write_bytes(code)
        path = med / ('runtime-overlays-'+fam+'-final.json')
        save(path, value); manifests.append(path)
    window = bytearray(before[b'WINDOW.BIN'])
    for section in a.sections:
        if section.name.startswith('.lisp65_c2_kernal_window.') and section.section_type != 'SHT_NOBITS':
            old, new = a.section_bytes(section.name), b.section_bytes(section.name)
            at = section.address-0xe000
            assert 0 <= at and at+len(old) <= len(window) and len(old) == len(new)
            assert window[at:at+len(old)] == old
            window[at:at+len(new)] = new
        elif section.name.startswith('.lisp65_c2_mapped_') and section.section_type != 'SHT_NOBITS':
            assert a.section_bytes(section.name) == b.section_bytes(section.name), section.name
    (artifacts / 'window.bin').write_bytes(window)
    assert a.section_bytes('.lisp65_c2_vectors') == b.section_bytes('.lisp65_c2_vectors')
    code = bytearray((artifacts / 'code.bin').read_bytes())
    baseline_code = (PREFLIGHT / 'planes/baseline/CODE.BIN').read_bytes()
    candidate_code = (PREFLIGHT / 'planes/candidate/CODE.BIN').read_bytes()
    once(med/'code-native-rebound.bin',code)
    code = project_delivery_code(code,baseline_code,candidate_code)
    (artifacts / 'code.bin').write_bytes(code)
    for name in ('SHELF.BIN', 'C2D.BIN'):
        candidate = (PREFLIGHT / 'planes/candidate' / name).read_bytes()
        if name == 'C2D.BIN':
            assert len(candidate) == C.M.C2D_PREFIX_BYTES
            candidate += bytes(C.M.C2D_RESET_DOMAIN_BYTES - len(candidate))
        (artifacts / name.lower()).write_bytes(candidate)
    table = C.P.verifier_binding_bytes(*manifests)+C.P.family_stage_binding_bytes(*manifests)
    assert len(table) == 40
    once(med / 'runtime-overlay-verifier-bindings.bin', table)
    prg = med / 'lisp65-c2-substitution-linked.prg'
    once(prg, elf.with_suffix('').read_bytes())
    C.FACADE.materialize_facade(prg, elf, med / 'facade-materialization.json')
    unbound = prg.read_bytes()
    once(med / 'lisp65-c2-substitution-unbound.prg', unbound)
    C.PRG.from_elf(elf, unbound)
    raw = bytearray(unbound)
    at = b.section('.lisp65_runtime_overlay_verifier_bindings').address-int.from_bytes(raw[:2], 'little')+2
    raw[at:at+40] = table
    binding = load(FROZEN_MEDIA / 'kernal-window-publish-last.json')
    crc = C.BANK.crc16_ccitt_false(window)
    binding['single_product_link_window'] = dict(bind(artifacts / 'window.bin'), crc16=f'0x{crc:04x}')
    for row in binding['binding_operands']:
        assert raw[row['file_offset']] == row['compiled_value']
        row['published_value'] = (crc >> 8) & 255 if row['name'].endswith('high') else crc & 255
        raw[row['file_offset']] = row['published_value']
    save(med / 'kernal-window-publish-last.json', binding)
    domain = set(range(at, at+40)) | {r['file_offset'] for r in binding['binding_operands']}
    assert len(raw) == len(unbound) and all(x == y or i in domain for i, (x, y) in enumerate(zip(unbound, raw)))
    save(med / 'total-publish-last-domain.json', dict(status='passed', changes_outside_declared_domains=0,
        declared_domain_bytes=len(domain), bound_product_sha256=sha(raw), unbound_product_sha256=sha(unbound)))
    prg.write_bytes(raw)
    (artifacts / 'lisp65.prg').write_bytes(C.PRG.from_elf(elf, bytes(raw), publication_dir=med))
    derive_profile(med,artifacts,pre)
    C.CAN.ARTIFACTS = artifacts
    _, geometry = C.CAN.build_boot_stage(elf, artifacts / 'profile')
    build_id=pre['constants']['after_product']['product_build_id_u32']
    records=pre['packages']
    for spec in records:
        (artifacts/spec['name']).write_bytes(checked(spec['candidate']))
    (artifacts/'l65index').write_bytes(checked(pre['package_index']['index']))
    save(med/'runtime-receipt.json',dict(status='PASS',ELF=bind(elf),families=families,
        boot_geometry=geometry,product_build_id=build_id,packages=records,package_index=pre['package_index'],
        comfort_bank2_bytes=next(r['row']['bank2'] for r in records if r['name']=='repl-comfort')))
    # The inherited cold delivery stager is not another product link.
    C.MED, C.ART, C.OUT, C.ELF = med, artifacts, HERE, elf
    C.run = lambda cmd: run(cmd, med / ('host-'+sha(str(cmd).encode())[:16]+'.log')).decode('latin1')
    C.M.ASM_CONTRACT_INCLUDE = med / 'stager-contract.inc'
    assembly = C.M.STAGER_S.read_text().replace(C.M.ASM_CONTRACT_INCLUDE_TOKEN,
        '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"')
    C.M.ASM_CONTRACT_INCLUDE_TOKEN = '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"'
    C.M.STAGER_S = med / 'cold-stager-chain.s'
    once(C.M.STAGER_S, assembly)
    C.M.run = lambda cmd, label: run(cmd, med / ('stager-'+sha(label.encode())[:16]+'.log')).decode('latin1')
    if stager:
        C.stager()
    # These payloads were reconstructed above from the classified ELF, its
    # publish-last bindings, frozen package manifests and cold stager. Bind
    # their exact bytes before entering the disk transaction. INIT stays fixed.
    derived={n.encode():(artifacts/n.lower()).read_bytes() for n in NATIVE_FILES
             if (artifacts/n.lower()).read_bytes()!=before[n.encode()]}
    save(med/'derived-file-bindings.json',[bind(artifacts/n.decode().lower()) for n in derived])
    result=pack_media(med,artifacts,before_raw,records,build_id,derived)
    result['native_bindings']=bind(med/'runtime-receipt.json')
    result['stager']=bind(med/'descriptor-stager-receipt.json') if stager else 'SKIPPED (pre-link rehearsal)'
    save(BUILD/'media.json',result)
    return result



def finish(pre, rehearsal=False):
    medium=load(BUILD/'media.json')
    inv=load(HERE/'inventory.json')
    assert medium['status']=='PASS' and medium['unclassified_bytes']==0
    assert inv['status']=='PASS' and inv['unclassified_bytes']==0
    checked(medium['medium'])
    save(BUILD/'price.json',dict(**pre['price'],static_deltas=pre['static_deltas'],
        native_ELF_bytes_before=inv['ELFs'][0]['bytes'],native_ELF_bytes_after=inv['ELFs'][1]['bytes']))
    save(BUILD/'capacity.json',pre['capacity'])
    save(BUILD/'source.json',dict(status='PASS',preflight=bind(PREFLIGHT/'receipt.json'),
        inputs=pre['inputs'],committed_source_admission='OPEN; no Git writes',
        e3=dict(reduced=pre['e3']['receipt'],exhaustive=load(BUILD/'attempt.json')['e3'])))
    save(BUILD/'inventory.json',inv)
    save(BUILD/'negative-controls.json',load(SELFTEST/'receipt.json'))
    complete=dict(status='REHEARSAL-NOT-A-PRODUCT' if rehearsal else 'PASS',seed=0 if rehearsal else 1,final=0,
        product_links=0 if rehearsal else 1,medium=medium['medium'],
        ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf'),emulator_runs=0,device_contacts=0,
        receipts=[bind(BUILD/n) for n in ('price.json','capacity.json','source.json','inventory.json','media.json','negative-controls.json')],
        claim='Host/native/media Seed only; target acceptance and release admission remain open')
    save(BUILD/'seed.json',complete);save(BUILD/'complete.json',complete)
    return complete


def seed():
    pre=verify_preflight()
    tests=load(SELFTEST/'receipt.json')
    assert tests['status']=='PASS' and tests['tools']==tool_identity(), 'tool bytes changed since selftest'
    assert tests['host']==host_identity(), 'host tools changed since selftest'
    assert CFG.same_authority(pre['source_revision'],source_revision()), 'authority or consumed roots moved since preflight'
    e3_receipt=require_e3(pre)
    assert not BUILD.exists(), 'write-once 2.5.5 Seed attempt already claimed; no retry'
    BUILD.mkdir()
    save(BUILD/'attempt.json',dict(status='STARTED',tools=tool_identity(),host=host_identity(),authority=source_revision(),
        predecessor=bind(BASE/'complete.json'),predecessor_link=CFG.BASE_LINK,preflight=bind(PREFLIGHT/'receipt.json'),e3=e3_receipt))
    try:
        commands=prepare_native(pre)
        for i,command in enumerate(commands):
            if i==74:
                save(BUILD/'product-link-claim.json',dict(product_links=1,command=command))
            (ROOT/command[command.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
            S.run(command,BUILD/f'command-{i:03d}.log')
            print(f'completed frozen command {i+1}/75',flush=True)
        # The merged bitcode of command 73 is a host-dependent intermediate: recorded, never compared with 2.5.4.
        save(BUILD/'linked.json',dict(status='LINKED',product_links=1,
            ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf'),host=host_identity(),python=python_runtime(),
            host_dependent_intermediate=bind(ROOT/commands[73][commands[73].index('-o')+1])))
        inventory()
        media()
        return finish(pre)
    except BaseException as error:
        save(BUILD/'halt.json',dict(status='HALT',error=repr(error),
            product_link_claimed=(BUILD/'product-link-claim.json').exists(),
            note='No in-place retry. Retain this attempt and review a named successor.'))
        raise


READ_ONLY_ELF_TOOLS = ('llvm-readobj', 'llvm-objdump', 'llvm-objcopy', 'llvm-nm')


def rehearsal_command_ok(command):
    """Pre-link rehearsal: only dependency preprocessing (-E -M, no -c / -o) and read-only ELF tools."""
    command = [str(x) for x in command]
    if command[:len(S.PRIORITY)] == list(S.PRIORITY):
        command = command[len(S.PRIORITY):]
    if not command:
        return False
    if Path(command[0]).name in READ_ONLY_ELF_TOOLS:
        return True
    return '-E' in command and '-M' in command and '-c' not in command and '-o' not in command


def guard(root, *, host_only, rehearsal=False):
    """Enforce the audited write boundary, even inside imported generators."""
    temporary = Path(tempfile.gettempdir()).resolve()
    assert not temporary.is_relative_to(ROOT), 'TMPDIR must not lie inside the repository'
    helper_executables = set()
    def audit(event,args):
        # Python 3.14 subprocess uses os.posix_spawn internally; process
        # creation stays gated by the subprocess.Popen audit event below.
        if event.startswith('socket.') or event in ('os.system','os.exec'):
            raise RuntimeError('forbidden operation: '+event)
        if rehearsal and event=='subprocess.Popen':
            if not rehearsal_command_ok(args[1]):
                raise RuntimeError('pre-link rehearsal refuses a compile/link/other process: '+repr(list(args[1]))[:300])
            REHEARSAL_COMMANDS.append([str(x) for x in args[1]])
        if host_only and event=='subprocess.Popen':
            executable,command=args[:2]
            # V6.direct_value deliberately calls the target MK_BCODE macro via
            # this tiny host probe, rather than reimplementing tag arithmetic.
            # This exception cannot invoke llvm-mos or the product/stager link.
            command=list(command)
            if (executable in ('cc','/usr/bin/cc') and len(command)==11
                    and command[1:8]==['-std=c99','-Os','-Wall','-Wextra','-Werror','-I',str(ROOT)]
                    and command[-2]=='-o'):
                source=Path(command[8]).resolve(); target=Path(command[-1]).resolve()
                assert source.parent==target.parent and source.parent.is_relative_to(temporary)
                assert source.name=='mk_bcode.c' and target.name=='mk_bcode'
                assert '#include "src/obj.h"' in source.read_text()
                helper_executables.add(str(target))
            elif len(command)==1 and command[0] in helper_executables:
                pass
            else:
                raise RuntimeError('forbidden preflight subprocess: '+repr(command))
            HOST_HELPER_COMMANDS.append(command)
        paths=[]
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
                paths=[path]
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod'):
            paths=[args[0]]
        elif event in ('os.rename','os.link','os.symlink'):
            paths=list(args[:2])
        for index,value in enumerate(paths):
            if isinstance(value,(str,bytes)):
                path=Path(os.fsdecode(value))
                dirfd = (args[1] if event in ('os.remove','os.rmdir') else args[2]
                         if event in ('os.mkdir','os.chmod') else args[2+index]
                         if event in ('os.rename','os.link') else -1)
                if not path.is_absolute() and isinstance(dirfd,int) and dirfd >= 0:
                    path=Path('/proc/self/fd')/str(dirfd)/path
                path=path.resolve()
                assert path.is_relative_to(root) or path.is_relative_to(temporary), 'write outside successor workspace: '+str(path)
    sys.addaudithook(audit)


# ===== 2.5.3 replacement and new functions (from new_functions.py) =====

# Replacement / new functions for c253_product.py.  Audit aid: derive_product.py
# splices these (by function name) into the c253 copy of o2_lite_r7_product.py.
# This file is NOT a module; names resolve inside c253_product.py.


def tool_identity():
    """All Seed tool files; a selftest/preflight/e3/rehearse/seed chain must agree on them.  FIVE members: the
    E3 harness of 2.5.5 imports its 2.5.4 base, so both files are tool bytes.  (The immediate-site table is bound
    by its sha256 in the config.)"""
    here = Path(__file__).resolve().parent
    assert Path(E3P.__file__).resolve() == (here / CFG.E3_TOOL).resolve(), 'E3 harness is not the installed tool'
    assert Path(E3BASE.__file__).resolve() == (here / CFG.E3_BASE_TOOL).resolve() and E3P.E3 is E3BASE, 'E3 base is not the installed tool'
    return dict(product=bind(Path(__file__)),
                producer=bind(here / CFG.PRODUCER_TOOL),
                config=bind(Path(CFG.__file__)),
                e3=bind(here / CFG.E3_TOOL),
                e3_base=bind(here / CFG.E3_BASE_TOOL))


def host_identity():
    """The host of this chain.  The three host tools must be the pinned Fedora 45 binaries (CFG.HOST_TOOLS; raises
    otherwise).  Every step stores it and refuses host tools that changed since the selftest.  The Python build is
    NOT pinned and not compared (reviewer decision 2026-10-06); python_runtime() only records it."""
    try:
        tools = CFG.host_tools()
    except ValueError as error:
        raise AssertionError(str(error))
    return dict(host=CFG.HOST, tools=tools)


def python_runtime():
    """Recorded, never compared: the interpreter this step ran on (2.5.5 preparation: 3.15.0rc3)."""
    return dict(version=sys.version, executable=str(Path(sys.executable).resolve()))


def e3_inputs(pre_dir):
    """The projected product IDE world of a preflight directory and the ide image it emitted."""
    suite = pre_dir / 'emission/ide/suite.json'          # the suite the image was emitted from
    blob = pre_dir / 'emission/ide/ide.blob.bin'
    manifest = load(pre_dir / 'emission/ide/ide.manifest.json')
    assert Path(manifest['suite']).resolve() == suite.resolve(), 'emitted ide image names another suite'
    assert suite.read_bytes() == (pre_dir / 'projection/ide/suite.json').read_bytes(), \
        'emitted ide suite is not the projected product world'
    assert any(Path(s).resolve().is_relative_to((pre_dir / 'projection/ide/sources').resolve())
               for s in load(suite)['sources']), 'ide world has no projected source'
    assert Path(manifest['blob']).resolve() == blob.resolve()
    return suite, blob


def e3_check(receipt, blob):
    """A stored E3 receipt must hold on its own data: PASS, discriminating, bound to the pinned ide image."""
    assert receipt['status'] == 'PASS' and not receipt['problems'], ('product-world E3 check', receipt['problems'])
    assert E3P.verdict(receipt['runs'], receipt['object_deltas']) == [], 'stored E3 runs do not satisfy the verdict'
    # 2.5.5 (c255_e3_product): the receipt must carry the three rules of the corrected tool, and both tool files.
    assert receipt['rules']['control_min_share'] == E3P.CONTROL_MIN_SHARE and receipt['rules']['regression_point'] == E3P.REGRESSION
    assert receipt['tool']['sha256'] == sha(Path(E3P.__file__).read_bytes()) and \
        receipt['base_tool']['sha256'] == sha(Path(E3BASE.__file__).read_bytes()), 'E3 receipt was made by other tool bytes'
    for name, totals in receipt['totals'].items():
        world = name.split(':')[0]
        assert world != 'A' or (totals['total_violations'] == 0 and totals['references_independent_equal']), ('E3 product world', name)
        assert world != 'noA' or all(t['violations'] >= E3P.CONTROL_MIN_SHARE * t['points'] > 0 for t in totals['by_shape'].values()), \
            ('E3 control without the publication does not fail in every shape', name)
    identity = receipt['world_identity']
    want = tuple(CFG.E3_PROOF_IDE_BLOB)
    assert identity['equal'] and (identity['world_blob_sha256'], identity['world_blob_bytes']) == want, \
        ('E3 harness world is not the pinned ide image (D-E3)', identity)
    assert (identity['emitted']['sha256'], identity['emitted']['bytes']) == want == (sha(blob.read_bytes()), blob.stat().st_size)
    assert CFG.CANDIDATE_BLOBS is not None and tuple(CFG.CANDIDATE_BLOBS['ide']) == want
    return receipt


def e3_reduced(pre_dir):
    """Mandatory preflight stage (D-E3): reduced but discriminating product-world E3 sweep."""
    suite, blob = e3_inputs(pre_dir)
    result = E3P.run(suite, pre_dir / 'e3', mode='reduced', emitted_blob=blob, seams=CFG.E3_PUBLICATION_SEAMS)
    save(pre_dir / 'e3/receipt.json', result)
    e3_check(result, blob)
    assert result['mode'] == 'reduced'
    print('product-world E3 (reduced sweep, both controls fail): PASS', flush=True)
    return dict(status='PASS', mode='reduced', receipt=bind(pre_dir / 'e3/receipt.json'), totals=result['totals'],
                world_identity=result['world_identity'], seconds=result['seconds'])


def e3(out):
    """Exhaustive product-world E3 sweep on the PREFLIGHT's projected IDE world (write-once, receipt-producing).
    Host only: no compile, no link, no media action.  rehearse and seed require its PASS receipt."""
    pre = verify_preflight()
    tests = load(SELFTEST / 'receipt.json')
    assert tests['status'] == 'PASS' and tests['tools'] == tool_identity(), 'tool bytes changed since selftest'
    assert tests['host'] == host_identity(), 'host tools changed since selftest'
    assert CFG.same_authority(pre['source_revision'], source_revision()), 'authority or consumed roots moved since preflight'
    assert out == ROOT / CFG.E3, 'the exhaustive E3 step has one configured name'
    assert not out.exists(), 'E3 directory is write-once'
    out.mkdir(parents=True)
    save(out / 'attempt.json', dict(status='STARTED', tools=tool_identity(), host=host_identity(), authority=source_revision(),
                                    preflight=bind(PREFLIGHT / 'receipt.json')))
    suite, blob = e3_inputs(PREFLIGHT)
    result = E3P.run(suite, out, mode='exhaustive', emitted_blob=blob, seams=CFG.E3_PUBLICATION_SEAMS)
    result.update(tools=tool_identity(), host=host_identity(), preflight=bind(PREFLIGHT / 'receipt.json'),
                  authority=source_revision(), native_links=0, media_transactions=0)
    save(out / 'receipt.json', result)
    e3_check(result, blob)
    assert result['mode'] == 'exhaustive'
    return dict(status='PASS', mode='exhaustive', totals=result['totals'], world_identity=result['world_identity'],
                seconds=result['seconds'])


def require_e3(pre):
    """Seed / rehearsal entry check (D-E3): the exhaustive product-world E3 receipt of THIS preflight and THESE tools."""
    assert pre.get('e3', {}).get('status') == 'PASS', 'preflight carries no product-world E3 stage'
    checked(pre['e3']['receipt'])
    _suite, blob = e3_inputs(PREFLIGHT)
    e3_check(load(PREFLIGHT / 'e3/receipt.json'), blob)
    path = ROOT / CFG.E3 / 'receipt.json'
    assert path.is_file(), 'exhaustive product-world E3 receipt missing: run `c255_seed_producer.py e3` after the preflight'
    receipt = load(path)
    assert receipt['mode'] == 'exhaustive', 'E3 receipt is not the exhaustive sweep'
    assert receipt['tools'] == tool_identity(), 'tool bytes changed since the E3 sweep'
    assert receipt['host'] == host_identity(), 'host tools changed since the E3 sweep'
    assert receipt['preflight'] == bind(PREFLIGHT / 'receipt.json'), 'E3 sweep ran against another preflight'
    assert CFG.same_authority(receipt['authority'], source_revision()), 'authority moved since the E3 sweep'
    suite, _blob = e3_inputs(PREFLIGHT)
    assert Path(receipt['suite']['path']).resolve() == suite.resolve() and receipt['suite']['sha256'] == sha(suite.read_bytes()), \
        'E3 sweep ran on another suite'
    for row in receipt['worlds']['A']['sources']:
        assert sha(Path(row['path']).read_bytes()) == row['sha256'], ('E3 world source drift', row['path'])
    e3_check(receipt, blob)
    return bind(path)


def source_revision():
    """Git identity read without any Git command; must match the pinned authority (c255_config)."""
    return CFG.authority_head(strict=True)


def predecessor():
    previous = load(BASE / 'complete.json')
    assert previous['status'] == 'PASS'
    for row in previous['receipts']:
        checked(row)
    medium, native = checked(previous['medium']), checked(previous['ELF'])
    assert sha(medium) == CFG.BASE_MEDIUM_SHA and sha(native) == CFG.BASE_ELF_SHA
    # 2.5.5: the 2.5.4 Seed is two directories (receipts r1b, link attempt r1); both must be the pinned ones.
    problems = CFG.baseline_link_problems()
    assert not problems, ('2.5.4 baseline (link attempt / continuation / Final seal)', problems)
    assert Path(previous['medium']['path']).parts[:2] == Path(CFG.BASE).parts and \
        Path(previous['ELF']['path']).parts[:2] == Path(CFG.BASE).parts, 'baseline receipt names another directory'
    D.validate_bam(medium)
    assert len(D.visible_files(medium)) == 20
    return previous, medium


def package_specs():
    """The six L65S packages exactly as the 2.5.4 Seed delivered them (frozen manifests, locators)."""
    rows = copy.deepcopy(load(FROZEN_MEDIA / 'runtime-receipt.json')['packages'])
    assert [r['name'] for r in rows] == list(CFG.PACKAGE_NAMES)
    for row in rows:
        checked(row['manifest'])
        for key in ('artifact', 'row', 'baseline', 'candidate', 'code', 'metadata', 'mode', 'moved_index_fields'):
            row.pop(key, None)
    return rows

ROLE = {'stdlib-p0': 'stdlib'}
SUITE_NAME = {'stdlib-p0': 'p0-stdlib-einsuite-core-workbench-subset.json', 'ide': 'p0-ide-core-lib.json',
              'idex': 'p0-ide-extra-lib.json', 'm65d': 'p0-m65d-lib.json'}


def role(key):
    return ROLE.get(key, key)


def entry_code(image, entry):
    """Object bytes with literal-patch slots zeroed (offsets are layout, not code)."""
    blob, m = image.code, image.manifest
    start = entry['blob_offset']
    raw = bytearray(blob[start:start + entry['length']])
    for patch in m.get('literal_patches', []):
        at = patch['blob_offset'] - start
        if 0 <= at < len(raw):
            raw[at:at + 2] = b'\0\0'
    return bytes(raw)


def classify_images(old_images, new_images, expect_changed, expect_exact):
    """Per static image: EXACT or CHANGED, with entry-level names; fail closed."""
    assert set(expect_changed) | set(expect_exact) == set(KEYS) and not set(expect_changed) & set(expect_exact)
    rows = {}
    for key, a, b in zip(KEYS, old_images, new_images, strict=True):
        image_budget(a); image_budget(b)
        ea = {e['name']: e for e in a.manifest['entries']}
        eb = {e['name']: e for e in b.manifest['entries']}
        added, removed = sorted(eb.keys() - ea.keys()), sorted(ea.keys() - eb.keys())
        changed = sorted(n for n in ea.keys() & eb.keys() if entry_code(a, ea[n]) != entry_code(b, eb[n]))
        exact = a.code == b.code and a.metadata == b.metadata
        # ENTRY-EXACT: same names/order/lengths and identical object bytes once literal-patch
        # slots are zeroed.  2.5.3 adds a resident object, which shifts literal tables of later
        # objects (see card-253-gates-r7 item 1); that is layout, not code.  Reported separately.
        entry_exact = (not exact and list(ea) == list(eb) and len(a.code) == len(b.code) and not changed and
                       all(ea[n]['length'] == eb[n]['length'] for n in ea))
        assert not any(not n.startswith('%') for n in removed), ('public name removed', key, removed)
        assert max(e['length'] for e in b.manifest['entries']) <= 255, ('256-byte object', key)
        rows[key] = dict(state='EXACT' if exact else 'ENTRY-EXACT' if entry_exact else 'CHANGED', code_before=len(a.code), code_after=len(b.code),
                         delta=len(b.code) - len(a.code), metadata_before=len(a.metadata),
                         metadata_after=len(b.metadata), entries_before=len(ea), entries_after=len(eb),
                         added=added, removed=removed, changed=changed, symbols_added=sorted(symbols(b.manifest) - symbols(a.manifest)))
        if key in expect_exact:
            assert rows[key]['state'] != 'CHANGED', ('image expected unchanged but differs: ' + key, rows[key])
        else:
            assert rows[key]['state'] == 'CHANGED', ('image expected CHANGED but is ' + rows[key]['state'] + ': ' + key)
    return rows


def image_rule(key, row):
    """2.5.5: an image expected EXACT is byte-exact (code and metadata), and no image gains or loses an object."""
    if CFG.EXACT_IS_BYTE_EXACT and key in CFG.EXPECT_EXACT:
        assert row['state'] == 'EXACT', ('image expected byte-EXACT against 2.5.4 but is ' + row['state'], key)
    if CFG.OBJECT_POPULATION_FROZEN:
        assert not row['added'] and not row['removed'] and row['entries_before'] == row['entries_after'], \
            ('object population changed', key, row['added'], row['removed'])


def price_images(old_images, new_images, touched=None):
    rows = classify_images(old_images, new_images, CFG.EXPECT_CHANGED, CFG.EXPECT_EXACT)
    # Attribution: in a projected world only objects defined in a projected source may differ,
    # and the added/removed names are exactly the projected defun population change.
    for key, names in (touched or {}).items():
        row = rows[key]
        assert set(row['changed']) <= names and set(row['added']) <= names, (
            'object change outside projected sources', key, sorted(set(row['changed']) - names))
        row['attribution'] = 'changed/added objects all defined in projected sources'
    for key, row in rows.items():
        lo, hi = CFG.IMAGE_DELTA_WINDOW[key]
        assert lo <= row['delta'] <= hi, ('image code delta outside the card window', key, row['delta'])
        image_rule(key, row)
    total = sum(r['delta'] for r in rows.values())
    return dict(status='PASS', images=rows, total_code_delta=total,
                expect_changed=list(CFG.EXPECT_CHANGED), expect_exact=list(CFG.EXPECT_EXACT))


ROUTE_NOTE = ('2.5.5 product projection (c255_config.PROJECTIONS) onto the 2.5.4 product worlds '
              '(build/card-254-preflight-r1/emission/<key>/suite.json): ide = ide-buffer / ide-keymap-generated / '
              'ide-ui (ide-ui with the two reviewed L2 PRODUCT_SEAMS); stdlib-p0 and lcc = the 2.5.4 worlds unchanged; '
              'm65d = r8 closure suite; idex = closure suite; buffer = tests/bytecode/libs/p0-buffer-lib.json; '
              'all against the projected resident, emitted in-process (base 0) into the preflight directory only')


def write_suite(path, suite):
    """Key order is semantic (disk_files = directory order): never sort_keys (rehearsal r3 HALT)."""
    once(path, json.dumps({k: v for k, v in suite.items() if not k.startswith('_')}, indent=2) + '\n')
    return path


def emit_suite(out, key, suite):
    out.mkdir(parents=True)  # first key creates out/emission (rehearsal r1 HALT)
    path = write_suite(out / 'suite.json', suite)
    suite = P._read_suite(str(path))
    P.emit_artifacts(str(path), suite, str(out / key), base_addr=0, artifact_role=role(key) if key == 'stdlib-p0' else 'disk-lib')
    return out / (key + '.manifest.json')


def lib_text(commit, rel):
    """lib/ text at BASE (era cache) or at the authority (working tree == authority, verified)."""
    if commit == CFG.BASE_AUTHORITY:
        return CFG.era_blob(commit, rel).decode()
    assert commit == CFG.authority_label()
    return (ROOT / rel).read_text()


def project_text(hist, old, new, label, seams=()):
    """Carry the BASE->authority change of one lib file onto a product-world copy.  Whole file when
    the copy is exactly T(old); else grouped diff hunks (3 lines context) whose old text occurs exactly
    once in the copy (seam count 1).  T in (identity, codemod rewrite_tokens).  A hunk that does not occur
    exactly once needs a reviewed product seam (c255_config.PRODUCT_SEAMS) bound to that hunk by the sha256
    of its (old, new) text: 'skip', or 'replace' product_old (count 1) by product_new.  Every seam must be
    consumed by exactly one hunk.  Fail closed."""
    import difflib
    transforms = (('identity', lambda x: x), ('rewrite_tokens', lambda x: CODEMOD.rewrite_tokens(x)[0]))
    for name, T in transforms:
        if hist == T(old):
            assert not seams, ('product seam declared for a whole-file projection', label)
            return T(new), dict(label=label, transform=name, mode='whole-file')
    misses = []
    for name, T in transforms:
        o, n = T(old).splitlines(True), T(new).splitlines(True)
        text, hunks, used, ok = hist, [], set(), True
        for group in difflib.SequenceMatcher(None, o, n, autojunk=False).get_grouped_opcodes(3):
            i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
            seg_o, seg_n = ''.join(o[i1:i2]), ''.join(n[j1:j2])
            digest = sha((seg_o + '\0' + seg_n).encode())
            count = text.count(seg_o)
            row = dict(old_lines=[i1 + 1, i2], new_lines=[j1 + 1, j2], count=count, lib_hunk_sha256=digest)
            hunks.append(row)
            if count == 1:
                text = text.replace(seg_o, seg_n)
                continue
            index = [i for i, s in enumerate(seams) if s['lib_hunk_sha256'] == digest and i not in used]
            if len(index) != 1:
                ok = False
                continue
            seam = seams[index[0]]; used.add(index[0])
            row.update(product_seam=seam['lib_hunk'], action=seam['action'])
            if seam['action'] == 'replace':
                row['product_count'] = text.count(seam['product_old'])
                if row['product_count'] != 1:
                    ok = False
                    continue
                text = text.replace(seam['product_old'], seam['product_new'])
            else:
                assert seam['action'] == 'skip' and seam['reason'], ('product seam action', label)
        if hunks and ok and len(used) == len(seams):
            return text, dict(label=label, transform=name, mode='hunks', hunks=hunks, product_seams=len(used))
        misses.append((name, hunks, sorted(set(range(len(seams))) - used)))
    raise AssertionError(('projection seam (count != 1, no reviewed product seam, or stale seam)', label, misses))

def edit_list(values, old, new, label):
    if old is None:
        assert not set(new) & set(values), ('append collision', label)
        return values + list(new)
    hits = [i for i in range(len(values) - len(old) + 1) if values[i:i + len(old)] == old]
    assert len(hits) == 1, ('suite list seam', label, old, len(hits))
    return values[:hits[0]] + list(new) + values[hits[0] + len(old):]


def defuns(text):
    return set(re.findall(r'^\(def(?:un|macro) (\S+)', text, re.M))


def anchored(suite, frozen_suite_path):
    """Pin relative sources of a frozen world to the immutable release tree that holds its suite.
    The v112 compiler suite names `build/post-promotion/...` relative to the v1.5.0 public build
    root; the same relative path under the repository root is a later, rebuildable tree."""
    frozen_suite_path = Path(frozen_suite_path).resolve()
    worlds = [d for d in frozen_suite_path.parents if d.is_relative_to(ROOT / 'build') and d != ROOT / 'build']
    mapping = {}
    for source in suite.get('sources', []) + list(suite.get('definition_source_overrides', {}).values()):
        if Path(source).is_absolute() or source in mapping:
            continue
        homes = [d for d in worlds if (d / source).is_file()]
        if homes:
            mapping[source] = str(homes[0] / source)
        # else: repository-relative (lib/..., or a frozen build/<attempt>/ path); bound in inputs.json
    suite = dict(suite, sources=[mapping.get(s, s) for s in suite['sources']])
    if 'definition_source_overrides' in suite:
        suite['definition_source_overrides'] = {k: mapping.get(v, v) for k, v in suite['definition_source_overrides'].items()}
    return suite, mapping


def project_world(out, key, frozen_suite_path, residents):
    """Projected suite for one frozen product world.  Returns (suite path, receipt row)."""
    suite = {k: v for k, v in P._read_suite(str(frozen_suite_path)).items() if not k.startswith('_')}
    suite, homes = anchored(suite, frozen_suite_path)
    mapping = CFG.PROJECTIONS.get(key, {})
    names = [Path(s).name for s in suite['sources']]
    assert set(mapping) <= set(names) and all(names.count(n) == 1 for n in mapping), ('projection map', key, names)
    rows, touched = [], set()
    sources = []
    for source in suite['sources']:
        lib = mapping.get(Path(source).name)
        if lib is None:
            sources.append(source); continue
        old, new = lib_text(CFG.BASE_AUTHORITY, lib), lib_text(CFG.authority_label(), lib)
        assert old != new, ('projected lib file did not change', key, lib)
        text, info = project_text((ROOT / source).read_text(), old, new, key + ':' + lib, CFG.product_seams(key, lib))
        target = out / 'sources' / Path(source).name
        once(target, text)
        added, removed = defuns(new) - defuns(old), defuns(old) - defuns(new)
        assert defuns(text) == (defuns((ROOT / source).read_text()) - removed) | added, ('defun population', key, lib)
        touched |= defuns(text)
        rows.append(dict(info, frozen=bind(ROOT / source), projected=bind(target), lib=lib,
                         defuns_added=sorted(added), defuns_removed=sorted(removed)))
        sources.append(str(target))
    moved = {old: new for old, new in zip(suite['sources'], sources) if old != new}
    suite['sources'] = sources
    if 'definition_source_overrides' in suite:
        # Overrides name a source path; follow the projected copy (v112 lcc-profile overrides).
        suite['definition_source_overrides'] = {k: moved.get(v, v) for k, v in suite['definition_source_overrides'].items()}
    for k, field, old, new in CFG.SUITE_EDITS:
        if k == key:
            suite[field] = edit_list(suite[field], old, new, (key, field))
    if key == 'ide':
        a = json.loads(CFG.era_blob(CFG.BASE_AUTHORITY, CFG.IDE_CASE_SOURCE)); b = load(ROOT / CFG.IDE_CASE_SOURCE)
        assert suite['disk_files'] == a['disk_files'], 'ide disk_files not the BASE form'
        suite['disk_files'] = b['disk_files']
        old_cases, new_cases = {c['name']: c for c in a['cases']}, {c['name']: c for c in b['cases']}
        moved = [c['name'] for c in suite['cases'] if old_cases.get(c['name']) == c and new_cases.get(c['name']) != c]
        assert all(n in new_cases for n in moved)
        suite['cases'] = [new_cases[c['name']] if c['name'] in moved else c for c in suite['cases']]
        rows.append(dict(label='ide:cases', replaced=moved, disk_files='BASE -> authority form'))
    for field in ('resident_suite', 'resident_suites'):
        suite.pop(field, None)
    suite.update(residents)
    path = write_suite(out / 'suite.json', suite)
    return path, dict(key=key, frozen_suite=bind(frozen_suite_path), suite=bind(path), projections=rows,
                      anchored_sources=homes, touched_defuns=sorted(touched))


@contextmanager
def base_era():
    """BASE_AUTHORITY host-source era from the primed cache (no git under the audit hook)."""
    import evidence_era as E
    saved = E.era_blob
    E.era_blob = CFG.era_blob
    try:
        with E.host_source_world(CFG.BASE_AUTHORITY, CFG.ERA_EXTRA_PATHS) as reads:
            yield reads
    finally:
        E.era_blob = saved


def emit_candidates(out, closure_receipt):
    """Emit the six static images (2.5.5 projection onto the 2.5.4 product worlds); never writes outside out/."""
    frozen = load(FROZEN_PLANE / 'product/substitution-artifacts.json')['manifests']
    fm = {k: load(ROOT / r['path']) for k, r in zip(KEYS, frozen, strict=True)}
    S0, M0 = Path(fm['stdlib-p0']['suite']), Path(fm['m65d']['suite'])
    lib_changed = set(CFG.CHANGED_LIB or ())
    assert sorted(lib_changed) == CFG.routed_lib(), ('changed lib files not all routed', sorted(lib_changed ^ set(CFG.routed_lib())))
    assert M0.is_file()
    # 1. Baseline control: all six 2.5.4 product worlds exactly as the 2.5.4 preflight emitted them (their
    #    resident references already name the 2.5.4 projected resident), BASE era, byte-exact.
    base_rows = {}
    with base_era() as reads:
        for key in KEYS:
            suite = {k: v for k, v in P._read_suite(fm[key]['suite']).items() if not k.startswith('_')}
            assert Path(fm[key]['suite']).resolve().is_relative_to(ROOT / CFG.BASE_PREFLIGHT), ('baseline world', key)
            suite, homes = anchored(suite, fm[key]['suite'])
            manifest = emit_suite(out / 'baseline-emission' / key, key, suite)
            a = F.emit_image(key, role(key), ROOT / frozen[KEYS.index(key)]['path'])
            b = F.emit_image(key, role(key), manifest)
            assert a.code == b.code and a.metadata == b.metadata, ('baseline emission replay', key)
            base_rows[key] = dict(frozen_suite=fm[key]['suite'], manifest=bind(manifest), exact=True, anchored_sources=homes)
            print('baseline emission replay EXACT: ' + key, flush=True)
        era_reads = dict(reads)
    save(out / 'baseline-emission.json', dict(status='PASS', era=CFG.BASE_AUTHORITY, rows=base_rows,
                                              era_reads=era_reads))
    # 2. Candidate worlds.
    work = out / 'projection'
    s1, srow = project_world(work / 'stdlib-p0', 'stdlib-p0', S0, {})
    m1 = {k: v for k, v in P._read_suite(str(out / 'closure/suites/p0-m65d-lib.json')).items() if not k.startswith('_')}
    assert m1['sources'] and all((ROOT / s).resolve().is_relative_to(out / 'closure') for s in m1['sources'])
    m1.pop('resident_suites', None); m1['resident_suite'] = str(s1)
    m1p = write_suite(work / 'm65d/suite.json', m1)
    i1, irow = project_world(work / 'ide', 'ide', Path(fm['ide']['suite']), dict(resident_suites=[str(s1), str(m1p)]))
    l1, lrow = project_world(work / 'lcc', 'lcc', Path(fm['lcc']['suite']), dict(resident_suite=str(s1)))
    idex = {k: v for k, v in P._read_suite(str(out / 'closure/suites/p0-ide-extra-lib.json')).items() if not k.startswith('_')}
    refs = [ROOT / r for r in P._as_list(idex.get('resident_suite')) + P._as_list(idex.get('resident_suites'))]
    assert refs and all(r.resolve().is_relative_to(out / 'closure/suites') for r in refs), ('idex resident', refs)
    buffer = {k: v for k, v in P._read_suite(str(ROOT / CFG.BUFFER_SUITE)).items() if not k.startswith('_')}
    assert not buffer.get('resident_suites') and Path(buffer['resident_suite']).name == 'p0-stdlib-einsuite-core-workbench-subset.json'
    buffer['resident_suite'] = str(s1)
    suites = {'stdlib-p0': load(s1), 'ide': load(i1), 'idex': idex, 'm65d': m1, 'buffer': buffer, 'lcc': load(l1)}
    manifests = [emit_suite(out / 'emission' / key, key, suites[key]) for key in KEYS]
    for path in manifests:
        assert not any(Path(s).resolve().is_relative_to(ROOT / 'build/bytecode') for s in load(path).get('sources', [])), \
            ('mutable build/bytecode source', path)
    save(out / 'emission-routes.json', dict(routes={'stdlib-p0': srow, 'ide': irow, 'lcc': lrow,
        'm65d': dict(route='closure:p0-m65d-lib.json (r8 closure config, lib/m65-disk.lisp unchanged)', suite=bind(m1p)),
        'idex': dict(route='closure:p0-ide-extra-lib.json'), 'buffer': dict(route=CFG.BUFFER_SUITE)},
        note=ROUTE_NOTE, closure=bind(closure_receipt), changed_lib=sorted(lib_changed)))
    touched = {'stdlib-p0': set(srow['touched_defuns']), 'ide': set(irow['touched_defuns']),
               'lcc': set(lrow['touched_defuns'])}
    return manifests, touched


def delivery_control(out, files):
    proof = {}
    for name in STATIC:
        raw = (out / name).read_bytes()
        assert raw == (FROZEN_PLANE / name).read_bytes(), ('baseline reproduction', name)
        delivered = files[name.encode()]
        if name == 'CODE.BIN':
            assert delivered[:len(raw)] == raw
        elif name == 'C2D.BIN':
            assert len(delivered) == CFG.C2D_DELIVERED_BYTES
            assert delivered == raw + bytes(len(delivered) - len(raw))
        else:
            assert delivered == raw
        proof[name] = dict(reproduced=bind(out / name), delivered_bytes=len(delivered),
                           delivered_sha256=sha(delivered))
    return proof


def symbol_capacity(commands, manifests):
    """Conservative name/namepool use: static native + six static + six package images."""
    import mvp_vm_stdlib_boot_budget as B
    names, inputs = set(), []
    for command in commands:
        if '-c' in command and command[command.index('-c') + 1].endswith('.c'):
            path = ROOT / command[command.index('-c') + 1]
            active = set(B.d_flags(' '.join(command))) | {'__MEGA65__'}
            native, _, _ = B.native_symbols_from_sources([path], active)
            names.update(native); inputs.append(bind(path))
    for path in manifests:
        entries, literals = B.manifest_symbols(load(path))
        names.update(entries | literals); inputs.append(bind(path))
    used = dict(symbols=len(names), namepool=B.namepool_bytes(names))
    assert CFG.SYMBOL_LIMITS['symbols'] - used['symbols'] >= CFG.SYMBOL_MARGIN['symbols'], 'symbol headroom'
    assert CFG.SYMBOL_LIMITS['namepool'] - used['namepool'] >= CFG.SYMBOL_MARGIN['namepool'], 'namepool headroom'
    return dict(status='PASS', used=used, limits=CFG.SYMBOL_LIMITS, names=sorted(names), inputs=inputs,
                scope='static native + six static + six package images; target session floor stays a reviewer gate')


def capacity(product, geometry, records, old_geometry, all_manifests):
    used = {k: base + sum(r['row'][field] for r in records) for k, field, base in [
        ('code', 'bank2', geometry['code_bytes']), ('entries', 'entries', product['entries']),
        ('resolutions', 'resolutions', product['resolutions']), ('roots', 'roots', product['roots']), ('images', 'images', 6)]}
    assert all(used[k] <= CFG.LIMITS[k] for k in used), ('capacity exceeded', used)
    headroom = {k: CFG.LIMITS[k] - used[k] for k in used}
    assert all(headroom[k] >= CFG.HEADROOM[k] for k in used), ('capacity headroom below the reviewed floor', headroom)
    scratch = sum(r['row']['scratch'] for r in records)
    frozen = load(BASE / 'capacity.json')
    assert frozen['entry_scratch_sum'] <= scratch <= frozen['entry_scratch_limit'], ('entry scratch', scratch)
    commands = load(FROZEN_NATIVE / 'command-proof.json')['commands']
    syms = symbol_capacity(commands, all_manifests)
    known = set(frozen['symbols']['names'])
    return dict(status='PASS', used=used, limits=CFG.LIMITS, headroom=headroom, headroom_floor=CFG.HEADROOM,
                entry_scratch_sum=scratch, entry_scratch_growth=scratch - frozen['entry_scratch_sum'],
                new_symbols=sorted(set(syms['names']) - known), retired_symbols=sorted(known - set(syms['names'])),
                entry_scratch_limit=frozen['entry_scratch_limit'], symbols=syms,
                before_used=frozen['used'],
                growth={k: used[k] - frozen['used'][k] for k in used})


def report(out, result=None, error=None):
    if error:
        text = ('# 2.5.5 Seed preflight (Chunk A)\n\n**HALT**. No native link and no media action ran.\n\n'
                'Baseline reproduction: ' + ('PASS' if (out / 'baseline-reproduction.json').exists() else 'FAIL / incomplete')
                + '.\n\nError: `' + repr(error) + '`\n\nThe attempt directory is retained; continuing needs a new ATTEMPT tag in '
                'c255_config.py and a reviewed successor.\n')
    else:
        c, p = result['constants'], result['price']
        text = ('# 2.5.5 Seed preflight (Chunk A)\n\nBaseline reproduction PASS (3 static files against the 2.5.4 delivery, '
                '6 package loaders byte-exact; no package is re-emitted in 2.5.5).\n\n'
                + ''.join(f"- `{k}`: {v['state']}, code {v['code_before']} -> {v['code_after']} ({v['delta']:+d}), "
                          f"added {len(v['added'])}, removed {len(v['removed'])}, changed {len(v['changed'])}\n"
                          for k, v in p['images'].items())
                + f"\nTotal static code delta {p['total_code_delta']:+d} B; new static build id "
                  f"`{c['LISP65_C2_PRODUCT_BUILD_ID']}`.\n\n| Constant | Value |\n| --- | --- |\n"
                + ''.join(f'| `{k}` | `{c[k]}` |\n' for k in ('LISP65_C2_PRODUCT_BUILD_ID', 'LISP65_C2_PRODUCT_SHELF_BYTES',
                                                               'LISP65_C2_LITE_STATIC_CODE_BYTES'))
                + f"\nCapacity code {result['capacity']['used']['code']}/{CFG.LIMITS['code']}.\n\n"
                  'Chunk C (Seed), reviewer release only:\n\n```sh\n' + CHUNK_C + '\n```\n\n'
                  'No Seed/target PASS is claimed.  Authority: ' + result['source_revision']['observed'] + '\n')
    if result and 'selftest' in result:
        text += '\nSelftest: PASS, ' + str(result['negative_controls']) + ' negative controls.\n'
    once(out / 'report.md', text)


def preflight(out=PREFLIGHT):
    assert not out.exists(), 'preflight is write-once; choose an explicitly named successor (new ATTEMPT)'
    out.mkdir(parents=True)
    save(out / 'attempt.json', dict(status='STARTED', tools=tool_identity(), host=host_identity(), native_links=0))
    try:
        revision = source_revision()
        previous, medium = predecessor()
        files = D.visible_files(medium)
        frozen = load(FROZEN_PLANE / 'product/substitution-artifacts.json')
        for row in frozen['manifests']:
            checked(row)
        old_manifests = [ROOT / r['path'] for r in frozen['manifests']]
        assert frozen['product_build_id_hex'] == CFG.BASE_PRODUCT_BUILD_ID
        # Product route (mk/workbench-service-inventory.mk V2_WORKBENCH_CODEMOD_TOOL): the dated r8
        # closure, whose m65d source suite is the D2-D5 r8 suite, emitted as suites/p0-m65d-lib.json.
        assert CODEMOD_R8.__name__ == CFG.CODEMOD_TOOL
        assert CODEMOD_R8.CLOSURE == ROOT / CFG.CLOSURE_CONFIG
        assert load(ROOT / CFG.CLOSURE_CONFIG)['artifacts'][3]['source_suite'] == CFG.M65D_SOURCE_SUITE
        closure = CODEMOD_R8.generate(ROOT / CFG.CLOSURE_CONFIG, out / 'closure')
        load_entry_emitter(out)
        before, old_geometry, old_images = plane(out / 'planes/baseline', old_manifests)
        assert before['product_build_id_hex'] == CFG.BASE_PRODUCT_BUILD_ID
        assert old_geometry['code_bytes'] == CFG.BASE_STATIC_CODE_BYTES
        static_proof = delivery_control(out / 'planes/baseline', files)
        baseline_packages, _ = packages(out / 'baseline-package-replay', files, before['product_build_id_u32'],
                                        before['product_build_id_u32'], reemit=False)
        save(out / 'baseline-reproduction.json', dict(status='PASS', static=static_proof, packages=baseline_packages,
                                                      predecessor=bind(BASE / 'complete.json')))
        print('baseline static plane and all six package loaders: PASS', flush=True)
        new_manifests, touched = emit_candidates(out, closure)
        # The candidate images must be exactly the reviewed ones (lcc = the ladder-gate image).  Unpinned
        # (None) is allowed in dry mode only: the dry preflight is what produces the values to pin.
        blobs = {key: Path(load(m)['blob']) for key, m in zip(KEYS, new_manifests, strict=True)}
        got = {key: (sha(b.read_bytes()), b.stat().st_size) for key, b in blobs.items()}
        save(out / 'candidate-blobs.json', {k: list(v) for k, v in got.items()})
        if CFG.CANDIDATE_BLOBS is None:
            assert CFG.DRY, 'CANDIDATE_BLOBS not pinned (set from the dry preflight, then use a new ATTEMPT)'
        else:
            assert got == CFG.CANDIDATE_BLOBS, ('candidate image drift', {k: got[k] for k in got if got[k] != CFG.CANDIDATE_BLOBS[k]})
        # D-E3 (mandatory): the product-world E3 check on the projected IDE sources of THIS preflight.
        assert tuple(got['ide']) == tuple(CFG.E3_PROOF_IDE_BLOB), ('ide image is not the E3 proof image', got['ide'])
        e3_stage = e3_reduced(out)
        after, geometry, new_images = plane(out / 'planes/candidate', new_manifests)
        assert CFG.CANDIDATE_STATIC_CODE_BYTES in (None if CFG.DRY else geometry['code_bytes'], geometry['code_bytes']), \
            ('static code bytes', geometry['code_bytes'])
        assert after['product_build_id_u32'] != before['product_build_id_u32']
        price = price_images(old_images, new_images, touched)
        residents = (Path(load(old_manifests[0])['suite']), out / 'projection/stdlib-p0/suite.json')
        assert residents[0].resolve().is_relative_to(ROOT / CFG.BASE_PREFLIGHT) and residents[1].is_file()
        records, package_index = packages(out / 'packages', files, before['product_build_id_u32'],
                                          after['product_build_id_u32'], residents=residents)
        pkg_got = {r['name']: (r['code']['sha256'], r['code']['bytes']) for r in records if r['mode'] == 'REEMIT'}
        save(out / 'package-blobs.json', {k: list(v) for k, v in pkg_got.items()})
        if CFG.PACKAGE_BLOBS is None:
            assert CFG.DRY, 'PACKAGE_BLOBS not pinned (set from the dry preflight, then use a new ATTEMPT)'
        else:
            assert pkg_got == CFG.PACKAGE_BLOBS, ('re-emitted package drift', pkg_got)
        const = constants(out / 'planes', before, after, old_geometry, geometry)
        all_manifests = new_manifests + [ROOT / r['manifest']['path'] for r in records]
        cap = capacity(after, geometry, records, old_geometry, all_manifests)
        expected_new = sorted(n for names in CFG.PACKAGE_NEW_SYMBOLS.values() for n in names)
        save(out / 'new-symbols.json', dict(new=cap['new_symbols'], retired=cap['retired_symbols'],
                                            package_objects=expected_new))
        assert set(expected_new) <= set(cap['new_symbols']), ('new package objects missing from the symbol set', cap['new_symbols'])
        # 2.5.5: L1-L4 change bodies only; a symbol that appears is a halt (retired symbols are reported).
        assert cap['new_symbols'] == sorted(CFG.NEW_SYMBOLS_EXPECTED), ('unexpected new symbol', cap['new_symbols'])
        deltas = {n: (out / 'planes/candidate' / n).stat().st_size - (out / 'planes/baseline' / n).stat().st_size for n in STATIC}
        # 2.5.5: the static plane SHRINKS; the delta is negative and equals the image price.
        assert deltas['CODE.BIN'] == geometry['code_bytes'] - old_geometry['code_bytes'] == price['total_code_delta'], \
            ('static code delta', deltas, price['total_code_delta'])
        assert old_geometry['code_bytes'] == CFG.BASE_STATIC_CODE_BYTES
        resident_header = out / 'emission/stdlib-p0/stdlib-p0.h'
        assert resident_header.is_file()
        # Native seam rehearsal (in memory; the Seed re-derives and must match exactly).
        base_header, cand_header = native_headers(out)
        census = seam_census(derive_native(const, load(out / 'emission/stdlib-p0/stdlib-p0.manifest.json'),
                                           cand_header, BUILD / 'native', base_header), BUILD / 'native')
        assert census['materialised'] == census['distinct_targets'], 'two native inputs share a target'
        assert all(name != 'BASE_ADDR' for row in census['changed'] for seam in row['seams']
                   for name, *_ in seam.get('counts', [])), 'resident ABI origin moved'
        save(out / 'native-seam-rehearsal.json', census)
        result = dict(status='PASS', source_revision=revision, baseline_reproduction='PASS',
                      predecessor=bind(BASE / 'complete.json'), price=price, capacity=cap, constants=const,
                      packages=records, static_deltas=deltas, native_links=0, media_transactions=0,
                      host_ABI_probe_commands=HOST_HELPER_COMMANDS, chunk_c_command=CHUNK_C, closure=bind(closure),
                      host=host_identity(), python=python_runtime(), host_equivalence=dict(
                          rule='the pinned host tools reproduce the 2.5.4 ELF / LTO object / PRG / D81 byte for byte',
                          records=[bind(ROOT / rel) for rel, _sha in CFG.HOST_EQUIVALENCE.values()],
                          problems=CFG.host_equivalence()),
                      resident_header=bind(resident_header), package_index=package_index,
                      candidate_blobs={k: list(v) for k, v in got.items()}, e3=e3_stage,
                      package_blobs={k: list(v) for k, v in pkg_got.items()},
                      native_sources=dict(rule='identical to 2.5.4 Seed r1 (no source seam); only generated-constant seams move',
                                          unchanged=revision.get('native_unchanged'), base_authority=CFG.BASE_AUTHORITY,
                                          recipe=bind(FROZEN_NATIVE / 'command-proof.json')))
        assert census['seen'].keys() == {'stdlib_header', 'static_plane', 'asserts'}, 'unexpected native seam class'
        assert not result['host_equivalence']['problems'], result['host_equivalence']['problems']
        for name, value in [('price.json', price), ('capacity.json', cap), ('constants.json', const)]:
            save(out / name, value)
        inputs = {Path(__file__).resolve(), Path(CFG.__file__).resolve(), BASE / 'complete.json',
                  FROZEN_PLANE / 'product/substitution-artifacts.json',
                  Path(__file__).resolve().parent / CFG.PRODUCER_TOOL, Path(E3P.__file__).resolve(),
                  Path(E3BASE.__file__).resolve(), ROOT / CFG.ENTRY_EMITTER,
                  *[ROOT / rel for rel, _sha in CFG.HOST_EQUIVALENCE.values()],
                  *[BASE_LINK / name for name, _sha in CFG.BASE_LINK_RECORDS], ROOT / CFG.BASE_FINAL / 'seal.json'}
        sites = Path(__file__).resolve().parent / CFG.SITES_TOOL
        assert sites.is_file(), 'native site table missing'
        inputs.add(sites)
        inputs.update(ROOT / r['path'] for r in load(closure)['inputs'])
        inputs.update(old_manifests); inputs.update(new_manifests)
        # Frozen product worlds: every suite file and source (incl. resident chains) that an emitted
        # baseline or candidate image consumed, so a drifting frozen world cannot pass verify_preflight.
        emitted = list(new_manifests) + sorted((out / 'baseline-emission').glob('*/*.manifest.json'))
        for manifest in emitted:
            top = P._read_suite(load(manifest)['suite'])
            for member in [top] + P._resident_suites(top):
                inputs.add(Path(member['_suite_path']).resolve())
                inputs.update((ROOT / s).resolve() for s in member.get('sources', []))
        for spec in package_specs():
            inputs.add(ROOT / spec['manifest']['path'])
        # Re-emitted packages: sources, suite, resident chain (live files; the baseline side is the era cache).
        consumed_sources = set()
        for name in CFG.PACKAGES_REEMIT:
            inputs.update(ROOT / s for s in CFG.PACKAGE_SOURCES[name])
            inputs.add(ROOT / CFG.PACKAGE_SUITE[name])
            if CFG.PACKAGE_RESIDENT[name] == CFG.PRODUCT_RESIDENT:
                continue                      # both product residents are bound through the emitted manifests
            top = dict(P._read_suite(str(ROOT / CFG.PACKAGE_SUITE[name])), resident_suite=str(ROOT / CFG.PACKAGE_RESIDENT[name]))
            top.pop('resident_suites', None)
            for member in P._resident_suites(top):
                inputs.add(Path(member['_suite_path']).resolve())
                inputs.update((ROOT / s).resolve() for s in member.get('sources', []))
        # No unrouted changed lib file may be a source of any emitted world or package.
        for manifest in emitted:
            top = P._read_suite(load(manifest)['suite'])
            for member in [top] + P._resident_suites(top):
                consumed_sources.update(Path(s).name for s in member.get('sources', []))
        consumed_sources.update(Path(s).name for name in CFG.PACKAGES_REEMIT for s in CFG.PACKAGE_SOURCES[name])
        leaked = sorted(lib for lib in CFG.UNROUTED_LIB if Path(lib).name in consumed_sources)
        assert not leaked, ('a changed lib file declared unrouted is a product source', leaked)
        for path in list(inputs):
            if path.name.endswith('.manifest.json'):
                inputs.add(Path(load(path)['blob']))
        import comfort_default_media as C  # bind deferred native/media helper closure
        inputs.update([F.CONTRACT, F.RECURSIVE, F.SYMBOL, F.SESSION, ROOT / 'src/obj.h',
            ROOT / 'scripts/c2d-v6-entry-host.c', ROOT / 'src/c2d_v6_entry.h',
            C.M.STAGER_S, C.M.STAGER_ROM_S,
            *[C.BASE / 'packed' / n for n in ('delivery-population.json', 'delivery-stager-main.c', 'delivery-roles.h')]])
        for fam in ('boot', 'session'):
            value = load(FROZEN_MEDIA / ('runtime-overlays-' + fam + '-final.json'))
            inputs.add(FROZEN_MEDIA / value['overflow_storage']['file'])
        inputs.add(C.M.ASM_CONTRACT.CONTRACT)
        for module in tuple(sys.modules.values()):
            filename = getattr(module, '__file__', None)
            if filename and Path(filename).resolve().is_relative_to(ROOT / 'tools/host-lisp'):
                inputs.add(Path(filename).resolve())
        commands, native_rows, native_tools = native_inputs()
        save(out / 'native-input-bindings.json', dict(recipe=bind(FROZEN_NATIVE / 'command-proof.json'),
                                                      inputs=native_rows, toolchain=native_tools))
        inputs.update(ROOT / r['path'] for r in native_rows + native_tools)
        inputs.update(Path(p) for p in CFG.HOST_TOOLS)      # /usr/bin/cc, llvm-link, setarch (pinned)
        inputs.update(FROZEN_NATIVE / n for n in ('command-ready.json', 'command-proof.json', 'derived-inputs.json'))
        inputs.update(FROZEN_MEDIA / n for n in ('runtime-receipt.json', 'runtime-overlays-boot-final.json',
                                                 'runtime-overlays-session-final.json', 'kernal-window-publish-last.json'))
        inputs.add(BASE / 'capacity.json')
        for row in load(closure)['inputs']:
            assert sha((ROOT / row['path']).read_bytes()) == row['sha256'], 'source raced closure generation'
        # Mutable generated tree must never be an input (2.5.2 Final r2 lesson).
        assert not any(p.is_relative_to(ROOT / 'build/bytecode') or p.is_relative_to(ROOT / 'build/post-promotion')
                       for p in inputs), 'mutable gate-rebuilt input (build/bytecode, build/post-promotion)'
        save(out / 'inputs.json', [bind(p) for p in sorted(inputs)])
        result['inputs'] = bind(out / 'inputs.json')
        if out == PREFLIGHT:
            tests = load(SELFTEST / 'receipt.json')
            assert tests['status'] == 'PASS' and tests['tools'] == tool_identity(), \
                'selftest ran against different tool bytes (re-run selftest under a new ATTEMPT)'
            assert tests['host'] == host_identity(), 'selftest ran with other host tools'
            assert load(out / 'attempt.json')['tools'] == tool_identity()
            result['selftest'] = bind(SELFTEST / 'receipt.json')
            result['negative_controls'] = len(tests['rejected'])
        result['artifacts'] = [bind(p) for p in sorted(out.rglob('*')) if p.is_file()]
        # No receipt binds a path its own tool still writes: receipt, report and halt record come after this list.
        own = {str((out / n).relative_to(ROOT)) for n in ('receipt.json', 'report.md', 'halt.json')}
        assert not own & {r['path'] for r in result['artifacts']}, 'the receipt would bind a file its own tool still writes'
        save(out / 'receipt.json', result)
        report(out, result)
        return {k: result[k] for k in ('status', 'baseline_reproduction', 'price', 'static_deltas', 'native_links', 'media_transactions')}
    except BaseException as error:
        save(out / 'halt.json', dict(status='HALT', error=repr(error)))
        report(out, error=error)
        raise


def project_delivery_code(delivered, baseline, candidate):
    """CODE.BIN = static code plane | zero fill | native suffix (from 0xee00).  The plane may grow into the zero
    fill or -- 2.5.5 -- SHRINK: the bytes the old plane held beyond the new one return to zero fill, which is what
    a build from nothing writes there (measured on the 2.5.4 medium: zero from the plane end to 0xee00)."""
    assert delivered[:len(baseline)] == baseline, 'wrong static baseline'
    assert 0 < len(candidate) <= CFG.LIMITS['code'], 'wrong static size'
    assert not any(delivered[len(baseline):max(len(baseline), len(candidate))]), 'native suffix overlap'
    result = bytearray(delivered)
    result[:len(candidate)] = candidate
    if len(candidate) < len(baseline):
        result[len(candidate):len(baseline)] = bytes(len(baseline) - len(candidate))
    behind = max(len(baseline), len(candidate))
    assert result[behind:] == delivered[behind:] and len(result) == len(delivered)
    return bytes(result)


# ---------------------------------------------------------------- native seams
def stdlib_header_projection(raw, old_manifest, new_manifest, candidate_header):
    """Adopt the emitted header's `#define LISP65_BYTECODE_STDLIB_*` values (counts, directory
    bytes AND entry indexes can all move when a resident function is added), keeping every other
    byte of the frozen native input.  Seams: (1) the frozen copy must carry the four count
    macros exactly as the frozen r7c manifest implies; (2) both headers define the same macro
    names; (3) after projection the text equals the emitted header modulo the suite comment."""
    def tokens(text):
        return re.sub(r'/\* suite: .*? \*/', '', text)
    pat = re.compile(r'^#define (LISP65_BYTECODE_STDLIB_\w+) (.*)$', re.M)
    old_defs = dict(pat.findall(raw.decode()))
    new_defs = dict(pat.findall(candidate_header))
    assert old_defs.keys() == new_defs.keys(), ('macro population drift', sorted(old_defs.keys() ^ new_defs.keys()))
    frozen = [('BLOB_BYTES', old_manifest['code_bytes'])] + [(m, len(old_manifest[k])) for m, k in
        [('LITERAL_INDEX_COUNT', 'literal_index'), ('LITERAL_NODE_COUNT', 'literal_nodes'), ('LITERAL_PATCH_COUNT', 'literal_patches')]]
    for macro, value in frozen:
        assert old_defs['LISP65_BYTECODE_STDLIB_' + macro] == f'{value}u', ('frozen header not as the baseline manifest', macro)
    moved = sorted(n.removeprefix('LISP65_BYTECODE_STDLIB_') for n in new_defs if old_defs[n] != new_defs[n])
    assert set(moved) <= set(CFG.STDLIB_HEADER_MAY_CHANGE), ('resident header macro moved outside the reviewed set '
                                                             '(an ENTRY index is an immediate of repl)', moved)
    text, changed = raw.decode(), []
    for name, value in new_defs.items():
        if old_defs[name] != value:
            line_old, line_new = f'#define {name} {old_defs[name]}', f'#define {name} {value}'
            assert text.count(line_old) == 1, ('stdlib header seam', name)
            text = text.replace(line_old, line_new)
            changed.append((name.removeprefix('LISP65_BYTECODE_STDLIB_'), old_defs[name], value))
    assert tokens(text) == tokens(candidate_header), 'unclassified stdlib header change'
    return text.encode(), changed


def native_headers(pre_dir):
    """Emitted (base 0) baseline/candidate resident headers, projected to the native Bank-5 ABI
    origin with the established S.native_stdlib_header seam (count 1)."""
    return [S.native_stdlib_header((pre_dir / d / 'stdlib-p0/stdlib-p0.h').read_text())
            for d in ('baseline-emission', 'emission')]


def derive_native(const, new_manifest, candidate_header, here, baseline_header):
    """Pure in-memory derivation of every native input seam (no writes, no process).

    Used by prepare_native (Chunk C, writes the result) AND by preflight as a seam
    rehearsal against the real frozen r7c inputs, so a seam-count miss halts before
    the Seed instead of inside it (2.5.2 r7 lesson)."""
    commands, sources, toolchain = native_inputs()
    base = CFG.BASE_LINK                   # the frozen commands and native inputs name the LINK attempt directory
    assert not any((CFG.BASE + '/') in arg for command in commands for arg in command), 'a frozen command names the continuation directory'
    oldprefix = base + '/native/candidate-inputs'
    oldderived = base + '/native/derived'
    newprefix = str((here / 'candidate-inputs').relative_to(ROOT))
    newderived = str((here / 'derived').relative_to(ROOT))
    # Longest first: the bare Seed prefix must be replaced last.
    path_replacements = {oldprefix: newprefix, oldderived: newderived, base: str(BUILD.relative_to(ROOT))}
    before = const['before_product']
    substitutions = {
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + before['product_build_id_hex'] + 'UL':
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + const['LISP65_C2_PRODUCT_BUILD_ID'] + 'UL',
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(before['artifacts']['shelf']['bytes']) + 'UL':
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(const['LISP65_C2_PRODUCT_SHELF_BYTES']) + 'UL'}
    assert before['product_build_id_hex'] == CFG.BASE_PRODUCT_BUILD_ID
    assert before['artifacts']['shelf']['bytes'] == CFG.BASE_SHELF_BYTES
    assert all(any(k in cmd for cmd in commands) for k in substitutions), 'substitution seam not consumed'

    def rebase(value):
        for a, b in path_replacements.items():
            value = value.replace(a, b)
        return value
    updated = [[rebase(substitutions.get(arg, arg)) for arg in cmd] for cmd in commands]
    derived = []
    table_source = commands[CFG.CRC_TABLE_COMMAND_INDEX][commands[CFG.CRC_TABLE_COMMAND_INDEX].index('-c') + 1]
    assert table_source.endswith('c2-stream-phase-02a.c'), table_source
    # 2.5.5: NO native source seam.  Every compiled source is the 2.5.4 materialised input, byte for byte; the
    # only rows that change are the generated-constant seams below.
    crc_generated = None
    old_code = const['before_geometry']['code_bytes']
    new_code = const['after_geometry']['code_bytes']
    assert old_code == CFG.BASE_STATIC_CODE_BYTES and 0 < new_code <= CFG.LIMITS['code']    # 2.5.5: the plane shrinks
    old_manifest = load(ROOT / load(FROZEN_PLANE / 'product/substitution-artifacts.json')['manifests'][0]['path'])
    seen = dict(stdlib_header=0, static_plane=0, asserts=0)
    for row in sources:
        path = ROOT / row['path']; raw = checked(row); new = raw
        target = ROOT / rebase(row['path'])
        assert target.is_relative_to(here) and target != path
        seams = []
        if row['path'] == table_source:
            text = raw.decode()
            for table in const['crc_tables']:
                def assembly(values):
                    return 'c2_phase02a_' + table['table'] + '_crc16:\\n' + '\\n'.join(f'.short 0x{x:04x}' for x in values) + '\\n'
                old, replacement = assembly(table['before']), assembly(table['after'])
                assert text.count(old) == 1, 'CRC source seam'
                text = text.replace(old, replacement)
                seams.append(dict(kind='CRC16 table', **table))
            new = text.encode(); crc_generated = target
        elif path.name == 'stdlib-p0.h':
            # Control: the BASE-era re-emitted resident header reproduces the frozen native input.
            assert re.sub(r'/\* suite: .*? \*/', '', raw.decode()) == re.sub(r'/\* suite: .*? \*/', '', baseline_header), \
                'frozen stdlib header not reproduced by the baseline emission'
            new, pairs = stdlib_header_projection(raw, old_manifest, new_manifest, candidate_header); seen['stdlib_header'] += 1
            seams.append(dict(kind='resident stdlib counts', counts=pairs))
        elif path.name == 'c2_lite_static_plane.h':
            old = f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {old_code}UL'.encode()
            replacement = f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {new_code}UL'.encode()
            # Historical copies in the input closure carry older plane sizes;
            # only the live definition is rebound.
            assert raw.count(old) in (0, 1)
            if raw.count(old) == 1:
                new = raw.replace(old, replacement); seen['static_plane'] += 1
                seams.append(dict(kind='static code size', before=old.decode(), after=replacement.decode()))
        elif path.name.endswith('.compiler-input-assert.h'):
            old = f'LISP65_C2_LITE_STATIC_CODE_BYTES != {old_code}UL'.encode()
            replacement = f'LISP65_C2_LITE_STATIC_CODE_BYTES != {new_code}UL'.encode()
            assert raw.count(old) in (0, 1)
            if raw.count(old) == 1:
                new = raw.replace(old, replacement); seen['asserts'] += 1
                seams.append(dict(kind='compiler assertion', before=old.decode(), after=replacement.decode()))
        derived.append((row, target, new, seams))
    assert crc_generated is not None
    # Seam census: every stdlib-p0.h copy re-derived; the live static-plane header and at least one
    # assertion header rebound; nothing else (2.5.5 has no native source seam).
    assert seen['stdlib_header'] >= 1 and seen['static_plane'] >= 1, seen
    kinds = {s['kind'] for _, _, _, seams in derived for s in seams}
    assert kinds <= {'CRC16 table', 'resident stdlib counts', 'static code size', 'compiler assertion'}, kinds
    if new_code != old_code:
        assert seen['asserts'] >= 1, seen
    for command in updated:
        output = ROOT / command[command.index('-o') + 1]
        assert output.is_relative_to(BUILD)
        assert not any(x in ' '.join(command).lower() for x in ('xemu', 'ssh ', 'curl ', 'wget ', 'make '))
    return dict(commands=updated, toolchain=toolchain, derived=derived, seen=seen, substitutions=substitutions,
                path_replacements=path_replacements, crc_generated=crc_generated, old_code=old_code, new_code=new_code)


def seam_census(d, here=None):
    """Receipt form of derive_native() (hashes only), JSON-normalised for exact comparison."""
    return json.loads(json.dumps(dict(seen=d['seen'], commands=len(d['commands']), substitutions=d['substitutions'],
                code_bytes_before=d['old_code'], code_bytes_after=d['new_code'],
                materialised=len(d['derived']), distinct_targets=len({str(t) for _, t, _, _ in d['derived']}),
                changed=[dict(source=row['path'], target=str(target.relative_to(here or HERE)), sha256=sha(new), seams=seams)
                         for row, target, new, seams in d['derived'] if seams]), sort_keys=True))


def prepare_native(preflight):
    """Pure file derivation followed by audited include preprocessing in Chunk C."""
    const = preflight['constants']
    HERE.mkdir()
    base_header, cand_header = native_headers(PREFLIGHT)
    d = derive_native(const, load(PREFLIGHT / 'emission/stdlib-p0/stdlib-p0.manifest.json'), cand_header, HERE, base_header)
    rehearsed = load(PREFLIGHT / 'native-seam-rehearsal.json')
    assert seam_census(d, HERE) == rehearsed, 'native seams differ from the preflight rehearsal'
    assert rehearsed['materialised'] == rehearsed['distinct_targets'], 'two native inputs share a target'
    updated, toolchain, seen, substitutions = d['commands'], d['toolchain'], d['seen'], d['substitutions']
    path_replacements, old_code, new_code = d['path_replacements'], d['old_code'], d['new_code']
    generated, changes, native = [], [], []
    for row, target, new, seams in d['derived']:
        once(target, new)
        generated.append(bind(target)); native.append(dict(source=row, restored=bind(target)))
        if seams:
            changes.append(dict(before=row, after=bind(target), seams=seams))
    crc_generated = d['crc_generated']
    for row in toolchain:
        native.append(dict(source=row, restored=row))
    save(HERE / 'derived-inputs.json', dict(generated=bind(crc_generated), all_generated=generated,
        crc_tables=const['crc_tables'], header_changes=changes,
        stdlib_header_changed=any(s.get('counts') for c in changes for s in c['seams']),
        code_bytes_before=old_code, code_bytes_after=new_code, replacements=substitutions,
        native_sources='identical to 2.5.4 Seed r1', census=seen,
        unchanged_inputs=sum(1 for _, _, _, seams in d['derived'] if not seams)))
    save(HERE / 'command-proof.json', dict(commands=updated, frozen=bind(FROZEN_NATIVE / 'command-proof.json'),
        allowed_substitutions=substitutions, path_replacements=path_replacements, source_changes=changes))
    save(HERE / 'plane-price.json', dict(before_product=const['before_product'], after_product=const['after_product'],
        artifacts=[bind(PREFLIGHT / 'planes' / side / name) for side in ('baseline', 'candidate') for name in STATIC]))
    ready = dict(native=native, toolchain=toolchain, commands=bind(HERE / 'command-proof.json'))
    S.HERE = HERE
    S.include_closure(updated, ready)
    save(HERE / 'command-ready.json', ready)
    return updated


# ------------------------------------------------------------ native attribution
# 2.5.4: no function may be classified changed.  Functions whose `#imm` operands carry a generated constant
# are classified 'immediate' (same size, objdump-verified, allowed byte pairs only).
EXPECTED_TEXT_CHANGED = CFG.NATIVE_TEXT_EXPECTED_CHANGED


def is_alloc(section):
    """ElfTruth reports flags as a tuple of names, e.g. ('SHF_ALLOC', 'SHF_EXECINSTR')."""
    flags = section.flags
    if isinstance(flags, (tuple, list, set, frozenset)):
        return 'SHF_ALLOC' in flags
    if isinstance(flags, str):
        return 'SHF_ALLOC' in flags or flags == 'A'
    return bool(int(flags) & 2)


def geometry_policy(a_sections, b_sections, text_cap=CFG.NATIVE_TEXT_CAP, metadata=CFG.NATIVE_METADATA_EXPECTED):
    """Only .text may grow (<= cap) and only the named metadata sections may change size
    (exact delta); every other section keeps address AND size."""
    ax = {s.name: s for s in a_sections}; bx = {s.name: s for s in b_sections}
    assert ax.keys() == bx.keys(), ('section population drift', sorted(ax.keys() ^ bx.keys()))
    moved = {}
    for name, x in ax.items():
        y = bx[name]
        if name in metadata:
            assert y.bytes - x.bytes == metadata[name], ('metadata section delta', name, x.bytes, y.bytes)
            moved[name] = dict(before=x.bytes, after=y.bytes, delta=metadata[name])
            continue
        if (x.address, x.bytes) == (y.address, y.bytes):
            continue
        if not is_alloc(x) and not is_alloc(y):
            # Link bookkeeping (.rela.*, .symtab, .strtab, .shstrtab, debug/comment) is not loaded and
            # follows the code change; shown on the real 36,419 -> 36,564 B link (.rela.text grew).
            moved[name] = dict(before=x.bytes, after=y.bytes, delta=y.bytes - x.bytes, loaded=False)
            continue
        assert name == '.text', ('unexpected section geometry change (needs reviewed attribution)', name,
                                 (x.address, x.bytes), (y.address, y.bytes))
        assert x.address == y.address and 0 < y.bytes - x.bytes <= text_cap, ('.text size change outside cap', x.bytes, y.bytes)
        moved[name] = dict(before=x.bytes, after=y.bytes, delta=y.bytes - x.bytes)
    return moved


def header_value_pairs(derived):
    """(old, new) integer pairs of the re-derived resident header macros (from derived-inputs.json)."""
    pairs = set()
    for change in derived['header_changes']:
        for seam in change['seams']:
            for name, old, new in seam.get('counts', []):
                assert name != 'BASE_ADDR', 'resident ABI origin moved'
                pairs.add((int(old.rstrip('u'), 0), int(new.rstrip('u'), 0)))
    return sorted(pairs)


def constant_values(const, header_pairs):
    b, a = const['before_product'], const['after_product']
    values = [(b['product_build_id_u32'], a['product_build_id_u32']),
              (b['artifacts']['shelf']['bytes'], a['artifacts']['shelf']['bytes']),
              (const['before_geometry']['code_bytes'], const['after_geometry']['code_bytes'])]
    return values + [tuple(x) for x in header_pairs]


def constant_patterns(const, header_pairs=()):
    """Little-endian old->new contiguous constants: build id, shelf bytes, static code bytes, resident
    header counts (u16/u32) and the CRC16 words."""
    pats = []
    for x, y in constant_values(const, header_pairs):
        pats.append((struct.pack('<I', x), struct.pack('<I', y)))
        if x < 65536 and y < 65536:
            pats.append((struct.pack('<H', x), struct.pack('<H', y)))
    for table in const['crc_tables']:
        for x, y in zip(table['before'], table['after']):
            pats.append((struct.pack('<H', x), struct.pack('<H', y)))
    return [(x, y) for x, y in pats if x != y]


def immediate_pairs(const, header_pairs=()):
    """Byte pairs an immediate operand may change by: each byte of each constant (and constant+1,
    the `x > limit` -> `x >= limit+1` lowering seen in 2.5.2 c2_stream_shelf_read)."""
    allowed = set()
    for x, y in constant_values(const, header_pairs):
        for adjust in (0, 1):
            allowed |= {(p, q) for p, q in zip(struct.pack('<I', x + adjust), struct.pack('<I', y + adjust)) if p != q}
    return allowed


def explained(old, new, patterns):
    """True when `new` is `old` with some little-endian constants replaced (strict equality after)."""
    rest = unexplained_offsets(old, new, patterns)
    return rest is not None and not rest   # None = size change, never explained (selftest r2 HALT)


def unexplained_offsets(old, new, patterns):
    if len(old) != len(new):
        return None
    diff = [i for i in range(len(old)) if old[i] != new[i]]
    covered = set()
    for x, y in patterns:
        for i in range(len(old) - len(x) + 1):
            if old[i:i + len(x)] == x and new[i:i + len(y)] == y:
                covered.update(range(i, i + len(x)))
    return [i for i in diff if i not in covered]


def symbol_resolver(truth):
    """Section-relative relocation targets (`.text` + addend: local labels, static functions) are
    position dependent: when .text grows, every such addend behind the growth point shifts.  Resolve
    them to (containing sized symbol, offset inside it), which is stable under a shift.  Without this
    every function that jumps to a local label behind the F2 growth would count as changed."""
    cache = getattr(truth, '_c255_resolver', None)
    if cache is not None:
        return cache
    sections = {s.name: s for s in truth.sections}
    by_index = {s.index: s for s in truth.symbols}
    sized = {}
    for s in truth.symbols:
        if s.bytes > 0 and s.symbol_type in ('Function', 'Object'):
            sized.setdefault(s.section, []).append(s)
    for rows in sized.values():
        rows.sort(key=lambda s: (s.value, -s.bytes))
    import bisect
    starts = {name: [s.value for s in rows] for name, rows in sized.items()}

    def resolve(r):
        target = by_index[r.target_symbol_index]
        if target.symbol_type != 'Section' or target.name not in sections:
            return (r.relocation_type, target.name, r.addend)
        address = sections[target.name].address + r.addend
        rows = sized.get(target.name, [])
        at = bisect.bisect_right(starts.get(target.name, []), address) - 1
        while at >= 0:
            s = rows[at]
            if s.value <= address < s.value + s.bytes:
                return (r.relocation_type, 'in:' + s.name, address - s.value)
            if s.value + 4096 < address:
                break
            at -= 1
        return (r.relocation_type, 'section:' + target.name, r.addend)
    try:
        truth._c255_resolver = resolve
    except (AttributeError, TypeError):
        pass
    return resolve


def reloc_index(truth, section):
    """{address: (kind, stable target, offset/addend)} for operands inside `section`."""
    resolve = symbol_resolver(truth)
    return {r.offset: resolve(r) for r in truth.relocations if r.source_section == section}


OPERAND_BYTES = {'R_MOS_ADDR8': 1, 'R_MOS_ADDR16': 2, 'R_MOS_ADDR16_LO': 1, 'R_MOS_ADDR16_HI': 1, 'R_MOS_IMM8': 1,
                 'R_MOS_IMM16': 2, 'R_MOS_ADDR24': 3, 'R_MOS_PCREL_8': 1, 'R_MOS_PCREL_16': 2}


def operand_size(kind, old=b'', new=b'', at=0):
    if kind == 'R_MOS_ADDR_ASCIZ':
        # Decimal address text ending in NUL; both sides must agree on its length.
        a, b = old.find(b'\0', at), new.find(b'\0', at)
        assert a == b and a >= at, 'ASCIZ relocation length drift'
        return a - at + 1
    assert kind in OPERAND_BYTES, ('unknown relocation kind', kind)
    return OPERAND_BYTES[kind]


IMMEDIATE_LINE = re.compile(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\w+)\s*(.*)$')


class Listings:
    """objdump -d over one symbol range (the 6-argument shape the Final replay admits)."""
    def __init__(self, logs='inventory-logs'):
        self.cache = {}
        self.logs = logs

    def __call__(self, elf, section, start, stop):
        command = [str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-d', '--section=' + section,
                   '--start-address=' + str(start), '--stop-address=' + str(stop), str(elf.relative_to(ROOT))]
        key = tuple(command)
        if key not in self.cache:
            raw = run(command, HERE / self.logs / (sha(' '.join(command).encode())[:20] + '.log')).decode()
            rows = {}
            for line in raw.splitlines():
                m = IMMEDIATE_LINE.match(line)
                if m:
                    rows[int(m[1], 16)] = (bytes.fromhex(m[2].replace(' ', '')), m[3], m[4].strip())
            self.cache[key] = rows
        return self.cache[key]


def immediate_explained(offsets, a_rows, b_rows, base_a, base_b, old, new, allowed):
    """Every offset (relative to the symbol start base_a / base_b) is a non-opcode byte of the same
    `<op> #imm` instruction in both listings and changes by an allowed constant byte pair."""
    starts = sorted(a_rows)
    proof = []
    for off in offsets:
        addr = base_a + off
        inst = max((s for s in starts if s <= addr), default=None)
        if inst is None or inst - base_a + base_b not in b_rows:
            return None
        ra, rb = a_rows[inst], b_rows[inst - base_a + base_b]
        if not (inst < addr < inst + len(ra[0]) and len(ra[0]) == len(rb[0]) and ra[1] == rb[1]
                and ra[2].startswith('#') and rb[2].startswith('#') and ra[0][0] == rb[0][0]):
            return None
        if (old[off], new[off]) not in allowed:
            return None
        proof.append(dict(address=addr, mnemonic=ra[1], before=f'0x{old[off]:02x}', after=f'0x{new[off]:02x}'))
    return proof


def text_attribution(a, b, expected_changed=None, allowed=frozenset(), listing=None, paths=None, enforce=True):
    """Function-level .text comparison: exact, relocated (operands with unchanged relocation
    (kind, target, addend)), immediate (objdump-verified `#imm` operands changed by a known constant
    pair) or changed.  Only `expected_changed` may be changed.  Fail closed."""
    expected_changed = CFG.NATIVE_TEXT_EXPECTED_CHANGED if expected_changed is None else expected_changed
    sa, sb = a.section('.text'), b.section('.text')
    ta, tb = a.section_bytes('.text'), b.section_bytes('.text')
    ra, rb = reloc_index(a, '.text'), reloc_index(b, '.text')
    fa = {s.name: s for s in a.symbols if s.section == '.text' and s.bytes > 0}
    fb = {s.name: s for s in b.symbols if s.section == '.text' and s.bytes > 0}
    added, removed = sorted(fb.keys() - fa.keys()), sorted(fa.keys() - fb.keys())
    result = dict(exact=[], relocated=[], immediate=[], changed=[], added=added, removed=removed)
    for name in sorted(fa.keys() & fb.keys()):
        x, y = fa[name], fb[name]
        ca = ta[x.value - sa.address:x.value - sa.address + x.bytes]
        cb = tb[y.value - sb.address:y.value - sb.address + y.bytes]
        ops_a = {o - x.value: v for o, v in ra.items() if x.value <= o < x.value + x.bytes}
        ops_b = {o - y.value: v for o, v in rb.items() if y.value <= o < y.value + y.bytes}
        if ca == cb and x.bytes == y.bytes:
            result['exact' if ops_a == ops_b else 'relocated'].append(name)
            continue
        if x.bytes == y.bytes and ops_a == ops_b:
            mask = set()
            for off, (kind, _, _) in ops_a.items():
                mask.update(range(off, off + operand_size(kind, ca, cb, off)))
            rest = [i for i in range(x.bytes) if ca[i] != cb[i] and i not in mask]
            if not rest:
                result['relocated'].append(name)
                continue
            if listing is not None:
                proof = immediate_explained(rest, listing(paths[0], '.text', x.value, x.value + x.bytes),
                                            listing(paths[1], '.text', y.value, y.value + y.bytes),
                                            x.value, y.value, ca, cb, allowed)
                if proof is not None:
                    result['immediate'].append(dict(name=name, operands=proof))
                    continue
        result['changed'].append(dict(name=name, before=x.bytes, after=y.bytes))
    names = sorted(r['name'] for r in result['changed'])
    assert len(fa) == sum(1 for s in a.symbols if s.section == '.text' and s.bytes > 0), 'duplicate .text symbol name (before)'
    assert len(fb) == sum(1 for s in b.symbols if s.section == '.text' and s.bytes > 0), 'duplicate .text symbol name (after)'
    if enforce:
        assert names == sorted(expected_changed), ('unexpected .text code change', names)
        assert not added and not removed, ('.text symbol population changed', added, removed)
    return result


def loosen_changed(index, changed):
    """Relocation operands that point INTO a function whose body is expected to change (the switch
    jump table `.rodata.<function>` of eval_v2_workbench_service points at labels inside it) move with
    its internal layout: compare kind and containing function only.  Every other target stays exact.
    Seed r6 real link: 16 jump-table operands moved by -15/+145..+212 B inside the +336 B function."""
    out = {}
    for at, (kind, target, extra) in index.items():
        if target.startswith('in:') and target[3:] in changed:
            extra = None
        out[at] = (kind, target, extra)
    return out


def data_attribution(a, b, patterns, allowed=frozenset(), listing=None, paths=None, changed=frozenset()):
    """Every allocated non-.text section: equal bytes, or each differing byte is (1) inside a known
    contiguous constant, (2) on a relocation operand whose (kind, target, addend) is unchanged
    (targets that moved with .text), or (3) in an executable section, an objdump-verified `#imm`
    operand changed by a known constant byte pair."""
    rows, bad = [], []
    for s in a.sections:
        if s.name == '.text' or not is_alloc(s) or s.section_type == 'SHT_NOBITS':
            continue
        old, new = a.section_bytes(s.name), b.section_bytes(s.name)
        if old == new:
            continue
        rest = unexplained_offsets(old, new, patterns)
        ok, how = rest is not None, ['constant']
        ra, rb = loosen_changed(reloc_index(a, s.name), changed), loosen_changed(reloc_index(b, s.name), changed)
        if ok and rest and ra == rb:
            mask = set()
            for addr, (kind, _, _) in rb.items():
                at = addr - s.address
                mask.update(range(at, at + operand_size(kind, old, new, at)))
            rest = [i for i in rest if i not in mask]; how.append('relocation')
        if ok and rest and listing is not None and 'SHF_EXECINSTR' in tuple(s.flags):
            proof = []
            funcs = sorted((x for x in a.symbols if x.section == s.name and x.bytes > 0), key=lambda x: x.value)
            for f in funcs:
                local = [i for i in rest if f.value <= s.address + i < f.value + f.bytes]
                if not local:
                    continue
                g = b.symbol(f.name)
                assert (g.value, g.bytes, g.section) == (f.value, f.bytes, f.section), ('symbol moved', f.name)
                got = immediate_explained([i - (f.value - s.address) for i in local],
                                          listing(paths[0], s.name, f.value, f.value + f.bytes),
                                          listing(paths[1], s.name, g.value, g.value + g.bytes),
                                          f.value, g.value, old[f.value - s.address:], new[f.value - s.address:], allowed)
                if got is None:
                    break
                proof.extend(got)
                rest = [i for i in rest if i not in local]
            how.append('immediate')
        ok = ok and not rest
        rows.append(dict(section=s.name, bytes=len(old), explained=ok, by=how,
                         unexplained=None if ok else (rest[:16] if rest is not None else 'size')))
        if not ok:
            bad.append(s.name)
    assert not bad, ('unclassified allocated-section change (needs reviewed attribution)', bad)
    return rows


def load_sites():
    """The immediate-site census of the baseline ELF (bound by CFG.NATIVE_SITES_SHA256)."""
    path = Path(__file__).resolve().parent / CFG.SITES_TOOL
    raw = path.read_bytes()
    if CFG.NATIVE_SITES_SHA256 is None:
        assert CFG.DRY, 'NATIVE_SITES_SHA256 not pinned'
    else:
        assert sha(raw) == CFG.NATIVE_SITES_SHA256, 'native site table is not the pinned file'
    table = json.loads(raw)
    assert table['elf_sha256'] == CFG.BASE_ELF_SHA, 'site table belongs to another ELF'
    return table


def constant_table(const):
    """name -> (old u32, new u32) of the generated constants that reach instruction operands."""
    b, a = const['before_product'], const['after_product']
    return dict(build_id=(b['product_build_id_u32'], a['product_build_id_u32']),
                shelf_bytes=(b['artifacts']['shelf']['bytes'], a['artifacts']['shelf']['bytes']),
                static_code_bytes=(const['before_geometry']['code_bytes'], const['after_geometry']['code_bytes']))


SHAPE_WINDOW = 12         # instructions on each side of a site that are compared for coincidences
#                           (the 2.5.2 `main` reuse of X = 0x84 sat 7 instructions after the SHELF mid-byte load)


def relation(x, y):
    """How a code generator can derive immediate x from a value y it already holds."""
    return 'eq' if x == y else '+1' if x == (y + 1) & 255 else '-1' if x == (y - 1) & 255 else None


def shape_flags(sites, rows, values):
    """Pure core of the immediate-shape prediction.  sites: site rows of ONE function; rows: {address:
    (bytes, mnemonic, operand)} of its baseline listing; values: constant_table().  A flag = a coincidence
    (zero, or eq/+1/-1 to an immediate within SHAPE_WINDOW instructions) that exists on one side only."""
    order = sorted(rows)
    imm = {a: int(rows[a][2][2:], 16) for a in order if re.fullmatch(r'#\$[0-9a-f]+', rows[a][2])}
    new = dict(imm)
    for s in sites:
        old_v, new_v = values[s['constant']]
        o = struct.pack('<I', old_v + s['adjust'])[s['byte']]
        assert s['address'] in imm and imm[s['address']] == o == s['value'], ('site is not the recorded immediate', s)
        new[s['address']] = struct.pack('<I', new_v + s['adjust'])[s['byte']]
    flags = []
    for s in sites:
        a = s['address']; at = order.index(a)
        special = lambda v: 'zero' if v == 0 else 'ff' if v == 255 else None   # stz / elided compare / carry shapes
        if special(imm[a]) != special(new[a]):
            flags.append(dict(id=f"{s['function']}@{a:#06x}:{special(new[a]) or special(imm[a])}", old=imm[a], new=new[a]))
        for other in order[max(0, at - SHAPE_WINDOW):at + SHAPE_WINDOW + 1]:
            if other == a or other not in imm:
                continue
            before, after = relation(imm[a], imm[other]), relation(new[a], new[other])
            if before != after:
                flags.append(dict(id=f"{s['function']}@{a:#06x}:{before or 'none'}->{after or 'none'}@{other:#06x}",
                                  old=[imm[a], imm[other]], new=[new[a], new[other]]))
    return flags, {a: [imm[a], new[a]] for a in sorted(s['address'] for s in sites)}


def immediate_shape(const, elf):
    """PRE-LINK prediction for the one thing only a link can otherwise show: do the new generated constants
    keep the instruction selection of every function that carries them?  (2.5.3: SHELF bytes 0x0184E3 ->
    0x018978 cost `main` +2 B because the 0x84 coincidence with the next immediate went away.)  Reads the
    baseline ELF with objdump only."""
    from elf_truth import ElfTruth
    table, values = load_sites(), constant_table(const)
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=False)
    listing, flags, rows = Listings('shape-logs'), [], []
    for name, (old_v, new_v) in values.items():
        if old_v >> 16 != new_v >> 16 and name != 'build_id':
            flags.append(dict(id=name + ':high-byte', old=old_v, new=new_v))
    groups = {}
    for s in table['sites']:
        groups.setdefault((s['section'], s['function']), []).append(s)
    for (section, function), sites in sorted(groups.items()):
        f = truth.symbol(function)
        assert f.section == section and f.bytes > 0, ('site function', function)
        got, values_at = shape_flags(sites, listing(elf, section, f.value, f.value + f.bytes), values)
        flags += got
        rows.append(dict(section=section, function=function, sites={f'{a:#06x}': v for a, v in values_at.items()}))
    return dict(status='PASS' if not flags else 'FLAGGED', flags=flags, functions=rows, window=SHAPE_WINDOW,
                constants={k: [f'{x:#x}', f'{y:#x}'] for k, (x, y) in values.items()}, sites=len(table['sites']),
                note='no flag = the new constants keep every recorded coincidence pattern: predicted .text '
                     'delta 0 and no section size change; a flag needs a reviewer decision BEFORE the link')


def inventory(identity=False):
    """2.5.5 native attribution: the new link against the 2.5.4 ELF (Seed r1b = Final r1, byte-identical).
    The reviewed commuting-pair class of the 2.5.4 continuation is deliberately absent: the baseline already
    has the order `clc ; sta $a` at 0xc473, and a pair that flips is an unexplained difference = HALT.
    Rule: no function changes except those forced by generated constants.  `.text` keeps address and size
    exactly; no function is 'changed'; 'immediate' functions in .text are limited to the reviewed set; every
    other allocated section is byte-equal or explained by constant patterns / unchanged relocation operands /
    objdump-verified immediates.  identity = pre-link rehearsal with the 2.5.4 ELF standing in for the new link."""
    from elf_truth import ElfTruth
    from dataclasses import asdict
    paths = [BASE / 'wplto/resident-island-seed.prg.elf', BUILD / 'wplto/resident-island-seed.prg.elf']
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in paths]
    a, b = truths
    save(HERE / 'section-symbol-inventory.json', dict(
        ELFs=[bind(p) for p in paths], before_sections=[asdict(s) for s in a.sections],
        after_sections=[asdict(s) for s in b.sections]))
    assert b.symbol('lisp65_comfort_state').value == 0xbff6
    const = load(PREFLIGHT / 'constants.json')
    header_pairs = header_value_pairs(load(HERE / 'derived-inputs.json'))
    moved = geometry_policy(a.sections, b.sections)
    assert a.section('.text').bytes == b.section('.text').bytes == CFG.BASE_TEXT_BYTES, \
        ('.text is not exactly the 2.5.4 size', a.section('.text').bytes, b.section('.text').bytes)
    assert '.text' not in moved and not any(row.get('loaded', True) and row['delta'] for row in moved.values()), moved
    patterns, allowed, listing = constant_patterns(const, header_pairs), immediate_pairs(const, header_pairs), Listings()
    text = text_attribution(a, b, expected_changed=(), allowed=allowed, listing=listing, paths=paths)
    immediate = sorted(r['name'] for r in text['immediate'])
    assert set(immediate) <= set(CFG.NATIVE_TEXT_IMMEDIATE_ALLOWED), ('.text immediate outside the reviewed set', immediate)
    assert not identity or not immediate
    prot = data_attribution(a, b, patterns, allowed=allowed, listing=listing, paths=paths, changed=frozenset())
    price = dict(text_delta=0, cap=CFG.NATIVE_TEXT_CAP, text_bytes=b.section('.text').bytes)
    result = dict(status='PASS', unclassified_bytes=0, geometry=moved, price=price,
                  text=dict(exact=len(text['exact']), relocated=len(text['relocated']), immediate=text['immediate'],
                            changed=text['changed']), header_pairs=header_pairs,
                  protected=prot, ELFs=[bind(p) for p in paths], plane=bind(HERE / 'plane-price.json'),
                  derived=bind(HERE / 'derived-inputs.json'), section_inventory=bind(HERE / 'section-symbol-inventory.json'),
                  standard='2.5.5 native rule: no function changes except those forced by generated constants; '
                           'no reviewed instruction-order class; structural attribution + byte-identical Final replay',
                  host=host_identity())
    save(HERE / 'inventory.json', result)
    return result

def selftest(out=SELFTEST):
    assert not out.exists(), 'selftest output is write-once'
    out.mkdir(parents=True)
    save(out / 'attempt.json', dict(status='STARTED', tools=tool_identity(), host=host_identity()))
    rejected = []

    def reject(name, fn):
        try:
            fn()
        except (AssertionError, FileExistsError, EXT.ProbeError, L.GateError, KeyError):
            rejected.append(name)
        else:
            raise AssertionError('negative survived: ' + name)
    previous, medium = predecessor()
    files = D.visible_files(medium)
    old_id = load(FROZEN_PLANE / 'product/substitution-artifacts.json')['product_build_id_u32']
    new_id = old_id ^ 0x100
    for spec in package_specs():
        name = spec['name']; print('selftest package ' + name, flush=True)
        image = F.emit_image(name, spec['shelf'], ROOT / spec['manifest']['path'])
        old = files[name.upper().encode()]
        new = EXT.build_extension(image, build_id=new_id)
        envelope_control(old, new, image, old_id, new_id)
        reject('old-ID package ' + name, lambda: EXT.decode_extension(old, image, expected_build_id=new_id))
        reject('new-ID package on old plane ' + name, lambda: EXT.decode_extension(new, image, expected_build_id=old_id))
        bad = bytearray(new); bad[-1] ^= 1
        reject('changed loader ' + name, lambda: envelope_control(old, bytes(bad), image, old_id, new_id))
    payloads = {s['name']: EXT.build_extension(F.emit_image(s['name'], s['shelf'], ROOT / s['manifest']['path']), build_id=new_id)
                for s in package_specs()}
    for name in payloads:
        bad = dict(payloads); bad[name] = files[name.upper().encode()]
        reject('one un-rebound package ' + name, lambda: L.decode_index(files[b'L65INDEX'], bad, artifact_build_id=new_id))
    path = out / 'write-once-control'; once(path, b'one')
    reject('write-once overwrite', lambda: once(path, b'two'))
    reject('write-once identical retry', lambda: once(path, b'one'))
    baseline = b'base'; candidate = b'newbase'; delivered = baseline + bytes(9) + b'native'
    assert project_delivery_code(delivered, baseline, candidate)[7:] == delivered[7:]
    reject('wrong baseline', lambda: project_delivery_code(b'X' + delivered[1:], baseline, candidate))
    # 2.5.5: the static plane may shrink; the freed bytes return to zero fill, everything behind is untouched.
    assert project_delivery_code(delivered, baseline, b'ba') == b'ba' + bytes(2) + delivered[4:]
    assert project_delivery_code(delivered, baseline, baseline) == delivered
    reject('empty static plane', lambda: project_delivery_code(delivered, baseline, b''))
    reject('static plane over the code limit', lambda: project_delivery_code(delivered + bytes(CFG.LIMITS['code']), baseline, bytes(CFG.LIMITS['code'] + 1)))
    reject('shrink against a wrong baseline', lambda: project_delivery_code(b'X' + delivered[1:], baseline, b'ba'))
    # 2.5.5 on the REAL 2.5.4 medium, in memory: a SHELF.BIN that is one sector shorter and a CODE.BIN whose
    # plane is 142 B shorter are complete classified transactions (chain shrink, BAM, directory block count).
    shrink_domains, shrunk = {}, medium
    shelf = files[b'SHELF.BIN'][:-300]
    plane_bytes = (FROZEN_PLANE / 'CODE.BIN').read_bytes()
    code = project_delivery_code(files[b'CODE.BIN'], plane_bytes, plane_bytes[:-142])
    for label, payload in (('SHELF.BIN', shelf), ('CODE.BIN', code)):
        shrunk = S.replace_file(shrunk, label, payload, shrink_domains)
    D.validate_bam(shrunk)
    after = D.visible_files(shrunk)
    assert after[b'SHELF.BIN'] == shelf and after[b'CODE.BIN'] == code and len(after) == 20
    assert all(after[n] == files[n] for n in files if n not in (b'SHELF.BIN', b'CODE.BIN')), 'shrink touched another file'
    assert (len(files[b'SHELF.BIN']) + 253) // 254 - (len(shelf) + 253) // 254 >= 1, 'control does not free a sector'
    ledger = classified(medium, shrunk, shrink_domains)
    assert {r['owner'].split(': ')[0] for r in ledger['rows']} == {'SHELF.BIN', 'CODE.BIN'}
    reject('shrink transaction with an unowned byte', lambda: classified(medium, shrunk[:-1] + bytes([shrunk[-1] ^ 1]), shrink_domains))
    # 2.5.5 zeroing step on that medium: one freed SHELF.BIN sector and the slack of its new last sector.
    reject('non-zero byte left in a freed sector (un-zeroed medium)', lambda: residue_record(medium, shrunk, after, ['SHELF.BIN', 'CODE.BIN']))
    zero_domains = dict(shrink_domains)
    zeroed, zrec = zero_residue(medium, shrunk, after, ['SHELF.BIN', 'CODE.BIN'], zero_domains)
    assert [r['file'] for r in zrec['files']] == ['SHELF.BIN'] and [x['kind'] for x in zrec['files'][0]['ranges']] == ['freed-sector', 'slack']
    assert zrec['nonzero_bytes_cleared'] > 0 and D.visible_files(zeroed) == after
    assert residue_record(medium, zeroed, after, ['SHELF.BIN', 'CODE.BIN'])['residue_bytes'] == 0
    reject('zeroing step applied to an already zeroed medium', lambda: zero_residue(medium, zeroed, after, ['SHELF.BIN'], dict(zero_domains)))
    classified(medium, zeroed, zero_domains)
    reject('zeroed medium against the un-zeroed ledger', lambda: classified(medium, zeroed, shrink_domains))
    spot = zrec['files'][0]['ranges'][0]['offset'] + 9
    dirty = zeroed[:spot] + b'\x01' + zeroed[spot + 1:]
    reject('one non-zero byte left in a freed sector', lambda: residue_record(medium, dirty, after, ['SHELF.BIN']))
    slack = zrec['files'][0]['ranges'][1]['offset']
    reject('one non-zero byte left in the slack of the shortened file', lambda: residue_record(
        medium, zeroed[:slack] + b'\x01' + zeroed[slack + 1:], after, ['SHELF.BIN']))
    stale = D.sector_offset(80, 39)
    assert D.sector_is_free(zeroed, 80, 39)
    reject('a free sector elsewhere that is not zero', lambda: residue_record(
        medium, zeroed[:stale] + b'\x01' + zeroed[stale + 1:], after, ['SHELF.BIN']))
    reject('freed sector already rewritten before the zeroing step', lambda: zero_residue(
        medium, shrunk[:spot] + bytes([shrunk[spot] ^ 1]) + shrunk[spot + 1:], after, ['SHELF.BIN'], dict(shrink_domains)))
    reject('native overlap', lambda: project_delivery_code(baseline + b'X' + delivered[5:], baseline, candidate))
    reject('unclassified byte', lambda: classified(b'a', b'b', {}))
    reject('wrong classified pair', lambda: classified(b'a', b'b', {0: (97, 99, 'owner')}))
    reject('foreign static image', lambda: image_equal(type('Image', (), dict(code=b'a', metadata=b'm'))(), type('Image', (), dict(code=b'b', metadata=b'm'))()))
    # Image classification, on the real frozen 2.5.2 images and synthetic mutations.
    frozen = load(FROZEN_PLANE / 'product/substitution-artifacts.json')
    images = [F.emit_image(k, role(k), ROOT / r['path']) for k, r in zip(KEYS, frozen['manifests'], strict=True)]
    exact = classify_images(images, images, (), KEYS)
    assert all(r['state'] == 'EXACT' for r in exact.values())
    reject('unchanged image expected CHANGED', lambda: classify_images(images, images, ('ide',), tuple(k for k in KEYS if k != 'ide')))
    bad = copy.deepcopy(images)
    bad[4].manifest['entries'][0]['length'] = 256
    reject('256-byte object', lambda: classify_images(images, bad, (), KEYS))
    drop = copy.deepcopy(images)
    victim = next(e['name'] for e in drop[1].manifest['entries'] if not e['name'].startswith('%'))
    drop[1].manifest['entries'] = [e for e in drop[1].manifest['entries'] if e['name'] != victim]
    reject('public name removed', lambda: classify_images(images, drop, ('ide',), tuple(k for k in KEYS if k != 'ide')))
    # Native attribution helpers on synthetic ELF stand-ins.
    from types import SimpleNamespace as N
    def sec(name, addr, size, f=('SHF_ALLOC',)): return N(name=name, address=addr, bytes=size, section_type='SHT_PROGBITS', flags=f)
    base = [sec('.text', 0x2023, 1000), sec('.rodata', 0xb61d, 10), sec('.lisp65_rt_x', 0xc000, 8)]
    # relocation-aware helpers on stand-ins (kind, target, addend); flags as int or str
    a_sec = N(name='.lisp65_rt_x', address=0xc000, bytes=4, section_type='SHT_PROGBITS', flags=2)
    assert is_alloc(a_sec) and not is_alloc(N(flags=0)) and is_alloc(N(flags=('SHF_ALLOC', 'SHF_EXECINSTR'))) and not is_alloc(N(flags=('SHF_MERGE',)))
    geometry_policy(base, base)
    reject('text growth (2.5.5: none)', lambda: geometry_policy(base, [sec('.text', 0x2023, 1001)] + base[1:]))
    reject('text over cap', lambda: geometry_policy(base, [sec('.text', 0x2023, 1000 + CFG.NATIVE_TEXT_CAP + 1)] + base[1:]))
    reject('text shrink', lambda: geometry_policy(base, [sec('.text', 0x2023, 999)] + base[1:]))
    meta = [sec('.lisp65_error_callsites', 0, 10, f=())]
    geometry_policy(base + meta, base + meta)
    reject('new error call site', lambda: geometry_policy(base + meta, base + [sec('.lisp65_error_callsites', 0, 11, f=())]))
    reject('metadata delta wrong', lambda: geometry_policy(base + meta, base + [sec('.lisp65_error_callsites', 0, 12, f=())]))
    reject('rodata moved', lambda: geometry_policy(base, [base[0], sec('.rodata', 0xb61e, 10), base[2]]))
    reject('protected resized', lambda: geometry_policy(base, [base[0], base[1], sec('.lisp65_rt_x', 0xc000, 9)]))
    reject('section dropped', lambda: geometry_policy(base, base[:2]))
    pats = [(struct.pack('<I', 0x8d22c8e6), struct.pack('<I', 0x11223344))]
    assert explained(b'\x00' + struct.pack('<I', 0x8d22c8e6), b'\x00' + struct.pack('<I', 0x11223344), pats)
    assert not explained(b'\x00' + struct.pack('<I', 0x8d22c8e6), b'\x01' + struct.pack('<I', 0x11223344), pats)
    assert not explained(b'ab', b'abc', pats)
    # Product projection helpers (2.5.3): whole file, unique hunks, fail-closed seams.
    old = ''.join(f'(defun f{i} () {i})\n' for i in range(20)); new = old.replace('(defun f9 () 9)', '(defun f9 () 99)')
    assert project_text(old, old, new, 'whole')[0] == new
    hist = ';; frozen header\n' + old
    assert project_text(hist, old, new, 'hunk')[0] == ';; frozen header\n' + new
    reject('projection seam missing', lambda: project_text(hist.replace('(defun f8 () 8)', '(defun f8 () 0)'), old, new, 'x'))
    reject('projection seam duplicated', lambda: project_text(hist + ''.join(old.splitlines(True)[6:13]), old, new, 'x'))
    assert edit_list(['a', 'b', 'c'], ['b'], ['b', 'x'], 'l') == ['a', 'b', 'x', 'c']
    reject('suite list seam missing', lambda: edit_list(['a'], ['b'], [], 'l'))
    reject('suite list seam duplicated', lambda: edit_list(['b', 'b'], ['b'], [], 'l'))
    reject('append collision', lambda: edit_list(['a'], None, ['a'], 'l'))
    # 2.5.4 product seams: a hunk that does not occur needs a reviewed seam bound to that hunk.
    lib_old = old; lib_new = old.replace('(defun f3 () 3)', '(defun f3 () 33)').replace('(defun f15 () 15)', '(defun f15 () 150)')
    world = ';; product world\n' + old.replace('(defun f15 () 15)', '(defun f15 () (poll))')
    reject('unprojectable hunk without a seam', lambda: project_text(world, lib_old, lib_new, 'x'))
    import difflib
    lo, ln = lib_old.splitlines(True), lib_new.splitlines(True)
    groups = list(difflib.SequenceMatcher(None, lo, ln, autojunk=False).get_grouped_opcodes(3))
    g = groups[-1]; digest = sha((''.join(lo[g[0][1]:g[-1][2]]) + '\0' + ''.join(ln[g[0][3]:g[-1][4]])).encode())
    seam = dict(lib_hunk='f15', lib_hunk_sha256=digest, action='replace',
                product_old='(defun f15 () (poll))\n', product_new='(defun f15 () (progn (publish) (poll)))\n')
    text, info = project_text(world, lib_old, lib_new, 'seam', (seam,))
    assert '(defun f3 () 33)' in text and '(progn (publish) (poll))' in text and info['product_seams'] == 1
    assert project_text(world, lib_old, lib_new, 'skip', (dict(seam, action='skip', reason='declined'),))[0].count('(poll)') == 1
    reject('seam bound to another hunk', lambda: project_text(world, lib_old, lib_new, 'x', (dict(seam, lib_hunk_sha256='0' * 64),)))
    reject('stale seam (hunk projects by itself)', lambda: project_text(';; w\n' + old, lib_old, lib_new, 'x', (seam,)))
    reject('seam product text missing', lambda: project_text(world, lib_old, lib_new, 'x', (dict(seam, product_old='(defun f15 () (other))\n'),)))
    reject('seam product text duplicated', lambda: project_text(world + '(defun f15 () (poll))\n', lib_old, lib_new, 'x', (seam,)))
    reject('seam on a whole-file projection', lambda: project_text(lib_old, lib_old, lib_new, 'x', (seam,)))
    # Package index rule (synthetic rows).  2.5.5 re-emits no package: the price-window helpers have no config.
    row = dict(name='repl-comfort', track=20, sector=33, combined_crc32=1, dependencies=[], execution_source=2,
               artifact_bytes=10, bank2=5, images=1, entries=2, resolutions=3, roots=1, scratch=8)
    assert index_row_control(row, dict(row, bank2=6, artifact_bytes=11, combined_crc32=2)) == ['artifact_bytes', 'bank2', 'combined_crc32']
    reject('index locator moved', lambda: index_row_control(row, dict(row, sector=34)))
    reject('index dependency moved', lambda: index_row_control(row, dict(row, dependencies=[1])))
    reject('index image count moved', lambda: index_row_control(row, dict(row, images=2)))
    reject('package price asked for a package that is not re-emitted', lambda: package_price(
        'repl-comfort', dict(code_bytes=1, entries=[]), dict(code_bytes=2, entries=[])))
    # 2.5.5 image rule: byte-EXACT is required where EXACT is expected, an added or removed object is refused.
    reject('all images unchanged (2.5.5 expects ide CHANGED)', lambda: price_images(images, images))
    same = dict(state='EXACT', added=[], removed=[], entries_before=204, entries_after=204)
    for key in KEYS:
        image_rule(key, dict(same, state='CHANGED' if key in CFG.EXPECT_CHANGED else 'EXACT'))
    for key in CFG.EXPECT_EXACT:
        reject('ENTRY-EXACT image where byte-EXACT is expected: ' + key, lambda: image_rule(key, dict(same, state='ENTRY-EXACT')))
        reject('CHANGED image where byte-EXACT is expected: ' + key, lambda: image_rule(key, dict(same, state='CHANGED')))
    reject('object added to the ide image', lambda: image_rule('ide', dict(same, state='CHANGED', added=['%new'], entries_after=205)))
    reject('object removed from the ide image', lambda: image_rule('ide', dict(same, state='CHANGED', removed=['%old'], entries_after=203)))
    # Resident header rule: an ENTRY index may never move; in 2.5.5 no macro may move at all (stdlib-p0 EXACT).
    def header(blob, entry): return ('#define LISP65_BYTECODE_STDLIB_BLOB_BYTES %du\n#define LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT 1u\n'
                                     '#define LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT 1u\n#define LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT 1u\n'
                                     '#define LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY %du\n' % (blob, entry))
    om = dict(code_bytes=100, literal_index=[0], literal_nodes=[0], literal_patches=[0])
    assert stdlib_header_projection(header(100, 7).encode(), om, None, header(100, 7)) == (header(100, 7).encode(), [])
    reject('resident BLOB_BYTES moved (2.5.5: stdlib-p0 is EXACT)', lambda: stdlib_header_projection(header(100, 7).encode(), om, None, header(146, 7)))
    reject('resident ENTRY index moved', lambda: stdlib_header_projection(header(100, 7).encode(), om, None, header(146, 8)))
    # Immediate-shape prediction (pure core; synthetic listing of one function).
    rows = {0x10: (b'\xa2\x79', 'ldx', '#$79'), 0x12: (b'\x8e\x84\xc0', 'stx', '$c084'), 0x15: (b'\xa2\x89', 'ldx', '#$89'),
            0x17: (b'\xa2\x01', 'ldx', '#$1'), 0x19: (b'\xa2\x84', 'ldx', '#$84')}
    sites = [dict(function='f', address=0x10, constant='shelf_bytes', byte=0, adjust=0, value=0x79),
             dict(function='f', address=0x15, constant='shelf_bytes', byte=1, adjust=0, value=0x89)]
    def flags(new): return [f['id'] for f in shape_flags(sites, rows, dict(shelf_bytes=(0x18979, new)))[0]]
    assert flags(0x18a7b) == [] and flags(0x18979) == []
    assert any(':zero' in f for f in flags(0x18a00)) and any('none->eq' in f for f in flags(0x18484))
    assert any('none->eq' in f for f in flags(0x18a8a)) and any('none->+1' in f for f in flags(0x18a02))
    reject('site table does not match the listing', lambda: shape_flags([dict(sites[0], value=0x78)], rows, dict(shelf_bytes=(0x18979, 0x18a7b))))
    # The product-world E3 verdict of c255_e3_product (10 new negatives + the 11 inherited ones; synthetic).
    rejected.extend(E3P.selftest())
    # Host: the Fedora 44 pins of the baseline are refused on this host.
    def other_host(pins):
        try:
            CFG.host_tools(pins)
        except ValueError as error:
            raise AssertionError(str(error))
    other_host(CFG.HOST_TOOLS)
    reject('baseline (Fedora 44) host tool pins on this host', lambda: other_host(CFG.BASE_HOST_TOOLS))
    reject('one drifted host tool', lambda: other_host(dict(CFG.HOST_TOOLS, **{'/usr/bin/llvm-link': '0' * 64})))
    # Write-once evidence of the synthetic result set.
    result = dict(status='PASS', tools=tool_identity(), host=host_identity(), python=python_runtime(), rejected=rejected,
                  native_links=0, media_transactions=0)
    save(out / 'receipt.json', result)
    return result


def rehearse(out):
    """Everything the Seed does EXCEPT the 75 frozen commands, into a rehearsal directory.

    Phase 1 (pre-link): the Seed's own entry checks, the full prepare_native materialisation
    (seams, identity, command list, audited -E -M include closure) and the per-command
    preconditions the Seed loop relies on.
    Phase 1b (pre-link prediction): immediate_shape() -- the new constants against the recorded immediate
    sites of the 2.5.4 ELF; an unaccepted flag halts here, before any link.
    Phase 2 (post-link, identity): the 2.5.4 ELF/PRG stand in for the link output and run through
    inventory(identity=True), media(stager=False) and finish(rehearsal=True): the same code paths, readers,
    rebinding, publish-last, D81 transaction (all six envelopes; the SHRUNK static plane: SHELF.BIN chain shorter,
    CODE.BIN zero fill) and receipts, with the candidate static plane.  For 2.5.5 the stand-in differs from the real
    link only in the generated-constant bytes (28 immediate operands, the CRC16 table words, the -D build
    id / SHELF data words) and whatever those change downstream (overlay CRCs, PRG, boot files).
    NOT a product: no compile, no link, no stager build; the guard refuses them."""
    global BUILD, HERE
    pre = verify_preflight()
    tests = load(SELFTEST / 'receipt.json')
    assert tests['status'] == 'PASS' and tests['tools'] == tool_identity(), 'tool bytes changed since selftest'
    assert tests['host'] == host_identity(), 'host tools changed since selftest'
    assert CFG.same_authority(pre['source_revision'], source_revision()), 'authority or consumed roots moved since preflight'
    e3_receipt = require_e3(pre)
    assert not out.exists(), 'rehearsal directory is write-once'
    real = BUILD, HERE
    BUILD, HERE = out, out / 'native'
    try:
        BUILD.mkdir(parents=True)
        once(BUILD / 'NOT-A-PRODUCT.txt', 'Pre-link/post-link REHEARSAL of the 2.5.5 Seed. No product compile or link ran.\n'
             'The ELF/PRG under wplto/ are copies of the 2.5.4 artifacts; the medium is not a deliverable (it does not boot).\n')
        save(BUILD / 'attempt.json', dict(status='REHEARSAL', tools=tool_identity(), host=host_identity(), authority=source_revision(),
                                          predecessor=bind(BASE / 'complete.json'), preflight=bind(PREFLIGHT / 'receipt.json'),
                                          e3=e3_receipt))
        commands = prepare_native(pre)
        assert len(commands) == CFG.NATIVE_COMMANDS
        produced, rows, missing_dirs = set(), [], set()
        for i, command in enumerate(commands):
            output = ROOT / command[command.index('-o') + 1]
            assert output.is_relative_to(BUILD) and not output.exists() and str(output) not in produced, ('output', i)
            output.parent.mkdir(parents=True, exist_ok=True)          # as the Seed loop does
            tool = Path(command[0] if Path(command[0]).is_absolute() else ROOT / command[0])
            assert tool.is_file() and os.access(tool, os.X_OK), ('command executable', i, command[0])
            inputs = []
            if '-c' in command:
                source = ROOT / command[command.index('-c') + 1]
                assert source.is_file(), ('compile source missing', i, source)
                inputs.append(str(source.relative_to(ROOT)))
            else:
                for arg in command[1:]:
                    q = ROOT / arg
                    if arg.endswith(('.o', '.bc')) and not arg.startswith('-') and arg != command[command.index('-o') + 1]:
                        assert str(q) in produced or q.is_file(), ('link input neither produced nor present', i, arg)
                        inputs.append(arg)
            for j, arg in enumerate(command):
                if arg in ('-include', '-T') and j + 1 < len(command):
                    assert (ROOT / command[j + 1]).exists(), ('include/script path missing', i, command[j + 1])
                if arg == '-I' and j + 1 < len(command) and not (ROOT / command[j + 1]).exists():
                    # An empty search directory is legal; it must be equally absent in the 2.5.4 link attempt.
                    twin = command[j + 1].replace(str(BUILD.relative_to(ROOT)), CFG.BASE_LINK, 1)
                    assert twin != command[j + 1] and not (ROOT / twin).exists(), ('include dir lost', i, command[j + 1])
                    missing_dirs.add(command[j + 1])
                if arg.startswith('-T') and len(arg) > 2:
                    assert (ROOT / arg[2:]).exists(), ('linker script missing', i, arg)
                if arg.startswith('-Wl,-T'):
                    assert (ROOT / arg[6:].lstrip(',')).exists(), ('linker script missing', i, arg)
            produced.add(str(output))
            rows.append(dict(index=i, output=str(output.relative_to(ROOT)), inputs=len(inputs)))
        assert '-Wl,--emit-relocs' in commands[74]
        save(BUILD / 'prelink.json', dict(status='PASS', commands=len(commands), executed=0, rows=rows,
                                           absent_include_dirs_as_in_baseline=sorted(missing_dirs),
                                           include_closure=bind(HERE / 'include-closure.json'),
                                           command_proof=bind(HERE / 'command-proof.json')))
        print('pre-link rehearsal: PASS (75 commands prepared, 0 executed)', flush=True)
        # ---- phase 1b: immediate-shape prediction on the baseline ELF (objdump only)
        shape = immediate_shape(pre['constants'], BASE / 'wplto/resident-island-seed.prg.elf')
        save(BUILD / 'immediate-shape.json', shape)
        open_flags = sorted(f['id'] for f in shape['flags'] if f['id'] not in CFG.NATIVE_SHAPE_ACCEPTED)
        assert not open_flags, ('immediate-shape flags need a reviewer decision before the link', open_flags)
        assert shape['sites'] == 28 and len(shape['functions']) == 9, ('site census of the 2.5.4 ELF', shape['sites'])
        assert set(CFG.NATIVE_SHAPE_ACCEPTED) <= {f['id'] for f in shape['flags']}, 'stale accepted shape flag'
        # ---- phase 2: identity stand-in for the link output
        for name in ('resident-island-seed.prg.elf', 'resident-island-seed.prg'):
            once(BUILD / 'wplto' / name, (BASE / 'wplto' / name).read_bytes())
        inv = inventory(identity=True)
        assert inv['status'] == 'PASS' and inv['price']['text_delta'] == 0 and not inv['text']['changed']
        med = media(stager=False)
        done = finish(pre, rehearsal=True)
        result = dict(status='PASS', kind='REHEARSAL-NOT-A-PRODUCT', prelink=bind(BUILD / 'prelink.json'),
                      inventory=bind(HERE / 'inventory.json'), media=bind(BUILD / 'media.json'),
                      immediate_shape=bind(BUILD / 'immediate-shape.json'),
                      changed_files=med['changed_files'], commands_executed=REHEARSAL_COMMANDS,
                      product_compiles=0, product_links=0, stager_builds=0, complete_status=done['status'])
        save(BUILD / 'rehearsal.json', result)
        return {k: result[k] for k in ('status', 'kind', 'changed_files', 'product_compiles', 'product_links')}
    except BaseException as error:
        if BUILD.exists() and not (BUILD / 'halt.json').exists():
            save(BUILD / 'halt.json', dict(status='HALT', kind='REHEARSAL', error=repr(error)))
        raise
    finally:
        BUILD, HERE = real
