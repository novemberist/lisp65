"""Materialize and pack the export-publication Seed measurement medium, without Runtime builds.

Provenance: copied from boot_name_index_seed_media.py rather than imported,
because that module's `pack_family`/`validate`/`negative`/`selftest` close
over its own module-level globals (`g`, `M`, `BANK`, `CARD`, `DRIVER`) built
at IMPORT TIME from `boot_name_index_producer` in command-probe mode --
importing it here to "reuse" those functions would, as a side effect, also
run boot_name_index_producer's whole command-probe pipeline again under this
card's identity, which is not what this adapter wants. The house convention
for this family of adapters is itself "pure renaming derivation" (see
boot_name_index_seed_media.py's own docstring, itself derived the same way
from native_diet_seed_media.py), so this file follows the same convention
one card further, not a generic import.

Catalog geometry is UNCHANGED from the boot-name-index card: this card adds
no new Session/decoder slice, so the Session family is still exactly 55
records, the private disk record still at slot 52, and the two boot-name-
index records still pinned at 53/54 (LISP65_C2_PHASE_10A_SLOT/_10B_SLOT in
src/c2_product_runtime.h, which this card's own hunk does not move). The
`pack_family`/`validate`/`negative`/`selftest` bodies below are therefore
UNCHANGED from boot_name_index_seed_media.py -- same DISK_SLOT/PIN_10A/
PIN_10B/SESSION_SLICES, same reslot/record helpers -- only the module-level
wiring (DRIVER, M.OUT, HERE, the stager/library provenance paths) points at
this card's own producer and Seed instead of r5's.

`export_publication_producer` (imported below) is this card's own producer;
it is not created by this adapter. Its AUTH is still '227e59e9' at the
time this file was written, so `producer()` below -- which drives
DRIVER.main() in command-probe mode -- raises SystemExit at the producer's
own AUTH_PENDING gate before it ever reaches the captured `exec()`; the
module-level `g = producer()` call therefore cannot complete and this file
cannot be fully imported yet. Only py_compile was possible for this file;
a dry-run import was attempted and confirmed to fail exactly at that gate
(SystemExit: 'bind AUTH to the commissioned source commit first'), not at
any earlier syntax or attribute error. Once AUTH is bound and a Seed for
this card exists, re-run the dry-run import to confirm it proceeds past
`producer()`.

Note for the boot ledger observer: this card's own pack() writes its
`packed-receipt.json` under `M.OUT`, i.e.
`build/export-publication-seed-medium-r1/packed-receipt.json`.
"""
from pathlib import Path
import builtins
import copy
import hashlib
import inspect
import json
import struct
import sys

import export_publication_producer as DRIVER
import capacity_disk_window_media as M
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'build/export-publication-r1'


def producer():
    captured = []
    def load_only(code, scope):
        assert scope['__name__'] == '__main__'
        scope['__name__'] = 'export_publication_media_configuration'
        builtins.exec(code, scope)
        captured.append(scope)
    argv = sys.argv
    try:
        sys.argv = [str(Path(DRIVER.__file__)), 'command-probe']
        DRIVER.exec = load_only
        DRIVER.main()
    finally:
        sys.argv = argv
        del DRIVER.exec
    assert len(captured) == 1
    return captured[0]['g']


g = producer()
M.OUT = ROOT/'build/export-publication-seed-medium-r1'
M.FINAL = M.OUT/'materialized'
M.PLANE = g['PLANE']
configured = False


