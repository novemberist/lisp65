"""Read the session-bank-alignment Seed map using the unchanged Storage
geometry price gate.

Predecessor is the accepted native-diet Final ELF; the output names the
card. Pure renaming derivation of native_diet_seed_price.py, the same way
boot_name_index_seed_price.py derives from it.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/index-crc-r1/seed-price.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-product-r2/': 'build/native-diet-product-r4/',
    'build/index-crc-product-r1/': 'build/session-bank-alignment-product-r1/',
    'index-crc-seed-price.json': 'session-bank-alignment-seed-price.json',
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new, 1)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
