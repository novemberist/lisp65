"""Card L catalog/media successor, preserving the historical Link-40 profile check."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import runtime_overlay_bank as B
import d81_persistence_fault as D81
import c2_lite_v6_roots_fronts_product_profile as P

ROOT=P.ROOT
HERE=ROOT/'build/card-l-seed-medium-r1/media-seed'
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/card-l-media-manifest-receipt-20260925.json'
ELF_SHA='7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
D81_SHA='bf9b829be99a737f6593d97eaf97eb9512f2a5d5111a6759cd8a87fdf54e561c'

def digest(raw):return hashlib.sha256(raw).hexdigest()

def validate(files,manifests):
    checked=[]
    for name,count in [('BOOT.BIN',17),('SESSION.BIN',56)]:
        raw=files[name.encode()];m=manifests[name]
        assert digest(raw)==m['storage']['sha256']
        assert B.HEADER.unpack_from(raw)[4]==m['catalog']['slice_count']==len(m['slices'])==count
        assert [r['id'] for r in m['slices']]==list(range(count))
        fresh=bytearray(raw);B._refresh_catalog_crcs(fresh);assert fresh==raw
        for row in m['slices']:
            at=B.HEADER_SIZE+row['id']*B.ENTRY_SIZE
            record=bytearray(raw[at:at+B.ENTRY_SIZE]);v=B.ENTRY.unpack(record)
            struct.pack_into('<H',record,22,0)
            assert v[10]==B.crc16_ccitt_false(record)==row['record_crc16']
            assert (v[0],v[1],v[3],v[4],v[5],v[6])==(row['id'],row['flags'],row['file_size'],row['vma'],row['memory_size'],row['entry_offset'])
            address=v[2]|(((v[11]>>8)&15)<<16)|(((v[11]>>16)&255)<<20)
            assert address==row['source_address'] and (v[11]&255)==row['region_id']
            start=row['file_offset'];n=row['file_size'];region=row['region_id']
            payload=raw[start:start+n] if region==0 else files[b'REGION1.BIN'][start:start+n] if region==1 else files[b'CODE.BIN'][address-0x20000:address-0x20000+n]
            assert len(payload)==n and digest(payload)==row['sha256'] and B.crc16_ccitt_false(payload)==v[9]==row['crc16']
            checked.append(dict(family=name,slot=row['id'],bytes=n,sha256=digest(payload)))
    marker=(ROOT/'build/card-l-r1/card-l-marker.bin').read_bytes()
    assert digest(marker)=='b504c29be383360f3f5257e03ca795f7930b8ec146f09632025c3b846038e3bf'
    assert files[b'BOOT.BIN'][0x4e00:0x6e00]==marker
    slot=manifests['SESSION.BIN']['slices'][55]
    payload=files[b'SESSION.BIN'][slot['file_offset']:slot['file_offset']+slot['file_size']]
    assert payload[593:597]==bytes.fromhex('0020727b')
    return checked

def inputs():
    elf=ROOT/'build/card-l-product-r1/wplto/resident-island-seed.prg.elf'
    medium=HERE/'card-l.d81'
    assert digest(elf.read_bytes())==ELF_SHA and digest(medium.read_bytes())==D81_SHA
    return D81.visible_files(medium.read_bytes()), {name:json.loads((HERE/path).read_text()) for name,path in [('BOOT.BIN','boot-manifest.json'),('SESSION.BIN','session-manifest.json')]}

def selftest():
    P.selftest()
    files,manifests=inputs();validate(files,manifests);trials=[]
    for name,old in [('BOOT.BIN',12),('SESSION.BIN',55)]:
        m=deepcopy(manifests);m[name]['catalog']['slice_count']=old;trials.append((name+'-old-count',files,m))
        m=deepcopy(manifests);m[name]['slices'].pop();trials.append((name+'-missing-record',files,m))
        f=dict(files);r=bytearray(f[name.encode()]);r[-1]^=1;f[name.encode()]=bytes(r);trials.append((name+'-payload-corruption',f,manifests))
    m=deepcopy(manifests);m['SESSION.BIN']['slices'][55]['source_address']+=256;trials.append(('source-address-drift',files,m))
    m=deepcopy(manifests);m['BOOT.BIN']['slices'][16]['record_crc16']^=1;trials.append(('record-crc-drift',files,m))
    rejected=[]
    for label,f,m in trials:
        try:validate(f,m)
        except AssertionError:rejected.append(label)
        else:raise AssertionError('surviving mutation '+label)
    print('Card L media: SELFTEST PASS inherited-mutations=4 new-mutations=8')
    return rejected

def derive():
    files,manifests=inputs();rows=validate(files,manifests)
    baseline=ROOT/'build/nested-error-recovery-seed-medium-r1/packed/hardware-sp-seed.d81'
    old=D81.visible_files(baseline.read_bytes());assert files[b'CODE.BIN']==old[b'CODE.BIN']
    comfort=ROOT/'build/card-l-seed-medium-r1/comfort/card-l-comfort.d81'
    assert digest(comfort.read_bytes())=='2c9a6ec3bc73c71575ce9becaac00216eeedab3157f94506ba122fc3d1817945'
    companion=D81.visible_files(comfort.read_bytes())
    assert set(companion)==set(files)|{b'REPL-COMFORT'}
    assert all(companion[k]==v for k,v in files.items() if k!=b'L65INDEX')
    return dict(status='PASS: CARD L MEDIA SUCCESSOR',date='2026-09-25',historical_profile=P.check(),
        predecessors=[P.bind(ROOT/'build/nested-error-recovery-seed-medium-r1/packed-receipt.json'),P.bind(ROOT/'tools/host-lisp/c2_v240_public_overlays.py')],
        catalogs=dict(session=56,boot=17),records=rows,mutations=selftest(),
        inputs=[P.bind(p) for p in [HERE/'card-l.d81',HERE/'boot-manifest.json',HERE/'session-manifest.json',comfort,Path(__file__)]],
        bank2_unchanged=True,comfort_runtime_files_identical=True,product_builds=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','selftest','check']);a=p.parse_args()
    if a.action=='selftest':selftest();return
    value=derive()
    if a.action=='prepare':assert not RECEIPT.exists();RECEIPT.write_text(json.dumps(value,indent=2)+'\n')
    else:assert json.loads(RECEIPT.read_text())==value,'dated receipt differs'
    print('Card L media: CHECK PASS Session=56 Boot=17 records=73 Bank-2 unchanged Comfort runtime identical builds=0')
if __name__=='__main__':main()
