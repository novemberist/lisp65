#!/usr/bin/env python3
"""2026-09-30 Seed r7 full-plane successor; Chunk A is host-only.

preflight: fresh source closure, exact r6 replay, M65D-only emission, six
unchanged-content package envelopes, computed constants. Only the canonical
MK_BCODE host ABI probe may compile/run; no product compiler/link/media action.
seed: explicitly deferred Chunk C; one attempt, one native link, fail-closed
native attribution, full classified D81 transaction. Historical worlds are read-only.
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

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/o2-lite-product-r6'
# r7 (first attempt) halted on a historical plane-size copy; named successor r7b.
BUILD = ROOT / 'build/o2-lite-product-r7c'
PREFLIGHT = ROOT / 'build/o2-lite-r7-preflight-d'
SELFTEST = ROOT / 'build/o2-lite-r7-selftest-c'
FROZEN_PLANE = ROOT / 'build/o2-lite-r4-slots-preflight/planes/candidate'
FROZEN_NATIVE = ROOT / 'build/o2-lite-r4-slots-preflight/native'
FROZEN_MEDIA = ROOT / 'build/o2-lite-product-r4/media-r4'
HERE = BUILD / 'native'
KEYS = ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc')
STATIC = ('CODE.BIN', 'C2D.BIN', 'SHELF.BIN')
NATIVE_FILES = ('AUTOBOOT.C65', 'BOOT.BIN', 'BOOT.ID', 'BOOTSTAGE.BIN',
                'LISP65.PRG', 'PROFILE', 'REGION1.BIN', 'SESSION.BIN', 'WINDOW.BIN')
OLD_FORM = '(dotimes (i 32 nil) (%disk-poke (+ base i) 0))'
NEW_FORM = '(dotimes (i 30 nil) (%disk-poke (+ base (+ i 2)) 0))'
BASE_MEDIUM_SHA = 'b1921228ba1166f283793ae21f51891e6cb48729a8f5d1b5c0d09cdc6e902aef'
BASE_ELF_SHA = 'a82d603a03f52a14e6b55bd4d8e35ad5b848b2a540f99f4a529ccddb15c70084'
sha, bind, checked, load, run = S.sha, S.bind, S.checked, S.load, S.run

def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw.encode() if isinstance(raw,str) else raw)

def save(path, value):
    once(path,json.dumps(value,indent=2,sort_keys=True)+'\n')
HOST_HELPER_COMMANDS = []
CHUNK_C = ('nice -n 18 ionice -c3 env PYTHONDONTWRITEBYTECODE=1 python3 '
           'tools/host-lisp/o2_lite_r7_product.py seed')


def source_revision():
    """Read Git identity without any Git command or repository mutation."""
    directory=ROOT/'.git'
    if directory.is_file():
        directory=(ROOT/directory.read_text().strip().removeprefix('gitdir: ')).resolve()
    head=(directory/'HEAD').read_text().strip()
    if head.startswith('ref: '):
        ref=head[5:]
        if (directory/ref).exists():
            head=(directory/ref).read_text().strip()
        else:
            common=directory
            if (directory/'commondir').exists():
                common=(directory/(directory/'commondir').read_text().strip()).resolve()
            if (common/ref).exists():
                head=(common/ref).read_text().strip()
            else:
                head=next(line.split()[0] for line in (common/'packed-refs').read_text().splitlines()
                          if line.endswith(' '+ref))
    assert re.fullmatch('[0-9a-f]{40}',head)
    return dict(requested='8c0e58ed',observed=head,
        note=('59aaeda8 adds only the parked-items register entry; producer-relevant sources match 8c0e58ed'
              if head=='59aaeda805942a061c09f0bdd7032e9eaf19d0f5' else 'Source bytes are independently bound in inputs.json'))


def predecessor():
    previous = load(BASE / 'complete.json')
    assert previous['status'] == 'PASS'
    for row in previous['receipts']:
        checked(row)
    medium, native = checked(previous['medium']), checked(previous['ELF'])
    assert sha(medium) == BASE_MEDIUM_SHA and sha(native) == BASE_ELF_SHA
    D.validate_bam(medium)
    assert len(D.visible_files(medium)) == 20
    return previous, medium


def package_specs():
    rows = copy.deepcopy(load(FROZEN_MEDIA / 'runtime-receipt.json')['packages'])
    assert len(rows) == 6
    for row in rows:
        if row['name'] == 'repl-comfort':
            row['manifest'] = bind(BASE / 'media-r6/repl-comfort.manifest.json')
        checked(row['manifest'])
        row.pop('artifact', None)
        row.pop('row', None)
    assert load(ROOT / rows[-1]['manifest']['path'])['code_bytes'] == 2095
    return rows


def image_equal(a, b):
    assert a.code == b.code and a.metadata == b.metadata, 'foreign image content'


def symbols(m):
    return {e['name'] for e in m['entries']} | {
        x['symbol'] for e in m['entries'] for x in e['literals']
        if isinstance(x, dict) and 'symbol' in x}


def source_control(generated, canonical):
    assert generated == CODEMOD.rewrite_tokens(canonical)[0], 'stale generated disk source'
    assert generated.count(NEW_FORM)==1 and OLD_FORM not in generated, 'wrong disk source'


def suite_population(suite, accepted):
    private=suite['private_inline_functions']
    assert len(private)==suite['min_private_inline_functions']==14
    assert set(suite['functions'])=={e['name'] for e in accepted['entries']}|set(private)
    assert [c['name'] for c in suite['cases']]==accepted['cases'], 'dropped/changed suite case'
    assert suite['directory_only_prefixes']==['%'] and suite['abi_profile']=='dialect-v2'


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


def price_images(a, b):
    """Only the dir-fill code object may change; no name/literal/export drift."""
    image_budget(a);image_budget(b)
    ma, mb = a.manifest, b.manifest
    assert (len(a.code), len(b.code)) == (4083, 4086), 'stale M65D price'
    assert len(ma['entries']) == len(mb['entries']) == 39
    assert max(e['length'] for e in mb['entries']) == 252 <= 255
    assert symbols(ma) == symbols(mb), 'symbol population drift'
    changed = []
    for x, y in zip(ma['entries'], mb['entries'], strict=True):
        assert x.keys() == y.keys()
        # Container offsets and lengths are derived; all other per-entry
        # metadata, including anonymous/export flags and literal lists, is exact.
        allowed = {'blob_offset', 'length', 'ext_addr'}
        assert {k:v for k,v in x.items() if k not in allowed} == {
            k:v for k,v in y.items() if k not in allowed}, ('entry metadata', x['name'])
        ax = a.code[x['blob_offset']:x['blob_offset']+x['length']]
        by = b.code[y['blob_offset']:y['blob_offset']+y['length']]
        if ax != by:
            changed.append(x['name'])
            assert (x['length'], y['length']) == (115, 118)
    assert changed == ['%m65d-dir-fill'], changed
    assert len(a.metadata) == len(b.metadata)
    return dict(status='PASS',before=len(a.code),after=len(b.code),delta=3,
                objects=39,max_object=252,changed=changed,metadata_bytes=len(b.metadata))


def emit_m65d(out, suite):
    out.mkdir()
    path = out / 'suite.json'
    save(path, {k:v for k,v in suite.items() if not k.startswith('_')})
    suite = P._read_suite(str(path))
    P.emit_artifacts(str(path), suite, str(out / 'm65d'), base_addr=0, artifact_role='disk-lib')
    return out / 'm65d.manifest.json'


def load_entry_emitter(out):
    """Reuse the frozen host ABI helper; no compiler or linker in preflight."""
    import ctypes
    source=ROOT/'build/c2-lite/product-shaped-v6-probe/c2d-v6-entry-emitter-host.so'
    pins={source:'b5f8d051c48c955ec5cfd9181f8ddf5fa199f452a8ae3fd7ce1407da6b354a2f',
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
        compilers_invoked=0,proof='Frozen shared target routine; baseline rows checked byte for byte'))


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


def delivery_control(out, files):
    proof = {}
    for name in STATIC:
        raw = (out / name).read_bytes()
        assert raw == (FROZEN_PLANE / name).read_bytes(), ('baseline reproduction', name)
        delivered = files[name.encode()]
        if name == 'CODE.BIN':
            assert delivered[:len(raw)] == raw
        elif name == 'C2D.BIN':
            assert len(raw) == 33840 and len(delivered) == 50816
            assert delivered == raw + bytes(len(delivered)-len(raw))
        else:
            assert delivered == raw
        proof[name] = dict(reproduced=bind(out/name),delivered_bytes=len(delivered),
                           delivered_sha256=sha(delivered))
    return proof


def envelope_control(old, new, image, old_id, new_id):
    a = EXT.decode_extension(old, image, expected_build_id=old_id)
    b = EXT.decode_extension(new, image, expected_build_id=new_id)
    assert old[:22] == new[:22] and old[26:] == new[26:], 'package content drift'
    assert len(old) == len(new) and a.combined_crc == b.combined_crc


def packages(out, files, old_id, new_id):
    old_rows = L.decode_index(files[b'L65INDEX'])
    rows, records, payloads = [], [], {}
    for spec in package_specs():
        name = spec['name']
        print('reproducing/rebinding package '+name,flush=True)
        old = next(r for r in old_rows if r['name'] == name)
        args = (name, name, spec['shelf'], ROOT/spec['manifest']['path'],
                tuple(spec['dependencies']), old['track'], old['sector'])
        row, baseline = PK.measured_row(*args, product_build_id=old_id)
        assert row == old and baseline == files[name.upper().encode()], ('baseline package', name)
        newrow, candidate = PK.measured_row(*args, product_build_id=new_id)
        assert newrow == old, 'index row drift'
        image = F.emit_image(name, spec['shelf'], ROOT/spec['manifest']['path'])
        envelope_control(baseline, candidate, image, old_id, new_id)
        for side, data in [('baseline',baseline),('candidate',candidate)]:
            once(out/side/(name+'.l65s'), data)
        once(out/'loader'/(name+'.code.bin'), image.code)
        once(out/'loader'/(name+'.c2i.bin'), image.metadata)
        rows.append(newrow); payloads[name] = candidate
        records.append(dict(**spec,baseline=bind(out/'baseline'/(name+'.l65s')),
                            candidate=bind(out/'candidate'/(name+'.l65s')),
                            code=bind(out/'loader'/(name+'.code.bin')),
                            metadata=bind(out/'loader'/(name+'.c2i.bin')),row=newrow))
    assert L.encode_index(rows) == files[b'L65INDEX'], 'index must remain exact'
    assert L.decode_index(files[b'L65INDEX'], payloads, artifact_build_id=new_id) == rows
    return records


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


def capacity(product, geometry, records, old_image, new_image):
    frozen = load(BASE/'capacity.json')
    used = {k:base+sum(r['row'][field] for r in records) for k,field,base in [
        ('code','bank2',geometry['code_bytes']),('entries','entries',product['entries']),
        ('resolutions','resolutions',product['resolutions']),('roots','roots',product['roots']),('images','images',6)]}
    assert used == {**frozen['used'],'code':frozen['used']['code']+3}, used
    assert all(used[k] <= frozen['limits'][k] for k in used)
    scratch = sum(r['row']['scratch'] for r in records)
    assert scratch == frozen['entry_scratch_sum'] <= frozen['entry_scratch_limit']
    assert symbols(old_image.manifest) == symbols(new_image.manifest)
    # All other loader images and all native source are frozen; equal names
    # make the accepted r6 symbol/namepool measurement applicable unchanged.
    syms = copy.deepcopy(frozen['symbols'])
    for row in syms['inputs']:
        checked(row)
    assert syms['limits']['symbols']-syms['used']['symbols'] >= 32
    assert syms['limits']['namepool']-syms['used']['namepool'] >= 384
    return dict(status='PASS',used=used,limits=frozen['limits'],entry_scratch_sum=scratch,
                entry_scratch_limit=frozen['entry_scratch_limit'],symbols=syms,
                symbol_proof='Exact old/new M65D name sets; five static and six package loader images exact')


def report(out, result=None, error=None):
    if error:
        text = ('# Seed r7 — Chunk A\n\nDeutsche Zusammenfassung: **HALT**. '
                'Kein Link und kein Medienlauf ausgeführt. Baseline-Reproduktion: '
                + ('PASS' if (out/'baseline-reproduction.json').exists() else 'FAIL / nicht abgeschlossen')
                + '.\n\nFehler: `'+repr(error)+'`\n\n'
                'Der vorhandene Versuch bleibt erhalten; Fortsetzung benötigt einen explizit benannten Nachfolger.\n')
    else:
        c = result['constants']; p = result['price']
        text = ('# Seed r7 — Chunk A\n\nDeutsche Zusammenfassung: **Baseline-Reproduktion PASS** '
                '(drei statische Dateien gegen r6-Auslieferung, sechs Paket-Loader bytegenau). '
                f'M65D: **{p["before"]} → {p["after"]} Byte (+{p["delta"]})**, '
                '39 Objekte, größtes Objekt 252 Byte. Nur `%m65d-dir-fill` wächst von 115 auf 118 Byte. '
                'Kein Produkt-Compiler/Link und kein Medienlauf ausgeführt. Der kanonische '
                '`MK_BCODE`-Host-ABI-Helfer wurde für die C2D-Reproduktion gebaut und ausgeführt; '
                'der eingefrorene C2D-Entry-Helfer wurde hashgeprüft wiederverwendet.\n\n'
                f'Neue statische Build-ID: **{c["LISP65_C2_PRODUCT_BUILD_ID"]}**. '
                'Alle sechs Pakete sind gegen diese ID neu umhüllt; Code und C2I bleiben exakt, '
                'einschließlich r6 Comfort mit 2.095 Byte. L65INDEX bleibt exakt.\n\n'
                '| Zu linkende Konstante | Wert |\n| --- | --- |\n'
                + ''.join(f'| `{k}` | `{c[k]}` |\n' for k in (
                    'LISP65_C2_PRODUCT_BUILD_ID','LISP65_C2_PRODUCT_SHELF_BYTES','LISP65_C2_LITE_STATIC_CODE_BYTES'))
                + '\n' + ''.join('`c2_phase02a_'+r['table']+'_crc16`: '+', '.join(f'0x{x:04x}' for x in r['after'])+'\n\n' for r in c['crc_tables'])
                + f'Gesamtkapazität Code: {result["capacity"]["used"]["code"]}/60758 Byte; '
                  'Entries/Resolutions/Roots/Images: 865/3723/620/12; Entry-Scratch: 632/16912.\n\n'
                'Chunk C, ausschließlich nach Reviewer-Freigabe aus dem Repository-Root:\n\n'
                '```sh\n'+CHUNK_C+'\n```\n\n'
                'Der Befehl beansprucht `build/o2-lite-product-r7/` einmalig und führt '
                'Native-Vorbereitung, genau einen Produkt-Link, Attribution, Medienableitung, '
                'vollständigen Readback und Abschluss aus. Unklassifizierte Native-Änderungen '
                'halten den Versuch vor dem Medienlauf an; zusätzliche Codegen-/Adressverschiebungen '
                'benötigen dann eine geprüfte Attributionsregel und einen benannten Nachfolgeversuch. '
                'Es wird keine native Byteidentität vorausgesetzt.\n\n'
                'Offen: Chunk B, unabhängige Review-Freigabe, tatsächlicher Native-/Medienlauf samt '
                'gemessenen Deltas, Zielsystemtests und Release-Admission. '
                'Dieser Bericht behauptet keinen Seed-/Target-PASS.\n\n'
                f'Quellenstand: angefordert `{result["source_revision"]["requested"]}`, '
                f'beobachtet `{result["source_revision"]["observed"]}`. '
                f'{result["source_revision"]["note"]}.\n')
    if result and 'selftest' in result:
        text+='\nSelftest: **PASS**, '+str(result['negative_controls'])+' abgewiesene Negativkontrollen; `build/o2-lite-r7-selftest/receipt.json`.\n'
    once(out/'report.md', text)


def preflight(out=PREFLIGHT):
    assert not out.exists(), 'preflight is write-once; choose an explicitly named successor'
    out.mkdir(parents=True)
    save(out/'attempt.json',dict(status='STARTED',producer=bind(Path(__file__)),native_links=0))
    try:
        revision=source_revision()
        previous, medium = predecessor()
        files = D.visible_files(medium)
        frozen = load(FROZEN_PLANE/'product/substitution-artifacts.json')
        for row in frozen['manifests']:
            checked(row)
        manifests = [ROOT/r['path'] for r in frozen['manifests']]
        closure = CODEMOD.generate(ROOT/'config/v2-workbench-artifact-closure.json',out/'closure')
        suite = P._read_suite(str(out/'closure/suites/p0-m65d-lib.json'))
        current = ROOT/suite['sources'][0]
        assert current.is_relative_to(out)
        text = current.read_text()
        source_control(text,(ROOT/'lib/m65-disk.lisp').read_text())
        suite_population(suite,load(manifests[3]))
        old_source = out/'baseline-m65-disk.lisp'
        once(old_source,text.replace(NEW_FORM,OLD_FORM))
        # Use the accepted resident owner, not the regenerated current resident.
        resident = load(manifests[0])['suite']
        suite['resident_suite'] = resident
        baseline_suite = dict(suite,sources=[str(old_source)])
        baseline_m = emit_m65d(out/'emission-baseline',baseline_suite)
        accepted = F.emit_image('m65d','m65d',manifests[3])
        replay = F.emit_image('m65d','m65d',baseline_m)
        image_equal(accepted,replay)
        load_entry_emitter(out)
        before, old_geometry, baseline_images = plane(out/'planes/baseline',manifests[:3]+[baseline_m]+manifests[4:])
        assert before['product_build_id_hex'] == frozen['product_build_id_hex']
        static_proof = delivery_control(out/'planes/baseline',files)
        # Baseline package replay is completed before candidate emission.
        baseline_packages = packages(out/'baseline-package-replay',files,before['product_build_id_u32'],before['product_build_id_u32'])
        save(out/'baseline-reproduction.json',dict(status='PASS',static=static_proof,packages=baseline_packages,
                                                  predecessor=bind(BASE/'complete.json')))
        print('baseline static plane and all six package loaders: PASS',flush=True)
        candidate_m = emit_m65d(out/'emission-candidate',suite)
        candidate_image = F.emit_image('m65d','m65d',candidate_m)
        price = price_images(replay,candidate_image)
        ext_before=(out/'emission-baseline/m65d.ext.bin').stat().st_size
        ext_after=(out/'emission-candidate/m65d.ext.bin').stat().st_size
        assert (ext_before,ext_after)==(6573,6576)
        price.update(legacy_external_before=ext_before,legacy_external_after=ext_after)
        after, geometry, candidate_images = plane(out/'planes/candidate',manifests[:3]+[candidate_m]+manifests[4:])
        for index in (0,1,2,4,5):
            image_equal(baseline_images[index],candidate_images[index])
        assert after['product_build_id_u32'] != before['product_build_id_u32']
        records = packages(out/'packages',files,before['product_build_id_u32'],after['product_build_id_u32'])
        const = constants(out/'planes',before,after,old_geometry,geometry)
        cap = capacity(after,geometry,records,replay,candidate_image)
        deltas = {n:(out/'planes/candidate'/n).stat().st_size-(out/'planes/baseline'/n).stat().st_size for n in STATIC}
        assert deltas == {'CODE.BIN':3,'C2D.BIN':0,'SHELF.BIN':3}
        result = dict(status='PASS',source_revision=revision,baseline_reproduction='PASS',predecessor=bind(BASE/'complete.json'),
                      price=price,capacity=cap,constants=const,packages=records,static_deltas=deltas,
                      native_links=0,media_transactions=0,host_ABI_probe_commands=HOST_HELPER_COMMANDS,chunk_c_command=CHUNK_C,closure=bind(closure))
        for name,value in [('price.json',price),('capacity.json',cap),('constants.json',const)]:
            save(out/name,value)
        # Freeze every consumed input, including all imported host modules, so
        # Chunk B can proceed independently without silently changing this lane.
        inputs = {Path(__file__).resolve(), BASE/'complete.json', FROZEN_PLANE/'product/substitution-artifacts.json'}
        inputs.update(ROOT/r['path'] for r in load(closure)['inputs'])
        inputs.update(manifests)
        for spec in package_specs():
            inputs.add(ROOT/spec['manifest']['path'])
        for path in list(inputs):
            if path.name.endswith('.manifest.json'):
                inputs.add(Path(load(path)['blob']))
        import comfort_default_media as C  # bind deferred native/media helper closure
        inputs.update([F.CONTRACT,F.RECURSIVE,F.SYMBOL,F.SESSION,ROOT/'src/obj.h',
            ROOT/'scripts/c2d-v6-entry-host.c',ROOT/'src/c2d_v6_entry.h',
            C.M.STAGER_S,C.M.STAGER_ROM_S,
            *[C.BASE/'packed'/n for n in ('delivery-population.json','delivery-stager-main.c','delivery-roles.h')]])
        for fam in ('boot','session'):
            value=load(FROZEN_MEDIA/('runtime-overlays-'+fam+'-final.json'))
            inputs.add(FROZEN_MEDIA/value['overflow_storage']['file'])
        # Stager's host-generated assembler constants consume this explicit contract.
        inputs.add(C.M.ASM_CONTRACT.CONTRACT)
        for module in tuple(sys.modules.values()):
            filename = getattr(module,'__file__',None)
            if filename and Path(filename).resolve().is_relative_to(ROOT/'tools/host-lisp'):
                inputs.add(Path(filename).resolve())
        commands, native_rows, native_tools = native_inputs()
        save(out/'native-input-bindings.json',dict(recipe=bind(FROZEN_NATIVE/'command-proof.json'),inputs=native_rows,toolchain=native_tools))
        inputs.update(ROOT/r['path'] for r in native_rows+native_tools)
        inputs.add(ROOT/'src/obj.h')
        inputs.add(Path('/usr/bin/cc'))
        inputs.add(FROZEN_NATIVE/'command-ready.json')
        inputs.add(FROZEN_NATIVE/'command-proof.json')
        inputs.add(FROZEN_NATIVE/'derived-inputs.json')
        inputs.update(FROZEN_MEDIA/n for n in ('runtime-receipt.json','runtime-overlays-boot-final.json',
                       'runtime-overlays-session-final.json','kernal-window-publish-last.json'))
        for row in load(closure)['inputs']:
            assert sha((ROOT/row['path']).read_bytes())==row['sha256'], 'source raced closure generation'
        save(out/'inputs.json',[bind(p) for p in sorted(inputs)])
        result['inputs'] = bind(out/'inputs.json')
        if out==PREFLIGHT:
            tests=load(SELFTEST/'receipt.json')
            assert tests['status']=='PASS' and tests['producer']==bind(Path(__file__))
            assert load(out/'attempt.json')['producer']==bind(Path(__file__))
            result['selftest']=bind(SELFTEST/'receipt.json')
            result['negative_controls']=len(tests['rejected'])
        result['artifacts'] = [bind(p) for p in sorted(out.rglob('*')) if p.is_file()]
        save(out/'receipt.json',result)
        report(out,result)
        return {k:result[k] for k in ('status','baseline_reproduction','price','static_deltas','native_links','media_transactions')}
    except BaseException as error:
        save(out/'halt.json',dict(status='HALT',error=repr(error)))
        report(out,error=error)
        raise


def verify_preflight():
    r = load(PREFLIGHT/'receipt.json')
    assert r['status'] == 'PASS' and r['baseline_reproduction'] == 'PASS'
    checked(r['inputs'])
    for row in load(PREFLIGHT/'inputs.json') + r['artifacts']:
        checked(row)
    predecessor()
    return r


def project_delivery_code(delivered, baseline, candidate):
    assert delivered[:len(baseline)] == baseline, 'wrong static baseline'
    assert len(candidate)-len(baseline) == 3 and len(candidate) <= 60758, 'wrong static growth'
    assert not any(delivered[len(baseline):len(candidate)]), 'native suffix overlap'
    result = bytearray(delivered)
    result[:len(candidate)] = candidate
    assert result[len(candidate):] == delivered[len(candidate):]
    return bytes(result)


def classified(before, after, domains):
    result = S.classify_bytes(before,after,domains)
    assert result['unclassified_bytes'] == 0, 'unclassified media change'
    return result


def selftest(out=SELFTEST):
    assert not out.exists(), 'selftest output is write-once'
    out.mkdir(parents=True)
    save(out/'attempt.json',dict(status='STARTED',producer=bind(Path(__file__))))
    rejected = []
    def reject(name, fn):
        try:
            fn()
        except (AssertionError,FileExistsError,EXT.ProbeError,L.GateError):
            rejected.append(name)
        else:
            raise AssertionError('negative survived: '+name)
    previous, medium = predecessor()
    files = D.visible_files(medium)
    old_id = load(FROZEN_PLANE/'product/substitution-artifacts.json')['product_build_id_u32']
    new_id = old_id ^ 0x100
    for spec in package_specs():
        name = spec['name']; print('selftest package '+name,flush=True); image = F.emit_image(name,spec['shelf'],ROOT/spec['manifest']['path'])
        old = files[name.upper().encode()]
        new = EXT.build_extension(image,build_id=new_id)
        envelope_control(old,new,image,old_id,new_id)
        reject('old-ID package '+name,lambda:EXT.decode_extension(old,image,expected_build_id=new_id))
        reject('new-ID package on old plane '+name,lambda:EXT.decode_extension(new,image,expected_build_id=old_id))
        bad = bytearray(new); bad[-1] ^= 1
        reject('changed loader '+name,lambda:envelope_control(old,bytes(bad),image,old_id,new_id))
    rows = L.decode_index(files[b'L65INDEX'])
    payloads = {s['name']:EXT.build_extension(F.emit_image(s['name'],s['shelf'],ROOT/s['manifest']['path']),build_id=new_id) for s in package_specs()}
    for name in payloads:
        bad = dict(payloads);bad[name] = files[name.upper().encode()]
        reject('one un-rebound package '+name,lambda:L.decode_index(files[b'L65INDEX'],bad,artifact_build_id=new_id))
    path=out/'write-once-control';once(path,b'one')
    reject('write-once overwrite',lambda:once(path,b'two'))
    reject('write-once identical retry',lambda:once(path,b'one'))
    baseline=b'base'; candidate=b'newbase'; delivered=baseline+bytes(9)+b'native'
    assert project_delivery_code(delivered,baseline,candidate)[7:] == delivered[7:]
    reject('wrong baseline',lambda:project_delivery_code(b'X'+delivered[1:],baseline,candidate))
    reject('stale growth',lambda:project_delivery_code(delivered,baseline,candidate+b'X'))
    reject('native overlap',lambda:project_delivery_code(baseline+b'X'+delivered[5:],baseline,candidate))
    reject('unclassified byte',lambda:classified(b'a',b'b',{}))
    reject('wrong classified pair',lambda:classified(b'a',b'b',{0:(97,99,'owner')}))
    reject('foreign static image',lambda:image_equal(type('Image',(),dict(code=b'a',metadata=b'm'))(),type('Image',(),dict(code=b'b',metadata=b'm'))()))
    frozen=ROOT/load(FROZEN_PLANE/'product/substitution-artifacts.json')['manifests'][3]['path']
    old_image=F.emit_image('m65d','m65d',frozen)
    image_budget(old_image)
    bad=copy.deepcopy(old_image);bad.manifest['entries'][0]['length']=256
    reject('256-byte object',lambda:image_budget(bad))
    bad=copy.deepcopy(old_image);bad.manifest['code_bytes']+=1
    reject('stale M65D byte price',lambda:image_budget(bad))
    bad=copy.deepcopy(old_image);bad.manifest['entries'].pop()
    reject('dropped M65D object',lambda:image_budget(bad))
    reject('old M65D image as candidate',lambda:price_images(old_image,old_image))
    canonical=(ROOT/'lib/m65-disk.lisp').read_text()
    generated=CODEMOD.rewrite_tokens(canonical)[0]
    source_control(generated,canonical)
    reject('stale generated source',lambda:source_control(generated.replace(NEW_FORM,OLD_FORM),canonical))
    reject('wrong canonical disk source',lambda:source_control(generated,canonical+'; changed'))
    suite=P._read_suite(str(ROOT/load(frozen)['suite']))
    suite_population(suite,load(frozen))
    bad=copy.deepcopy(suite);bad['cases'].pop()
    reject('dropped test row',lambda:suite_population(bad,load(frozen)))
    # The complete media transaction is not run by selftest; classification and
    # package decoding use in-memory controls and leave r6 untouched.
    result=dict(status='PASS',producer=bind(Path(__file__)),rejected=rejected,native_links=0,media_transactions=0)
    save(out/'receipt.json',result)
    return result


def native_inputs():
    """Read and verify the exact recipe that produced the r4/r5/r6 ELF."""
    recipe = load(FROZEN_NATIVE/'command-proof.json')
    derivation = load(FROZEN_NATIVE/'derived-inputs.json')
    ready = load(FROZEN_NATIVE/'command-ready.json')
    rows = derivation['all_generated'] + [derivation['generated']]
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
    return commands, rows, tools


def prepare_native(preflight):
    """Pure file derivation followed by audited include preprocessing in Chunk C."""
    commands, sources, toolchain = native_inputs()
    const = preflight['constants']
    HERE.mkdir()
    oldprefix = str((FROZEN_NATIVE/'candidate-inputs').relative_to(ROOT))
    oldderived = str((FROZEN_NATIVE/'derived').relative_to(ROOT))
    newprefix = str((HERE/'candidate-inputs').relative_to(ROOT))
    newderived = str((HERE/'derived').relative_to(ROOT))
    path_replacements = {oldprefix:newprefix,oldderived:newderived,'build/o2-lite-product-r4':str(BUILD.relative_to(ROOT))}
    before = const['before_product']
    substitutions = {
        '-DLISP65_C2_PRODUCT_BUILD_ID='+before['product_build_id_hex']+'UL':
        '-DLISP65_C2_PRODUCT_BUILD_ID='+const['LISP65_C2_PRODUCT_BUILD_ID']+'UL',
        '-DLISP65_C2_PRODUCT_SHELF_BYTES='+str(before['artifacts']['shelf']['bytes'])+'UL':
        '-DLISP65_C2_PRODUCT_SHELF_BYTES='+str(const['LISP65_C2_PRODUCT_SHELF_BYTES'])+'UL'}
    assert all(any(k in cmd for cmd in commands) for k in substitutions)
    def rebase(value):
        for a,b in path_replacements.items():
            value = value.replace(a,b)
        return value
    updated = [[rebase(substitutions.get(arg,arg)) for arg in cmd] for cmd in commands]
    generated, changes, native = [], [], []
    table_source = commands[29][commands[29].index('-c')+1]
    crc_generated = None
    old_code = const['before_geometry']['code_bytes']
    new_code = const['after_geometry']['code_bytes']
    assert (old_code,new_code) == (50060,50063)
    for row in sources:
        path = ROOT/row['path']; raw = checked(row); new = raw
        target = ROOT/rebase(row['path'])
        assert target.is_relative_to(HERE) and target != path
        seams = []
        if row['path'] == table_source:
            text = raw.decode()
            for table in const['crc_tables']:
                def assembly(values):
                    return 'c2_phase02a_'+table['table']+'_crc16:\\n'+'\\n'.join(f'.short 0x{x:04x}' for x in values)+'\\n'
                old, replacement = assembly(table['before']),assembly(table['after'])
                assert text.count(old) == 1, 'CRC source seam'
                text = text.replace(old,replacement)
                seams.append(dict(kind='CRC16 table',**table))
            new = text.encode(); crc_generated = target
        elif path.name == 'c2_lite_static_plane.h':
            old = f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {old_code}UL'.encode()
            replacement = f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {new_code}UL'.encode()
            # Historical copies in the input closure carry older plane sizes
            # (e.g. 45939, 50007); only the live 50060 definition is rebound.
            assert raw.count(old) in (0, 1)
            if raw.count(old) == 1:
                new = raw.replace(old,replacement);seams.append(dict(kind='static code size',before=old.decode(),after=replacement.decode()))
        elif path.name.endswith('.compiler-input-assert.h'):
            old = f'LISP65_C2_LITE_STATIC_CODE_BYTES != {old_code}UL'.encode()
            replacement = f'LISP65_C2_LITE_STATIC_CODE_BYTES != {new_code}UL'.encode()
            assert raw.count(old) in (0, 1)
            if raw.count(old) == 1:
                new = raw.replace(old,replacement);seams.append(dict(kind='compiler assertion',before=old.decode(),after=replacement.decode()))
        else:
            assert new == raw
        # Resident source/header and every other native input remain exact.
        if path.name == 'stdlib-p0.h':
            assert new == raw
        once(target,new)
        generated.append(bind(target));native.append(dict(source=row,restored=bind(target)))
        if seams:
            changes.append(dict(before=row,after=bind(target),seams=seams))
    assert crc_generated is not None
    assert {'c2_lite_static_plane.h'} <= {Path(r['after']['path']).name for r in changes}
    for row in toolchain:
        native.append(dict(source=row,restored=row))
    # Every -o, map and LTO output resolves inside this attempt. No Make graph.
    for command in updated:
        output = ROOT/command[command.index('-o')+1]
        assert output.is_relative_to(BUILD)
        assert not any(x in ' '.join(command).lower() for x in ('xemu','ssh ','curl ','wget ','make '))
    save(HERE/'derived-inputs.json',dict(generated=bind(crc_generated),all_generated=generated,
        crc_tables=const['crc_tables'],header_changes=changes,stdlib_header_changed=False,
        code_bytes_before=old_code,code_bytes_after=new_code,replacements=substitutions))
    save(HERE/'command-proof.json',dict(commands=updated,frozen=bind(FROZEN_NATIVE/'command-proof.json'),
        allowed_substitutions=substitutions,path_replacements=path_replacements,source_changes=changes))
    save(HERE/'plane-price.json',dict(before_product=const['before_product'],after_product=const['after_product'],
        artifacts=[bind(PREFLIGHT/'planes'/side/name) for side in ('baseline','candidate') for name in STATIC]))
    ready = dict(native=native,toolchain=toolchain,commands=bind(HERE/'command-proof.json'))
    S.HERE = HERE
    S.include_closure(updated,ready)
    save(HERE/'command-ready.json',ready)
    return updated


def inventory():
    """Attribute exact constant/CRC bytes; unexpected codegen stays FIRST RED.

    r4's hardcoded old-to-r4 overlay shrink rules are intentionally inapplicable.
    All sections/symbols are inventoried before a strict projection is attempted.
    A geometry/codegen change is never excused as an arbitrary changed section.
    """
    from elf_truth import ElfTruth
    paths = [BASE/'wplto/resident-island-seed.prg.elf',BUILD/'wplto/resident-island-seed.prg.elf']
    truths = [ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in paths]
    a,b = truths
    from dataclasses import asdict
    save(HERE/'section-symbol-inventory.json',dict(
        ELFs=[bind(p) for p in paths],before_sections=[asdict(s) for s in a.sections],
        after_sections=[asdict(s) for s in b.sections],before_symbols=[asdict(s) for s in a.symbols],
        after_symbols=[asdict(s) for s in b.symbols],
        changed_sections=[s.name for s in a.sections if s.name in {t.name for t in b.sections}
                          and s.section_type not in ('SHT_NOBITS','SHT_NULL')
                          and a.section_bytes(s.name)!=b.section_bytes(s.name)]))
    assert b.symbol('lisp65_comfort_state').value == 0xbff6
    # S's unchanged-geometry path classifies only known immediate operands and
    # six-image CRC arrays and compares every physical ELF byte. It cannot use
    # the historical strings/r4 movement rules for this successor.
    assert a.sections == b.sections, 'new native geometry needs reviewed exact attribution; inspect section-symbol-inventory.json'
    S.HERE = HERE
    result = S.inventory_analysis(paths,[p.read_bytes() for p in paths],truths)
    result.update(ELFs=[bind(p) for p in paths],plane=bind(HERE/'plane-price.json'),
                  derived=bind(HERE/'derived-inputs.json'),section_inventory=bind(HERE/'section-symbol-inventory.json'))
    save(HERE/'inventory.json',result)
    assert result['status']=='PASS' and result['unclassified_bytes']==0, 'unclassified native codegen'
    return result


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


def pack_media(med,artifacts,before_raw,records,build_id,derived):
    """One complete r6 -> r7 transaction; every change has an exact byte pair."""
    before = D.visible_files(before_raw)
    expected = {name:(artifacts/name.decode().lower()).read_bytes() for name in before}
    assert len(expected)==20
    assert expected[b'INIT.L65']==before[b'INIT.L65']
    assert expected[b'L65INDEX']==before[b'L65INDEX']
    assert set(derived) <= {n.encode() for n in NATIVE_FILES}
    assert derived == {n:expected[n] for n in derived} and all(derived[n]!=before[n] for n in derived)
    baseline=(PREFLIGHT/'planes/baseline/CODE.BIN').read_bytes()
    candidate=(PREFLIGHT/'planes/candidate/CODE.BIN').read_bytes()
    assert expected[b'CODE.BIN']==project_delivery_code((med/'code-native-rebound.bin').read_bytes(),baseline,candidate)
    assert expected[b'SHELF.BIN']==(PREFLIGHT/'planes/candidate/SHELF.BIN').read_bytes()
    initial=(PREFLIGHT/'planes/candidate/C2D.BIN').read_bytes()
    assert expected[b'C2D.BIN']==initial+bytes(50816-len(initial))
    permitted = {n.encode() for n in STATIC}|set(derived)|{r['name'].upper().encode() for r in records}
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
    # replace_file preserves first-sector locators; all six rows must be exact.
    assert L.encode_index(rows)==before[b'L65INDEX'], 'unexpected index locator/content drift'
    assert L.decode_index(expected[b'L65INDEX'],payloads,artifact_build_id=build_id)==rows
    final=med/'o2lite.d81';once(final,raw)
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
    assert {r['owner'] for r in diff['rows']} <= {name+': '+kind for name in changed for kind in ('file-chain','directory','BAM')}
    save(med/'classified-byte-ledger.json',dict(entries=[dict(offset=i,before=x,after=y,owner=owner) for i,(x,y,owner) in sorted(domains.items())]))
    save(med/'d81-byte-diff.json',diff)
    return dict(status='PASS',medium=bind(final),predecessor_medium=bind(ROOT/load(BASE/'complete.json')['medium']['path']),
        files={n.decode():dict(bytes=len(v),sha256=sha(v)) for n,v in expected.items()},
        changed_files=changed,every_file_read_back=True,index_exact=True,INIT_exact=True,
        index_rows=rows,unclassified_bytes=0,diff=bind(med/'d81-byte-diff.json'),
        ledger=bind(med/'classified-byte-ledger.json'),mutations=mutations)


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


def media():
    import comfort_default_media as C
    pre = verify_preflight()
    inv = load(HERE/'inventory.json')
    assert inv['status']=='PASS' and inv['unclassified_bytes']==0
    for row in inv['ELFs']:
        checked(row)
    previous,before_raw=predecessor()
    before=D.visible_files(before_raw)
    delivery_control(PREFLIGHT/'planes/baseline',before)
    med = BUILD/'media-r7'
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
    save(med/'runtime-receipt.json',dict(status='PASS',ELF=bind(elf),families=families,
        boot_geometry=geometry,product_build_id=build_id,packages=records,comfort_bank2_bytes=2095))
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
    C.stager()
    # These payloads were reconstructed above from the classified ELF, its
    # publish-last bindings, frozen package manifests and cold stager. Bind
    # their exact bytes before entering the disk transaction. INIT stays fixed.
    derived={n.encode():(artifacts/n.lower()).read_bytes() for n in NATIVE_FILES
             if (artifacts/n.lower()).read_bytes()!=before[n.encode()]}
    save(med/'derived-file-bindings.json',[bind(artifacts/n.decode().lower()) for n in derived])
    result=pack_media(med,artifacts,before_raw,records,build_id,derived)
    result['native_bindings']=bind(med/'runtime-receipt.json')
    result['stager']=bind(med/'descriptor-stager-receipt.json')
    save(BUILD/'media.json',result)
    return result



def finish(pre):
    medium=load(BUILD/'media.json')
    inv=load(HERE/'inventory.json')
    assert medium['status']=='PASS' and medium['unclassified_bytes']==0
    assert inv['status']=='PASS' and inv['unclassified_bytes']==0
    checked(medium['medium'])
    save(BUILD/'price.json',dict(**pre['price'],static_deltas=pre['static_deltas'],
        native_ELF_bytes_before=inv['ELFs'][0]['bytes'],native_ELF_bytes_after=inv['ELFs'][1]['bytes']))
    save(BUILD/'capacity.json',pre['capacity'])
    save(BUILD/'source.json',dict(status='PASS',preflight=bind(PREFLIGHT/'receipt.json'),
        inputs=pre['inputs'],committed_source_admission='OPEN; no Git writes'))
    save(BUILD/'inventory.json',inv)
    save(BUILD/'negative-controls.json',load(SELFTEST/'receipt.json'))
    complete=dict(status='PASS',seed=1,final=0,product_links=1,medium=medium['medium'],
        ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf'),emulator_runs=0,device_contacts=0,
        receipts=[bind(BUILD/n) for n in ('price.json','capacity.json','source.json','inventory.json','media.json','negative-controls.json')],
        claim='Host/native/media Seed only; target acceptance and release admission remain open')
    save(BUILD/'seed.json',complete);save(BUILD/'complete.json',complete)
    return complete


def seed():
    pre=verify_preflight()
    tests=load(SELFTEST/'receipt.json')
    assert tests['status']=='PASS' and tests['producer']==bind(Path(__file__))
    assert not BUILD.exists(), 'write-once r7 attempt already claimed; no retry'
    BUILD.mkdir()
    save(BUILD/'attempt.json',dict(status='STARTED',producer=bind(Path(__file__)),
        predecessor=bind(BASE/'complete.json'),preflight=bind(PREFLIGHT/'receipt.json')))
    try:
        commands=prepare_native(pre)
        for i,command in enumerate(commands):
            if i==74:
                save(BUILD/'product-link-claim.json',dict(product_links=1,command=command))
            (ROOT/command[command.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
            S.run(command,BUILD/f'command-{i:03d}.log')
            print(f'completed frozen command {i+1}/75',flush=True)
        save(BUILD/'linked.json',dict(status='LINKED',product_links=1,
            ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf')))
        inventory()
        media()
        return finish(pre)
    except BaseException as error:
        save(BUILD/'halt.json',dict(status='HALT',error=repr(error),
            product_link_claimed=(BUILD/'product-link-claim.json').exists(),
            note='No in-place retry. Retain this attempt and review a named successor.'))
        raise


def guard(root, *, host_only):
    """Enforce the audited write boundary, even inside imported generators."""
    temporary = Path(tempfile.gettempdir()).resolve()
    helper_executables = set()
    def audit(event,args):
        # Python 3.14 subprocess uses os.posix_spawn internally; process
        # creation stays gated by the subprocess.Popen audit event below.
        if event.startswith('socket.') or event in ('os.system','os.exec'):
            raise RuntimeError('forbidden operation: '+event)
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


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    assert not sys.flags.optimize, 'assertions are mandatory'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','selftest','seed'])
    parser.add_argument('--output',type=Path,help='explicit named successor for preflight/selftest; never an in-place retry')
    args=parser.parse_args()
    assert args.action!='seed' or args.output is None
    root=(args.output.resolve() if args.output else {'preflight':PREFLIGHT,'selftest':SELFTEST,'seed':BUILD}[args.action])
    assert root.is_relative_to(ROOT/'build') and root!=ROOT/'build'
    assert not any(root.is_relative_to(p) for p in (BASE,FROZEN_PLANE,FROZEN_NATIVE,FROZEN_MEDIA))
    assert args.action=='seed' or root.relative_to(ROOT/'build').parts[0].startswith('o2-lite-r7-')
    existed=root.exists()
    guard(root,host_only=args.action!='seed')
    try:
        result=seed() if args.action=='seed' else globals()[args.action](root)
    except BaseException as error:
        if not existed and root.exists() and not (root/'halt.json').exists():
            save(root/'halt.json',dict(status='HALT',error=repr(error)))
        raise
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
