"""Existing lane/GC instruments, rebound to the immediate carrier world."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'tools/host-lisp/ov_crc16_qualification.py'
raw = source.read_text()
raw = raw[raw.index('from pathlib import Path'):]
changes = {
    'build/ov-crc16-ready-instrument-r1': 'build/code-object-cache-ready-instrument-r1',
    'build/ov-crc16-product-r1-preflight': 'build/code-object-cache-product-r3-preflight',
    'build/ov-crc16-r1/': 'build/code-object-cache-card-r3/',
    "build/ov-crc16-r1'": "build/code-object-cache-card-r3'",
    'build/ov-crc16-': 'build/code-object-cache-',
    "'ov-crc16-seed-medium-r1'": "'code-object-cache-seed-medium-r1'",
    'build/export-publication-r1/': 'build/put-kit-r4/',
    'build/export-publication-ready-instrument-r1/': 'build/put-kit-ready-instrument-r2/',
    'build/export-publication-seed-medium-r1': 'build/put-kit-seed-medium-r1',
    "'export-publication-seed-medium-r1'": "'put-kit-seed-medium-r1'",
    "authority='0a41035d'": "authority='ed617afb'",
}
raw = re.sub('|'.join(re.escape(k) for k in sorted(changes, key=len, reverse=True)),
             lambda m: changes[m[0]], raw)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
