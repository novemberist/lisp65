"""Read the ov_crc16 Seed map using the unchanged Storage geometry price gate.

Pure renaming derivation of export_publication_seed_price.py (itself a
renaming derivation of boot_name_index_seed_price.py, itself a renaming
derivation of native_diet_seed_price.py) for the "ov_crc16" card.
Predecessor is this card's own r1 world's predecessor, the accepted
export-publication Seed (build/export-publication-product-r2); the output
names this card's own r1 product. Nothing here is executed as part of
writing this file -- the `raw.count(old) == 1` anchors below were checked
against the live template with a standalone text-only check before this
file was created.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/export-publication-product-r2/',
    'build/index-crc-product-r1/': 'build/ov-crc16-product-r1/',
    'index-crc-seed-price.json': 'ov-crc16-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
