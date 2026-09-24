"""Measure the grouped Seed using the existing witnessed lcc-run/Append ledger."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/definition-ledger-r1/full-r2.py'
raw = source.read_text()
for old, new in {
    "f'build/definition-ledger-full-{slots}-r2'": "f'build/definition-set-a-ledger-{slots}-r2'",
    'build/append-name-trace-inspect-r1/receipt.json': 'build/definition-set-a-seed-medium-r1/packed-receipt.json',
    'build/transient-retirement-final-medium-r1/': 'build/definition-set-a-seed-medium-r1/',
    'range(3 + 3*slots)': 'range(1)',
    'i == 2+3*slots': 'i == 0',
    "assert m.memory_range(append, 2) == bytes.fromhex('8609')":
        "assert truth.symbol('c2_ready').value < 256\n    assert m.memory_range(append, 2) == bytes([0xa4, truth.symbol('c2_ready').value])",
}.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
