#!/usr/bin/env python3
"""Regenerate the 2.5.3 Final six-image Lisp plane from public manifests.

SHELF.BIN and the static plane code are re-emitted from the six projected
compiled manifests; C2D.BIN is a projected plane input (2.5.1 precedent),
checked through the CRC arrays compiled into the native phase-02a source.
"""
import json
import struct
from pathlib import Path
import c2_v253_r2_public_native as N

POLICY = N.ROOT / ('config/%s-plane.json' % N.PREFIX)


def artifacts():
    import c2_full_emission as F
    p = N.load(POLICY)
    rows = p['manifests']
    N.require([r['key'] for r in rows] == ['stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc'], 'plane image order')
    for r in rows:
        N.bound(r['manifest'])
    images = [F.emit_image(r['key'], r['shelf'], N.local(r['manifest']['path'])) for r in rows]
    shelf, _, _ = F.build_shelf(images)
    code = b''.join(i.code for i in images)
    c2d = N.bound(p['c2d'])
    N.require(N.identity(shelf) == p['expected']['shelf'], 'public six-image shelf regeneration drift')
    N.require(N.identity(code) == p['expected']['code'], 'public static plane code regeneration drift')
    bid = struct.unpack_from('<I', shelf, 22)[0]
    N.require(bid == p['product_build_id_u32'] == int(p['product_build_id_hex'], 16) == 0xaff6dfd2, 'derived build ID drift')
    return dict(images=images, shelf=shelf, code=code, c2d=c2d, build_id=bid, policy=p)


def check():
    import runtime_overlay_bank as BANK
    a = artifacts()
    recipe = N.load(N.RECIPE)
    inputs = {r['materialized_path']: r['source'] for r in recipe['inputs']}
    commands = recipe['commands']
    hexid = a['policy']['product_build_id_hex']
    for c in commands[:73]:
        N.require('-DLISP65_C2_PRODUCT_BUILD_ID=' + hexid + 'UL' in c, 'build ID not consumed')
        N.require('-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(len(a['shelf'])) + 'UL' in c, 'shelf size not consumed')
    tu = [c[c.index('-c') + 1] for c in commands[:73] if c[c.index('-c') + 1].endswith('/c2-stream-phase-02a.c')]
    N.require(len(tu) == 1, 'phase-02a translation unit population')
    source = N.bound(inputs[tu[0]]).decode()
    arrays = {}
    c2d = a['c2d']
    for name, raw, at in [('shelf', a['shelf'], 32), ('c2d', c2d, struct.unpack_from('<H', c2d, 28)[0])]:
        values = [BANK.crc16_ccitt_false(raw[at + i * 32:at + (i + 1) * 32]) for i in range(6)]
        expected = 'c2_phase02a_' + name + '_crc16:\\n' + '\\n'.join(f'.short 0x{x:04x}' for x in values) + '\\n'
        N.require(source.count(expected) == 1, 'derived CRC array drift: ' + name)
        arrays[name] = values
    N.require(struct.unpack_from('<I', c2d, 44)[0] == a['build_id'], 'C2D build ID drift')
    return dict(status='PASS', images=6, code_bytes=len(a['code']), shelf_bytes=len(a['shelf']),
                c2d_bytes=len(c2d), product_build_id=hex(a['build_id']), crc_arrays=arrays)


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
