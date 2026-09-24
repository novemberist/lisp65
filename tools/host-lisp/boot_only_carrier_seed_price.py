"""Carrier Seed price using the existing physical storage geometry oracle."""
from pathlib import Path
import boot_only_carrier_elf_gate as CARRIER

ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'build/index-crc-r1/seed-price.py'
raw=source.read_text()
for old,new in {
    'build/storage-owner-product-r2/':'build/ov-crc16-product-r1/',
    'build/index-crc-product-r1/':'build/boot-only-carrier-product-r1/',
    'index-crc-seed-price.json':'boot-only-carrier-seed-price.json',
}.items():
    assert raw.count(old)==1
    raw=raw.replace(old,new,1)
seam="out.write_text(json.dumps(result,indent=2)+'\\n')"
assert raw.count(seam)==1
raw=raw.replace(seam,"""recovered=new['ordinary_text_free']-old['ordinary_text_free']
assert recovered>=600, 'ordinary text recovery below bound'
assert new['rodata_bytes']==old['rodata_bytes'], 'rodata changed'
result['carrier']=CARRIER.check(ELF)
result['ordinary_text_recovered']=recovered
result['status']='PASS: CARRIER SEED PRICE AND STORAGE GEOMETRY'
"""+seam)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__,CARRIER=CARRIER))
