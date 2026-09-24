"""Read the Set-A Seed map using the unchanged Storage geometry price gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/transient-retirement-product-r1/',
    'build/index-crc-product-r1/': 'build/definition-set-a-product-r1/',
    'index-crc-seed-price.json': 'definition-set-a-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
