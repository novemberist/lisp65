"""Unchanged lane/GC instruments rebound to the immediate ov_crc16 predecessor."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
template=ROOT/'tools/host-lisp/ov_crc16_qualification.py'
raw=template.read_text()
raw=raw[raw.index('from pathlib import Path'):]
changes={
    'build/ov-crc16-':'build/boot-only-carrier-',
    "'ov-crc16-seed-medium-r1'":"'boot-only-carrier-seed-medium-r1'",
    'build/export-publication-r1/':'build/ov-crc16-r1/',
    'build/export-publication-ready-instrument-r1/':'build/ov-crc16-ready-instrument-r1/',
    'build/export-publication-seed-medium-r1':'build/ov-crc16-seed-medium-r1',
    "'export-publication-seed-medium-r1'":"'ov-crc16-seed-medium-r1'",
    "authority='0a41035d'":"authority='4cd7eac3'",
}
raw=re.sub('|'.join(re.escape(k) for k in sorted(changes,key=len,reverse=True)),
           lambda m:changes[m[0]],raw)
exec(compile(raw,str(template),'exec'),dict(__name__='__main__',__file__=__file__))
