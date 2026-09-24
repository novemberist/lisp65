"""Existing lane/GC instruments, rebound to the immediate carrier world."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'tools/host-lisp/ov_crc16_qualification.py'
raw = source.read_text()
raw = raw[raw.index('from pathlib import Path'):]
changes = {
    'build/ov-crc16-ready-instrument-r1': 'build/put-kit-ready-instrument-r2',
    'build/ov-crc16-product-r1-preflight': 'build/put-kit-product-r4-preflight',
    'build/ov-crc16-r1/': 'build/put-kit-r4/',
    "build/ov-crc16-r1'": "build/put-kit-r4'",
    'build/ov-crc16-': 'build/put-kit-',
    "'ov-crc16-seed-medium-r1'": "'put-kit-seed-medium-r1'",
    'build/export-publication-r1/': 'build/boot-only-carrier-r1/',
    'build/export-publication-ready-instrument-r1/': 'build/boot-only-carrier-ready-instrument-r1/',
    'build/export-publication-seed-medium-r1': 'build/boot-only-carrier-seed-medium-r1',
    "'export-publication-seed-medium-r1'": "'boot-only-carrier-seed-medium-r1'",
    "authority='0a41035d'": "authority='3bd13625'",
}
raw = re.sub('|'.join(re.escape(k) for k in sorted(changes, key=len, reverse=True)),
             lambda m: changes[m[0]], raw)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
