"""Existing GC instruments, rebound to the repair Final (baseline) vs the nested-error recovery Seed (candidate)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'tools/host-lisp/ov_crc16_qualification.py'
raw = source.read_text()
raw = raw[raw.index('from pathlib import Path'):]
changes = {
    'build/ov-crc16-ready-instrument-r1': 'build/nested-error-recovery-ready-instrument-r1',
    'build/ov-crc16-product-r1-preflight': 'build/nested-error-recovery-product-r1-preflight',
    'build/ov-crc16-r1/': 'build/nested-error-recovery-r1/',
    "build/ov-crc16-r1'": "build/nested-error-recovery-r1'",
    'build/ov-crc16-': 'build/nested-error-recovery-',
    "'ov-crc16-seed-medium-r1'": "'nested-error-recovery-seed-medium-r1'",
    'build/export-publication-r1/': 'build/retained-callable-repair-r2/',
    'build/export-publication-ready-instrument-r1/': 'build/dirty-anchor-ready-instrument-r1/',
    'build/export-publication-seed-medium-r1': 'build/retained-callable-repair-seed-medium-r2',
    "'export-publication-seed-medium-r1'": "'retained-callable-repair-seed-medium-r2'",
    "authority='0a41035d'": "authority='90b5f9f2'",
}
raw = re.sub('|'.join(re.escape(k) for k in sorted(changes, key=len, reverse=True)),
             lambda m: changes[m[0]], raw)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