BANK = M.BANK
CARD = M.CARD
# Catalog geometry, unchanged from boot_name_index_seed_media.py: 55 records,
# the private f011-write-member at slot 52, the two boot-name-index records
# pinned at 53/54. This card adds no new slice, so these are copied verbatim.
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
    """Pack the Session family with the private disk record kept at slot 52.

    Unchanged from boot_name_index_seed_media.py: the catalog shape this
    card packs is exactly the r5 shape (55 dense records, disk record
    stitched back in at 52, the two pinned records lowered/raised around
    it) -- this card's own hunk does not touch the Session catalog.
    """
    p = g['P']
    if family != 'session':
        return M.ORIGINAL_PACK(out, target, contract, family, suffix)
    specs = list(p.SESSION_SLICE_SPECS)
    assert len(specs) == SESSION_SLICES
    assert [int(spec.split(':')[0]) for spec in specs] == list(range(SESSION_SLICES))
    assert specs[DISK_SLOT].split(':')[2] == CARD.D.SECTION
    tail = specs[DISK_SLOT+1:]
    assert [spec.split(':')[2] for spec in tail] == list(PIN_SECTIONS)
    lowered = [f"{int(spec.split(':', 1)[0])-1}:{spec.split(':', 1)[1]}" for spec in tail]
    try:
        p.SESSION_SLICE_SPECS = specs[:DISK_SLOT] + lowered
        image, manifest = M.ORIGINAL_PACK(out, target, contract, family, suffix)
    finally:
        p.SESSION_SLICE_SPECS = specs
    value = json.loads(manifest.read_text())
    data, source, vma, entry, owner = M.payload(Path(str(target)+'.elf'))
    raw = bytearray(image.read_bytes())
    count = value['catalog']['slice_count']
    assert count == SESSION_SLICES-1
    assert [r['id'] for r in value['slices']] == list(range(count))
    assert [r['section'] for r in value['slices'][DISK_SLOT:]] == list(PIN_SECTIONS)
    assert _catalog_ids(raw, count) == list(range(count))
    start = BANK.HEADER_SIZE + DISK_SLOT*BANK.ENTRY_SIZE
    assert BANK.HEADER_SIZE + (count+1)*BANK.ENTRY_SIZE <= value['catalog']['payload_offset']
    assert not any(raw[start+2*BANK.ENTRY_SIZE:start+3*BANK.ENTRY_SIZE])
    record = M.make_record(data, source, vma, entry, DISK_SLOT, value['profile_build_id'])
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
        bytes=len(data), sha256=M.bind(blob)['sha256'], crc16=BANK.crc16_ccitt_false(data), owner=owner)
    value['storage'].update(size=len(raw), crc16=BANK.crc16_ccitt_false(bytes(raw)),
                            sha256=M.bind(image)['sha256'])
    fields = BANK.HEADER.unpack(bytes(raw[:BANK.HEADER_SIZE]))
    value['catalog'].update(slice_count=count+1, directory_crc16=fields[12], header_crc16=fields[13])
    value['slices'] = value['slices'][:DISK_SLOT] + [dict(id=DISK_SLOT,
        name='f011-write-member', section=CARD.D.SECTION,
        start_symbol='__lisp65_rt_card2b_disk_start', end_symbol='__lisp65_rt_card2b_disk_end',
        entry_symbol='__lisp65_rt_card2b_disk_entry', flags=BANK.FLAG_RUNTIME|BANK.FLAG_REUSABLE,
        roles=BANK._roles(BANK.FLAG_RUNTIME|BANK.FLAG_REUSABLE), file_offset=0, file_size=len(data),
        memory_size=len(data), vma=vma, end=vma+len(data), entry=entry, entry_offset=entry-vma,
        abi_version=BANK.ENTRY_ABI, slice_build_id=value['profile_build_id'], capability_mask=0,
        crc16=BANK.crc16_ccitt_false(data), record_crc16=struct.unpack_from('<H', record, 22)[0],
        sha256=M.bind(blob)['sha256'], region_id=2, source_address=source)] + rows
    M.write(manifest, value)
    validate(image, value, 'export-publication-pack')
    selftest(image, value)
    return image, manifest


