"""Reuse the established lane/GC instruments on the replacement Seed."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
kind=sys.argv.pop(1)
names={'instrument':'ready-instrument','lanes':'native-lanes','gc':'gc-equal','vm':'vm-lanes'}
assert kind in names
source=ROOT/f'build/index-crc-r1/{names[kind]}.py'
raw=source.read_text()
for old,new in {
    'build/storage-owner-r2/ready-instrument.json':'build/transient-retirement-r2/ready-instrument.json',
    'build/storage-owner-ready-instrument-r2b/xemu':'build/transient-retirement-ready-instrument-r1/xemu',
    'build/index-crc-ready-instrument-r1b':'build/definition-set-a-auth-ready-instrument-r1',
    'build/storage-owner-final-medium-r2':'build/transient-retirement-final-medium-r1',
    "'storage-owner-final-medium-r2'":"'transient-retirement-final-medium-r1'",
    'build/index-crc-seed-medium-r1':'build/definition-set-a-seed-medium-r2',
    "'index-crc-seed-medium-r1'":"'definition-set-a-seed-medium-r2'",
    'build/index-crc-r1/ready-instrument.json':'build/definition-set-a-r3/ready-instrument.json',
    'build/index-crc-native-':'build/definition-set-a-auth-native-',
    'build/index-crc-gc-equal-':'build/definition-set-a-auth-gc-equal-',
    'build/index-crc-seed-vm-lanes-r1':'build/definition-set-a-auth-vm-lanes-r1',
    'build/index-crc-product-r1-preflight':'build/definition-set-a-product-r3-preflight',
    "authority='4cf5a2f9'":"authority='20e4aa49'",
}.items():raw=raw.replace(old,new)
raw=raw.replace('HERE=Path(__file__).resolve().parent',"HERE=ROOT/'build/definition-set-a-r3'")
needle="exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))"
if needle in raw:
    raw=raw.replace(needle,"raw=raw.replace('HERE=Path(__file__).resolve().parent',\"HERE=ROOT/'build/definition-set-a-r3'\")\n"+needle)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
