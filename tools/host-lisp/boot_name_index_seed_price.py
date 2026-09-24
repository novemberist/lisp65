"""Read the boot-name-index Seed map using the unchanged Storage geometry price gate.

Pure renaming derivation of native_diet_seed_price.py for the "boot-time
name index" card.  r5 resumes the card on the accepted Session-bank capacity
world (build/session-bank-alignment-product-r1) as predecessor instead of
the r4 native-diet predecessor; the output names this card's own r5 product.
Nothing here is executed as part of writing this file -- the
`raw.count(old) == 1` anchors below were checked against the live template
with a standalone text-only check before this file was created.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/session-bank-alignment-product-r1/',
    'build/index-crc-product-r1/': 'build/boot-name-index-product-r5/',
    'index-crc-seed-price.json': 'boot-name-index-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
