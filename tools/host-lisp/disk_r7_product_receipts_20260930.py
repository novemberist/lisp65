"""Read-only r7 plane/media consumer. Receipt build is deferred until Chunk C.

Never calls the producer, linker, emulator, or device. Missing complete.json is
a hard failure, not a source-only substitute for product evidence.
"""
import argparse
import copy
import json
from pathlib import Path
import disk_r7_consumers_20260930 as C
import strings_seed_producer as S
import d81_persistence_fault as D
import c2_full_emission as F
import c2_session_extension_probe as EXT
import c2_require_resolver_gate as INDEX

ROOT = C.ROOT
BASE = ROOT / 'build/o2-lite-product-r6/complete.json'
COMPLETE = ROOT / 'build/o2-lite-product-r7c/complete.json'
RECEIPT = ROOT / 'config/disk-r7-product-receipt-20260930.json'


def require(ok, why):
    C.require(ok, why)


def price_check(value):
    require((value['before'], value['after'], value['delta']) == (4083, 4086, 3),
            'stale M65D product price')


def foreign_check(old_code, old_metadata, code, metadata):
    require(old_code == code and old_metadata == metadata, 'foreign static image change')


def load_bound(row):
    return json.loads(S.checked(row))


def ledger_check(before, after, entries):
    require(len({r['offset'] for r in entries}) == len(entries), 'duplicate byte owner')
    domains = {r['offset']: (r['before'], r['after'], r['owner']) for r in entries}
    result = S.classify_bytes(before, after, domains)
    require(result['unclassified_bytes'] == 0, 'unclassified disk-byte change')
    return result


def reject(name, fn):
    try:
        fn()
    except (ValueError, AssertionError, EXT.ProbeError, INDEX.GateError):
        return name
    raise ValueError('mutation survived: ' + name)


def selftest():
    """Pre-C controls use r6 bytes with a deliberately distinct synthetic ID."""
    C.source_controls()
    old = json.loads(BASE.read_bytes())
    files = D.visible_files(S.checked(old['medium']))
    product = json.loads((ROOT / 'build/o2-lite-r4-slots-preflight/planes/candidate/product/substitution-artifacts.json').read_bytes())
    old_id = product['product_build_id_u32']
    new_id = old_id ^ 0x100
    specs = json.loads((ROOT / 'build/o2-lite-product-r4/media-r4/runtime-receipt.json').read_bytes())['packages']
    mutations = []
    for spec in specs:
        name = spec['name']
        manifest = (ROOT / 'build/o2-lite-product-r6/media-r6/repl-comfort.manifest.json'
                    if name == 'repl-comfort' else ROOT / spec['manifest']['path'])
        image = F.emit_image(name, spec['shelf'], manifest)
        original = files[name.upper().encode()]
        EXT.decode_extension(original, image, expected_build_id=old_id)
        candidate = EXT.build_extension(image, build_id=new_id)
        EXT.decode_extension(candidate, image, expected_build_id=new_id)
        mutations.append(reject('un-rebound ' + name,
            lambda: EXT.decode_extension(original, image, expected_build_id=new_id)))
        mutations.append(reject('old static ID ' + name,
            lambda: EXT.decode_extension(candidate, image, expected_build_id=old_id)))
        bad = bytearray(candidate); bad[-1] ^= 1
        mutations.append(reject('object/CRC ' + name,
            lambda: EXT.decode_extension(bytes(bad), image, expected_build_id=new_id)))
    entries = [dict(offset=1, before=0, after=1, owner='test: file-chain')]
    ledger_check(bytes(4), b'\0\1\0\0', entries)
    mutations.append(reject('unclassified byte', lambda: ledger_check(bytes(4), b'\0\1\1\0', entries)))
    mutations.append(reject('dropped byte owner', lambda: ledger_check(bytes(4), b'\0\1\0\0', [])))
    price_check(dict(before=4083, after=4086, delta=3))
    for field in ('before', 'after', 'delta'):
        price = dict(before=4083, after=4086, delta=3); price[field] -= 1
        mutations.append(reject('stale price '+field, lambda: price_check(price)))
    static = F.emit_image('stdlib-p0', 'stdlib', ROOT / product['manifests'][0]['path'])
    foreign_check(static.code, static.metadata, static.code, static.metadata)
    wrong = bytearray(static.code); wrong[-1] ^= 1
    mutations.append(reject('foreign static image', lambda:
        foreign_check(static.code, static.metadata, bytes(wrong), static.metadata)))
    print('disk-r7-product: SELFTEST PASS mutations=' + str(len(mutations)) + '; product receipt deferred')


