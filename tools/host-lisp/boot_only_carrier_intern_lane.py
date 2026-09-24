"""Unchanged public-intern instrument on both carrier qualification worlds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/ov-crc16-r1/intern-lane.py'
raw = source.read_text()
changes = {
    'HERE=Path(__file__).resolve().parent': "HERE=ROOT/'build/boot-only-carrier-r1'",
    'build/ov-crc16-intern-lane-': 'build/boot-only-carrier-intern-lane-',
}
for old, new in changes.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
