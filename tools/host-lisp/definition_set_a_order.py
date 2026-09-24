"""Retain the exact native 5/6 visibility witness on the Set-A Seed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/definition-pricing-r1/order-witness.py'
raw = source.read_text()
for old, new in {
    'build/definition-publication-order-r1': 'build/definition-set-a-order-r1',
    'build/append-name-trace-inspect-r1/receipt.json': 'build/definition-set-a-seed-medium-r1/packed-receipt.json',
    "truth = ElfTruth.read(": "base['binary'] = R.bind(ROOT/'build/append-name-pricing-r1/observer/build/bin/xmega65.native')\ntruth = ElfTruth.read(",
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