def derive():
    C.source_controls()
    require(COMPLETE.is_file(), 'Chunk C incomplete: r7 complete.json is required')
    old = json.loads(BASE.read_bytes())
    new = json.loads(COMPLETE.read_bytes())
    require(new['status'] == 'PASS' and new['seed'] == 1 and new['final'] == 0
            and new['product_links'] == 1, 'r7 Seed completion contract drift')
    for row in old['receipts'] + new['receipts']:
        S.checked(row)
    before, after = S.checked(old['medium']), S.checked(new['medium'])
    require(len(before) == len(after) == 819200, 'D81 extent drift')
    require(S.checked(old['ELF']) != S.checked(new['ELF']), 'stale native identity')
    receipts = {Path(r['path']).name: load_bound(r) for r in new['receipts']}
    require(set(receipts) == {'price.json', 'capacity.json', 'source.json', 'inventory.json',
                              'media.json', 'negative-controls.json'}, 'product receipt population drift')
    pre = load_bound(receipts['source.json']['preflight'])
    price_check(pre['price'])
    price_check(receipts['price.json'])
    prepath = ROOT / receipts['source.json']['preflight']['path']
    for row in pre['artifacts']:
        S.checked(row)
    inputs = load_bound(pre['inputs'])
    for row in inputs:
        S.checked(row)
    require(next(r for r in inputs if r['path'] == C.SOURCE)['sha256'] == C.SOURCE_SHA,
            'product consumed wrong disk source')
    a, b = pre['constants']['before_product'], pre['constants']['after_product']
    old_id, new_id = a['product_build_id_u32'], b['product_build_id_u32']
    require(old_id != new_id and len(a['manifests']) == len(b['manifests']) == 6, 'stale static ID/population')
    images = []
    keys = ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc')
    for i, key in enumerate(keys):
        S.checked(a['manifests'][i]); S.checked(b['manifests'][i])
        x = F.emit_image(key, 'stdlib' if i == 0 else key, ROOT / a['manifests'][i]['path'])
        y = F.emit_image(key, 'stdlib' if i == 0 else key, ROOT / b['manifests'][i]['path'])
        if key != 'm65d':
            foreign_check(x.code, x.metadata, y.code, y.metadata)
        else:
            require(len(x.code) == 4083 and len(y.code) == 4086, 'stale product M65D price')
            require(len(x.manifest['entries']) == len(y.manifest['entries']) == 39, 'M65D population drift')
            require(max(e['length'] for e in y.manifest['entries']) == 252, 'M65D object bound drift')
            changed = []
            for left, right in zip(x.manifest['entries'], y.manifest['entries'], strict=True):
                allowed = {'blob_offset', 'length', 'code_addr', 'payload_addr', 'ext_addr'}
                require(left.keys() == right.keys() and
                        {k:v for k,v in left.items() if k not in allowed} ==
                        {k:v for k,v in right.items() if k not in allowed}, 'M65D entry metadata drift')
                xc = x.code[left['blob_offset']:left['blob_offset']+left['length']]
                yc = y.code[right['blob_offset']:right['blob_offset']+right['length']]
                if xc != yc:
                    changed.append(left['name'])
            require(changed == ['%m65d-dir-fill'], 'foreign M65D object change')
        images.append(dict(name=key, code_bytes=len(y.code), metadata_bytes=len(y.metadata)))
    previous, current = D.visible_files(before), D.visible_files(after)
    require(set(previous) == set(current) and len(current) == 20, 'media file population drift')
    require(current[b'INIT.L65'] == previous[b'INIT.L65'] and current[b'L65INDEX'] == previous[b'L65INDEX'], 'INIT/index drift')
    plane = prepath.parent / 'planes/candidate'
    code, c2d, shelf = [(plane / n).read_bytes() for n in ('CODE.BIN','C2D.BIN','SHELF.BIN')]
    require(current[b'CODE.BIN'][:len(code)] == code and len(code) == 50063, 'stale delivered CODE')
    require(current[b'C2D.BIN'] == c2d + bytes(50816-len(c2d)), 'stale delivered C2D')
    require(current[b'SHELF.BIN'] == shelf and len(shelf) == 99555, 'stale delivered SHELF')
    D.validate_bam(after)
    occupied = set()
    for slot in D.directory_slots(after):
        if not slot.record[2]:
            continue
        chain = D.file_chain(after, slot.record)
        require(not occupied.intersection(chain), 'crosslinked media file')
        occupied.update(chain)
        require(all(not D.sector_is_free(after,*ts) for ts in chain), 'visible free sector')
        require(D.read_record_payload(after,slot.record) == current[D.entry_name(slot.record)], 'file readback drift')
    payloads, mutations = {}, []
    require(len(pre['packages']) == 6, 'package population drift')
    for spec in pre['packages']:
        name = spec['name']; raw = current[name.upper().encode()]
        original = previous[name.upper().encode()]
        image = F.emit_image(name, spec['shelf'], ROOT / spec['manifest']['path'])
        S.checked(spec['manifest'])
        EXT.decode_extension(raw, image, expected_build_id=new_id)
        EXT.decode_extension(original, image, expected_build_id=old_id)
        require(raw == S.checked(spec['candidate']), 'package candidate drift')
        require(raw[:22] == original[:22] and raw[26:] == original[26:], 'package loader content drift')
        payloads[name] = raw
        mutations.append(reject('one un-rebound header: '+name,
            lambda: EXT.decode_extension(original, image, expected_build_id=new_id)))
    rows = INDEX.decode_index(current[b'L65INDEX'], payloads, artifact_build_id=new_id)
    index_mutations = INDEX.mutation_gate(current[b'L65INDEX'], payloads, artifact_build_id=new_id)
    media = receipts['media.json']
    require(media['medium'] == new['medium'], 'media/complete identity drift')
    require(media['files'] == {n.decode(): dict(bytes=len(raw), sha256=S.sha(raw))
                              for n, raw in current.items()}, 'media file binding drift')
    changed_files = {n.decode() for n in current if current[n] != previous[n]}
    require(set(media['changed_files']) == changed_files, 'changed file inventory drift')
    native = load_bound(media['native_bindings'])
    require(native['ELF'] == new['ELF'] and native['product_build_id'] == new_id,
            'native runtime identity drift')
    S.checked(media['stager'])
    entries = load_bound(media['ledger'])['entries']
    diff = ledger_check(before, after, entries)
    require(diff == load_bound(media['diff']), 'classified byte ledger drift')
    require({r['owner'] for r in diff['rows']} <=
            {name + ': ' + kind for name in changed_files for kind in ('file-chain', 'directory', 'BAM')},
            'foreign disk-byte owner')
    require(receipts['inventory.json']['unclassified_bytes'] == 0, 'unclassified native bytes')
    require(receipts['inventory.json']['ELFs'] == [old['ELF'], new['ELF']], 'native inventory identities drift')
    changed = next(i for i,(x,y) in enumerate(zip(before,after)) if x != y)
    mutations.append(reject('dropped disk-byte owner', lambda: ledger_check(before, after,
        [r for r in entries if r['offset'] != changed])))
    trial = bytearray(after); trial[changed] ^= 1
    mutations.append(reject('unclassified disk-byte change', lambda: ledger_check(before, bytes(trial), entries)))
    mutations.append(reject('old static ID', lambda: INDEX.decode_index(current[b'L65INDEX'], payloads, artifact_build_id=old_id)))
    return dict(status='PASS', predecessor=S.bind(BASE), complete=S.bind(COMPLETE),
                source=C.S.bind(C.SOURCE), static_id=new_id, images=images, index_rows=rows,
                medium=S.bind(ROOT/new['medium']['path']), native=S.bind(ROOT/new['ELF']['path']),
                changed_bytes=diff['changed_bytes'], mutations=mutations, index_mutations=index_mutations,
                claim_limit='Host readback of completed r7 Seed; no emulator/device/release acceptance')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('build','check','selftest'))
    args = parser.parse_args()
    if args.action == 'selftest':
        selftest()
        return
    value = dict(current=derive(), inputs=[C.S.bind(p) for p in (
        __file__, C.__file__, 'tools/host-lisp/c2_full_emission.py',
        'tools/host-lisp/c2_session_extension_probe.py', 'tools/host-lisp/c2_require_resolver_gate.py')])
    raw = C.S.canonical(value)
    if args.action == 'build':
        with RECEIPT.open('xb') as stream:
            stream.write(raw)
    else:
        require(RECEIPT.read_bytes() == raw, 'r7 product receipt drift')
    print('disk-r7-product: PASS')


if __name__ == '__main__':
    main()
