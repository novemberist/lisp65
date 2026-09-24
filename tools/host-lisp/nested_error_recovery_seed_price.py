"""Nested-error recovery Seed price on the unchanged storage geometry oracle.

Pure rebinding of the index-crc first-price oracle (as the retained-callable
repair price did): predecessor is the accepted retained-callable repair Final
ELF, candidate is this card's Seed ELF.  Every resident owner is compared as an
exact equality except ordinary text, which absorbs the one changed function
(.text.c2_abort_empty_journal) and must stay at or above its 32-byte floor.
No allocated section other than .text may change size.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/retained-callable-repair-final-r1/',
    'build/index-crc-product-r1/': 'build/nested-error-recovery-product-r1/',
    'index-crc-seed-price.json': 'nested-error-recovery-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
seam = "out.write_text(json.dumps(result,indent=2)+'\\n')"
assert raw.count(seam) == 1
raw = raw.replace(seam, """import hashlib
assert hashlib.sha256(BASE.read_bytes()).hexdigest()=='815b60a5fb4baf405d5b8e14dac5ad9e593c9bf3f73877efc6b6f63499dc26a1'
for key in ('rodata_bytes','rodata_free','E000_free','capture_free',
            'frame_start','frame_bytes','metadata_start','metadata_bytes','high_bss_free','CRT_zero_bytes'):
    assert new[key]==old[key],key
grow=after.symbol('c2_abort_empty_journal_derived').bytes-before.symbol('c2_abort_empty_journal_derived').bytes
assert {d['section'] for d in deltas}=={'.text'},deltas
assert new['text_bytes']-old['text_bytes']==grow
assert new['ordinary_text_free']==old['ordinary_text_free']-grow>=new['text_floor']
result['changed_function']=dict(name='c2_abort_empty_journal_derived',
    before=dict(address=before.symbol('c2_abort_empty_journal_derived').value,bytes=before.symbol('c2_abort_empty_journal_derived').bytes),
    after=dict(address=after.symbol('c2_abort_empty_journal_derived').value,bytes=after.symbol('c2_abort_empty_journal_derived').bytes),
    delta=grow)
result['owner_floors_unchanged']=True
result['status']='PASS: SEED PRICE; ONE ORDINARY-TEXT FUNCTION GROWS, EVERY OTHER RESIDENT OWNER UNCHANGED'
result['budget']=dict(seed=1,final=0,product_link=0)
"""+seam)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
