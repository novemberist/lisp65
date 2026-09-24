"""Producer-side admission check for the boot-name-index card.

The batched boot name resolution (decoder phase split into a Bank-5 collect
walk plus a resolve phase 10b, see `boot_name_index_split_probe.py`) assumes
that no single accepted product image carries more than 1,024 literal
records of kind 5 (compiler-proven exported-call name) or kind 8 (general
symbol spelling). This script measures that count directly from the accepted
diet-card static plane's own bytes -- Shelf plus C2D -- with no build, no
link, and no device contact.

Data sources (read-only, both already accepted native-diet r4 preflight
inputs):
  Shelf: build/native-diet-product-r4-preflight/setup-owned/static-plane/
         narrow-static/product/product-shelf-v4-direct.bin
  C2D:   build/native-diet-product-r4-preflight/setup-owned/static-plane/
         narrow-static/v6-semantics/initial.c2d-v6.bin

Record layout, taken directly from the shipped product decoder (not
reconstructed by inspection alone):

  - C2D header (48 bytes, C2D-v6/NESTED_APPEND_V5 shape): magic 'C2D',
    h[4]==6, h[5]==48 (header length), h[6]==32 (image record capacity),
    h[7]==10. image_count = u16(h+12); images_offset = u16(h+28) (must be
    48, i.e. the image table starts right after the header) -- all checked
    in `c2_stream_phase_00`/`c2_stream_phase_00b`
    (build/native-diet-product-r4/wplto/generated-product-sources/
    c2-stream-decoder.c, and src/c2_product_runtime.c for the same
    constants under LISP65_C2_NESTED_APPEND_V5).

  - Each C2D image record is 32 bytes at `images_offset + image*32`
    (`raw`). For a static (pre-boot) image, `raw[0] == 0` and `raw[2]`
    must equal the image ordinal (checked in
    `c2_stream_product_image_read`, src/c2_product_runtime.c:574). Because
    this product world is compiled with LISP65_C2_LITE_COLD_EVICTION (
    confirmed against build/native-diet-product-r4-preflight/
    command-world-x7d_cygv/command-proof.json), the *metadata* pointer for
    a static image is NOT taken from the C2D record itself: it is read
    back from the Shelf's own 32-byte catalog record at
    `32 + raw[2]*32` (the `source` array in the same function), as
    `meta = u24(source[13:16])`, cross-checked against
    `u16(source[11:13]) == u16(raw[21:23])`.

  - The per-image metadata header `h` (24 bytes) lives in the Shelf at
    offset `meta`. Literal count `lc = u16(h[12:14])`, literal-record
    offset `lo = u16(h[16:18])` (exactly as `c2_stream_phase_10` in
    scripts/c2-stream-v2-decoder.c reads them, and as
    `boot_name_index_split_probe.py`'s `BOOT_COLLECT_PHASE`/`RESOLVE_PHASE`
    already assume for the batched split).

  - Each of the `lc` literal records is 8 bytes at `meta + lo + i*8`;
    `kind = r[0]`. Only `kind in (5, 8)` need boot-time name resolution
    (kind 5: compiler-proven callable export edges; kind 8: general
    symbol spellings) -- this is the exact filter in
    `c2_stream_phase_10`.

All of this was cross-checked against the live bytes of both files (see
`--selftest` and the receipt's `bindings`), not just read from the C source.

Every measurement is instrumentless (no build, no link, no device contact,
budget 0/0/0/0).
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANE = (ROOT / 'build/native-diet-product-r4-preflight/setup-owned/'
                'static-plane/narrow-static')
SHELF_PATH = PLANE / 'product/product-shelf-v4-direct.bin'
C2D_PATH = PLANE / 'v6-semantics/initial.c2d-v6.bin'
OUT = ROOT / 'build/boot-name-index-admission-r1'
BATCH_CAP = 1024
CENSUS_EXPECTED_REQUESTS = 2071


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path):
    data = path.read_bytes()
    try:
        shown = str(path.relative_to(ROOT))
    except ValueError:
        shown = str(path)  # selftest fixtures live outside ROOT, under a temp dir
    return dict(path=shown, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def u16(buf, offset):
    return buf[offset] | (buf[offset + 1] << 8)


def u24(buf, offset):
    return buf[offset] | (buf[offset + 1] << 8) | (buf[offset + 2] << 16)


def u32(buf, offset):
    return struct.unpack_from('<I', buf, offset)[0]


def parse_c2d_header(c2d):
    """Validate the 48-byte C2D-v6 header exactly as c2_stream_phase_00 does
    (NESTED_APPEND_V5 branch): magic, version, record sizes, fixed length."""
    if len(c2d) != 33840:
        raise ValueError('unexpected C2D length: %d (expected 33840)' % len(c2d))
    if c2d[0:3] != b'C2D' or c2d[3] != 0:
        raise ValueError('bad C2D magic')
    if c2d[4] != 6 or c2d[5] != 48 or c2d[6] != 32 or c2d[7] != 10:
        raise ValueError('unexpected C2D-v6 header shape')
    header = dict(
        generation=u16(c2d, 10), image_count=u16(c2d, 12),
        entry_count=u16(c2d, 16), resolution_count=u16(c2d, 20),
        c2_root_count=u16(c2d, 24), images_offset=u16(c2d, 28),
        entries_offset=u16(c2d, 30), resolutions_offset=u16(c2d, 32),
        roots_offset=u16(c2d, 34), catalog_crc32=u32(c2d, 40))
    if header['images_offset'] != 48:
        raise ValueError('images_offset drift: %d (expected 48)' % header['images_offset'])
    if header['image_count'] == 0 or header['image_count'] > 64:
        raise ValueError('image_count out of the accepted 1..64 domain')
    return header


def parse_shelf_header(shelf):
    if shelf[0:4] != b'L65S':
        raise ValueError('bad Shelf magic')
    return dict(image_count=shelf[7])


def image_literal_records(shelf, c2d, header, image):
    """Read one image's 32-byte C2D record, resolve its metadata pointer
    through the Shelf catalog (the LISP65_C2_LITE_COLD_EVICTION static
    path), and return the list of (kind,) 8-byte literal records."""
    images_offset = header['images_offset']
    raw = c2d[images_offset + image * 32: images_offset + image * 32 + 32]
    if len(raw) != 32:
        raise ValueError('truncated C2D image record %d' % image)
    kind_byte, reserved1, source_idx, reserved3 = raw[0], raw[1], raw[2], raw[3]
    if kind_byte > 2 or reserved1 or reserved3:
        raise ValueError('image %d: unexpected image-record kind/reserved bytes' % image)
    if kind_byte != 0:
        raise ValueError('image %d: not a static (pre-boot) image (kind=%d); '
                          'this admission check only covers the narrow-static '
                          'plane' % (image, kind_byte))
    if source_idx != image:
        raise ValueError('image %d: Shelf source index drift (%d)' % (image, source_idx))
    source_off = 32 + source_idx * 32
    source = shelf[source_off:source_off + 32]
    if len(source) != 32 or source[30] != 1 or source[31] != 0:
        raise ValueError('image %d: bad Shelf catalog record' % image)
    meta = u24(source, 13)
    if u16(source, 11) != u16(raw, 21):
        raise ValueError('image %d: meta_len cross-check failed (Shelf vs C2D)' % image)
    h = shelf[meta:meta + 24]
    if len(h) != 24:
        raise ValueError('image %d: truncated metadata header at Shelf offset %d' % (image, meta))
    lc = u16(h, 12)
    lo = u16(h, 16)
    records = []
    for i in range(lc):
        off = meta + lo + i * 8
        r = shelf[off:off + 8]
        if len(r) != 8:
            raise ValueError('image %d: truncated literal record %d' % (image, i))
        records.append(r[0])
    return lc, records, meta, lo


def measure(shelf_path=SHELF_PATH, c2d_path=C2D_PATH):
    shelf = shelf_path.read_bytes()
    c2d = c2d_path.read_bytes()
    header = parse_c2d_header(c2d)
    shelf_header = parse_shelf_header(shelf)
    if shelf_header['image_count'] != header['image_count']:
        raise ValueError('Shelf/C2D image_count mismatch: %d vs %d' %
                          (shelf_header['image_count'], header['image_count']))
    images = []
    total_kind58 = 0
    total_literals = 0
    for image in range(header['image_count']):
        lc, records, meta, lo = image_literal_records(shelf, c2d, header, image)
        kind58 = sum(1 for k in records if k in (5, 8))
        images.append(dict(ordinal=image, literal_count=lc, kind5_8_count=kind58,
                            max=BATCH_CAP, meta_offset=meta, literal_table_offset=lo))
        total_kind58 += kind58
        total_literals += lc
    if total_literals != header['resolution_count']:
        raise ValueError('sum(literal_count) != C2D resolution_count (%d != %d)' %
                          (total_literals, header['resolution_count']))
    return dict(header=header, images=images, total_kind5_8=total_kind58,
                total_literals=total_literals)


def build_receipt(shelf_path=SHELF_PATH, c2d_path=C2D_PATH):
    measured = measure(shelf_path, c2d_path)
    status = 'PASS' if all(row['kind5_8_count'] <= BATCH_CAP for row in measured['images']) else 'FAIL'
    max_seen = max((row['kind5_8_count'] for row in measured['images']), default=0)
    census_delta = measured['total_kind5_8'] - CENSUS_EXPECTED_REQUESTS
    explanation = (
        'measured count equals the census figure' if census_delta == 0 else
        'measured static-plane kind-5/8 total (%d) differs from the phase-10 boot '
        'census figure (%d) by %+d. This script only walks the six static images of '
        'the narrow-static plane (build/native-diet-product-r4-preflight/...); the '
        'census figure of %d was supplied as prior knowledge of a live phase-10 '
        'request count and could not be reproduced or its origin located in this '
        'repository during this measurement, so the difference is reported, not '
        'silently reconciled. Candidate causes worth checking against the actual '
        'census source: the census may count phase-10 c2_stream_name_value calls '
        'from a different or later plane generation than the one pinned here, or '
        'it may include name-resolution requests from other call sites/phases '
        '(e.g. session appends, requires, or the export-journal builder in '
        'src/c2_product_runtime.c) that are outside the six-image static walk '
        'this script measures.' % (measured['total_kind5_8'], CENSUS_EXPECTED_REQUESTS,
                                    census_delta, CENSUS_EXPECTED_REQUESTS))
    receipt = dict(
        claim='PRODUCER-SIDE ADMISSION CHECK ONLY; NO BUILD, NO LINK, NO DEVICE CONTACT',
        budget=dict(seed=0, finale=0, link=0, device_contacts=0),
        batch_cap=BATCH_CAP,
        status=status,
        max_kind5_8_in_any_image=max_seen,
        images=measured['images'],
        total_kind5_8_records=measured['total_kind5_8'],
        total_literal_records=measured['total_literals'],
        c2d_header=measured['header'],
        census=dict(expected_phase_10_requests=CENSUS_EXPECTED_REQUESTS,
                    measured_static_plane_kind5_8=measured['total_kind5_8'],
                    delta=census_delta, note=explanation),
        bindings=dict(shelf=bind(shelf_path), c2d=bind(c2d_path)),
    )
    return receipt


def put(path, text):
    if path.exists() and path.read_text() != text:
        raise ValueError('refusing to overwrite differing receipt: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text)


def selftest():
    """Mutate one image's on-disk-equivalent bytes in memory so its kind5/8
    count exceeds the 1,024 batch cap, and check the admission flips to FAIL."""
    shelf = bytearray(SHELF_PATH.read_bytes())
    c2d = C2D_PATH.read_bytes()
    header = parse_c2d_header(c2d)
    # Pick image 0 (already the largest literal count) and overwrite its
    # first 1,025 literal records' kind byte to 5, guaranteeing > 1,024
    # kind-5/8 hits without touching the record count or any other field.
    image = 0
    lc, records, meta, lo = image_literal_records(bytes(shelf), c2d, header, image)
    mutate_count = min(lc, BATCH_CAP + 1)
    if mutate_count <= BATCH_CAP:
        raise ValueError('selftest fixture image does not have enough literal '
                          'records to exceed the cap (has %d)' % lc)
    for i in range(mutate_count):
        shelf[meta + lo + i * 8] = 5
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        mutated_shelf = Path(tmp) / 'mutated-shelf.bin'
        mutated_shelf.write_bytes(bytes(shelf))
        receipt = build_receipt(shelf_path=mutated_shelf, c2d_path=C2D_PATH)
    if receipt['status'] != 'FAIL':
        raise SystemExit('selftest FAILED: mutated image did not flip status to FAIL')
    if receipt['max_kind5_8_in_any_image'] <= BATCH_CAP:
        raise SystemExit('selftest FAILED: mutated max did not exceed the cap')
    print('selftest OK: mutated image %d kind5/8=%d > cap=%d -> status=%s' % (
        image, receipt['images'][image]['kind5_8_count'], BATCH_CAP, receipt['status']))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--selftest', action='store_true',
                    help='run the mutation selftest (no receipt.json is read or written '
                         'for the mutated case; only stdout is used)')
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('admission receipt must stay under build/')
    receipt = build_receipt()
    put(out / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'images'}, indent=2))
    for row in receipt['images']:
        print('  image %d: literal_count=%-5d kind5/8=%-5d max=%d' % (
            row['ordinal'], row['literal_count'], row['kind5_8_count'], row['max']))


if __name__ == '__main__':
    main()
