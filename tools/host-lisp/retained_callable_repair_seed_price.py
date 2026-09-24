"""Retained-callable repair Seed price on the unchanged storage geometry oracle.

Pure rebinding of the index-crc first-price oracle (as boot_only_carrier_seed_price.py
and ov_crc16_seed_price.py do): predecessor is the accepted dirty-anchor Final
ELF, candidate is this card's Seed ELF.  Adds the owner floors of the binding
(ordinary text, .rodata, E000, capture, high BSS, soft frames and metadata,
CRT zero interval) as exact equalities, and the two member sections.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/dirty-anchor-final-r3/',
    'build/index-crc-product-r1/': 'build/retained-callable-repair-product-r1/',
    'index-crc-seed-price.json': 'retained-callable-repair-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
seam = "out.write_text(json.dumps(result,indent=2)+'\\n')"
assert raw.count(seam) == 1
raw = raw.replace(seam, """import hashlib
assert hashlib.sha256(BASE.read_bytes()).hexdigest()=='6aa3040c3f6533a94c053b7b64b932be15514d856dd05f675da771a1f1ea1811'
for key in ('text_bytes','ordinary_text_free','rodata_bytes','rodata_free','E000_free','capture_free',
            'frame_start','frame_bytes','metadata_start','metadata_bytes','high_bss_free','CRT_zero_bytes'):
    assert new[key]==old[key],key
members={'.lisp65_rt_c2d_12','.lisp65_rt_c2append_journal_prepare'}
assert {d['section'] for d in deltas}==members,deltas
result['members']={d['section']:d for d in deltas}
result['owner_floors_unchanged']=True
result['status']='PASS: SEED PRICE; RESIDENT OWNERS UNCHANGED, TWO SESSION SLICES CHANGED'
result['budget']=dict(seed=1,final=0,product_link=0)
"""+seam)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
