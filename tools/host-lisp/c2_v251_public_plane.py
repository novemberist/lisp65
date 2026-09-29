#!/usr/bin/env python3
"""Bind the accepted Lisp plane to public sources and derived native constants."""
import json,struct
from pathlib import Path
import c2_v251_public_native as N
import runtime_overlay_bank as BANK
ROOT=N.ROOT
AUTHORITY=ROOT/'config/c2-v251-public-plane/inputs.json'

def check():
    a=json.loads(AUTHORITY.read_text())
    for row in a['files']:N.bound(row)
    for row in a['inputs']:N.bound(row['source'])
    product=json.loads(N.bound(a['product']))
    for row in product['manifests']+list(product['artifacts'].values()):N.bound(row)
    shelf=N.bound(product['artifacts']['shelf'])
    bid=struct.unpack_from('<I',shelf,22)[0]
    N.require(bid==product['product_build_id_u32']==int(product['product_build_id_hex'],16),'derived build ID drift')
    replay=json.loads((ROOT/'config/c2-v251-public-replay.json').read_text())
    inputs={r['materialized_path']:r['source'] for r in replay['inputs']}
    commands=replay['commands']
    for c in commands[:73]:
        N.require('-DLISP65_C2_PRODUCT_BUILD_ID='+product['product_build_id_hex']+'UL' in c,'build ID not consumed')
        N.require('-DLISP65_C2_PRODUCT_SHELF_BYTES='+str(len(shelf))+'UL' in c,'shelf size not consumed')
    source=N.bound(inputs[commands[29][commands[29].index('-c')+1]]).decode()
    c2d=N.bound(next(r['source'] for r in a['inputs'] if r['materialized_path'].endswith('initial.c2d-v6.bin')))
    arrays={}
    for name,raw,at in [('shelf',shelf,32),('c2d',c2d,struct.unpack_from('<H',c2d,28)[0])]:
        values=[BANK.crc16_ccitt_false(raw[at+i*32:at+(i+1)*32]) for i in range(6)]
        expected='c2_phase02a_'+name+'_crc16:\\n'+'\\n'.join(f'.short 0x{x:04x}' for x in values)+'\\n'
        N.require(source.count(expected)==1,'derived CRC array drift: '+name);arrays[name]=values
    # Re-emit all six images and shelf from the projected Lisp manifests/blobs.
    import c2_full_emission as F
    images=[F.emit_image(Path(r['path']).name.removesuffix('.manifest.json'),
        'stdlib' if i==0 else Path(r['path']).name.removesuffix('.manifest.json'),N.local(r['path']))
        for i,r in enumerate(product['manifests'])]
    generated,_,_=F.build_shelf(images)
    N.require(generated==shelf,'public six-image shelf regeneration drift')
    code=b''.join(i.code for i in images)
    expected=N.bound(next(r['source'] for r in a['inputs'] if r['materialized_path'].endswith('bank2-static-code.bin')))
    N.require(code==expected,'public static code regeneration drift')
    return dict(status='PASS',images=len(images),code_bytes=len(code),shelf_bytes=len(shelf),product_build_id=hex(bid),crc_arrays=arrays)
if __name__=='__main__':print(json.dumps(check(),indent=2))