def validate(image, value, label):
    if 'external_storage' not in value:
        return M.ORIGINAL_VALIDATE(image, value, label)
    ext = value['external_storage']; data = (image.parent/ext['file']).read_bytes()
    rows = value['slices']; r = rows[DISK_SLOT]; raw = image.read_bytes()
    elf = image.parent/value['elf']['file']
    assert M.bind(elf)['sha256'] == value['elf']['sha256']
    expected_data, expected_source, expected_vma, expected_entry, expected_owner = M.payload(elf)
    assert (data, r['source_address'], r['vma'], r['entry'], ext['owner']) == \
        (expected_data, expected_source, expected_vma, expected_entry, expected_owner)
    assert len(rows) == value['catalog']['slice_count'] == SESSION_SLICES
    assert [row['id'] for row in rows] == list(range(SESSION_SLICES))
    assert r['id'] == DISK_SLOT and r['section'] == CARD.D.SECTION
    assert [row['section'] for row in rows[PIN_10A:]] == list(PIN_SECTIONS)
    assert _catalog_ids(raw, SESSION_SLICES) == list(range(SESSION_SLICES))
    assert ext['region_id'] == r['region_id'] == 2
    assert ext['source_address'] == r['source_address'] == ext['owner']['payload']['start']
    assert ext['bytes'] == r['file_size'] == len(data) <= ext['owner']['payload']['capacity']
    assert hashlib.sha256(data).hexdigest() == ext['sha256'] == r['sha256']
    assert BANK.crc16_ccitt_false(data) == ext['crc16'] == r['crc16']
    expected = M.make_record(data, r['source_address'], r['vma'], r['entry'], r['id'],
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
    M.ORIGINAL_VALIDATE(image, ordinary, label)


def negative(image, manifest):
    value = json.loads(manifest.read_text())
    if 'external_storage' not in value:
        return M.ORIGINAL_NEGATIVE(image, manifest)
    source = image.parent/value['external_storage']['file']; p = source.with_suffix('.negative')
    raw = bytearray(source.read_bytes()); raw[len(raw)//2] ^= 1; p.write_bytes(bytes(raw))
    value['external_storage']['file'] = p.name
    try:
        validate(image, value, 'export-publication-mutation')
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
                validate(target, candidate, 'export-publication-pin-mutation')
            except (AssertionError, RuntimeError):
                results[name] = 'rejected'
            else:
                raise AssertionError('export-publication pin mutation survived: '+name)
    finally:
        mutated.unlink()
    print('export-publication pin selftest: '+json.dumps(results, sort_keys=True), flush=True)
    return results


def setup():
    global configured
    if configured:
        return
    g['configure']()
    def forbidden(*args, **kwargs):
        raise RuntimeError('Runtime compilation/link forbidden during Seed materialization')
    p = g['P']
    p.compile_link = forbidden
    p.PRODUCT_ARTIFACTS_MANIFEST = M.PLANE/'product/substitution-artifacts.json'
    p.INITIAL_C2D = M.PLANE/'product/initial.c2d-v3.bin'
    p.PRODUCT_SHELF = M.PLANE/'product/product-shelf-v4-direct.bin'
    p.overlay_pack_family, p._validate_family_artifact = pack_family, validate
    p._family_identity_negative_selftest = negative
    truth = ElfTruth.read(g['BUILD']/'wplto/resident-island-seed.prg.elf',
                          llvm_readobj=p.TOOLCHAIN/'llvm-readobj')
    p.VERIFIER_BINDING_BASE = p.LINK60_VERIFIER_BINDING_BASE = truth.section(p.VERIFIER_BINDING_SECTION).address
    configured = True


M.setup = setup


def libraries():
    """Keep four packages exact; substitute only the admitted defstruct image.

    Unchanged in shape from boot_name_index_seed_media.py's own libraries();
    this card adds no new library and does not move the defstruct admission
    or the stager-CRC32 delta.
    """
    raw = (ROOT/'build/init-echo-r1/library-media.py').read_text()
    raw = raw.replace('build/init-echo-product-r1-preflight/setup-owned/static-plane/narrow-static',
                      str(g['PLANE'].relative_to(ROOT)))
    needle = "exec(compile(raw,str(source),'exec'),globals())"
    assert raw.count(needle) == 1
    addition = '''
old="            row,data=LIB.measured(spec,(1,1),build_id)"
new="""            if name=='defstruct':
                admitted=json.loads((ROOT/'build/definition-group-composition-r6/receipt.json').read_text())['package']['candidate']
                candidate=ROOT/admitted['path']
                assert bind(candidate)['sha256']==admitted['sha256']
                spec=(*spec[:3],candidate,spec[4])
                specs[specs.index(next(s for s in specs if s[0]==name))]=spec
            row,data=LIB.measured(spec,(1,1),build_id)"""
assert raw.count(old)==1
raw=raw.replace(old,new)
'''
    raw = raw.replace(needle, addition+'\n'+needle)
    old_write = "  generated.write_text(base['source'])"
    assert raw.count(old_write) == 1
    raw = raw.replace(old_write, """  live=(ROOT/'scripts/r3-cold-stager-main.c').read_text()
  source=base['source'].replace(D.c_function(base['source'],'crc32_step'),D.c_function(live,'crc32_step'))
  assert source==(ROOT/'build/stager-crc32-r2/stager-main.c').read_text(),'stager is not the accepted CRC32 stager source'
  generated.write_text(source)""")
    scope = dict(__name__='export_publication_libraries', __file__=str(HERE/'library-media.py'))
    builtins.exec(compile(raw, str(ROOT/'build/init-echo-r1/library-media.py'), 'exec'), scope)
    scope['install']()


def pack():
    libraries()
    setup()
    import hardware_sp_seed_media as BASE
    record = json.loads((M.OUT/'materialization.json').read_text())
    record['materialized_prg'] = record['prg']
    M.write(M.OUT/'materialization.json', record)
    BASE.OUT, BASE.FINAL, BASE.PLANE, BASE.SEED = M.OUT, M.FINAL, M.PLANE, g['BUILD']
    BASE.setup, BASE.bind = setup, M.bind
    BASE.authority = lambda: dict(commit=DRIVER.AUTH, role='export-publication-seed',
        measurement_only=True, product_builds=0, host_images=1, device_contacts=0)
    original = BASE.COMPOSE.mapped_section_rows
    def composed(truth, names):
        rows = original(truth, names)
        data, source, _, _, owner = M.payload(M.FINAL/'lisp65-c2-substitution-linked.prg.elf')
        assert all(source+len(data)<=start or source>=start+len(raw) for start,raw,_ in rows)
        return sorted(rows+[(source, data, g['R'].B.D.SECTION)])
    BASE.COMPOSE.mapped_section_rows = composed
    code = inspect.getsource(BASE.pack)
    assert code.count('assert len(prefix)==47795') == 1
    code = code.replace('assert len(prefix)==47795', 'assert len(prefix)==EXPECTED_EXTENT')
    namespace = dict(BASE.__dict__)
    emission = json.loads((HERE/'plane.json').read_text())
    assert g['R'].C.bind(g['PLANE']/'v6-semantics/bank2-static-code.bin')['sha256'] == emission['bank2']['sha256']
    namespace['EXPECTED_EXTENT'] = emission['plane_bytes']
    builtins.exec(compile(code, str(Path(BASE.__file__)), 'exec'), namespace)
    namespace['pack']()


if __name__ == '__main__':
    if sys.argv[1:] == ['materialize']:
        setup(); M.materialize()
    elif sys.argv[1:] == ['resume']:
        setup(); M.resume()
    elif sys.argv[1:] == ['pack']:
        pack()
    else:
        raise SystemExit('materialize | resume | pack')
