"""Read the native-diet Seed map using the unchanged Storage geometry price gate.

Predecessor is the accepted Set-A Final ELF; the output names the card.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/definition-set-a-product-r2/',
    'build/index-crc-product-r1/': 'build/native-diet-product-r4/',
    'index-crc-seed-price.json': 'native-diet-fourth-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
