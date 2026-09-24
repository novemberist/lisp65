"""Existing lane/GC instruments, rebound to anchor Final (baseline) vs repair Seed (candidate)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'tools/host-lisp/ov_crc16_qualification.py'
raw = source.read_text()
raw = raw[raw.index('from pathlib import Path'):]
changes = {
    'build/ov-crc16-ready-instrument-r1': 'build/dirty-anchor-ready-instrument-r1',
    'build/ov-crc16-product-r1-preflight': 'build/retained-callable-repair-product-r1-preflight',
    'build/ov-crc16-r1/': 'build/retained-callable-repair-r1/',
    "build/ov-crc16-r1'": "build/retained-callable-repair-r1'",
    'build/ov-crc16-': 'build/retained-callable-repair-',
    "'ov-crc16-seed-medium-r1'": "'retained-callable-repair-seed-medium-r1'",
    'build/export-publication-r1/': 'build/dirty-anchor-card-r1/',
    'build/export-publication-ready-instrument-r1/': 'build/dirty-anchor-ready-instrument-r1/',
    'build/export-publication-seed-medium-r1': 'build/dirty-anchor-seed-medium-r1',
    "'export-publication-seed-medium-r1'": "'dirty-anchor-seed-medium-r1'",
    "authority='0a41035d'": "authority='e0be22c1'",
}
raw = re.sub('|'.join(re.escape(k) for k in sorted(changes, key=len, reverse=True)),
             lambda m: changes[m[0]], raw)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
