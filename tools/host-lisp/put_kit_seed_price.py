"""Read-only price of the sole Put-Kit Seed; inherited physical owner oracle."""
from pathlib import Path
import boot_only_carrier_elf_gate as CARRIER

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for before, after in {
    'build/storage-owner-product-r2/': 'build/boot-only-carrier-product-r1/',
    'build/index-crc-product-r1/': 'build/put-kit-product-r4/',
    'index-crc-seed-price.json': 'put-kit-seed-price.json',
}.items():
    assert raw.count(before) == 1
    raw = raw.replace(before, after)
seam = "out.write_text(json.dumps(result,indent=2)+'\\n')"
assert raw.count(seam) == 1
raw = raw.replace(seam, """assert new['rodata_bytes']==old['rodata_bytes']
result['carrier']=CARRIER.check(ELF)
result['text_cost']=old['ordinary_text_free']-new['ordinary_text_free']
encoded=json.dumps(result,indent=2)+'\\n'
if out.exists():
    assert out.read_text()==encoded, 'price is immutable'
else:
    out.write_text(encoded)
""")
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__, CARRIER=CARRIER))
