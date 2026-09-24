"""Unchanged native public-intern protocol on Put-Kit and carrier worlds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'build/ov-crc16-r1/intern-lane.py'
raw = source.read_text()
for old, new in {
    'HERE=Path(__file__).resolve().parent': "HERE=ROOT/'build/put-kit-r4'",
    'build/ov-crc16-intern-lane-': 'build/put-kit-intern-lane-',
}.items():
    assert raw.count(old) == 1
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
